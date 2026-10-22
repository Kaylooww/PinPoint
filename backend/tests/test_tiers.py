"""MinerU tier choice: flash for digital PDFs and Office files, basic for scans and photos,
and a fallback to basic when flash fails. No MinerU needed (parse_file is faked).

  cd backend && .venv/bin/python tests/test_tiers.py
"""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PINPOINT_DATA_DIR"] = tempfile.mkdtemp(prefix="pinpoint-test-")
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from app import parsing, storage  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="pinpoint-tiers-"))


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        sys.exit(1)


def text_pdf(path: Path, pages: int, line: str) -> None:
    """A minimal PDF with a real text layer (Helvetica), no PDF library needed."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for _ in range(pages):
        stream = "BT /F1 9 Tf 40 800 Td " + " ".join(f"({line}) Tj 0 -11 Td" for _ in range(30)) + " ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {len(objects)} 0 R >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {pages} >>"
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(out)


digital = TMP / "Rules.pdf"
text_pdf(digital, 4, "Section 1. The defendant shall file an answer within fifteen days.")
scanned = TMP / "Scan.pdf"
Image.new("RGB", (600, 800), (250, 250, 248)).save(scanned, "PDF")
photo = TMP / "Photo.jpg"
Image.new("RGB", (300, 400), (240, 240, 230)).save(photo, "JPEG")
broken = TMP / "Broken.pdf"
broken.write_bytes(b"not a pdf")

check("digital PDF -> flash, page count from pypdf", parsing.choose_tier(str(digital)) == ("flash", 4))
check("scanned (image-only) PDF -> basic", parsing.choose_tier(str(scanned))[0] == "basic")
check("photo -> basic", parsing.choose_tier(str(photo)) == ("basic", 0))
check("Office file -> flash", parsing.choose_tier("Engagement.docx") == ("flash", 0) and parsing.choose_tier("Ledger.xlsx")[0] == "flash")
check("unreadable PDF -> basic (let MinerU OCR it)", parsing.choose_tier(str(broken))[0] == "basic")

# The parse job records the tier, and falls back to basic when flash fails.
WS = "reyes-partners"
storage.create_workspace("Reyes & Partners", "Law office", WS)
raw = {"content": {"short_id": "abc1234", "tier": "flash", "sha256": "", "content": "<!-- page 1 of 1 -->\n\nSection 1. The defendant shall file an answer within fifteen days."}}
tiers_called: list[str] = []


def fake_parse(path: str, tier: str = "basic") -> dict:
    tiers_called.append(tier)
    if tier == "flash" and "fail" in path:
        raise parsing.ParseError("flash tier unavailable")
    return {**raw, "content": {**raw["content"], "tier": tier}}


parsing.parse_file = fake_parse
for name, src in [("Rules.pdf", digital), ("fail-Rules.pdf", digital)]:
    record = storage.add_upload(WS, name, src.read_bytes())
    if "fail" in name:  # make the stored path carry the marker the fake looks for
        records = storage.list_file_records(WS)
        new = Path(record["path"]).with_name("fail-" + Path(record["path"]).name)
        Path(record["path"]).rename(new)
        for r in records:
            if r["id"] == record["id"]:
                r["path"] = str(new)
        storage.save_file_records(WS, records)
    parsing._parse_job(WS, record["id"])

records = {r["name"]: r for r in storage.list_file_records(WS)}
check("digital PDF parsed on flash and recorded", records["Rules.pdf"]["status"] == "ready" and records["Rules.pdf"]["tier"] == "flash")
check("parse time recorded", isinstance(records["Rules.pdf"].get("parse_seconds"), float))
check("flash failure falls back to basic", tiers_called[-2:] == ["flash", "basic"] and records["fail-Rules.pdf"]["tier"] == "basic" and records["fail-Rules.pdf"]["status"] == "ready")
blocks = storage.load_blocks(WS)
check("locators carry the tier used", any("/tier:flash/" in b["locator"] for b in blocks) and any("/tier:basic/" in b["locator"] for b in blocks))
print("tier checks passed")
