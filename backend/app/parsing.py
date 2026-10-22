"""MinerU integration. The parser itself comes later, after inspecting real output."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def mineru_bin() -> str | None:
    """The mineru CLI, also found when uvicorn's PATH lacks ~/.local/bin."""
    found = shutil.which("mineru")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "mineru"
    return str(fallback) if fallback.exists() else None


def server_status() -> dict[str, Any]:
    """Output of `mineru server status --json`, or {"ok": False, "error"} if unavailable."""
    binary = mineru_bin()
    if not binary:
        return {"ok": False, "error": "mineru is not installed or not on PATH"}
    try:
        proc = subprocess.run(
            [binary, "server", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "mineru server status timed out"}
    if proc.returncode != 0:
        message = (proc.stderr or proc.stdout).strip().splitlines()
        return {"ok": False, "error": message[-1] if message else f"exit code {proc.returncode}"}
    try:
        status = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "mineru returned non-JSON status"}
    return {"ok": True, "status": status}
