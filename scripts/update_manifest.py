#!/usr/bin/env python3
"""
SAIL manual change-detection + manifest updater.

Default run: read-only diff against manifest.json.
With --apply: writes the updated manifest if all safety gates pass.

Built deliberately to fail loudly rather than silently — this is the
replacement for the disabled sail-manual-updater task that wiped prod
on 2026-04-13 by pushing empty HTML.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "manifest.json"

MANUALS = [
    "Compass-Counsellor-Manual.html",
    "Compass-Manual.html",
    "IELTS-OS-Manual.html",
    "Life-OS-Manual.html",
    "SAIL-Helm-Manual.html",
    "SuperStudent-Manual.html",
    "SuperTeacher-Manual.html",
    "Wealth-OS-Manual.html",
]

MIN_SIZE_BYTES = 80_000
MAX_SHRINK_RATIO = 0.20


def regenerate(manual: str) -> None:
    raise NotImplementedError(
        f"No generator wired up for {manual}. "
        "Until an upstream source + generator exists, regeneration "
        "must be done manually. This stub exists to make that explicit."
    )


def hash_file(path: Path) -> tuple[str, int]:
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {"lastUpdated": None, "manuals": {}}
    return json.loads(MANIFEST_PATH.read_text())


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def diff(manifest: dict) -> dict:
    """Return per-manual status: 'unchanged' | 'changed' | 'new' | 'missing'."""
    stored = manifest.get("manuals", {})
    report = {}
    for name in MANUALS:
        path = REPO_ROOT / name
        if not path.exists():
            report[name] = {"status": "missing", "stored": stored.get(name)}
            continue
        h, size = hash_file(path)
        prior = stored.get(name)
        if prior is None:
            report[name] = {"status": "new", "current": {"hash": h, "fileSize": size}}
        elif prior["hash"] == h:
            report[name] = {"status": "unchanged", "current": {"hash": h, "fileSize": size}}
        else:
            report[name] = {
                "status": "changed",
                "stored": prior,
                "current": {"hash": h, "fileSize": size},
            }
    return report


def safety_gate(report: dict) -> list[str]:
    """Return list of safety violations. Empty list = safe to apply."""
    violations = []
    for name, entry in report.items():
        if entry["status"] == "missing":
            violations.append(f"{name}: file missing on disk")
            continue
        cur = entry.get("current", {})
        if cur.get("fileSize", 0) < MIN_SIZE_BYTES:
            violations.append(
                f"{name}: size {cur['fileSize']} < {MIN_SIZE_BYTES} (wipe-incident signature)"
            )
        if entry["status"] == "changed":
            old = entry["stored"]["fileSize"]
            new = cur["fileSize"]
            if old > 0 and (old - new) / old > MAX_SHRINK_RATIO:
                violations.append(
                    f"{name}: shrank from {old} to {new} "
                    f"(>{int(MAX_SHRINK_RATIO * 100)}% reduction — refusing)"
                )
    return violations


def apply(report: dict, manifest: dict) -> dict:
    timestamp = now_iso()
    new_manuals = dict(manifest.get("manuals", {}))
    for name, entry in report.items():
        if entry["status"] in ("new", "changed"):
            cur = entry["current"]
            new_manuals[name] = {
                "hash": cur["hash"],
                "fileSize": cur["fileSize"],
                "regeneratedAt": timestamp,
            }
        elif entry["status"] == "unchanged" and name in new_manuals:
            pass
    return {"lastUpdated": timestamp, "manuals": new_manuals}


def print_report(report: dict) -> None:
    for name in MANUALS:
        e = report[name]
        if e["status"] == "unchanged":
            print(f"  ok       {name}  ({e['current']['fileSize']:,} bytes)")
        elif e["status"] == "new":
            print(f"  NEW      {name}  ({e['current']['fileSize']:,} bytes)")
        elif e["status"] == "changed":
            old = e["stored"]["fileSize"]
            new = e["current"]["fileSize"]
            delta = new - old
            print(f"  CHANGED  {name}  ({old:,} -> {new:,}, {delta:+,} bytes)")
        elif e["status"] == "missing":
            print(f"  MISSING  {name}  -- file not on disk")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true",
        help="Write updated manifest.json. Without this, runs read-only.",
    )
    args = parser.parse_args()

    manifest = load_manifest()
    report = diff(manifest)

    print(f"Manifest: {MANIFEST_PATH}")
    print(f"Last updated: {manifest.get('lastUpdated', 'never')}")
    print()
    print_report(report)
    print()

    violations = safety_gate(report)
    if violations:
        print("SAFETY GATE FAILED:")
        for v in violations:
            print(f"  - {v}")
        print("\nRefusing to update manifest. Investigate before retrying.")
        return 2

    changed = [n for n, e in report.items() if e["status"] in ("new", "changed")]
    if not changed:
        print("No changes detected.")
        return 0

    print(f"{len(changed)} manual(s) flagged for manifest update: {', '.join(changed)}")
    if not args.apply:
        print("Dry run. Re-run with --apply to write manifest.json.")
        return 0

    new_manifest = apply(report, manifest)
    MANIFEST_PATH.write_text(json.dumps(new_manifest, indent=2) + "\n")
    print(f"Wrote {MANIFEST_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
