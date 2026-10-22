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
MAX_CONTEXT_BLOCKS = 12
BLOCK_POSITION = re.compile(r"-p(\d+)-b(\d+)$")
MAX_BLOCK_CHARS = 1200
# The model reasons before answering and those tokens count toward max_tokens: about 450 of a
# 500 budget went to reasoning, which cut the JSON off mid-quote. Leave room for both.
ANSWER_MAX_TOKENS = 2000  # structured answers (lists) are longer; reasoning shares this budget
EXTRACTIVE_LABEL = "Showing matching passages."

ANSWER_SYSTEM = """You answer questions using ONLY the numbered passages from the user's documents.
Rules:
- Every sentence in "answer" must list in "sources" the passage ids (b1, b2, ...) that directly support it.
- Use only facts stated in the passages. No outside knowledge, no guesses.
- Do not calculate totals or do arithmetic; quote the figures that appear instead.
- If the passages do not contain the answer, set "status" to "not_found", leave "answer" empty, and give a one-sentence "reason".
- Be brief and easy to scan. Format "answer" as a list of items, each with a "kind":
  - Start with a one-sentence direct answer ("paragraph").
  - When the answer names 3 or more things (types of bills, requirements, parties, fees), the first paragraph says what they are in general, then give one "bullet" item per thing. Do not pack the list into one sentence.
  - Use "numbered" items for steps, procedures, or anything in order (deadlines by date, filing steps).
  - Use at most one or two "heading" items (a label of up to 6 words, "sources" may be empty), only for answers with distinct groups.
  - One fact per item, short sentences, plain language, no markdown symbols in the text (no **, #, or -).
  - A simple question with one fact is a single "paragraph". Don't force lists.
- In "quotes", for each passage you cite, copy the shortest span of that passage that supports the answer, exactly as written (same words, spelling, and typos; do not fix, reword, or shorten inside the span).
- If the status is "not_found" but a passage covers something close to what was asked (for example the same kind of document with a different date, number, or name), add "suggestion": {"text": "Did you mean ...?", "question": "the question asked again about what the passage actually contains", "sources": ["b2"]}. "text" is one short question that names the close match and does not contain the answer. Use only dates, numbers, and names exactly as they appear in those passages. Never answer the original question from a mismatched passage; the status stays "not_found".
Respond as {"status": "answered" | "not_found", "answer": [{"kind": "paragraph" | "bullet" | "numbered" | "heading", "text": "...", "sources": ["b1"]}], "quotes": {"b1": "exact words from b1"}, "reason": "...", "suggestion": {"text": "...", "question": "...", "sources": ["b2"]}}"""

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


def expand_context(
    blocks: list[dict[str, Any]], hits: list[dict[str, Any]], cap: int = MAX_CONTEXT_BLOCKS
) -> list[dict[str, Any]]:
    """Retrieved blocks plus their neighbours (same page, ±1) and the first 3 blocks of each
    file's page 1 (letterhead, date, addressee), deduplicated, in document order per file,
    at most `cap`. Short blocks like a date line rarely match the question's words, so this
    is how they reach the LLM. Block boundaries, locators, and crops are unchanged.
    """
    position: dict[str, tuple[str, int, int]] = {}
    by_position: dict[tuple[str, int, int], dict[str, Any]] = {}
    for block in blocks:
        match = BLOCK_POSITION.search(block["id"])
        if block.get("kind", "file") == "file" and match:
            key = (block["file_id"], int(match.group(1)), int(match.group(2)))
            position[block["id"]] = key
            by_position[key] = block

    chosen: dict[str, dict[str, Any]] = {}

    def add(block: dict[str, Any] | None) -> None:
        if block is not None and len(chosen) < cap:
            chosen.setdefault(block["id"], block)

    # 1. Retrieved blocks: never dropped by the cap.
    for hit in hits:
        add(hit)
    # 2. Each retrieved file's page-1 header (first 3 blocks), round-robin across files so
    #    every file's date and addressee lines get in before any one file's neighbours.
    files = list(dict.fromkeys(position[h["id"]][0] for h in hits if h["id"] in position))
    headers = {f: sorted(m for (fid, p, m) in by_position if fid == f and p == 1)[:3] for f in files}
    for i in range(3):
        for f in files:
            if i < len(headers[f]):
                add(by_position[(f, 1, headers[f][i])])
    # 3. Neighbours on the same page (±1), in retrieval order, while there is room.
    for hit in hits:
        if hit["id"] in position:
            file_id, page, m = position[hit["id"]]
            add(by_position.get((file_id, page, m - 1)))
            add(by_position.get((file_id, page, m + 1)))

    file_order = list(dict.fromkeys(b["file_id"] for b in chosen.values()))
    return sorted(
        chosen.values(),
        key=lambda b: (file_order.index(b["file_id"]), position.get(b["id"], ("", 0, 0))[1:]),
    )


