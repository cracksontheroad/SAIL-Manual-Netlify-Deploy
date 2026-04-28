#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Validating manuals + updating manifest"
python3 scripts/update_manifest.py --apply

if [ "${1:-}" != "-y" ] && [ "${1:-}" != "--yes" ]; then
  echo
  read -p "Deploy to sailecosystem.netlify.app? Type 'deploy' to confirm: " confirm
  [ "$confirm" = "deploy" ] || { echo "Aborted."; exit 1; }
fi

echo "==> Deploying..."
netlify deploy --prod --dir .
