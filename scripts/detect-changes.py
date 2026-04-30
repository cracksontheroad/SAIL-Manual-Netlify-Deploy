import re,sys,os,json,urllib.request,urllib.error
from datetime import datetime
FILE_MAP=json.load(open('scripts/file-map.json'))
def changelog(f):
    try: src=open(f).read()
    except: return[f"Not found: {f}"]
    e=[re.match(r'\s*//\s*(CHANGELOG.*)',l).group(1) for l in src.split('\n')[:80] if re.match(r'\s*//\s*(CHANGELOG.*)',l)]
    return e if e else["No CHANGELOG — review manually"]
def sections(f,cl):
    e=FILE_MAP.get(f)
    if not e: return["(not in file-map)"],[]
    kw={"calendar":["administration","calendar"],"dashboard":["dashboard"],"course":["courses"],"assignment":["assignments"],"gradebook":["gradebook-entry"],"attendance":["attendance"],"wellbeing":["wellbeing-dashboard"],"ai":["ai-features","ai-studio-overview"],"student":["students","student-roster"],"analytics":["analytics"],"messages":["communication","messages"],"settings":["settings"],"compliance":["compliance"],"pulse":["class-pulse"],"admin":["administration"],"tier":["administration","calendar"]}
    aff=set()
    t=" ".join(cl).lower()
    for k,v in kw.items():
        if k in t: aff.update(v)
    for k,v in e.get("section_map",{}).items():
        if k in t: aff.add(v)
    return sorted(aff) if aff else["(review all)"],e.get("cascade",[])
def issue(title,body):
    tok,repo=os.environ.get("GH_TOKEN"),os.environ.get("GH_REPO")
    if not tok: print(title+"\n\n"+body); return
    req=urllib.request.Request(f"https://api.github.com/repos/{repo}/issues",json.dumps({"title":title,"body":body,"labels":["manual-update"]}).encode(),method="POST")
    req.add_header("Authorization",f"Bearer {tok}")
    req.add_header("Content-Type","application/json")
    req.add_header("Accept","application/vnd.github+json")
    try:
        with urllib.request.urlopen(req) as r: print("Issue: "+json.loads(r.read())["html_url"])
    except urllib.error.HTTPError as e: print(f"HTTP {e.code}")
def main():
    info,apps={},[]
    for f in sys.argv[1].split():
        f=f.strip()
        if not f.startswith("apps/") or f not in FILE_MAP: continue
        cl=changelog(f); sc,cas=sections(f,cl)
        info[f]={"cl":cl,"sc":sc,"cas":cas}
        apps.append(os.path.basename(f).replace('.jsx',''))
    if not info: print("No tracked files."); return
    lines=["## Manual Update Required",f"**{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}**\n---"]
    for f,d in info.items():
        e=FILE_MAP.get(f,{})
        lines+=[f"### `{f}`",f"**Manual:** `{e.get('manual','?')}`\n","**CHANGELOG:**"]+[f"- {c}" for c in d["cl"]]+["","**Sections:**"]+[f"- `#{s}`" for s in d["sc"]]+[""]
        if d["cas"]: lines+=["**Cascade:**"]+[f"- `{FILE_MAP.get(c,{}).get('manual',c)}`" for c in d["cas"]]+[""]
    lines+=["---","## Cowork: edit the HTML sections listed, commit, push, then go to Actions → Deploy Manuals → Run workflow → enter what changed → Run."]
    body="\n".join(lines)
    issue(f"Manual update: {', '.join(apps)} [{datetime.utcnow().strftime('%Y-%m-%d')}]",body)
main()
