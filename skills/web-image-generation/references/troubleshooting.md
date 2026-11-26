# Troubleshooting

## "Why not attach to my normal Chrome?"
Chrome 136+ ignores `--remote-debugging-port` when the profile is the default one (a security hardening against cookie theft). The scripts therefore use a dedicated profile at `~/.pro-skills/chrome-profile` (override with `PRO_SKILLS_HOME`). Sign in once; it persists like any Chrome profile. It is a separate window from your daily Chrome; you can keep both open.

## Checklist
| Symptom | Likely cause | Fix |
|---|---|---|
| exit 2 "playwright is not installed" | missing dependency | `python3 -m pip install playwright` |
| exit 2 "Chrome not found" | non-standard install | set `CHROME_BIN=/path/to/chrome` |
| exit 4 login | session expired | `python3 scripts/flowkit.py start <site url>`, sign in, re-run |
| exit 3 "find input box" | site UI changed | `--inspect`, edit `scripts/sites.json` |
| exit 3 "wait for generated image", bundle shows a refusal or limit message | policy / quota | adjust prompt (do not evade policy) or wait for quota reset |
| image saved is small or a thumbnail | picked the preview | raise `--min-side`; open the tab with `--keep-open` and inspect |
| wrong account | profile signed in as someone else | sign out/in inside the automation Chrome window |

## Port or profile in use
`python3 scripts/flowkit.py status` shows whether the debugging port answers. `flowkit.py stop` quits the automation Chrome (macOS/Linux). Use `PRO_SKILLS_CDP_PORT` to change the port.