def _not_found(
    reason: str,
    searched_files: int,
    started: float,
    near_matches: list[dict[str, Any]] | None = None,
    suggestion: dict[str, str] | None = None,
) -> dict[str, Any]:
    response = _response("not_found", [], [], searched_files, started, reason)
    response["near_matches"] = near_matches or []
    if suggestion:
        response["suggestion"] = suggestion
    return response


MONTHS = (
    "january february march april may june july august september october november december "
    "jan feb mar apr jun jul aug sep sept oct nov dec"
).split()
FACT_TOKEN = re.compile(r"\d[\d,./:-]*\d|\d|[A-Za-z]+")


def suggestion_facts(text: str) -> list[str]:
    """Dates, numbers, amounts, and month names in a suggestion; each must be in the blocks."""
    facts = []
    for token in FACT_TOKEN.findall(text):
        low = token.lower()
        if any(ch.isdigit() for ch in token) or low in MONTHS:
            facts.append(low.rstrip(".,"))
    return facts


def validate_suggestion(raw: Any, blocks: list[dict[str, Any]]) -> dict[str, str] | None:
    """{text, question} if every date, number, amount, and month in it appears verbatim in
    one of `blocks` (case and whitespace ignored); otherwise None."""
    if not isinstance(raw, dict):
        return None
    text, question = str(raw.get("text", "")).strip(), str(raw.get("question", "")).strip()
    if not text or not question or len(text) > 300 or len(question) > 300 or not blocks:
        return None
    # One short question that doesn't carry the answer: "Did you mean X? Its total is Y." is out.
    if not text.endswith("?") or re.search(r"[.!?]\s+\S", text):
        return None
    haystack = " ".join(" ".join(b["text"].split()).lower() for b in blocks)
    compact = haystack.replace(" ", "")
    for fact in suggestion_facts(f"{text} {question}"):
        if fact not in haystack and fact.replace(" ", "") not in compact:
            return None
    return {"text": text, "question": question}


MAX_CITATION_CHARS = 4000
ITEM_KINDS = ("paragraph", "bullet", "numbered", "heading")
MAX_HEADING_WORDS = 8
LEADING_MARKER = re.compile(r"^\s*(?:#{1,6}\s+|[-*+•]\s+|\d{1,3}[.)]\s+)")
INLINE_MARKUP = re.compile(r"\*\*|__|`|(?<!\w)\*(?=\S)|(?<=\S)\*(?!\w)")


def clean_item_text(text: str) -> str:
    """Strip stray markdown the model may add (list markers, #, **, backticks)."""
    text = LEADING_MARKER.sub("", text.strip())
    return re.sub(r"\s{2,}", " ", INLINE_MARKUP.sub("", text)).strip()


def _citation(ws: str, block: dict[str, Any], n: int, query: str, quote: str | None = None) -> dict[str, Any]:
    full = block["text"] if len(block["text"]) <= MAX_CITATION_CHARS else block["text"][:MAX_CITATION_CHARS] + "…"
    citation = {
        "id": f"c{n}",
        "number": n,
        "kind": block.get("kind", "file"),
        "file_id": block["file_id"],
        "file_name": block["file_name"],
        "page": block["page"],
        "locator": block["locator"],
        "text": full,
        "excerpt": excerpts.excerpt(block["text"], query, quote),
        "crop_url": crops.crop_url(ws, block) if block.get("kind", "file") == "file" else None,
    }
    if block.get("table"):
        citation["table"] = block["table"]
    return citation


NEAR_MATCHES = 3


