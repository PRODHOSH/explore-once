#!/usr/bin/env python3
"""fill_form.py - fill a web form from a JSON file, then STOP for your approval.

Two phases, on purpose:
  1) review (default): fills the form, writes review.json + a screenshot, prints an
     approval code. Nothing is submitted.
  2) submit: only runs with the approval code from phase 1 (it is a hash of the page URL and
     the data, so editing the data invalidates it). Re-fills, then clicks submit.

  python3 fill_form.py --url https://example.com/apply --data me.json --out ./form-out
  python3 fill_form.py --url https://example.com/apply --data me.json --out ./form-out --submit 3fa91c0d

me.json: {"Full name": "Ada Lovelace", "Email": "ada@example.com", "Country": "United Kingdom",
          "Plan": "Pro", "Subscribe to newsletter": true, "Resume": "/path/cv.pdf"}
Keys are matched to fields by label / placeholder / aria-label / name (fuzzy, unique 1:1).

Never fills password, card, CVV or SSN-like fields: it reports them so the person enters them.
Handles single-page forms. Multi-step wizards: run once per step with --no-submit-check.
Exit codes: 0 ok, 2 setup/approval problem, 3 step failed, 4 needs a human.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flowkit import emit, human, looks_like_login, session, setup_error, step  # noqa: E402

COLLECT_JS = """() => {
  const vis = e => { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
                     return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const labels = el => {
    const t = [];
    if (el.labels) for (const l of el.labels) t.push(l.innerText);
    const al = el.getAttribute('aria-label'); if (al) t.push(al);
    const lb = el.getAttribute('aria-labelledby');
    if (lb) for (const id of lb.split(/\\s+/)) { const n = document.getElementById(id); if (n) t.push(n.innerText); }
    const ph = el.getAttribute('placeholder'); if (ph) t.push(ph);
    return t.map(x => (x || '').replace(/\\*/g, ' ').trim()).filter(Boolean);
  };
  const out = []; let i = 0;
  for (const el of document.querySelectorAll('input, select, textarea')) {
    const type = (el.getAttribute('type') || el.tagName).toLowerCase();
    if (['hidden', 'submit', 'button', 'reset', 'image'].includes(type)) continue;
    if (type !== 'file' && !vis(el)) continue;
    el.setAttribute('data-pf-idx', i);
    const fs = el.closest('fieldset'); const lg = fs && fs.querySelector('legend');
    out.push({idx: i, tag: el.tagName.toLowerCase(), type, name: el.name || '', id: el.id || '',
              ac: el.getAttribute('autocomplete') || '', labels: labels(el), group: lg ? lg.innerText.trim() : '',
              options: el.tagName === 'SELECT' ? Array.from(el.options).map(o => o.text.trim()) : [],
              required: el.required || el.getAttribute('aria-required') === 'true', value: el.value || '', checked: !!el.checked});
    i++;
  }
  return out;
}"""

SENSITIVE_RE = re.compile(r"passw|passcode|cvv|cvc|card[-_ ]?num|cc[-_ ]?(num|number|csc)|security[-_ ]?code|ssn|social[-_ ]?security|iban|routing", re.I)


def norm(s: str) -> str:
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s or "")
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def score(key: str, descs: List[str]) -> int:
    nk = norm(key)
    kt = set(nk.split())
    best = 0
    for d in descs:
        nd = norm(d)
        if not nd:
            continue
        dt = set(nd.split())
        if nd == nk:
            s = 100
        elif kt and kt <= dt:
            s = 80 - len(dt - kt)
        elif dt and dt <= kt:
            s = 60 - len(kt - dt)
        elif min(len(nk), len(nd)) >= 4 and (f" {nk} " in f" {nd} " or f" {nd} " in f" {nk} "):
            s = 40  # whole-word containment only; tiny ids like "t" must never match by substring
        else:
            s = 0
        best = max(best, s)
    return best


def build_fields(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge radios / multi-checkbox with the same name into one group field."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for f in raw:
        if f["type"] in ("radio", "checkbox") and f["name"]:
            groups.setdefault(f["type"] + ":" + f["name"], []).append(f)
    fields: List[Dict[str, Any]] = []
    seen = set()
    for f in raw:
        gk = f["type"] + ":" + f["name"]
        if gk in groups and (f["type"] == "radio" or len(groups[gk]) > 1):
            if gk in seen:
                continue
            seen.add(gk)
            members = groups[gk]
            descs = [m["group"] for m in members if m["group"]] + [f["name"]]
            fields.append({"kind": f["type"] + "-group", "members": members, "descs": descs,
                           "required": any(m["required"] for m in members), "label": (members[0]["group"] or f["name"])})
        else:
            descs = f["labels"] + [f["name"], f["id"]]
            if f["group"]:
                descs.append(f["group"])
            fields.append({"kind": f["type"] if f["tag"] == "input" else f["tag"], "members": [f], "descs": descs,
                           "required": f["required"], "label": (f["labels"] or [f["name"] or f["id"] or f["type"]])[0]})
    return fields


def is_sensitive(field: Dict[str, Any]) -> bool:
    m = field["members"][0]
    return m["type"] == "password" or m["ac"].startswith("cc-") or bool(SENSITIVE_RE.search(" ".join(field["descs"] + [m["name"], m["id"]])))


def match(data: Dict[str, Any], fields: List[Dict[str, Any]]) -> Tuple[List[Tuple[str, Dict[str, Any]]], List[str]]:
    pairs = sorted(((score(k, f["descs"]), k, i) for k in data for i, f in enumerate(fields)), reverse=True)
    used_k, used_f, chosen = set(), set(), []
    for s, k, i in pairs:
        if s < 40 or k in used_k or i in used_f:
            continue
        used_k.add(k); used_f.add(i); chosen.append((k, fields[i]))
    return chosen, [k for k in data if k not in used_k]


def pick_option(wanted: str, options: List[str]) -> Optional[str]:
    nw = norm(wanted)
    for o in options:
        if norm(o) == nw:
            return o
    cands = [o for o in options if nw and (nw in norm(o) or norm(o) in nw) and norm(o)]
    return cands[0] if len(cands) == 1 else None


def apply_value(page: Any, key: str, field: Dict[str, Any], value: Any) -> str:
    """Fill one field; returns a short description of what was set, or raises."""
    kind, members = field["kind"], field["members"]
    loc = lambda m: page.locator(f'[data-pf-idx="{m["idx"]}"]')  # noqa: E731
    if kind == "radio-group":
        for m in members:
            opts = m["labels"] + [m["value"]]
            if any(norm(str(value)) == norm(o) for o in opts if o):
                loc(m).check(); return str(value)
        raise ValueError(f"no radio option matches {value!r}; options: {[m['labels'][:1] for m in members]}")
    if kind == "checkbox-group":
        wanted = value if isinstance(value, list) else [value]
        for m in members:
            on = any(norm(str(w)) in [norm(x) for x in m["labels"] + [m["value"]]] for w in wanted)
            loc(m).set_checked(on)
        return ", ".join(map(str, wanted))
    m = members[0]
    if kind == "checkbox":
        loc(m).set_checked(bool(value)); return str(bool(value))
    if kind == "select":
        opt = pick_option(str(value), m["options"])
        if opt is None:
            raise ValueError(f"no option matches {value!r}; options: {m['options'][:12]}")
        loc(m).select_option(label=opt); return opt
    if kind == "file":
        p = Path(str(value)).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"file not found: {p}")
        loc(m).set_input_files(str(p)); return p.name
    loc(m).fill(str(value)); return str(value)


def find_submit(page: Any, selector: Optional[str]) -> Optional[Tuple[Any, str]]:
    cands = [page.locator(selector)] if selector else [
        page.locator("button[type=submit]"), page.locator("input[type=submit]"),
        page.get_by_role("button", name=re.compile(r"^(submit|send|apply|register|sign up|continue|save|book|request)", re.I))]
    for c in cands:
        for i in range(min(c.count(), 3)):
            el = c.nth(i)
            if el.is_visible():
                return el, (el.inner_text().strip() or el.get_attribute("value") or "submit")[:60]
    return None


def fill_everything(page: Any, data: Dict[str, Any]) -> Dict[str, Any]:
    fields = build_fields(page.evaluate(COLLECT_JS))
    chosen, unmatched = match(data, fields)
    filled, refused, errors = [], [], []
    matched_ids = set()
    for key, field in chosen:
        matched_ids.add(id(field))
        if is_sensitive(field):
            refused.append(key); continue
        try:
            shown = apply_value(page, key, field, data[key])
            filled.append({"key": key, "field": field["label"], "value": shown})
        except Exception as exc:  # noqa: BLE001
            errors.append({"key": key, "field": field["label"], "error": str(exc).splitlines()[0][:200]})
    missing_required = [f["label"] for f in fields if f["required"] and id(f) not in matched_ids]
    sensitive_unfilled = [f["label"] for f in fields if is_sensitive(f)]
    return {"filled": filled, "errors": errors, "unmatched_keys": unmatched, "refused_sensitive": refused,
            "required_not_provided": missing_required, "sensitive_fields_for_you": sensitive_unfilled}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True)
    ap.add_argument("--data", required=True, help="JSON file: {field label: value}")
    ap.add_argument("--out", default="./form-out")
    ap.add_argument("--submit", metavar="CODE", help="approval code printed by the review phase")
    ap.add_argument("--submit-selector", help="CSS selector of the submit button if auto-detection is wrong")
    ap.add_argument("--allow-missing", action="store_true", help="submit even if required fields were not provided")
    ap.add_argument("--keep-open", action="store_true")
    args = ap.parse_args()

    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(Path(args.data).read_text(encoding="utf-8"))
        assert isinstance(data, dict) and data
    except Exception:
        setup_error("--data must be a JSON object file like {\"Email\": \"a@b.c\"}")
    code = hashlib.sha256((args.url + "\n" + json.dumps(data, sort_keys=True)).encode()).hexdigest()[:8]
    if args.submit and args.submit != code:
        setup_error("Approval code does not match this URL + data. Re-run the review phase and show the person the new review.", expected_changed=True)

    with session(keep_open=args.keep_open) as page:
        with step(page, "open form", out):
            page.goto(args.url, wait_until="domcontentloaded", timeout=45_000)
            page.wait_for_timeout(800)
            if looks_like_login(page):
                human("Login required. Run `flowkit.py start <url>`, sign in, then re-run.")
        with step(page, "fill fields", out):
            report = fill_everything(page, data)
        with step(page, "locate submit button", out):
            found = find_submit(page, args.submit_selector)
            if not found:
                raise RuntimeError("no visible submit button found; pass --submit-selector")
            button, button_text = found

        if not args.submit:
            shot = out / "review.png"
            with step(page, "screenshot for review", out):
                page.screenshot(path=str(shot), full_page=True)
            review = {"url": args.url, "approval_code": code, "submit_button": button_text, **report, "screenshot": str(shot)}
            (out / "review.json").write_text(json.dumps(review, indent=2), encoding="utf-8")
            emit({"ok": True, "phase": "review", "submitted": False, **review, "next": "Show the person review.png and the lists; submit only with their go-ahead: re-run with --submit " + code})
            return

        if (report["errors"] or (report["required_not_provided"] and not args.allow_missing)):
            emit({"ok": False, "phase": "submit", "submitted": False, "reason": "form not fully fillable; see lists", **report})
            sys.exit(3)
        with step(page, "click submit", out):
            before = page.url
            button.click()
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            page.wait_for_timeout(500)
        shot = out / "after-submit.png"
        with step(page, "screenshot result", out):
            page.screenshot(path=str(shot), full_page=True)
            body = page.locator("body").inner_text()[:300].replace("\n", " ")
        emit({"ok": True, "phase": "submit", "submitted": True, "url_before": before, "url_after": page.url,
              "page_text_start": body, "screenshot": str(shot)})


if __name__ == "__main__":
    main()
