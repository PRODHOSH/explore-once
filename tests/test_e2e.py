#!/usr/bin/env python3
"""End-to-end smoke tests against LOCAL fixtures only (no real websites, no logins).

Run:  python3 tests/test_e2e.py        (needs: playwright, pillow, Chrome)
Uses an isolated EXPLORE_ONCE_HOME and port so it never touches your real automation profile.
Covers: flowkit chrome launch + attach, the flow template, the failure-bundle contract
(exit 3), the login guard (exit 4), the flow library, gallery-harvest end to end, and the
image-generation flow against a fake chat page.
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import random
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = Path(tempfile.mkdtemp(prefix="proskills-test-"))
PORT = "9333"
ENV = {**os.environ, "EXPLORE_ONCE_HOME": str(TMP / "home"), "EXPLORE_ONCE_CDP_PORT": PORT}
FIX = TMP / "site"
FIX.mkdir()
fails = []


def build_fixtures() -> None:
    from PIL import Image
    rnd = random.Random(7)
    cards = []
    for i in range(1, 11):
        # distinct pictures: random blocks, so near-duplicate detection keeps them
        im = Image.new("RGB", (640, 480), (rnd.randint(0, 255),) * 3)
        for _ in range(12):
            x, y = rnd.randint(0, 560), rnd.randint(0, 400)
            im.paste((rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255)), (x, y, x + 80, y + 80))
        im.save(FIX / f"shot{i}.png")
        cards.append(f'<a href="/shot/{i}" title="Shot {i}"><img alt="Shot {i}" loading="lazy" width="320" height="240" '
                     f'srcset="/shot{i}.png 640w" style="display:block;margin:30px"></a>')
    # an exact duplicate of shot1 under another URL, and a tiny icon that must be ignored
    (FIX / "dup.png").write_bytes((FIX / "shot1.png").read_bytes())
    cards.append('<a href="/dup"><img alt="dup" width="320" height="240" src="/dup.png"></a>')
    cards.append('<img alt="icon" width="24" height="24" src="/shot2.png">')
    (FIX / "gallery.html").write_text("<html><body>" + "".join(cards) + "</body></html>")

    (FIX / "chat.html").write_text("""<html><body>
