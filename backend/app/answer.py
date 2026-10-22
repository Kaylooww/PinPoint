"""The ask pipeline: expand → retrieve → answer → validate citations in code → crops.

Modes (docs/ARCHITECTURE.md, "LLM modes"):
  generate    the LLM expands the query and writes a cited answer
  extractive  no LLM (or it failed): top BM25 passages are the answer, each citing itself
"""

from __future__ import annotations

import re
import threading
import time
from typing import Any

from . import crops, llm, search, storage

TOP_K = 6
MAX_BLOCK_CHARS = 1200
EXTRACTIVE_LABEL = "Showing matching passages."

ANSWER_SYSTEM = """You answer questions using ONLY the numbered passages from the user's documents.
Rules:
- Every sentence in "answer" must list in "sources" the passage ids (b1, b2, ...) that directly support it.
- Use only facts stated in the passages. No outside knowledge, no guesses.
- Do not calculate totals or do arithmetic; quote the figures that appear instead.
- If the passages do not contain the answer, set "status" to "not_found", leave "answer" empty, and give a one-sentence "reason".
- Be brief: 1-3 sentences.
Respond as {"status": "answered" | "not_found", "answer": [{"text": "...", "sources": ["b1"]}], "reason": "..."}"""

_cache: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
_cache_guard = threading.Lock()


def _normalize(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def _ready_file_ids(ws: str) -> tuple[str, ...]:
    return tuple(sorted(r["id"] for r in storage.list_file_records(ws) if r["status"] == "ready"))


def _snippet(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rsplit(" ", 1)[0] + "…"


def _response(
    status: str,
    answer: list[dict[str, Any]],
    citations: list[dict[str, Any]],
    searched_files: int,
    started: float,
    reason: str | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "status": status,
        "answer": answer,
        "citations": citations,
        "searched_files": searched_files,
        "elapsed_ms": round((time.perf_counter() - started) * 1000),
    }
    if reason:
        response["reason"] = reason
    return response


def _not_found(reason: str, searched_files: int, started: float) -> dict[str, Any]:
    return _response("not_found", [], [], searched_files, started, reason)


def _cite(ws: str, sentences: list[tuple[str, list[dict[str, Any]]]]) -> tuple[list, list]:
    """Number cited blocks by first appearance; return (answer, citations) in the API shape."""
    numbers: dict[str, int] = {}
    citations: list[dict[str, Any]] = []
    answer: list[dict[str, Any]] = []
    for text, blocks in sentences:
        ids = []
        for block in blocks:
            if block["id"] not in numbers:
                n = len(numbers) + 1
                numbers[block["id"]] = n
                citations.append(
                    {
                        "id": f"c{n}",
                        "number": n,
                        "kind": "file",
                        "file_id": block["file_id"],
                        "file_name": block["file_name"],
                        "page": block["page"],
                        "locator": block["locator"],
                        "text": _snippet(block["text"], 2000),
                        "crop_url": crops.crop_url(ws, block),
                    }
                )
            cid = f"c{numbers[block['id']]}"
            if cid not in ids:
                ids.append(cid)
        answer.append({"text": text, "sources": ids})
    return answer, citations


def _extractive(ws: str, question: str, searched_files: int, started: float) -> dict[str, Any]:
    hits = search.search(ws, question, k=3)
    if not hits:
        return _not_found("No passages in these files match the question.", searched_files, started)
    best = hits[0][1]
    hits = [(b, s) for b, s in hits if s >= best * 0.25]
    answer, citations = _cite(ws, [(_snippet(b["text"], 320), [b]) for b, _ in hits])
    return _response("answered", answer, citations, searched_files, started, EXTRACTIVE_LABEL)


def _generate(ws: str, question: str, searched_files: int, started: float) -> dict[str, Any]:
    """Raises llm.LLMError (except bad JSON, which becomes not_found) so the caller can fall back."""
    try:
        expansions = search.expand_query(question)
    except llm.LLMBadJSON:
        expansions = []
    hits = search.search(ws, " ".join([question, *expansions]), k=TOP_K)
    if not hits:
        return _not_found("No passages in these files match the question.", searched_files, started)

    by_id = {f"b{i}": block for i, (block, _) in enumerate(hits, start=1)}
    passages = "\n\n".join(
        f"[{bid}] ({block['file_name']}, page {block['page']})\n{_snippet(block['text'], MAX_BLOCK_CHARS)}"
        for bid, block in by_id.items()
    )
    try:
        reply = llm.chat_json(ANSWER_SYSTEM, f"Question: {question}\n\nPassages:\n{passages}", max_tokens=500)
    except llm.LLMBadJSON:
        return _not_found("The answer could not be checked against the files.", searched_files, started)

    # Validation in code: keep only sentences whose sources are passages we actually sent.
    sentences: list[tuple[str, list[dict[str, Any]]]] = []
    raw_answer = reply.get("answer") if reply.get("status") == "answered" else []
    for item in raw_answer if isinstance(raw_answer, list) else []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        sources = item.get("sources") if isinstance(item.get("sources"), list) else []
        blocks = [by_id[s] for s in dict.fromkeys(str(s).strip() for s in sources) if s in by_id]
        if text and blocks:
            sentences.append((text, blocks))

    if not sentences:
        reason = str(reply.get("reason") or "").strip() or "These files don't contain the answer."
        return _not_found(reason, searched_files, started)
    answer, citations = _cite(ws, sentences)
    return _response("answered", answer, citations, searched_files, started)


def ask(ws: str, question: str) -> dict[str, Any]:
    started = time.perf_counter()
    file_ids = _ready_file_ids(ws)
    searched_files = len(file_ids)
    if not file_ids:
        return _not_found("No files in this workspace are ready yet.", 0, started)

    key = (ws, _normalize(question), file_ids)
    with _cache_guard:
        cached = _cache.get(key)
    if cached is not None:
        return {**cached, "elapsed_ms": round((time.perf_counter() - started) * 1000)}

    cacheable = True
    if llm.config().provider == "none":
        response = _extractive(ws, question, searched_files, started)
    else:
        try:
            response = _generate(ws, question, searched_files, started)
        except llm.LLMError:
            # LLM down, misconfigured, or timed out: answer from passages, and retry the LLM next time.
            response = _extractive(ws, question, searched_files, started)
            cacheable = False

    if cacheable:
        with _cache_guard:
            _cache[key] = response
    return response
