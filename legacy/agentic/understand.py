"""Query understanding: follow-up resolution, NER, rewrite, strategy classification."""

import logging
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field

from .agent_config import (
    QUERY_SHAPE_LANGUAGE_RULE,
    RESOLVE_FOLLOWUP_PROMPT,
    UNDERSTAND_PROMPT,
)
from .config import (
    TEMP_CLASSIFY,
    get_chat_model,
)
from .state import OrchestratorState, format_history_turns
from .utils import emit_ui_event

logger = logging.getLogger(__name__)

STRATEGY_LABELS = {
    "react_agent": "Searching and analyzing",
    "react_agent_exhaustive": "Exhaustive search and analyzing",
    "map_reduce": "Summarizing all documents",
    "plan_execute": "Complex task execution",
    "dag": "Multi-query decomposition",
    "conversational": "Responding",
}


# ---------------------------------------------------------------------------
# Structured output schemas
# ---------------------------------------------------------------------------


class QueryShape(BaseModel):
    """Everything that can be decided from the query and the history alone.

    Language detection and follow-up classification were two separate mini calls that
    saw the same material and neither of which saw any document. Merging them keeps the
    property that justified the isolation — no contamination from the document
    languages — and costs one call instead of two on every single request.
    """

    query_language: str = Field(
        default="English",
        description=(
            "Language of the user's query, by sentence structure, ignoring proper "
            "nouns. E.g. English, Spanish, Italian."
        ),
    )
    followup_type: Literal["standalone", "drill_down", "expansive"] = Field(
        default="standalone",
        description=(
            "standalone: new topic or generic command. "
            "drill_down: more detail on something already in the prior response. "
            "expansive: references conversation topic but asks about something NOT in the prior response."
        ),
    )


class ExtractedEntity(BaseModel):
    name: str = Field(description="Entity name, e.g. 'Valerio Simoni'")
    type: str = Field(
        default="", description="Entity type, e.g. 'person', 'location', 'document'"
    )


class UnderstandResult(BaseModel):
    extracted_entities: list[ExtractedEntity] = Field(
        default_factory=list,
        description="Named entities extracted from the query",
    )
    rewritten_query: str = Field(
        default="",
        description=(
            "Query rewritten for optimal retrieval. Keep it SHORT (1-2 sentences). "
            "Do NOT include document names, context, or metadata — only the question. "
            "MUST stay in the SAME language as the user's question — NEVER translate. "
            "If user asked in English, rewrite in English. Include key entity names. "
            "If chat history is provided (follow-up), resolve pronouns and references "
            "to actual names from the history, but keep the query language unchanged."
        ),
    )
    key_terms: list[str] = Field(
        default_factory=list,
        description=(
            "8-20 key search terms for retrieval. Include: "
            "1) terms in the document language AND English, "
            "2) specific numbers, article numbers, dates, and identifiers mentioned in the query, "
            "3) related concepts and synonyms the documents might use instead of the user's words. "
            "Think about what words the DOCUMENTS would use, not just the user's words."
        ),
    )
    entity_types_filter: list[str] = Field(
        default_factory=list,
        description=(
            "Which 1-2 NER entity types are MOST relevant to answering this query. "
            "Pick ONLY from the 'Available NER entity types' listed in the context. "
            "E.g. 'who is the victim' → ['person'], "
            "'when was he killed' → ['date'], "
            "'where did it happen' → ['loc'], "
            "'what address' → ['loc'], "
            "'recurring names across documents' → ['person'], "
            "'which organizations' → ['org'], "
            "'contact info' → ['phone', 'email']. "
            "Empty = no NER filtering needed."
        ),
    )
    document_domain: str = Field(
        default="general",
        description=(
            "Detected domain: legal, financial, forensic, criminology, intelligence, general. "
            "court/judgment/appeal → legal, SAR/bank/transaction → financial, "
            "victim/DNA/autopsy → forensic, trafficking/recruiter → criminology."
        ),
    )
    complexity: Literal["simple", "moderate", "complex"] = Field(
        default="moderate",
        description=(
            "Query complexity. simple: single fact lookup (name, date, yes/no). "
            "moderate: requires reading 1-3 documents. "
            "complex: requires comparing multiple documents, extracting exhaustive lists, "
            "or analyzing across multiple phases/years/subjects."
        ),
    )
    needs_decomposition: bool = Field(
        default=False,
        description=(
            "True when the query contains MULTIPLE INDEPENDENT sub-questions that "
            "benefit from being answered separately and then combined. Examples: "
            "'For each judgment from 2009 to 2016, state the outcome' (one sub-Q per year), "
            "'Compare X across documents A, B, C' (one sub-Q per document). "
            "False for single questions even if complex: 'extract all addresses of X' "
            "is ONE question answered by scanning documents, not multiple sub-questions."
        ),
    )
    exhaustive_extraction: bool = Field(
        default=False,
        description=(
            "True when the query demands COMPLETENESS — finding all items or "
            "covering all instances across the document set. Set True if ANY of: "
            "(1) 'extract ALL X', 'list ALL X', 'find ALL X' — exhaustive list of entities; "
            "(2) 'for each X', 'separately for each X' — iterate over multiple items/years/phases; "
            "(3) 'how many X' when X requires scanning multiple documents; "
            "(4) 'who are the most/all X', 'are there other X', 'are there names that appear both as A and B' — "
            "requires scanning many docs to compare/aggregate; "
            "(5) 'is X part of a larger ring/network' — requires gathering all evidence. "
            "Set False ONLY for: images/photos, single-document extraction, "
            "summaries, timelines, simple yes/no questions, specific fact lookups "
            "in 1-2 docs ('what is the victim's name')."
        ),
    )
    strategy: Literal["react_agent", "conversational"] = Field(
        default="react_agent",
        description=(
            "conversational for greetings, thanks and small talk; react_agent for "
            "everything else. This field ONLY separates chat from work — the actual "
            "strategy is decided from needs_decomposition and complexity."
        ),
    )
    reasoning: str = Field(
        default="",
        description="One sentence explaining why this strategy was chosen",
    )


