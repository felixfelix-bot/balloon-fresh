import json, os, subprocess
WT = os.path.expanduser("~/worktrees/bf-consolidate")
d = json.load(open(os.path.expanduser("~/reports/balloon-consolidation/triage.json")))

def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True, cwd=WT)
    return r.stdout.strip()

rows = []
for x in d["unmerged"]:
    meta = sh('git log -1 --format="%ad~%an~%s" --date=short "' + x["ref"] + '"')
    rows.append((x, meta.split("~", 2)))
for x, m in sorted(rows, key=lambda r: r[1][0]):
    ad = m[0] if m else "?"
    an = m[1] if len(m) > 1 else "?"
    subj = m[2] if len(m) > 2 else "?"
    tag = "CLEAN" if x["clean"] else "CONF "
    print(f'{ad} {an:<16} +{x["ahead"]:>3} {len(x["conflicts"]):>2}f {tag} {x["branch"]}')
    print(f'      {subj[:112]}')
