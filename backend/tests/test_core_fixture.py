"""End-to-end check of storage, endpoints, BM25, and /ask against the temporary fixture.

Runs on a throwaway data dir, so backend/data is never touched:
  cd backend && .venv/bin/python tests/test_core_fixture.py           # uses the configured LLM
  cd backend && LLM_PROVIDER=none .venv/bin/python tests/test_core_fixture.py   # extractive only
"""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PINPOINT_DATA_DIR"] = tempfile.mkdtemp(prefix="pinpoint-test-")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app import main, search, storage  # noqa: E402

FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "blocks.json").read_text())
WS = "reyes-partners"


def load_fixture() -> None:
    records = [
        {**f, "size_bytes": 1000, "status": "ready", "source": "upload", "path": "", "created_at": storage.now_iso()}
        for f in FIXTURE["files"]
    ]
    storage.save_file_records(WS, records)
    for f in FIXTURE["files"]:
        storage.replace_file_blocks(WS, f["id"], [b for b in FIXTURE["blocks"] if b["file_id"] == f["id"]])
    search.rebuild(WS)


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        sys.exit(1)


with TestClient(main.app) as client:
    workspaces = client.get("/api/workspaces").json()
    check("demo workspace seeded", [w["name"] for w in workspaces] == ["Reyes & Partners"])
    check("workspace shape", set(workspaces[0]) == {"id", "name", "industry", "file_count", "updated_at"})

    created = client.post("/api/workspaces", json={"name": "Santos Realty", "industry": "Real estate"}).json()
    check("create workspace", created["id"] == "santos-realty" and created["file_count"] == 0)

    load_fixture()
    files = client.get(f"/api/workspaces/{WS}/files").json()
    check("files listed", len(files) == 2 and all(f["status"] == "ready" for f in files))
    check("file shape", set(files[0]) == {"id", "name", "type", "pages", "size_bytes", "status", "source"})
    check("unknown workspace 404", client.get("/api/workspaces/nope/files").status_code == 404)

    q1 = "When is the filing deadline for the Santos case?"
    r1 = client.post(f"/api/workspaces/{WS}/ask", json={"question": q1}).json()
    print(json.dumps(r1, indent=1))
    check("deadline answered", r1["status"] == "answered")
    check("cites the March 14 block", any("March 14" in c["text"] for c in r1["citations"]))
    ids = {c["id"] for c in r1["citations"]}
    check("every sentence cites a real citation", all(s["sources"] and set(s["sources"]) <= ids for s in r1["answer"]))
    check(
        "citation shape",
        set(r1["citations"][0]) == {"id", "number", "kind", "file_id", "file_name", "page", "locator", "text", "crop_url"},
    )

    again = client.post(f"/api/workspaces/{WS}/ask", json={"question": "  when is the FILING deadline for the santos case? "}).json()
    check("cache hit (same answer, fast)", again["answer"] == r1["answer"] and again["elapsed_ms"] < 50)

    r2 = client.post(f"/api/workspaces/{WS}/ask", json={"question": "What is the client's favorite color?"}).json()
    print(json.dumps(r2, indent=1))
    check("unanswerable -> not_found with reason", r2["status"] == "not_found" and r2.get("reason"))

    empty = client.post("/api/workspaces/santos-realty/ask", json={"question": "Anything?"}).json()
    check("empty workspace -> not_found", empty["status"] == "not_found" and empty["searched_files"] == 0)

print("all checks passed")

# Notes: saved, indexed, cited as kind "note" with no crop, and deletable.
with TestClient(main.app) as client:
    note = client.post(f"/api/workspaces/{WS}/notes", json={"text": "The client prefers updates by email, not phone calls."}).json()
    check("note shape", set(note) == {"id", "text", "created_at"})
    check("notes listed", [n["id"] for n in client.get(f"/api/workspaces/{WS}/notes").json()] == [note["id"]])
    r3 = client.post(f"/api/workspaces/{WS}/ask", json={"question": "How does the client want to be updated?"}).json()
    print(json.dumps(r3, indent=1))
    notes_cited = [c for c in r3["citations"] if c["kind"] == "note"]
    check("answer cites the note", r3["status"] == "answered" and notes_cited and notes_cited[0]["crop_url"] is None)
    check("delete note", client.delete(f"/api/workspaces/{WS}/notes/{note['id']}").json() == {"ok": True})
    check("deleted note 404", client.delete(f"/api/workspaces/{WS}/notes/{note['id']}").status_code == 404)
    check("notes empty", client.get(f"/api/workspaces/{WS}/notes").json() == [])

print("note checks passed")

# History, saved answers, follow-up threads, knowledge stats.
with TestClient(main.app) as client:
    first = client.post(f"/api/workspaces/{WS}/ask", json={"question": "Who is counsel for the respondent in the Santos case?"}).json()
    check("ask returns thread_id and history_id", first.get("thread_id") and first.get("history_id"))
    follow = client.post(
        f"/api/workspaces/{WS}/ask", json={"question": "When must they file the Answer?", "thread_id": first["thread_id"]}
    ).json()
    print("follow-up:", follow["status"], [s["text"] for s in follow["answer"]], follow.get("reason"))
    check("follow-up stays in the thread", follow["thread_id"] == first["thread_id"])
    check("follow-up answered from documents", follow["status"] == "answered" and any("March 14" in c["text"] for c in follow["citations"]))
    fresh = client.post(f"/api/workspaces/{WS}/ask", json={"question": "Any receipts?", "thread_id": "unknown-thread"}).json()
    check("unknown thread starts a new one", fresh["thread_id"] not in (first["thread_id"], "unknown-thread"))

    history = client.get(f"/api/workspaces/{WS}/history").json()
    check("history newest first", history[0]["id"] == fresh["history_id"])
    check("history item shape", set(history[0]) == {"id", "question", "status", "answer_preview", "thread_id", "created_at", "saved"})
    detail = client.get(f"/api/workspaces/{WS}/history/{first['history_id']}").json()
    check("history detail has full response", set(detail) == {"question", "response", "thread_id", "created_at", "saved"} and detail["response"]["citations"])
    saved = client.patch(f"/api/workspaces/{WS}/history/{first['history_id']}", json={"saved": True}).json()
    check("save answer", saved["saved"] is True and saved["id"] == first["history_id"])
    check("unknown history 404", client.get(f"/api/workspaces/{WS}/history/nope").status_code == 404)

    stats = client.get(f"/api/workspaces/{WS}/knowledge").json()
    print("knowledge:", stats)
    check("knowledge shape", set(stats) == {"files", "ready_files", "pages", "passages", "notes", "folders", "last_indexed_at"})
    check("knowledge counts", stats["files"] == 2 and stats["ready_files"] == 2 and stats["passages"] == 4 and stats["pages"] == 3)

print("history checks passed")
