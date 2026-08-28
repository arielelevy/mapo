"""The experiment harness: run every paradigm on every task, then measure.

The full cross product is the point. Production would run one paradigm per task, but
the study needs the oracle, and the oracle is only knowable by having run them all.
That is what makes the numbers here checkable rather than asserted.

Results are appended incrementally and keyed by (task, paradigm, trial), so an
interrupted run resumes without redoing work. With `workers > 1` the ORDER of rows in
the file is nondeterministic: every row is self-contained so analysis is unaffected, but
the file is no longer a chronological log and must not be read as one. Wall-clock per
row also stops being a latency measurement once workers contend — token counts and
quality stay exact.
"""

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import feasibility, grading
import httpx

from .config import Settings
from .llm import RETRYABLE_STATUS
from .features import REGION_VOCABULARY, FeatureExtractor, Features, payload_for
from dataclasses import replace as dc_replace

from .beliefs import Provenance
from .decide import decide as decide_once
from .features import measure_continuation
from .llm import LLMClient, SealedCacheMiss, SeededClient, Usage
from .metrics import Observation, Study
from .fsio import exclusive
from .contracts import verify_coverage
from .paradigms import CATALOG, COST_PRIORS, FALLBACK, Infeasible, REGISTRY, RETIRED
from .embeddings import EmbeddingClient
from .retrieval import CorpusView, Retriever, build_arms
from .tools import VARIANTS, ToolSurface
from .assurance import Assurance
from .policy import Episode, Plasticity, PolicyBundle, promote
from .store import LearningStore


class _RetiredTaskCorpus:
    """Corpus view scoped to one task's units, with a pluggable retriever.

    Scoping matters: a paradigm must not be able to reach units the task did not
    supply, or high-cardinality tasks would leak into low-cardinality ones and the
    cardinality dial would stop meaning anything.

    The retriever is injected rather than hard-coded because retrieval quality decides
    which paradigm wins. Two of the seven search and four read, so a weak retriever
    handicaps the searchers and a perfect one makes reading pointless — either way the
    result would be about the tool rather than the topology. It is a controlled
    variable, recorded on every row.
    """

    def __init__(
        self,
        documents: dict[str, str],
        unit_ids: list[str],
        retriever: Retriever | None = None,
        task_id: str = "",
        relevant_units: list[str] | None = None,
    ) -> None:
        self._documents = documents
        self._unit_ids = list(unit_ids)
        self._retriever = retriever or LexicalRetriever()
        self._view = CorpusView(
            task_id=task_id,
            documents=documents,
            unit_ids=list(unit_ids),
            relevant_units=list(relevant_units or []),
        )

    def unit_ids(self) -> list[str]:
        return list(self._unit_ids)

    def read(self, unit_id: str) -> str:
        if unit_id not in self._unit_ids:
            # Not an empty string: a paradigm reaching outside its units is a bug we
            # want to see, not silently absorb.
            raise KeyError(f"Unit {unit_id} is not part of this task.")
        return self._documents[unit_id]

    def search(self, query: str, limit: int) -> list[tuple[str, str]]:
        ranked = self._retriever.rank(self._view, query, limit)
        return [(unit_id, self._documents[unit_id][:400]) for unit_id in ranked]


