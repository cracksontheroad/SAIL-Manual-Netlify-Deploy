# SAIL Manual Deploy — Project Memory for Claude Code

This file is the project memory for the SAIL manual deploy repo.
Read it at the start of every session before touching any file.

---

## Who you are working with

**Carl Alston** — Founder, SAIL Education (sailedu.co). UK citizen based in China.
Building a suite of EdTech React/JSX apps for international schools.

---

## What this repo is

**Repo:** `github.com/cracksontheroad/SAIL-Manual-Netlify-Deploy`
**Live site:** `https://sailecosystem.netlify.app` (NOT git-connected — deploy via CLI only)
**Purpose:** the 8 external HTML manuals + the automation that keeps them in sync with the apps.

```
SAIL-Manual-Netlify-Deploy/
├── *.html                         # 8 product manuals + index + ecosystem map
├── icons/                         # 360px product logo icons
├── manual-style.css               # shared stylesheet
├── manifest.json                  # SHA256 + size baseline (safety gate state)
├── apps/
│   └── *.changelog                # per-app CHANGELOG manifests (no source, no secrets)
├── scripts/
│   ├── deploy.sh                  # safety-gated CLI deploy wrapper
│   ├── update_manifest.py         # safety-gate enforcer
│   ├── sync-apps.py               # extracts apps/*.changelog from source files outside repo
│   ├── detect-changes.py          # called by GH Action; opens manual-update Issue
│   └── file-map.json              # changelog → manual + section IDs
└── .github/workflows/
    └── detect-changes.yml         # fires on push to apps/**, opens issue (no deploy)
```

The 8 product manuals at the repo root are the **only** files that ship to Netlify. Everything else (`apps/`, `scripts/`, `.github/`) is tooling.

---

## The product suite

| App | Source file (outside repo) | Manual |
|---|---|---|
| SAIL Helm | `SAIL-Helm-v9.jsx` | `SAIL-Helm-Manual.html` |
| SuperTeacher | `SuperTeacher-v6.jsx` | `SuperTeacher-Manual.html` |
| SuperStudent | `SuperStudent-v5.jsx` | `SuperStudent-Manual.html` |
| Compass | `compass-v3.jsx` | `Compass-Manual.html` |
| Compass Counsellor | `compass-counsellor-v3.jsx` | `Compass-Counsellor-Manual.html` |
| SAIL IELTS-OS | `sail-ielts-v5.jsx` | `IELTS-OS-Manual.html` |
| Life-OS | `LifeOS-v2.jsx` | `Life-OS-Manual.html` |
| Wealth-OS | `sail-wealth-v10.html` | `Wealth-OS-Manual.html` |

**Source files live OUTSIDE this repo** at `~/Documents/SAIL/Projects/` (set `SAIL_APP_SOURCE` env var to override). They contain hardcoded API keys and must never be committed here.

---

## How updates flow

```
edit app source at ~/Documents/SAIL/Projects/
        ↓
./scripts/sync-apps.py                      # writes apps/*.changelog
git add apps/ && git commit && git push     # triggers detect-changes workflow
        ↓
GitHub Issue opens with label `manual-update`
listing affected manual sections per file-map.json
        ↓
[FUTURE: scripts/generate.py reads issue, calls Claude API,
 writes updated manual sections, opens PR for review]
        ↓
edit affected manual HTML at repo root (today: by hand)
        ↓
./scripts/deploy.sh                         # safety-gated deploy
        ↓
sailecosystem.netlify.app live with new content
        ↓
git commit + push the manual changes (archival)
```

**No auto-deploy on git push exists or should ever exist.** The site is not git-connected. Deploys go through `./scripts/deploy.sh` which calls Netlify CLI directly after validating the safety gate. This is the post-wipe-incident model.

---

## Safety guardrails (MANDATORY)

These rules exist because a previous automation run wiped all manual content on **2026-04-13**. The `./scripts/deploy.sh` wrapper enforces them automatically — do NOT bypass.

1. **NEVER deploy a manual under 80 KB.**
2. **NEVER deploy when any manual has shrunk by more than 20%** vs the manifest baseline.
3. **All 8 product manuals must be present.**
4. **Every manual MUST contain `learn@sailedu.co`** in its footer.
5. **NEVER modify `manual-style.css`, `index.html`, or anything in `icons/`** — protected.
6. **NEVER modify `<script>` blocks in manuals** — navigation JS is hand-tuned.
7. **NEVER add version stamps** — no "v2", "Updated: ..." notes anywhere.
8. **NEVER bypass `./scripts/deploy.sh`.** Bare `netlify deploy` skips the gate.

If the gate refuses, investigate. There is no `--force`. Edit the gate constants in `update_manifest.py` only as a deliberate, audited override.

---

## Section-class quirks per manual

Most manuals use `<div class="content-section">`. Three differ:

- **Life-OS-Manual.html** — `class="section-content"`
- **Compass-Manual.html** — `class="section"` with `<div>` tags
- **Compass-Counsellor-Manual.html** — `class="section"` with `<section>` tags

When editing or generating, match the existing pattern for that file.

---

## Standing rules — enforce without being asked

