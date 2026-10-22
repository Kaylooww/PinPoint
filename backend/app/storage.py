"""Workspaces, files, and blocks on disk under backend/data/{ws}/ (see docs/ARCHITECTURE.md).

All writes are atomic (temp file + rename) and serialized per workspace, so the
background parser and request handlers can share the same JSON files.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# PINPOINT_DATA_DIR lets tests run against a throwaway copy.
DATA_DIR = Path(os.getenv("PINPOINT_DATA_DIR") or Path(__file__).resolve().parent.parent / "data")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

DEMO_WORKSPACE = {"id": "reyes-partners", "name": "Reyes & Partners", "industry": "Law office"}

EXTENSION_TYPES = {
    "pdf": "pdf",
    **dict.fromkeys(["png", "jpg", "jpeg", "webp", "gif", "bmp", "tif", "tiff", "heic"], "image"),
    **dict.fromkeys(["doc", "docx", "rtf", "txt", "md", "odt"], "doc"),
    **dict.fromkeys(["xls", "xlsx", "csv", "ods"], "sheet"),
    **dict.fromkeys(["ppt", "pptx", "odp"], "slides"),
}

_locks: dict[str, threading.RLock] = {}
_locks_guard = threading.Lock()


class NotFound(Exception):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def lock(ws: str) -> threading.RLock:
    with _locks_guard:
        return _locks.setdefault(ws, threading.RLock())


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def ws_dir(ws: str) -> Path:
    if not ID_RE.match(ws):
        raise NotFound(ws)
    return DATA_DIR / ws


def uploads_dir(ws: str) -> Path:
    return ws_dir(ws) / "uploads"


def parsed_dir(ws: str) -> Path:
    return ws_dir(ws) / "parsed"


def crops_dir(ws: str) -> Path:
    return ws_dir(ws) / "crops"


# Workspaces


def workspace_ids() -> list[str]:
    if not DATA_DIR.exists():
        return []
    return sorted(p.parent.name for p in DATA_DIR.glob("*/workspace.json"))


def _workspace_record(ws: str) -> dict[str, Any]:
    record = _read_json(ws_dir(ws) / "workspace.json", None)
    if record is None:
        raise NotFound(ws)
    return record


def workspace_view(ws: str) -> dict[str, Any]:
    """Workspace in the API shape: {id, name, industry, file_count, updated_at}."""
    record = _workspace_record(ws)
    files = list_files(ws)
    return {
        "id": record["id"],
        "name": record["name"],
        "industry": record["industry"],
        "file_count": len(files),
        "updated_at": record.get("updated_at") or record.get("created_at") or now_iso(),
    }


def list_workspaces() -> list[dict[str, Any]]:
    views = [workspace_view(ws) for ws in workspace_ids()]
    return sorted(views, key=lambda w: w["updated_at"], reverse=True)


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "workspace"
    slug, n = base, 2
    while (DATA_DIR / slug).exists():
        slug, n = f"{base}-{n}", n + 1
    return slug


def create_workspace(name: str, industry: str, ws_id: str | None = None) -> dict[str, Any]:
    ws = ws_id or _slugify(name)
    with lock(ws):
        stamp = now_iso()
        _write_json(
            ws_dir(ws) / "workspace.json",
            {"id": ws, "name": name, "industry": industry, "created_at": stamp, "updated_at": stamp},
        )
        for sub in (uploads_dir(ws), parsed_dir(ws), crops_dir(ws)):
            sub.mkdir(parents=True, exist_ok=True)
    return workspace_view(ws)


def touch_workspace(ws: str) -> None:
    with lock(ws):
        record = _workspace_record(ws)
        record["updated_at"] = now_iso()
        _write_json(ws_dir(ws) / "workspace.json", record)


def seed_demo_workspace() -> None:
    if not (DATA_DIR / DEMO_WORKSPACE["id"] / "workspace.json").exists():
        create_workspace(DEMO_WORKSPACE["name"], DEMO_WORKSPACE["industry"], DEMO_WORKSPACE["id"])


# Files (files.json holds internal records; file_view() is the API shape)


def file_type(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return EXTENSION_TYPES.get(ext, "other")


def list_file_records(ws: str) -> list[dict[str, Any]]:
    return _read_json(ws_dir(ws) / "files.json", [])


def save_file_records(ws: str, records: list[dict[str, Any]]) -> None:
    with lock(ws):
        _write_json(ws_dir(ws) / "files.json", records)


def file_view(record: dict[str, Any]) -> dict[str, Any]:
    view = {
        "id": record["id"],
        "name": record["name"],
        "type": record["type"],
        "pages": record.get("pages", 0),
        "size_bytes": record["size_bytes"],
        "status": record["status"],
        "source": record.get("source", "upload"),
    }
    for optional in ("progress_label", "error", "source_path"):
        if record.get(optional):
            view[optional] = record[optional]
    return view


def list_files(ws: str) -> list[dict[str, Any]]:
    return [file_view(r) for r in reversed(list_file_records(ws))]


def add_upload(ws: str, filename: str, data: bytes) -> dict[str, Any]:
    """Save an uploaded file and register it as queued. Returns the internal record."""
    file_id = uuid.uuid4().hex[:12]
    safe_name = Path(filename).name or "file"
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else ""
    path = uploads_dir(ws) / (f"{file_id}.{ext}" if ext else file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    record = {
        "id": file_id,
        "name": safe_name,
        "type": file_type(safe_name),
        "pages": 0,
        "size_bytes": len(data),
        "status": "queued",
        "source": "upload",
        "path": str(path),
        "created_at": now_iso(),
    }
    with lock(ws):
        records = list_file_records(ws)
        records.append(record)
        save_file_records(ws, records)
    touch_workspace(ws)
    return record


def update_file(ws: str, file_id: str, **changes: Any) -> dict[str, Any]:
    with lock(ws):
        records = list_file_records(ws)
        for record in records:
            if record["id"] == file_id:
                for key, value in changes.items():
                    if value is None:
                        record.pop(key, None)
                    else:
                        record[key] = value
                save_file_records(ws, records)
                return record
    raise NotFound(file_id)


# Blocks (one list per workspace; each block belongs to one file)


def load_blocks(ws: str) -> list[dict[str, Any]]:
    return _read_json(ws_dir(ws) / "blocks.json", [])


def replace_file_blocks(ws: str, file_id: str, blocks: list[dict[str, Any]]) -> None:
    with lock(ws):
        kept = [b for b in load_blocks(ws) if b["file_id"] != file_id]
        _write_json(ws_dir(ws) / "blocks.json", kept + blocks)
