"""Encrypted and long PDFs: a decrypted working copy for owner-restricted PDFs, a clear
failure for password-protected ones, 20-page chunks with absolute page numbers, one retry
then skip for a failing chunk, and HTML tables turned into rows. No MinerU needed.

  cd backend && .venv/bin/python tests/test_encrypted.py
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PINPOINT_DATA_DIR"] = tempfile.mkdtemp(prefix="pinpoint-test-")
os.environ["EMBED_BASE"] = ""  # BM25 only, offline
sys.path.insert(0, str(ROOT))

from pypdf import PdfReader, PdfWriter  # noqa: E402

from app import parsing, storage  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="pinpoint-enc-"))
WS = "din-yutas"


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


def encrypted(src: Path, dest: Path, user_password: str) -> None:
    writer = PdfWriter(clone_from=PdfReader(str(src)))
    writer.encrypt(user_password=user_password, owner_password="owner-secret", permissions_flag=0, algorithm="AES-256")
    writer.write(str(dest))


storage.create_workspace("Din Yutas", "Accounting", WS)
plain = TMP / "Plain.pdf"
text_pdf(plain, 3, "Total assets as of December 31, 2024 were 206,879,651.")
restricted = TMP / "Restricted.pdf"
encrypted(plain, restricted, "")
locked = TMP / "Locked.pdf"
encrypted(plain, locked, "open-sesame")

# Owner restrictions only: a decrypted copy in parsed/, the original untouched.
before = restricted.read_bytes()
copy = parsing.prepare_pdf(WS, "f1", str(restricted))
check("owner-restricted PDF -> decrypted copy in parsed/", copy == str(storage.parsed_dir(WS) / "f1.decrypted.pdf"))
check("copy opens unencrypted with the same page count", not PdfReader(copy).is_encrypted and len(PdfReader(copy).pages) == 3)
check("original file unchanged", restricted.read_bytes() == before)
check("plain PDF parsed in place", parsing.prepare_pdf(WS, "f2", str(plain)) == str(plain))
try:
    parsing.prepare_pdf(WS, "f3", str(locked))
    check("password-protected PDF raises", False)
except parsing.ParseError as e:
    check("password-protected PDF -> the unlock message", str(e) == parsing.PASSWORD_MESSAGE)

# The parse job: a locked file fails with the message, shown as-is.
record = storage.add_upload(WS, "Locked.pdf", locked.read_bytes())
parsing._parse_job(WS, record["id"])
r = next(r for r in storage.list_file_records(WS) if r["id"] == record["id"])
check("locked upload -> failed with the unlock message", r["status"] == "failed" and r["error"] == parsing.PASSWORD_MESSAGE)

# Long PDF: 45 pages -> chunks 1-20, 21-40, 41-45. Chunk 21-40 fails twice and is skipped.
long_pdf = TMP / "Long.pdf"
text_pdf(long_pdf, 45, "Net income for 2024 was 4,635,736.")
calls: list[tuple[str, str]] = []
labels: list[str] = []


def fake_parse(path: str, tier: str = "basic", pages: str = "all") -> dict:
    calls.append((tier, pages))
    start, end = (int(p) for p in pages.split("-"))
    if start == 21:
        raise parsing.ParseError("chunk timed out")
    content = "\n\n".join(f"<!-- page {p} of 45 -->\n\nPage {p} says net income was 4,635,736." for p in range(start, end + 1))
    return {"content": {"short_id": "abc1234", "tier": tier, "sha256": "", "content": content}}


real_progress = parsing._progress


def spy_progress(ws: str, file_id: str, **changes) -> None:
    if changes.get("progress_label"):
        labels.append(changes["progress_label"])
    real_progress(ws, file_id, **changes)


parsing.parse_file = fake_parse
parsing._progress = spy_progress
record = storage.add_upload(WS, "Long.pdf", long_pdf.read_bytes())
parsing._parse_job(WS, record["id"])
r = next(r for r in storage.list_file_records(WS) if r["id"] == record["id"])
blocks = [b for b in storage.load_blocks(WS) if b["file_id"] == record["id"]]
pages = sorted({b["page"] for b in blocks})
check("long PDF still becomes ready", r["status"] == "ready")
check("progress labels per chunk", {"Reading pages 1–20 of 45", "Reading pages 21–40 of 45", "Reading pages 41–45 of 45"} <= set(labels))
check("failing chunk tried twice, then skipped", [c for c in calls if c[1] == "21-40"] == [("flash", "21-40"), ("basic", "21-40")])
check("skip note on the file", r["error"] == "Pages 21–40 couldn't be read.")
check("absolute page numbers kept", pages == list(range(1, 21)) + list(range(41, 46)))
check("locators carry real page numbers", any("/page:45/" in b["locator"] for b in blocks))

# HTML tables (MinerU basic tier) -> one row per line, no markup.
raw = {"content": {"short_id": "x", "tier": "basic", "sha256": "", "content": (
    "<!-- page 7 of 7 -->\n\nCONSOLIDATED STATEMENTS OF FINANCIAL POSITION\n\n"
    "<table><tr><td></td><td>2024</td><td>2023</td></tr><tr><td>TOTAL ASSETS</td><td>P=206,879,651</td><td>P=204,476,077</td></tr></table>"
)}}
table_blocks, _ = parsing.extract_saved(raw, "t1", "FS.pdf")
table = next(b for b in table_blocks if "TOTAL ASSETS" in b["text"])
check("HTML table rows readable", "TOTAL ASSETS · P=206,879,651 · P=204,476,077" in table["text"].splitlines())
check("no HTML left in the block", "<td" not in table["text"] and "table" in table)
print("encrypted/long PDF checks passed")
