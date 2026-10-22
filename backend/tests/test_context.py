"""Context expansion: a letter's separate date block reaches the LLM.

  cd backend && .venv/bin/python tests/test_context.py [--offline]

(a) offline unit test on a fixture letter; (b) live: the real Villanueva engagement letter
answers "When was this letter sent?" with March 2, 2026, citing the date block.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from app import answer  # noqa: E402


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        sys.exit(1)


def block(file_id: str, page: int, m: int, text: str) -> dict:
    return {"id": f"{file_id}-p{page}-b{m}", "file_id": file_id, "file_name": f"{file_id}.pdf", "page": page,
            "locator": f"doc:x/tier:basic/page:{page}/block:{m}", "text": text}


letter = [
    block("letter", 1, 1, "VILLANUEVA ACCOUNTING Certified Public Accountants"),
    block("letter", 1, 2, "March 2, 2026"),
    block("letter", 1, 3, "Ms. Lorna Dizon, Owner, Bayview Bakery Co."),
    block("letter", 1, 4, "ENGAGEMENT LETTER FOR ACCOUNTING AND TAX SERVICES"),
    block("letter", 1, 5, "This letter confirms that we will provide monthly bookkeeping."),
    block("letter", 1, 6, "Fees. Our monthly retainer is PHP 18,500."),
    block("letter", 1, 7, "Client responsibilities. Records by the 5th."),
    block("letter", 2, 1, "Term. This engagement starts on March 1, 2026."),
    block("letter", 2, 2, "Confidentiality. We keep all client records confidential."),
]
other = [block("memo", 1, m, f"Memo paragraph {m}") for m in range(1, 8)]
everything = letter + other

# (a) "When was this letter sent?" retrieves the body paragraph, not the date line.
ctx = answer.expand_context(everything, [letter[4]])
ids = [b["id"] for b in ctx]
check("date block is in the context", "letter-p1-b2" in ids)
check("neighbours ±1 included", {"letter-p1-b4", "letter-p1-b6"} <= set(ids))
check("first 3 blocks of page 1 included", {"letter-p1-b1", "letter-p1-b2", "letter-p1-b3"} <= set(ids))
check("document order within the file", ids == sorted(ids, key=lambda i: (int(i.split("-p")[1].split("-b")[0]), int(i.split("-b")[1]))))
check("no duplicates", len(ids) == len(set(ids)))

# Page-2 hit still pulls the letter's page-1 header (date).
ctx = answer.expand_context(everything, [letter[7]])
check("page-2 hit includes page-1 date", "letter-p1-b2" in [b["id"] for b in ctx])

# Cap at 12, and retrieved blocks are never dropped by it.
many_hits = [letter[5], letter[8], *other[2:6]]
ctx = answer.expand_context(everything, many_hits)
check(f"capped at 12 (got {len(ctx)})", len(ctx) <= 12)
check("all retrieved blocks kept under the cap", {b["id"] for b in many_hits} <= {b["id"] for b in ctx})
check("files stay grouped", [b["file_id"] for b in ctx] == sorted([b["file_id"] for b in ctx], key=[b["file_id"] for b in ctx].index))

# Notes have no neighbours and pass through untouched.
note = {"id": "note-abc", "kind": "note", "file_id": "abc", "file_name": "Note", "page": 1, "locator": "note:abc", "text": "Prefers email."}
check("notes pass through", [b["id"] for b in answer.expand_context(everything + [note], [note])] == ["note-abc"])

if "--offline" in sys.argv:
    print("context checks passed (offline)")
    sys.exit(0)

# (b) live, real Villanueva letter.
r = httpx.post(
    "http://localhost:8000/api/workspaces/villanueva-accounting/ask", json={"question": "When was this letter sent?"}, timeout=120
).json()
print("   answer:", " ".join(s["text"] for s in r["answer"]) or r.get("reason"))
check("live: answered with March 2, 2026", r["status"] == "answered" and "March 2, 2026" in " ".join(s["text"] for s in r["answer"]))
check(
    "live: cites the date block",
    any(c["text"].strip() == "March 2, 2026" and c["file_name"].startswith("Engagement_Letter") for c in r["citations"]),
)
print("context checks passed")
