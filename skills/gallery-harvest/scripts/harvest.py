#!/usr/bin/env python3
"""harvest.py - collect every image from a gallery/inspiration page and hand Claude
numbered CONTACT SHEETS instead of hundreds of separate screenshots.

  python3 harvest.py https://dribbble.com/search/dashboard --out ./dribbble-dashboard
  python3 harvest.py URL --out DIR --max 120 --strip-query --next "a[rel=next]" --pages 3

Writes in DIR:  sheet-01.jpg ...  (16 numbered thumbnails each)   index.json   images/NNN.ext
Prints ONE JSON summary line. Claude looks at the sheets (a few images), then opens only the
numbered originals it wants to study. Exit codes: 0 ok, 2 setup, 3 step failed, 4 needs human.

Install: python3 -m pip install playwright pillow
Use for personal reference/inspiration; respect each site's terms and the artists' copyright.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flowkit import emit, human, looks_like_login, session, setup_error, step  # noqa: E402

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    setup_error("Pillow is not installed. Run: python3 -m pip install pillow")

EXTRACT_JS = """(minRender) => {
  const pick = (srcset) => {            // largest candidate of a srcset string
    if (!srcset) return null;
    let best = null, bw = -1;
    for (const part of srcset.split(',')) {
      const [u, d] = part.trim().split(/\\s+/);
      const w = d ? parseFloat(d) : 1;
      if (u && w >= bw) { best = u; bw = w; }
    }
    return best;
  };
  const rows = [];
  for (const img of document.images) {
    const r = img.getBoundingClientRect();
    if (r.width < minRender || r.height < minRender * 0.6) continue;   // skip icons/avatars
    const pic = img.closest('picture');
    const src = pick(img.getAttribute('srcset')) || pick(img.dataset.srcset)
      || (pic && pick((pic.querySelector('source[srcset]') || {}).srcset))
      || img.dataset.src || img.dataset.original || img.currentSrc || img.src;
    if (!src || src.startsWith('data:')) continue;
    const a = img.closest('a[href]');
    rows.push({src: new URL(src, location.href).href, link: a ? a.href : null,
               title: (img.alt || (a && (a.title || a.getAttribute('aria-label'))) || '').trim().slice(0, 120)});
  }
  return rows;
}"""


def best_font(size: int) -> Any:
    try:
        return ImageFont.load_default(size=size)  # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def ahash(img: Image.Image) -> int:
    px = list(img.convert("L").resize((8, 8)).getdata())
    avg = sum(px) / 64
    return sum(1 << i for i, p in enumerate(px) if p > avg)


def download(item: Dict[str, Any], referer: str, timeout: int = 25) -> Optional[bytes]:
    req = urllib.request.Request(item["src"], headers={"User-Agent": "Mozilla/5.0", "Referer": referer})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(15_000_001)
            return data if len(data) <= 15_000_000 else None
    except Exception:
        return None


def collect(page: Any, args: argparse.Namespace, found: Dict[str, Dict[str, Any]]) -> None:
    idle = 0
    for _ in range(args.scrolls):
        before = len(found)
        for row in page.evaluate(EXTRACT_JS, args.min_render):
            key = row["src"].split("?")[0] if args.strip_query else row["src"]
            found.setdefault(key, row)
        if len(found) >= args.max:
            return
        idle = idle + 1 if len(found) == before else 0
        if idle >= args.patience:
            return
        page.mouse.wheel(0, 2400)       # lazy-loaded grids only fetch what scrolls into view
        page.wait_for_timeout(args.pause_ms)


def make_sheets(entries: List[Dict[str, Any]], out: Path, cols: int, rows: int, cell: int) -> List[str]:
    per = cols * rows
    cw, ch, pad = cell, int(cell * 0.75), 6
    paths = []
    label_font = best_font(18)
    for s in range(0, len(entries), per):
        chunk = entries[s:s + per]
        nrows = (len(chunk) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * (cw + pad) + pad, nrows * (ch + pad) + pad), (24, 24, 27))
        draw = ImageDraw.Draw(sheet)
        for i, e in enumerate(chunk):
            x, y = pad + (i % cols) * (cw + pad), pad + (i // cols) * (ch + pad)
            with Image.open(out / e["file"]) as im:
                im = im.convert("RGB")
                im.thumbnail((cw, ch))
                sheet.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2))
            tag = str(e["n"])
            draw.rectangle([x, y, x + 12 + 11 * len(tag), y + 26], fill=(0, 0, 0))
            draw.text((x + 6, y + 3), tag, fill=(255, 255, 255), font=label_font)
            e["sheet"] = f"sheet-{s // per + 1:02d}.jpg"
        path = out / f"sheet-{s // per + 1:02d}.jpg"
        sheet.save(path, quality=85)
        paths.append(str(path))
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max", type=int, default=80, help="stop after this many unique images")
    ap.add_argument("--scrolls", type=int, default=40, help="max scroll rounds per page")
    ap.add_argument("--patience", type=int, default=3, help="stop after N scroll rounds with nothing new")
    ap.add_argument("--pause-ms", type=int, default=900)
    ap.add_argument("--min-render", type=int, default=140, help="min on-screen px of an <img> to consider")
    ap.add_argument("--min-size", type=int, default=300, help="min natural width px to keep after download")
    ap.add_argument("--strip-query", action="store_true", help="drop ?resize=... params to fetch originals (try when thumbs are tiny)")
    ap.add_argument("--next", help="CSS selector of the 'next page' link/button")
    ap.add_argument("--pages", type=int, default=1, help="pages to walk when --next is given")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--rows", type=int, default=4)
    ap.add_argument("--cell", type=int, default=360, help="thumbnail width in px (cols*cell should stay <= ~1500)")
    ap.add_argument("--dedupe", type=int, default=3, help="drop near-duplicates within this hash distance (0=off)")
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()

    out = Path(args.out)
    (out / "images").mkdir(parents=True, exist_ok=True)

    found: Dict[str, Dict[str, Any]] = {}
    with session(headless=args.headless) as page:
        with step(page, "open gallery", out):
            page.goto(args.url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(1500)
            if looks_like_login(page):
                human("Page redirected to a login/challenge. Run `flowkit.py start <url>`, sign in or solve it, then re-run.")
        for pg in range(args.pages):
            with step(page, f"collect images (page {pg + 1})", out):
                collect(page, args, found)
            if not args.next or len(found) >= args.max or pg == args.pages - 1:
                break
            with step(page, "go to next page", out):
                nxt = page.locator(args.next).first
                nxt.scroll_into_view_if_needed(timeout=8_000)
                nxt.click()
                page.wait_for_load_state("domcontentloaded")
                page.wait_for_timeout(1500)

    if not found:
        emit({"ok": False, "step": "collect images", "error": "no images found; try --min-render 80, --scrolls, or check login", "url": args.url})
        sys.exit(3)

    items = list(found.values())[: args.max * 2]  # headroom for failed/duplicate downloads
    with ThreadPoolExecutor(max_workers=8) as pool:
        blobs = list(pool.map(lambda it: download(it, args.url), items))

    entries: List[Dict[str, Any]] = []
    hashes: List[int] = []
    skipped = {"download": 0, "small": 0, "duplicate": 0}
    for item, blob in zip(items, blobs):
        if len(entries) >= args.max:
            break
        if not blob:
            skipped["download"] += 1
            continue
        try:
            im = Image.open(io.BytesIO(blob))
            im.load()
        except Exception:
            skipped["download"] += 1
            continue
        if im.width < args.min_size:
            skipped["small"] += 1
            continue
        h = ahash(im)
        if args.dedupe and any(bin(h ^ o).count("1") <= args.dedupe for o in hashes):
            skipped["duplicate"] += 1
            continue
        hashes.append(h)
        n = len(entries) + 1
        ext = (im.format or "jpeg").lower().replace("jpeg", "jpg")
        name = f"images/{n:03d}.{ext}"
        (out / name).write_bytes(blob)
        entries.append({"n": n, "file": name, "w": im.width, "h": im.height, "link": item["link"], "title": item["title"], "src": item["src"]})

    if not entries:
        emit({"ok": False, "step": "download images", "error": "nothing survived filters", "skipped": skipped})
        sys.exit(3)

    sheets = make_sheets(entries, out, args.cols, args.rows, args.cell)
    (out / "index.json").write_text(json.dumps(entries, indent=1), encoding="utf-8")
    emit({"ok": True, "images": len(entries), "sheets": sheets, "index": str(out / "index.json"), "skipped": skipped})


if __name__ == "__main__":
    main()
