"""Generate the fictional "Villanueva Accounting" demo documents.

  cd backend && .venv/bin/python scripts/make_demo_files.py

Everything here is invented (the repo is public): the firm, its client, people, TINs,
invoice numbers, and amounts. Writes backend/demo_files/villanueva-accounting/:
  Engagement_Letter_Bayview_Bakery.pdf   scanned-style letter (image PDF, 2 pages)
  Sales_Invoice_VA-2026-0187.pdf         BIR-style invoice (image PDF)
  Expense_Report_Q1_2026.csv             spreadsheet
  Receipt_Northwind_Stationers.jpg       phone photo of a paper receipt
  Memo_Year_End_Close.txt                short internal memo

Facts the demo questions rely on (keep docs/DEMO.md in sync if you change them):
  retainer PHP 18,500/month, billed on the 10th; invoice VA-2026-0187 VAT PHP 2,640.00
  (total PHP 24,640.00), due 2026-05-15; February travel PHP 6,450.00; receipt total
  PHP 1,236.50; year-end close deadline January 15, 2027.
"""

from __future__ import annotations

import random
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent.parent / "demo_files" / "villanueva-accounting"
PAGE = (1240, 1754)  # A4 at 150 dpi
INK, PAPER = (28, 28, 30), (252, 251, 248)
MARGIN = 120


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


class Page:
    """A simple top-to-bottom text page."""

    def __init__(self) -> None:
        self.img = Image.new("RGB", PAGE, PAPER)
        self.draw = ImageDraw.Draw(self.img)
        self.y = MARGIN

    def text(self, s: str, size: int = 26, gap: int = 14, indent: int = 0, width: int = 74) -> None:
        for line in textwrap.wrap(s, width=width) or [""]:
            self.draw.text((MARGIN + indent, self.y), line, font=font(size), fill=INK)
            self.y += size + 10
        self.y += gap

    def rule(self, gap: int = 20) -> None:
        self.draw.line((MARGIN, self.y, PAGE[0] - MARGIN, self.y), fill=(150, 150, 150), width=2)
        self.y += gap

    def row(self, cells: list[str], xs: list[int], size: int = 24, gap: int = 12) -> None:
        for cell, x in zip(cells, xs):
            self.draw.text((MARGIN + x, self.y), cell, font=font(size), fill=INK)
        self.y += size + gap


def scanned(img: Image.Image, angle: float) -> Image.Image:
    """Slight tilt, blur, and grain, like a quick office scan."""
    rnd = random.Random(7)
    out = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=PAPER)
    px = out.load()
    for _ in range(9000):
        x, y = rnd.randrange(out.width), rnd.randrange(out.height)
        v = rnd.randrange(200, 245)
        px[x, y] = (v, v, v - 4)
    return out.filter(ImageFilter.GaussianBlur(0.6))


def engagement_letter() -> None:
    p1 = Page()
    p1.text("VILLANUEVA ACCOUNTING", 40, 4)
    p1.text("Certified Public Accountants · 4F Mabini Building, Iloilo City", 22, 6)
    p1.rule(40)
    p1.text("March 2, 2026", 26)
    p1.text("Ms. Lorna Dizon, Owner", 26, 2)
    p1.text("Bayview Bakery Co.", 26, 2)
    p1.text("Diversion Road, Iloilo City", 26, 30)
    p1.text("ENGAGEMENT LETTER FOR ACCOUNTING AND TAX SERVICES", 30, 24)
    p1.text(
        "This letter confirms that Villanueva Accounting will provide monthly bookkeeping, "
        "quarterly VAT and income tax filing, and year-end financial statements for Bayview "
        "Bakery Co. for calendar year 2026."
    )
    p1.text(
        "Fees. Our monthly retainer is PHP 18,500, billed on the 10th of each month and payable "
        "within 15 days. Audit support and BIR examinations are billed separately at PHP 2,200 per hour."
    )
    p1.text(
        "Client responsibilities. The client will send sales and expense records by the 5th of "
        "the following month and keep original receipts for at least ten years."
    )
    p2 = Page()
    p2.text(
        "Term. This engagement starts on March 1, 2026 and renews each year unless either party "
        "gives 30 days written notice."
    )
    p2.text(
        "Confidentiality. We keep all client records confidential and use them only to provide "
        "the services in this letter."
    )
    p2.text("Agreed and accepted:", 26, 40)
    p2.row(["Ramon Villanueva, CPA", "Lorna Dizon"], [0, 560], 26)
    p2.row(["Managing Partner", "Owner, Bayview Bakery Co."], [0, 560], 22)
    pages = [scanned(p1.img, 0.4), scanned(p2.img, -0.3)]
    pages[0].save(OUT / "Engagement_Letter_Bayview_Bakery.pdf", "PDF", resolution=150, save_all=True, append_images=pages[1:])


