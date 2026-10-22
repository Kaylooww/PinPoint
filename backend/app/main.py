from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import answer, crops, llm, parsing, search, storage

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Persistent knowledge base: everything is reloaded from backend/data on startup.
    storage.seed_demo_workspace()
    for ws in storage.workspace_ids():
        search.rebuild(ws)
        parsing.resume_interrupted(ws)
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


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


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
    return answer.ask(ws, body.question.strip())


@app.get("/api/crops/{crop_id}.png")
def get_crop(crop_id: str) -> FileResponse:
    path = crops.crop_path(crop_id)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Crop not found")
    return FileResponse(path, media_type="image/png")
