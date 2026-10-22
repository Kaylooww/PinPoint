"""MinerU integration: server status, background parsing, and block extraction."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from . import search, storage

PARSE_WAIT_SECONDS = 900
MINERU_TIER = os.getenv("MINERU_TIER", "basic")
# Digital documents (a real text layer) don't need OCR or layout models: MinerU's "flash"
# tier reads them in seconds instead of minutes. Scans and photos keep MINERU_TIER (basic).
FAST_TIER = "flash"
TEXT_LAYER_MIN_CHARS = 200  # per page, over the first 3 pages
OFFICE_EXTENSIONS = {"docx", "doc", "xlsx", "xls", "pptx", "ppt", "html", "htm", "odt", "ods", "odp", "rtf"}

log = logging.getLogger("pinpoint.parsing")

# One parse at a time: MinerU's local server does the heavy lifting.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="parse")
# Embedding a large document can take minutes; do it on its own thread so the parse queue
# keeps moving (a ready file is searchable by BM25 right away; vectors fill in behind it).
_embed_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="embed")


class ParseError(Exception):
    pass


def mineru_bin() -> str | None:
    """The mineru CLI, also found when uvicorn's PATH lacks ~/.local/bin."""
    found = shutil.which("mineru")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "mineru"
    return str(fallback) if fallback.exists() else None


