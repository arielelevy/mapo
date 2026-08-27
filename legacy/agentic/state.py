"""LangGraph state definitions for the orchestrator pipeline."""

import operator
from collections.abc import Mapping
from typing import Annotated, Any, NotRequired, TypedDict

from langchain_core.messages import AIMessage, BaseMessage

from app.api.v1.ai.chat.chat_model import ChatRequest


class Extraction(TypedDict):
    name: str
    entity_type: str
    role: str
    context: str
    source_document: str
    no_relevant_info: NotRequired[bool]


# ---------------------------------------------------------------------------
# DAG strategy types
# ---------------------------------------------------------------------------


class SubQuestionDict(TypedDict):
    """Serialized form of strategies.dag_strategy.SubQuestion (with wave assigned)."""

    id: str
    question: str
    dependencies: list[str]
    priority: int
    context_from_deps: bool
    verification_criteria: str
    wave: int  # assigned by _assign_waves before the field is read


class DagExtraction(TypedDict):
    """Result produced by a single dag_execute sub-agent."""

    id: str
    result: str


class VerificationDict(TypedDict):
    """Serialized form of strategies.dag_strategy.VerificationResult."""

    sub_question_id: str
    status: str  # "complete" | "partial" | "incomplete"
    completeness_score: float
    missing_aspects: list[str]
    contradictions: list[str]
    recommendation: str  # "accept" | "retry"


class DagState(TypedDict, total=False):
    """All DAG-strategy state, grouped to keep OrchestratorState flat-ish."""

    sub_questions: list[SubQuestionDict]
    extractions: list[DagExtraction]  # accumulated across waves (merged by reducer)
    current_wave: int
    iteration: int  # replan iteration (0, 1, 2)
    verification: list[VerificationDict]  # last verify results (overwritten each cycle)
    prev_verification_avg: float  # prior iteration's avg completeness


def merge_dag_state(left: DagState | None, right: DagState | None) -> DagState:
    """Reducer for the grouped dag field.

    Merges shallowly, but concatenates the `extractions` list so fan-out
    sub-agents (dag_execute Sends) accumulate results across a wave.
    """
    if not left:
        return right or {}
    if not right:
        return left
    merged: DagState = {**left, **right}  # type: ignore[typeddict-item]
    left_ext = left.get("extractions")
    right_ext = right.get("extractions")
    if left_ext is not None and right_ext is not None:
        merged["extractions"] = left_ext + right_ext
    return merged


class OutputState(TypedDict):
    """Subset exposed as LangSmith 'Output' column."""

    strategy: str
    answer: str


class OrchestratorState(TypedDict):
    # Input from handle_chat (ChatState fields)
    request: ChatRequest
    username: str

    # Extracted from request by load_context
    query: str
    workspace_id: str
    suite: str
    context_doc_ids: list[str]
    followup_doc_ids: list[
        str
    ]  # doc IDs parsed from entity links in prior assistant responses
    messages: list[BaseMessage]
    history_text: str  # formatted turns: "[Turn 1] User: ... \n[Turn 1] Assistant: ..."

    # understand_query output
    strategy: (
        str  # "react_agent" | "map_reduce" | "plan_execute" | "dag" | "conversational"
    )
    forced_strategy: (
        str  # set from ChatRequest.strategy, bypasses classification when non-empty
    )
    rewritten_query: str  # query optimized for retrieval (translated, reformulated)
    router_reasoning: str
    document_domain: str  # "legal" | "financial" | "forensic" | "criminology" | "intelligence" | "general"
    complexity: str  # "simple" | "moderate" | "complex"
    entity_context: str
    doc_ner_entities: (
        dict  # NER entities from context docs {type: [names]} from ner:entities
    )
    key_terms: list[str]  # search terms in doc language + English
    entity_types_filter: list[str]  # entity type filters from classification
    history_relevant: bool  # whether chat history is relevant (follow-up query)
    followup_type: str  # "standalone" | "drill_down" | "expansive"
    query_language: str  # detected language of user's query (e.g. "English", "Spanish")
    document_languages: list[str]  # detected from docs (e.g. ["Italian", "English"])
    hyde_queries: list[str]  # hypothetical document embeddings for KNN search
    prefetch_results: dict  # retrieval results (structured) from pre_fetch node

    # Map-reduce accumulators
    documents: list[dict]  # used by mr_list_docs (actual doc IDs)
    extractions: Annotated[list[Extraction], operator.add]

    # Plan-execute
    pe_sub_queries: list[str]  # used by pe_plan (sub-query texts)

    # DAG strategy (VMAO-inspired) — grouped under one key with a custom reducer
    # so fan-out sub-agents accumulate `extractions` across a wave.
    dag: Annotated[DagState, merge_dag_state]

    # Final
    answer: str
    response: AIMessage | None
    confidence_score: float  # 0-1 from verify_answer
    unsupported_claims: list[str]  # claims not backed by context
    verification_status: str  # "passed" | "failed" | "retry" | ""
    tool_context: str  # accumulated tool outputs for faithfulness check
    verify_retried: bool  # whether verify_answer already triggered a retry
    total_chunks: int  # total chunks across all context docs (from load_context)
    has_fragments: bool  # True if index has os_fragment entities (pages). BM25 skips os_file when True.
    # Anything that silently narrowed the corpus (a search set that failed to expand, a
    # document cap that dropped documents). Carried so the answer can say so instead of
    # looking complete over half the material.
    scope_warnings: list[str]


