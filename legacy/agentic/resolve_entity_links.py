"""Resolve entity names in the answer to clickable entity links.

Searches each mentioned entity name against OpenSearch to find its
entity_id and entity_type, then replaces **name** with [name](entity:id/type).

After resolving, validates ALL entity links in the answer against OpenSearch:
  - Links with non-existent IDs are stripped (replaced with **name**)
  - Links with wrong entity_type are corrected to the real type from OS

Runs after strategy nodes, before verify_answer.
"""

import logging
import re

from langchain_core.callbacks import adispatch_custom_event
from langchain_core.runnables import RunnableConfig

from .state import OrchestratorState
from .tools.opensearch_repository import (
    batch_search_entity_by_label,
    batch_verify_entity_details,
    batch_verify_entity_types,
)

logger = logging.getLogger(__name__)

# Match **bold names** that aren't already entity links
BOLD_NAME_RE = re.compile(r"\*\*([^*]+)\*\*")
# Already an entity link (with type)
ENTITY_LINK_RE = re.compile(r"\[([^\]]+)\]\(entity:([^/\)]+)/([^)]+)\)")
# Malformed entity link (missing /type)
ENTITY_LINK_NO_TYPE_RE = re.compile(r"\[([^\]]+)\]\(entity:([a-f0-9-]{36})(?!/)\)")


async def resolve_entity_links(
    state: OrchestratorState, config: RunnableConfig
) -> dict:
    """Replace **bold names** with entity links, then validate all links."""
    answer = state.get("answer", "")
    if not answer or len(answer) < 20:
        return {}

    workspace_id = state.get("workspace_id", "")
    changed = False

    # --- Phase 1: Resolve bold names to entity links ---
    bold_names = set(BOLD_NAME_RE.findall(answer))
    if bold_names:
        existing_links = set(m.group(0) for m in ENTITY_LINK_RE.finditer(answer))
        search_names = [
            name
            for name in bold_names
            if len(name) >= 3
            and name.lower() not in {"yes", "no", "note", "source"}
            and not any(name in link for link in existing_links)
        ]
        if search_names:
            results = await batch_search_entity_by_label(
                search_names, workspace_id, config
            )
            for name, entity in results.items():
                if entity and entity["entity_id"]:
                    eid = entity["entity_id"]
                    etype = entity["entity_type"] or "entity"
                    link = f"[{name}](entity:{eid}/{etype})"
                    answer = answer.replace(f"**{name}**", link, 1)
                    changed = True

    # --- Phase 1b: Fix malformed links (missing /type) ---
    malformed = list(ENTITY_LINK_NO_TYPE_RE.finditer(answer))
    if malformed:
        mal_ids = list({m.group(2) for m in malformed})
        mal_verified = await batch_verify_entity_details(mal_ids, config)
        for match in reversed(malformed):
            label = match.group(1)
            eid = match.group(2)
            info = mal_verified.get(eid)
            if info and info["type"]:
                real_label = label
                if (
                    label.lower() in ("document", "source", "file", "doc")
                    and info["label"]
                ):
                    real_label = info["label"]
                fixed = f"[{real_label}](entity:{eid}/{info['type']})"
                answer = answer[: match.start()] + fixed + answer[match.end() :]
                changed = True
                logger.info(
                    "resolve_entity_links: fixed malformed link %s → %s/%s",
                    eid[:8],
                    real_label,
                    info["type"],
                )
            else:
                answer = (
                    answer[: match.start()] + f"**{label}**" + answer[match.end() :]
                )
                changed = True

    # --- Phase 2: Prevent hallucinations — verify entity links the LLM wrote ---
    all_links = list(ENTITY_LINK_RE.finditer(answer))
    if all_links:
        unique_ids = list({m.group(2) for m in all_links})
        verified = await batch_verify_entity_types(unique_ids, config)

        for match in reversed(all_links):
            name = match.group(1)
            eid = match.group(2)
            etype_in_answer = match.group(3)

            if eid not in verified:
                # ID doesn't exist — strip the link, keep name as bold
                answer = answer[: match.start()] + f"**{name}**" + answer[match.end() :]
                changed = True
                logger.info(
                    "resolve_entity_links: stripped invalid link %s (%s)",
                    eid,
                    name,
                )
            elif verified[eid] and verified[eid] != etype_in_answer:
                # ID exists but type is wrong — fix it
                correct_type = verified[eid]
                fixed_link = f"[{name}](entity:{eid}/{correct_type})"
                answer = answer[: match.start()] + fixed_link + answer[match.end() :]
                changed = True
                logger.info(
                    "resolve_entity_links: fixed type %s -> %s for %s",
                    etype_in_answer,
                    correct_type,
                    eid,
                )

        valid_count = sum(1 for m in all_links if m.group(2) in verified)
        stripped_count = len(all_links) - valid_count
        if stripped_count > 0:
            logger.info(
                "resolve_entity_links: %d valid, %d stripped",
                valid_count,
                stripped_count,
            )

    if changed:
        await adispatch_custom_event(
            name="on_ui_event",
            data={"channel": "text_replace", "content": answer},
            config=config,
        )
        return {"answer": answer}
    return {}
