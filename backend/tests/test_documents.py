"""Opening originals: GET .../files/{id}/raw and /text serve registered files only.

  cd backend && .venv/bin/python tests/test_documents.py   (no MinerU or LLM needed)
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PINPOINT_DATA_DIR"] = tempfile.mkdtemp(prefix="pinpoint-test-")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app import main, storage  # noqa: E402

WS = "reyes-partners"
MEMO = b"Memo\n\nThe hearing moved to June 2.\n"


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        sys.exit(1)


def wait_ready(client: TestClient) -> list[dict]:
    for _ in range(50):
        files = client.get(f"/api/workspaces/{WS}/files").json()
        if files and all(f["status"] in ("ready", "failed") for f in files):
            return files
        time.sleep(0.2)
    return files


with TestClient(main.app) as client:
    uploaded = client.post(f"/api/workspaces/{WS}/files", files=[("files", ("Memo.txt", MEMO))]).json()[0]
    wait_ready(client)
    raw = client.get(f"/api/workspaces/{WS}/files/{uploaded['id']}/raw")
    check("raw serves the uploaded original", raw.status_code == 200 and raw.content == MEMO)
    check("inline with the right media type", raw.headers["content-type"].startswith("text/plain") and raw.headers["content-disposition"].startswith("inline"))
    text = client.get(f"/api/workspaces/{WS}/files/{uploaded['id']}/text").json()
    check("text returns parsed pages", text["pages"][0]["page"] == 1 and "June 2" in text["pages"][0]["blocks"][-1]["text"])

    for bad in ["unknown123456", "..", "..%2F..%2Fetc%2Fpasswd", "%2Fetc%2Fpasswd", "..%5C..%5Cwindows", "a.b"]:
        for kind in ("raw", "text"):
            status = client.get(f"/api/workspaces/{WS}/files/{bad}/{kind}").status_code
            check(f"{kind} 404 for id {bad!r} (got {status})", status == 404)

    for bad in ["unknown123456", "..%2F..%2Fetc", uploaded["id"]]:  # last one: a .txt, not a PDF
        status = client.get(f"/api/workspaces/{WS}/files/{bad}/pages/1.png").status_code
        check(f"page image 404 for {bad!r} (got {status})", status == 404)
    text = client.get(f"/api/workspaces/{WS}/files/{uploaded['id']}/text").json()
    check("text has page_count and block locators", text["page_count"] == 1 and "locator" in text["pages"][0]["blocks"][0])

    # A record that points outside uploads/ (tampered files.json) is refused.
    records = storage.list_file_records(WS)
    records[0]["path"] = "/etc/hosts"
    storage.save_file_records(WS, records)
    check("record path outside uploads/ -> 404", client.get(f"/api/workspaces/{WS}/files/{uploaded['id']}/raw").status_code == 404)

    # Folder files are served only while inside a connected folder.
    folder_dir = Path(tempfile.mkdtemp(prefix="pinpoint-folder-"))
    (folder_dir / "Letter.md").write_text("# Letter\n\nRetainer is PHP 50,000.\n")
    folder = client.post(f"/api/workspaces/{WS}/folders", json={"path": str(folder_dir)}).json()
    for _ in range(50):
        if client.get(f"/api/workspaces/{WS}/folders").json()[0]["status"] == "ready":
            break
        time.sleep(0.2)
    letter = next(f for f in wait_ready(client) if f["name"] == "Letter.md")
    check("folder file served while connected", client.get(f"/api/workspaces/{WS}/files/{letter['id']}/raw").status_code == 200)
    folders = storage.list_folder_records(WS)
    folders[0]["path"] = str(Path(tempfile.mkdtemp(prefix="other-")).resolve())
    storage.save_folder_records(WS, folders)
    check("folder file outside its connected folder -> 404", client.get(f"/api/workspaces/{WS}/files/{letter['id']}/raw").status_code == 404)
    client.delete(f"/api/workspaces/{WS}/folders/{folder['id']}")
    check("disconnected folder file -> 404", client.get(f"/api/workspaces/{WS}/files/{letter['id']}/raw").status_code == 404)
    check("folder untouched on disk", (folder_dir / "Letter.md").exists())

print("document checks passed")
