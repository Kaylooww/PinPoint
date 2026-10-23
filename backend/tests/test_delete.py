"""DELETE /api/workspaces/{ws}/files/{id}: removes an upload, its blocks, and our copies in
backend/data; refuses folder files; cancels a file that is queued or being read (a fake,
slow mineru is killed mid-parse). DELETE /api/workspaces/{ws}: removes the workspace and
all of its data. No real MinerU or network.

  cd backend && .venv/bin/python tests/test_delete.py
"""

import os
import stat
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PINPOINT_DATA_DIR"] = tempfile.mkdtemp(prefix="pinpoint-test-")
os.environ["EMBED_BASE"] = ""  # BM25 only, offline
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app import main, parsing, search, storage  # noqa: E402

WS = "reyes-partners"


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        sys.exit(1)


storage.create_workspace("Reyes & Partners", "Law office", WS)
keep = storage.add_upload(WS, "Lease.md", b"# Lease\n\nThe renter is Maria Santos.")
gone = storage.add_upload(WS, "Retainer.md", b"# Retainer\n\nThe monthly retainer is PHP 18,500.")
for record in (keep, gone):
    parsing._parse_job(WS, record["id"])
search.rebuild(WS)

# Leftovers a PDF would have: saved parse, decrypted copy, a crop, a rendered page.
parsed = storage.parsed_dir(WS)
parsed.mkdir(parents=True, exist_ok=True)
(parsed / f"{gone['id']}.json").write_text("{}")
(parsed / f"{gone['id']}.decrypted.pdf").write_bytes(b"%PDF")
(parsed / f"{keep['id']}.json").write_text("{}")
gone_block = next(b for b in storage.load_blocks(WS) if b["file_id"] == gone["id"])
(storage.crops_dir(WS) / "pages").mkdir(parents=True, exist_ok=True)
(storage.crops_dir(WS) / f"{gone_block['id']}.png").write_bytes(b"png")

folder = Path(tempfile.mkdtemp(prefix="pinpoint-folder-"))
original = folder / "Notes.md"
original.write_text("Folder note.")
in_folder = storage.add_folder_file(WS, "f1", str(original), original.stat().st_size, original.stat().st_mtime)
storage.update_file(WS, in_folder["id"], status="ready")
queued = storage.add_upload(WS, "Queued.md", b"Waiting.")