def run_mineru(args: list[str], timeout: float) -> subprocess.CompletedProcess[str]:
    binary = mineru_bin()
    if not binary:
        raise ParseError("mineru is not installed or not on PATH")
    try:
        return subprocess.run([binary, *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        raise ParseError(f"mineru {args[0]} timed out after {timeout:.0f}s") from e


def _last_line(proc: subprocess.CompletedProcess[str]) -> str:
    lines = (proc.stderr or proc.stdout).strip().splitlines()
    return lines[-1] if lines else f"exit code {proc.returncode}"


def server_status() -> dict[str, Any]:
    """Output of `mineru server status --json`, or {"ok": False, "error"} if unavailable."""
    try:
        proc = run_mineru(["server", "status", "--json"], timeout=10)
    except ParseError as e:
        return {"ok": False, "error": str(e)}
    if proc.returncode != 0:
        return {"ok": False, "error": _last_line(proc)}
    try:
        status = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "mineru returned non-JSON status"}
    return {"ok": True, "status": status}


def pdf_info(path: str) -> tuple[int, bool]:
    """(page count, has a text layer) for a PDF; (0, False) if it can't be read."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(path)
        pages = len(reader.pages)
        sample = [len((reader.pages[i].extract_text() or "").strip()) for i in range(min(3, pages))]
    except Exception:  # noqa: BLE001 - unreadable here means "let MinerU OCR it"
        return 0, False
    digital = bool(sample) and sum(n > TEXT_LAYER_MIN_CHARS for n in sample) >= (len(sample) + 1) // 2
    return pages, digital


def choose_tier(path: str) -> tuple[str, int]:
    """(MinerU tier, PDF page count or 0): flash for digital PDFs and Office/HTML files,
    the default (basic) for scanned PDFs and images."""
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    if ext == "pdf":
        pages, digital = pdf_info(path)
        return (FAST_TIER if digital else MINERU_TIER), pages
    if ext in OFFICE_EXTENSIONS:
        return FAST_TIER, 0
    return MINERU_TIER, 0


def parse_file(path: str, tier: str = MINERU_TIER) -> dict[str, Any]:
    """Raw `mineru parse --json` output for one file (all pages)."""
    args = ["parse", path, "--tier", tier, "--json", "--wait", str(PARSE_WAIT_SECONDS), "--limit", "50000000"]
    if path.lower().endswith(".pdf"):
        args += ["--pages", "all"]  # MinerU rejects --pages for non-PDF files
    proc = run_mineru(args, timeout=PARSE_WAIT_SECONDS + 60)
    try:
        raw = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ParseError(_last_line(proc) if proc.returncode else "mineru returned non-JSON output") from e
    if "error" in raw:
        raise ParseError(str(raw["error"].get("message") or raw["error"]))
    if proc.returncode != 0:
        raise ParseError(_last_line(proc))
    return raw


# Real `mineru parse --json` output (inspected in backend/samples/*.mineru.json):
#   {"parse": {short_id, tier, status, ...},
#    "content": {short_id, tier, format: "markdown", content: "<!-- page 1 of 2 -->\n\n# Title\n\nPara...",
#                content_ranges, truncated, ...}}
# Each page's markdown is a list of blank-line-separated blocks, and block m (1-based) of
# page n is addressable as doc:{short_id}/tier:{tier}/page:{n}/block:{m}. No bbox is
# included; we read it best-effort from MinerU's own parse store for the crop fallback.
PAGE_MARKER = re.compile(r"<!-- page (\d+) of (\d+) -->")
BLOCK_SPLIT = re.compile(r"\n\s*\n")
TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{3,}")


HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
EMPHASIS = re.compile(r"\*{2,}|_{2,}|`+")


def _clean_text(line: str) -> str:
    """Strip parser artifacts: HTML comments, heading marks, emphasis and asterisk runs."""
    line = HTML_COMMENT.sub("", line)
    line = re.sub(r"^#{1,6}\s+", "", line.strip())
    return re.sub(r"\s{2,}", " ", EMPHASIS.sub("", line)).strip()


def _table_rows(markdown: str) -> list[list[str]] | None:
    """Rows of cells if the block is a markdown table (rule rows dropped), else None."""
    lines = [ln for ln in markdown.splitlines() if ln.strip()]
    if len(lines) < 2 or not all(ln.strip().startswith("|") for ln in lines):
        return None
    rows = [[_clean_text(c) for c in ln.strip().strip("|").split("|")] for ln in lines if not TABLE_RULE.match(ln)]
    return [r for r in rows if any(r)] or None


def _clean_block(markdown: str) -> str:
    lines = []
    for line in HTML_COMMENT.sub("", markdown).splitlines():
        if TABLE_RULE.match(line):
            continue
        if "|" in line:
            line = " · ".join(c for c in (_clean_text(cell) for cell in line.strip().strip("|").split("|")) if c)
        else:
            line = _clean_text(line)
        if line:
            lines.append(line)
    return "\n".join(lines)


def _mineru_bboxes(sha256: str, tier: str) -> dict[tuple[int, int], list[float]]:
    """{(page, block): [x0, y0, x1, y1] normalized 0-1}, or {} if MinerU's store isn't readable."""
    try:
        store = Path.home() / ".mineru" / "doclib" / "parsed" / sha256[:2] / sha256 / tier
        newest = max(store.glob("*.json"), key=lambda p: p.stat().st_mtime)
        middle = json.loads(newest.read_text(encoding="utf-8"))
        return {
            (page["page_idx"] + 1, i + 1): block["bbox"]
            for page in middle["pages"]
            for i, block in enumerate(page["blocks"])
            if isinstance(block.get("bbox"), list) and len(block["bbox"]) == 4
        }
    except (OSError, ValueError, KeyError, TypeError):
        return {}


# Heading breadcrumbs. Levels: a heading at one level clears everything below it.
HEADING_LEVELS = {
    "book": 0, "part": 1, "schedule": 1, "annex": 1, "title": 2, "article": 3,
    "chapter": 4, "rule": 5, "section": 6, "sec.": 6, "§": 6, "clause": 7,
}
HEADING_RE = re.compile(
    r"^(book|part|title|article|chapter|rule|section|sec\.|§|clause|schedule|annex)\s*"
    r"([0-9]+(?:\.[0-9]+)*[a-z]?|[ivxlcdm]+)\b[.:]?\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)
# "1. Scope" or "2.3 Fees": a dot is required, so OCR lines like "6000 L AND W" don't count.
NUMBERED_RE = re.compile(r"^(\d{1,2}\.|\d{1,2}(?:\.\d{1,2}){1,3})\s+([A-Za-z].*)$")
MAX_HEADING_LINE = 100


def _titled(text: str) -> str:
    return text.title() if text.isupper() else text


def heading_of(block: dict[str, Any], next_block: dict[str, Any] | None) -> tuple[int, str] | None:
    """(level, label) if the block starts a heading; Sections also carry their own text."""
    text = block["text"].strip()
    first_line = text.split("\n", 1)[0]
    match = HEADING_RE.match(first_line)
    if match:
        word, number, rest = match.group(1).lower(), match.group(2), match.group(3).strip()
        level = HEADING_LEVELS[word]
        name = {"sec.": "Section", "§": "Section"}.get(word, word.capitalize())
        number = number.upper() if re.fullmatch(r"[ivxlcdm]+", number, re.IGNORECASE) else number
        if level == HEADING_LEVELS["section"] or level == HEADING_LEVELS["clause"]:
            return level, f"{name} {number}"  # "Section 21. The Senate ..." is a section that starts here
        if "\n" in text or len(text) > MAX_HEADING_LINE or re.search(r"\s\d+\s*$", rest):
            return None  # a table of contents ("RULE 63 Declaratory Relief ... 45") or prose that mentions a rule
        title = rest.rstrip(" .0123456789").strip()
        if not title and next_block is not None:
            nxt = next_block["text"].strip()
            if nxt.isupper() and len(nxt) <= 80 and not HEADING_RE.match(nxt) and not any(ch.isdigit() for ch in nxt):
                title = nxt
        return level, f"{name} {number}" + (f" — {_titled(title)}" if title else "")
    numbered = NUMBERED_RE.match(first_line)
    if numbered and "\n" not in text and len(text) <= 60 and not text.endswith("."):
        number = numbered.group(1).rstrip(".")
        return 8 + number.count("."), f"{number} {numbered.group(2)}"
    return None


def add_breadcrumbs(blocks: list[dict[str, Any]]) -> None:
    """Give each block "path" (heading labels above it, outermost first) and "heading_ids"
    (the block ids of those headings), walking the file in reading order."""
    # Table-of-contents pages are mostly bare "RULE 20 …" / "PART V …" lines; their headings
    # must not open a Part or Rule over the real body that follows.
    per_page: dict[int, list[bool]] = {}
    for block in blocks:
        first = block["text"].strip().split("\n", 1)[0]
        bare = bool(HEADING_RE.match(first)) and not re.match(r"^(section|sec\.|§)", first, re.IGNORECASE)
        per_page.setdefault(block["page"], []).append(bare)
    toc_pages = {
        page for page, marks in per_page.items()
        if (sum(marks) >= 4 and sum(marks) >= 0.4 * len(marks)) or (sum(marks) >= 6 and sum(marks) >= 0.2 * len(marks))
    }

    open_headings: dict[int, tuple[str, str]] = {}
    for i, block in enumerate(blocks):
        found = None if block["page"] in toc_pages else heading_of(block, blocks[i + 1] if i + 1 < len(blocks) else None)
        if found:
            level, label = found
            for deeper in [lv for lv in open_headings if lv >= level]:
                del open_headings[deeper]
            open_headings[level] = (label, block["id"])
        levels = sorted(open_headings)
        block["path"] = [open_headings[lv][0] for lv in levels]
        block["heading_ids"] = [open_headings[lv][1] for lv in levels]


def extract_blocks(raw: dict[str, Any], file_id: str, file_name: str) -> tuple[list[dict[str, Any]], int]:
    """Blocks {id, file_id, file_name, page, locator, text, bbox?} and the page count."""
    content = raw.get("content") or {}
    markdown = content.get("content") or ""
    short_id = content.get("short_id") or raw.get("parse", {}).get("short_id")
    tier = content.get("tier") or raw.get("parse", {}).get("tier") or MINERU_TIER
    if not short_id:
        raise ParseError("MinerU output has no document id")
    bboxes = _mineru_bboxes(content.get("sha256", ""), tier)

    parts = PAGE_MARKER.split(markdown)  # [before, page, total, body, page, total, body, ...]
    blocks: list[dict[str, Any]] = []
    pages = 0
    for i in range(1, len(parts) - 2, 3):
        page, total, body = int(parts[i]), int(parts[i + 1]), parts[i + 2]
        pages = max(pages, total, page)
        for m, chunk in enumerate((c for c in BLOCK_SPLIT.split(body) if c.strip()), start=1):
            text = _clean_block(chunk)
            if sum(ch.isalnum() for ch in text) < 3:  # scanner watermarks like "CS"
                continue
            block = {
                "id": f"{file_id}-p{page}-b{m}",
                "file_id": file_id,
                "file_name": file_name,
                "page": page,
                "locator": f"doc:{short_id}/tier:{tier}/page:{page}/block:{m}",
                "text": text,
            }
            if (page, m) in bboxes:
                block["bbox"] = bboxes[(page, m)]
            table = _table_rows(chunk)
            if table:
                block["table"] = table
            blocks.append(block)
    add_breadcrumbs(blocks)
    return blocks, pages


TEXT_EXTENSIONS = {"md", "txt", "csv"}


def text_file_blocks(path: str, file_id: str, file_name: str) -> tuple[list[dict[str, Any]], int]:
    """Plain-text files skip MinerU (it refuses them): one block per paragraph, no page image."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    chunks = [c for c in BLOCK_SPLIT.split(text) if c.strip()] if not file_name.lower().endswith(".csv") else text.splitlines()
    blocks = []
    for m, chunk in enumerate(chunks, start=1):
        cleaned = _clean_block(chunk) if not file_name.lower().endswith(".csv") else chunk.strip()
        if sum(ch.isalnum() for ch in cleaned) >= 3:
            blocks.append(
                {
                    "id": f"{file_id}-p1-b{m}",
                    "file_id": file_id,
                    "file_name": file_name,
                    "page": 1,
                    "locator": f"text:{file_id}/page:1/block:{m}",
                    "text": cleaned,
                }
            )
    add_breadcrumbs(blocks)
    return blocks, 1


def _parse_job(ws: str, file_id: str) -> None:
    record = next((r for r in storage.list_file_records(ws) if r["id"] == file_id), None)
    if record is None:
        return
    started = time.monotonic()
    storage.update_file(ws, file_id, status="parsing", progress_label="Reading pages…", error=None)
    try:
        if record["name"].rsplit(".", 1)[-1].lower() in TEXT_EXTENSIONS:
            tier = "text"
            blocks, pages = text_file_blocks(record["path"], file_id, record["name"])
        else:
            tier, page_count = choose_tier(record["path"])
            # MinerU's CLI doesn't report per-page progress, so show the page count from pypdf.
            label = f"Reading {page_count} pages…" if page_count > 1 else "Reading pages…"
            storage.update_file(ws, file_id, tier=tier, progress_label=label)
            log.info("parsing %s (%s) on MinerU tier %s, %d pages", record["name"], file_id, tier, page_count)
            try:
                raw = parse_file(record["path"], tier)
            except ParseError:
                if tier == MINERU_TIER:
                    raise
                # Fast path failed: fall back to the old behavior (the default tier).
                log.warning("tier %s failed for %s; retrying on %s", tier, record["name"], MINERU_TIER)
                tier = MINERU_TIER
                storage.update_file(ws, file_id, tier=tier)
                raw = parse_file(record["path"], tier)
            (storage.parsed_dir(ws) / f"{file_id}.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            blocks, pages = extract_blocks(raw, file_id, record["name"])
        if not blocks:
            raise ParseError("No readable text found. Try a clearer copy.")
        storage.replace_file_blocks(ws, file_id, blocks)
        search.rebuild(ws)
        seconds = round(time.monotonic() - started, 1)
        storage.update_file(ws, file_id, status="ready", pages=pages, progress_label=None, tier=tier, parse_seconds=seconds)
        log.info("ready: %s on tier %s, %d pages, %d blocks, %.1fs", record["name"], tier, pages, len(blocks), seconds)
        # Vectors for hybrid search, off the parse thread; on failure asks/startup retry.
        _embed_executor.submit(search.index_vectors, ws)
    except Exception as e:  # noqa: BLE001 - any failure marks the file failed, never crashes the worker
        message = str(e) if isinstance(e, ParseError) else f"Couldn't read this file ({type(e).__name__})."
        storage.update_file(ws, file_id, status="failed", progress_label=None, error=message)
    storage.touch_workspace(ws)


def enqueue(ws: str, file_id: str) -> None:
    _executor.submit(_parse_job, ws, file_id)


def resume_interrupted(ws: str) -> None:
    """On startup: anything left mid-parse goes back to queued, then every queued file is parsed."""
    for record in storage.list_file_records(ws):
        if record["status"] == "parsing":
            storage.update_file(ws, record["id"], status="queued", progress_label=None)
            record["status"] = "queued"
        if record["status"] == "queued":
            enqueue(ws, record["id"])
