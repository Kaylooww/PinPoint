from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import llm, parsing

app = FastAPI(title="PinPoint API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    status = llm.health()
    return {
        "ok": True,
        "llm": {k: status.get(k) for k in ("ok", "provider", "model", "mode", "latency_ms", "error")},
        "mineru": parsing.server_status(),
    }
