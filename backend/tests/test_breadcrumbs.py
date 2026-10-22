"""Heading breadcrumbs at block extraction (no MinerU, no network).

  cd backend && .venv/bin/python tests/test_breadcrumbs.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import parsing, search  # noqa: E402


def check(label: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        sys.exit(1)


def blocks(page_texts: list[tuple[int, str]]) -> list[dict]:
    return [{"id": f"f-p{p}-b{i}", "file_id": "f", "page": p, "text": t} for i, (p, t) in enumerate(page_texts, start=1)]


doc = blocks([
    (1, "ARTICLE VI"),
    (1, "THE LEGISLATIVE DEPARTMENT"),
    (1, "Section 1. The legislative power shall be vested in the Congress."),
    (2, "Section 21. The Senate or the House may conduct inquiries."),
    (2, "Its rules of procedure shall be published."),
    (3, "ARTICLE VII"),
    (3, "EXECUTIVE DEPARTMENT"),
    (3, "Section 21. No treaty shall be valid without two-thirds of the Senate."),
    (4, "6000 L AND W SERVICES 4 6 a"),
])
parsing.add_breadcrumbs(doc)
paths = [b["path"] for b in doc]
check("article title joined from the next block", paths[2] == ["Article VI — The Legislative Department", "Section 1"])
check("a new Section replaces the previous one", paths[3] == ["Article VI — The Legislative Department", "Section 21"])
check("body text under a section inherits its path", paths[4] == paths[3])
check("a new Article resets the Section below it", paths[5] == ["Article VII — Executive Department"])
check("Article VII, Section 21", paths[7] == ["Article VII — Executive Department", "Section 21"])
check("heading_ids point at the heading blocks", doc[7]["heading_ids"] == ["f-p3-b6", "f-p3-b8"])
check("OCR line starting with a number is not a numbered heading", paths[8] == paths[7])

rules = blocks([
    (1, "RULE 40 Appeal From Municipal Trial Courts 30"), (1, "RULE 41 Appeal From the Regional Trial Courts 31"),
    (1, "PART V PROVISIONS SPECIFIC TO OTHER FORMS OF ADR"), (1, "RULE 42 Petition for Review 32"),
    (1, "RULE 43 Appeals From the CTA 33"), (1, "RULE 44 Ordinary Appealed Cases 34"), (1, "RULE 45 Appeal by Certiorari 35"),
    (2, "RULE 41 Appeal From The Regional Trial Courts"),
    (2, "Section 3. Period of ordinary appeal. — The appeal shall be taken within fifteen (15) days."),
    (2, "Sec. 4. Appellate court docket and other lawful fees."),
])
parsing.add_breadcrumbs(rules)
check("table-of-contents page opens no headings (no stray Part V)", rules[8]["path"] == ["Rule 41 — Appeal From The Regional Trial Courts", "Section 3"])
check("'Sec.' is a Section", rules[9]["path"] == ["Rule 41 — Appeal From The Regional Trial Courts", "Section 4"])

numbered = blocks([(1, "1. Scope"), (1, "This policy covers all staff."), (1, "1.1 Definitions"), (1, "Terms used here."), (1, "2. Fees")])
parsing.add_breadcrumbs(numbered)
check("numbered headings nest and reset", [b["path"] for b in numbered] == [["1 Scope"], ["1 Scope"], ["1 Scope", "1.1 Definitions"], ["1 Scope", "1.1 Definitions"], ["2 Fees"]])

check("search indexes the path with the text", search.index_text(doc[7]).startswith("Article VII — Executive Department > Section 21: Section 21. No treaty"))
print("breadcrumb checks passed")
