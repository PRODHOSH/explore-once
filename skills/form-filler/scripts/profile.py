#!/usr/bin/env python3
"""profile.py - the person's facts, stored locally, so forms get true and consistent answers.

Two files in $EXPLORE_ONCE_HOME/profile/ (default ~/.explore-once/profile/), mode 600:
  profile.json  structured facts: contact, education, experience, projects, clubs, skills ...
  answers.json  answers the person already APPROVED, tagged (why-hire, strengths, project-x ...)

  profile.py init                          create profile.json from the template (never overwrites)
  profile.py show [section]                print a section or everything
  profile.py get basics.email              read one value (dotted path, list index like projects.0.name)
  profile.py set basics.phone "+91 ..."    write one value (creates lists/dicts as needed)
  profile.py add projects '{"name": ...}'  append JSON to a list (projects, experience, voice.samples ...)
  profile.py missing                       which commonly asked fields are still empty
  profile.py save-answer --tags why-hire --q "Why should we hire you?" --a "..."
  profile.py find-answers "why hire"       previously approved answers matching words or tags
  profile.py facts                         compact digest for drafting (names, one-liners, stacks)

Nothing here leaves the machine. Do not commit the profile folder anywhere.
Exit codes: 0 ok, 2 bad input / missing profile.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, List

HOME = Path(os.environ.get("EXPLORE_ONCE_HOME", str(Path.home() / ".explore-once")))
DIR = HOME / "profile"
PROFILE, ANSWERS = DIR / "profile.json", DIR / "answers.json"
TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "profile.template.json"

COMMONLY_ASKED = [
    "basics.full_name", "basics.email", "basics.phone", "basics.location",
    "links.github", "links.linkedin", "links.resume_path",
    "education.0.school", "education.0.degree", "education.0.end",
    "projects.0.name", "projects.0.what_i_built",
    "availability.notice_period", "availability.start_date", "availability.work_authorization",
    "about.why_hire_notes", "about.career_goal",
]


def die(msg: str, code: int = 2) -> None:
    print(json.dumps({"ok": False, "error": msg}))
    sys.exit(code)


def read(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write(path: Path, data: Any) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)  # personal data: owner only


def need_profile() -> dict:
    if not PROFILE.exists():
        die("no profile yet. Run: profile.py init")
    return read(PROFILE, {})


def walk(data: Any, path: str, create: bool = False) -> Any:
    """Return (container, key) for a dotted path; ints index lists."""
    parts = path.split(".")
    cur = data
    for i, part in enumerate(parts[:-1]):
        nxt = parts[i + 1]
        cur = step(cur, part, [] if nxt.isdigit() else {}, create)
    return cur, parts[-1]


def step(cur: Any, key: str, fresh: Any, create: bool) -> Any:
    if isinstance(cur, list):
        idx = int(key)
        while create and len(cur) <= idx:
            cur.append({})
        return cur[idx]
    if key not in cur:
        if not create:
            raise KeyError(key)
        cur[key] = fresh
    return cur[key]


def get_path(data: Any, path: str) -> Any:
    cur = data
    for part in path.split("."):
        cur = cur[int(part)] if isinstance(cur, list) else cur[part]
    return cur


def is_empty(v: Any) -> bool:
    return v in ("", None, [], {})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    p = sub.add_parser("show"); p.add_argument("section", nargs="?")
    p = sub.add_parser("get"); p.add_argument("path")
    p = sub.add_parser("set"); p.add_argument("path"); p.add_argument("value")
    p = sub.add_parser("add"); p.add_argument("section"); p.add_argument("json")
    sub.add_parser("missing")
    p = sub.add_parser("save-answer"); p.add_argument("--q", required=True); p.add_argument("--a", required=True); p.add_argument("--tags", default="")
    p = sub.add_parser("find-answers"); p.add_argument("query")
    sub.add_parser("facts")
    a = ap.parse_args()

    if a.cmd == "init":
        if PROFILE.exists():
            print(json.dumps({"ok": True, "note": "profile already exists, left untouched", "path": str(PROFILE)})); return 0
        write(PROFILE, json.loads(TEMPLATE.read_text(encoding="utf-8")))
        print(json.dumps({"ok": True, "path": str(PROFILE), "next": "ask the person for their details and fill them with `set` / `add`"})); return 0

    if a.cmd == "show":
        d = need_profile()
        print(json.dumps(d.get(a.section) if a.section else d, indent=2, ensure_ascii=False)); return 0

    if a.cmd == "get":
        try:
            v = get_path(need_profile(), a.path)
        except (KeyError, IndexError, ValueError):
            die(f"no value at {a.path}")
        print(json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v); return 0

    if a.cmd == "set":
        d = need_profile()
        try:
            container, key = walk(d, a.path, create=True)
            try:
                value = json.loads(a.value)  # allows lists/objects/numbers; plain text falls through
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    value = a.value  # keep phone numbers, years and grades exactly as typed
            except ValueError:
                value = a.value
            if isinstance(container, list):
                idx = int(key)
                while len(container) <= idx:
                    container.append("")
                container[idx] = value
            else:
                container[key] = value
        except (KeyError, IndexError, ValueError, TypeError):
            die(f"cannot set {a.path}")
        write(PROFILE, d); print(json.dumps({"ok": True, "set": a.path})); return 0

    if a.cmd == "add":
        d = need_profile()
        try:
            item = json.loads(a.json)
        except ValueError:
            die("add expects JSON, e.g. '{\"name\": \"My project\"}' or '\"a sentence\"'")
        try:
            container, key = walk(d, a.section, create=True)
            if isinstance(container, list):
                die(f"{a.section}: point at a list by name, like projects or voice.samples")
            container.setdefault(key, [])
            if not isinstance(container[key], list):
                die(f"{a.section} is not a list")
            container[key].append(item)
            count = len(container[key])
        except (KeyError, IndexError, ValueError, TypeError):
            die(f"cannot add to {a.section}")
        write(PROFILE, d); print(json.dumps({"ok": True, "section": a.section, "count": count})); return 0

    if a.cmd == "missing":
        d = need_profile()
        gaps: List[str] = []
        for path in COMMONLY_ASKED:
            try:
                if is_empty(get_path(d, path)):
                    gaps.append(path)
            except (KeyError, IndexError, ValueError):
                gaps.append(path)
        print(json.dumps({"ok": True, "missing": gaps})); return 0

    if a.cmd == "save-answer":
        answers = read(ANSWERS, [])
        answers.append({"question": a.q, "answer": a.a, "tags": [t.strip().lower() for t in a.tags.split(",") if t.strip()], "saved": time.strftime("%Y-%m-%d")})
        write(ANSWERS, answers); print(json.dumps({"ok": True, "saved": len(answers)})); return 0

    if a.cmd == "find-answers":
        words = [w for w in a.query.lower().replace("-", " ").split() if len(w) > 2]
        hits = []
        for ans in read(ANSWERS, []):
            hay = (ans["question"] + " " + " ".join(ans["tags"])).lower().replace("-", " ")
            score = sum(w in hay for w in words)
            if score:
                hits.append((score, ans))
        hits.sort(key=lambda t: -t[0])
        print(json.dumps({"ok": True, "answers": [h[1] for h in hits[:5]]}, ensure_ascii=False)); return 0

    if a.cmd == "facts":
        d = need_profile()
        out = {"name": d["basics"].get("full_name"), "about": d.get("about", {}),
               "projects": [{k: p.get(k) for k in ("name", "one_line", "problem", "what_i_built", "stack", "my_role", "outcome", "metrics", "links") if not is_empty(p.get(k))} for p in d.get("projects", []) if p.get("name")],
               "experience": [e for e in d.get("experience", []) if e.get("org")],
               "clubs_and_activities": [c for c in d.get("clubs_and_activities", []) if c.get("name")],
               "achievements": d.get("achievements", []), "skills": d.get("skills", {}), "voice": d.get("voice", {})}
        print(json.dumps(out, indent=1, ensure_ascii=False)); return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
