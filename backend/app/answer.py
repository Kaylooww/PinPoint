"""The ask pipeline: expand → retrieve → answer → validate citations in code → crops.

Modes (docs/ARCHITECTURE.md, "LLM modes"):
  generate    the LLM expands the query and writes a cited answer
  extractive  no LLM (or it failed): top BM25 passages are the answer, each citing itself
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from typing import Any

from . import crops, excerpts, llm, search, storage

TOP_K = 6
MAX_BLOCK_CHARS = 1200
# The model reasons before answering and those tokens count toward max_tokens: about 450 of a
# 500 budget went to reasoning, which cut the JSON off mid-quote. Leave room for both.
ANSWER_MAX_TOKENS = 1200
EXTRACTIVE_LABEL = "Showing matching passages."

ANSWER_SYSTEM = """You answer questions using ONLY the numbered passages from the user's documents.
Rules:
- Every sentence in "answer" must list in "sources" the passage ids (b1, b2, ...) that directly support it.
- Use only facts stated in the passages. No outside knowledge, no guesses.
- Do not calculate totals or do arithmetic; quote the figures that appear instead.
- If the passages do not contain the answer, set "status" to "not_found", leave "answer" empty, and give a one-sentence "reason".
- Be brief: 1-3 sentences.
- In "quotes", for each passage you cite, copy the shortest span of that passage that supports the answer, exactly as written (same words, spelling, and typos; do not fix, reword, or shorten inside the span).
Respond as {"status": "answered" | "not_found", "answer": [{"text": "...", "sources": ["b1"]}], "quotes": {"b1": "exact words from b1"}, "reason": "..."}"""

_cache: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
_cache_guard = threading.Lock()


def _source_label(block: dict[str, Any]) -> str:
    if block.get("kind") == "note":
        return "Note saved by the user about this client"
    return f"{block['file_name']}, page {block['page']}"


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


MAX_CITATION_CHARS = 4000


def _cite(
    ws: str,
    sentences: list[tuple[str, list[dict[str, Any]]]],
    question: str,
    quotes: dict[str, str] | None = None,
) -> tuple[list, list]:
    """Number cited blocks by first appearance; return (answer, citations) in the API shape.

    `quotes` maps block id -> the LLM's proposed supporting span, used only if verbatim.
    """
    numbers: dict[str, int] = {}
    citations: list[dict[str, Any]] = []
    answer: list[dict[str, Any]] = []
    support: dict[str, list[str]] = {}
    for text, blocks in sentences:
        for block in blocks:
            support.setdefault(block["id"], []).append(text)
    for text, blocks in sentences:
        ids = []
        for block in blocks:
            if block["id"] not in numbers:
                n = len(numbers) + 1
                numbers[block["id"]] = n
                full = block["text"] if len(block["text"]) <= MAX_CITATION_CHARS else block["text"][:MAX_CITATION_CHARS] + "…"
                query = " ".join([question, *support[block["id"]]])
                citation = {
                    "id": f"c{n}",
                    "number": n,
                    "kind": block.get("kind", "file"),
                    "file_id": block["file_id"],
                    "file_name": block["file_name"],
                    "page": block["page"],
                    "locator": block["locator"],
                    "text": full,
                    "excerpt": excerpts.excerpt(block["text"], query, (quotes or {}).get(block["id"])),
                    "crop_url": crops.crop_url(ws, block) if block.get("kind", "file") == "file" else None,
                }
                if block.get("table"):
                    citation["table"] = block["table"]
                citations.append(citation)
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
    answer, citations = _cite(ws, [(_snippet(b["text"], 320), [b]) for b, _ in hits], question)
    return _response("answered", answer, citations, searched_files, started, EXTRACTIVE_LABEL)


def _generate(
    ws: str, question: str, searched_files: int, started: float, context: list[tuple[str, str]]
) -> dict[str, Any]:
    """Raises llm.LLMError (except bad JSON, which becomes not_found) so the caller can fall back."""
    try:
        expansions = search.expand_query(question, context)
    except llm.LLMBadJSON:
        expansions = []
    hits = search.hybrid(ws, question, expansions, k=TOP_K)
    if not hits:
        return _not_found("No passages in these files match the question.", searched_files, started)

    by_id = {f"b{i}": block for i, (block, _) in enumerate(hits, start=1)}
    passages = "\n\n".join(
        f"[{bid}] ({_source_label(block)})\n{_snippet(block['text'], MAX_BLOCK_CHARS)}"
        for bid, block in by_id.items()
    )
    try:
        reply = llm.chat_json(ANSWER_SYSTEM, f"Question: {question}\n\nPassages:\n{passages}", max_tokens=ANSWER_MAX_TOKENS)
    except llm.LLMBadJSON:
        return {**_not_found("The answer could not be checked against the files.", searched_files, started), "_nocache": True}

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
    raw_quotes = reply.get("quotes") if isinstance(reply.get("quotes"), dict) else {}
    quotes = {by_id[k]["id"]: v for k, v in raw_quotes.items() if k in by_id and isinstance(v, str)}
    answer, citations = _cite(ws, sentences, question, quotes)
    return _response("answered", answer, citations, searched_files, started)


def _answer(ws: str, question: str, context: list[tuple[str, str]]) -> dict[str, Any]:
    started = time.perf_counter()
    file_ids = _ready_file_ids(ws)
    searched_files = len(file_ids)
    note_ids = tuple(sorted(n["id"] for n in storage.list_notes(ws)))
    if not file_ids and not note_ids:
        return _not_found("No files in this workspace are ready yet.", 0, started)

    # Follow-ups depend on the thread, so only stand-alone questions are cached.
    key = (ws, _normalize(question), file_ids + note_ids)
    if not context:
        with _cache_guard:
            cached = _cache.get(key)
        if cached is not None:
            return {**cached, "elapsed_ms": round((time.perf_counter() - started) * 1000)}

    cacheable = not context
    if llm.config().provider == "none":
        response = _extractive(ws, question, searched_files, started)
    else:
        try:
            response = _generate(ws, question, searched_files, started, context)
        except llm.LLMError:
            # LLM down, misconfigured, or timed out: answer from passages, and retry the LLM next time.
            response = _extractive(ws, question, searched_files, started)
            cacheable = False

    if response.pop("_nocache", False):
        cacheable = False  # a garbled LLM reply shouldn't stick; try again next time
    if cacheable:
        with _cache_guard:
            _cache[key] = response
    return response


def ask(ws: str, question: str, thread_id: str | None = None) -> dict[str, Any]:
    """AskResponse plus {thread_id, history_id}; every ask is stored in history."""
    known = thread_id and any(r["thread_id"] == thread_id for r in storage.list_history_records(ws))
    thread_id = thread_id if known else uuid.uuid4().hex[:12]
    context = storage.thread_context(ws, thread_id) if known else []
    response = _answer(ws, question, context)
    record = storage.add_history(ws, question, response, thread_id)
    return {**response, "thread_id": thread_id, "history_id": record["id"]}
