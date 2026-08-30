"""Retrieval as a controlled experimental variable, not a hidden constant.

WHY THIS EXISTS. The harness previously offered one search tool: term-frequency
bag-of-words, with no IDF and no length normalisation. That is not a weak retriever, it
is a BIASED one — longer documents accumulate more term hits, so they rank higher for
being long. The corpus hardening then made every document four times longer with
padding, which means the hardening actively degraded retrieval while appearing only to
add difficulty.

Two paradigms search and four read. A retriever that silently favours long documents
handicaps the ones that search, so "the searching topology lost" would have been
uninterpretable: no way to separate a topology that does not work from a tool that was
broken and then made worse.

THE DESIGN. Retriever quality becomes a dial with a number on it, and the dial is
DETERMINISTIC — which is why simulation beats a real retriever here. A real embedding
model would add cost, a second noise floor, and its own confounds. A simulated one is
free, replayable and parameterised, so the study can ask the question that actually
matters to anyone deploying this:

    at what retrieval quality does the choice of topology stop mattering?

Three arms bracket the answer:

    HYBRID     BM25 + dense, fused by RRF. THE PRIMARY ARM: a result measured under
               lexical-only retrieval is dismissible, because nobody deploys BM25 alone.
    LEXICAL    BM25 with IDF and length normalisation. A component, and a floor.
    SEMANTIC   Dense only. The other component, for attribution.
    SIMULATED  A stated (recall, precision). Deterministic given the task and query.
               Sensitivity analysis, not the headline.
    ORACLE     recall = precision = 1. The upper bound; no retrieval error at all.

Hybrid stays deterministic because vectors are cached by content hash, so after the
first pass fusion is local arithmetic. Optional LLM rerank is the one stage that is not,
and it is off by default and marked as such.

The corpus declares which units bear each answer, so recall and precision here are
measured quantities rather than adjectives.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .embeddings import cosine

_TOKEN = re.compile(r"[a-z0-9]+")

# Standard BM25 parameters. b = 0.75 is the length-normalisation strength, and it is the
# term whose absence produced the original bias.
BM25_K1 = 1.5
BM25_B = 0.75

# EL FILTRO DE LARGO ERA UN BUG QUE EL CORPUS VIEJO ESCONDIA. `len(t) > 2` descartaba todo
# token de una o dos letras, y con el corpus previo a `K-6` eso no costaba nada porque
# ningun nombre traia iniciales. Con variantes de superficie cuesta la medicion entera:
#
#   tokenise("M. Cavallero")  ->  ['cavallero']
#   tokenise("I. Cavallero")  ->  ['cavallero']      <- IDENTICO
#
# La inicial es LA senal que desambigua a dos personas que comparten apellido, y BM25 no la
# veia. El brazo lexico quedaba ciego exactamente donde el corpus nuevo mide, y el hibrido
# heredaba la ceguera por su mitad lexica.
#
# LA REPARACION ES LA DE UN MOTOR REAL: no se filtra por largo, se filtra por una lista de
# palabras vacias. Un motor Lucene conserva «m» como token y deja que el IDF decida su
# peso — que es la respuesta correcta, porque un token frecuente se penaliza solo. Filtrar
# por largo es una heuristica que confunde «corto» con «poco informativo», y una inicial es
# corta y decisiva.
# LA VERSION DEL ANALIZADOR, estampada en cada fila. NO va en el fingerprint de
# decodificacion a proposito: ese entra en la clave de cache, y meterlo ahi invalidaria los
# 148 MB de cache **incluso donde sigue siendo valido** — una tarea de una sola unidad
# produce el mismo prompt con cualquier tokenizador, y medido son 7 de 26 tareas de
# `gold_p17` cuyo ranking no cambia.
#
# DONDE SI TIENE QUE ESTAR: en la FILA, para que el analisis no pueda promediar a traves de
# un cambio de analizador. Es la misma disciplina que el brazo de recuperacion, que ya vive
# en un archivo aparte con guarda de mezcla en `load_rows`.
#
# v1 = filtro por largo (`len(t) > 2`), que descartaba las iniciales
# v2 = sin filtro de largo, con stopwords (2026-08-29): `M. Cavallero` e `I. Cavallero`
#      dejaron de tokenizar identico, que era lo que volvia ciego al lexico justo donde el
#      corpus de entidades mide
ANALYZER_VERSION = "v2-stopwords"

STOPWORDS = frozenset("""
a an and are as at be been but by for from has have in into is it its of on or such that
the their then there these they this to was were will with no not any all each every than
""".split())


def tokenise(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


@dataclass
class CorpusView:
    """The units one task ranges over, plus which of them bear the answer."""

    task_id: str
    documents: dict[str, str]
    unit_ids: list[str]
    relevant_units: list[str]

    @property
    def relevant(self) -> set[str]:
        # Intersected with the task's own units: a relevance label naming a unit the
        # task does not supply would silently inflate measured recall.
        return set(self.relevant_units) & set(self.unit_ids)

    @property
    def irrelevant(self) -> list[str]:
        relevant = self.relevant
        return [u for u in self.unit_ids if u not in relevant]


class Retriever(Protocol):
    """El contrato de un brazo de recuperación: ordenar unidades, y decir qué es.

    ES UN `Protocol` Y NO UNA CLASE BASE porque la calidad de recuperación es un FACTOR
    medido, no una pieza fija: híbrido, léxico, semántico, dos degradaciones simuladas a
    recall y precisión declarados, y un oráculo. Las simulaciones son funciones
    deterministas de `(tarea, consulta, unidad)`, así que la calidad del retriever es un
    dial controlado y no otra fuente de ruido.

    `describe()` no es opcional ni decorativo: es lo que hace que la fila diga bajo qué
    recuperación se produjo. Un banco que no reporta la calidad de su superficie de
    recuperación no compara topologías — compara un retriever envuelto de N maneras.
    """

    def rank(self, view: CorpusView, query: str, limit: int) -> list[str]: ...
    def describe(self) -> dict[str, Any]: ...


class LexicalRetriever:
    """BM25 over the task's units.

    IDF and length normalisation are the point. Without them a padded document ranks
    highly for being padded, which is the bias the corpus hardening introduced.
    """

    name = "lexical"

    def rank(self, view: CorpusView, query: str, limit: int) -> list[str]:
        return [u for _, u in self._scored(view, query)[:limit]]

    def _scored(self, view: CorpusView, query: str) -> list[tuple[float, str]]:
        terms = tokenise(query)
        if not terms:
            return []

        docs = {u: tokenise(view.documents[u]) for u in view.unit_ids}
        n = len(docs)
        if n == 0:
            return []
        avg_len = sum(len(t) for t in docs.values()) / n

        # Document frequency per query term, for IDF.
        df = {
            term: sum(1 for tokens in docs.values() if term in tokens)
            for term in set(terms)
        }

        scored: list[tuple[float, str]] = []
        for unit_id, tokens in docs.items():
            if not tokens:
                continue
            length = len(tokens)
            score = 0.0
            for term in set(terms):
                freq = tokens.count(term)
                if freq == 0:
                    continue
                idf = math.log((n - df[term] + 0.5) / (df[term] + 0.5) + 1.0)
                denominator = freq + BM25_K1 * (
                    1.0 - BM25_B + BM25_B * length / avg_len
                )
                score += idf * freq * (BM25_K1 + 1.0) / denominator
            if score > 0:
                scored.append((score, unit_id))

        # Unit id breaks ties, so the ranking is total and reproducible.
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return scored

    def scored(self, view: CorpusView, query: str, limit: int) -> list[tuple[str, float]]:
        """Como `rank`, pero con el score. Lo pide Relative Score Fusion, no RRF.

        Se expone en vez de recalcular afuera: dos implementaciones del mismo BM25 se
        desincronizan, y la primera vez que difieran las dos devuelven un orden plausible.
        """
        pares = self._scored(view, query)
        return [(u, sc) for sc, u in pares[:limit]]

    def describe(self) -> dict[str, Any]:
        return {"retriever": self.name, "k1": BM25_K1, "b": BM25_B}


class SimulatedRetriever:
    """Retrieval at a stated recall and precision, deterministically.

    This is the dial. Given the relevant set the corpus declares, it returns

        ceil(recall * |relevant|)   relevant units
        enough irrelevant units to hit the requested precision

    Which units are dropped and which noise is injected is a pure function of
    (task, query, unit) — no RNG state crosses calls — so the same query returns the
    same ranking on every run and in every replicate. That is what makes retriever
    quality a controlled variable rather than another source of noise.

    Relevant and irrelevant results are INTERLEAVED rather than ranked relevant-first.
    Precision means the model has to read past noise; putting the good hits on top
    would report a precision the paradigm never actually experiences.
    """

    name = "simulated"

    def __init__(self, recall: float, precision: float, salt: int = 0) -> None:
        if not 0.0 <= recall <= 1.0:
            raise ValueError(f"recall must be in [0,1], got {recall}")
        if not 0.0 < precision <= 1.0:
            raise ValueError(f"precision must be in (0,1], got {precision}")
        self.recall = recall
        self.precision = precision
        self.salt = salt

    def _order(self, task_id: str, query: str, units: list[str]) -> list[str]:
        """Deterministic pseudo-random order: a hash, not a random generator."""

        def key(unit: str) -> str:
            blob = f"{self.salt}|{task_id}|{query}|{unit}"
            return hashlib.sha256(blob.encode("utf-8")).hexdigest()

        return sorted(units, key=key)

    def rank(self, view: CorpusView, query: str, limit: int) -> list[str]:
        relevant = self._order(view.task_id, query, sorted(view.relevant))
        irrelevant = self._order(view.task_id, query, view.irrelevant)

        # The composition is chosen to fit `limit` BEFORE selecting, then ordered.
        # Selecting first and truncating afterwards destroyed it: recall 1.0 with
        # precision 0.25 wants 6 hits and 18 noise, and cutting the interleaved 24 down
        # to 10 left zero hits — a retriever that reported perfect recall and delivered
        # none of it.
        wanted_hits = math.ceil(self.recall * len(relevant)) if relevant else 0
        # At the target precision, this is the most hits that fit in `limit`.
        affordable_hits = max(1, math.floor(limit * self.precision)) if relevant else 0
        hits = relevant[: min(wanted_hits, affordable_hits)]

        # precision = hits / (hits + noise)  =>  noise = hits * (1/precision - 1)
        if hits:
            noise_count = math.ceil(len(hits) * (1.0 / self.precision - 1.0))
        else:
            # Nothing relevant to find, or none affordable: return noise only, so the
            # paradigm experiences a search that found nothing useful rather than an
            # empty tool result it cannot distinguish from a broken tool.
            noise_count = limit
        noise = irrelevant[: max(0, min(noise_count, limit - len(hits)))]

        # Order the chosen set, so noise is distributed through the ranking rather than
        # parked at the bottom where it costs nothing to skip.
        return self._order(view.task_id, query, hits + noise)

    def describe(self) -> dict[str, Any]:
        return {
            "retriever": self.name,
            "recall": self.recall,
            "precision": self.precision,
            "salt": self.salt,
        }


class OracleRetriever:
    """Every relevant unit, nothing else. The upper bound.

    Not realistic and not meant to be. It answers the question a production team
    actually has: if retrieval were perfect, would the topology still matter? A gap
    that vanishes here was never about the topology.
    """

    name = "oracle"

    def rank(self, view: CorpusView, query: str, limit: int) -> list[str]:
        return sorted(view.relevant)[:limit]

    def describe(self) -> dict[str, Any]:
        return {"retriever": self.name, "recall": 1.0, "precision": 1.0}


ARMS: dict[str, Retriever] = {
    "lexical": LexicalRetriever(),
    "oracle": OracleRetriever(),
    # A middle rung: most relevant units found, half the results are noise. Roughly
    # where a decent production retriever sits on a corpus with distractors.
    "sim_r80_p50": SimulatedRetriever(recall=0.8, precision=0.5),
    # Poor recall: the failure mode that should punish search-and-stop hardest.
    "sim_r40_p50": SimulatedRetriever(recall=0.4, precision=0.5),
    # Good recall, poor precision: punishes read-everything less than search.
    "sim_r100_p25": SimulatedRetriever(recall=1.0, precision=0.25),
}


def measure(view: CorpusView, retriever: Retriever, query: str, limit: int) -> dict[str, Any]:
    """Actual recall and precision of one ranking. For validating the dial."""
    returned = retriever.rank(view, query, limit)
    relevant = view.relevant
    hits = len([u for u in returned if u in relevant])
    return {
        "returned": len(returned),
        # Recall over an empty relevant set is 1.0: every one of the zero relevant
        # units was found.
        "recall": (hits / len(relevant)) if relevant else 1.0,
        # Precision is UNDEFINED when nothing is relevant, not zero. Reporting zero
        # there made the negative C7 cases look like a retrieval failure when the
        # correct behaviour is precisely to find nothing.
        "precision": (hits / len(returned)) if returned and relevant else None,
        "achieved_note": (
            "recall is quantised by the size of the relevant set: 0.8 of 4 units "
            "rounds up to all 4"
        ),
    }


# RRF constant. 60 is the value from the original formulation and is not sensitive.
RRF_K = 60


class SemanticRetriever:
    """Dense retrieval by cosine similarity over cached embeddings."""

    name = "semantic"

    def __init__(self, embedder: Any) -> None:
        self._embedder = embedder

    def rank(self, view: CorpusView, query: str, limit: int) -> list[str]:
        return [u for _, u in self._scored(view, query)[:limit]]

    def _scored(self, view: CorpusView, query: str) -> list[tuple[float, str]]:
        query_vector = self._embedder.embed(query)
        scored: list[tuple[float, str]] = []
        for unit_id in view.unit_ids:
            similarity = cosine(query_vector, self._embedder.embed(view.documents[unit_id]))
            scored.append((similarity, unit_id))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return scored

    def scored(self, view: CorpusView, query: str, limit: int) -> list[tuple[str, float]]:
        return [(u, sc) for sc, u in self._scored(view, query)[:limit]]

    def describe(self) -> dict[str, Any]:
        return {"retriever": self.name, **self._embedder.describe()}


class HybridRetriever:
    """BM25 and dense retrieval fused by Reciprocal Rank Fusion.

    The primary arm. RRF combines RANKS rather than scores, which matters: a BM25 score
    and a cosine similarity are on incomparable scales, so interpolating the numbers
    needs an arbitrary normalisation and interpolating the ranks needs none.

        score(unit) = sum over rankers of 1 / (k + rank(unit))

    A unit both rankers place highly beats one that only one of them liked, which is the
    whole point of hybrid: lexical catches exact identifiers a dense model blurs, dense
    catches paraphrase a lexical model misses. This corpus has both — account numbers
    that must match exactly, and five surface phrasings of every role.
    """

    name = "hybrid"

    def __init__(self, embedder: Any, depth: int = 40, fusion: str = "rrf") -> None:
        # LA FUSION ES UN FACTOR, y esta explicito porque el default de una herramienta
        # ajena no puede decidirlo en silencio: Weaviate cambio su `fusionType` de RRF a
        # Relative Score Fusion en v1.24, asi que quien actualiza sin fijarlo cambia de
        # metodo sin enterarse. Si produccion fusiona distinto que el banco, el banco mide
        # otra cosa — y ese es el modo de falla que este parametro vuelve visible.
        if fusion not in ("rrf", "relative_score"):
            raise ValueError(f"fusion desconocida: {fusion!r}")
        self._fusion = fusion
        self._lexical = LexicalRetriever()
        self._semantic = SemanticRetriever(embedder)
        # How deep each ranker contributes before fusion. Deeper than `limit` on
        # purpose: a unit ranked 15th by one ranker and 2nd by the other should be able
        # to surface, and it cannot if each list was already cut to the final size.
        self._depth = depth

    def rank(self, view: CorpusView, query: str, limit: int) -> list[str]:
        if self._fusion == "rrf":
            fused = self._rrf(view, query)
        else:
            fused = self._relative_score(view, query)
        ordered = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
        return [unit_id for unit_id, _ in ordered[:limit]]

    def _rrf(self, view: CorpusView, query: str) -> dict[str, float]:
        """Fusion por RANGOS. No mira los scores, asi que no necesita normalizarlos."""
        lists = [
            self._lexical.rank(view, query, self._depth),
            self._semantic.rank(view, query, self._depth),
        ]
        fused: dict[str, float] = {}
        for ranking in lists:
            for position, unit_id in enumerate(ranking, start=1):
                fused[unit_id] = fused.get(unit_id, 0.0) + 1.0 / (RRF_K + position)
        return fused

    def _relative_score(self, view: CorpusView, query: str) -> dict[str, float]:
        """Fusion por SCORES normalizados a [0,1] por lista, y despues sumados.

        QUE GANA Y QUE PIERDE FRENTE A RRF, para que la comparacion sea honesta. Gana
        MAGNITUD: RRF trata igual a un primer puesto que gano por goleada y a uno que gano
        por un pelo, y esa distincion a veces es la senal. Pierde ROBUSTEZ: normalizar
        min-max hace que el resultado dependa del PEOR elemento de cada lista, asi que un
        cambio en la cola mueve el tope, y una lista de un solo elemento no tiene rango que
        normalizar. Cual conviene es empirico y por eso los dos estan.

        El elemento unico se mapea a 1,0 y no a 0,0: con `hi == lo` la normalizacion no
        esta definida, y elegir 0 haria que una lista que encontro UNA cosa relevante no
        aporte nada — el peor default posible de los dos.
        """
        fused: dict[str, float] = {}
        for ranker in (self._lexical, self._semantic):
            pares = ranker.scored(view, query, self._depth)
            if not pares:
                continue
            valores = [sc for _, sc in pares]
            hi, lo = max(valores), min(valores)
            span = hi - lo
            for unit_id, sc in pares:
                norm = 1.0 if span <= 0 else (sc - lo) / span
                fused[unit_id] = fused.get(unit_id, 0.0) + norm
        return fused

    def describe(self) -> dict[str, Any]:
        return {
            "retriever": self.name,
            "fusion": self._fusion,
            "k": RRF_K if self._fusion == "rrf" else None,
            "depth": self._depth,
            "components": ["bm25", "dense"],
        }


class HydeFused:
    """HyDE como RAMA PARALELA fusionada por RRF. `H-1`, `H-2`, `F-3`.

    QUE ES. Se le pide al modelo una respuesta HIPOTETICA a la pregunta —como se veria el
    parrafo que la contesta, escrito en el estilo del corpus— y se rankea densamente con
    ESE texto en vez de con la pregunta. El puente que cruza: la pregunta dice «cuenta de
    liquidacion de Valerio» y el documento dice «AC-7741, titular Valerio Simoni, rol
    custodio». Un vector de la pregunta y uno del documento viven lejos; un vector de la
    respuesta hipotetica vive cerca del documento, porque tiene su forma.

    POR QUE RAMA Y NO HERRAMIENTA, que es la decision de `H-1`. Una herramienta la llama el
    MODELO, y eso pone flujo de control del lado del sensor — el invariante del producto lo
    prohibe. Como brazo de recuperacion, quien decide usarla es la configuracion de la
    corrida: determinista, registrable, y comparable contra el brazo sin ella.

    POR QUE FUSIONADA Y NO REEMPLAZANDO. Una respuesta hipotetica puede estar bien
    imaginada y ser falsa —el modelo inventa una cuenta que no existe— y entonces su vector
    apunta a documentos parecidos y equivocados. Fusionar por RRF hace que ese error tenga
    que VENCER al ranking base en vez de reemplazarlo: una unidad que solo la rama HyDE
    quiere entra abajo, y una que las dos quieren sube. Es la misma logica por la que
    `hybrid` fusiona lexico y denso en vez de elegir uno.

    LO QUE NO ES DETERMINISTA, Y SE DECLARA. La generacion es una llamada al modelo, asi
    que este brazo reintroduce varianza en la recuperacion — un segundo piso de ruido
    encima del de los paradigmas. Mismo estatus que `LLMReranked`: sirve para preguntar si
    HyDE cambia la conclusion, no para producir el numero titular.

    Y CUESTA. Una llamada por consulta, y las consultas las emite el paradigma, asi que el
    costo escala con cuanto busca cada topologia — un brazo que busca diez veces paga diez
    generaciones. Sin cobrarlo, comparar `hybrid` contra `hybrid_hyde` compara una
    recuperacion gratis contra una paga y llama «mejor» a la diferencia (`H-3`).
    """

    name = "hybrid_hyde"

    # Un parrafo corto. El objetivo es la FORMA del documento, no su contenido: un texto
    # largo agrega tokens y ruido lexico sin acercar el vector, porque lo que lo acerca es
    # el registro —nombres, identificadores, la sintaxis del corpus— y eso entra en dos
    # oraciones. Mas largo es mas caro y no mas parecido.
    HYDE_MAX_TOKENS = 160

    HYDE_PROMPT = (
        "Write ONE short paragraph that looks like the passage which would answer this "
        "question, as it would appear in an internal records document. Use the same "
        "register: entity name, the specific value, the role or context. Invent "
        "plausible values — this text is used only as a search probe, never shown to "
        "anyone.\n\nOutput only the paragraph.\n\nQuestion: {query}"
    )

    def __init__(self, base: Any, embedder: Any, client: Any, depth: int = 40) -> None:
        self._base = base
        self._semantic = SemanticRetriever(embedder)
        self._client = client
        self._depth = depth
        # Una generacion por CONSULTA distinta, no por llamada. Un paradigma que repite la
        # misma busqueda no paga dos veces, que es lo que pasaria sin esto y haria que el
        # costo del brazo dependiera de cuanto se repite el paradigma en vez de cuanto
        # busca. Local a la instancia, o sea a la celda: no cruza tareas.
        self._generated: dict[str, str] = {}
        self.generations = 0

    def _hypothetical(self, query: str) -> str:
        if query in self._generated:
            return self._generated[query]
        completion = self._client.complete(
            messages=[{"role": "user",
                       "content": self.HYDE_PROMPT.format(query=query)}],
            max_tokens=self.HYDE_MAX_TOKENS,
        )
        texto = (completion.text or "").strip()
        self.generations += 1
        self._generated[query] = texto
        return texto

    def rank(self, view: CorpusView, query: str, limit: int) -> list[str]:
        base_ranking = self._base.rank(view, query, self._depth)
        hipotetica = self._hypothetical(query)
        if not hipotetica:
            # UNA GENERACION VACIA NO ES UN RANKING VACIO. Se cae al brazo base y no a
            # nada: descartar el ranking base porque la rama extra fallo haria que una
            # falla de HyDE se lea como una falla de recuperacion, que es el mismo error
            # que `LLMReranked` evita al no parsear su respuesta.
            return base_ranking[:limit]

        lists = [base_ranking, self._semantic.rank(view, hipotetica, self._depth)]
        fused: dict[str, float] = {}
        for ranking in lists:
            for position, unit_id in enumerate(ranking, start=1):
                fused[unit_id] = fused.get(unit_id, 0.0) + 1.0 / (RRF_K + position)
        ordered = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
        return [unit_id for unit_id, _ in ordered[:limit]]

    def describe(self) -> dict[str, Any]:
        return {
            "retriever": self.name,
            "base": self._base.describe(),
            "fusion": "rrf",
            "k": RRF_K,
            "depth": self._depth,
            "generations": self.generations,
            # Se declara, igual que `LLMReranked`: una generacion es una llamada al modelo,
            # asi que este brazo tiene su propio piso de ruido.
            "deterministic": False,
        }


class LLMReranked:
    """Optional cross-encoder-style rerank of a base retriever's candidates.

    OFF BY DEFAULT, and flagged, because it is the one retrieval stage that is not a
    pure function. Everything else here is deterministic given cached vectors; a model
    scoring query-document pairs reintroduces sampling variance into retrieval, which
    means a second noise floor on top of the paradigms' own. Enable it to check whether
    rerank changes the conclusion, not to produce the headline.
    """

    name = "hybrid_reranked"

    def __init__(self, base: Any, client: Any, candidates: int = 20) -> None:
        self._base = base
        self._client = client
        self._candidates = candidates

    def rank(self, view: CorpusView, query: str, limit: int) -> list[str]:
        shortlist = self._base.rank(view, query, self._candidates)
        if len(shortlist) <= limit:
            return shortlist

        numbered = "\n\n".join(
            f"[{i}] {view.documents[u][:600]}" for i, u in enumerate(shortlist)
        )
        prompt = (
            f"Query: {query}\n\n"
            f"Rank the passages by how well they answer the query. "
            f"Return only a JSON array of indices, best first, at most {limit}.\n\n"
            f"{numbered}"
        )
        completion = self._client.complete(
            messages=[{"role": "user", "content": prompt}], max_tokens=200
        )
        try:
            order = json.loads(completion.text.strip())
            picked = [shortlist[int(i)] for i in order if 0 <= int(i) < len(shortlist)]
        except (json.JSONDecodeError, TypeError, ValueError, IndexError):
            # An unparseable rerank falls back to the base ranking rather than to
            # nothing: the base order is a real ranking, and discarding it would make a
            # rerank failure look like a retrieval failure.
            return shortlist[:limit]
        return picked[:limit] or shortlist[:limit]

    def describe(self) -> dict[str, Any]:
        return {
            "retriever": self.name,
            "base": self._base.describe(),
            "candidates": self._candidates,
            "deterministic": False,
        }


# BRAZOS QUE LLAMAN AL MODELO, y por eso no se pueden compartir entre celdas.
#
# Dos consecuencias, y ninguna es cosmetica:
#
#   costo    su gasto tiene que ir al medidor de LA CELDA. Con una instancia compartida,
#            la generacion de la primera tarea subsidiaria a todas las demas
#   estado   su memo de consultas es local a la celda. Compartido, una tarea heredaria
#            la hipotetica de otra y el brazo mediria el orden del recorrido
#
# Los demas brazos son funciones puras sobre vectores cacheados: compartirlos es correcto
# y ademas barato, asi que la distincion no es «por las dudas».
MODEL_CALLING_ARMS = frozenset({"hybrid_reranked", "hybrid_hyde"})


def build_arm(name: str, embedder: Any, client: Any) -> Any:
    """Una instancia FRESCA del brazo, para una celda.

    Se levanta si el brazo no existe: caer al lexico callado es como una corrida entera
    mide un brazo que nadie pidio y el registro dice otro.
    """
    arms = build_arms(embedder=embedder, client=client)
    if name not in arms:
        raise ValueError(
            f"Brazo de recuperacion {name!r} desconocido. Disponibles: {sorted(arms)}. "
            f"Se levanta en vez de caer a uno por omision: una corrida que mide un brazo "
            f"y registra otro es peor que una que no corre."
        )
    return arms[name]


def build_arms(embedder: Any = None, client: Any = None) -> dict[str, Any]:
    """Assemble the arms available for a run.

    `hybrid` is the primary and requires an embedder. The degraded simulations need
    nothing and are always present, because they are the sensitivity analysis.
    """
    arms: dict[str, Any] = dict(ARMS)
    if embedder is not None:
        arms["hybrid"] = HybridRetriever(embedder)
        arms["semantic"] = SemanticRetriever(embedder)
        if client is not None:
            arms["hybrid_reranked"] = LLMReranked(arms["hybrid"], client)
            # HyDE es una RAMA, no una herramienta: quien decide usarla es la corrida y no
            # el modelo. Necesita cliente por la misma razon que el rerank —genera texto—
            # y por eso comparte su condicion de NO determinista.
            arms["hybrid_hyde"] = HydeFused(arms["hybrid"], embedder, client)
    return arms
