from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import answer, crops, folders, llm, parsing, search, storage

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Persistent knowledge base: everything is reloaded from backend/data on startup.
    storage.seed_demo_workspace()
    for ws in storage.workspace_ids():
        search.rebuild(ws)
        parsing.resume_interrupted(ws)
        folders.resume(ws)
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
        "mineru": parsing.server_status(),
    }


@app.get("/api/workspaces")
def list_workspaces() -> list[dict[str, Any]]:
    return storage.list_workspaces()


@app.post("/api/workspaces")
def create_workspace(body: CreateWorkspace) -> dict[str, Any]:
    return storage.create_workspace(body.name.strip(), body.industry.strip())


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


@app.post("/api/workspaces/{ws}/ask")
def ask(ws: str, body: AskRequest) -> dict[str, Any]:
    _require_workspace(ws)
    return answer.ask(ws, body.question.strip(), body.thread_id)


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
