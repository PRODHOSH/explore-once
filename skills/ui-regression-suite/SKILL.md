---
name: ui-regression-suite
description: Build and run a UI regression suite for a website or web app that checks every page at desktop and mobile sizes for console errors, failed requests, broken images, horizontal overflow, missing content, accessibility basics and visual changes against baseline screenshots, and reports only the pages that need a human look. Use this skill whenever the user wants to test a site or web app, check that a change did not break the UI, do visual or responsive checks, run a pre-release or smoke test, catch regressions, or review "does everything still look right", even if they only say "test my site" and never mention screenshots or Playwright.
license: Apache-2.0
compatibility: Python 3.9+, Google Chrome, and `pip install playwright pillow`.
---

# UI regression suite

Opening every page by hand and eyeballing it is slow and uses a screenshot read per page. A suite does the repeating work in Python and shows Claude only what failed. After the first run, checking the whole site costs a few hundred tokens when nothing changed.

## Setup
`python3 -m pip install playwright pillow` (the scripts drive your installed Chrome; no browser download). For a local app, start your dev server first.

## Workflow

1. **Write `suite.json`.** List the important routes. Ask the user which pages matter, or read the app's routes. A good start is 5-10 pages: home, key flows, a form page, one error page.
   ```json
   {"base_url": "http://localhost:3000",
    "viewports": {"desktop": [1280, 800], "mobile": [375, 812]},
    "threshold": 0.002,
    "pages": [
      {"name": "home", "path": "/", "expect_text": ["Welcome"], "expect_selector": ["nav", "main h1"], "mask": [".clock"]},
      {"name": "pricing", "path": "/pricing", "wait_for": "main"}]}
   ```
   - `expect_text` / `expect_selector` pin the content that must exist; they catch pages that load but render empty.
   - `mask` hides regions that legitimately change (clocks, ads, random avatars) so they do not cause false alarms.
   - Add `wait_for` for pages that render after load.
2. **First run creates baselines.** `python3 scripts/run_suite.py suite.json`. A first run reports "new_baselines" and compares nothing visually. Look at the new screenshots once (`ui-report/shots/`) to make sure the baselines show a *correct* page; a baseline of a broken page protects the break.
3. **Later runs compare.** Same command. Exit 0 means pass. Exit 3 means failures: read the JSON `failures` and `ui-report/report.md`. For each visual failure open the diff image (baseline | actual | difference) and decide: bug or intended change?
4. **Intended change?** Re-run with `--update` to accept the new screenshots as baselines, and say that you did.
5. **Fix, re-run, and only report green when it is green.**

## What the generic checks cover
Errors (fail the run): HTTP error status, console errors, uncaught exceptions, failed or 4xx/5xx requests, horizontal overflow (a classic mobile bug), broken images, missing expected text or elements, screenshots that differ beyond the threshold. Warnings (reported, fail only with `--strict`): images without `alt`, missing `<title>`, no `<h1>`, links and buttons without an accessible name. These are quick checks, not an accessibility audit. Say so if the user asks about compliance.

## Tuning
- Many false visual failures: add `mask` entries or raise `threshold` slightly (0.005). Do not raise it until real changes stop being caught.
- Fonts or rendering differ between machines, so baselines are best made and checked on the same machine or in the same CI image. Say this when the user wants baselines in git.
- `--only <page name>` re-runs one page quickly while fixing.
- Logged-in pages: sign in via `python3 scripts/flowkit.py start <url>` first; the suite uses that profile. Test accounts only; never a real user's production login.

## Reporting
Lead with the result in one line (checked N page/viewport combos, M failed), then list failures grouped by page with the cause and the fix. Mention warnings briefly. If you changed baselines, say which and why.

## Exit codes
0 pass | 2 setup (bad suite file, missing dependency) | 3 failures found (not a script error: it is the finding).
