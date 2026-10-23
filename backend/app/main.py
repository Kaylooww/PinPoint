import logging
import mimetypes
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from . import answer, crops, folders, llm, parsing, picker, search, storage

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Our own log lines (tier choice, parse times, embedding failures) next to uvicorn's.
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
logging.getLogger("pinpoint").addHandler(_handler)
logging.getLogger("pinpoint").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Persistent knowledge base: everything is reloaded from backend/data on startup.
    storage.seed_demo_workspace()
    for ws in storage.workspace_ids():
        search.rebuild(ws)
        parsing.resume_interrupted(ws)
        folders.resume(ws)
    parsing.start_watchdog()
    # Fill in any missing vectors without delaying startup.
    threading.Thread(target=lambda: [search.index_vectors(ws) for ws in storage.workspace_ids()], daemon=True).start()
    yield


app = FastAPI(title="PinPoint API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateWorkspace(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    industry: str = Field(min_length=1, max_length=60)


class CreateNote(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class ConnectFolder(BaseModel):
    path: str = Field(min_length=1, max_length=1024)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    thread_id: str | None = Field(default=None, max_length=64)
    file_ids: list[str] | None = Field(default=None, max_length=50)


class SaveHistory(BaseModel):
    saved: bool


def _require_workspace(ws: str) -> None:
    try:
        storage.workspace_view(ws)
    except storage.NotFound:
        raise HTTPException(status_code=404, detail="Workspace not found") from None


@app.get("/api/health")
def health() -> dict[str, Any]:
    status = llm.health()
    return {
        "ok": True,
        "llm": {k: status.get(k) for k in ("ok", "provider", "model", "mode", "latency_ms", "error")},
        "embeddings": llm.embed_health(),
        "mineru": parsing.server_status(),
    }


@app.post("/api/system/pick-folder", response_model=None)
def pick_folder(request: Request) -> dict[str, str | None] | JSONResponse:
    """Open the OS folder picker and return the chosen path (null if cancelled).

    Localhost only. It does not connect the folder; POST /folders validates the path.
    """
    if request.client is None or request.client.host not in ("127.0.0.1", "::1"):
        return JSONResponse(status_code=403, content={"error": "The folder picker is only available on this computer."})
    try:
        return {"path": picker.pick_folder()}
    except picker.PickerUnavailable:
        return JSONResponse(status_code=501, content={"error": "Folder picker not available; type the path instead."})


@app.get("/api/workspaces")
def list_workspaces() -> list[dict[str, Any]]:
    return storage.list_workspaces()


@app.post("/api/workspaces")
def create_workspace(body: CreateWorkspace) -> dict[str, Any]:
    return storage.create_workspace(body.name.strip(), body.industry.strip())


@app.delete("/api/workspaces/{ws}")
def delete_workspace(ws: str) -> dict[str, bool]:
    """Delete a workspace and all of its data in backend/data. Parsing is cancelled first."""
    _require_workspace(ws)
    for record in storage.list_file_records(ws):
        if record["status"] in ("queued", "parsing"):
            parsing.cancel(ws, record["id"])
    try:
        storage.delete_workspace(ws)
    except storage.NotFound:
        raise HTTPException(status_code=404, detail="Workspace not found") from None
    search.forget(ws)
    answer.forget(ws)
    return {"ok": True}


@app.get("/api/workspaces/{ws}/files")
def list_files(ws: str) -> list[dict[str, Any]]:
    _require_workspace(ws)
    return storage.list_files(ws)


@app.post("/api/workspaces/{ws}/files")
async def upload_files(ws: str, files: list[UploadFile] = File(...)) -> list[dict[str, Any]]:
    _require_workspace(ws)
    added = []
    for upload in files:
        data = await upload.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"{upload.filename} is larger than 50 MB")
        record = storage.add_upload(ws, upload.filename or "file", data)
        parsing.enqueue(ws, record["id"])
        added.append(storage.file_view(record))
    return added


@app.delete("/api/workspaces/{ws}/files/{file_id}")
def delete_file(ws: str, file_id: str) -> dict[str, bool]:
    """Delete an uploaded file; one that is queued or being read is cancelled first."""
    _require_workspace(ws)
    record = next((r for r in storage.list_file_records(ws) if r["id"] == file_id), None)
    if record and record.get("source") != "folder" and record["status"] in ("queued", "parsing"):
        parsing.cancel(ws, file_id)
    try:
        storage.delete_file(ws, file_id)
    except storage.NotFound:
        raise HTTPException(status_code=404, detail="File not found") from None
    except storage.CannotDelete as e:
        raise HTTPException(status_code=409, detail=str(e)) from None
    search.rebuild(ws)
    storage.touch_workspace(ws)
    return {"ok": True}


@app.get("/api/workspaces/{ws}/files/{file_id}/raw")
def raw_file(ws: str, file_id: str) -> FileResponse:
    """The original document, inline. Registered files only; never a path from the URL."""
    _require_workspace(ws)
    path = storage.original_path(ws, file_id)
    if path is None:
        raise HTTPException(status_code=404, detail="File not found")
    name = next(r["name"] for r in storage.list_file_records(ws) if r["id"] == file_id)
    media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=name, content_disposition_type="inline")