def _near_matches(
    ws: str, question: str, retrieved: list[dict[str, Any]], context: list[dict[str, Any]], raw: Any, by_id: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, str] | None]:
    """Up to 3 close passages for a not_found answer, plus the LLM's suggestion if it checks out.

    The suggestion's own sources (and context blocks holding its facts) come first, then the
    retrieved blocks in rank order. The suggestion is validated against the near matches.
    """
    def flat(block: dict[str, Any]) -> str:
        return " ".join(block["text"].split()).lower()

    # Candidates: every block of the files retrieval found (a title line with an invoice
    # number can fall outside the 12-block context). Facts are still checked verbatim.
    hit_files = {b["file_id"] for b in retrieved}
    files_only = [b for b in search.get_index(ws).blocks if b.get("kind", "file") == "file" and b["file_id"] in hit_files] or [
        b for b in context if b.get("kind", "file") == "file"
    ]
    chosen: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        # 1. Cover the suggestion's facts (dates, numbers, months) with as few blocks as possible.
        facts = set(suggestion_facts(f"{raw.get('text', '')} {raw.get('question', '')}"))
        named = {by_id[str(x).strip()]["id"] for x in (raw.get("sources") or []) if str(x).strip() in by_id}
        rank = {b["id"]: i for i, b in enumerate(retrieved)}
        while len(chosen) < NEAR_MATCHES:
            covered = " ".join(flat(b) for b in chosen.values())
            missing = {f for f in facts if f not in covered}
            # Most uncovered facts first; ties go to passages the LLM named, then retrieval rank.
            best = max(
                (b for b in files_only if b["id"] not in chosen),
                key=lambda b: (sum(f in flat(b) for f in missing), b["id"] in named, -rank.get(b["id"], len(rank))),
                default=None,
            )
            if not missing or best is None or not any(f in flat(best) for f in missing):
                break
            chosen[best["id"]] = best
        # 2. Then the passages the LLM named.
        sources = raw.get("sources") if isinstance(raw.get("sources"), list) else []
        for b in (by_id[s] for s in (str(x).strip() for x in sources) if s in by_id):
            if len(chosen) < NEAR_MATCHES and b.get("kind", "file") == "file":
                chosen.setdefault(b["id"], b)
    # 3. Then the retrieved blocks in rank order.
    for b in retrieved:
        if len(chosen) < NEAR_MATCHES and b.get("kind", "file") == "file":
            chosen.setdefault(b["id"], b)
    blocks = list(chosen.values())
    suggestion = validate_suggestion(raw, blocks)
    query = " ".join([question, suggestion["question"] if suggestion else ""])
    return [_citation(ws, b, n, query) for n, b in enumerate(blocks, start=1)], suggestion


def _cite(
    ws: str,
    sentences: list[tuple[str, list[dict[str, Any]], str]],
    question: str,
    quotes: dict[str, str] | None = None,
) -> tuple[list, list]:
    """Number cited blocks by first appearance; return (answer, citations) in the API shape.

    `sentences` are (text, blocks, kind). `quotes` maps block id -> the LLM's proposed
    supporting span, used only if verbatim.
    """
    numbers: dict[str, int] = {}
    citations: list[dict[str, Any]] = []
    answer: list[dict[str, Any]] = []
    support: dict[str, list[str]] = {}
    for text, blocks, _ in sentences:
        for block in blocks:
            support.setdefault(block["id"], []).append(text)
    for text, blocks, kind in sentences:
        ids = []
        for block in blocks:
            if block["id"] not in numbers:
                n = len(numbers) + 1
                numbers[block["id"]] = n
                query = " ".join([question, *support[block["id"]]])
                citations.append(_citation(ws, block, n, query, (quotes or {}).get(block["id"])))
            cid = f"c{numbers[block['id']]}"
            if cid not in ids:
                ids.append(cid)
        answer.append({"kind": kind, "text": text, "sources": ids})
    return answer, citations


def _extractive(
    ws: str, question: str, searched_files: int, started: float, file_ids: set[str] | None = None
) -> dict[str, Any]:
    hits = search.search(ws, question, k=3, file_ids=file_ids)
    if not hits:
        return _not_found("No passages in these files match the question.", searched_files, started)
    best = hits[0][1]
    hits = [(b, s) for b, s in hits if s >= best * 0.25]
    answer, citations = _cite(ws, [(_snippet(b["text"], 320), [b], "paragraph") for b, _ in hits], question)
    return _response("answered", answer, citations, searched_files, started, EXTRACTIVE_LABEL)


def validate_items(reply: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]], str]]:
    """Validation in code: (text, blocks, kind) for items whose sources are passages we sent.

    Every non-heading item must cite at least one valid passage, or it's dropped. Headings
    may have no sources but are not claims: they are kept only before a factual item, and
    an answer of headings alone is no answer. Long "headings" are demoted to paragraphs.
    """
    raw_answer = reply.get("answer") if reply.get("status") == "answered" else []
    items: list[tuple[str, list[dict[str, Any]], str]] = []
    for item in raw_answer if isinstance(raw_answer, list) else []:
        if not isinstance(item, dict):
            continue
        text = clean_item_text(str(item.get("text", "")))
        kind = item.get("kind") if item.get("kind") in ITEM_KINDS else "paragraph"
        if kind == "heading" and len(text.split()) > MAX_HEADING_WORDS:
            kind = "paragraph"
        sources = item.get("sources") if isinstance(item.get("sources"), list) else []
        blocks = [by_id[s] for s in dict.fromkeys(str(s).strip() for s in sources) if s in by_id]
        if text and (blocks or kind == "heading"):
            items.append((text, blocks, kind))
    # Drop headings with nothing factual after them (before the next heading or at the end).
    kept: list[tuple[str, list[dict[str, Any]], str]] = []
    for i, item in enumerate(items):
        if item[2] == "heading" and not any(k != "heading" for _, _, k in items[i + 1 : next((j for j in range(i + 1, len(items)) if items[j][2] == "heading"), len(items))]):
            continue
        kept.append(item)
    return kept if any(k != "heading" for _, _, k in kept) else []


