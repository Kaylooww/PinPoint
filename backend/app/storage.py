"""Workspaces, files, and blocks on disk under backend/data/{ws}/ (see docs/ARCHITECTURE.md).

All writes are atomic (temp file + rename) and serialized per workspace, so the
background parser and request handlers can share the same JSON files.
"""

from __future__ import annotations

import json
import os
import re
import shutil
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
# Workspaces deleted while a background job (parse, folder scan, embedding) may still write
# to them: those writes are dropped so the folder doesn't come back.
_deleted: set[str] = set()


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


def is_deleted(ws: str) -> bool:
    return ws in _deleted


def _write_json(path: Path, value: Any) -> None:
    resolved = path.resolve()
    if resolved.is_relative_to(DATA_DIR.resolve()) and resolved.relative_to(DATA_DIR.resolve()).parts[0] in _deleted:
        return
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
    _deleted.discard(ws)
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


def delete_workspace(ws: str) -> None:
    """Delete a workspace and everything PinPoint stored for it in backend/data/{ws}: uploads,
    parses, blocks, vectors, crops, notes, history. Connected folders' originals are never touched."""
    with lock(ws):
        _workspace_record(ws)  # NotFound if it doesn't exist
        _deleted.add(ws)
        path = ws_dir(ws)
        if path.resolve().parent == DATA_DIR.resolve():  # never anything outside backend/data
            shutil.rmtree(path, ignore_errors=True)


def seed_demo_workspace() -> None:
    """A fresh install starts with the demo workspace; once deleted, it stays deleted."""
    if not workspace_ids():
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


# Notes: user-written facts, one markdown file per note in notes/, searched and cited like documents.

NOTE_ID_RE = re.compile(r"^[a-f0-9]{12}$")


def notes_dir(ws: str) -> Path:
    return ws_dir(ws) / "notes"


def _read_note(path: Path) -> dict[str, Any] | None:
    raw = path.read_text(encoding="utf-8")
    match = re.match(r"^---\ncreated_at: (.+)\n---\n(.*)$", raw, re.DOTALL)
    if not match:
        return None
    return {"id": path.stem, "text": match.group(2).strip(), "created_at": match.group(1).strip()}


def list_notes(ws: str) -> list[dict[str, Any]]:
    notes = [n for p in notes_dir(ws).glob("*.md") if (n := _read_note(p))]
    return sorted(notes, key=lambda n: n["created_at"], reverse=True)


def add_note(ws: str, text: str) -> dict[str, Any]:
    note = {"id": uuid.uuid4().hex[:12], "text": text.strip(), "created_at": now_iso()}
    path = notes_dir(ws) / f"{note['id']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ncreated_at: {note['created_at']}\n---\n{note['text']}\n", encoding="utf-8")
    touch_workspace(ws)
    return note


def delete_note(ws: str, note_id: str) -> None:
    if not NOTE_ID_RE.match(note_id):
        raise NotFound(note_id)
    path = notes_dir(ws) / f"{note_id}.md"
    if not path.exists():
        raise NotFound(note_id)
    path.unlink()
    touch_workspace(ws)


def note_blocks(ws: str) -> list[dict[str, Any]]:
    """Notes as searchable blocks (kind "note"; no page image, so no crop)."""
    return [
        {
            "id": f"note-{n['id']}",
            "kind": "note",
            "file_id": n["id"],
            "file_name": "Note",
            "page": 1,
            "locator": f"note:{n['id']}",
            "text": n["text"],
        }
        for n in list_notes(ws)
    ]


def remove_file(ws: str, file_id: str) -> None:
    """Forget a file: its record and its blocks. Never touches the user's original on disk."""
    with lock(ws):
        save_file_records(ws, [r for r in list_file_records(ws) if r["id"] != file_id])
        replace_file_blocks(ws, file_id, [])


class CannotDelete(Exception):
    pass