def format_history_turns(messages: list[BaseMessage], max_messages: int = 6) -> str:
    """Format message history as numbered turns.

    Output:
        [Turn 1] User: ...
        [Turn 1] Assistant: ...
        [Turn 2] User: ...
    """
    if not messages:
        return ""
    turn = 0
    parts = []
    for m in messages[-max_messages:]:
        is_user = hasattr(m, "type") and m.type == "human"
        if is_user:
            turn += 1
        role = "User" if is_user else "Assistant"
        content = str(m.content)
        if not is_user and len(content) > 1000:
            content = content[:1000] + "…"
        parts.append(f"[Turn {turn}] {role}: {content}")
    return "\n".join(parts)


def get_scoped_doc_ids(state: OrchestratorState | Mapping[str, Any]) -> list[str]:
    """Return the doc IDs to scope searches to.

    Only narrows scope on drill_down follow-ups (user asks for more detail
    about something already in the prior response). Uses followup_doc_ids
    so the search targets only the cited documents.

    On expansive follow-ups (user asks about something NOT in the prior
    response, e.g. "ya singapur??" after a trip list that didn't mention
    Singapore), returns full context_doc_ids so new documents can be found.

    Used by: pre_fetch, react_agent, map_reduce, plan_execute, dag.
    """
    if state.get("followup_type") == "drill_down" and state.get("followup_doc_ids"):
        return state["followup_doc_ids"]
    return state.get("context_doc_ids", [])


class DocProcessState(TypedDict):
    """Per-document state for map-reduce fan-out."""

    query: str
    doc_id: str
    document_domain: str
    query_language: str
    extractions: list[Extraction]


class SubQueryState(TypedDict):
    """Per sub-query state for plan_execute fan-out."""

    sub_query: str
    workspace_id: str
    suite: str
    context_doc_ids: list[str]
    entity_context: str
    prefetch_results: dict
    document_domain: str
    query_language: str
    history_text: str
    # Carried into the fan-out: without them the sub-agent's find_recurring_names has
    # no candidate set and answers "none" to every cross-document question.
    doc_ner_entities: dict
    entity_types_filter: list[str]
    scope_warnings: list[str]
    result: str


class DagSubQueryState(TypedDict):
    """Per sub-question state for DAG strategy fan-out."""

    sub_question_id: str
    sub_question: str
    verification_criteria: str
    dependency_context: str  # injected results from deps (wave 1+)
    workspace_id: str
    suite: str
    context_doc_ids: list[str]
    entity_context: str
    prefetch_results: dict | str
    document_domain: str
    query_language: str
    history_text: str
    doc_ner_entities: dict
    entity_types_filter: list[str]
    scope_warnings: list[str]
