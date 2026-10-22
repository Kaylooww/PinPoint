"""Block and note vectors for hybrid retrieval, cached in data/{ws}/embeddings.json.

Vectors are keyed by a hash of the block text (and the model and dimensions), so restarts
and rescans only embed new or changed blocks. Everything here degrades quietly: if the
embedding server is off or failing, callers get whatever vectors are cached and fall back
to BM25 for the rest.
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


def text_hash(text: str) -> str:
    cfg = llm.embed_config()
    return hashlib.sha256(f"{cfg.model}|{cfg.dimensions}|{text}".encode()).hexdigest()[:20]


def normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector)) or 1.0
    return [x / norm for x in vector]


def _path(ws: str):
    return storage.ws_dir(ws) / "embeddings.json"


def load(ws: str) -> dict[str, list[float]]:
    try:
        return json.loads(_path(ws).read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def _lock(ws: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(ws, threading.Lock())


def ensure(ws: str, blocks: list[dict[str, Any]], max_new: int | None = None) -> dict[str, list[float]]:
    """Unit vectors keyed by text hash for `blocks`, embedding any that are missing.

    Never raises: on failure, returns what is cached. `max_new` caps how many blocks are
    embedded in this call (keeps asks fast when a big backlog is missing).
    """
    with _lock(ws):
        cached = load(ws)
        # Vectors embed the passage text alone (the heading path goes to BM25), so existing
        # vectors stay valid when breadcrumbs change and nothing needs a mass re-embed.
        wanted = {text_hash(b["text"]): b["text"] for b in blocks if b.get("text", "").strip()}
        missing = [(h, t) for h, t in wanted.items() if h not in cached]
        if max_new is not None:
            missing = missing[:max_new]
        if missing and llm.embeddings_enabled():
            try:
                vectors = llm.embed([t for _, t in missing])
                for (h, _), v in zip(missing, vectors):
                    cached[h] = [round(x, 6) for x in normalize(v)]
            except llm.LLMError as e:
                log.warning("embedding %d blocks for %s failed: %s", len(missing), ws, e)
        kept = {h: v for h, v in cached.items() if h in wanted}  # drop vectors of deleted blocks
        if missing or len(kept) != len(cached):
            storage.ws_dir(ws).mkdir(parents=True, exist_ok=True)
            tmp = _path(ws).with_suffix(".tmp")
            tmp.write_text(json.dumps(kept), encoding="utf-8")
            tmp.replace(_path(ws))
        return kept
