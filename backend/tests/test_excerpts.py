"""Citation excerpts: verbatim LLM spans are kept, anything else falls back to block text.

  cd backend && .venv/bin/python tests/test_excerpts.py   (no network: the LLM is faked)
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
os.environ.setdefault("OPENAI_COMPAT_KEY", "fake")
os.environ.setdefault("OPENAI_COMPAT_MODEL", "fake")
sys.path.insert(0, str(ROOT))

from app import answer, excerpts, llm, parsing, search, storage  # noqa: E402

FIXTURE = json.loads((ROOT / "tests" / "fixtures" / "blocks.json").read_text())
WS = "reyes-partners"
DEADLINE = "The Court grants the motion. Respondent shall file its Answer on or before March 14, 2026. No further extensions will be granted."


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        sys.exit(1)


# Unit: verbatim matching ignores whitespace and case, nothing else.
check("verbatim span found despite case/whitespace", excerpts.verbatim_span(DEADLINE, "file its answer   on or BEFORE march 14, 2026") == "file its Answer on or before March 14, 2026")
check("reworded span rejected", excerpts.verbatim_span(DEADLINE, "must file the Answer by 14 March 2026") is None)
check("too-short span rejected", excerpts.verbatim_span(DEADLINE, "Answer") is None)
receipt = "Official receipt No. 0412.\nFiling fee paid: PHP 3,500.00.\nReceived by the Office of the Clerk of Court, April 12, 2025."
check("best lines pick the overlapping line", excerpts.best_lines(receipt, "How much was the filing fee?") == "Filing fee paid: PHP 3,500.00.")

# Parser cleanup and tables, on a real-shaped MinerU table block.
table_md = "| Invoice # 0001 **** Date 05/01 | <!-- x --> TOTAL |\n| --- | --- |\n| ## Item A ** ** | 160.00 |"
check("table rows parsed, artifacts stripped", parsing._table_rows(table_md) == [["Invoice # 0001 Date 05/01", "TOTAL"], ["Item A", "160.00"]])
check("text keeps one line per row", parsing._clean_block(table_md) == "Invoice # 0001 Date 05/01 · TOTAL\nItem A · 160.00")

# Integration: /ask with a fake LLM.
storage.create_workspace("Reyes & Partners", "Law office", WS)
records = [{**f, "size_bytes": 1000, "status": "ready", "source": "upload", "path": "", "created_at": storage.now_iso()} for f in FIXTURE["files"]]
storage.save_file_records(WS, records)
for f in FIXTURE["files"]:
    storage.replace_file_blocks(WS, f["id"], [b for b in FIXTURE["blocks"] if b["file_id"] == f["id"]])
search.rebuild(WS)


def fake_llm(quote: str):
    def chat_json(system: str, user: str, max_tokens: int = 500) -> dict:
        if "keywords" in system:
            return {"keywords": ["deadline", "file", "answer", "March"]}
        # Cite whichever passage holds the deadline.
        bid = next(b for b, body in re.findall(r"\[(b\d+)\][^\n]*\n([^\n]*)", user) if "March 14, 2026" in body)
        return {"status": "answered", "answer": [{"text": "The Answer is due March 14, 2026.", "sources": [bid]}], "quotes": {bid: quote}}
    return chat_json


llm.chat_json = fake_llm("Respondent must file its Answer by 14 March 2026")  # reworded: not in the document
r = answer.ask(WS, "When is the deadline to file the Answer in the Santos case?")
check(f"fake answer accepted: {r.get('status')} {r.get('reason', '')}", r["status"] == "answered")
c = r["citations"][0]
print("fallback excerpt:", repr(c["excerpt"]))
check("non-verbatim span falls back to block text", c["excerpt"] != "Respondent must file its Answer by 14 March 2026")
check("fallback excerpt is literally in the block", c["excerpt"] in DEADLINE and "March 14, 2026" in c["excerpt"])
check("full text kept with line breaks", c["text"] == DEADLINE)

llm.chat_json = fake_llm("shall file its Answer on or before March 14, 2026")  # verbatim
r = answer.ask(WS, "By what date must the respondent file?")
check("verbatim span is used as the excerpt", r["citations"][0]["excerpt"] == "shall file its Answer on or before March 14, 2026")

print("excerpt checks passed")
