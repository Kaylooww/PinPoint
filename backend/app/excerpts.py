"""The short supporting passage shown for each citation.

The excerpt is always text that is literally in the block. An LLM-proposed span is used
only if it is a verbatim substring of the block (whitespace and case normalized); the
excerpt is then cut from the block itself, never from the LLM's copy. Otherwise, the 1-3
lines or sentences with the most query-term overlap are used.
"""

from __future__ import annotations

import re

from . import search

MAX_EXCERPT_CHARS = 500
MIN_QUOTE_CHARS = 12
SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+(?=[A-Z0-9(\"'])")


def verbatim_span(text: str, quote: str) -> str | None:
    """The block's own text matching `quote` word for word (whitespace and case ignored), or None."""
    words = quote.split()
    if len(" ".join(words)) < MIN_QUOTE_CHARS:
        return None
    pattern = r"\s+".join(re.escape(w) for w in words)
    match = re.search(pattern, text, re.IGNORECASE)
    return text[match.start() : match.end()] if match else None


def segments(text: str) -> list[str]:
    """Lines, split further into sentences, in document order."""
    out = []
    for line in text.splitlines():
        out.extend(s.strip() for s in SENTENCE_SPLIT.split(line) if s.strip())
    return out


def best_lines(text: str, query: str, limit: int = 3) -> str:
    """The 1-`limit` segments with the most query-term overlap, in document order."""
    parts = segments(text)
    if not parts:
        return ""
    terms = set(search.tokenize(query))
    scores = [len(terms & set(search.tokenize(p))) for p in parts]
    best = max(scores)
    if best == 0:
        return _cap(parts[0])
    ranked = sorted(range(len(parts)), key=lambda i: scores[i], reverse=True)
    keep = sorted(i for i in ranked[:limit] if scores[i] >= max(1, best / 2))
    return _cap("\n".join(parts[i] for i in keep))


def excerpt(text: str, query: str, quote: str | None = None) -> str:
    if quote:
        span = verbatim_span(text, quote)
        if span:
            return _cap(span)
    return best_lines(text, query)


def _cap(text: str) -> str:
    return text if len(text) <= MAX_EXCERPT_CHARS else text[: MAX_EXCERPT_CHARS - 1].rsplit(" ", 1)[0] + "…"
