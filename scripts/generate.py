#!/usr/bin/env python3
"""
generate.py
───────────
Read an apps/<name>.changelog manifest and update the corresponding
manual sections by calling Claude API.

Default: dry-run — prints proposed diffs only.
With --apply: writes updated HTML to disk (after structural validators pass).
With --apply --deploy: also runs scripts/deploy.sh after.
With --review: adds a self-review pass that flags hallucinated content.

Requirements:
  pip3 install anthropic
  export ANTHROPIC_API_KEY=sk-ant-...

Cascade is NOT processed in v1. Re-run the script on each cascade
manifest manually if needed.
"""

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FILE_MAP_PATH = REPO_ROOT / "scripts" / "file-map.json"

with open(FILE_MAP_PATH) as f:
    FILE_MAP = json.load(f)

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8000
FOOTER_EMAIL = "learn@sailedu.co"
MIN_SIZE_BYTES = 80_000
MAX_SHRINK_RATIO = 0.20

SYSTEM_PROMPT = """You are a technical writer updating user-facing HTML documentation for an EdTech application.

You will receive:
- CHANGELOG entries describing what changed in the app
- The current HTML for one section of the manual
- The section's identifier and the manual it belongs to

Update the section's HTML to reflect the changelog. Strict rules:

- Modify only content within the existing tag structure.
- Preserve all CSS class names exactly (`content-section`, `section-content`, `section`, `role-badge`, `tip`, `warning`, `note`, `steps`, etc.).
- Preserve the section's `id` attribute exactly.
- Do NOT add version stamps, version numbers, or "Updated: ..." notes.
- Do NOT invent features not mentioned in the CHANGELOG.
- Do NOT remove existing content unless the changelog clearly says it was removed.
- Match the existing tone. Plain editorial language.
- If the changelog doesn't describe a user-visible change, return the section unchanged.

Output ONLY the updated HTML for the section. No code fences. No preamble. Start with the opening tag, end with the matching closing tag."""

REVIEW_PROMPT = """You are reviewing a documentation update for factual accuracy.

ORIGINAL SECTION:
{original}

PROPOSED UPDATE:
{updated}

CHANGELOG ENTRIES:
{changelog}

List any claim or feature in the proposed update that is NOT supported by the changelog or the original. If everything is supported, reply with exactly "OK". Otherwise list each unsupported claim, one per line, prefixed with "- "."""


def find_section(html_src: str, section_id: str):
    """Locate <div|section ... id='X'> ... </> with proper depth tracking. Returns (start, end, html) or None."""
    open_re = re.compile(rf'<(div|section)\s+[^>]*id="{re.escape(section_id)}"[^>]*>')
    match = open_re.search(html_src)
    if not match:
        return None
    start = match.start()
    tag = match.group(1)
    pos = match.end()
    depth = 1
    open_tag_re = re.compile(rf'<{tag}\b')
    close_tag_re = re.compile(rf'</{tag}>')
    while depth > 0:
        n_open = open_tag_re.search(html_src, pos)
        n_close = close_tag_re.search(html_src, pos)
        if not n_close:
            return None
        if n_open and n_open.start() < n_close.start():
            depth += 1
            pos = n_open.end()
        else:
            depth -= 1
            pos = n_close.end()
    return start, pos, html_src[start:pos]