@app.get("/api/workspaces/{ws}/files/{file_id}/pages/{page}.png")
def page_png(ws: str, file_id: str, page: int) -> FileResponse:
    """A PDF page rendered as an image (registered files only, by id; 404 otherwise)."""
    _require_workspace(ws)
    locator = storage.page_locator(ws, file_id, page)
    path = crops.page_image(ws, locator) if locator else None
    if path is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return FileResponse(path, media_type="image/png")


@app.get("/api/workspaces/{ws}/files/{file_id}/text")
def file_text(ws: str, file_id: str) -> dict[str, Any]:
    _require_workspace(ws)
    text = storage.file_text(ws, file_id)
    if text is None:
        raise HTTPException(status_code=404, detail="File not found")
    return text


@app.post("/api/workspaces/{ws}/ask")
def ask(ws: str, body: AskRequest) -> dict[str, Any]:
    _require_workspace(ws)
    return answer.ask(ws, body.question.strip(), body.thread_id, body.file_ids)


@app.get("/api/workspaces/{ws}/history")
def list_history(ws: str) -> list[dict[str, Any]]:
    _require_workspace(ws)
    return [storage.history_item(r) for r in reversed(storage.list_history_records(ws))]


@app.get("/api/workspaces/{ws}/history/{history_id}")
def get_history(ws: str, history_id: str) -> dict[str, Any]:
    _require_workspace(ws)
    try:
        return storage.history_detail(storage.get_history(ws, history_id))
    except storage.NotFound:
        raise HTTPException(status_code=404, detail="Not found in history") from None


@app.patch("/api/workspaces/{ws}/history/{history_id}")
def save_history(ws: str, history_id: str, body: SaveHistory) -> dict[str, Any]:
    _require_workspace(ws)
    try:
        return storage.history_item(storage.set_history_saved(ws, history_id, body.saved))
    except storage.NotFound:
        raise HTTPException(status_code=404, detail="Not found in history") from None


@app.get("/api/workspaces/{ws}/knowledge")
def knowledge(ws: str) -> dict[str, Any]:
    _require_workspace(ws)
    return storage.knowledge_stats(ws)


@app.get("/api/workspaces/{ws}/notes")
def list_notes(ws: str) -> list[dict[str, Any]]:
    _require_workspace(ws)
    return storage.list_notes(ws)


@app.post("/api/workspaces/{ws}/notes")
def create_note(ws: str, body: CreateNote) -> dict[str, Any]:
    _require_workspace(ws)
    note = storage.add_note(ws, body.text)
    search.rebuild(ws)
    search.index_vectors(ws)
    return note


@app.delete("/api/workspaces/{ws}/notes/{note_id}")
def delete_note(ws: str, note_id: str) -> dict[str, bool]:
    _require_workspace(ws)
    try:
        storage.delete_note(ws, note_id)
    except storage.NotFound:
        raise HTTPException(status_code=404, detail="Note not found") from None
    search.rebuild(ws)
    return {"ok": True}


@app.get("/api/workspaces/{ws}/folders")
def list_folders(ws: str) -> list[dict[str, Any]]:
    _require_workspace(ws)
    return [storage.folder_view(ws, f) for f in storage.list_folder_records(ws)]


@app.post("/api/workspaces/{ws}/folders")
def connect_folder(ws: str, body: ConnectFolder) -> dict[str, Any]:
    _require_workspace(ws)
    try:
        return folders.connect(ws, body.path)
    except folders.FolderError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@app.post("/api/workspaces/{ws}/folders/{folder_id}/rescan")
def rescan_folder(ws: str, folder_id: str) -> dict[str, Any]:
    _require_workspace(ws)
    try:
        return folders.rescan(ws, folder_id)
    except storage.NotFound:
        raise HTTPException(status_code=404, detail="Folder not found") from None


@app.delete("/api/workspaces/{ws}/folders/{folder_id}")
def disconnect_folder(ws: str, folder_id: str) -> dict[str, bool]:
    _require_workspace(ws)
    try:
        folders.disconnect(ws, folder_id)
    except storage.NotFound:
        raise HTTPException(status_code=404, detail="Folder not found") from None
    return {"ok": True}


@app.get("/api/crops/{crop_id}.png")
def get_crop(crop_id: str) -> FileResponse:
    path = crops.crop_path(crop_id)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Crop not found")
    return FileResponse(path, media_type="image/png")