def delete_file(ws: str, file_id: str) -> None:
    """Delete a file the user uploaded: its record, blocks, and our copies inside backend/data
    (upload, saved parse, decrypted copy, crops). A file still queued or being read is
    cancelled first by the caller (parsing.cancel). Folder files are refused: their original
    belongs to the user, and a rescan would bring them back."""
    with lock(ws):
        record = next((r for r in list_file_records(ws) if r["id"] == file_id), None)
        if record is None:
            raise NotFound(file_id)
        if record.get("source") == "folder":
            raise CannotDelete("This file is in a connected folder. Remove it from the folder and rescan, or disconnect the folder.")
        blocks = load_blocks(ws)
        gone = [b for b in blocks if b["file_id"] == file_id]
        remove_file(ws, file_id)
        files = [uploads_dir(ws) / Path(record["path"]).name, *parsed_dir(ws).glob(f"{file_id}.*")]
        files += [crops_dir(ws) / f"{b['id']}.png" for b in gone]
        # Rendered pages are shared by every upload of the same document; keep them while one remains.
        docs = {b["locator"].split("/", 1)[0] for b in gone if b["locator"].startswith("doc:")}
        docs -= {b["locator"].split("/", 1)[0] for b in blocks if b["file_id"] != file_id}
        for doc in docs:
            files += (crops_dir(ws) / "pages").glob(re.sub(r"[^a-z0-9]+", "-", doc.lower()) + "-*.png")
        for path in files:
            if path.resolve().is_relative_to(ws_dir(ws).resolve()):  # never outside backend/data/{ws}
                path.unlink(missing_ok=True)


def add_folder_file(ws: str, folder_id: str, source_path: str, size: int, mtime: float) -> dict[str, Any]:
    name = Path(source_path).name
    record = {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "type": file_type(name),
        "pages": 0,
        "size_bytes": size,
        "status": "queued",
        "source": "folder",
        "source_path": source_path,
        "path": source_path,  # parsed in place, read-only
        "folder_id": folder_id,
        "mtime": mtime,
        "created_at": now_iso(),
    }
    with lock(ws):
        records = list_file_records(ws)
        records.append(record)
        save_file_records(ws, records)
    return record


# Connected folders (folders.json)


def list_folder_records(ws: str) -> list[dict[str, Any]]:
    return _read_json(ws_dir(ws) / "folders.json", [])


def save_folder_records(ws: str, records: list[dict[str, Any]]) -> None:
    with lock(ws):
        _write_json(ws_dir(ws) / "folders.json", records)


def update_folder(ws: str, folder_id: str, **changes: Any) -> dict[str, Any]:
    with lock(ws):
        records = list_folder_records(ws)
        for record in records:
            if record["id"] == folder_id:
                for key, value in changes.items():
                    if value is None:
                        record.pop(key, None)
                    else:
                        record[key] = value
                save_folder_records(ws, records)
                return record
    raise NotFound(folder_id)


def folder_view(ws: str, record: dict[str, Any]) -> dict[str, Any]:
    count = sum(1 for r in list_file_records(ws) if r.get("folder_id") == record["id"])
    view = {
        "id": record["id"],
        "path": record["path"],
        "file_count": count,
        "status": record["status"],
        "last_scanned_at": record.get("last_scanned_at"),
    }
    if record.get("error"):
        view["error"] = record["error"]
    return view


# History: every ask, with its full response, thread, and saved flag (history.json).


def list_history_records(ws: str) -> list[dict[str, Any]]:
    return _read_json(ws_dir(ws) / "history.json", [])


def add_history(ws: str, question: str, response: dict[str, Any], thread_id: str) -> dict[str, Any]:
    record = {
        "id": uuid.uuid4().hex[:12],
        "question": question,
        "response": response,
        "thread_id": thread_id,
        "created_at": now_iso(),
        # Answered questions go to Saved answers automatically; not-found ones stay in History.
        "saved": response.get("status") == "answered",
    }
    with lock(ws):
        records = list_history_records(ws)
        records.append(record)
        _write_json(ws_dir(ws) / "history.json", records)
    return record


def get_history(ws: str, history_id: str) -> dict[str, Any]:
    for record in list_history_records(ws):
        if record["id"] == history_id:
            return record
    raise NotFound(history_id)


def set_history_saved(ws: str, history_id: str, saved: bool) -> dict[str, Any]:
    with lock(ws):
        records = list_history_records(ws)
        for record in records:
            if record["id"] == history_id:
                record["saved"] = saved
                _write_json(ws_dir(ws) / "history.json", records)
                return record
    raise NotFound(history_id)


def answer_text(response: dict[str, Any]) -> str:
    return " ".join(s["text"] for s in response.get("answer", []))


