import json, os, subprocess
WT = os.path.expanduser("~/worktrees/bf-consolidate")
d = json.load(open(os.path.expanduser("~/reports/balloon-consolidation/triage.json")))

def sh(c):
    r = subprocess.run(c, shell=True, capture_output=True, text=True, cwd=WT)
    return r.stdout.strip()

print("branch                           new  equiv  already?")
res = {}
for x in d["unmerged"]:
    out = sh('git cherry -v HEAD "%s" 2>/dev/null' % x["ref"]) if False else sh('git cherry HEAD "' + x["ref"] + '" 2>/dev/null')
    lines = [l for l in out.splitlines() if l.strip()]
    new = [l for l in lines if l.startswith("+")]
    eq = [l for l in lines if l.startswith("-")]
    res[x["branch"]] = {"new": len(new), "equiv": len(eq)}
    tag = "OBSOLETE" if new == [] and lines else ("NEW-WORK" if lines else "EMPTY")
    print(f'{x["branch"]:<34} {len(new):>3}  {len(eq):>3}   {tag}')
json.dump(res, open(os.path.expanduser("~/reports/balloon-consolidation/cherry.json"), "w"), indent=1)
