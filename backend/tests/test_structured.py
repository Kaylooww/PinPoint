"""Structured answers: item kinds, markdown cleanup, and citation rules per item.

  cd backend && .venv/bin/python tests/test_structured.py   (no network)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import answer  # noqa: E402


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        sys.exit(1)


by_id = {"b1": {"id": "x1"}, "b2": {"id": "x2"}}


def run(items: list[dict]) -> list[tuple[str, list[str], str]]:
    return [(t, [b["id"] for b in blocks], k) for t, blocks, k in answer.validate_items({"status": "answered", "answer": items}, by_id)]


out = run([
    {"kind": "paragraph", "text": "**Six** kinds of bills.", "sources": ["b1"]},
    {"kind": "heading", "text": "## Money bills", "sources": []},
    {"kind": "bullet", "text": "- Appropriation bills", "sources": ["b2"]},
    {"kind": "bullet", "text": "Invented", "sources": ["b9"]},
    {"kind": "numbered", "text": "1. File the notice", "sources": ["b1"]},
    {"kind": "heading", "text": "Orphan", "sources": []},
])
check("markdown stripped from text", [t for t, _, _ in out] == ["Six kinds of bills.", "Money bills", "Appropriation bills", "File the notice"])
check("kinds kept", [k for _, _, k in out] == ["paragraph", "heading", "bullet", "numbered"])
check("uncited bullet dropped (citation rule unchanged)", "Invented" not in [t for t, _, _ in out])
check("heading may have no sources", out[1] == ("Money bills", [], "heading"))
check("trailing heading with nothing after it dropped", "Orphan" not in [t for t, _, _ in out])
check("headings alone are no answer", run([{"kind": "heading", "text": "Bills", "sources": ["b1"]}]) == [])
check("uncited paragraph alone is no answer", run([{"kind": "paragraph", "text": "Guess", "sources": []}]) == [])
check("missing or unknown kind -> paragraph", [k for _, _, k in run([{"text": "A", "sources": ["b1"]}, {"kind": "table", "text": "B", "sources": ["b2"]}])] == ["paragraph", "paragraph"])
check("over-long heading demoted to a cited paragraph", run([{"kind": "heading", "text": "This heading is far too long to be a heading at all", "sources": ["b1"]}])[0][2] == "paragraph")
check("not_found replies yield nothing", answer.validate_items({"status": "not_found", "answer": [{"text": "x", "sources": ["b1"]}]}, by_id) == [])
print("structured answer checks passed")
