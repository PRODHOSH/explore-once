#!/usr/bin/env python3
"""Local-fixture tests for form-filler and ui-regression-suite.

Run:  python3 tests/test_more.py      (needs playwright, pillow, Chrome; isolated profile/port)
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "skills"
TMP = Path(tempfile.mkdtemp(prefix="proskills-test2-"))
ENV = {**os.environ, "PRO_SKILLS_HOME": str(TMP / "home"), "PRO_SKILLS_CDP_PORT": "9334"}
SITE = TMP / "site"; SITE.mkdir()
fails = []

FORM = """<html><head><title>Apply</title></head><body><h1>Apply</h1>
<form id="f" onsubmit="event.preventDefault(); document.getElementById('res').textContent='Thanks '+document.getElementById('n').value">
<label for="n">Full name *</label><input id="n" name="full_name" required>
<label for="e">Email address</label><input id="e" name="email" type="email">
<input name="phone" placeholder="Phone number">
<label for="c">Country</label><select id="c" name="country"><option>India</option><option>United Kingdom</option></select>
<fieldset><legend>Plan</legend>
 <label><input type="radio" name="plan" value="free"> Free</label>
 <label><input type="radio" name="plan" value="pro"> Pro</label></fieldset>
<label><input type="checkbox" name="news"> Subscribe to newsletter</label>
<label for="m">Message</label><textarea id="m" name="message"></textarea>
<label for="p">Password</label><input id="p" type="password" name="pw">
<label for="t">Referral code *</label><input id="t" name="ref" required>
<button type="submit">Apply now</button></form><div id="res"></div></body></html>"""

GOOD = """<html><head><title>Home</title></head><body><nav><a href="/">Home</a></nav><main><h1>Welcome</h1>
<img src="/ok.png" alt="ok" width="100" height="100"><p>Hello world</p></main></body></html>"""
BAD = """<html><body><main><div style="width:3000px">wide</div>
<img src="/missing.png" width="100" height="100"><img src="/ok.png" width="100" height="100">
<button></button><script>console.error('boom')</script></main></body></html>"""


def run(args, **kw):
    return subprocess.run([sys.executable] + [str(a) for a in args], env=ENV, capture_output=True, text=True, timeout=240, **kw)


def last_json(p):
    lines = [l for l in p.stdout.strip().splitlines() if l.startswith("{")]
    return json.loads(lines[-1]) if lines else {}


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))
    if not cond:
        fails.append(name)


def main() -> int:
    from PIL import Image
    Image.new("RGB", (100, 100), (200, 50, 50)).save(SITE / "ok.png")
    for n, c in {"form.html": FORM, "good.html": GOOD, "bad.html": BAD}.items():
        (SITE / n).write_text(c)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    handler.log_message = lambda *a, **k: None  # type: ignore[attr-defined]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    # ---------------- form-filler
    ff = S / "form-filler/scripts/fill_form.py"
    data = TMP / "me.json"
    data.write_text(json.dumps({"Full name": "Ada Lovelace", "Email": "ada@example.com", "Phone": "555-0100", "Country": "United Kingdom",
                                "Plan": "Pro", "Subscribe to newsletter": True, "message": "Hi there", "Password": "hunter2", "Nonexistent field": "x"}))
    p = run([ff, "--url", f"{base}/form.html", "--data", data, "--out", TMP / "f1"])
    r = last_json(p)
    keys = {f["key"] for f in r.get("filled", [])}
    check("review phase ok, not submitted", p.returncode == 0 and r.get("submitted") is False, p.stdout + p.stderr)
    check("filled name/email/phone/country/plan/newsletter/message", keys == {"Full name", "Email", "Phone", "Country", "Plan", "Subscribe to newsletter", "message"}, str(r.get("filled")))
    check("password refused, not filled", "Password" in r.get("refused_sensitive", []) and "Password" not in keys, str(r))
    check("unmatched key reported", r.get("unmatched_keys") == ["Nonexistent field"], str(r.get("unmatched_keys")))
    check("required field not provided is flagged", any("Referral" in x for x in r.get("required_not_provided", [])), str(r.get("required_not_provided")))
    code = r.get("approval_code", "")
    p = run([ff, "--url", f"{base}/form.html", "--data", data, "--out", TMP / "f2", "--submit", "deadbeef"])
    check("wrong approval code refused (exit 2)", p.returncode == 2, p.stdout)
    p = run([ff, "--url", f"{base}/form.html", "--data", data, "--out", TMP / "f3", "--submit", code])
    check("submit blocked while required field missing (exit 3)", p.returncode == 3 and last_json(p).get("submitted") is False, p.stdout)
    data.write_text(json.dumps({**json.loads(data.read_text()), "Referral code": "ABC"}))
    p = run([ff, "--url", f"{base}/form.html", "--data", data, "--out", TMP / "f4"])
    code2 = last_json(p)["approval_code"]
    check("editing data changes the approval code", code2 != code)
    p = run([ff, "--url", f"{base}/form.html", "--data", data, "--out", TMP / "f5", "--submit", code2])
    r = last_json(p)
    check("submit with valid code works", p.returncode == 0 and r.get("submitted") and "Thanks Ada Lovelace" in r.get("page_text_start", ""), p.stdout + p.stderr)

    # ---------------- ui-regression-suite
    rs = S / "ui-regression-suite/scripts/run_suite.py"
    bad_suite = {"base_url": base, "viewports": {"mobile": [375, 700]}, "pages": [{"name": "bad", "path": "/bad.html"}]}
    (TMP / "bad_suite.json").write_text(json.dumps(bad_suite))
    p = run([rs, TMP / "bad_suite.json", "--out", TMP / "r1", "--baselines", TMP / "b1"])
    text = p.stdout + (TMP / "r1/report.md").read_text()
    check("bad page fails (exit 3)", p.returncode == 3, p.stdout)
    for needle in ("horizontal overflow", "broken image", "boom", "HTTP 404"):
        check(f"detects: {needle}", needle in text, text[-600:])
    check("warns on missing alt / title / h1 / unnamed button", all(w in text for w in ("image without alt", "missing <title>", "no <h1>", "unnamed link/button")), text[-700:])
    good_suite = {"base_url": base, "viewports": {"desktop": [900, 600]}, "pages": [{"name": "home", "path": "/good.html", "expect_text": ["Welcome"], "expect_selector": ["nav"]}]}
    (TMP / "good_suite.json").write_text(json.dumps(good_suite))
    p = run([rs, TMP / "good_suite.json", "--out", TMP / "r2", "--baselines", TMP / "b2"])
    check("first run creates baseline and passes", p.returncode == 0 and last_json(p)["new_baselines"] == ["home-desktop"], p.stdout + p.stderr)
    p = run([rs, TMP / "good_suite.json", "--out", TMP / "r2", "--baselines", TMP / "b2"])
    check("second run passes against baseline", p.returncode == 0 and last_json(p)["new_baselines"] == [], p.stdout + p.stderr)
    (SITE / "good.html").write_text(GOOD.replace("Hello world", "Hello world, now with a much longer changed paragraph " * 10).replace("<main>", "<main style='background:#fdd'>"))
    p = run([rs, TMP / "good_suite.json", "--out", TMP / "r2", "--baselines", TMP / "b2"])
    check("visual change fails with diff image", p.returncode == 3 and (TMP / "r2/diffs/home-desktop.png").exists(), p.stdout)
    p = run([rs, TMP / "good_suite.json", "--out", TMP / "r2", "--baselines", TMP / "b2", "--update"])
    check("--update accepts new baseline", p.returncode == 0, p.stdout)

    run([ROOT / "shared/flowkit.py", "stop"])
    srv.shutdown()
    print(f"\n{len(fails)} failure(s)" if fails else "\nall passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
