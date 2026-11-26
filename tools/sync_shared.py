#!/usr/bin/env python3
"""Copy shared/*.py into every skills/*/scripts/ folder (skills must be self-contained,
because users install a single skill folder). `--check` fails if any copy has drifted."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    check = "--check" in sys.argv
    drift = []
    for src in sorted((ROOT / "shared").glob("*.py")):
        for scripts in sorted((ROOT / "skills").glob("*/scripts")):
            dest = scripts / src.name
            if check:
                if not dest.exists() or dest.read_bytes() != src.read_bytes():
                    drift.append(str(dest.relative_to(ROOT)))
            else:
                shutil.copy2(src, dest)
    if drift:
        print("out of sync (run tools/sync_shared.py):\n  " + "\n  ".join(drift))
        return 1
    print("shared files in sync" if check else "synced")
    return 0


if __name__ == "__main__":
    sys.exit(main())
