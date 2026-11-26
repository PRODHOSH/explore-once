# Compiling browser tests

Use the same pieces (`flowkit.session`, `step`, `emit`); a test is a flow whose steps are assertions.

## Shape of a test script
```python
from flowkit import emit, session, step
results = []

def check(page, name, fn):
    """Run one check; record the result instead of exiting, so one run reports everything."""
    try:
        fn(); results.append({"test": name, "ok": True})
    except Exception as e:
        results.append({"test": name, "ok": False, "error": str(e).splitlines()[0][:200]})
        page.screenshot(path=f"out/{name}.png")

with session(headless=True) as page:
    with step(page, "open app"):
        page.goto("http://localhost:3000")
    check(page, "login-form-visible", lambda: page.get_by_label("Email").wait_for(timeout=5000))
    check(page, "title", lambda: page.wait_for_function("document.title.includes('Dashboard')", timeout=5000))

failed = [r for r in results if not r["ok"]]
emit({"ok": not failed, "passed": len(results) - len(failed), "failed": failed})
raise SystemExit(0 if not failed else 3)
```
Only `step` aborts (the page itself did not load); `check` collects. The agent reads one short JSON result, then opens screenshots only for failures.

## Patterns
- **Local apps**: tests for the user's own app on `localhost` can use headless and a throwaway profile; the logged-in automation Chrome is for third-party sites.
- **Viewports**: `page.set_viewport_size({"width": 375, "height": 812})` per check for responsive tests.
- **Console and network errors**: `page.on("console", ...)` and `page.on("pageerror", ...)` to assert "no errors on load".
- **Visual checks**: take a screenshot and let Claude look only at the ones that failed or that you flag for review; pixel-diff tooling is better for large suites.
- **Test data**: create what you need at the start of the run and clean it up at the end; tests that depend on leftover state fail on the second run.
- **CI**: the script's exit code (0/3) plus its JSON line is enough for most CI systems.
