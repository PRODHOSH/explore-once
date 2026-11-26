#!/usr/bin/env python3
"""generate_image.py - generate an image with ChatGPT or Gemini through your logged-in
automation Chrome, wait for it, and save the file. No LLM tokens are spent while it runs.

  python3 generate_image.py --site chatgpt --prompt "a watercolor fox" --out ./images
  python3 generate_image.py --site gemini  --prompt-file p.txt --out ./images --count 2
  python3 generate_image.py --site chatgpt --inspect     # dump the page's controls (for repairs)

Result: ONE JSON line on stdout. Exit codes: 0 ok, 2 setup, 3 step failed, 4 needs human.

How it finds the result without site-specific selectors for the image itself: it records
every large <img> on the page before sending, then waits for NEW large images that stop
changing. Only the input box / send button selectors (sites.json) are site-specific.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flowkit import (EXIT_STEP, emit, human, looks_like_login, session, setup_error, slug,  # noqa: E402
                     step, wait_until)

IMG_JS = """() => Array.from(document.images).map(i => ({
  src: i.currentSrc || i.src, w: i.naturalWidth, h: i.naturalHeight, done: i.complete
}))"""

MAGIC = [(b"\x89PNG", "png"), (b"\xff\xd8\xff", "jpg"), (b"RIFF", "webp"), (b"GIF8", "gif")]


def first_visible(page: Any, selectors: List[str], timeout: float = 30.0) -> Optional[Any]:
    """Return a locator for the first selector that is visible, polling up to timeout."""
    def probe() -> Optional[Any]:
        for sel in selectors:
            loc = page.locator(sel).first
            try:
                if loc.is_visible():
                    return loc
            except Exception:
                continue
        return None
    return wait_until(probe, timeout=timeout, interval=0.4)


def big_images(page: Any, min_side: int) -> Dict[str, Dict[str, Any]]:
    out = {}
    for im in page.evaluate(IMG_JS):
        if im["done"] and im["w"] >= min_side and im["h"] >= min_side and im["src"]:
            out[im["src"]] = im
    return out


def fetch_bytes(page: Any, src: str) -> bytes:
    if src.startswith("data:"):
        return base64.b64decode(src.split(",", 1)[1])
    if src.startswith("http"):
        try:  # shares the logged-in cookies of the browser context
            resp = page.context.request.get(src, timeout=60_000)
            if resp.ok:
                return resp.body()
        except Exception:
            pass
    b64 = page.evaluate(
        """async (u) => { const r = await fetch(u); const b = new Uint8Array(await r.arrayBuffer());
           let s = ''; for (let i = 0; i < b.length; i += 32768) s += String.fromCharCode(...b.subarray(i, i + 32768));
           return btoa(s); }""", src)
    return base64.b64decode(b64)


def extension(data: bytes) -> str:
    for magic, ext in MAGIC:
        if data.startswith(magic):
            return ext
    return "bin"


def main() -> None:
    sites = json.loads((Path(__file__).with_name("sites.json")).read_text(encoding="utf-8"))
    sites.pop("_comment", None)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", required=True, choices=sorted(sites))
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--out", default="./images")
    ap.add_argument("--count", type=int, default=1, help="max images to save from the reply")
    ap.add_argument("--timeout", type=int, default=240, help="seconds to wait for the image")
    ap.add_argument("--min-side", type=int, default=512, help="ignore images smaller than this (icons, avatars)")
    ap.add_argument("--raw-prompt", action="store_true", help="do not prepend the site's 'Generate an image:' prefix")
    ap.add_argument("--inspect", action="store_true", help="print visible controls instead of generating")
    ap.add_argument("--keep-open", action="store_true", help="leave the tab open afterwards")
    args = ap.parse_args()

    cfg = sites[args.site]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    prompt = args.prompt or (Path(args.prompt_file).read_text(encoding="utf-8").strip() if args.prompt_file else "")
    if not prompt and not args.inspect:
        setup_error("Provide --prompt or --prompt-file.")
    if not args.raw_prompt:
        prompt = cfg["prompt_prefix"] + prompt

    with session(keep_open=args.keep_open or args.inspect) as page:
        with step(page, "open site", out):
            page.goto(cfg["url"], wait_until="domcontentloaded", timeout=45_000)

        with step(page, "find input box", out):
            box = first_visible(page, cfg["input"], timeout=30)
            if box is None:
                if looks_like_login(page):
                    human(f"Not logged in to {args.site}. Run `flowkit.py start {cfg['url']}` and sign in once.")
                raise RuntimeError("no input selector matched; update sites.json (use --inspect)")

        if args.inspect:
            snap = page.locator("body").aria_snapshot()
            emit({"ok": True, "site": args.site, "url": page.url, "matched_input": True, "aria": snap[:6000]})
            return

        baseline = set(big_images(page, args.min_side))

        with step(page, "type and send prompt", out):
            box.click()
            page.keyboard.insert_text(prompt)  # one event: fast, and works for contenteditable and textarea
            send = first_visible(page, cfg["send"], timeout=5)
            if send is not None:
                send.click()
            else:
                page.keyboard.press("Enter")

        saved: List[Dict[str, Any]] = []
        with step(page, "wait for generated image", out):
            deadline = time.time() + args.timeout
            stable_polls, last = 0, set()
            while time.time() < deadline:
                time.sleep(1.5)
                current = set(big_images(page, args.min_side)) - baseline
                generating = first_visible(page, cfg["stop"], timeout=0.2) is not None
                if current and current == last and not generating:
                    stable_polls += 1
                    if stable_polls >= 2:  # unchanged for ~3s and the "stop" button is gone
                        break
                else:
                    stable_polls = 0
                last = current
            else:
                raise TimeoutError(f"no new image within {args.timeout}s (the aria snapshot in the bundle shows the model's reply, e.g. a refusal)")
            new_srcs = sorted(last)[: args.count]

        with step(page, "download image", out):
            base = f"{slug(prompt[len(cfg['prompt_prefix']):] if not args.raw_prompt else prompt, 32)}-{time.strftime('%H%M%S')}"
            for n, src in enumerate(new_srcs, 1):
                data = fetch_bytes(page, src)
                path = out / f"{base}-{n}.{extension(data)}"
                path.write_bytes(data)
                saved.append({"file": str(path), "bytes": len(data)})

    emit({"ok": True, "site": args.site, "files": saved})


if __name__ == "__main__":
    main()
