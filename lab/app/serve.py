"""The product path: one request in, one answer out, with the decision on the record.

WHAT WAS MISSING. Everything here already existed and none of it was reachable from
outside the bench. `Runner` takes a corpus name and a task id; `sense()` reads
`unit_ids`, `budget_tokens` and `oracle`; `/decide` returns a plan and stops. A caller
holding a question and some documents had no way in, and nothing executed what the
decision layer decided. That is the difference between a library and a product.

WHAT THIS IS NOT. It is not a second decision layer. Every call here goes through the
same feasibility arithmetic, the same router, the same assurance dial and the same
paradigms the bench measures — because the moment the product path builds its own
version of any of those, the measurements stop being about the product.

THE THREE OUTCOMES. A request is answered, deferred, or gated, and they are different
things:

  answered  a paradigm ran and produced text
  gated     an irreversible or shared-write action needs a human before anything runs;
            the plan is returned and NOTHING is executed
  deferred  the router abstained -- theta had no margin it trusted in this region -- and
            the fallback ran instead. Recorded as an abstention, not as a choice.

Conflating the last two is the failure this layer exists to prevent: a system that
"handles" an irreversible request by quietly picking a safe paradigm has made the
decision a human was supposed to make.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from typing import Any

from .verify import score as detector_score
from .assurance import Assurance
from .config import Settings
from .features import FeatureExtractor, measure_continuation, payload_for
from .llm import LLMClient, Usage
from .paradigms import COST_PRIORS, FALLBACK, REGISTRY
from .pool import ModelPool
from .policy import no_online_learning
from .policy import PolicyBundle
from .beliefs import Provenance
from .decide import decide as decide_once
from .rec import diagnose as rec_diagnose
from .rules import BeliefPolicy
from .embeddings import EmbeddingClient
from .retrieval import CorpusView, build_arms
from .router import Router
from .tools import ToolSurface


@dataclass(frozen=True)
class Request:
    """What a caller actually has: a question, some documents, and a budget.

    This is the product's input vocabulary. The bench's task record is derived from it
    (`as_task`), never the other way round — a request does not have a `task_id`, a
    `cell`, or a list of which units bear the answer, and pretending it does is how a
    decision layer ends up unusable outside the harness that grew it.
    """

    question: str
    documents: dict[str, str]
    budget_tokens: int
    # Declared by the caller, never inferred. `sense()` asserts these as COMPUTED with
    # credence 1.0, so inferring them from the text would put a guess where the belief
    # layer promises a fact.
    irreversible: bool = False
    shared_writes: bool = False
    regulated: bool = False
    # An exact-match oracle, when the caller has one. Its presence is what makes the
    # cascade admissible: escalating on observed failure needs a cheap failure detector.
    oracle: list[str] = field(default_factory=list)
    # EL DOMINIO SOBRE EL QUE LA RESPUESTA TIENE QUE SER COMPLETA, si el caller lo tiene.
    # Se declara, como `irreversible`: deducirlo del enunciado seria construir el sensor
    # sobre prosa libre, que es exactamente lo que la capa de creencias no acepta.
    #
    # Vacio = sin contrato de completitud, no «completitud trivialmente satisfecha». Las
    # dos cosas se ven igual en la salida y son opuestas, asi que el veredicto lo dice.
    completeness_domain: list[str] = field(default_factory=list)
    request_id: str = ""

    def identity(self) -> str:
        """A stable id for the record. Content-addressed when the caller gave none, so
        the same request twice is the same line in the log rather than two."""
        if self.request_id:
            return self.request_id
        blob = f"{self.question}|{sorted(self.documents)}|{self.budget_tokens}"
        return "req-" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    def as_task(self) -> dict[str, Any]:
        """The decision layer's vocabulary, derived from the caller's."""
        return {
            "task_id": self.identity(),
            "question": self.question,
            "unit_ids": sorted(self.documents),
            "budget_tokens": int(self.budget_tokens),
            "oracle": list(self.oracle),
            "has_oracle": bool(self.oracle),
            "irreversible": self.irreversible,
            "shared_writes": self.shared_writes,
            "regulated": self.regulated,
            "domain_keys": list(self.completeness_domain),
        }


@dataclass
class Answer:
    """What came back, and everything needed to defend how."""

    outcome: str  # "answered" | "gated" | "deferred"
    text: str
    paradigm: str
    explain: dict[str, Any]
    usage: dict[str, Any] = field(default_factory=dict)
    probe: dict[str, Any] | None = None
    ladder_run: list[dict[str, Any]] = field(default_factory=list)
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        body = {
            "outcome": self.outcome,
            "answer": self.text,
            "paradigm": self.paradigm,
            "usage": self.usage,
            "explain": self.explain,
        }
        if self.probe is not None:
            body["probe"] = self.probe
        if self.ladder_run:
            body["cascade"] = self.ladder_run
        if self.note:
            body["note"] = self.note
        return body


def _surface(request: Request, settings: Settings) -> ToolSurface:
    """The same surface a measured paradigm gets, over the caller's documents.

    `relevant_units` is empty and that is correct: it is the bench's ground truth about
    which units bear the answer, and a real request does not know it. Nothing in the
    surface's behaviour depends on it — only its recall accounting does, which is the
    bench's business.
    """
    view = CorpusView(
        task_id=request.identity(),
        documents=request.documents,
        unit_ids=sorted(request.documents),
        relevant_units=[],
    )
    # build_arms, not hand-assembled: the bench's fused retriever and the product's
    # have to be the same object, or the measured surface stops being the served one.
    arms = build_arms(
        embedder=EmbeddingClient(settings, settings.embedding_deployment)
    )
    return ToolSurface(
        view=view,
        hybrid=arms["hybrid"],
        semantic=arms["semantic"],
        lexical=arms["lexical"],
        variant="basic",
        budget_tokens=int(request.budget_tokens),
    )


def answer(
    request: Request,
    settings: Settings,
    bundle: PolicyBundle,
    requested: Assurance = Assurance.STANDARD,
    probe: bool = True,
    store: Any = None,
) -> Answer:
    """Decide, then execute what was decided — and record both."""
    # EL DIAL DECLARABA UNA GARANTIA QUE NADIE IMPONIA. `theta_may_learn_online` vivia en
    # el perfil y no lo leia ningun camino: la invariante «nada aprende adentro de un
    # request» se cumplia porque `Plasticity.apply` solo se llama offline — o sea, por
    # casualidad. Una invariante que se cumple por casualidad la rompe el proximo cambio
    # sin que nada avise.
    #
    # Se impone acá, alrededor del request ENTERO, y no adentro de cada paradigma: el
    # punto es que NADA en este tramo pueda acumular, venga de donde venga.
    with no_online_learning():
        result = _answer(request, settings, bundle, requested, probe)

    # EL PRODUCTO NO DEJABA RASTRO. `serve.py` decidia, ejecutaba, respondia — y no
    # escribia nada. Consecuencias, y son las mismas que el banco ya pago tres veces:
    #
    #   sin registro de la decision   no hay EXPLAIN que auditar despues de responder
    #   sin log de creencias          la calibracion nunca se computa, asi que
    #                                 `trusts_elicited` no se gana NUNCA en produccion
    #
    # Se persiste acá, alrededor del request entero y despues de decidir, por la misma
    # razon que la guarda de aprendizaje: un solo lugar, y nada adentro puede olvidarlo.
    if store is not None:
        _record(store, request, result, requested)
    return result


def _record(store: Any, request: Request, result: Answer,
            requested: Assurance) -> None:
    """Dejar rastro de una decision de produccion. Lo que se puede, y solo eso.

    LO QUE SE ESCRIBE. El plan entero —la decision, sus motivos tipados, la sonda si
    corrio, el consumo— y la base de creencias cuando el perfil lo declara.
    Honrar `log_belief_base` es lo unico que puede alimentar la calibracion, y sin
    calibracion el piso derivado se queda en OBSERVED para siempre.
    """
    from .assurance import PROFILES

    # EL NIVEL EFECTIVO, no el pedido. La garantia puede haber SUBIDO por lo que el
    # request declara —una accion irreversible fuerza el piso— y registrar el pedido
    # diria que se decidio bajo una garantia mas floja de la que se aplico.
    #
    # Si el plan no lo trae en la forma esperada se cae al pedido y NO se inventa: es
    # un dato del plan, y suponerlo seria escribir algo que nadie decidio.
    stated = result.plan.get("assurance")
    resolved = stated.get("level") if isinstance(stated, dict) else stated
    profile = PROFILES.get(resolved, PROFILES[requested])

    store.append_decision({
        "request_id": request.identity(),
        "plan": result.plan,
        "answer": result.answer,
        "citations": list(result.citations),
        "usage": result.usage.as_dict() if hasattr(result.usage, "as_dict") else {},
    })

    if profile.log_belief_base:
        store.append_belief_base(
            result.plan.get("beliefs", {}),
            context={
                "task_id": request.identity(),
                "region": result.plan.get("region", ""),
                "assurance": getattr(profile.level, "label", str(profile.level)),
                "action": result.plan.get("action", ""),
                "paradigm": result.plan.get("paradigm", ""),
                "theta_version": result.plan.get("theta_version", 0),
            },
        )

    # LO QUE NO SE ESCRIBE, Y POR QUE. Un `Episode` — que es lo que theta aprende — lleva
    # `was_best`, y eso exige saber que habrian hecho los OTROS paradigmas. Produccion
    # corre uno solo. Fabricar el campo enseñaria que el brazo elegido siempre gana, que
    # es la forma exacta de que un sistema aprenda de su propia eleccion.
    #
    # Asi que el bucle se cierra hasta donde la evidencia alcanza: produccion alimenta
    # CALIBRACION —opinion contra observacion, que si se puede adjudicar por request— y
    # no alimenta UTILIDAD. Cerrarlo del todo necesita un detector barato, que es
    # exactamente lo que `has_oracle` declara y casi ninguna tarea real tiene.


def _answer(
    request: Request,
    settings: Settings,
    bundle: PolicyBundle,
    requested: Assurance,
    probe: bool,
) -> Answer:
    task = request.as_task()
    # EL POOL SOLO EXISTE SI HAY CATALOGO. Con un solo modelo el sistema corre como
    # siempre y el plan dice `model=""` — que es distinto de mentir un nombre por omision.
    pool = ModelPool(settings, settings.model_deployments) if (
        len(settings.model_deployments) > 1
    ) else None
    # El cliente de PLANIFICACION es el barato: sondear y sensar no son la respuesta, y
    # pagarlos al precio del caro compraria precision donde no decide nada.
    client = (
        pool.client_for(pool.models[0].name) if pool else LLMClient(settings)
    )
    surface = _surface(request, settings)
    # La confianza en credencia elicitada va ADENTRO del bundle firmado, no como
    # parametro: un parametro se puede olvidar en un sitio de construccion.
    router = Router(bundle, COST_PRIORS, FALLBACK)

    # Computable features only. The derived ones cost a call and the probe below is the
    # honest way to pay for evidence: an estimate that nothing checks would enter the
    # belief base as ELICITED and the assurance dial would have to distrust it anyway.
    # `as_task()` ya tradujo el request al vocabulario de la decision, asi que el payload
    # sale de ahi y no de una segunda lectura del request. Eran los mismos valores
    # escritos dos veces, y esa es la forma en que dos copias empiezan a diferir.
    features, _ = FeatureExtractor().extract(payload_for(task), allow_derived=False)
    features = replace(
        features,
        continuation=measure_continuation(request.documents, task["unit_ids"]),
    )

    # El ciclo, una sola vez y compartido con el banco (app/decide.py). Copiarlo aca
    # habria dado dos implementaciones de una decision, libres de separarse.
    decision = decide_once(
        task,
        router=router,
        features=features,
        candidates=sorted(REGISTRY),
        documents=request.documents,
        requested=requested,
        client=client,
        surface=surface,
        probe=probe,
        models=pool.models if pool else None,
    )
    plan = decision.plan
    features = decision.features
    reading = decision.probe

    # EL MODELO ES PARTE DE LA ACCION, asi que la EJECUCION cambia de cliente. Planificar
    # barato y ejecutar con el que el plan eligio es la unica lectura coherente de «el
    # modelo se elige»: si se planificara con uno y se ejecutara con otro sin decirlo, el
    # EXPLAIN registraria una decision que no ocurrio.
    if pool and plan.model:
        client = pool.client_for(plan.model)

    explain = plan.explain()
    probe_record = reading.as_dict() if reading else None

    # REC F3: the counterfactual reading of THIS decision travels with it. Pure CPU,
    # replayable from the record alone (no model, no corpus): which minimal admitted
    # belief change would have altered the plan, and what evidence strength it needs.
    # This is what the offline clause-learning loop consumes — and what an auditor
    # reads to see whether the decision was belief-sensitive at all.
    diagnosis_policy = BeliefPolicy(
        derived_floor=Provenance(
            plan.assurance.get("profile", {}).get("derived_floor", "observed")
        ),
        tau=bundle.tau,
    )
    explain["rec_diagnosis"] = rec_diagnose(
        plan.verdict.get("beliefs", {}).get("beliefs", []),
        diagnosis_policy,
        fallback=bundle.fallback,
    ).as_dict()

    if plan.gated:
        # Lo que costo DECIDIR ya viene contado en la decision: reconstruirlo aca
        # era una tercera copia de la misma aritmetica, y las tres podian separarse.
        gate_usage = Usage()
        gate_usage.merge(decision.usage)
        # Nothing runs. The caller asked for something whose consequences a human owns,
        # and returning a plan is the whole answer.
        return Answer(
            outcome="gated",
            text="",
            paradigm=plan.paradigm,
            explain=explain,
            usage=gate_usage.as_dict(),
            probe=probe_record,
            note=(
                "This request is gated: it declares an irreversible action or a write to "
                "shared state. The plan is returned for review; nothing was executed."
            ),
        )

    if decision.unresolved:
        # FAIL-CLOSED. The plan still wants evidence nobody produced — probing was
        # disabled, or the reading did not reach the floor the rules demand. The
        # paradigm on the plan is a PLACEHOLDER the probe rule chose as "cheapest to
        # try after probing"; executing it as if it were a decision would act on
        # evidence the gate just said is insufficient. Deferring to the fallback is
        # the honest move, and it is recorded as exactly that.
        fallback_result = REGISTRY[bundle.fallback](client, surface, task)
        deferred_usage = Usage()
        deferred_usage.merge(decision.usage)
        deferred_usage.merge(fallback_result.usage)
        return Answer(
            outcome="deferred",
            text=fallback_result.answer,
            paradigm=bundle.fallback,
            explain=explain,
            usage=deferred_usage.as_dict(),
            probe=probe_record,
            note=(
                "the probe requirement was not resolved (probing disabled, or the "
                "reading stayed below the required provenance floor): the fallback "
                "ran instead of the plan's placeholder paradigm"
            ),
        )

    # Decidir cuesta tokens, y esos tokens estan en la factura: una sonda que no
    # llega al total hace que el camino gobernado parezca tan barato como el ciego,
    # que es des-medir el unico trade-off que esta capa existe para tasar.
    usage = Usage()
    usage.merge(decision.usage)
    ladder: list[dict[str, Any]] = []

    if plan.ladder and len(plan.ladder) > 1 and request.oracle:
        # Cascade: run rungs until the cheap detector says the answer is good. Only
        # admissible WITH an oracle -- escalating on observed failure requires observing
        # the failure, and without a detector this degenerates into paying for the whole
        # ladder every time.
        text = ""
        for rung in plan.ladder:
            result = REGISTRY[rung](client, surface, task)
            usage.merge(result.usage)
            score = detector_score(result.answer, request.oracle)
            ladder.append(
                {"paradigm": rung, "utility": round(score, 3),
                 "tokens": result.usage.total_tokens}
            )
            text = result.answer
            if score >= 1.0:
                return Answer(
                    outcome="answered",
                    text=text,
                    paradigm=rung,
                    explain=explain,
                    usage=usage.as_dict(),
                    probe=probe_record,
                    ladder_run=ladder,
                )
        return Answer(
            outcome="answered",
            text=text,
            paradigm=plan.ladder[-1],
            explain=explain,
            usage=usage.as_dict(),
            probe=probe_record,
            ladder_run=ladder,
            note="the whole ladder ran and no rung satisfied the detector",
        )

    result = REGISTRY[plan.paradigm](client, surface, task)
    usage.merge(result.usage)
    deferred = plan.paradigm == bundle.fallback and plan.action == "defer_to_fallback"
    return Answer(
        outcome="deferred" if deferred else "answered",
        text=result.answer,
        paradigm=plan.paradigm,
        explain=explain,
        usage=usage.as_dict(),
        probe=probe_record,
        note=(
            "the router abstained: no paradigm had a margin it trusted in this region, "
            "so the general fallback ran. This is a recorded abstention, not a choice."
            if deferred
            else ""
        ),
    )