1. **Babel parse check before delivery** — never deliver a JSX file that fails Babel.
2. **Helm cascade** — any change to SAIL-Helm must apply to SuperTeacher and SuperStudent in the same session. Version up: Helm v(N) → SuperTeacher v(N+1), SuperStudent v(N+1). Babel-check all three.
3. **In-app manual sync** — Helm/SuperTeacher/SuperStudent each contain their own user guide via `roleContent`, `MAN_ROLE_SECTIONS`, and `HELP_CONTENT`. Update all three layers when a feature changes.
4. **Never overwrite** — version up the file, preserve previous builds.
5. **No fake functionality** — every button does something real.
6. **No partial fixes** — identify root cause first.
7. **Generated content scrolls internally** — `overflow-y-auto` + `max-height`, never expand past device screen.
8. **Mobile-first** — test at 375 px minimum width.
9. **Loading + error states** for all async actions.
10. **CHANGELOG comment** at top of each app file on every change. Format:
    ```
    // CHANGELOG v{N}: {what changed} — {feature area keywords}
    ```
    Keywords matter — `scripts/detect-changes.py` matches them against `file-map.json`.
11. **Presentations** — always PDF + PPTX, PDF first.
12. **Cancel button** for any in-progress AI generation.
13. **After every build** — ask how to reduce running costs (model tier, caching, batching).

---

## Architecture decisions (locked)

### AI
- All AI calls route through `SAIL_CONFIG.aiEndpoint` (proxy-ready).
- Haiku for high-volume/routine, Sonnet for complex reasoning.
- **Never hardcode `api.anthropic.com`** — always use `SAIL_CONFIG.aiEndpoint`.
- AI proxy Edge Function (Netlify or Supabase) is the highest-priority architecture task. Until it lands, browser-exposed keys are a known risk.

### Storage
- `SK_SCHOOL(key)` helper scopes storage keys by school when `SAIL_CONFIG.schoolId` is set.
- Helm: `sailhelm_*`, SuperTeacher: `st2_*`, SuperStudent: `ss_*`.
- `SAIL_CONFIG.schoolId` is `""` by default (single-school mode).

### Notifications
- All notification creation goes through `notify(setNotificationsFn, {type, text, forRoles})`.
- Never call `setNotifications()` directly in new code.

### Roles (Helm)
- `super_admin > admin > dept_head > teacher > student > parent`.
- Use `isAdminPlus()`, `isDeptHeadPlus()`, `isStaffRole()` — never raw string checks.
- Permission matrix is `const PERMISSIONS = {}`.

### Calendar
- Day / Week / Month / Year views (no Schedule tab).
- `slotsToEvents()` generates lesson events from timetable data.
- Visibility by role: admin all courses, dept heads their dept, teachers `ownerId === user.id`, students `enrolledCourses`.
- Academic year: 2025-09-01 → 2026-07-15.

### Demo data (Horizon International School)
- 3 departments: Humanities (dh1/th1-th3), Sciences (ds1/ts1-ts3), Arts (da1/ta1-ta3).
- 27 courses (hec1-au3), 71 timetable slots (sc001-sc071), 12 students (s1-s12).

---

## Known security flags

- **All apps**: Claude API key browser-exposed. Use `SAIL_CONFIG.aiEndpoint` proxy at deployment.
- **SuperTeacher v6, line 2**: Supabase publishable key. Less critical (publishable, not service) but rotate when convenient.

---

## Outstanding architecture work

- [ ] Build AI proxy Edge Function (Netlify or Supabase) — highest priority.
- [ ] Build `scripts/generate.py` — LLM-based manual updater that closes the loop from issue → updated HTML.
- [ ] Auto-deploy workflow (post-LLM-generator) that runs `update_manifest.py --apply` then `netlify deploy --prod --dir .`. Only safe to add **after** the LLM generator is proven.
- [ ] Add `schoolId` to all data entities for multi-tenancy.
- [ ] Separate submissions from assignment objects (own storage key).
- [ ] Build in-app `roleContent` manuals for IELTS-OS, Life-OS, Wealth-OS, Bridge, Compass apps.

---

## Notion workspace (reference)

- **Cowork Instructions:** https://www.notion.so/351926ae7d1b81759fb8f02da02ffc7f
- **Architecture Audit:** https://www.notion.so/345926ae7d1b81a4a62cde5e4445140f
- **Helm Refactor Report:** https://www.notion.so/347926ae7d1b81f1b61bca10b485a794

---

## Design system (Helm aesthetic — applies to all apps)

```
Page background:  #F8FAFC  (slate-50)
Cards:            #FFFFFF with #E2E8F0 border, rounded-2xl, shadow-sm
Primary:          #4F46E5  (indigo-600)
Active nav:       bg-indigo-600 text-white rounded-xl
Sidebar:          bg-white border-r border-slate-100
Text headings:    #0F172A  (slate-900)
Text muted:       #64748B  (slate-500)
Emerald accent:   #10B981
```

---

## Key patterns

### Babel check
```bash
node -e "
const p = require('@babel/parser');
const fs = require('fs');
const src = fs.readFileSync('SAIL-Helm-v9.jsx', 'utf8');
try {
  p.parse(src, { sourceType: 'module', plugins: ['jsx'] });
  console.log('PASS (' + src.split('\n').length + 'L)');
} catch(e) {
  console.log('FAIL L' + e.loc?.line + ' — ' + e.message);
}"
```

### Storage key
```js
const SK_SCHOOL = (key) =>
  SAIL_CONFIG.schoolId
    ? `sailhelm_${SAIL_CONFIG.schoolId}_${key}`
    : `sailhelm_${key}`;
```

### Notify
```js
notify(setNotifications, {
  type: "submission",
  text: "New submission from Sofia Patel",
  forRoles: ["teacher", "admin"]
});
```

### SAIL_CONFIG
```js
const SAIL_CONFIG = {
  aiEndpoint: (typeof SAIL_AI_PROXY !== "undefined" ? SAIL_AI_PROXY : null)
              || "https://api.anthropic.com/v1/messages",
  appId:      "sail-helm",
  appVersion: "9.0",
  schoolId:   "",
};
```

---

*Last updated: 2026-04-30*
