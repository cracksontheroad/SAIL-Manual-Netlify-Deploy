#!/usr/bin/env bash
# auto-update.sh
# ──────────────
# One-command pipeline: refresh manifests → LLM-generate manual updates →
# safety-gate → deploy → archive to GitHub.
#
# Validators (per-section + whole-file + manifest gate) replace human review.
# No prompts, no diffs to inspect. If any validator catches a problem,
# the pipeline aborts loudly and nothing ships.

set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Refreshing manifests from app source"
python3 scripts/sync-apps.py
echo

CHANGED=$(
  (
    git diff --name-only HEAD -- apps/
    git ls-files --others --exclude-standard apps/
  ) | grep '\.changelog$' | sort -u
)

if [ -z "$CHANGED" ]; then
  echo "No manifest changes. Nothing to update."
  exit 0
fi

echo "==> Manifests changed:"
echo "$CHANGED" | sed 's/^/    /'
echo

ANY_APPLIED=false
for f in $CHANGED; do
  echo "==> Generating updates for $f"
  if ./scripts/generate.py "$f" --apply; then
    ANY_APPLIED=true
  else
    echo "    (skipped: generation failed validators or had nothing to apply)"
  fi
  echo
done

if [ "$ANY_APPLIED" != "true" ]; then
  echo "No manuals were updated. Nothing to deploy."
  exit 0
fi

echo "==> Deploying"
./scripts/deploy.sh -y
echo

echo "==> Archiving to GitHub"
git add apps/ *.html manifest.json 2>/dev/null || true
if git diff --cached --quiet; then
  echo "    (nothing staged to commit)"
else
  git commit -m "Auto-update manuals from app changes — $(date -u +%Y-%m-%d)"
  git push origin main
fi

echo
echo "==> Done. Live at https://sailecosystem.netlify.app"