# ---------------------------------------------------------------------------
# QueryUnderstanding
# ---------------------------------------------------------------------------


class QueryUnderstanding:
    """LangGraph node: analyse the user query before strategy execution.

    Two lightweight (mini) LLM calls:

    1. **Query shape** (_query_shape):
       - Language of the query, and whether it is standalone, drill_down or expansive.
       - Does NOT rewrite the query — keeps the original language intact.
       - Sees the query and the history only, never document content.

    2. **Strategy classification** (_classify):
       - Uses structured output (UnderstandResult) to produce in a single call:
         rewritten_query, key_terms, entity_types_filter, document_domain,
         query_language, and the chosen strategy.
       - For follow-ups, includes chat history so rewritten_query can resolve
         pronouns/references while preserving the original query language.
       - No strategy guards: the ones that used to be described here were commented
         out, and the comment claimed they were inactive because "strategy is always
         react_agent" — which stopped being true when dag and the exhaustive variant
         were added. The scope caps they described now live where they can be enforced
         and recorded (map_reduce applies its own document budget).

    State fields produced:
        strategy, rewritten_query, router_reasoning, document_domain,
        entity_context (with search hints appended), key_terms,
        entity_types_filter, doc_ner_entities, query, history_relevant,
        query_language.
    """

    async def __call__(
        self,
        state: OrchestratorState,
        config: RunnableConfig | None = None,
    ) -> dict:
        query = state.get("query", "")
        messages = state.get("messages", [])
        context_docs = state.get("context_doc_ids", [])
        entity_context = state.get("entity_context", "")
        followup_doc_ids = state.get("followup_doc_ids", [])

        # Forced strategy override — bypasses the CLASSIFIER, and only the classifier.
        # It used to return here with history_relevant=False and history_text="", so
        # forcing a strategy also silently switched off follow-up resolution: pronouns
        # stopped resolving and drill-down scoping stopped narrowing, for a flag that
        # says nothing about either.
        forced = (state.get("forced_strategy") or "").strip()
        if forced and forced not in STRATEGY_LABELS:
            logger.warning(
                "understand: unknown forced_strategy=%r, falling back to react_agent",
                forced,
            )
            forced = "react_agent"
        if forced:
            logger.info("understand: forced_strategy=%s (bypassing classifier)", forced)
            shape = await self._query_shape(query, messages, followup_doc_ids, config)
            history_relevant = shape.followup_type != "standalone"
            label = STRATEGY_LABELS.get(forced, forced)
            await emit_ui_event(config, label)
            return {
                "strategy": forced,
                "rewritten_query": query,
                "router_reasoning": f"forced via request.strategy={forced}",
                "key_terms": [],
                "entity_types_filter": [],
                "document_domain": "general",
                "complexity": "moderate",
                "history_relevant": history_relevant,
                "followup_type": shape.followup_type,
                "query_language": shape.query_language,
                "history_text": (
                    format_history_turns(messages) if history_relevant else ""
                ),
            }

        # Step 1: language + follow-up type, in ONE call (no document context)
        shape = await self._query_shape(query, messages, followup_doc_ids, config)
        query_language = shape.query_language
        followup_type = shape.followup_type
        history_relevant = followup_type != "standalone"
        history_text = format_history_turns(messages) if history_relevant else ""

        # Step 2: Classify strategy + extract key_terms, domain, entity_types
        result = await self._classify(
            query, state, context_docs, config, followup_type, history_text
        )

        # Routing:
        #   conversational → conversational
        #   multi-query (needs_decomposition) → dag (plan + waves + verify)
        #   single-query → react_agent (exhaustive mode if exhaustive_extraction)
        if result.strategy == "conversational":
            strategy = "conversational"
            reasoning = result.reasoning
        elif result.needs_decomposition:
            strategy = "dag"
            reasoning = (
                f"dag (needs_decomposition, {result.complexity}, {result.reasoning})"
            )
        elif result.complexity == "complex":
            strategy = "react_agent_exhaustive"
            reasoning = f"react_agent_exhaustive ({result.reasoning})"
        else:
            strategy = "react_agent"
            reasoning = f"react_agent ({result.complexity}, {result.reasoning})"

        # Follow-up emit
        if history_relevant:
            label = (
                f"Drill-down: {len(followup_doc_ids)} referenced documents"
                if followup_type == "drill_down" and followup_doc_ids
                else (
                    "Expansive follow-up: searching all documents"
                    if followup_type == "expansive"
                    else "Follow-up"
                )
            )
            await emit_ui_event(config, label)

        if result.key_terms:
            entity_context += (
                f"\n\n## Search hints\n"
                f"Use these terms for better results: {', '.join(result.key_terms)}"
            )

        rewritten_query = result.rewritten_query or query
        document_domain = result.document_domain or "general"

        logger.info(
            "understand_query: strategy=%s | exhaustive=%s | complexity=%s | decompose=%s | domain=%s | lang=%s | docs=%d | followup=%d | terms=%s | ner_filter=%s | %s",
            strategy,
            result.complexity == "complex",
            result.complexity,
            result.needs_decomposition,
            document_domain,
            query_language,
            len(context_docs),
            len(followup_doc_ids),
            result.key_terms,
            result.entity_types_filter,
            reasoning,
        )

        # NER entities passed as-is
        ner_entities = state.get("doc_ner_entities", {})

        # UI events
        label = STRATEGY_LABELS.get(strategy, strategy)
        domain_suffix = f" ({document_domain})" if document_domain != "general" else ""
        await emit_ui_event(config, f"{label}{domain_suffix}", tooltip=reasoning)
        if rewritten_query and rewritten_query != query:
            await emit_ui_event(config, f"Refined query: {rewritten_query}")
        if result.key_terms:
            await emit_ui_event(config, f"Search terms: {', '.join(result.key_terms)}")
        if query_language:
            await emit_ui_event(config, f"Query language: {query_language}")

        return {
            "strategy": strategy,
            "rewritten_query": rewritten_query,
            "router_reasoning": reasoning,
            "document_domain": document_domain,
            "entity_context": entity_context,
            "key_terms": result.key_terms,
            "entity_types_filter": result.entity_types_filter,
            "doc_ner_entities": ner_entities,
            "query": query,
            "history_relevant": history_relevant,
            "history_text": history_text,
            "followup_type": followup_type,
            "query_language": query_language,
            "complexity": result.complexity,
        }

    # ------------------------------------------------------------------
    # Step 1: query shape — language + follow-up, isolated from document context
    # ------------------------------------------------------------------

    async def _query_shape(
        self,
        query: str,
        messages: list,
        followup_doc_ids: list[str],
        config: RunnableConfig | None,
    ) -> QueryShape:
        """Language and follow-up type in one call.

        Runs on the query and the history only — no document context, no entity names —
        which is what keeps the language of the DOCUMENTS from being reported as the
        language of the QUESTION.
        """
        history_text = (
            format_history_turns(messages, max_messages=4) if messages else ""
        )
        doc_hint = ""
        if followup_doc_ids and messages:
            doc_hint = "\n\nDocument IDs from prior responses:\n" + "\n".join(
                followup_doc_ids
            )

        try:
            llm = await get_chat_model(config, temperature=0, mini=True)
            llm = llm.with_structured_output(QueryShape)
            content = (
                f"History:\n{history_text}{doc_hint}\n\nQuery: {query}"
                if history_text
                else f"Query: {query}"
            )
            result: QueryShape = await llm.ainvoke(  # type: ignore[assignment]
                [
                    SystemMessage(
                        content=RESOLVE_FOLLOWUP_PROMPT + QUERY_SHAPE_LANGUAGE_RULE
                    ),
                    HumanMessage(content=content),
                ]
            )
            if not messages:
                # With no history there is nothing to follow up on, whatever the model
                # says: the classification is only meaningful against a prior turn.
                result.followup_type = "standalone"
            result.query_language = (
                str(result.query_language).strip().strip(".") or "English"
            )
            logger.debug(
                "understand_query: shape=%s/%s for '%s'",
                result.query_language,
                result.followup_type,
                query[:50],
            )
            return result
        except Exception as e:
            logger.error("_query_shape failed: %s", e, exc_info=True)
            return QueryShape()

    # ------------------------------------------------------------------
    # Step 2: Classification
    # ------------------------------------------------------------------

    async def _classify(
        self,
        query: str,
        state: OrchestratorState,
        context_docs: list[str],
        config: RunnableConfig | None,
        followup_type: str = "standalone",
        history_text: str = "",
    ) -> UnderstandResult:
        """Classify the original query into strategy + metadata.

        When followup_type != "standalone", includes chat history so the LLM
        can resolve pronouns/references in rewritten_query while keeping
        the original query language intact.
        """
        llm = await get_chat_model(
            config,
            temperature=TEMP_CLASSIFY,
            mini=True,
        )
        llm = llm.with_structured_output(UnderstandResult)

        context_info = ""
        if state.get("workspace_id"):
            context_info += f"\nWorkspace: {state['workspace_id']}"
        if state.get("suite"):
            context_info += f"\nSuite: {state['suite']}"
        if context_docs:
            context_info += (
                f"\nContext docs ({len(context_docs)}): {', '.join(context_docs[:10])}"
            )

        ner_entities = state.get("doc_ner_entities", {})
        if ner_entities:
            ner_summary = ", ".join(f"{k} ({len(v)})" for k, v in ner_entities.items())
            context_info += f"\nAvailable NER entity types: {ner_summary}"

        # For follow-ups, include chat history so the LLM can resolve
        # pronouns and references in rewritten_query
        if history_text:
            context_info += f"\n\nChat history (this is a {followup_type} follow-up — resolve references in rewritten_query):\n{history_text}"

        result: UnderstandResult = await llm.ainvoke(  # type: ignore[assignment]
            [
                SystemMessage(
                    content=UNDERSTAND_PROMPT.replace(
                        "{document_languages}",
                        str(state.get("document_languages") or ["English"]),
                    )
                ),
                HumanMessage(content=f"Query: {query}{context_info}"),
            ]
        )
        return result
