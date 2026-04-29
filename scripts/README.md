# scripts/

Tooling for the SAIL Manual deploy folder. Hand-edited HTML manuals are
the source of truth; this folder is the safety + ergonomics layer.

## Daily use

To update a manual: edit its HTML in this repo, then run:

```
./scripts/deploy.sh
```

That command:

1. Validates all 8 manuals against the safety gate (>80KB, no >20% shrink, none missing).
2. Updates `manifest.json` with new SHA256 hashes.
3. Asks you to confirm.
4. Runs `netlify deploy --prod --dir .` to push to `sailecosystem.netlify.app`.

Pass `-y` (or `--yes`) to skip the confirmation prompt.

## Why this layer exists

On 2026-04-13, an automated updater pushed empty HTMLs to GitHub and
wiped the production site (commit `9cf1ef0`, +9 / -16,221 lines). That
task — `sail-manual-updater`, daily 04:00 in Cowork — is disabled.

This tooling replaces it with a fail-loud, human-gated alternative:

- The safety gate in `update_manifest.py` refuses to update the manifest
  if any manual is missing, shrinks below 80KB, or shrinks by more than
  20% — the three signatures of the 2026-04-13 wipe.
- Deploy is CLI-only (`netlify deploy`); the GitHub remote is archival.
  Pushing to GitHub does **not** trigger a Netlify build.
- No auto-commit, no auto-push, no scheduled execution. Every step is
  a deliberate human action.

## When the safety gate fires

`update_manifest.py` exits with code 2 and refuses to update the manifest
if a check fails. Before bypassing:

- **Manual missing** — was a file deleted by accident? Restore from git.
- **<80KB** — file is suspiciously small. Did the editor truncate it,
  or is the content genuinely that short?
- **>20% shrink** — significant content removal. Verify it's intentional
  (e.g., a CSS extraction refactor) before forcing through.

There is intentionally no `--force` flag. If you genuinely need to land
a smaller version, edit the gate constants in `update_manifest.py`,
deploy, then revert the change. The friction is the point.

## Change-detection signal (apps/ → manual-update issue)

When a `.jsx` (or `.html`) file in `apps/` is pushed to `main`, the
GitHub Actions workflow `.github/workflows/detect-changes.yml` runs
`scripts/detect-changes.py`. That script:

- reads CHANGELOG comments from the changed app file,
- maps keywords to manual section IDs via `scripts/file-map.json`,
- opens a GitHub Issue labeled `manual-update` listing which manual
  sections likely need updating.

**The workflow does not deploy.** It only signals. A human still has
to edit the manual HTML and run `./scripts/deploy.sh`. This keeps the
deploy gate intact while making the "which sections changed?" question
machine-answerable.

## What does NOT happen automatically

- `regenerate()` in `update_manifest.py` is a stub that raises
  `NotImplementedError`. There is no upstream source or generator yet —
  manuals are hand-edited.
- `manifest.json` only updates when `update_manifest.py --apply` runs
  (which `deploy.sh` does for you).
- Pushing to GitHub does **not** deploy. Use `./scripts/deploy.sh`.
- The detect-changes workflow does **not** deploy or modify manuals —
  it only opens an issue.

## State reference

- Netlify project: `sailecosystem` (id `ffbe383c-5b9e-4b89-a4cb-6ad862d8c143`)
- Production URL: https://sailecosystem.netlify.app
- GitHub remote: `cracksontheroad/SAIL-Manual-Netlify-Deploy@main`
- Tracked content: 8 product manuals + `index.html`, `SAIL-Ecosystem-Map.html`,
  `manual-style.css`, `icons/`.
