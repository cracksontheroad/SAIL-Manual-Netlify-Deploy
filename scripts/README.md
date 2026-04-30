# scripts/

Tooling for the SAIL Manual deploy folder. The 8 product manuals at
the repo root are what gets shipped; this folder is the automation
that keeps them in sync with the apps.

## Daily use — one command

After you (or chat-Claude) edit any app source file at
`~/Documents/SAIL/Projects/`:

```
./scripts/auto-update.sh
```

That runs the entire pipeline:

1. `sync-apps.py` — auto-discovers latest app source versions, writes
   stable-name manifests `apps/<App>.changelog`.
2. For each manifest that changed, runs `generate.py --apply` to call
   Claude and rewrite the affected manual sections.
3. `deploy.sh -y` runs the safety gate and pushes to Netlify.
4. Commits and pushes to GitHub for archival.

No prompts, no diffs to review. Validators do the checking. If any
validator fails, the pipeline aborts loudly and nothing ships.

## Lower-level — manual control

If you want to run pieces individually (debugging or one-off control):

```
./scripts/sync-apps.py                                 # refresh manifests
./scripts/generate.py apps/SAIL-Helm.changelog         # dry-run, prints proposed diff
./scripts/generate.py apps/SAIL-Helm.changelog --apply # writes the new HTML
./scripts/deploy.sh                                    # interactive safety-gated deploy
./scripts/deploy.sh -y                                 # skip confirmation prompt
```

`deploy.sh` does:

1. Validates all 8 manuals against the safety gate (>80KB, no >20% shrink, none missing).
2. Updates `manifest.json` with new SHA256 hashes.
3. (interactive only) asks you to confirm.
4. Runs `netlify deploy --prod --dir .` to push to `sailecosystem.netlify.app`.

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
- No scheduled execution. No GitHub Actions auto-deploy. No webhook
  triggers. The pipeline only runs when you invoke it with
  `./scripts/auto-update.sh` (or one of the lower-level scripts).

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

## What's in apps/ — manifests, not source

The repo does **not** contain app source files — those live outside
this repo at `~/Documents/SAIL/Projects/` and contain hardcoded API
keys that must never be committed. Instead, `apps/` contains a
`<App>.changelog` manifest per app: a tiny plain-text file with the
CHANGELOG comments extracted from the app source.

Manifest filenames are version-stable (`apps/SAIL-Helm.changelog`,
not `apps/SAIL-Helm-v9.changelog`). `sync-apps.py` auto-discovers
the latest version of each app from the source dir, so v9 → v10
needs no config changes.

When a `.changelog` file changes on `main`, the workflow
`.github/workflows/detect-changes.yml` runs `scripts/detect-changes.py`,
which:

- reads the changed manifest(s),
- maps keywords to manual section IDs via `scripts/file-map.json`,
- opens a GitHub Issue labeled `manual-update` listing which manual
  sections likely need updating.

**The workflow does not deploy.** It only signals. A human still
edits the manual HTML and runs `./scripts/deploy.sh`. The deploy gate
stays intact.

## LLM-based manual generator (`generate.py`)

Closes the loop from "issue says these sections need updating" to
"updated HTML is on disk and ready to deploy" without you writing
prose.

### Setup (one-time)
```
pip3 install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
```
Add the env var to your shell profile (`~/.zshrc` or `~/.bash_profile`)
so it's persistent.

### Use
```
./scripts/generate.py apps/SAIL-Helm.changelog              # dry-run, prints diffs
./scripts/generate.py apps/SAIL-Helm.changelog --review     # adds self-review pass
./scripts/generate.py apps/SAIL-Helm.changelog --apply      # writes updates to disk
./scripts/generate.py apps/SAIL-Helm.changelog --apply --deploy   # writes + runs deploy.sh
```

### How it works

1. Reads the manifest's CHANGELOG entries.
2. Looks up `file-map.json` to find the target manual + which section
   keywords matched.
3. For each affected section, locates the `<div id="X">...</div>` block
   in the manual.
4. Calls Claude (Sonnet 4.6 by default) with a constrained prompt:
   "rewrite this section to reflect the changelog, preserve all classes
   and IDs, no version stamps, no invented features."
5. Validates each proposed update:
   - Section `id="..."` preserved
   - Class attribute on opening tag unchanged
   - No `class="version-note"`, no "Updated: ..." stamps
   - Non-empty
6. After all sections processed, runs whole-file structural validators:
   - `learn@sailedu.co` still in footer
   - Manual still ≥ 80 KB
   - Manual hasn't shrunk by > 20 %
7. With `--apply`, writes the new HTML. With `--deploy`, chains into
   `deploy.sh` which runs the manifest gate and deploys to Netlify.

### Optional `--review` flag

Runs a second LLM call per section asking "list any claim in the
proposed update not supported by the CHANGELOG." If anything's flagged,
that section is skipped. Adds latency and cost; recommended until you've
seen enough output to trust the prompt.

### Cascade is NOT processed in v1

If a manifest's `cascade` lists other manifests (Helm cascades to
SuperTeacher and SuperStudent), you currently have to run the script
once per manifest. To be added in v2.

## What does NOT happen automatically

- `regenerate()` in `update_manifest.py` is still a stub that raises
  `NotImplementedError`. The actual generator lives in `generate.py`.
- `manifest.json` only updates when `update_manifest.py --apply` runs
  (which `deploy.sh` does for you).
- Pushing to GitHub does **not** deploy. Use `./scripts/deploy.sh`
  or `./scripts/generate.py --apply --deploy`.
- The detect-changes workflow does **not** deploy or modify manuals —
  it only opens an issue.

## State reference

- Netlify project: `sailecosystem` (id `ffbe383c-5b9e-4b89-a4cb-6ad862d8c143`)
- Production URL: https://sailecosystem.netlify.app
- GitHub remote: `cracksontheroad/SAIL-Manual-Netlify-Deploy@main`
- Tracked content: 8 product manuals + `index.html`, `SAIL-Ecosystem-Map.html`,
  `manual-style.css`, `icons/`.
