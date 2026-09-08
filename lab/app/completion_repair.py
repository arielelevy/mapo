"""One bounded repair driven by a declared-domain deficit, independent of the benchmark.

The caller authorizes the retry and supplies its limits. A coverage verdict is about names
addressed, not factual correctness. No oracle, relevant-unit labels or scoring enter here.
Both repair controls use the same prompt and limits; the code changes retrieval queries.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .contracts import complete_answer
from .llm import Usage
from .paradigms import ANSWER_CONTRACT, parse_answer
from .retrieval import CorpusView, LexicalRetriever

VERSION = "declared-domain-repair/1"
MODES = frozenset({"retain", "directed", "generic"})


@dataclass(frozen=True)
class RepairRequest:
    """Lo que el caller AUTORIZA para una reparacion, con sus limites adentro.

    Los limites viajan en el pedido y no en una constante del modulo porque una reparacion
    es gasto que alguien habilito: quien la pide declara cuanto. `__post_init__` los valida
    en el constructor, asi que un pedido mal formado no llega a hacer una llamada.

    `domain` son las claves declaradas que la respuesta tiene que cubrir. Es la entrada del
    diagnostico de completitud, y es del caller: el codigo cuenta cuales faltan, nunca las
    infiere del enunciado.
    """

    question: str
    domain: tuple[str, ...]
    unit_ids: tuple[str, ...]
    evidence_chars: int
    max_completion_tokens: int
    max_input_chars: int
    max_units: int

    def __post_init__(self) -> None:
        if not self.question.strip() or not self.domain:
            raise ValueError("Repair needs a question and an explicitly declared domain")
        if any(not k.strip() for k in self.domain) or len(set(self.domain)) != len(self.domain):
            raise ValueError("Domain keys must be nonempty and unique")
        if len(set(self.unit_ids)) != len(self.unit_ids):
            raise ValueError("Scope unit ids must be unique")
        if min(self.evidence_chars, self.max_completion_tokens,
               self.max_input_chars, self.max_units) <= 0:
            raise ValueError("All repair limits must be positive")


@dataclass
class RepairResult:
    """El resultado de una reparacion, con las DOS respuestas conservadas por separado.

    `original` y `candidate` no se pisan: una reparacion que empeora tiene que poder verse,
    y con una sola cadena el registro solo mostraria la ultima. `answer` es lo que se emite
    —`None` cuando se difiere—, que es la tercera cosa y no un alias de ninguna de las dos.

    `status` dice que paso, y una respuesta que sigue incompleta se difiere en vez de
    emitirse: el gasto quedo hecho igual y se cobra igual, asi que se registra igual.
    """

    original: str
    candidate: str
    answer: str | None
    status: str
    usage: Usage
    events: list[dict[str, Any]]

    def as_dict(self) -> dict[str, Any]:
        return {"version": VERSION, "original": self.original, "candidate": self.candidate,
                "answer": self.answer, "status": self.status,
                "usage": self.usage.as_dict(), "events": self.events}


def repair_once(request: RepairRequest, original: str, documents: Mapping[str, str],
                client: Any, *, mode: str) -> RepairResult:
    """Emit if complete; otherwise retrieve once, revise once, and recheck or defer.

The generic control has the identical trigger but retrieves for the original question.
Infrastructure exceptions propagate: an unavailable model is not a policy outcome.
Budget limits apply before reading/sending, and are recorded in characters plus output
tokens; they are not presented as an exact input-token count.
"""
    if mode not in MODES:
        raise ValueError(f"Unknown repair mode: {mode}")
    absent = set(request.unit_ids) - documents.keys()
    if absent:
        raise ValueError(f"Scope contains unavailable units: {sorted(absent)}")
    verdict = complete_answer(original, list(request.domain))
    events = [{"node": "check_initial", "verdict": verdict.as_dict()}]
    result = RepairResult(original, original, None, "deferred", Usage(), events)
    if verdict.emitted:
        result.answer, result.status = original, "unchanged"
        events.append({"node": "emit_original"})
        return result
    if mode == "retain":
        events.append({"node": "defer", "reason": "retention_only"})
        return result

    queries = list(verdict.missing) if mode == "directed" else [request.question]
    # Gold is absent even from the view used by the retriever.
    view = CorpusView("repair", {u: documents[u] for u in request.unit_ids},
                      list(request.unit_ids), [])
    retriever = LexicalRetriever()
    rankings = [retriever.rank(view, q, request.max_units) for q in queries]
    # Round robin ensures that one missing key cannot consume the entire read allowance.
    ordered = list(dict.fromkeys(u for depth in range(request.max_units)
                                for ranking in rankings for u in ranking[depth:depth + 1]))
    blocks, selected, skipped = [], [], []
    for uid in ordered:
        if len(selected) >= request.max_units:
            break
        block = f"[{uid}]\n{documents[uid]}"
        if len("\n\n".join([*blocks, block])) > request.evidence_chars:
            skipped.append(uid)
            continue
        blocks.append(block)
        selected.append(uid)
    events.append({"node": "retrieve", "queries": queries, "units": selected,
                   "skipped_for_budget": skipped, "limits": asdict(request)})
    if not blocks:
        events.append({"node": "defer", "reason": "no_evidence_within_budget"})
        return result
    prompt = (
        f"Task: {request.question}\n\nPrevious answer:\n{original}\n\n"
        f"Additional evidence:\n{'\n\n'.join(blocks)}\n\n"
        "Using the evidence, revise the answer to the original task. Return the whole "
        "answer, preserving supported information. Do not invent missing facts.\n\n"
        f"{ANSWER_CONTRACT}"
    )
    if len(prompt) > request.max_input_chars:
        events.append({"node": "defer", "reason": "input_budget", "chars": len(prompt)})
        return result
    events.append({"node": "revise", "input_chars": len(prompt)})
    completion = client.complete(messages=[{"role": "user", "content": prompt}],
                                 max_tokens=request.max_completion_tokens)
    result.usage.merge(completion.usage)
    result.candidate = parse_answer(completion.text)
    after = complete_answer(result.candidate, list(request.domain))
    events.append({"node": "check_repair", "verdict": after.as_dict()})
    if after.emitted:
        result.answer, result.status = result.candidate, "repaired"
        events.append({"node": "emit_repair"})
    else:
        events.append({"node": "defer", "reason": "deficit_remains"})
    return result
