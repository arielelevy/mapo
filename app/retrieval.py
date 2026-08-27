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


def tokenise(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if len(t) > 2]


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
    def rank(self, view: CorpusView, query: str, limit: int) -> list[str]: ...
    def describe(self) -> dict[str, Any]: ...


class LexicalRetriever:
    """BM25 over the task's units.

    IDF and length normalisation are the point. Without them a padded document ranks
    highly for being padded, which is the bias the corpus hardening introduced.
    """

    name = "lexical"

    def rank(self, view: CorpusView, query: str, limit: int) -> list[str]:
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
        return [unit_id for _, unit_id in scored[:limit]]

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
        query_vector = self._embedder.embed(query)
        scored: list[tuple[float, str]] = []
        for unit_id in view.unit_ids:
            similarity = cosine(query_vector, self._embedder.embed(view.documents[unit_id]))
            scored.append((similarity, unit_id))
        scored.sort(key=lambda pair: (-pair[0], pair[1]))
        return [unit_id for _, unit_id in scored[:limit]]

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

    def __init__(self, embedder: Any, depth: int = 40) -> None:
        self._lexical = LexicalRetriever()
        self._semantic = SemanticRetriever(embedder)
        # How deep each ranker contributes before fusion. Deeper than `limit` on
        # purpose: a unit ranked 15th by one ranker and 2nd by the other should be able
        # to surface, and it cannot if each list was already cut to the final size.
        self._depth = depth

    def rank(self, view: CorpusView, query: str, limit: int) -> list[str]:
        lists = [
            self._lexical.rank(view, query, self._depth),
            self._semantic.rank(view, query, self._depth),
        ]
        fused: dict[str, float] = {}
        for ranking in lists:
            for position, unit_id in enumerate(ranking, start=1):
                fused[unit_id] = fused.get(unit_id, 0.0) + 1.0 / (RRF_K + position)
        ordered = sorted(fused.items(), key=lambda kv: (-kv[1], kv[0]))
        return [unit_id for unit_id, _ in ordered[:limit]]

    def describe(self) -> dict[str, Any]:
        return {
            "retriever": self.name,
            "fusion": "rrf",
            "k": RRF_K,
            "depth": self._depth,
            "components": ["bm25", "dense"],
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
    return arms
