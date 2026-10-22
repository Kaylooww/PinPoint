"""Crop images for cited blocks, cached in data/{ws}/crops/{block_id}.png.

Order of attempts (docs/ARCHITECTURE.md):
  1. mineru read "<block locator>" --format image
  2. render the page with mineru read "<page locator>" --format image, crop it with Pillow
     using the block's normalized bbox
  3. the page image itself
"""

from __future__ import annotations

import re
import shutil
import threading
from pathlib import Path
from typing import Any

from PIL import Image

from . import parsing, storage

CROP_ID_RE = re.compile(r"^([a-z0-9][a-z0-9-]{0,63})\.([a-z0-9][a-z0-9-]{0,127})$")
READ_TIMEOUT = 30
PADDING = 0.01  # of page size, around the bbox

_lock = threading.Lock()


def crop_path(crop_id: str) -> Path | None:
    match = CROP_ID_RE.match(crop_id)
    if not match:
        return None
    ws, block_id = match.groups()
    try:
        return storage.crops_dir(ws) / f"{block_id}.png"
    except storage.NotFound:
        return None


def _read_image(locator: str, out: Path) -> bool:
    try:
        proc = parsing.run_mineru(["read", locator, "--format", "image", "--output", str(out)], timeout=READ_TIMEOUT)
    except parsing.ParseError:
        return False
    return proc.returncode == 0 and out.exists() and out.stat().st_size > 0


def page_image(ws: str, page_locator: str) -> Path | None:
    """Rendered page image (mineru read --format image), cached in crops/pages/."""
    out = storage.crops_dir(ws) / "pages" / (re.sub(r"[^a-z0-9]+", "-", page_locator.lower()).strip("-") + ".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        return out if out.exists() or _read_image(page_locator, out) else None


def _page_image(ws: str, block: dict[str, Any]) -> Path | None:
    page_locator = block["locator"].rsplit("/block:", 1)[0]
    out = storage.crops_dir(ws) / "pages" / (re.sub(r"[^a-z0-9]+", "-", page_locator.lower()).strip("-") + ".png")
    out.parent.mkdir(parents=True, exist_ok=True)
    return out if out.exists() or _read_image(page_locator, out) else None


def _crop_from_page(page: Path, bbox: list[float], out: Path) -> bool:
    try:
        with Image.open(page) as img:
            w, h = img.size
            x0, y0, x1, y1 = bbox
            box = (
                max(0, int((x0 - PADDING) * w)),
                max(0, int((y0 - PADDING) * h)),
                min(w, int((x1 + PADDING) * w)),
                min(h, int((y1 + PADDING) * h)),
            )
            if box[2] <= box[0] or box[3] <= box[1]:
                return False
            img.crop(box).save(out, "PNG")
        return True
    except (OSError, ValueError):
        return False


def ensure_crop(ws: str, block: dict[str, Any]) -> Path | None:
    if not block["locator"].startswith("doc:"):  # notes and plain-text files have no page image
        return None
    out = storage.crops_dir(ws) / f"{block['id']}.png"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        if out.exists() or _read_image(block["locator"], out):
            return out
        page = _page_image(ws, block)
        if page is None:
            return None
        if block.get("bbox") and _crop_from_page(page, block["bbox"], out):
            return out
        shutil.copyfile(page, out)
        return out


def crop_url(ws: str, block: dict[str, Any]) -> str | None:
    """API path of the block's crop, creating it on first use; None if no image is possible."""
    return f"/api/crops/{ws}.{block['id']}.png" if ensure_crop(ws, block) else None
