"""Block and note vectors for hybrid retrieval, cached in data/{ws}/embeddings.json.

The file is {"model", "dimensions", "complete", "vectors": {text hash: unit vector}}. Vectors
are keyed by a hash of the block text (and the model and dimensions), so restarts and
rescans only embed new or changed blocks. When the stored model differs from EMBED_MODEL
(or the file predates the model field), every block is re-embedded in the background, in
saved chunks; until that finishes, search uses BM25 alone. Files are never re-parsed.

Everything here degrades quietly: if the embedding server is off or failing, callers get
whatever vectors are cached and fall back to BM25 for the rest.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import threading
from typing import Any

from . import llm, storage

log = logging.getLogger("pinpoint.embeddings")
_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()
_running: set[str] = set()  # workspaces with a full embedding pass in progress
CHUNK = 256  # blocks embedded (and saved) per step of a full pass


def text_hash(text: str) -> str:
    cfg = llm.embed_config()
    return hashlib.sha256(f"{cfg.model}|{cfg.dimensions}|{text}".encode()).hexdigest()[:20]


def normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def query_text(question: str) -> str:
    """The question in the form the embedding model was trained on for search queries."""
    model = llm.embed_config().model.lower()
    if "embeddinggemma" in model:
        return f"task: search result | query: {question}"
    if "nomic" in model:
        return f"search_query: {question}"
    # Qwen3-Embedding is trained with an instruction on queries (never on documents).
    return f"Instruct: Given a question about a client's documents, retrieve passages that answer it\nQuery: {question}"


def document_text(text: str) -> str:
    model = llm.embed_config().model.lower()
    if "embeddinggemma" in model:
        return f"title: none | text: {text}"
    if "nomic" in model:
        return f"search_document: {text}"
    return text


def _path(ws: str):
    return storage.ws_dir(ws) / "embeddings.json"


def _read(ws: str) -> dict[str, Any]:
    try:
        data = json.loads(_path(ws).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {"model": None, "dimensions": None, "complete": True, "vectors": {}, "exists": False}
    if "vectors" not in data:  # before the model field: vectors from the organizers' qwen3-embedding
        return {"model": None, "dimensions": None, "complete": False, "vectors": data, "exists": True}
    return {**data, "exists": True}


def _current(data: dict[str, Any]) -> bool:
    cfg = llm.embed_config()
    return data["model"] == cfg.model and data["dimensions"] == cfg.dimensions


def _write(ws: str, vectors: dict[str, list[float]], complete: bool) -> None:
    cfg = llm.embed_config()
    storage.ws_dir(ws).mkdir(parents=True, exist_ok=True)
    tmp = _path(ws).with_suffix(".tmp")
    payload = {"model": cfg.model, "dimensions": cfg.dimensions, "complete": complete, "vectors": vectors}
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(_path(ws))


def load(ws: str) -> dict[str, list[float]]:
    """Cached vectors for the configured model; empty if they came from another model."""
    data = _read(ws)
    return data["vectors"] if _current(data) else {}


def ready(ws: str) -> bool:
    """False while vectors are from another model or a re-embed is unfinished (use BM25 alone)."""
    data = _read(ws)
    return not data["exists"] or (_current(data) and data.get("complete", True))


def _lock(ws: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(ws, threading.Lock())


def reembed_in_background(ws: str, blocks: list[dict[str, Any]]) -> None:
    """Start a full pass for `ws` on a daemon thread unless one is already running."""
    with _guard:
        if ws in _running:
            return
    threading.Thread(target=ensure, args=(ws, blocks), daemon=True, name=f"embed-{ws}").start()


def ensure(ws: str, blocks: list[dict[str, Any]], max_new: int | None = None) -> dict[str, list[float]]:
    """Unit vectors keyed by text hash for `blocks`, embedding any that are missing.

    Never raises: on failure, returns what is cached. `max_new` caps how many blocks are
    embedded in this call (keeps asks fast when a big backlog is missing); without it this
    is a full pass, saved every CHUNK blocks so asks can read progress and a restart resumes.
    """
    # Vectors embed the passage text alone (the heading path goes to BM25), so existing
    # vectors stay valid when breadcrumbs change and nothing needs a mass re-embed.
    wanted = {text_hash(b["text"]): b["text"] for b in blocks if b.get("text", "").strip()}
    if max_new is not None:
        with _guard:
            busy = ws in _running
        if busy:
            return load(ws)  # the full pass will get there; don't hold up the ask
        return _step(ws, wanted, max_new)

    with _guard:
        if ws in _running:
            return load(ws)
        _running.add(ws)
    try:
        data = _read(ws)
        if data["exists"] and not _current(data):
            log.info("re-embedding %s with %s (stored vectors are from %s)", ws, llm.embed_config().model, data["model"] or "an older model")
        while True:
            before = len(load(ws))
            vectors = _step(ws, wanted, CHUNK, final=True)
            if len(vectors) == before or all(h in vectors for h in wanted):
                return vectors  # done, or the embedding server failed (retried on a later ask)
    finally:
        with _guard:
            _running.discard(ws)


def _step(ws: str, wanted: dict[str, str], limit: int, final: bool = False) -> dict[str, list[float]]:
    with _lock(ws):
        data = _read(ws)
        cached = data["vectors"] if _current(data) else {}
        # A new workspace starts complete; vectors from another model start a re-embed.
        complete = data.get("complete", True) if _current(data) else not data["exists"]
        missing = [(h, t) for h, t in wanted.items() if h not in cached][:limit]
        if missing and llm.embeddings_enabled():
            try:
                vectors = llm.embed([document_text(t) for _, t in missing])
                for (h, _), v in zip(missing, vectors):
                    cached[h] = [round(x, 6) for x in normalize(v)]
            except llm.LLMError as e:
                log.warning("embedding %d blocks for %s failed: %s", len(missing), ws, e)
        if final and all(h in cached for h in wanted):
            complete = True
        kept = {h: v for h, v in cached.items() if h in wanted}  # drop vectors of deleted blocks
        if missing or len(kept) != len(data["vectors"]) or complete != data.get("complete", True) or not _current(data):
            _write(ws, kept, complete)
        return kept
