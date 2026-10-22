"""MinerU integration: server status, background parsing, and block extraction."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from . import search, storage

PARSE_WAIT_SECONDS = 900
MINERU_TIER = os.getenv("MINERU_TIER", "basic")

# One parse at a time: MinerU's local server does the heavy lifting.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="parse")


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


def parse_file(path: str) -> dict[str, Any]:
    """Raw `mineru parse --json` output for one file (all pages)."""
    args = ["parse", path, "--tier", MINERU_TIER, "--json", "--wait", str(PARSE_WAIT_SECONDS), "--limit", "50000000"]
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


def _clean_block(markdown: str) -> str:
    lines = []
    for line in markdown.splitlines():
        if TABLE_RULE.match(line):
            continue
        line = re.sub(r"^#{1,6}\s+", "", line.strip())
        if "|" in line:
            line = " · ".join(cell.strip() for cell in line.strip("|").split("|") if cell.strip())
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
            blocks.append(block)
    return blocks, pages


def _parse_job(ws: str, file_id: str) -> None:
    record = next((r for r in storage.list_file_records(ws) if r["id"] == file_id), None)
    if record is None:
        return
    storage.update_file(ws, file_id, status="parsing", progress_label="Reading pages…", error=None)
    try:
        raw = parse_file(record["path"])
        (storage.parsed_dir(ws) / f"{file_id}.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        blocks, pages = extract_blocks(raw, file_id, record["name"])
        if not blocks:
            raise ParseError("No readable text found. Try a clearer copy.")
        storage.replace_file_blocks(ws, file_id, blocks)
        search.rebuild(ws)
        storage.update_file(ws, file_id, status="ready", pages=pages, progress_label=None)
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
