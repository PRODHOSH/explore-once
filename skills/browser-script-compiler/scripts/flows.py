#!/usr/bin/env python3
"""flows.py - a tiny library of compiled browser flows.

Why: the whole point of compiling a flow is reuse. Without a registry the next session
re-explores the site and pays the tokens again. Check `flows.py list` FIRST.

  flows.py list                          # name, description, params, health
  flows.py show NAME                     # metadata + path
  flows.py add PATH --name N --desc D    # copy a script into the library
  flows.py run NAME [-- script args]     # run it, record success/failure
  flows.py rm NAME

Library location: $EXPLORE_ONCE_HOME/flows (default ~/.explore-once/flows).
Exit code of `run` is the script's exit code (0/2/3/4, see flowkit.py).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HOME = Path(os.environ.get("EXPLORE_ONCE_HOME", str(Path.home() / ".explore-once")))
LIB = HOME / "flows"
MANIFEST = LIB / "manifest.json"


def load() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def save(data: dict) -> None:
    LIB.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    p = sub.add_parser("show"); p.add_argument("name")
    p = sub.add_parser("add"); p.add_argument("path"); p.add_argument("--name", required=True)
    p.add_argument("--desc", required=True, help="one line: what it does and the site it targets")
    p.add_argument("--params", default="", help="e.g. 'prompt, out_dir'")
    p = sub.add_parser("rm"); p.add_argument("name")
    p = sub.add_parser("run"); p.add_argument("name"); p.add_argument("rest", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    data = load()

    if a.cmd == "list":
        if not data:
            print("(no flows yet - explore the task once, then compile it)")
        for name, m in sorted(data.items()):
            print(f"{name:28} ok={m.get('ok', 0):<3} fail={m.get('fail', 0):<3} params=[{m.get('params', '')}]  {m.get('desc', '')}")
        return 0
    if a.cmd == "show":
        m = data.get(a.name)
        if not m:
            print(f"no such flow: {a.name}", file=sys.stderr); return 2
        print(json.dumps({**m, "path": str(LIB / m["file"])}, indent=2)); return 0
    if a.cmd == "add":
        src = Path(a.path)
        if not src.exists():
            print(f"missing file: {src}", file=sys.stderr); return 2
        LIB.mkdir(parents=True, exist_ok=True)
        dest = f"{a.name}.py"
        shutil.copy2(src, LIB / dest)
        kit = Path(__file__).with_name("flowkit.py")  # flows import it from their own folder
        if kit.exists():
            shutil.copy2(kit, LIB / "flowkit.py")
        data[a.name] = {**data.get(a.name, {}), "file": dest, "desc": a.desc, "params": a.params,
                        "created": data.get(a.name, {}).get("created", time.strftime("%Y-%m-%d")),
                        "updated": time.strftime("%Y-%m-%d")}
        save(data); print(f"saved {a.name} -> {LIB / dest}"); return 0
    if a.cmd == "rm":
        m = data.pop(a.name, None)
        if m:
            (LIB / m["file"]).unlink(missing_ok=True)
            save(data)
        return 0
    if a.cmd == "run":
        m = data.get(a.name)
        if not m:
            print(f"no such flow: {a.name}", file=sys.stderr); return 2
        rest = a.rest[1:] if a.rest[:1] == ["--"] else a.rest
        code = subprocess.call([sys.executable, str(LIB / m["file"])] + rest)
        key = "ok" if code == 0 else "fail"
        m[key] = m.get(key, 0) + 1
        m["last_run"] = time.strftime("%Y-%m-%d %H:%M"); m["last_exit"] = code
        save(data); return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
