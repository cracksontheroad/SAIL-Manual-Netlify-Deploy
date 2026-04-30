#!/usr/bin/env python3
import re, sys, os, json, urllib.request, urllib.error
from datetime import datetime

with open('scripts/file-map.json') as f:
    FILE_MAP = json.load(f)

def extract_changelog(filepath):
    try:
        src = open(filepath).read()
    except FileNotFoundError:
        return [f"File not found: {filepath}"]
    lines = src.split('\n')[:80]
    entries = [re.match(r'\s*//\s*(CHANGELOG[^:]*:.*)', l).group(1).strip()
               for l in lines if re.match(r'\s*//\s*(CHANGELOG[^:]*:.*)', l)]
    if not entries:
        entries = [re.match(r'\s*//\s*(.*)', l).group(1).strip()
                   for l in lines if re.match(r'\s*//\s*(.*)', l)
                   and re.search(r'(added|removed|rebuilt|updated|fixed|new)\b', l, re.IGNORECASE)
                   and len(re.match(r'\s*//\s*(.*)', l).group(1)) > 10]
    return entries if entries else ["No CHANGELOG found — review manually."]

def find_sections(filepath, cl):
    entry = FILE_MAP.get(filepath)
    if not entry:
        return ["(not in file-map)"], []
    kw = {"calendar":["administration","calendar"],"dashboard":["dashboard"],"course":["courses","create-course"],"assignment":["assignments","create-assignment"],"gradebook":["gradebook-entry"],"attendance":["attendance","daily-attendance"],"wellbeing":["attendance","wellbeing-dashboard"],"ai":["ai-features","ai-studio-overview"],"student":["students","student-roster"],"analytics":["analytics"],"messages":["communication","messages"],"settings":["settings"],"compliance":["compliance"],"pulse":["class-pulse"],"rubric":["rubric-options"],"admin":["administration"],"tier":["administration","calendar"],"dept":["administration","calendar"],"tutor":["tutor"],"provision":["provisioning"]}
    affected = set()
    text = " ".join(cl).lower()
    for k, v in kw.items():
        if k in text: affected.update(v)
    for k, v in entry.get("section_map", {}).items():
        if k.lower() in text: affected.add(v)
    return sorted(affected) if affected else ["(review all)"], entry.get("cascade", [])

def build_body(info):
    out = [f"## Manual Update Required\n**Triggered:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n---\n"]
    for fp, d in info.items():
        entry = FILE_MAP.get(fp, {})
        out += [f"### `{fp}`", f"**Manual:** `{entry.get('manual','?')}`\n", "**CHANGELOG:**"]
        out += [f"- {c}" for c in d["changelog"]]
        out += ["", "**Sections to update:**"] + [f"- `#{s}`" for s in d["sections"]] + [""]
        if d["cascade"]:
            out += ["**Cascade — also update:**"] + [f"- `{FILE_MAP.get(c,{}).get('manual',c)}`" for c in d["cascade"]] + [""]
        out.append("---\n")
    out += ["## Cowork checklist\n","1. Open the HTML manual file listed above","2. Find each `#section-id`: `grep -n 'id=\"X\"' file.html`","3. Update content to match CHANGELOG","4. Add: `<p class=\"version-note\"><em>Updated: [Month Year]</em></p>`","5. Check cascade files and update those too","6. `git add *.html && git commit -m 'Update manual' && git push`","7. Actions tab → Deploy Manuals → Run workflow","8. Verify live URL, close this issue\n","_Ref: https://www.notion.so/351926ae7d1b81759fb8f02da02ffc7f_"]
    return "\n".join(out)

def create_issue(title, body):
    token, repo = os.environ.get("GH_TOKEN"), os.environ.get("GH_REPO")
    if not token or not repo:
        print(f"TITLE: {title}\n\n{body}"); return
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues",
          json.dumps({"title":title,"body":body,"labels":["manual-update"]}).encode(), method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/vnd.github+json")
    try:
        with urllib.request.urlopen(req) as r:
            print(f"Issue: {json.loads(r.read())['html_url']}")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()}")

def main():
    if len(sys.argv) < 2: sys.exit("Usage: detect-changes.py 'files'")
    info, apps = {}, []
    for f in sys.argv[1].split():
        f = f.strip()
        if not f.startswith("apps/") or f not in FILE_MAP: continue
        cl = extract_changelog(f)
        sections, cascade = find_sections(f, cl)
        info[f] = {"changelog": cl, "sections": sections, "cascade": cascade}
        apps.append(os.path.basename(f).replace('.jsx','').replace('.html',''))
    if not info: print("No tracked files changed."); return
    title = f"Manual update required: {', '.join(apps)} [{datetime.utcnow().strftime('%Y-%m-%d')}]"
    body = build_body(info)
    print(body)
    create_issue(title, body)

if __name__ == "__main__":
    main()