def history_item(record: dict[str, Any]) -> dict[str, Any]:
    response = record["response"]
    preview = answer_text(response) or response.get("reason") or ""
    return {
        "id": record["id"],
        "question": record["question"],
        "status": response["status"],
        "answer_preview": preview[:160] + ("…" if len(preview) > 160 else ""),
        "thread_id": record["thread_id"],
        "created_at": record["created_at"],
        "saved": record["saved"],
    }


def history_detail(record: dict[str, Any]) -> dict[str, Any]:
    return {k: record[k] for k in ("question", "response", "thread_id", "created_at", "saved")}


def thread_context(ws: str, thread_id: str, limit: int = 3) -> list[tuple[str, str]]:
    """The last `limit` (question, answer) pairs of a thread, oldest first."""
    turns = [r for r in list_history_records(ws) if r["thread_id"] == thread_id]
    return [(r["question"], answer_text(r["response"]) or "(not found)") for r in turns[-limit:]]


# Knowledge stats


def _mtime_iso(paths: list[Path]) -> str | None:
    times = [p.stat().st_mtime for p in paths if p.exists()]
    if not times:
        return None
    return datetime.fromtimestamp(max(times), timezone.utc).isoformat(timespec="seconds")


def knowledge_stats(ws: str) -> dict[str, Any]:
    records = list_file_records(ws)
    ready = [r for r in records if r["status"] == "ready"]
    notes = list_notes(ws)
    return {
        "files": len(records),
        "ready_files": len(ready),
        "pages": sum(r.get("pages", 0) for r in ready),
        "passages": len(load_blocks(ws)) + len(notes),
        "notes": len(notes),
        "folders": len(list_folder_records(ws)),
        "last_indexed_at": _mtime_iso([ws_dir(ws) / "blocks.json", *notes_dir(ws).glob("*.md")]),
    }


# Opening the original document (GET .../files/{id}/raw and /text)

FILE_ID_RE = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def original_path(ws: str, file_id: str) -> Path | None:
    """The original file on disk for a registered file id, or None.

    Uploads must resolve inside this workspace's uploads/; folder files are served only
    while their source_path is still inside a connected folder. Symlinks are never followed.
    """
    if not FILE_ID_RE.match(file_id):
        return None
    record = next((r for r in list_file_records(ws) if r["id"] == file_id), None)
    if record is None or not record.get("path"):
        return None
    raw = Path(record["path"])
    if raw.is_symlink():
        return None
    path = raw.resolve()
    if record.get("source") == "folder":
        roots = [Path(f["path"]).resolve() for f in list_folder_records(ws) if f["id"] == record.get("folder_id")]
        allowed = any(_inside(path, root) for root in roots)
    else:
        allowed = _inside(path, uploads_dir(ws).resolve())
    return path if allowed and path.is_file() else None


def file_text(ws: str, file_id: str) -> dict[str, Any] | None:
    """{id, name, type, pages: [{page, blocks: [{text, table?}]}]} from the parsed blocks."""
    record = next((r for r in list_file_records(ws) if r["id"] == file_id), None) if FILE_ID_RE.match(file_id) else None
    if record is None:
        return None
    pages: dict[int, list[dict[str, Any]]] = {}
    for block in load_blocks(ws):
        if block["file_id"] == file_id:
            item = {"text": block["text"], "locator": block["locator"]}
            if block.get("table"):
                item["table"] = block["table"]
            if block.get("bbox"):
                item["bbox"] = block["bbox"]
            pages.setdefault(block["page"], []).append(item)
    return {
        "id": record["id"],
        "name": record["name"],
        "type": record["type"],
        "page_count": max([record.get("pages") or 0, *pages]) if pages else record.get("pages") or 0,
        "pages": [{"page": n, "blocks": pages[n]} for n in sorted(pages)],
    }


def page_locator(ws: str, file_id: str, page: int) -> str | None:
    """doc:{id}/tier:{tier}/page:{n} for a parsed PDF page, from its blocks' locators."""
    record = next((r for r in list_file_records(ws) if r["id"] == file_id), None) if FILE_ID_RE.match(file_id) else None
    if record is None or record["type"] != "pdf" or not 1 <= page <= max(record.get("pages") or 0, 1):
        return None
    for block in load_blocks(ws):
        if block["file_id"] == file_id and block["locator"].startswith("doc:"):
            return re.sub(r"/page:\d+.*$", f"/page:{page}", block["locator"])
    return None
