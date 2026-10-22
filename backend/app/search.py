"""BM25 retrieval over a workspace's blocks, plus LLM query expansion."""

from __future__ import annotations

import math
import re
import threading
from dataclasses import dataclass
from typing import Any

from rank_bm25 import BM25Okapi

from . import llm, storage

STOPWORDS = set(
    """a an and are as at be by for from has have how i in is it its of on or that the this
    to was were what when where which who whom why will with does did do can could should
    would about into than then there their they them our your you we me my"""
    .split()
)
TOKEN_RE = re.compile(r"[\w$€£₱%.,/-]+", re.UNICODE)


def stem(token: str) -> str:
    """Light suffix stripping so "filing", "filed", "files" and "file" all become "fil"."""
    if token[0].isdigit() or len(token) <= 3:
        return token
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3 and not token.endswith("ss"):
            token = token[: -len(suffix)]
            if suffix in ("ing", "ed") and len(token) > 3 and token[-1] == token[-2]:
                token = token[:-1]  # "submitted" -> "submit"
            break
    return token[:-1] if len(token) > 3 and token.endswith("e") else token


def index_text(block: dict[str, Any]) -> str:
    """What search sees: the heading path, then the text ("Article VI — ... > Section 21: ...")."""
    path = block.get("path") or []
    return f"{' > '.join(path)}: {block['text']}" if path else block["text"]


def tokenize(text: str) -> list[str]:
    tokens = []
    for raw in TOKEN_RE.findall(text.lower()):
        token = raw.strip(".,/-")
        if token and token not in STOPWORDS:
            tokens.append(stem(token))
    return tokens


class BM25(BM25Okapi):
    """BM25Okapi with Lucene's always-positive IDF.

    The classic IDF is 0 (or negative) for a term in half or more of the blocks, which
    zeroes out real matches in a small workspace.
    """

    def _calc_idf(self, nd: dict[str, int]) -> None:
        n_docs = self.corpus_size
        for word, freq in nd.items():
            self.idf[word] = math.log(1 + (n_docs - freq + 0.5) / (freq + 0.5))
        self.average_idf = sum(self.idf.values()) / len(self.idf) if self.idf else 0.0


@dataclass
class Index:
    blocks: list[dict[str, Any]]
    bm25: BM25 | None


_indexes: dict[str, Index] = {}
_guard = threading.Lock()


def rebuild(ws: str) -> Index:
    blocks = [b for b in storage.load_blocks(ws) + storage.note_blocks(ws) if b.get("text", "").strip()]
    corpus = [tokenize(index_text(b)) for b in blocks]
    bm25 = BM25(corpus) if corpus and any(corpus) else None
    index = Index(blocks=blocks, bm25=bm25)
    with _guard:
        _indexes[ws] = index
    return index


def get_index(ws: str) -> Index:
    with _guard:
        index = _indexes.get(ws)
    return index if index is not None else rebuild(ws)


def search(ws: str, query: str, k: int = 6, file_ids: set[str] | None = None) -> list[tuple[dict[str, Any], float]]:
    """Top-k blocks with a positive BM25 score, best first; only from `file_ids` if given."""
    index = get_index(ws)
    terms = tokenize(query)
    if index.bm25 is None or not terms:
        return []
    scores = index.bm25.get_scores(terms)
    pairs = [(b, s) for b, s in zip(index.blocks, scores) if file_ids is None or b["file_id"] in file_ids]
    ranked = sorted(pairs, key=lambda pair: pair[1], reverse=True)
    return [(block, float(score)) for block, score in ranked[:k] if score > 0]


EXPANSION_SYSTEM = (
    "You help search a law/business firm's documents with keyword search. "
    "Given a question, return 5-10 short keywords and synonyms likely to appear in the "
    "documents that answer it (names, dates, legal and business terms, alternative wordings). "
    "If the question asks when something happened or a date (when, what date, sent, signed, "
    "issued, dated, due), also include date words: date, dated, issued, the month names, and "
    "the year if one is implied. "
    'Respond as {"keywords": ["..."]}.'
)


def expand_query(question: str, context: list[tuple[str, str]] | None = None) -> list[str]:
    """Keywords and synonyms from the LLM. Raises llm.LLMError if the LLM is unavailable.

    `context` (earlier questions and answers in the thread) is used only here, to resolve
    references like "that case"; it is never a source for answers.
    """
    user = question
    if context:
        earlier = "\n".join(f"Q: {q}\nA: {a}" for q, a in context)
        user = (
            f"Earlier in this conversation:\n{earlier}\n\nNew question: {question}\n"
            "Resolve references in the new question (like \"it\" or \"that case\") and include the resolved names as keywords."
        )
    reply = llm.chat_json(EXPANSION_SYSTEM, user, max_tokens=400)  # room for the model's reasoning tokens
    keywords = reply.get("keywords", [])
    if not isinstance(keywords, list):
        return []
    return [str(k).strip() for k in keywords if str(k).strip()][:10]


# Hybrid retrieval: BM25 + embedding cosine, fused with reciprocal rank fusion.

RRF_K = 60
CANDIDATES = 30
# Qwen3-Embedding is trained with an instruction on queries (never on documents).
QUERY_INSTRUCTION = "Instruct: Given a question about a client's documents, retrieve passages that answer it\nQuery: "


def index_vectors(ws: str) -> None:
    """Embed any blocks and notes without a cached vector. Never raises."""
    from . import embeddings

    if llm.embeddings_enabled():
        embeddings.ensure(ws, get_index(ws).blocks)


def hybrid(
    ws: str, question: str, expansions: list[str], k: int = 6, file_ids: set[str] | None = None
) -> list[tuple[dict[str, Any], float]]:
    """Top-k blocks by RRF over BM25 (question + expansions) and cosine similarity to the question.

    Falls back to BM25 alone, silently, if embeddings are off or fail, or vectors are missing.
    """
    from . import embeddings

    lexical = search(ws, " ".join([question, *expansions]), k=CANDIDATES, file_ids=file_ids)
    if not llm.embeddings_enabled():
        return lexical[:k]
    index = get_index(ws)
    try:
        query = embeddings.normalize(llm.embed([QUERY_INSTRUCTION + question])[0])
    except llm.LLMError:
        return lexical[:k]
    vectors = embeddings.ensure(ws, index.blocks, max_new=32)  # retry a few missing ones per ask
    scored = []
    for block in index.blocks:
        if file_ids is not None and block["file_id"] not in file_ids:
            continue
        vector = vectors.get(embeddings.text_hash(block["text"]))
        if vector is not None:
            scored.append((block, sum(a * b for a, b in zip(query, vector))))
    if not scored:
        return lexical[:k]
    dense = sorted(scored, key=lambda pair: pair[1], reverse=True)[:CANDIDATES]

    fused: dict[str, float] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for ranking in (lexical, dense):
        for rank, (block, _) in enumerate(ranking, start=1):
            fused[block["id"]] = fused.get(block["id"], 0.0) + 1.0 / (RRF_K + rank)
            by_id[block["id"]] = block
    top = sorted(fused.items(), key=lambda pair: pair[1], reverse=True)[:k]
    return [(by_id[block_id], score) for block_id, score in top]
