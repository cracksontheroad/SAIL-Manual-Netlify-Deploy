#!/usr/bin/env python3
"""
sync-apps.py
────────────
Extract CHANGELOG manifests from SAIL app source files into apps/.

Auto-discovers the latest version of each app — no version numbers
baked into manifest filenames. Manifests are stable: `apps/SAIL-Helm.changelog`,
`apps/SuperTeacher.changelog`, etc. When SAIL-Helm-v9.jsx becomes
SAIL-Helm-v10.jsx, the pipeline picks up the new file automatically.

Source files live OUTSIDE this repo at $SAIL_APP_SOURCE
(default ~/Documents/SAIL/Projects/) and are deliberately NOT
copied here, because they contain hardcoded API keys.
"""

import os
import re
from pathlib import Path
from typing import Optional, List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = REPO_ROOT / "apps"
SOURCE_DIR = Path(
    os.environ.get("SAIL_APP_SOURCE", os.path.expanduser("~/Documents/SAIL/Projects"))
)

APPS = [
    {"manifest": "SAIL-Helm",          "glob": "SAIL-Helm-v*.jsx",           "manual": "SAIL-Helm-Manual.html"},
    {"manifest": "SuperTeacher",       "glob": "SuperTeacher-v*.jsx",        "manual": "SuperTeacher-Manual.html"},
    {"manifest": "SuperStudent",       "glob": "SuperStudent-v*.jsx",        "manual": "SuperStudent-Manual.html"},
    {"manifest": "Compass",            "glob": "compass-v*.jsx",             "manual": "Compass-Manual.html"},
    {"manifest": "Compass-Counsellor", "glob": "compass-counsellor-v*.jsx",  "manual": "Compass-Counsellor-Manual.html"},
    {"manifest": "IELTS-OS",           "glob": "sail-ielts-v*.jsx",          "manual": "IELTS-OS-Manual.html"},
    {"manifest": "Life-OS",            "glob": "LifeOS-v*.jsx",              "manual": "Life-OS-Manual.html"},
    {"manifest": "Wealth-OS",          "glob": "sail-wealth-v*.html",        "manual": "Wealth-OS-Manual.html"},
]

VERSION_RE = re.compile(r"-v(\d+(?:\.\d+)?)\.")


def version_of(filename):
    m = VERSION_RE.search(filename)
    if not m:
        return (-1,)
    parts = m.group(1).split(".")
    return tuple(int(p) for p in parts)


def latest_source(glob_pattern):
    matches = list(SOURCE_DIR.glob(glob_pattern))
    if not matches:
        return None
    matches.sort(key=lambda p: version_of(p.name))
    return matches[-1]


def extract(src):
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
    for app in APPS:
        src_path = latest_source(app["glob"])
        if not src_path:
            print(f"  miss   {app['manifest']:24s}  (no match for {app['glob']} in source dir)")
            missing += 1
            continue
        try:
            content = src_path.read_text(errors="replace")
        except Exception as e:
            print(f"  error  {app['manifest']:24s}  {e}")
            missing += 1
            continue
        entries = extract(content)
        out_path = APPS_DIR / f"{app['manifest']}.changelog"
        if entries:
            body = "\n".join(entries)
        else:
            body = "(no CHANGELOG comments found in source)"
        out_path.write_text(body + "\n")
        print(f"  ok     {out_path.name:32s}  <- {src_path.name}  ({len(entries)} entries)")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
