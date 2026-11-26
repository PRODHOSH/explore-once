#!/usr/bin/env python3
"""flowkit - shared helpers for pro-skills browser flows.

Canonical copy lives in shared/flowkit.py and is synced into every skill's
scripts/ folder by tools/sync_shared.py (skills must stay self-contained).

What it gives a compiled browser script:
  * start/attach to a dedicated automation Chrome over CDP (one-time login, persists)
  * step(): named steps that, on failure, write a small "failure bundle"
    (screenshot + trimmed accessibility snapshot) and exit with a repairable code
  * emit()/human(): one-line JSON results so the calling agent reads ~100 tokens
    instead of re-reading the page

Exit codes (a contract the skills rely on):
  0 ok | 2 setup problem | 3 a step failed (repairable) | 4 needs a human (login/CAPTCHA)

Requires: Python 3.9+, `pip install playwright` (no `playwright install` needed:
we drive your own Chrome).
"""
from __future__ import annotations

import contextlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional

EXIT_OK, EXIT_SETUP, EXIT_STEP, EXIT_HUMAN = 0, 2, 3, 4

HOME = Path(os.environ.get("PRO_SKILLS_HOME", str(Path.home() / ".pro-skills")))
PROFILE_DIR = HOME / "chrome-profile"
FAILURES_DIR = HOME / "failures"
DEFAULT_PORT = int(os.environ.get("PRO_SKILLS_CDP_PORT", "9222"))

LOGIN_HINTS = ("login", "signin", "sign-in", "sign_in", "/auth", "accounts.google.com", "challenge", "captcha")


# --------------------------------------------------------------------------- output
def emit(obj: Dict[str, Any]) -> None:
    """Print one compact JSON line. Keep results tiny: the agent pays per token."""
    print(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), flush=True)


def human(reason: str, **extra: Any) -> None:
    """Stop because only a person can continue (login, CAPTCHA, 2FA)."""
    emit({"ok": False, "needs_human": True, "reason": reason, **extra})
    sys.exit(EXIT_HUMAN)


def setup_error(message: str, **extra: Any) -> None:
    emit({"ok": False, "setup_error": message, **extra})
    sys.exit(EXIT_SETUP)


def slug(text: str, limit: int = 40) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()[:limit] or "x"


