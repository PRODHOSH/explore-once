#!/usr/bin/env python3
"""run_suite.py - run a UI regression suite and report ONLY what needs a human look.

  python3 run_suite.py suite.json                 # run, compare to baselines
  python3 run_suite.py suite.json --update        # accept current screenshots as baselines
  python3 run_suite.py suite.json --only home     # one page

suite.json
{
  "base_url": "http://localhost:3000",
  "viewports": {"desktop": [1280, 800], "mobile": [375, 812]},
  "threshold": 0.002,                       # fraction of pixels allowed to differ
  "pages": [
    {"name": "home", "path": "/", "expect_text": ["Welcome"], "expect_selector": ["nav", "main h1"],
     "wait_for": "main", "mask": [".clock", "[data-dynamic]"]},
    {"name": "pricing", "path": "/pricing"}
  ]
}

Every page x viewport gets generic health checks for free (errors fail, warnings inform):
  ERROR  bad HTTP status | console error | uncaught exception | failed/4xx/5xx request
         | horizontal overflow | broken image | expect_text / expect_selector missing
         | screenshot differs from baseline beyond threshold
  WARN   image without alt | missing <title> | no <h1> | link/button without accessible name
Output: one JSON line + report.md + diff images (baseline | actual | difference) for failures only.
Exit codes: 0 pass, 3 failures (details in the JSON/report), 2 setup problem.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flowkit import emit, session, setup_error  # noqa: E402

try:
    from PIL import Image, ImageChops
except ImportError:  # pragma: no cover
    setup_error("Pillow is not installed. Run: python3 -m pip install pillow")

CHECKS_JS = """() => {
  const res = {};
  res.overflow = document.documentElement.scrollWidth - window.innerWidth;
  res.title = document.title || '';
  res.h1 = document.querySelectorAll('h1').length;
  res.brokenImages = Array.from(document.images).filter(i => i.complete && i.naturalWidth === 0 && (i.currentSrc || i.src)).map(i => i.currentSrc || i.src).slice(0, 5);
  res.noAlt = Array.from(document.images).filter(i => !i.hasAttribute('alt') && i.getBoundingClientRect().width > 24).map(i => i.currentSrc || i.src).slice(0, 5);
  const unnamed = el => !((el.innerText || '').trim() || el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('aria-labelledby') || (el.querySelector('img[alt]:not([alt=""])')) || el.getAttribute('value'));
  res.unnamed = Array.from(document.querySelectorAll('a[href], button')).filter(unnamed).map(e => e.outerHTML.slice(0, 80)).slice(0, 5);
  return res;
}"""

FREEZE_CSS = "*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}"


def diff_ratio(a: Image.Image, b: Image.Image) -> Any:
    w, h = min(a.width, b.width), min(a.height, b.height)
    ca, cb = a.convert("RGB").crop((0, 0, w, h)), b.convert("RGB").crop((0, 0, w, h))
    d = ImageChops.difference(ca, cb).convert("L").point(lambda v: 255 if v > 16 else 0)
    changed = sum(1 for p in d.getdata() if p)
    return changed / max(w * h, 1), d, (ca, cb)


def make_diff_image(path: Path, base: Image.Image, cur: Image.Image, mask: Image.Image) -> None:
    w = min(base.width, cur.width, mask.width)
    h = min(base.height, cur.height, mask.height)
    red = Image.new("RGB", (w, h), (255, 0, 80))
    over = Image.composite(red, cur.convert("RGB").crop((0, 0, w, h)).point(lambda v: v // 3 + 120), mask.crop((0, 0, w, h)))
    sheet = Image.new("RGB", (w * 3 + 20, h), (30, 30, 30))
    sheet.paste(base.convert("RGB").crop((0, 0, w, h)), (0, 0))
    sheet.paste(cur.convert("RGB").crop((0, 0, w, h)), (w + 10, 0))
    sheet.paste(over, (2 * w + 20, 0))
    scale = min(1.0, 1500 / sheet.width)
    if scale < 1:
        sheet = sheet.resize((int(sheet.width * scale), int(sheet.height * scale)))
    sheet.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("suite")
    ap.add_argument("--out", default="./ui-report")
    ap.add_argument("--baselines", default="./ui-baselines")
    ap.add_argument("--update", action="store_true", help="overwrite baselines with the current screenshots")
    ap.add_argument("--only", help="run just the page with this name")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    ap.add_argument("--visible", action="store_true", help="show the browser (default: headless unless the automation Chrome is already open)")
    args = ap.parse_args()

    try:
        suite = json.loads(Path(args.suite).read_text(encoding="utf-8"))
        base_url = suite["base_url"].rstrip("/")
        pages = [p for p in suite["pages"] if not args.only or p["name"] == args.only]
        assert pages
    except Exception:
        setup_error("suite must be JSON with base_url and a non-empty pages list (see --help)")
    viewports: Dict[str, List[int]] = suite.get("viewports", {"desktop": [1280, 800]})
    threshold = float(suite.get("threshold", 0.002))
    out, base_dir = Path(args.out), Path(args.baselines)
    (out / "shots").mkdir(parents=True, exist_ok=True); (out / "diffs").mkdir(exist_ok=True); base_dir.mkdir(parents=True, exist_ok=True)

    failures: List[Dict[str, Any]] = []
    warnings = 0
    created: List[str] = []
    lines = [f"# UI regression report - {time.strftime('%Y-%m-%d %H:%M')}\n"]
    runs = 0

    with session(headless=not args.visible) as page:
        errs: List[str] = []
        page.on("console", lambda m: errs.append(f"console error: {m.text[:160]}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(f"uncaught exception: {str(e)[:160]}"))
        page.on("response", lambda r: errs.append(f"HTTP {r.status}: {r.url[:140]}") if r.status >= 400 else None)
        page.on("requestfailed", lambda r: errs.append(f"request failed: {r.url[:140]}"))

        for pg in pages:
            for vp_name, (vw, vh) in viewports.items():
                runs += 1
                errs.clear()
                problems: List[str] = []
                warns: List[str] = []
                tag = f"{pg['name']}-{vp_name}"
                try:
                    page.set_viewport_size({"width": vw, "height": vh})
                    resp = page.goto(base_url + pg["path"], wait_until="load", timeout=30_000)
                    if resp is not None and resp.status >= 400:
                        problems.append(f"page returned HTTP {resp.status}")
                    if pg.get("wait_for"):
                        page.wait_for_selector(pg["wait_for"], timeout=10_000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=4000)
                    except Exception:
                        pass
                    problems += list(dict.fromkeys(errs))
                    r = page.evaluate(CHECKS_JS)
                    if r["overflow"] > 1:
                        problems.append(f"horizontal overflow: page is {r['overflow']}px wider than the viewport")
                    problems += [f"broken image: {u[:100]}" for u in r["brokenImages"]]
                    body = page.locator("body").inner_text()
                    problems += [f"expected text missing: {t!r}" for t in pg.get("expect_text", []) if t not in body]
                    for sel in pg.get("expect_selector", []):
                        if page.locator(sel).count() == 0:
                            problems.append(f"expected element missing: {sel}")
                    warns += [f"image without alt: {u[:90]}" for u in r["noAlt"]]
                    warns += [] if r["title"] else ["missing <title>"]
                    warns += [] if r["h1"] else ["no <h1>"]
                    warns += [f"unnamed link/button: {h}" for h in r["unnamed"]]

                    page.add_style_tag(content=FREEZE_CSS)
                    for sel in pg.get("mask", []):
                        page.add_style_tag(content=f"{sel}{{visibility:hidden!important}}")
                    shot = out / "shots" / f"{tag}.png"
                    page.screenshot(path=str(shot), full_page=True)
                    base_path = base_dir / f"{tag}.png"
                    if args.update or not base_path.exists():
                        base_path.write_bytes(shot.read_bytes())
                        if not args.update:
                            created.append(tag)
                    else:
                        with Image.open(base_path) as bi, Image.open(shot) as ci:
                            bi.load(); ci.load()
                            if bi.size != ci.size:
                                problems.append(f"page size changed {bi.size[0]}x{bi.size[1]} -> {ci.size[0]}x{ci.size[1]}")
                            ratio, mask, _ = diff_ratio(bi, ci)
                            if ratio > threshold:
                                dpath = out / "diffs" / f"{tag}.png"
                                make_diff_image(dpath, bi, ci, mask)
                                problems.append(f"screenshot differs from baseline by {ratio:.2%} (limit {threshold:.2%}); see {dpath}")
                except Exception as exc:  # noqa: BLE001 - one broken page must not stop the suite
                    problems.append(f"run error: {str(exc).splitlines()[0][:200]}")

                warnings += len(warns)
                if args.strict:
                    problems += warns
                status = "FAIL" if problems else "pass"
                lines.append(f"## {status} - {tag}\n" + "".join(f"- ERROR {p}\n" for p in problems) + "".join(f"- warn {w}\n" for w in warns))
                if problems:
                    failures.append({"page": pg["name"], "viewport": vp_name, "problems": problems})

    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    emit({"ok": not failures, "checked": runs, "failed": len(failures), "warnings": warnings,
          "new_baselines": created, "report": str(out / "report.md"), "failures": failures[:8]})
    sys.exit(0 if not failures else 3)


if __name__ == "__main__":
    main()
