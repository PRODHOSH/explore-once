#!/usr/bin/env python3
"""FLOW: <one line - what this does, which site>
PARAMS: url, expect_heading, out_dir
Compiled from a live exploration on <date>. Selectors verified: <date>.

Copy this file, keep the shape, replace the steps. The shape is what makes it cheap to
repair: one `with step(...)` per user-visible action, one JSON line out.
This template runs as-is against https://example.com (a smoke test of your setup).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flowkit import emit, human, looks_like_login, session, step, wait_until  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://example.com")
    ap.add_argument("--expect-heading", default="Example Domain")
    ap.add_argument("--out-dir", default="./out")
    ap.add_argument("--headless", action="store_true", help="only for sites that do not need your login")
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    with session(headless=args.headless) as page:
        with step(page, "open page", out):
            page.goto(args.url, wait_until="domcontentloaded", timeout=30_000)
            if looks_like_login(page):
                human("Login required. Run `flowkit.py start <url>`, sign in, then re-run.")

        # Prefer role/text/label locators over CSS classes (see references/selectors.md).
        with step(page, "find heading", out):
            heading = page.get_by_role("heading", level=1).first
            heading.wait_for(state="visible", timeout=10_000)
            text = heading.inner_text()

        with step(page, "assert heading", out):
            assert args.expect_heading in text, f"expected {args.expect_heading!r}, got {text!r}"

        with step(page, "save evidence", out):
            shot = out / "evidence.png"
            page.screenshot(path=str(shot))

    emit({"ok": True, "heading": text, "screenshot": str(shot)})


if __name__ == "__main__":
    main()
