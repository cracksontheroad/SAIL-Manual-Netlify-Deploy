#!/usr/bin/env python3
"""
detect-changes.py
─────────────────
Reads CHANGELOG manifest files in apps/*.changelog and opens a
manual-update GitHub Issue listing affected manual sections.

Manifests are plain-text files (one CHANGELOG entry per line).
Generate them with scripts/sync-apps.py from app source files
that live OUTSIDE this repo.

This script does NOT deploy. Deploy is gated separately through
scripts/deploy.sh.

Called by .github/workflows/detect-changes.yml on push to apps/**.
"""

import re
import sys
import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FILE_MAP_PATH = REPO_ROOT / "scripts" / "file-map.json"

with open(FILE_MAP_PATH) as f:
    FILE_MAP = json.load(f)


def read_manifest(filepath: str) -> list[str]:
    p = REPO_ROOT / filepath
    if not p.exists():
        return [f"Manifest not found: {filepath}"]
    return [line.strip() for line in p.read_text().splitlines() if line.strip()]


def find_affected_sections(filepath: str, changelog_lines: list[str]) -> tuple[list[str], list[str]]:
    entry = FILE_MAP.get(filepath)
    if not entry:
        return ["(not in file-map — add to scripts/file-map.json)"], []

    section_map = entry.get("section_map", {})
    cascade = entry.get("cascade", [])

    keywords = {
        "calendar":     ["administration", "calendar"],
        "dashboard":    ["dashboard"],
        "course":       ["courses", "create-course"],
        "assignment":   ["assignments", "create-assignment"],
        "gradebook":    ["gradebook-entry", "grade-calculation"],
        "attendance":   ["attendance", "daily-attendance"],
        "wellbeing":    ["attendance", "mood-checkins", "wellbeing-dashboard"],
        "ai":           ["ai-features", "ai-studio-overview", "ai-grading"],
        "student":      ["students", "student-roster"],
        "analytics":    ["analytics"],
        "messages":     ["communication", "messages"],
        "settings":     ["settings"],
        "compliance":   ["compliance"],
        "pulse":        ["class-pulse"],
        "leaderboard":  ["leaderboard"],
        "portfolio":    ["portfolio"],
        "rubric":       ["rubric-options", "courses"],
        "permission":   ["roles"],
        "admin":        ["administration"],
        "tier":         ["administration", "calendar"],
        "dept":         ["administration", "calendar"],
        "tutor":        ["tutor"],
        "provision":    ["provisioning"],
    }

    affected = set()
    text = " ".join(changelog_lines).lower()
    for kw, sections in keywords.items():
        if kw in text:
            affected.update(sections)
    for key, sid in section_map.items():
        if key.lower() in text:
            affected.add(sid)

    return sorted(affected) if affected else ["(review all — no keywords matched)"], cascade


def build_body(info: dict) -> str:
    out = [
        "## Manual Update Required\n",
        f"**Triggered:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n",
        "---\n",
    ]
    for filepath, data in info.items():
        entry = FILE_MAP.get(filepath, {})
        out.append(f"### `{filepath}`")
        out.append(f"**Manual:** `{entry.get('manual','unknown')}`\n")
        out.append("**CHANGELOG:**")
        for c in data["changelog"]:
            out.append(f"- {c}")
        out.append("")
        out.append("**Sections to update:**")
        for s in data["sections"]:
            out.append(f"- `#{s}`")
        out.append("")
        if data["cascade"]:
            out.append("**Cascade — also update:**")
            for c in data["cascade"]:
                out.append(f"- `{FILE_MAP.get(c,{}).get('manual',c)}`")
            out.append("")
        out.append("---\n")
    out += [
        "## Cowork checklist\n",
        "1. Open each HTML manual listed above (at the repo root)",
        "2. Find each `#section-id`",
        "3. Update content to match CHANGELOG (no version stamps)",
        "4. Validate: every manual > 80KB, no > 20% shrink, footer has learn@sailedu.co",
        "5. Run `./scripts/deploy.sh` to deploy (CLI-gated; pushing to GitHub does NOT deploy)",
        "6. Close this issue\n",
    ]
    return "\n".join(out)


def create_issue(title: str, body: str) -> None:
    token = os.environ.get("GH_TOKEN")
    repo = os.environ.get("GH_REPO")
    if not token or not repo:
        print(f"TITLE: {title}\n\n{body}")
        return
    url = f"https://api.github.com/repos/{repo}/issues"
    data = json.dumps({"title": title, "body": body, "labels": ["manual-update"]}).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req) as r:
            print(f"Issue created: {json.loads(r.read())['html_url']}")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("Usage: detect-changes.py 'file1 file2 ...'")

    info = {}
    apps = []
    for f in sys.argv[1].split():
        f = f.strip()
        if not f.startswith("apps/") or f not in FILE_MAP:
            continue
        cl = read_manifest(f)
        sections, cascade = find_affected_sections(f, cl)
        info[f] = {"changelog": cl, "sections": sections, "cascade": cascade}
        apps.append(os.path.basename(f).replace(".changelog", ""))

    if not info:
        print("No tracked manifest files changed.")
        return

    title = f"Manual update required: {', '.join(apps)} [{datetime.now(timezone.utc).strftime('%Y-%m-%d')}]"
    body = build_body(info)
    print(body)
    create_issue(title, body)


if __name__ == "__main__":
    main()