def invoice() -> None:
    p = Page()
    p.text("VILLANUEVA ACCOUNTING", 38, 4)
    p.text("VAT Reg. TIN 123-456-789-000 · 4F Mabini Building, Iloilo City", 22, 20)
    p.text("SALES INVOICE  No. VA-2026-0187", 32, 10)
    p.row(["Date: April 15, 2026", "Due date: May 15, 2026"], [0, 560], 24, 20)
    p.text("Billed to: Bayview Bakery Co., Diversion Road, Iloilo City · TIN 987-654-321-000", 24, 24)
    p.rule()
    xs = [0, 640, 860]
    p.row(["Description", "Qty", "Amount (PHP)"], xs, 24, 18)
    p.rule()
    p.row(["Monthly bookkeeping, April 2026", "1", "18,500.00"], xs)
    p.row(["Q1 VAT return preparation (BIR 2550Q)", "1", "3,500.00"], xs)
    p.rule()
    p.row(["Vatable sales", "", "22,000.00"], xs)
    p.row(["VAT (12%)", "", "2,640.00"], xs)
    p.row(["TOTAL AMOUNT DUE", "", "24,640.00"], xs, 28, 30)
    p.text("Please pay by bank transfer and email the deposit slip to billing@villanueva-accounting.example.", 22)
    p.text("THIS DOCUMENT IS NOT VALID FOR CLAIM OF INPUT TAX. (Demo document. Fictional.)", 20)
    scanned(p.img, 0.25).save(OUT / "Sales_Invoice_VA-2026-0187.pdf", "PDF", resolution=150)


def expense_report() -> None:
    rows = [
        "Month,Category,Vendor,Amount (PHP)",
        "January 2026,Office supplies,Northwind Stationers,2140.00",
        "January 2026,Travel,Iloilo Cab Co.,3825.00",
        "January 2026,Software,LedgerCloud,4500.00",
        "February 2026,Office supplies,Northwind Stationers,1236.50",
        "February 2026,Travel,Panay Air,6450.00",
        "February 2026,Training,PICPA Iloilo Chapter,3000.00",
        "March 2026,Office supplies,Northwind Stationers,980.00",
        "March 2026,Travel,Iloilo Cab Co.,2175.00",
        "March 2026,Software,LedgerCloud,4500.00",
    ]
    (OUT / "Expense_Report_Q1_2026.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


def receipt() -> None:
    w, h = 620, 1180
    paper = Image.new("RGB", (w, h), (246, 244, 236))
    d = ImageDraw.Draw(paper)
    y = 40

    def line(s: str, size: int = 26, center: bool = False) -> None:
        nonlocal y
        x = (w - d.textlength(s, font=font(size))) / 2 if center else 40
        d.text((x, y), s, font=font(size), fill=(40, 40, 45))
        y += size + 14

    line("NORTHWIND STATIONERS", 32, True)
    line("Iznart St., Iloilo City", 22, True)
    line("VAT Reg TIN 222-333-444-000", 22, True)
    y += 10
    line("OFFICIAL RECEIPT No. 004521", 26, True)
    line("Feb 12, 2026   10:42 AM", 22, True)
    y += 10
    for item, amt in [
        ("Bond paper A4 x5 reams", "1,125.00"),
        ("Ballpen black x12", "84.00"),
        ("Folder long x20", "27.50"),
    ]:
        line(item, 24)
        line(f"{'':>28}{amt}", 24)
    y += 6
    line("TOTAL           PHP 1,236.50", 28)
    line("Cash            PHP 1,300.00", 24)
    line("Change          PHP    63.50", 24)
    y += 14
    line("Sold to: Villanueva Accounting", 22)
    line("Thank you! Demo receipt - fictional.", 20, True)

    # Photographed on a desk: tilt, shadowed background, blur, grain.
    photo = Image.new("RGB", (900, 1400), (92, 84, 74))
    tilted = paper.rotate(3, resample=Image.BICUBIC, expand=True, fillcolor=(92, 84, 74))
    photo.paste(tilted, ((photo.width - tilted.width) // 2, (photo.height - tilted.height) // 2))
    rnd = random.Random(11)
    px = photo.load()
    for _ in range(40000):
        x, y2 = rnd.randrange(photo.width), rnd.randrange(photo.height)
        r, g, b = px[x, y2]
        n = rnd.randrange(-12, 12)
        px[x, y2] = (max(0, min(255, r + n)), max(0, min(255, g + n)), max(0, min(255, b + n)))
    photo.filter(ImageFilter.GaussianBlur(0.8)).save(OUT / "Receipt_Northwind_Stationers.jpg", "JPEG", quality=85)


def memo() -> None:
    (OUT / "Memo_Year_End_Close.txt").write_text(
        "MEMO\n"
        "To: All staff, Villanueva Accounting\n"
        "From: Ramon Villanueva, Managing Partner\n"
        "Date: November 20, 2026\n"
        "Subject: Year-end close schedule\n\n"
        "All client books for 2026 must be closed by January 15, 2027.\n\n"
        "Bank reconciliations are due December 31, 2026. Draft financial statements go to "
        "clients by February 28, 2027, and annual income tax returns are filed by April 15, 2027.\n\n"
        "Bayview Bakery Co. asked that drafts be sent to Ms. Lorna Dizon by email only.\n",
        encoding="utf-8",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for make in (engagement_letter, invoice, expense_report, receipt, memo):
        make()
    for path in sorted(OUT.iterdir()):
        print(f"{path.stat().st_size:>8,} B  {path.relative_to(OUT.parent.parent)}")


if __name__ == "__main__":
    main()