def _is_infrastructure(exc: BaseException) -> bool:
    """Whether this failure belongs to the transport rather than to the paradigm.

    Deliberately narrow. Anything not clearly infrastructural stays a paradigm failure
    and still scores zero, because the opposite mistake -- excusing a real bug as a
    network blip -- flatters the paradigm, which is the error this harness exists to
    avoid.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return isinstance(exc, (httpx.TransportError, httpx.StreamError))


@dataclass
class Row:
    task_id: str
    cell: str
    paradigm: str
    trial: int
    region: str
    utility: float
    cost_tokens: int
    calls: int
    wall_seconds: float
    iterations: int
    cross_unit_lookups: int
    hallucinated_units: int
    tool_usage: dict[str, Any]
    infeasible: bool
    retriever: str
    has_oracle: bool
    answer: str
    truth_coupling: float
    error: str = ""
    # An infrastructure failure is not a measurement. A 429 from the embedding
    # endpoint says nothing about the topology, so these rows are recorded and
    # then excluded from every statistic rather than scored as a wrong answer.
    infra_error: bool = False
    # CON QUE DECODIFICACION SE PRODUJO ESTA FILA. `config.py` dice desde siempre que la
    # huella «goes into every cache key and every result row», y en la fila NO ESTABA: el
    # registro no decia con que modelo se pago, y lo unico que separaba a `gpt-5-chat` de
    # `gpt-5.4-nano` era en que carpeta habia caido el archivo.
    #
    # Eso costo caro y se midio (R-1, 2026-08-28). Un replay sellado reconstruyo los
    # ajustes desde `Settings.from_env()` —que devuelve el primer modelo, congelado— y
    # fallo el 100% de las entradas sin que nada dijera por que: la clave de cache es
    # `sha256(fingerprint, payload)`, asi que un modelo distinto hace miss en todo aunque
    # el cache este intacto. Con la huella EN la fila, el replay la lee del registro en
    # vez de adivinarla, y `load_rows` puede negarse a mezclar.
    fingerprint: str = ""
    # CON QUE VOCABULARIO SE COMPUTO LA REGION. `features.REGION_VOCABULARY` lo declara y
    # su propio comentario dice para que: «un theta ajustado bajo un vocabulario nunca
    # debe consumir regiones de otro, y el EXPLAIN registra cual hablo la decision».
    # NADA LO ESTAMPABA.
    #
    # Es el mismo agujero que la huella de decodificacion, y con la misma consecuencia:
    # dos filas de vocabularios distintos son indistinguibles al leerlas, asi que se
    # promedian. P15 pago exactamente eso — el cuarto segmento del vocabulario le costo a
    # theta toda su confianza, y ninguna fila decia bajo cual habia sido computada.
    region_vocabulary: str = ""
    # EL SPLIT, y no es un detalle contable. `Usage` lo lleva desde siempre; la fila
    # guardaba solo el total, asi que la informacion se tiraba al escribir.
    #
    # Entrada y salida NO valen lo mismo —el precio de salida es varias veces el de
    # entrada— y los paradigmas se diferencian justo en esa proporcion: uno que relee el
    # contexto en cada vuelta gasta casi todo en entrada, uno que genera planes largos
    # gasta en salida. Sumarlos y multiplicar por un precio promedio borra la diferencia
    # que decide cual es mas barato DE VERDAD.
    #
    # Medido sobre el cache entero (`_analyze_spend.py`, 2026-08-28): la salida es el
    # 1,7% de los tokens. Eso valida que barrer lambda sobre el total sea un proxy
    # razonable ACA — no lo vuelve cierto en general, y sin el split por fila no se
    # puede saber si algun paradigma se sale de esa proporcion.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    # VEREDICTO DE `C-COMPLETE`, cuando la tarea declara un dominio enumerable.
    #
    # `None` = la tarea no declara dominio, o sea que NO HAY CONTRATO — distinto de un
    # contrato que se cumplio. Las dos cosas se ven igual en un booleano y son opuestas:
    # una dice «nadie verifico», la otra «se verifico y paso».
    #
    # Se registra aparte de `utility` a proposito. La utilidad es F1 contra el gold y
    # castiga igual una respuesta incompleta que una equivocada; el contrato separa esas
    # dos, que es lo que ninguna metrica de anclaje puede hacer.
    completeness: dict[str, Any] | None = None
    # EL VECTOR phi, QUE ES LO QUE EL ROUTER TIENE CUANDO DECIDE.
    #
    # No estaba en la fila, y esa ausencia explica P-5 entera: el descubrimiento de
    # particiones solo podia partir sobre lo que la fila guardaba —el oraculo del
    # extractor y tres variables posteriores— asi que ninguna particion descubierta era
    # EVALUABLE en el momento de decidir, y por eso nadie las consultaba.
    #
    # `region` ya estaba, pero es una funcion de estos valores y ya discretizada: partir
    # sobre una etiqueta categorica no encuentra el umbral, encuentra la grilla que
    # alguien eligio antes.
    #
    # `None` en un derivado significa NO ESTABLECIDO, nunca cero — es el contrato de
    # `Features` y se conserva al escribirlo.
    n_units: int = 0
    phi_coupling: float | None = None
    phi_horizon_unknown: bool | None = None
    phi_continuation: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


# Un aviso por archivo: repetirlo por fila lo vuelve ruido y deja de leerse.
_avisados: set[str] = set()


def load_rows(
    path: Path, include_infra: bool = False, expect: str | None = None,
) -> list[dict[str, Any]]:
    """Filas para analisis, desde un archivo. Las de `infra_error` se excluyen POR DEFECTO.

    ES FUNCION DE MODULO Y NO METODO, y esa es la correccion. Las dos guardas de mezcla
    —decodificacion y vocabulario de region— vivian adentro de `Runner`, que es la clase
    que CORRE. Todo analizador lee el `.jsonl` con `json.loads` a mano, asi que **ninguna
    de las dos protegia a quien analiza**: la forma que busca el barrido de hoy — una
    garantia completa por un camino que nadie toma.

    Las de `infra_error` se registran —el archivo las conserva— pero no son mediciones.
    Excluirlas solo en `study()` las dejaba filtrarse a `episodes()`, `replicates()` y
    `consolidate()`. Un solo porton, y ahora tambien del lado del analisis.
    """
    if not path.exists():
        return []
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    # DOS COSAS DISTINTAS, y confundirlas fue el primer intento de esta guarda.
    #
    # (1) EL ARCHIVO NO PUEDE MEZCLAR. "Nunca mezclar modelos en un mismo archivo de
    #     resume" era una regla escrita sostenida por convencion de directorio.
    #     Promediar entre modelos no mide un paradigma: mide el modelo. Eso es un
    #     error y levanta.
    #
    # (2) QUE EL LECTOR COINCIDA es otra pregunta, y para ANALIZAR no hace falta: un
    #     script que solo promedia filas no llama al modelo, asi que sus ajustes son
    #     irrelevantes. Levantar ahi obligaria a todo analizador a reconstruir un
    #     endpoint que no va a usar.
    #
    #     Pero AVISA, porque es exactamente la confusion que dejo a R-1 sin concluir:
    #     un replay sellado reconstruyo `Settings.from_env()` —el primer modelo, que
    #     quedo congelado— y fallo el 100% de las entradas sin que nada dijera por que.
    #     Un replay con los ajustes equivocados no puede acertar una sola clave.
    seen = sorted({r["fingerprint"] for r in rows if r.get("fingerprint")})
    if len(seen) > 1:
        raise ValueError(
            f"{path.name} mezcla decodificaciones: {seen}. Promediar "
            f"entre modelos no mide un paradigma: mide el modelo. Separa los archivos."
        )
    # Y LO MISMO PARA EL VOCABULARIO DE REGION, por la misma razon. Una region es una
    # etiqueta cuyo significado lo fija el vocabulario que la produjo; dos filas de
    # vocabularios distintos llevan la misma etiqueta queriendo decir cosas distintas.
    vocabs = sorted({r["region_vocabulary"] for r in rows
                     if r.get("region_vocabulary")})
    if len(vocabs) > 1:
        raise ValueError(
            f"{path.name} mezcla vocabularios de region: {vocabs}. Una "
            f"region significa lo que su vocabulario dice que significa, asi que "
            f"promediarlas compara etiquetas que no nombran lo mismo."
        )
    # `expect` ausente = quien llama no decodifica nada, asi que no hay con
    # que comparar. No es «coincide»: es «no aplica».
    if expect and seen and seen[0] != expect and path.name not in _avisados:
        _avisados.add(path.name)
        print(
            f"  [aviso] {path.name} se produjo bajo {seen[0]!r} y esta "
            f"sesion es {expect!r}. Para ANALIZAR no importa; para un REPLAY SELLADO "
            f"falla el 100% de las claves, que es como R-1 quedo sin concluir."
        )

    if include_infra:
        return rows
    return [r for r in rows if not r.get("infra_error")]


class Runner:
    # Una vez por proceso. Un aviso que se repite por cada lectura se vuelve ruido y deja
    # de leerse, que es la forma en que un aviso deja de ser un aviso.

    def __init__(
        self,
        settings: Settings,
        corpus_name: str,
        sealed: bool = False,
        retriever_arm: str = "hybrid",
        surface_variant: str = "basic",
        stop_on_barren: int = 0,
        offer_read_all: bool = False,
    ) -> None:
        # Hybrid is the default because it is what a real deployment has. The degraded
        # arms exist to test whether the conclusion depends on retrieval quality, not to
        # produce the headline number.
        embedder = EmbeddingClient(
            settings, settings.embedding_deployment, sealed=sealed
        )
        arms = build_arms(embedder=embedder)
        if retriever_arm not in arms:
            raise ValueError(
                f"Unknown retriever arm {retriever_arm!r}. Available: {sorted(arms)}"
            )
        if surface_variant not in VARIANTS:
            raise ValueError(
                f"Unknown surface variant {surface_variant!r}. Use one of {VARIANTS}."
            )
        self.surface_variant = surface_variant
        self.retriever_arm = retriever_arm
        # FACTOR, no patron: se aplica o no a TODOS los brazos por igual, asi que se mide
        # cruzado `{con, sin} x {patrones}`. `0` lo apaga, que es el default — encenderlo
        # cambia lo que los paradigmas pueden hacer, asi que sus filas NO son comparables
        # con las de una corrida sin el y van a otro archivo.
        self.stop_on_barren = stop_on_barren
        # Mismo razonamiento: cambia lo que el paradigma PUEDE hacer, asi que es
        # factor, apagado por defecto, y sus filas van a otro archivo.
        self.offer_read_all = offer_read_all
        self._retriever = arms[retriever_arm]
        # Kept so the surface can expose lexical and dense SEPARATELY alongside the
        # fused entry point. Offering only the fused view took the choice of modality
        # away from the agent, and that choice is part of the topology.
        self._arms = arms
        self._settings = settings
        self._client = LLMClient(settings, sealed=sealed)
        self._extractor = FeatureExtractor(self._client)

        root = settings.corpus_dir / corpus_name
        self._documents: dict[str, str] = json.loads(
            (root / "documents.json").read_text(encoding="utf-8")
        )
        self._tasks: list[dict[str, Any]] = json.loads(
            (root / "tasks.json").read_text(encoding="utf-8")
        )
        self._corpus_name = corpus_name
        # One file per (corpus, retriever arm). Pooling arms would average over the
        # very variable the arms exist to separate.
        suffix = "" if retriever_arm == "hybrid" else f"_{retriever_arm}"
        if surface_variant != "basic":
            suffix += f"_{surface_variant}"
        # Un factor que cambia lo que el paradigma PUEDE hacer separa archivos, por la
        # misma razon que los separa el brazo de recuperacion: promediar dos condiciones
        # en un mismo `.jsonl` mide el promedio de dos experimentos, no uno.
        if stop_on_barren:
            suffix += f"_stop{stop_on_barren}"
        if offer_read_all:
            suffix += "_readall"
        self._results_path = (
            settings.results_dir / f"{corpus_name}{suffix}_rows.jsonl"
        )
        self.store = LearningStore(settings.results_dir, corpus_name)

    # -- features ----------------------------------------------------------

    def decide_for(
        self,
        task: dict[str, Any],
        router: Any,
        candidates: list[str],
        region: str,
        requested: Any = None,
        resolve_probes: bool = False,
        client: Any = None,
    ) -> Any:
        """One decision for the bench, through the SAME cycle the product uses.

        `resolve_probes` is opt-in and off by default, for two reasons. It spends a
        model call per probing task — real money that the caller has to choose to
        spend — and it changes what a decision IS on any task where the probe rule
        fires, which must never happen underneath a prediction already registered
        against the single-step behaviour.

        With it off, this is exactly what `report()` always did: one `plan()` call,
        and on a probing task the answer is a placeholder rather than a decision.
        `Decision.unresolved` is what says so, instead of the caller having to know.
        """
        features = self.features_for(task, allow_derived=False)
        features = dc_replace(
            features,
            continuation=measure_continuation(self._documents, task["unit_ids"]),
        )
        return decide_once(
            task,
            router=router,
            features=features,
            candidates=candidates,
            requested=requested,
            client=client if resolve_probes else None,
            surface=self.surface_for(task) if resolve_probes else None,
            probe=resolve_probes,
        )

    def surface_for(self, task: dict[str, Any]) -> ToolSurface:
        """The tool surface for one task, built the same way the grid builds it.

        Extracted from `run_cross_product`'s local closure so that anything outside the
        measurement loop -- the probe, the /decide endpoint -- gets the SAME surface a
        paradigm would get. A second construction of it elsewhere would be a second
        definition of what the agent can see.
        """
        view = CorpusView(
            task_id=task["task_id"],
            documents=self._documents,
            unit_ids=task["unit_ids"],
            relevant_units=task.get("relevant_units", []),
        )
        return ToolSurface(
            view=view,
            hybrid=self._retriever,
            semantic=self._arms["semantic"],
            lexical=self._arms["lexical"],
            variant=self.surface_variant,
            budget_tokens=int(task["budget_tokens"]),
            stop_on_barren=self.stop_on_barren,
            offer_read_all=self.offer_read_all,
        )

    def features_for(self, task: dict[str, Any], allow_derived: bool) -> Features:
        features, _ = self._extractor.extract(
            payload_for(task), allow_derived=allow_derived
        )
        # Continuation is measured from the material itself — free, deterministic,
        # COMPUTED. This is the axis whose absence P15 paid for.
        return dc_replace(
            features,
            continuation=measure_continuation(self._documents, task["unit_ids"]),
        )

    # -- execution ---------------------------------------------------------

    def existing_keys(self) -> set[tuple[str, str, int]]:
        if not self._results_path.exists():
            return set()
        keys: set[tuple[str, str, int]] = set()
        for line in self._results_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            keys.add((row["task_id"], row["paradigm"], row.get("trial", 0)))
        return keys

    def run_cross_product(
        self,
        paradigms: list[str] | None = None,
        limit: int | None = None,
        resume: bool = True,
        repeat: int = 1,
        task_ids: list[str] | None = None,
        workers: int = 1,
    ) -> list[Row]:
        """Como `_run_cross_product`, con un solo escritor por archivo de resultados.

        Dos corridas sobre el mismo corpus escriben las MISMAS celdas en el mismo
        `.jsonl`, y `study()` promedia por celda contando cada fila: la celda duplicada
        pesa el doble y ninguna estadistica lo denuncia. El lock convierte eso en una
        excepcion, que es la unica forma de enterarse.
        """
        with exclusive(self._results_path, owner=f"corpus={self._corpus_name}"):
            return self._run_cross_product(
                paradigms=paradigms, limit=limit, resume=resume,
                repeat=repeat, task_ids=task_ids, workers=workers,
            )

    def _run_cross_product(
        self,
        paradigms: list[str] | None = None,
        limit: int | None = None,
        resume: bool = True,
        repeat: int = 1,
        task_ids: list[str] | None = None,
        workers: int = 1,
    ) -> list[Row]:
        """Run the cross product, `repeat` times per cell.

        repeat > 1 is what makes the noise floor measurable. Since gpt-5-chat refuses
        an explicit temperature, one trial per cell cannot separate a real paradigm
        difference from sampling noise, and the oracle is biased upward by that noise.
        """
        if repeat < 1:
            raise ValueError("repeat must be >= 1")
        if paradigms:
            blocked = sorted(set(paradigms) & RETIRED)
            if blocked:
                # La razon Y la condicion de revival viajan con el rechazo. Un error que
                # solo dice "no se corre" obliga a ir a buscar por que a un documento —
                # que es exactamente como una decision empieza a vivir en dos lados.
                lines = []
                for name in blocked:
                    entry = CATALOG[name]
                    line = f"  {name} [{entry.status.value}]: {entry.reason}"
                    if entry.revives_when:
                        line += f"\n    revive si: {entry.revives_when}"
                    lines.append(line)
                raise ValueError(
                    f"Estos paradigmas no se corren:\n{chr(10).join(lines)}\n"
                    "Su dato historico se replaya desde las filas ya pagadas."
                )
        selected = paradigms or sorted(set(REGISTRY) - RETIRED)
        # An explicit task list beats `limit`: probing whether a specific feature cell
        # discriminates needs those tasks, not the first N in generation order.
        if task_ids:
            missing = set(task_ids) - {t["task_id"] for t in self._tasks}
            if missing:
                raise ValueError(f"Unknown task ids: {sorted(missing)}")
            tasks = [t for t in self._tasks if t["task_id"] in set(task_ids)]
        else:
            tasks = self._tasks[:limit] if limit else self._tasks
        done = self.existing_keys() if resume else set()

        if workers < 1:
            raise ValueError("workers must be >= 1")

        rows: list[Row] = []
        total = len(tasks) * len(selected) * repeat
        completed = 0
        sink_lock = threading.Lock()
        counter_lock = threading.Lock()

        with self._results_path.open("a", encoding="utf-8") as sink:
            for task in tasks:
                # Derived features are computed once per task, not once per paradigm:
                # the feature vector describes the task, and recomputing it per
                # paradigm would charge the same estimate six times.
                features = self.features_for(task, allow_derived=True)
                # A fresh surface per task: the usage trace must not accumulate
                # across tasks, or every paradigm would inherit the previous task's
                # reads and the trace would stop describing what it actually did.
                def make_surface() -> ToolSurface:
                    return self.surface_for(task)

                # The grid of cells for this task. Tasks stay sequential because each
                # begins with one feature extraction that the whole grid shares.
                # Feasibility is arithmetic over what the task already declares, so it
                # costs nothing and is checked before any token is spent. A paradigm that
                # cannot run is RECORDED as infeasible rather than run into a wall or
                # silently skipped: the record has to show it was considered and why it
                # could not go.
                _, verdicts = feasibility.admissible(selected, self._documents, task)

                cells = [
                    (trial, name)
                    for trial in range(repeat)
                    for name in selected
                    if (task["task_id"], name, trial) not in done
                ]
                skipped = len(selected) * repeat - len(cells)
                with counter_lock:
                    completed += skipped

                def execute(cell: tuple[int, str]) -> Row:
                    trial, name = cell
                    verdict = verdicts[name]
                    if not verdict.feasible:
                        return self._infeasible_row(task, name, features, trial, verdict)
                    # One seed per trial, shared by every paradigm in that trial, so
                    # paradigms are compared under the same sampling conditions.
                    client = SeededClient(self._client, self._settings.seed + trial)
                    return self._run_one(
                        task, name, features, make_surface(), trial, client
                    )

                def record(row: Row, trial: int, name: str) -> None:
                    nonlocal completed
                    with counter_lock:
                        completed += 1
                        seen = completed
                    with sink_lock:
                        # Un solo punto de escritura, asi que un solo lugar donde
                        # estampar la huella: ninguna fila puede salir sin decir bajo que
                        # decodificacion se produjo.
                        row.fingerprint = self._settings.fingerprint()
                        row.region_vocabulary = REGION_VOCABULARY
                        sink.write(json.dumps(row.as_dict(), ensure_ascii=False) + "\n")
                        sink.flush()
                    status = row.error or f"u={row.utility:.3f}"
                    # flush=True: stdout is block-buffered when redirected, so a
                    # background run would show no progress until it finished.
                    print(
                        f"[{seen}/{total}] {task['task_id']:<14} "
                        f"{name:<14} t{trial} {status:<24} tok={row.cost_tokens}",
                        flush=True,
                    )

                if workers == 1:
                    for trial, name in cells:
                        row = execute((trial, name))
                        rows.append(row)
                        record(row, trial, name)
                else:
                    with ThreadPoolExecutor(max_workers=workers) as pool:
                        futures = {
                            pool.submit(execute, cell): cell for cell in cells
                        }
                        for future in as_completed(futures):
                            trial, name = futures[future]
                            row = future.result()
                            rows.append(row)
                            record(row, trial, name)

        return rows

    def _infeasible_row(
        self,
        task: dict[str, Any],
        paradigm: str,
        features: Features,
        trial: int,
        verdict: Any,
    ) -> Row:
        """A paradigm that cannot run this task, recorded rather than omitted."""
        return Row(
            task_id=task["task_id"],
            cell=task["cell"],
            paradigm=paradigm,
            trial=trial,
            region=features.region(),
            utility=0.0,
            cost_tokens=0,
            calls=0,
            wall_seconds=0.0,
            iterations=0,
            cross_unit_lookups=0,
            hallucinated_units=0,
            tool_usage={"infeasible": verdict.reason, **verdict.as_dict()},
            infeasible=True,
            retriever=self.retriever_arm,
            has_oracle=bool(task.get("has_oracle", True)),
            answer="",
            truth_coupling=task.get("truth_coupling", 0.0),
            n_units=features.n_units,
            phi_coupling=features.coupling,
            phi_horizon_unknown=features.horizon_unknown,
            phi_continuation=getattr(features, "continuation", None),
        )

    def _run_one(
        self,
        task: dict[str, Any],
        paradigm: str,
        features: Features,
        surface: ToolSurface,
        trial: int,
        client: Any,
    ) -> Row:
        started = time.perf_counter()
        try:
            result = REGISTRY[paradigm](client, surface, task)
            utility = grading.score(result.answer, task["oracle"])
            # El contrato corre sobre la respuesta, no sobre el gold: lo que verifica es
            # que la respuesta ATIENDA a cada elemento del dominio declarado, que es
            # comprobable en produccion sin oraculo. Que lo que diga de cada uno sea
            # correcto es otro contrato (`C-CITE`) y necesita el indice.
            contract = verify_coverage(task, result.answer)
            return Row(
                task_id=task["task_id"],
                cell=task["cell"],
                paradigm=paradigm,
                trial=trial,
                region=features.region(),
                utility=utility,
                cost_tokens=result.usage.total_tokens,
                prompt_tokens=result.usage.prompt_tokens,
                completion_tokens=result.usage.completion_tokens,
                completeness=contract,
                calls=result.usage.calls,
                wall_seconds=round(time.perf_counter() - started, 3),
                iterations=result.iterations,
                cross_unit_lookups=result.cross_unit_lookups,
                hallucinated_units=result.hallucinated_units,
                tool_usage=result.tool_usage,
                infeasible=False,
                retriever=self.retriever_arm,
                # Declared, never inferred from `bool(oracle)`: a task whose correct
                # answer is the empty set still HAS a cheap oracle, and inferring it
                # would mislabel exactly those tasks as unverifiable.
                has_oracle=bool(task.get("has_oracle", True)),
                answer=result.answer[:500],
                truth_coupling=task.get("truth_coupling", 0.0),
                n_units=features.n_units,
                phi_coupling=features.coupling,
                phi_horizon_unknown=features.horizon_unknown,
                phi_continuation=getattr(features, "continuation", None),
            )
        except Infeasible as reason:
            # Recorded as a distinct outcome. It scores no utility — nothing was
            # answered — but it is not a wrong answer, and its zero cost must not enter
            # the cost model as if the paradigm had run cheaply.
            return Row(
                task_id=task["task_id"],
                cell=task["cell"],
                paradigm=paradigm,
                trial=trial,
                region=features.region(),
                utility=0.0,
                cost_tokens=0,
                calls=0,
                wall_seconds=0.0,
                iterations=0,
                cross_unit_lookups=0,
                hallucinated_units=0,
                tool_usage={"infeasible": str(reason)},
                infeasible=True,
                retriever=self.retriever_arm,
                has_oracle=bool(task.get("has_oracle", True)),
                answer="",
                truth_coupling=task.get("truth_coupling", 0.0),
                n_units=features.n_units,
                phi_coupling=features.coupling,
                phi_horizon_unknown=features.horizon_unknown,
                phi_continuation=getattr(features, "continuation", None),
            )
        except SealedCacheMiss:
            # Never swallowed: a sealed replay that silently went live would not be a
            # replay at all.
            raise
        except Exception as exc:  # noqa: BLE001
            # A paradigm that blows up on a task scores zero for that task. That is the
            # honest utility, and hiding the failure would flatter the paradigm -- but
            # only when the failure is the paradigm's. A rate limit or a dropped
            # connection is the transport's, and scoring it as a wrong answer attributes
            # someone else's quota to a topology.
            infra = _is_infrastructure(exc)
            # The tokens the paradigm burned before blowing up are gone from its own
            # Usage (it never returned one), but the client metered them. Recording 0
            # here would teach the cost model that this paradigm fails cheaply.
            spent = getattr(client, "spent", None) or Usage()
            return Row(
                task_id=task["task_id"],
                cell=task["cell"],
                paradigm=paradigm,
                trial=trial,
                region=features.region(),
                utility=0.0,
                cost_tokens=spent.total_tokens,
                prompt_tokens=spent.prompt_tokens,
                completion_tokens=spent.completion_tokens,
                calls=spent.calls,
                wall_seconds=round(time.perf_counter() - started, 3),
                iterations=0,
                cross_unit_lookups=0,
                hallucinated_units=0,
                tool_usage={},
                infeasible=False,
                retriever=self.retriever_arm,
                has_oracle=bool(task.get("has_oracle", True)),
                answer="",
                truth_coupling=task.get("truth_coupling", 0.0),
                n_units=features.n_units,
                phi_coupling=features.coupling,
                phi_horizon_unknown=features.horizon_unknown,
                phi_continuation=getattr(features, "continuation", None),
                error=f"{type(exc).__name__}: {exc}"[:300],
                infra_error=infra,
            )

    # -- analysis ----------------------------------------------------------

    def load_rows(self, include_infra: bool = False) -> list[dict[str, Any]]:
        """Las filas de ESTA corrida. La logica y las guardas son del modulo."""
        return load_rows(
            self._results_path, include_infra, expect=self._settings.fingerprint()
        )

    def study(self, lambda_cost: float = 0.0) -> Study:
        """Study over trial-averaged cells.

        Averaging across trials BEFORE taking the oracle is what shrinks the upward
        bias in `max`. Feeding raw trials in would let the oracle pick each paradigm's
        luckiest sample and inflate the gap.
        """
        cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
        dropped = 0
        for r in self.load_rows():
            # An infrastructure failure is not evidence about a paradigm. Averaging it in
            # would drag the cell down by however much of the quota someone else used.
            if r.get("infra_error"):
                dropped += 1
                continue
            cells.setdefault((r["task_id"], r["paradigm"]), []).append(r)
        if dropped:
            print(
                f"  [study] {dropped} filas excluidas por fallo de infraestructura "
                f"(no son mediciones)"
            )

        return Study(
            (Observation(
                task_id=task_id,
                region=rows[0]["region"],
                paradigm=paradigm,
                utility=sum(x["utility"] for x in rows) / len(rows),
                cost_tokens=int(sum(x["cost_tokens"] for x in rows) / len(rows)),
                prompt_tokens=int(
                    sum(x.get("prompt_tokens", 0) for x in rows) / len(rows)
                ),
                completion_tokens=int(
                    sum(x.get("completion_tokens", 0) for x in rows) / len(rows)
                ),
                has_oracle=rows[0]["has_oracle"],
                # Max across replicates, not mean: the question is whether the paradigm
                # was ever in a position to answer, and one trial that reached the
                # evidence establishes that it could.
                relevant_units_read=max(
                    ((x.get("tool_usage") or {}).get("relevant_units_read") or 0)
                    for x in rows
                ),
                relevant_units_available=self._relevant_count(task_id),
            )
            for (task_id, paradigm), rows in cells.items()),
            lambda_cost=lambda_cost,
        )

    def _relevant_count(self, task_id: str) -> int:
        task = next((t for t in self._tasks if t["task_id"] == task_id), None)
        return len(task.get("relevant_units", [])) if task else 0

    def replicates(self, paradigm: str | None = None) -> dict[str, list[float]]:
        """Per-task replicate utilities for one paradigm, for the noise floor.

        Defaults to the fallback: it is the paradigm every task runs, and the one whose
        variance the deferral decision is measured against.
        """
        target = paradigm or FALLBACK
        out: dict[str, list[float]] = {}
        for r in self.load_rows():
            if r["paradigm"] == target:
                out.setdefault(r["task_id"], []).append(r["utility"])
        return out

    def episodes(self) -> list[Episode]:
        """Convert rows into learning episodes: ONE per (task, paradigm) cell.

        Trials are replicates of the same measurement, not independent evidence.
        Emitting one episode per trial let three repeats of one task count three
        times (pseudoreplication), and computing `was_best` against raw trials let a
        single lucky replicate collect the reinforcement its paradigm's MEAN never
        earned. Aggregating first makes the unit of learning the unit of evidence,
        and `was_best` answer the question the router actually needs estimated:
        'was this the right paradigm here, on average'.
        """
        cells: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for r in self.load_rows():
            cells.setdefault((r["task_id"], r["paradigm"]), []).append(r)

        mean_utility = {
            key: sum(x["utility"] for x in rows) / len(rows)
            for key, rows in cells.items()
        }
        best: dict[str, float] = {}
        for (task_id, _), value in mean_utility.items():
            best[task_id] = max(best.get(task_id, 0.0), value)

        return [
            Episode(
                task_id=task_id,
                region=rows[0]["region"],
                paradigm=paradigm,
                utility=mean_utility[(task_id, paradigm)],
                cost_tokens=int(sum(x["cost_tokens"] for x in rows) / len(rows)),
                was_best=(mean_utility[(task_id, paradigm)] >= best[task_id] > 0.0),
            )
            for (task_id, paradigm), rows in sorted(cells.items())
        ]

    # -- the report --------------------------------------------------------

    def report(
        self,
        assurance: Assurance = Assurance.STANDARD,
        lambda_cost: float = 0.0,
    ) -> dict[str, Any]:
        from .assurance import PROFILES  # local imports: avoid a cycle via policy
        from .router import Router

        study = self.study(lambda_cost=lambda_cost)
        episodes = self.episodes()

        # Learn theta from the observed episodes, then evaluate the router it implies.
        # Persisted, not discarded: a theta that only ever existed inside this call
        # could not be audited, diffed against its successor, or promoted. Persisted
        # in `fitted/`, OUTSIDE the glob that `latest_theta_path()` treats as the
        # live policy: a report is a reading, and a reading must not install an
        # unpromoted bundle as production — that path goes through `promote()` only.
        # La confianza en credencia elicitada se computa desde el log de creencias y va
        # ADENTRO del bundle, firmada — no como parametro del router. El bundle frio no
        # la trae, asi que se asienta acá, que es donde se arma el que va a decidir.
        cold = dc_replace(
            PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3),
            trusts_elicited=self.store.trusts_elicited(),
        )
        learned = Plasticity.candidate(
            cold, episodes, tau=0.3, notes=f"fitted from {len(episodes)} episodes"
        )
        fitted_dir = self.store.policy_dir / "fitted"
        fitted_dir.mkdir(parents=True, exist_ok=True)
        learned.save(fitted_dir)
        router = Router(learned, COST_PRIORS, FALLBACK)
        profile = PROFILES[assurance]

        rows_by_task: dict[str, dict[str, Any]] = {}
        for r in self.load_rows():
            rows_by_task.setdefault(r["task_id"], {})[r["paradigm"]] = r

        def task_of(task_id: str) -> dict[str, Any]:
            return next(t for t in self._tasks if t["task_id"] == task_id)

        def region_of(task_id: str) -> str:
            return next(iter(rows_by_task[task_id].values()))["region"]

        def decide(task_id: str) -> str:
            plan = router.plan(
                task=task_of(task_id),
                candidates=sorted(rows_by_task[task_id]),
                region=region_of(task_id),
                requested=assurance,
            )
            # This is what makes `log_belief_base` mean something. The flag was declared
            # on the A2 and A3 profiles and nothing acted on it, so no belief base was
            # ever written, so calibration could never be computed, so elicited
            # credence could never earn trust. Honouring the flag closes that loop.
            if profile.log_belief_base:
                beliefs = plan.verdict.get("beliefs", {})
                self.store.append_belief_base(
                    beliefs,
                    context={
                        "task_id": task_id,
                        "region": region_of(task_id),
                        "assurance": assurance.label,
                        "action": plan.action,
                        "paradigm": plan.paradigm,
                        "theta_version": plan.theta_version,
                        # The two fields §6.2 learns from. `elicited_offered` is the
                        # denominator: a request that never asserted anything elicited
                        # cannot have one refused, and counting it would dilute the
                        # rate with requests that never asked.
                        "elicited_offered": any(
                            b.get("provenance") == Provenance.ELICITED.value
                            for b in beliefs.get("beliefs", [])
                        ),
                        "gate_rejections": plan.verdict.get("gate_rejections", []),
                    },
                )
            return plan.paradigm

        def rank(task_id: str) -> float:
            # The confidence that drives the risk-coverage sweep is theta's margin:
            # a fact about the bundle, not a credence about the world.
            return router.theta_assertions(
                region_of(task_id), sorted(rows_by_task[task_id])
            )[1]

        ladder = sorted(REGISTRY, key=lambda p: COST_PRIORS[p])

        calibration = self.store.rebuild_calibration()

        return {
            "corpus": self._corpus_name,
            "assurance": assurance.label,
            "learning_state": self.store.summary(),
            "calibration": calibration,
            "settings": self._settings.fingerprint(),
            "theta_version": learned.version,
            "theta_signature": learned.signature,
            "summary": study.summary(),
            "oracle_gap_credibility": study.credible_oracle_gap(self.replicates()),
            "selection_terms": study.selection_terms(decide).as_dict(),
            "router_captured_fraction": round(study.captured_fraction(decide), 5),
            "risk_coverage": study.risk_coverage(rank, decide),
            "cascade": study.cascade_value(ladder, detector_sensitivity=1.0),
            "cascade_weak_detector": study.cascade_value(ladder, detector_sensitivity=0.6),
        }

    def consolidate(self, tau: float = 0.3) -> dict[str, Any]:
        """Run one sleep cycle over the recorded episodes and persist the result.

        Costs nothing in inference: the cross product is already on disk, so
        consolidation is counterfactual replay over the record.

        Copy-on-write. The incumbent theta is never mutated; a candidate is built and
        installed only if the promotion guard says it does not regress on held-out
        episodes. Discovered propositions are persisted so that being re-proposed on a
        different split across cycles becomes visible — one discovery may be an
        artefact, three in a row is a finding.
        """
        from .assurance import Assurance  # local import: avoids a cycle
        from .consolidation import sleep_cycle
        from .router import Router

        rows = self.load_rows()
        if not rows:
            raise RuntimeError("Nothing to consolidate: no execution record yet.")

        latest = self.store.latest_theta_path()
        incumbent = (
            PolicyBundle.load(latest) if latest
            else PolicyBundle.cold_start(fallback=FALLBACK, tau=tau)
        )
        if latest is None:
            incumbent.save(self.store.policy_dir)

        def promote_fn(inc: PolicyBundle, cand: PolicyBundle, holdout: list[Episode]):
            return promote(
                inc, cand, holdout,
                lambda bundle, eps: Router(
                    bundle, COST_PRIORS, FALLBACK
                ).value_on(eps, requested=Assurance.STANDARD),
            )

        cycle = self.store.next_cycle()
        installed, report = sleep_cycle(
            incumbent=incumbent,
            rows=rows,
            episodes=self.episodes(),
            belief_log=self.store.belief_log(),
            promote_fn=promote_fn,
            cycle=cycle,
            tau=tau,
        )

        body = report.as_dict()
        body["discoveries_persisted"] = self.store.record_discoveries(
            report.discovered, cycle
        )
        if installed.signature != incumbent.signature:
            body["installed_theta"] = str(installed.save(self.store.policy_dir))
        else:
            body["installed_theta"] = None

        self.store.save_dream(body)
        body["learning_state"] = self.store.summary()
        return body

    def save_report(self, report: dict[str, Any]) -> Path:
        path = self._settings.results_dir / f"{self._corpus_name}_report.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