# --------------------------------------------------------------------------- chrome
def chrome_binary() -> Optional[str]:
    override = os.environ.get("CHROME_BIN")
    if override and Path(override).exists():
        return override
    system = platform.system()
    candidates = []
    if system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    elif system == "Windows":
        for base in (os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)"), os.environ.get("LOCALAPPDATA")):
            if base:
                candidates.append(str(Path(base) / "Google/Chrome/Application/chrome.exe"))
    else:
        for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge"):
            found = shutil.which(name)
            if found:
                candidates.append(found)
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def cdp_alive(port: int = DEFAULT_PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def start_chrome(port: int = DEFAULT_PORT, headless: bool = False, url: Optional[str] = None) -> None:
    """Start the dedicated automation Chrome if it is not already listening.

    Why a separate profile: since Chrome 136 the remote-debugging switch is ignored for
    the default profile (a security change), so we cannot attach to your everyday Chrome.
    The automation profile is a normal Chrome profile: log in to ChatGPT/Gemini/etc. once
    and the sessions persist in PROFILE_DIR.
    """
    if cdp_alive(port):
        return
    binary = chrome_binary()
    if not binary:
        setup_error("Chrome not found. Install Chrome or set CHROME_BIN to its executable.")
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    args = [
        binary,
        f"--remote-debugging-port={port}",
        "--remote-debugging-address=127.0.0.1",  # never expose CDP beyond this machine
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if headless:
        args.append("--headless=new")
    if url:
        args.append(url)
    subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    deadline = time.time() + 25
    while time.time() < deadline:
        if cdp_alive(port):
            return
        time.sleep(0.3)
    setup_error(f"Chrome did not open a debugging port on {port} within 25s.")


def stop_chrome() -> bool:
    """Quit the automation Chrome (posix only). Returns True if a kill was attempted."""
    if platform.system() == "Windows":
        return False
    subprocess.run(["pkill", "-f", f"--user-data-dir={PROFILE_DIR}"], check=False)
    return True


@contextlib.contextmanager
def session(port: int = DEFAULT_PORT, headless: bool = False, new_tab: bool = True, keep_open: bool = False) -> Iterator[Any]:
    """Yield a Playwright Page attached to the automation Chrome."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        setup_error("playwright is not installed. Run: python3 -m pip install playwright")
    start_chrome(port, headless=headless)
    with sync_playwright() as pw:
        browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page() if (new_tab or not ctx.pages) else ctx.pages[0]
        try:
            yield page
        finally:
            if new_tab and not keep_open:
                with contextlib.suppress(Exception):
                    page.close()


# --------------------------------------------------------------------------- steps
def looks_like_login(page: Any) -> bool:
    url = (page.url or "").lower()
    return any(h in url for h in LOGIN_HINTS)


def wait_until(predicate: Callable[[], Any], timeout: float = 30.0, interval: float = 0.5) -> Any:
    """Poll until predicate() is truthy; returns its value or None on timeout.

    Prefer this (or Playwright auto-waits) over fixed sleeps: sleeps are the #1 cause of
    flaky and slow scripts."""
    end = time.time() + timeout
    while time.time() < end:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return None


def failure_bundle(page: Any, step_name: str, error: BaseException, out_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Capture just enough state for an agent to repair one broken step."""
    folder = (out_dir or FAILURES_DIR) / f"{time.strftime('%Y%m%d-%H%M%S')}-{slug(step_name)}"
    folder.mkdir(parents=True, exist_ok=True)
    info: Dict[str, Any] = {"step": step_name, "error": str(error).strip().splitlines()[0][:300] if str(error).strip() else type(error).__name__}
    with contextlib.suppress(Exception):
        info["url"] = page.url
        info["title"] = page.title()
    with contextlib.suppress(Exception):
        shot = folder / "screenshot.png"
        page.screenshot(path=str(shot), full_page=False)
        info["screenshot"] = str(shot)
    with contextlib.suppress(Exception):
        snap = page.locator("body").aria_snapshot()
        (folder / "aria.txt").write_text(snap[:8000], encoding="utf-8")
        info["aria"] = str(folder / "aria.txt")
    (folder / "info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    info["bundle"] = str(folder)
    return info


@contextlib.contextmanager
def step(page: Any, name: str, out_dir: Optional[Path] = None) -> Iterator[None]:
    """Run a named step. On failure: write a failure bundle, print it, exit 3.

    Exiting (instead of retrying blindly) is deliberate: a failed selector means the site
    changed, and a retry loop would burn minutes. The agent repairs only this step."""
    try:
        yield
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - we want every failure captured
        info = failure_bundle(page, name, exc, out_dir)
        emit({"ok": False, **info})
        sys.exit(EXIT_STEP)


# --------------------------------------------------------------------------- cli
def _main(argv: list) -> int:
    cmd = argv[1] if len(argv) > 1 else "help"
    port = DEFAULT_PORT
    if cmd == "start":  # visible window, for first-time logins
        start_chrome(port, url=argv[2] if len(argv) > 2 else None)
        emit({"ok": True, "port": port, "profile": str(PROFILE_DIR), "note": "Log in to your sites in this window once; sessions persist."})
    elif cmd == "status":
        emit({"ok": True, "running": cdp_alive(port), "port": port, "profile": str(PROFILE_DIR), "chrome": chrome_binary()})
    elif cmd == "stop":
        emit({"ok": stop_chrome()})
    else:
        print("usage: flowkit.py start [url] | status | stop")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv))