with TestClient(main.app) as client:
    url = f"/api/workspaces/{WS}/files"
    r = client.delete(f"{url}/{gone['id']}")
    check("delete an upload -> 200", r.status_code == 200 and r.json() == {"ok": True})
    ids = [f["id"] for f in client.get(url).json()]
    check("gone from the file list, other files stay", gone["id"] not in ids and keep["id"] in ids)
    check("its blocks are gone", not any(b["file_id"] == gone["id"] for b in storage.load_blocks(WS)))
    check("other blocks stay", any(b["file_id"] == keep["id"] for b in storage.load_blocks(WS)))
    check("upload copy removed", not Path(gone["path"]).exists() and Path(keep["path"]).exists())
    check("saved parse and decrypted copy removed", not list(parsed.glob(f"{gone['id']}.*")) and (parsed / f"{keep['id']}.json").exists())
    check("its crop removed", not (storage.crops_dir(WS) / f"{gone_block['id']}.png").exists())
    hits = search.search(WS, "monthly retainer PHP 18,500")
    check("no longer searchable", all(b["file_id"] != gone["id"] for b, _ in hits) and all(b["file_id"] != gone["id"] for b in search.get_index(WS).blocks))

    r = client.delete(f"{url}/{in_folder['id']}")
    check("folder file -> 409 with a message", r.status_code == 409 and "connected folder" in r.json()["detail"])
    check("folder original untouched", original.read_text() == "Folder note.")
    # Cancel a file mid-parse: a fake mineru that would take 30 s is killed.
    fake = Path(tempfile.mkdtemp(prefix="pinpoint-fake-")) / "mineru"
    fake.write_text("#!/bin/sh\nsleep 30\necho '{}'\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    parsing.mineru_bin = lambda: str(fake)
    scan = storage.add_upload(WS, "Scan.png", b"not really a png")
    job = threading.Thread(target=parsing._parse_job, args=(WS, scan["id"]))
    job.start()
    for _ in range(50):
        if parsing._proc is not None:
            break
        time.sleep(0.1)
    check("parse is running mineru", parsing._proc is not None and storage.list_files(WS)[0] is not None)
    started = time.monotonic()
    r = client.delete(f"{url}/{scan['id']}")
    job.join(timeout=10)
    check(f"cancel mid-parse -> 200, job stopped in {time.monotonic() - started:.1f}s", r.status_code == 200 and not job.is_alive())
    check("cancelled file gone, not marked failed", scan["id"] not in [f["id"] for f in client.get(url).json()])
    check("cancelled file left no blocks or upload", not any(b["file_id"] == scan["id"] for b in storage.load_blocks(WS)) and not Path(scan["path"]).exists())

    queued2 = storage.add_upload(WS, "Later.md", b"Queued behind another file.")
    r = client.delete(f"{url}/{queued2['id']}")
    parsing._parse_job(WS, queued2["id"])  # the queue reaching it later does nothing
    check("cancel a queued file -> 200, never parsed", r.status_code == 200 and not any(b["file_id"] == queued2["id"] for b in storage.load_blocks(WS)))
    check("unknown id -> 404", client.delete(f"{url}/does-not-exist").status_code == 404)
    check("path-like id -> 404", client.delete(f"{url}/..%2F..%2Fworkspace.json").status_code == 404)
    check("unknown workspace -> 404", client.delete(f"/api/workspaces/nope/files/{keep['id']}").status_code == 404)

    # Delete a workspace.
    other = client.post("/api/workspaces", json={"name": "Doomed Realty", "industry": "Real estate"}).json()
    doc = storage.add_upload(other["id"], "Deed.md", b"# Deed\n\nLot 7 belongs to Ana Cruz.")
    parsing._parse_job(other["id"], doc["id"])
    client.post(f"/api/workspaces/{other['id']}/ask", json={"question": "Who owns lot 7?"})
    folder_ws = Path(tempfile.mkdtemp(prefix="pinpoint-folder-"))
    (folder_ws / "Keep.md").write_text("The user's own file.")
    client.post(f"/api/workspaces/{other['id']}/folders", json={"path": str(folder_ws)})
    path = storage.ws_dir(other["id"])
    r = client.delete(f"/api/workspaces/{other['id']}")
    check("delete workspace -> 200", r.status_code == 200 and r.json() == {"ok": True})
    check("its folder in backend/data is gone", not path.exists())
    check("gone from the workspace list, others stay", [w["id"] for w in client.get("/api/workspaces").json()] == [WS])
    check("its files -> 404", client.get(f"/api/workspaces/{other['id']}/files").status_code == 404)
    check("connected folder's own files untouched", (folder_ws / "Keep.md").read_text() == "The user's own file.")
    time.sleep(1)  # a folder scan still running must not bring it back
    check("not recreated by background jobs", not path.exists())
    check("unknown workspace -> 404", client.delete("/api/workspaces/nope").status_code == 404)
    check("path-like workspace id -> 404", client.delete("/api/workspaces/..%2Fdata").status_code in (404, 405))
    again = client.post("/api/workspaces", json={"name": "Doomed Realty", "industry": "Real estate"}).json()
    check("same name again starts empty", again["file_count"] == 0 and client.get(f"/api/workspaces/{again['id']}/history").json() == [])

    client.delete(f"/api/workspaces/{WS}")
    storage.seed_demo_workspace()
    check("a deleted demo workspace isn't re-seeded while other workspaces exist", storage.workspace_ids() == [again["id"]])
    client.delete(f"/api/workspaces/{again['id']}")
storage.seed_demo_workspace()
check("with no workspaces left, a fresh start seeds the demo workspace", storage.workspace_ids() == [WS])
print("delete checks passed")
