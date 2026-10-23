"""Local models (Ollama): request options, thinking/JSON parsing, context cap, model switch.

  cd backend && .venv/bin/python tests/test_local_llm.py

Runs offline: the chat and embedding servers are faked. Covers
- localhost gets temperature, thinking off, and JSON mode, and drops JSON mode when the
  model refuses it; a remote server gets none of these (the organizers' server rejected them);
- thinking text and prose around the JSON are stripped before parsing;
- a local model gets at most 8 context blocks, with every retrieved block kept;
- embeddings.json from another model: search uses BM25 alone, a background pass re-embeds
  every block (no re-parse), records the model, and hybrid search resumes.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PINPOINT_DATA_DIR"] = tempfile.mkdtemp(prefix="pinpoint-test-")
os.environ.update(
    LLM_PROVIDER="openai_compatible",
    OPENAI_COMPAT_BASE="http://localhost:11434/v1",
    OPENAI_COMPAT_KEY="ollama",
    OPENAI_COMPAT_MODEL="gemma4:e2b",
    EMBED_BASE="http://localhost:11434/v1",
    EMBED_MODEL="embeddinggemma",
    EMBED_DIMENSIONS="8",
)
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from app import answer, embeddings, llm, search, storage  # noqa: E402

FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "blocks.json").read_text())
WS = "reyes-partners"


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        sys.exit(1)


# 1. Request options per server.
sent: list[dict] = []
reply = {"status": "answered", "answer": []}


def fake_post(url, headers=None, json=None, timeout=None):
    sent.append(dict(json))
    if url.endswith("/embeddings"):
        data = [{"index": i, "embedding": [float(len(t) % 7 + 1), 1.0, 0, 0, 0, 0, 0, float(i)]} for i, t in enumerate(json["input"])]
        return httpx.Response(200, json={"data": data})
    if "response_format" in json:
        return httpx.Response(501, json={"error": {"message": "structured output is unavailable"}})
    content = "<think>The user wants {json}.</think>\n```json\n" + __import__("json").dumps(reply) + "\n```"
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


httpx.post = fake_post
result = llm.chat_json("Answer.", "q")
check("local: first request has temperature 0, reasoning_effort none, JSON mode", sent[0].get("temperature") == 0 and sent[0].get("reasoning_effort") == "none" and "response_format" in sent[0])
check("local: JSON mode refused (501) → same call retried without it", len(sent) == 2 and "response_format" not in sent[1])
check("thinking tags and code fences stripped before parsing", result == reply)
sent.clear()
llm.chat_json("Answer.", "q")
check("refusal remembered: no JSON mode on later calls", len(sent) == 1 and "response_format" not in sent[0])

os.environ["OPENAI_COMPAT_BASE"] = "https://webui.example.org/api"
sent.clear()
llm.chat_json("Answer.", "q")
check("remote server: no temperature, reasoning_effort, or response_format", not {"temperature", "reasoning_effort", "response_format"} & set(sent[0]))
check("remote server: 12 context blocks", llm.max_context_blocks() == 12)
os.environ["OPENAI_COMPAT_BASE"] = "http://localhost:11434/v1"
check("localhost: 8 context blocks", llm.max_context_blocks() == 8)

# 2. Replies a small local model gives: prose after the JSON, and the object closed early.
text = '{"status": "answered", "quotes": {"b1": "x"}} Hope this helps {"draft": 1}'
check("prose after the JSON: first object parsed", llm.parse_json_object(text) == {"status": "answered", "quotes": {"b1": "x"}})
text = '{"status": "not_found", "reason": "r"},\n"suggestion": {"text": "Did you mean?", "sources": ["b2"]}'
check("object closed early: trailing keys merged back in", llm.parse_json_object(text) == {"status": "not_found", "reason": "r", "suggestion": {"text": "Did you mean?", "sources": ["b2"]}})
text = '{"status": "answered", "answer": [{"text": "Stamp “NOT VALID FOR INPUT TAX." on it.", "sources": ["b1"]}]}'
check("unescaped quote copied from a document: repaired", llm.parse_json_object(text)["answer"][0]["text"] == 'Stamp “NOT VALID FOR INPUT TAX." on it.')
text = '{"status": "answered", "answer": [{"text": "Stamp “Invoice", “Cash Invoice" on it.", "sources": ["b1"]}]}'
check("mismatched document quotes (“Invoice\", “Cash Invoice\"): repaired", llm.parse_json_object(text)["answer"][0]["text"] == 'Stamp “Invoice", “Cash Invoice" on it.')
try:
    llm.parse_json_object('{"status": "answered", "answer": [{"text": "cut off')
    check("cut-off reply still raises", False)
except json.JSONDecodeError:
    check("cut-off reply still raises (so the stricter retry runs)", True)

# 3. Workspace with vectors from the organizers' model (flat file, 512 dims).
storage.create_workspace("Reyes & Partners", "Law office", WS)
storage.save_file_records(
    WS, [{**f, "size_bytes": 1000, "status": "ready", "source": "upload", "path": "", "created_at": storage.now_iso()} for f in FIXTURE["files"]]
)
for f in FIXTURE["files"]:
    storage.replace_file_blocks(WS, f["id"], [b for b in FIXTURE["blocks"] if b["file_id"] == f["id"]])
search.rebuild(WS)
path = storage.ws_dir(WS) / "embeddings.json"
path.write_text(json.dumps({"abc123": [0.1] * 512}))
blocks_before = (storage.ws_dir(WS) / "blocks.json").read_text()

check("old-model file: not ready", embeddings.ready(WS) is False)
sent.clear()
hits = search.hybrid(WS, "When must the respondent file its Answer?", [], k=6)
check("old-model file: hybrid still returns BM25 hits", len(hits) > 0)
for _ in range(50):
    if embeddings.ready(WS) and WS not in embeddings._running:
        break
    time.sleep(0.1)
stored = json.loads(path.read_text())
texts = {b["text"] for b in search.get_index(WS).blocks if b["text"].strip()}
check("background pass re-embedded every block", stored.get("model") == "embeddinggemma" and stored.get("complete") is True and len(stored["vectors"]) == len(texts))
check("old vectors dropped, dimensions recorded", "abc123" not in stored["vectors"] and stored["dimensions"] == 8)
check("embeddinggemma document prefix used", any(t.startswith("title: none | text: ") for s in sent if "input" in s for t in s["input"]))
check("blocks.json untouched (no re-parse)", (storage.ws_dir(WS) / "blocks.json").read_text() == blocks_before)
sent.clear()
search.hybrid(WS, "When must the respondent file its Answer?", [], k=6)
check("after re-embed: query embedded with the search-query prefix", sent and sent[0]["input"] == ["task: search result | query: When must the respondent file its Answer?"])

# 4. Context cap: 8 blocks, retrieved ones always kept. A 20-block page about penalties
#    (plus its heading) gives retrieval, neighbours, and headings more than 8 to offer.
long_blocks = [{"id": "fx-long-p1-b1", "file_id": "fx-long", "file_name": "Rental.pdf", "page": 1, "locator": "doc:fxl/page:1/block:1", "text": "Article V. Penalties"}]
long_blocks += [
    {"id": f"fx-long-p1-b{i}", "file_id": "fx-long", "file_name": "Rental.pdf", "page": 1, "locator": f"doc:fxl/page:1/block:{i}",
     "text": f"Clause {i}: the renter pays a penalty of PHP {i},000 if the car leaves Cebu.", "heading_ids": ["fx-long-p1-b1"], "path": ["Article V. Penalties"]}
    for i in range(2, 22)
]
records = storage.list_file_records(WS) + [{"id": "fx-long", "name": "Rental.pdf", "type": "pdf", "pages": 1, "size_bytes": 1000, "status": "ready", "source": "upload", "path": "", "created_at": storage.now_iso()}]
storage.save_file_records(WS, records)
storage.replace_file_blocks(WS, "fx-long", long_blocks)
search.rebuild(WS)
seen_passages: list[str] = []


def fake_chat_json(system: str, user: str, max_tokens: int = 500) -> dict:
    if "keywords" in system:
        return {"keywords": ["penalty", "car", "Cebu"]}
    seen_passages.append(user)
    return {"status": "not_found", "answer": [], "reason": "test"}


llm.chat_json = fake_chat_json
question = "What is the penalty if the car leaves Cebu?"
retrieved = [b["id"] for b, _ in search.hybrid(WS, question, ["penalty", "car", "Cebu"], k=answer.TOP_K)]
answer.ask(WS, question)
count = seen_passages[-1].count("\n[b")
check(f"local model: {count} context blocks (at most 8)", count == 8)
by_text = {b["id"]: b["text"] for b in long_blocks}
check("all 6 retrieved blocks are in the context", len(retrieved) == 6 and all(by_text.get(r, r) in seen_passages[-1] for r in retrieved))
check("heading block included (its text starts a passage line)", "\nArticle V. Penalties" in seen_passages[-1])

print("local model checks passed")
