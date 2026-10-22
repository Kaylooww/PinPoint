"""Connected local folders: read in place, rescanned on request, never modified.

Safety limits (docs/ARCHITECTURE.md, "Local folders"): the path must be an existing
directory; walk read-only to depth 5; at most 200 files of at most 50 MB each; supported
extensions only; skip hidden folders, node_modules, .git, and system folders; never
follow symlinks. Nothing outside backend/data is ever written or deleted.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from . import parsing, search, storage

MAX_DEPTH = 5
MAX_FILES = 200
MAX_FILE_BYTES = 50 * 1024 * 1024
SUPPORTED = {"pdf", "png", "jpg", "jpeg", "webp", "docx", "xlsx", "pptx", "csv", "md", "txt"}
SKIP_DIRS = {
    "node_modules", "__pycache__", "venv", ".venv", "Library", "System", "Applications",
    "Windows", "Program Files", "Program Files (x86)", "$RECYCLE.BIN", "System Volume Information",
}
SYSTEM_ROOTS = {Path("/"), Path("/System"), Path("/Library"), Path("/usr"), Path("/bin"), Path("/etc"), Path("/private")}

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scan")


class FolderError(Exception):
    pass


def validate_path(raw: str) -> Path:
    path = Path(os.path.expanduser(raw.strip()))
    if not path.is_absolute():
        raise FolderError("Use a full folder path, for example /Users/you/Documents/Client.")
    if path.is_symlink():
        raise FolderError("That path is a shortcut (symlink). Choose the real folder.")
    if not path.exists():
        raise FolderError("That folder doesn't exist on this computer.")
    if not path.is_dir():
        raise FolderError("That path is a file, not a folder.")
    resolved = path.resolve()
    if resolved in SYSTEM_ROOTS or resolved == Path.home().resolve():
        raise FolderError("Choose a specific folder, not a system or home folder.")
    if resolved == storage.DATA_DIR.resolve() or storage.DATA_DIR.resolve() in resolved.parents:
        raise FolderError("That folder is PinPoint's own data folder.")
    return resolved


def walk(root: Path) -> list[tuple[str, int, float]]:
    """Supported files under root as (path, size, mtime), within every safety limit."""
    found: list[tuple[str, int, float]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        depth = len(Path(dirpath).relative_to(root).parts)
        # Prune in place so os.walk never descends into skipped folders.
        dirnames[:] = sorted(
            d for d in dirnames
            if not d.startswith(".") and d not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d))
        ) if depth < MAX_DEPTH else []
        for name in sorted(filenames):
            if name.startswith(".") or name.rsplit(".", 1)[-1].lower() not in SUPPORTED or "." not in name:
                continue
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue
            try:
                stat = os.stat(full, follow_symlinks=False)
            except OSError:
                continue
            if stat.st_size == 0 or stat.st_size > MAX_FILE_BYTES:
                continue
            found.append((full, stat.st_size, stat.st_mtime))
            if len(found) >= MAX_FILES:
                return found
    return found


def _scan(ws: str, folder_id: str) -> None:
    folder = next((f for f in storage.list_folder_records(ws) if f["id"] == folder_id), None)
    if folder is None:
        return
    try:
        root = validate_path(folder["path"])
        on_disk = {path: (size, mtime) for path, size, mtime in walk(root)}
        known = {r["source_path"]: r for r in storage.list_file_records(ws) if r.get("folder_id") == folder_id}
        changed = False
        for path, record in known.items():
            if path not in on_disk:  # deleted from the folder: drop from the index
                storage.remove_file(ws, record["id"])
                changed = True
        for path, (size, mtime) in on_disk.items():
            record = known.get(path)
            if record is None:
                record = storage.add_folder_file(ws, folder_id, path, size, mtime)
                parsing.enqueue(ws, record["id"])
            elif record.get("mtime") != mtime or record.get("size_bytes") != size:
                storage.update_file(ws, record["id"], status="queued", size_bytes=size, mtime=mtime, error=None)
                parsing.enqueue(ws, record["id"])
        if changed:
            search.rebuild(ws)
        storage.update_folder(ws, folder_id, status="ready", last_scanned_at=storage.now_iso(), error=None)
    except Exception as e:  # noqa: BLE001 - a failed scan marks the folder failed
        message = str(e) if isinstance(e, FolderError) else f"Couldn't read this folder ({type(e).__name__})."
        storage.update_folder(ws, folder_id, status="failed", last_scanned_at=storage.now_iso(), error=message)
    storage.touch_workspace(ws)


def connect(ws: str, raw_path: str) -> dict[str, Any]:
    root = validate_path(raw_path)
    records = storage.list_folder_records(ws)
    if any(f["path"] == str(root) for f in records):
        raise FolderError("That folder is already connected.")
    record = {"id": uuid.uuid4().hex[:12], "path": str(root), "status": "scanning", "last_scanned_at": None}
    storage.save_folder_records(ws, [*records, record])
    _executor.submit(_scan, ws, record["id"])
    return storage.folder_view(ws, record)


def rescan(ws: str, folder_id: str) -> dict[str, Any]:
    record = storage.update_folder(ws, folder_id, status="scanning", error=None)
    _executor.submit(_scan, ws, folder_id)
    return storage.folder_view(ws, record)


def disconnect(ws: str, folder_id: str) -> None:
    """Remove the folder's files from the index. The folder on disk is left untouched."""
    records = storage.list_folder_records(ws)
    if not any(f["id"] == folder_id for f in records):
        raise storage.NotFound(folder_id)
    for record in storage.list_file_records(ws):
        if record.get("folder_id") == folder_id:
            storage.remove_file(ws, record["id"])
    storage.save_folder_records(ws, [f for f in records if f["id"] != folder_id])
    search.rebuild(ws)
    storage.touch_workspace(ws)


def resume(ws: str) -> None:
    """On startup, finish scans that were interrupted."""
    for folder in storage.list_folder_records(ws):
        if folder["status"] == "scanning":
            _executor.submit(_scan, ws, folder["id"])
