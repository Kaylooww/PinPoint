"""Rebuild the "Reyes & Partners" demo workspace and wait until every file is ready.

Run with the MinerU server and the backend already running:
  cd backend && .venv/bin/python scripts/reset_demo.py [--api http://localhost:8000]

It deletes only backend/data/reyes-partners/ (files, blocks, notes, history, crops,
connected folders), recreates the workspace through the API, uploads every supported
file from backend/demo_files/ (or backend/samples/ if demo_files/ is missing or empty),
and polls until each file is ready. Exits 1 if any file fails or times out.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND / "data"
WS_ID, WS_NAME, WS_INDUSTRY = "reyes-partners", "Reyes & Partners", "Law office"
SUPPORTED = {"pdf", "png", "jpg", "jpeg", "webp", "docx", "xlsx", "pptx", "csv", "md", "txt"}


def demo_files() -> tuple[Path, list[Path]]:
    for folder in (BACKEND / "demo_files", BACKEND / "samples"):
        files = sorted(
            p
            for p in folder.glob("*")
            if p.is_file() and not p.name.startswith(".") and p.suffix.lower().lstrip(".") in SUPPORTED
        )
        if files:
            return folder, files
    sys.exit("No demo files: put them in backend/demo_files/ (or backend/samples/).")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8000", help="backend base URL")
    parser.add_argument("--timeout", type=int, default=900, help="seconds to wait for parsing")
    args = parser.parse_args()
    api = args.api.rstrip("/")

    folder, files = demo_files()
    if folder.name != "demo_files":
        print(f"backend/demo_files/ is missing or empty: using backend/{folder.name}/ instead.")
    print(f"Demo files ({len(files)}): {', '.join(p.name for p in files)}")

    with httpx.Client(base_url=api, timeout=120) as client:
        try:
            health = client.get("/api/health").json()
        except httpx.HTTPError:
            print(f"The backend isn't reachable at {api}. Start it first (see docs/DEMO.md).")
            return 1
        parse_ok = health.get("mineru", {}).get("status", {}).get("parse_server", {}).get("local", {}).get("healthy")
        print(f"Health: llm ok={health['llm'].get('ok')} ({health['llm'].get('provider')}), MinerU parse server healthy={parse_ok}")
        if not parse_ok:
            print("MinerU's parse server isn't healthy. Run: mineru server start, then check mineru server status --json")
            return 1

        target = DATA_DIR / WS_ID
        if target.exists():
            shutil.rmtree(target)
            print(f"Removed {target.relative_to(BACKEND)}/")
        created = client.post("/api/workspaces", json={"name": WS_NAME, "industry": WS_INDUSTRY})
        created.raise_for_status()
        if created.json()["id"] != WS_ID:
            print(f"Unexpected workspace id {created.json()['id']!r}; is another 'Reyes & Partners' folder in backend/data?")
            return 1

        uploads = [("files", (p.name, p.read_bytes())) for p in files]
        client.post(f"/api/workspaces/{WS_ID}/files", files=uploads).raise_for_status()
        print("Uploaded. Waiting for parsing…")

        started, last = time.monotonic(), ""
        while True:
            items = client.get(f"/api/workspaces/{WS_ID}/files").json()
            summary = ", ".join(f"{f['name']}: {f['status']}" for f in items)
            if summary != last:
                print(f"  [{round(time.monotonic() - started):>3}s] {summary}")
                last = summary
            if all(f["status"] in ("ready", "failed") for f in items):
                break
            if time.monotonic() - started > args.timeout:
                print(f"Timed out after {args.timeout}s.")
                return 1
            time.sleep(2)

    failed = [f for f in items if f["status"] == "failed"]
    for f in failed:
        print(f"FAILED  {f['name']}: {f.get('error')}")
    pages = sum(f["pages"] for f in items if f["status"] == "ready")
    print(f"{'Done' if not failed else 'Finished with failures'}: {len(items) - len(failed)}/{len(items)} files ready, {pages} pages.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
