#!/usr/bin/env python3
"""
sync-apps.py
────────────
Extract CHANGELOG metadata from SAIL app source files and write
manifest .changelog files into apps/. Run this whenever an app
source changes, then commit and push the resulting apps/*.changelog
files to trigger the detect-changes workflow.

The source files live OUTSIDE this repo at $SAIL_APP_SOURCE
(default ~/Documents/SAIL/Projects/) and are deliberately NOT
copied here, because they contain hardcoded API keys that must
never be committed. Only the CHANGELOG comments — which contain
no secrets — get extracted.
"""

import os
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = REPO_ROOT / "apps"
SOURCE_DIR = Path(
    os.environ.get("SAIL_APP_SOURCE", os.path.expanduser("~/Documents/SAIL/Projects"))
)

APPS = {
    "SAIL-Helm-v9.jsx":          "SAIL-Helm-v9",
    "SuperTeacher-v6.jsx":       "SuperTeacher-v6",
    "SuperStudent-v5.jsx":       "SuperStudent-v5",
    "compass-v3.jsx":            "compass-v3",
    "compass-counsellor-v3.jsx": "compass-counsellor-v3",
    "sail-ielts-v5.jsx":         "sail-ielts-v5",
    "LifeOS-v2.jsx":             "LifeOS-v2",
    "sail-wealth-v10.html":      "sail-wealth-v10",
}


def extract(src: str) -> list[str]:
    """Pull CHANGELOG comments from the top of an app source file."""
    lines = src.split("\n")[:80]
    out = []
    for line in lines:
        m = re.match(r"\s*//\s*(CHANGELOG[^:]*:.*)", line)
        if m:
            out.append(m.group(1).strip())
    if not out:
        for line in lines:
            if re.search(r"(added|removed|rebuilt|updated|fixed|new)\b", line, re.IGNORECASE):
                m2 = re.match(r"\s*//\s*(.*)", line)
                if m2 and len(m2.group(1)) > 10:
                    out.append(m2.group(1).strip())
    return out


def main() -> int:
    APPS_DIR.mkdir(exist_ok=True)
    print(f"Source: {SOURCE_DIR}")
    print(f"Output: {APPS_DIR}")
    print()
    missing = 0
    for source_name, app_key in APPS.items():
        src_path = SOURCE_DIR / source_name
        if not src_path.exists():
            print(f"  miss   {source_name}  (not at {src_path})")
            missing += 1
            continue
        try:
            content = src_path.read_text(errors="replace")
        except Exception as e:
            print(f"  error  {source_name}  {e}")
            missing += 1
            continue
        entries = extract(content)
        out_path = APPS_DIR / f"{app_key}.changelog"
        body = "\n".join(entries) if entries else "(no CHANGELOG comments found in source)"
        out_path.write_text(body + "\n")
        print(f"  ok     {out_path.relative_to(REPO_ROOT)}  ({len(entries)} entries)")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
