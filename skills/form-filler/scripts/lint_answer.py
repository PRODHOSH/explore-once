#!/usr/bin/env python3
"""lint_answer.py - check a drafted form answer before it goes into a form.

Catches what makes written answers sound machine-made or untrue:
  * em dashes and en dashes, exclamation marks, emoji, markdown (a plain text box is not a README)
  * stock phrases ("passionate", "leverage", "I am excited to", "proven track record", ...)
  * numbers that are NOT in the person's profile (invented metrics are the worst failure)
  * answers over the field's character limit

  python3 lint_answer.py --text "I built a tracker for my hostel mess." --max-chars 400
  python3 lint_answer.py --file answer.txt --allow 2026 --allow "Acme"

Facts come from $EXPLORE_ONCE_HOME/profile/{profile,answers}.json. A number is "supported" when
the same digits appear in those files (or in an --allow value, e.g. a year printed on the form).
Prints one JSON line; exit 0 when clean, 3 when there are problems.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

HOME = Path(os.environ.get("EXPLORE_ONCE_HOME", str(Path.home() / ".explore-once")))
PROFILE_DIR = HOME / "profile"

# Phrases that read as boilerplate. Matched case-insensitively as whole words/phrases.
BANNED = [
    "passionate", "passion for", "leverage", "leveraging", "delve", "seamless", "seamlessly", "robust",
    "cutting-edge", "cutting edge", "state-of-the-art", "game-changer", "game changer", "synergy",
    "fast-paced", "dynamic environment", "proven track record", "team player", "hard-working", "hardworking",
    "detail-oriented", "results-driven", "self-starter", "go-getter", "think outside the box",
    "i am excited to", "i'm excited to", "i am thrilled", "i'm thrilled", "i am eager to", "eager to contribute",
    "in today's", "in the ever-evolving", "ever-evolving", "rapidly evolving", "world of technology",
    "testament to", "tapestry", "navigate the landscape", "unlock the potential", "realm of",
    "i believe i would be a great fit", "perfect fit", "ideal candidate", "bring to the table",
    "take it to the next level", "elevate", "spearhead", "utilize", "utilise", "furthermore", "moreover",
    "it is worth noting", "needless to say", "at the end of the day", "dive into", "deep dive",
    "i am writing to express", "to whom it may concern", "esteemed", "honed my skills",
]
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐✅❌]")
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def load_facts() -> str:
    parts = []
    for name in ("profile.json", "answers.json"):
        p = PROFILE_DIR / name
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))
    return "\n".join(parts)


def lint(text: str, facts: str = "", allow: Optional[Iterable[str]] = None, max_chars: int = 0) -> List[str]:
    problems: List[str] = []
    if "—" in text or "–" in text:
        problems.append("contains an em or en dash: use a comma, a full stop, or rewrite the sentence")
    if "!" in text:
        problems.append("contains an exclamation mark")
    if EMOJI_RE.search(text):
        problems.append("contains emoji")
    if re.search(r"(\*\*|__|^#{1,6}\s|^\s*[-*•]\s)", text, re.M):
        problems.append("contains markdown or bullets; write plain sentences unless the field clearly wants a list")
    low = text.lower()
    for phrase in BANNED:
        if re.search(r"(?<![\w-])" + re.escape(phrase) + r"(?![\w-])", low):
            problems.append(f"stock phrase: '{phrase}'")
    if re.search(r"\bnot (?:just|only|merely)\b[^.]{0,60}\bbut (?:also )?\b", low):
        problems.append("'not just X but Y' construction (reads as machine-written)")
    if re.search(r"\b(\w+), (\w+),? and (\w+)\b", text) and len(text) < 160:
        pass  # short lists are fine; we only flag stock phrases above
    haystack = (facts + " " + " ".join(allow or [])).lower()
    flat = re.sub(r"(?<=\d),(?=\d)", "", haystack)
    for m in NUMBER_RE.finditer(text):
        raw = m.group(0).rstrip(".,")
        num = raw.replace(",", "")
        if not re.search(r"(?<![\d.])" + re.escape(num) + r"(?![\d])", flat):
            problems.append(f"number '{raw}' is not in the profile; remove it or ask the person for the real figure")
    if max_chars and len(text) > max_chars:
        problems.append(f"{len(text)} characters, limit is {max_chars}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--text")
    g.add_argument("--file")
    ap.add_argument("--max-chars", type=int, default=0)
    ap.add_argument("--allow", action="append", default=[], help="extra text that counts as a known fact (e.g. a year or company name from the form)")
    args = ap.parse_args()
    text = args.text if args.text is not None else Path(args.file).read_text(encoding="utf-8")
    problems = lint(text.strip(), load_facts(), args.allow, args.max_chars)
    print(json.dumps({"ok": not problems, "chars": len(text.strip()), "problems": problems}, ensure_ascii=False, separators=(",", ":")))
    return 0 if not problems else 3


if __name__ == "__main__":
    sys.exit(main())
