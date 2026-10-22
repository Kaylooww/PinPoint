"""Hybrid retrieval: embedding fallbacks, and the zero-outbound guarantee with LLM_PROVIDER=none.

  cd backend && .venv/bin/python tests/test_hybrid.py

Part A runs offline on the fixture (the LLM is faked; the embedding server is pointed at
an unreachable address). Part B needs the running backend with the real samples, the
LLM, and the embedding server: "Who is the renter?" (wording not in the document's
relevant passage) must answer with a citation naming the renter. Skip B with --offline.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PINPOINT_DATA_DIR"] = tempfile.mkdtemp(prefix="pinpoint-test-")
os.environ["EMBED_BASE"] = "http://10.255.255.1:9/v1"  # non-routable: connections hang until the timeout
os.environ.setdefault("EMBED_MODEL", "qwen3-embedding")
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from app import answer, llm, search, storage  # noqa: E402

FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "blocks.json").read_text())
WS = "reyes-partners"


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        sys.exit(1)


storage.create_workspace("Reyes & Partners", "Law office", WS)
storage.save_file_records(
    WS, [{**f, "size_bytes": 1000, "status": "ready", "source": "upload", "path": "", "created_at": storage.now_iso()} for f in FIXTURE["files"]]
)
for f in FIXTURE["files"]:
    storage.replace_file_blocks(WS, f["id"], [b for b in FIXTURE["blocks"] if b["file_id"] == f["id"]])
search.rebuild(WS)


def fake_chat_json(system: str, user: str, max_tokens: int = 500) -> dict:
    if "keywords" in system:
        return {"keywords": ["deadline", "file"]}
    bid = "b1"
    for chunk in user.split("\n[")[1:]:
        if "March 14, 2026" in chunk:
            bid = chunk.split("]")[0]
    return {"status": "answered", "answer": [{"text": "Due March 14, 2026.", "sources": [bid]}]}


real_chat_json = llm.chat_json
llm.chat_json = fake_chat_json

# A: embedding server unreachable -> BM25, answer within the normal time.
os.environ["LLM_PROVIDER"] = "openai_compatible"
os.environ.setdefault("OPENAI_COMPAT_BASE", "http://fake.invalid/api")
os.environ.setdefault("OPENAI_COMPAT_MODEL", "fake")
started = time.perf_counter()
r1 = answer.ask(WS, "When is the filing deadline for the Santos case?")
first = time.perf_counter() - started
check(f"unreachable embeddings: still answered ({first:.1f}s, timeout {llm.embed_config().timeout:.0f}s)", r1["status"] == "answered" and first < llm.embed_config().timeout + 1.5)
check("cites the deadline passage via BM25", any("March 14, 2026" in c["text"] for c in r1["citations"]))
started = time.perf_counter()
r2 = answer.ask(WS, "Who is counsel for the respondent?")
second = time.perf_counter() - started
check("circuit open after the failure", llm._embed_down_until > time.monotonic())
check(f"next ask doesn't wait on the dead server: {second * 1000:.0f} ms", second < 1.5)
health = llm.embed_health(force=True)
check(f"/api/health reports embeddings not ok: {health.get('error')}", health["ok"] is False)

# A2: LLM_PROVIDER=none -> zero outbound calls (any httpx request fails the test).
os.environ["LLM_PROVIDER"] = "none"
calls = []
real_post = httpx.post
httpx.post = lambda *a, **kw: calls.append(a) or (_ for _ in ()).throw(AssertionError("outbound call"))
r3 = answer.ask(WS, "How much was the filing fee on the official receipt?")
search.index_vectors(WS)
httpx.post = real_post
check("LLM_PROVIDER=none: answered extractively", r3["status"] == "answered" and r3.get("reason") == "Showing matching passages.")
check("LLM_PROVIDER=none: zero outbound calls (LLM and embeddings)", calls == [])

llm.chat_json = real_chat_json
if "--offline" in sys.argv:
    print("hybrid checks passed (offline)")
    sys.exit(0)

# B: live, against the running backend and the real samples.
api = "http://localhost:8000/api/workspaces/reyes-partners/ask"
health = httpx.get("http://localhost:8000/api/health", timeout=30).json()
check(f"live: embeddings ok in /api/health ({health['embeddings'].get('latency_ms')} ms)", health["embeddings"]["ok"] is True)
live = httpx.post(api, json={"question": "Who is the renter?"}, timeout=120).json()
print("   answer:", " ".join(s["text"] for s in live["answer"]) or live.get("reason"))
check(
    "live: 'Who is the renter?' answers with a citation naming the renter",
    live["status"] == "answered" and any("Caldenm" in c["text"] for c in live["citations"]),
)
print("hybrid checks passed")
