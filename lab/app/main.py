"""FastAPI surface over the harness.

Thin by design: every endpoint delegates to `Runner`, `Router` or `Study`. The science
lives in those modules and must be runnable from a plain script, because an experiment
that can only be reproduced through an HTTP server is not reproducible.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import Settings
from .paradigms import COST_PRIORS, FALLBACK, REGISTRY
from .assurance import Assurance
from .llm import LLMClient
from .policy import Plasticity, PolicyBundle, promote
from . import serve
from .probe import probe_coupling
from .rules import ELICITED_PRIOR_CREDENCE
from .beliefs import Provenance
from .router import Router
from .runner import Runner

app = FastAPI(title="lab", version="0.1.0")
settings = Settings.from_env()

POLICY_DIR = settings.results_dir / "policies"


class RunRequest(BaseModel):
    """Pedido de `/run`: correr el producto cruzado sobre un corpus. Es del BANCO.

    `resume=True` por defecto, y no es una comodidad: una corrida cortada se retoma sin
    re-pagar las celdas hechas, porque el resume va por `(tarea, paradigma, trial)`.
    Ponerlo en `False` re-ejecuta todo — sobre el caché sale gratis, contra el proveedor
    no, y esa diferencia no la dice el flag sino `calls - cached_calls`.

    `paradigms=None` significa el plantel de campaña, no «todos»: correr un brazo retirado
    exige nombrarlo, y la razón queda en el log.
    """

    corpus: str
    paradigms: list[str] | None = None
    limit: int | None = Field(default=None, ge=1)
    resume: bool = True


class DecideRequest(BaseModel):
    """Pedido de `/decide`: la capa de decisión sobre UNA tarea, sin ejecutarla.

    Es el endpoint que muestra el producto y no el banco: factibilidad → creencias con
    procedencia → dial de garantía → ruteo o abstención → `EXPLAIN`. No llama al modelo
    para resolver la tarea; decide qué haría y por qué.

    `assurance` es lo que el llamador PIDE, y el nivel efectivo es
    `max(pedido, piso de creencias, piso aprendido)`: puede subir, nunca bajar. El piso
    sale de propiedades del request mismo —`irreversible` eleva a A3, `shared_writes` a
    A2— así que un llamador que pudiera bajarlo podría declarar una acción irreversible y
    después pedir tratarla como exploratoria, que es la combinación exacta que el piso
    existe para impedir.

    La sonda está APAGADA por defecto: cuesta una llamada barata, y así `/decide` sigue
    siendo gratis de llamar y quien la paga es quien la pidió.
    """

    corpus: str
    task_id: str
    assurance: Assurance = Assurance.STANDARD
    # A probe costs one cheap call. Off by default so /decide stays free to call, and
    # so that whoever pays for it is the one who asked for it.
    probe: bool = True


class PromoteRequest(BaseModel):
    """Pedido de `/promote`: intentar instalar un θ candidato como política viva.

    ES EL ÚNICO CAMINO A PRODUCCIÓN. `report()` ajusta candidatos y los persiste en
    `fitted/`, **fuera** del glob que trata a un bundle como vivo: una lectura no puede
    instalar. Acá se corre la guarda anti-regresión sobre episodios held-out, y el
    candidato entra sólo si no empeora.

    `holdout_fraction` parte por TAREA y no por fila: una partición por fila dejaría
    réplicas de la misma tarea a los dos lados, y entonces el holdout estaría puntuando
    una regla con datos que la propusieron.

    `tau` es el umbral de abstención — cuánto margen exige θ para opinar en vez de
    diferir al fallback. Vale `0,3` en el bundle **desde siempre y sin haberse ajustado
    nunca**: es un parámetro que gobierna la curva riesgo-cobertura que el paper reporta,
    fijado a mano, y eso está anotado como deuda.
    """

    corpus: str
    tau: float = Field(default=0.3, ge=0.0, le=1.0)
    holdout_fraction: float = Field(default=0.3, gt=0.0, lt=1.0)


def _current_bundle() -> PolicyBundle:
    POLICY_DIR.mkdir(parents=True, exist_ok=True)
    bundles = sorted(POLICY_DIR.glob("theta_v*.json"))
    if not bundles:
        cold = PolicyBundle.cold_start(fallback=FALLBACK, tau=0.3)
        cold.save(POLICY_DIR)
        return cold
    return PolicyBundle.load(bundles[-1])


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "fingerprint": settings.fingerprint(),
        "paradigms": sorted(REGISTRY),
        "fallback": FALLBACK,
        "assurance_levels": [a.label for a in Assurance],
    }


@app.get("/corpus/{name}")
def corpus_manifest(name: str) -> dict[str, Any]:
    path = settings.corpus_dir / name / "manifest.json"
    if not path.exists():
        raise HTTPException(404, f"No corpus manifest at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/run")
def run(request: RunRequest) -> dict[str, Any]:
    unknown = set(request.paradigms or []) - set(REGISTRY)
    if unknown:
        raise HTTPException(400, f"Unknown paradigms: {sorted(unknown)}")

    runner = Runner(settings, request.corpus)
    rows = runner.run_cross_product(
        paradigms=request.paradigms, limit=request.limit, resume=request.resume
    )
    return {
        "executed": len(rows),
        "errors": sum(1 for r in rows if r.error),
        "results_file": str(settings.results_dir / f"{request.corpus}_rows.jsonl"),
    }


@app.get("/report/{corpus}")
def report(corpus: str, assurance: Assurance = Assurance.STANDARD) -> dict[str, Any]:
    runner = Runner(settings, corpus)
    if not runner.load_rows():
        raise HTTPException(409, "No results yet. POST /run first.")
    body = runner.report(assurance)
    runner.save_report(body)
    return body


@app.post("/decide")
def decide(request: DecideRequest) -> dict[str, Any]:
    runner = Runner(settings, request.corpus)
    task = next(
        (t for t in runner._tasks if t["task_id"] == request.task_id), None  # noqa: SLF001
    )
    if task is None:
        raise HTTPException(404, f"No task {request.task_id} in {request.corpus}")

    bundle = _current_bundle()
    router = Router(bundle, COST_PRIORS, FALLBACK)
    features = runner.features_for(task, allow_derived=True)
    plan = router.plan(
        task=task,
        candidates=sorted(REGISTRY),
        region=features.region(),
        requested=request.assurance,
        coupling=features.coupling,
        coupling_credence=(
            ELICITED_PRIOR_CREDENCE if features.coupling is not None else 0.0
        ),
        horizon_unknown=features.horizon_unknown,
        # Del MISMO acto de habla del modelo, pero declarado aparte: el horizonte no
        # hereda nada del acoplamiento, ni credencia ni procedencia.
        horizon_provenance=Provenance.ELICITED,
        horizon_credence=(
            ELICITED_PRIOR_CREDENCE if features.horizon_unknown is not None else 0.0
        ),
    )

    # probe_then_decide, executed rather than merely planned.
    #
    # The rule has always been able to demand a probe and the plan has always been able
    # to report `needs_probe`; nothing ever ran one, so a rule that required OBSERVED
    # provenance could never be satisfied and the request fell to the fallback for a
    # reason that had nothing to do with the request. With the assurance floor now
    # raising itself from rejection statistics (§6.2), that gap closes on its own into
    # a system that probes-and-never-probes.
    #
    # Deciding twice is the point: the first decision is what the system would have done
    # believing an estimate, the second is what it does having measured. Both are in the
    # artifact, so the probe's effect on the outcome is visible instead of implied.
    explained = plan.explain()
    if plan.needs_probe and request.probe:
        client = LLMClient(settings)
        surface = runner.surface_for(task)
        reading = probe_coupling(client, surface, task)
        replanned = router.plan(
            task=task,
            candidates=sorted(REGISTRY),
            region=features.region(),
            requested=request.assurance,
            coupling=reading.coupling,
            coupling_provenance=reading.provenance,
            coupling_credence=reading.credence,
            horizon_unknown=features.horizon_unknown,
            # La sonda midio ACOPLAMIENTO. El horizonte conserva lo que dijo el
            # extractor y NO sube a OBSERVED con evidencia que no lo tocó.
            horizon_provenance=Provenance.ELICITED,
            horizon_credence=(
                ELICITED_PRIOR_CREDENCE if features.horizon_unknown is not None else 0.0
            ),
        )
        explained = replanned.explain()
        explained["probe"] = {
            **reading.as_dict(),
            "plan_before_probe": {
                "action": plan.action,
                "paradigm": plan.paradigm,
            },
            "changed_the_decision": (
                plan.action != replanned.action or plan.paradigm != replanned.paradigm
            ),
        }
    return explained


class AnswerRequest(BaseModel):
    """A real request: a question, the documents, a budget. No task_id, no corpus."""

    question: str
    documents: dict[str, str]
    budget_tokens: int = Field(default=60_000, gt=0)
    irreversible: bool = False
    shared_writes: bool = False
    regulated: bool = False
    oracle: list[str] = Field(default_factory=list)
    assurance: Assurance = Assurance.STANDARD
    probe: bool = True


@app.post("/answer")
def answer_request(request: AnswerRequest) -> dict[str, Any]:
    """Decide AND execute, on documents the caller brought.

    /decide returns a plan; this returns what the plan produced. The difference is the
    difference between a decision layer and a product, and both endpoints exist because
    both questions are legitimate: "what would you do" is auditable on its own.
    """
    result = serve.answer(
        serve.Request(
            question=request.question,
            documents=request.documents,
            budget_tokens=request.budget_tokens,
            irreversible=request.irreversible,
            shared_writes=request.shared_writes,
            regulated=request.regulated,
            oracle=request.oracle,
        ),
        settings=settings,
        bundle=_current_bundle(),
        requested=request.assurance,
        probe=request.probe,
    )
    return result.as_dict()


@app.get("/policy")
def policy() -> dict[str, Any]:
    bundle = _current_bundle()
    return {
        "version": bundle.version,
        "signature": bundle.signature,
        "verified": bundle.verify(),
        "fallback": bundle.fallback,
        "tau": bundle.tau,
        "readable": bundle.explain_text(),
    }


@app.post("/policy/promote")
def policy_promote(request: PromoteRequest) -> dict[str, Any]:
    runner = Runner(settings, request.corpus)
    episodes = runner.episodes()
    if not episodes:
        raise HTTPException(409, "No episodes to learn from. POST /run first.")

    # Split by TASK, never by episode: the same task appearing in both halves would
    # leak the answer and make the promotion guard meaningless.
    task_ids = sorted({e.task_id for e in episodes})
    cut = int(len(task_ids) * (1.0 - request.holdout_fraction))
    train_ids, holdout_ids = set(task_ids[:cut]), set(task_ids[cut:])

    train = [e for e in episodes if e.task_id in train_ids]
    holdout = [e for e in episodes if e.task_id in holdout_ids]

    incumbent = _current_bundle()
    candidate = Plasticity.candidate(incumbent, train, tau=request.tau)

    def value_fn(bundle: PolicyBundle, eps: list[Any]) -> float:
        return Router(bundle, COST_PRIORS, FALLBACK).value_on(eps)

    verdict = promote(incumbent, candidate, holdout, value_fn)
    saved: str | None = None
    if verdict.accepted:
        saved = str(candidate.save(POLICY_DIR))

    return {
        "verdict": verdict.as_dict(),
        "train_tasks": len(train_ids),
        "holdout_tasks": len(holdout_ids),
        "installed": saved,
        "candidate_readable": candidate.explain_text(),
    }
