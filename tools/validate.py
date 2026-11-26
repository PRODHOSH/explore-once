#!/usr/bin/env python3
"""Validate every skill against the Agent Skills spec + our house rules. Stdlib only.

Checks: SKILL.md exists; frontmatter has name+description; name == folder name, is
lowercase-hyphen <=64 chars; description <=1024 chars and says when to use it; body
<500 lines; every relative file mentioned as `scripts/...`, `references/...`,
`assets/...` exists; python files compile; shared modules in sync.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise ValueError("missing YAML frontmatter")
    data, key = {}, None
    for line in m.group(1).splitlines():
        if re.match(r"^[A-Za-z_-]+:", line):
            key, _, val = line.partition(":")
            data[key.strip()] = val.strip().strip('"').strip("'")
        elif key and line.startswith((" ", "\t")):
            data[key] += " " + line.strip()
    return data


def main() -> int:
    errors = []
    skills = sorted(p for p in (ROOT / "skills").iterdir() if p.is_dir())
    for d in skills:
        md = d / "SKILL.md"
        if not md.exists():
            errors.append(f"{d.name}: SKILL.md missing"); continue
        text = md.read_text(encoding="utf-8")
        try:
            fm = frontmatter(text)
        except ValueError as e:
            errors.append(f"{d.name}: {e}"); continue
        name, desc = fm.get("name", ""), fm.get("description", "")
        if name != d.name: errors.append(f"{d.name}: name '{name}' != folder")
        if not NAME_RE.match(name) or len(name) > 64: errors.append(f"{d.name}: bad name format")
        if not desc: errors.append(f"{d.name}: empty description")
        if len(desc) > 1024: errors.append(f"{d.name}: description {len(desc)} chars (>1024)")
        if "use" not in desc.lower(): errors.append(f"{d.name}: description should say when to use the skill")
        if len(text.splitlines()) > 500: errors.append(f"{d.name}: SKILL.md over 500 lines")
        for rel in sorted(set(re.findall(r"`((?:scripts|references|assets)/[A-Za-z0-9_./-]+)`", text))):
            if not (d / rel).exists(): errors.append(f"{d.name}: referenced file missing: {rel}")
        for py in d.rglob("*.py"):
            try: compile(py.read_text(encoding="utf-8"), str(py), "exec")
            except SyntaxError as e: errors.append(f"{py.relative_to(ROOT)}: {e}")
        print(f"checked {d.name}: desc {len(desc)} chars, {len(text.splitlines())} lines")
    if subprocess.call([sys.executable, str(ROOT / "tools/sync_shared.py"), "--check"]) != 0:
        errors.append("shared modules out of sync")
    for e in errors: print("ERROR:", e)
    print("OK" if not errors else f"{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