def _generate(
    ws: str,
    question: str,
    searched_files: int,
    started: float,
    context: list[tuple[str, str]],
    file_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Raises llm.LLMError (except bad JSON, which becomes not_found) so the caller can fall back."""
    try:
        expansions = search.expand_query(question, context)
    except llm.LLMBadJSON:
        expansions = []
    hits = search.hybrid(ws, question, expansions, k=TOP_K, file_ids=file_ids)
    if not hits:
        return _not_found("No passages in these files match the question.", searched_files, started)

    pool = [b for b in search.get_index(ws).blocks if file_ids is None or b["file_id"] in file_ids]
    context = expand_context(pool, [block for block, _ in hits])
    by_id = {f"b{i}": block for i, block in enumerate(context, start=1)}
    passages = "\n\n".join(
        f"[{bid}] ({_source_label(block)})\n{_snippet(block['text'], MAX_BLOCK_CHARS)}"
        for bid, block in by_id.items()
    )
    try:
        reply = llm.chat_json(ANSWER_SYSTEM, f"Question: {question}\n\nPassages:\n{passages}", max_tokens=ANSWER_MAX_TOKENS)
    except llm.LLMBadJSON:
        return {**_not_found("The answer could not be checked against the files.", searched_files, started), "_nocache": True}

    sentences = validate_items(reply, by_id)
    if not sentences:
        reason = str(reply.get("reason") or "").strip() or "These files don't contain the answer."
        near, suggestion = _near_matches(ws, question, [b for b, _ in hits], context, reply.get("suggestion"), by_id)
        return _not_found(reason, searched_files, started, near, suggestion)
    raw_quotes = reply.get("quotes") if isinstance(reply.get("quotes"), dict) else {}
    quotes = {by_id[k]["id"]: v for k, v in raw_quotes.items() if k in by_id and isinstance(v, str)}
    answer, citations = _cite(ws, sentences, question, quotes)
    return _response("answered", answer, citations, searched_files, started)


def _answer(
    ws: str, question: str, context: list[tuple[str, str]], only: list[str] | None = None
) -> dict[str, Any]:
    started = time.perf_counter()
    file_ids = _ready_file_ids(ws)
    restrict = set(only) & set(file_ids) if only else None  # "Ask about this document"
    if only:
        file_ids = tuple(sorted(restrict))
    searched_files = len(file_ids)
    note_ids = () if only else tuple(sorted(n["id"] for n in storage.list_notes(ws)))
    if not file_ids and not note_ids:
        return _not_found("No files in this workspace are ready yet." if not only else "This document isn't ready yet.", 0, started)

    # Follow-ups depend on the thread, so only stand-alone questions are cached.
    key = (ws, _normalize(question), file_ids + note_ids + (("only",) if only else ()))
    if not context:
        with _cache_guard:
            cached = _cache.get(key)
        if cached is not None:
            return {**cached, "elapsed_ms": round((time.perf_counter() - started) * 1000)}

    cacheable = not context
    if llm.config().provider == "none":
        response = _extractive(ws, question, searched_files, started, restrict)
    else:
        try:
            response = _generate(ws, question, searched_files, started, context, restrict)
        except llm.LLMError:
            # LLM down, misconfigured, or timed out: answer from passages, and retry the LLM next time.
            response = _extractive(ws, question, searched_files, started, restrict)
            cacheable = False

    if response.pop("_nocache", False):
        cacheable = False  # a garbled LLM reply shouldn't stick; try again next time
    if cacheable:
        with _cache_guard:
            _cache[key] = response
    return response


def ask(ws: str, question: str, thread_id: str | None = None, file_ids: list[str] | None = None) -> dict[str, Any]:
    """AskResponse plus {thread_id, history_id}; every ask is stored in history."""
    known = thread_id and any(r["thread_id"] == thread_id for r in storage.list_history_records(ws))
    thread_id = thread_id if known else uuid.uuid4().hex[:12]
    context = storage.thread_context(ws, thread_id) if known else []
    response = _answer(ws, question, context, file_ids)
    record = storage.add_history(ws, question, response, thread_id)
    return {**response, "thread_id": thread_id, "history_id": record["id"]}
