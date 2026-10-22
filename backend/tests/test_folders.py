"""Connected folders: safety limits, rescan, disconnect, and that the folder is never modified.

  cd backend && .venv/bin/python tests/test_folders.py   (needs the MinerU server for the .jpg)
"""
import os, shutil, sys, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PINPOINT_DATA_DIR"] = tempfile.mkdtemp(prefix="pinpoint-test-")
sys.path.insert(0, str(ROOT))
from fastapi.testclient import TestClient  # noqa: E402
from app import main  # noqa: E402

# A client folder that trips every safety rule: hidden file and folder, node_modules,
# a symlink, an unsupported extension, an empty file, and nesting deeper than 5 levels.
F = tempfile.mkdtemp(prefix="pinpoint-folder-")
for d in ("sub/.hidden", "node_modules", "a/b/c/d/e/f"):
    os.makedirs(os.path.join(F, d))
receipt = next((ROOT / "samples").glob("*.jpg"), None)
if receipt:
    shutil.copy(receipt, os.path.join(F, "receipt.jpg"))
files = {
    "sub/engagement.md": "# Engagement letter\n\nThe retainer for Reyes & Partners is PHP 50,000 per month, billed on the 5th.\n",
    "notes.txt": "Meeting notes: client meeting moved to Friday 3 PM.\n",
    ".env": "secret", "sub/.hidden/h.txt": "x", "node_modules/n.txt": "x", "a/b/c/d/e/f/deep.txt": "x", "tool.exe": "x", "empty.txt": "",
}
for rel, text in files.items():
    Path(F, rel).write_text(text)
os.symlink("/etc/hosts", os.path.join(F, "link.txt"))
EXPECTED = sorted(["engagement.md", "notes.txt"] + (["receipt.jpg"] if receipt else []))
WS = "reyes-partners"
def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)
    if not cond: sys.exit(1)
with TestClient(main.app) as c:
    for bad, why in [("relative/path", "relative"), ("/does/not/exist", "missing"), (F + "/notes.txt", "file"), (os.path.expanduser("~"), "home"), ("/", "root")]:
        r = c.post(f"/api/workspaces/{WS}/folders", json={"path": bad}); check(f"reject {why}: {r.json().get('detail')}", r.status_code == 400)
    folder = c.post(f"/api/workspaces/{WS}/folders", json={"path": F}).json()
    check("folder shape", set(folder) == {"id", "path", "file_count", "status", "last_scanned_at"} and folder["status"] == "scanning")
    check("duplicate rejected", c.post(f"/api/workspaces/{WS}/folders", json={"path": F}).status_code == 400)
    for _ in range(120):
        files = c.get(f"/api/workspaces/{WS}/files").json()
        if files and all(f["status"] in ("ready", "failed") for f in files): break
        time.sleep(2)
    names = sorted(f["name"] for f in files)
    print("files:", [(f["name"], f["status"], f.get("error")) for f in files])
    check("only supported, visible, shallow, non-symlink files", names == EXPECTED)
    check("folder file shape", all(f["source"] == "folder" and f["source_path"].startswith(F) for f in files))
    fl = c.get(f"/api/workspaces/{WS}/folders").json()[0]
    check(f"folder ready with 3 files: {fl}", fl["status"] == "ready" and fl["file_count"] == len(EXPECTED) and fl["last_scanned_at"])
    os.remove(F + "/notes.txt"); open(F + "/new.txt", "w").write("New memo: the hearing was moved to June 2.\n")
    c.post(f"/api/workspaces/{WS}/folders/{fl['id']}/rescan")
    for _ in range(60):
        files = c.get(f"/api/workspaces/{WS}/files").json()
        if c.get(f"/api/workspaces/{WS}/folders").json()[0]["status"] == "ready" and all(f["status"] in ("ready","failed") for f in files): break
        time.sleep(2)
    check("rescan: deleted removed, new added", sorted(f["name"] for f in files) == sorted(set(EXPECTED) - {"notes.txt"} | {"new.txt"}))
    check("disconnect", c.delete(f"/api/workspaces/{WS}/folders/{fl['id']}").json() == {"ok": True})
    check("files gone from index", c.get(f"/api/workspaces/{WS}/files").json() == [])
    check("folder still on disk", os.path.exists(F + "/sub/engagement.md") and os.path.exists(F + "/new.txt"))
print("folder checks passed")
