"""Grading: exact, deterministic, no LLM judge.

Every task in the corpus has a set-valued oracle, so utility is set F1 after
normalisation. Singletons degrade to exact match, which keeps one scale across all
cells rather than mixing metrics.

The absence of an LLM judge is a design requirement, not a convenience. The effect
under study is a few percentage points; judge noise on that order would be
indistinguishable from the effect, which is precisely what makes small reported gains
in this literature impossible to falsify.
"""

from __future__ import annotations

import re
import unicodedata

_PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACE = re.compile(r"\s+")

# Leading articles and hedges a model may prepend to an otherwise correct item.
_STRIP_PREFIX = re.compile(r"^(the|a|an|el|la|los|las|un|una)\s+", flags=re.IGNORECASE)


def normalise(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = _PUNCT.sub(" ", text)
    text = _SPACE.sub(" ", text).strip().lower()
    return _STRIP_PREFIX.sub("", text)


def split_items(answer: str) -> set[str]:
    """Split a model answer into items.

    The answer contract asks for '; ' separation, but models drift to commas and
    newlines. Accepting all three is tolerance of format, not of content: a wrong
    item still scores zero. Being strict about separators would measure instruction
    following rather than control structure.
    """
    parts = re.split(r"[;\n]|,(?![^(]*\))", answer)
    items = {normalise(p) for p in parts if normalise(p)}
    return {i for i in items if i not in {"none", "nothing", "n a", "na"}}


EMPTY_ANSWERS = {"none", "nothing", "no one", "nobody", "n a", "na", "empty", "0 items"}


def score(answer: str, oracle: list[str]) -> float:
    """Set F1 in [0, 1].

    An EMPTY oracle is a real and important question — "list every X" where no X
    exists — and it tests whether a paradigm invents items that are not there. It used
    to raise, which meant the exception was swallowed upstream and every paradigm
    scored zero on a task that several would have answered correctly.
    """
    # Only items with normalised CONTENT. An oracle of pure punctuation (";;;") used to
    # normalise to {""}, and the empty string is a substring of everything: every
    # single-item answer scored a perfect 1.0 against it. Now it is what it is -- an
    # empty oracle -- and takes the explicit-emptiness path below.
    truth = {n for n in (normalise(o) for o in oracle) if n}
    if not truth:
        stated = split_items(answer)
        explicit = {normalise(a) for a in EMPTY_ANSWERS}
        # Credit only an explicit statement of emptiness. Silence is not an answer:
        # a paradigm that returned nothing because it crashed must not score the same
        # as one that looked and reported finding nothing. `answer.strip()` is required
        # unconditionally — an earlier version short-circuited on the second clause and
        # handed an empty string full credit.
        return 1.0 if answer.strip() and stated <= explicit else 0.0

    predicted = split_items(answer)
    if not predicted:
        return 0.0

    # A singleton oracle is a single-answer question. Requiring the prediction to be
    # that one item stops a paradigm from scoring by listing every candidate it saw,
    # which set F1 alone would partially reward.
    if len(truth) == 1:
        only = next(iter(truth))
        if predicted == {only}:
            return 1.0
        # Substring credit covers 'AR123' inside 'account AR123' without rewarding a
        # scattergun list: it applies only when the model committed to one item, and
        # only in that direction. The reverse test ('candidate in only') handed 1.0
        # to every prefix of the right answer — '4' scored perfect against '42'.
        if len(predicted) == 1:
            candidate = next(iter(predicted))
            return 1.0 if only in candidate else 0.0
        return 0.0

    hits = len(truth & predicted)
    if hits == 0:
        return 0.0
    precision = hits / len(predicted)
    recall = hits / len(truth)
    return 2 * precision * recall / (precision + recall)
