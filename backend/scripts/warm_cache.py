"""Pre-warm the answer cache (and crops) with the demo questions.

  cd backend && .venv/bin/python scripts/warm_cache.py [--questions ../docs/DEMO_QUESTIONS.md] [--api ...]

Every line in the questions file that ends with "?" is asked once (list markers,
numbering, quotes, and emphasis are stripped). The cache lives in the backend's
memory, so run this AFTER the final backend start; a restart clears it. Crops are
written to disk and survive restarts. Each question is stored in History.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parent.parent
WS_ID = "reyes-partners"


def questions(path: Path) -> list[str]:
    found = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", line).strip().strip("*_\"'“”`").strip()
        if text.endswith("?") and len(text) > 3:
            found.append(text)
    return list(dict.fromkeys(found))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--questions", type=Path, default=BACKEND.parent / "docs" / "DEMO_QUESTIONS.md")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--workspace", default=WS_ID)
    args = parser.parse_args()

    if not args.questions.exists():
        print(f"{args.questions} doesn't exist yet.")
        return 1
    qs = questions(args.questions)
    if not qs:
        print(f"No questions (lines ending in '?') found in {args.questions}.")
        return 1

    problems = 0
    with httpx.Client(base_url=args.api.rstrip("/"), timeout=120) as client:
        for q in qs:
            r = client.post(f"/api/workspaces/{args.workspace}/ask", json={"question": q})
            if r.status_code != 200:
                print(f"ERROR {r.status_code}  {q}")
                problems += 1
                continue
            res = r.json()
            crops = sum(1 for c in res["citations"] if c["crop_url"])
            mode = " (extractive)" if res.get("reason") == "Showing matching passages." else ""
            print(f"{res['status']:<10} {res['elapsed_ms']:>6} ms  {len(res['citations'])} citations, {crops} crops{mode}  {q}")
            if res.get("reason") and res["status"] == "not_found":
                print(f"           reason: {res['reason']}")
            if mode:
                problems += 1  # extractive answers aren't cached; the LLM was unavailable
            again = client.post(f"/api/workspaces/{args.workspace}/ask", json={"question": q}).json()
            if not mode and again["elapsed_ms"] > 200:
                print(f"           warning: second ask took {again['elapsed_ms']} ms (not cached?)")
    print(f"Warmed {len(qs)} questions" + (f", {problems} need attention." if problems else "."))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