<div id="log"></div>
<div id="prompt-textarea" contenteditable="true" role="textbox" style="border:1px solid;min-height:30px"></div>
<button data-testid="send-button" onclick="go()">Send</button>
<script>
function go(){
  const text = document.getElementById('prompt-textarea').innerText;
  document.getElementById('log').textContent = 'working: ' + text;
  setTimeout(() => { const i = new Image(); i.width = 600; i.height = 600; i.src = '/shot3.png';
    document.body.appendChild(i); }, 1500);
}
</script></body></html>""")
    (FIX / "login.html").write_text("<html><body>please login</body></html>")


def run(args, **kw):
    return subprocess.run([sys.executable] + [str(a) for a in args], env=ENV, capture_output=True, text=True, timeout=180, **kw)


def last_json(proc):
    lines = [l for l in proc.stdout.strip().splitlines() if l.startswith("{")]
    return json.loads(lines[-1]) if lines else {}


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))
    if not cond:
        fails.append(name)


def main() -> int:
    build_fixtures()
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(FIX))
    handler.log_message = lambda *a, **k: None  # type: ignore[attr-defined]
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    S = ROOT / "skills"
    tpl = S / "browser-script-compiler/assets/flow_template.py"
    # the template imports flowkit from its own folder; copy it next to a scratch copy
    work = TMP / "work"; work.mkdir()
    (work / "flowkit.py").write_bytes((ROOT / "shared/flowkit.py").read_bytes())
    flow = work / "flow.py"; flow.write_bytes(tpl.read_bytes())

    # 1. template smoke test on a local page (fixture has an h1 we control)
    (FIX / "h1.html").write_text("<html><body><h1>Example Domain</h1></body></html>")
    p = run([flow, "--url", f"{base}/h1.html", "--out-dir", work / "o1", "--headless"])
    check("template flow passes (exit 0)", p.returncode == 0 and last_json(p).get("ok") is True, p.stdout + p.stderr)

    # 2. failure contract: wrong expectation -> exit 3 + bundle with screenshot and aria
    p = run([flow, "--url", f"{base}/h1.html", "--expect-heading", "Nope", "--out-dir", work / "o2", "--headless"])
    j = last_json(p)
    bundle = Path(j.get("bundle", "/nonexistent"))
    check("failed step exits 3 with bundle", p.returncode == 3 and (bundle / "screenshot.png").exists() and (bundle / "aria.txt").exists(), p.stdout + p.stderr)
    check("failure JSON names the step", j.get("step") == "assert heading", str(j))

    # 3. login guard: URL containing 'login' -> exit 4
    (FIX / "login").mkdir(exist_ok=True); (FIX / "login/index.html").write_text("please login")
    p = run([flow, "--url", f"{base}/login/", "--out-dir", work / "o3", "--headless"])
    check("login page exits 4 (needs human)", p.returncode == 4 and last_json(p).get("needs_human") is True, p.stdout + p.stderr)

    # 4. flow library round trip
    flows = S / "browser-script-compiler/scripts/flows.py"
    # use the skill's own synced copy of flows.py (it copies the flowkit sitting beside it)
    run([flows, "add", flow, "--name", "t", "--desc", "test flow", "--params", "url"])
    lst = run([flows, "list"]).stdout
    check("flows list shows flow", "test flow" in lst, lst)
    lib = Path(ENV["EXPLORE_ONCE_HOME"]) / "flows"  # flows.py add must bring flowkit.py along
    p = run([flows, "run", "t", "--", "--url", f"{base}/h1.html", "--out-dir", work / "o4", "--headless"])
    check("flows run executes and records ok", p.returncode == 0 and '"ok": 1' in (lib / "manifest.json").read_text(), p.stdout + p.stderr)

    # 5. gallery harvest: 10 unique + 1 dup + 1 icon -> expect 10, sheets made
    out = TMP / "gal"
    p = run([S / "gallery-harvest/scripts/harvest.py", f"{base}/gallery.html", "--out", out, "--headless", "--max", "50", "--scrolls", "6", "--patience", "2", "--pause-ms", "300"])
    j = last_json(p)
    check("harvest ok", p.returncode == 0 and j.get("ok"), p.stdout + p.stderr)
    check("harvest found 10 unique (dup removed, icon ignored)", j.get("images") == 10, str(j))
    check("harvest wrote sheets + index", len(j.get("sheets", [])) == 1 and (out / "index.json").exists() and (out / "images/001.png").exists(), str(j))
    if (out / "index.json").exists():
        idx = json.loads((out / "index.json").read_text())
        check("index keeps links and titles", idx[0]["link"] and idx[0]["title"].startswith("Shot"), str(idx[0]))

    # 6. image generation flow against a fake chat UI (selectors from the chatgpt entry match the fixture)
    sites = S / "web-image-generation/scripts/sites.json"
    cfg = json.loads(sites.read_text()); cfg.pop("_comment")
    test_sites = TMP / "gen"; test_sites.mkdir()
    cfg["chatgpt"]["url"] = f"{base}/chat.html"
    (test_sites / "sites.json").write_text(json.dumps(cfg))
    (test_sites / "flowkit.py").write_bytes((ROOT / "shared/flowkit.py").read_bytes())
    (test_sites / "generate_image.py").write_bytes((S / "web-image-generation/scripts/generate_image.py").read_bytes())
    p = run([test_sites / "generate_image.py", "--site", "chatgpt", "--prompt", "a red fox", "--out", TMP / "img", "--timeout", "40", "--min-side", "400"])
    j = last_json(p)
    files = j.get("files", [])
    check("image flow ok and saved a png", p.returncode == 0 and files and files[0]["file"].endswith(".png") and files[0]["bytes"] > 1000, p.stdout + p.stderr)

    run([ROOT / "shared/flowkit.py", "stop"])
    server.shutdown()
    print(f"\n{len(fails)} failure(s)" if fails else "\nall passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
