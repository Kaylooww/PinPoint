"""Re-extract blocks for every ready file from its saved parse (no MinerU calls).

  cd backend && .venv/bin/python scripts/rebuild_blocks.py

Use after changing block extraction (e.g. heading breadcrumbs). File ids are kept; a file
whose saved parse is missing keeps its current blocks. Each blocks.json is backed up to
blocks.json.bak first. Restart the backend afterwards (or touch app/main.py under --reload):
it rebuilds the search indexes on startup and fills in the embeddings in the background.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import parsing, storage  # noqa: E402


def main() -> int:
    for ws in storage.workspace_ids():
        path = storage.ws_dir(ws) / "blocks.json"
        if path.exists():
            shutil.copyfile(path, path.with_name("blocks.json.bak"))
        old = storage.load_blocks(ws)
        rebuilt: list[dict] = []
        for record in storage.list_file_records(ws):
            if record["status"] != "ready":
                rebuilt += [b for b in old if b["file_id"] == record["id"]]
                continue
            try:
                if record["name"].rsplit(".", 1)[-1].lower() in parsing.TEXT_EXTENSIONS:
                    blocks, _ = parsing.text_file_blocks(record["path"], record["id"], record["name"])
                else:
                    raw = json.loads((storage.parsed_dir(ws) / f"{record['id']}.json").read_text(encoding="utf-8"))
                    blocks, _ = parsing.extract_blocks(raw, record["id"], record["name"])
            except (OSError, ValueError, parsing.ParseError) as e:
                print(f"  {ws}: kept old blocks for {record['name']} ({type(e).__name__})")
                blocks = [b for b in old if b["file_id"] == record["id"]]
            rebuilt += blocks
        with storage.lock(ws):
            storage._write_json(path, rebuilt)
        with_path = sum(1 for b in rebuilt if b.get("path"))
        print(f"{ws}: {len(old)} -> {len(rebuilt)} blocks, {with_path} with a heading path")
    return 0


if __name__ == "__main__":
    sys.exit(main())
