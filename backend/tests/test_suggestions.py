"""'Did you mean…?' on not_found: near matches, and suggestions validated against them.

  cd backend && .venv/bin/python tests/test_suggestions.py [--offline]

Offline: a fake LLM returns not_found with (1) a valid suggestion, kept, and (2) one whose
date isn't in the blocks, dropped while the near matches stay. Live: "the invoice from
August 15" on Villanueva Accounting suggests the invoice dated April 15, 2026.
"""

import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PINPOINT_DATA_DIR"] = tempfile.mkdtemp(prefix="pinpoint-test-")
os.environ["LLM_PROVIDER"] = "openai_compatible"
os.environ.setdefault("OPENAI_COMPAT_BASE", "http://fake.invalid/api")
os.environ.setdefault("OPENAI_COMPAT_MODEL", "fake")
os.environ["EMBED_BASE"] = ""  # BM25 only, offline
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


def fake(suggestion_text: str, suggestion_question: str):
    def chat_json(system: str, user: str, max_tokens: int = 500) -> dict:
        if "keywords" in system:
            return {"keywords": ["receipt", "fee", "filing"]}
        receipt = next(b for b, body in re.findall(r"\[(b\d+)\][^\n]*\n([^\n]*)", user) if "receipt" in body.lower())
        return {
            "status": "not_found",
            "answer": [],
            "reason": "There is no receipt dated August 12, 2025.",
            "suggestion": {"text": suggestion_text, "question": suggestion_question, "sources": [receipt]},
        }
    return chat_json


# Unit: the validator itself.
blocks = [b for b in FIXTURE["blocks"] if b["file_id"] == "fx-receipt"]
check("valid suggestion kept", answer.validate_suggestion({"text": "Did you mean the receipt dated April 12, 2025?", "question": "What was paid on April 12, 2025?"}, blocks) is not None)
check("invented date dropped", answer.validate_suggestion({"text": "Did you mean August 12, 2025?", "question": "What was paid on August 12, 2025?"}, blocks) is None)
check("invented amount dropped", answer.validate_suggestion({"text": "Did you mean the PHP 4,500.00 fee?", "question": "Who paid PHP 4,500.00?"}, blocks) is None)

# (1) not_found with a valid suggestion.
llm.chat_json = fake("Did you mean the receipt dated April 12, 2025?", "How much was the filing fee on the receipt dated April 12, 2025?")
r = answer.ask(WS, "How much was the filing fee on the receipt from August 12?")
check("status stays not_found", r["status"] == "not_found" and r["answer"] == [] and r["citations"] == [])
check(f"near matches returned ({len(r['near_matches'])})", 1 <= len(r["near_matches"]) <= 3)
check("receipt is the first near match", "receipt" in r["near_matches"][0]["text"].lower())
check("near matches are full citations", {"id", "number", "kind", "file_id", "file_name", "page", "locator", "text", "excerpt", "crop_url"} <= set(r["near_matches"][0]))
check("valid suggestion kept", r.get("suggestion") == {"text": "Did you mean the receipt dated April 12, 2025?", "question": "How much was the filing fee on the receipt dated April 12, 2025?"})

# (2) the LLM invents a date that isn't in the blocks: suggestion dropped, near matches kept.
llm.chat_json = fake("Did you mean the receipt dated August 21, 2025?", "How much was the fee on August 21, 2025?")
r = answer.ask(WS, "What was the filing fee on the receipt from August 2025?")
check("invented-date suggestion dropped", "suggestion" not in r)
check("near matches still shown", len(r["near_matches"]) >= 1 and r["status"] == "not_found")

if "--offline" in sys.argv:
    print("suggestion checks passed (offline)")
    sys.exit(0)

# Live: Villanueva invoice dated April 15, 2026, asked about "August 15".
live = httpx.post(
    "http://localhost:8000/api/workspaces/villanueva-accounting/ask",
    json={"question": "How much is the total of the invoice from August 15?"},
    timeout=120,
).json()
print("   reason:", live.get("reason"))
print("   suggestion:", live.get("suggestion"))
print("   near matches:", [(c["file_name"], c["excerpt"][:50]) for c in live.get("near_matches", [])])
check("live: not_found (never answers the mismatched question)", live["status"] == "not_found" and live["answer"] == [])
check("live: near matches include the invoice", any(c["file_name"].startswith("Sales_Invoice") for c in live["near_matches"]))
check("live: suggestion mentions April 15, 2026", "April 15" in (live.get("suggestion") or {}).get("text", ""))
print("suggestion checks passed")
