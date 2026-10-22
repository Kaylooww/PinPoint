"""MinerU integration: server status, background parsing, and block extraction."""

from __future__ import annotations

import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from . import search, storage

PARSE_WAIT_SECONDS = 900

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
    proc = run_mineru(
        ["parse", path, "--pages", "all", "--json", "--wait", str(PARSE_WAIT_SECONDS)],
        timeout=PARSE_WAIT_SECONDS + 60,
    )
    if proc.returncode != 0:
        raise ParseError(_last_line(proc))
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ParseError("mineru returned non-JSON output") from e


def extract_blocks(raw: dict[str, Any], file_id: str, file_name: str) -> tuple[list[dict[str, Any]], int]:
    """Blocks {id, file_id, file_name, page, locator, text, bbox?} and the page count."""
    raise NotImplementedError("written after inspecting real MinerU output")


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