def clean_llm_output(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        nl = text.find("\n")
        if nl > 0:
            text = text[nl + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def call_claude(client, model: str, system: str, user: str) -> str:
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def validate_section(updated: str, original: str, section_id: str) -> list[str]:
    issues = []
    if f'id="{section_id}"' not in updated:
        issues.append(f"section id '{section_id}' missing in update")

    orig_open = re.match(r'<(?:div|section)\s+[^>]*?>', original)
    new_open = re.match(r'<(?:div|section)\s+[^>]*?>', updated)
    if orig_open and new_open:
        oc = re.search(r'class="([^"]*)"', orig_open.group(0))
        nc = re.search(r'class="([^"]*)"', new_open.group(0))
        if oc and (not nc or oc.group(1) != nc.group(1)):
            issues.append(f"class changed: {oc.group(1)!r} -> {nc.group(1) if nc else None!r}")

    if 'class="version-note"' in updated or re.search(r'Updated:\s*\d', updated):
        issues.append("version stamp present (forbidden)")

    if not updated.strip():
        issues.append("empty output")

    return issues


def show_diff(old: str, new: str, label: str) -> None:
    diff = list(difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile=f"{label} (current)",
        tofile=f"{label} (proposed)",
        n=2,
    ))
    if diff:
        print("".join(diff))
    else:
        print(f"  (no textual diff for {label})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("manifest", help="path to apps/<name>.changelog")
    parser.add_argument("--apply", action="store_true", help="write updates to disk")
    parser.add_argument("--deploy", action="store_true", help="run scripts/deploy.sh after applying")
    parser.add_argument("--review", action="store_true", help="add a self-review pass per section")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model (default {DEFAULT_MODEL})")
    args = parser.parse_args()

    if args.deploy and not args.apply:
        sys.exit("--deploy requires --apply")

    manifest_path = args.manifest
    if not manifest_path.startswith("apps/") or manifest_path not in FILE_MAP:
        sys.exit(f"{manifest_path} not in scripts/file-map.json")

    entry = FILE_MAP[manifest_path]
    manual_path = REPO_ROOT / entry["manual"]
    section_map = entry["section_map"]

    if not manual_path.exists():
        sys.exit(f"Manual not found: {manual_path}")

    changelog = (REPO_ROOT / manifest_path).read_text().strip()
    if not changelog or changelog == "(no CHANGELOG comments found in source)":
        print(f"No CHANGELOG entries in {manifest_path}; nothing to do.")
        return

    text = changelog.lower()
    affected = sorted({sid for kw, sid in section_map.items() if kw in text})
    if not affected:
        print(f"No section keywords matched in {manifest_path}; aborting (too broad to update everything).")
        return

    print(f"Manifest: {manifest_path}")
    print(f"Manual:   {entry['manual']}")
    print(f"Affected: {', '.join(affected)}")
    print()

    try:
        from anthropic import Anthropic
    except ImportError:
        sys.exit("Install the Anthropic SDK first: pip3 install anthropic")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY environment variable.")

    client = Anthropic()
    html_src = manual_path.read_text()

    proposed: dict[str, tuple[str, str]] = {}
    for sid in affected:
        loc = find_section(html_src, sid)
        if not loc:
            print(f"  [skip]      #{sid} not found in {entry['manual']}")
            continue
        _, _, original = loc
        user_prompt = (
            f"## Manual: {entry['manual']}\n"
            f"## Section ID: {sid}\n\n"
            f"## CHANGELOG:\n{changelog}\n\n"
            f"## Current section HTML:\n{original}\n"
        )
        print(f"  [calling]   #{sid} ({len(original)} chars)")
        try:
            updated = clean_llm_output(call_claude(client, args.model, SYSTEM_PROMPT, user_prompt))
        except Exception as e:
            print(f"  [error]     #{sid}: {e}")
            continue
        if updated == original:
            print(f"  [unchanged] #{sid}")
            continue
        issues = validate_section(updated, original, sid)
        if issues:
            print(f"  [invalid]   #{sid}:")
            for i in issues:
                print(f"    - {i}")
            continue
        if args.review:
            review = call_claude(
                client, args.model,
                "You are a careful technical reviewer.",
                REVIEW_PROMPT.format(original=original, updated=updated, changelog=changelog),
            ).strip()
            if review != "OK":
                print(f"  [reviewed]  #{sid} flagged:")
                for line in review.splitlines():
                    print(f"    {line}")
                print(f"  [skip]      #{sid} (review failure)")
                continue
        proposed[sid] = (original, updated)
        print(f"  [ok]        #{sid}")

    if not proposed:
        print("\nNothing to apply.")
        return

    print("\n=== Proposed diffs ===\n")
    for sid, (old, new) in proposed.items():
        show_diff(old, new, f"#{sid}")

    if not args.apply:
        print("\nDry run. Re-run with --apply to write.")
        return

    locations = []
    for sid in proposed:
        loc = find_section(html_src, sid)
        if loc:
            locations.append((loc[0], loc[1], sid))
    locations.sort(key=lambda x: x[0], reverse=True)

    new_html = html_src
    for start, end, sid in locations:
        _, updated = proposed[sid]
        new_html = new_html[:start] + updated + new_html[end:]

    if FOOTER_EMAIL not in new_html:
        sys.exit(f"FOOTER GUARD: '{FOOTER_EMAIL}' missing in updated manual; refusing to write.")
    if len(new_html) < MIN_SIZE_BYTES:
        sys.exit(f"SIZE GUARD: {len(new_html)} bytes < {MIN_SIZE_BYTES}; refusing to write.")
    if (len(html_src) - len(new_html)) / max(1, len(html_src)) > MAX_SHRINK_RATIO:
        sys.exit(f"SHRINK GUARD: >{int(MAX_SHRINK_RATIO * 100)}% reduction; refusing to write.")

    manual_path.write_text(new_html)
    print(f"\nWrote {manual_path.relative_to(REPO_ROOT)} ({len(new_html)} bytes)")

    if args.deploy:
        import subprocess
        print("\n=== Running deploy.sh ===")
        result = subprocess.run([str(REPO_ROOT / "scripts" / "deploy.sh")], cwd=REPO_ROOT)
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
