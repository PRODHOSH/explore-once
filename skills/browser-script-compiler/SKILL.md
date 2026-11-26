---
name: browser-script-compiler
description: Turn a browser task Claude has to repeat into a reusable Python (Playwright) script so later runs cost almost no tokens - explore the site once live, compile the working path into a script that drives your logged-in Chrome, replay it, and repair only the broken step when the site changes. Use this skill whenever the user wants to automate a repetitive or multi-step web task, run the same flow on many inputs or on a schedule, write or run browser/UI/end-to-end tests, save tokens on Claude-in-Chrome or Playwright-MCP work, or says things like "do this every time", "automate this", "this keeps taking so many tokens", "turn that into a script", "regression test this page", even if they never mention scripts or Playwright.
---

# Browser script compiler

Driving a browser step by step is expensive: every click re-reads a screenshot or page snapshot, and the context grows with each step. A script costs nothing to run. So: **explore once with the model, compile the path, replay with Python, bring the model back only to repair.**

## Decide first: compile or just do it?

Compile when the task will run again (3+ times, on many inputs, on a schedule) or is long (roughly 8+ steps). For a true one-off of a few steps, do it live; writing a script would cost more than it saves.

Check the library first. A past session may already have compiled this:

```bash
python3 scripts/flows.py list
```

If a flow matches, run it (`flows.py run NAME -- --arg value`) and skip to **Handle the exit code**.

## One-time setup

1. `python3 -m pip install playwright` (no browser download: scripts drive your own Chrome).
2. Start the automation Chrome and log in to the sites you need, once:
   `python3 scripts/flowkit.py start https://the-site.example`
   Sessions persist in `~/.pro-skills/chrome-profile`.

Why a separate Chrome instead of the everyday one: since Chrome 136 the debugging port is ignored for the default profile, so scripts cannot attach to it. The automation profile is a normal profile that you sign in to once. Never log it in to anything you would not want a script to be able to act on, because any local process that can reach the debugging port controls that browser (it binds to 127.0.0.1 only).

## Workflow

### 1. Explore live, and keep notes for the compiler
Use whatever browser tool is available (Claude in Chrome, the built-in browser, Playwright MCP). While doing the task, record for each step: the action, the **stable locator** you would use (see `references/selectors.md`), and the **observable signal that the step finished** (an element appears, the URL changes, a stop button disappears). Those two things are what separate a script that works for months from one that breaks tomorrow. Read page text rather than taking screenshots where you can; it is cheaper and gives you locators.

### 2. Compile
Start from `assets/flow_template.py`; keep its shape:
- one `with step(page, "human-readable name", out):` per user-visible action, so a failure names the exact step;
- parameters via `argparse` (never hard-code the user's inputs);
- waits on conditions (`locator.wait_for`, `wait_until`), not `sleep`;
- one `emit({...})` JSON line at the end with only what the caller needs (paths, extracted values). Large payloads go to files.
- call `human(...)` if a login page or CAPTCHA appears. Never try to bypass a CAPTCHA.

Save it in the library so the next session finds it:
`python3 scripts/flows.py add my_flow.py --name site-task --desc "what it does, which site" --params "url, out_dir"`

### 3. Verify before trusting
Run it twice on real inputs. The second run proves it does not depend on state left by exploration. If the flow changes anything real (sends, posts, buys, deletes), the first verification run must be a dry run that stops before the final irreversible click, and the user approves the real run.

### 4. Replay
`python3 scripts/flows.py run site-task -- --url ... --out-dir ...`. Read only the JSON line it prints.

### Handle the exit code
| Code | Meaning | You do |
|---|---|---|
| 0 | ok | use the JSON result |
| 2 | setup (no Chrome, no playwright) | fix per the message |
| 3 | a step failed | **Repair** (below) |
| 4 | needs a human (login, CAPTCHA, 2FA) | tell the user exactly what to do in the automation Chrome window, then re-run |

### Repair, don't re-explore
On exit 3 the JSON names the failing `step` and a `bundle` folder (screenshot + trimmed accessibility tree). Read `aria.txt`, find the element's new name or position, edit only that step's locator, re-run, and update the library entry. If two or more steps fail, the site probably changed its flow; re-explore just that section, not the whole task. Spend tokens on the broken step only; that is the whole point.

## Testing mode (browser and UI tests)
The same loop produces regression tests: explore the feature once, compile assertions (`assert` on text, URL, element state; a failed assert is a failed step), and run on demand or in CI. Read `references/testing.md` for patterns (fixtures, multiple viewports, collecting results into one report).

## Rules of thumb
- Anything irreversible or outward-facing (sending messages, posting, payments, deleting) needs the user's explicit go-ahead for the real run; scripts do not make that decision safer, only faster.
- Keep credentials out of scripts. Use the logged-in profile; never type passwords into a flow.
- Respect each site's terms and rate limits; add small waits between repeated runs and prefer an official API when one exists.
- Prefer `--headless` only for sites that do not need your login; many sites treat headless sessions differently.
- Do not claim a flow works until you have run it. Report what you ran and the exit code.
