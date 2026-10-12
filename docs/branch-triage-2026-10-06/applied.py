#!/usr/bin/env python3
"""Effect-superseded test: can the branch's change be REVERSE-applied to the trunk?

If `git apply --check -R` succeeds for a file, the branch's version of that file
is already the trunk's version (i.e. the branch carries nothing new there).
Read-only: --check never writes.
"""
import json, os, subprocess

WT = os.path.expanduser("~/worktrees/bf-consolidate")
d = json.load(open(os.path.expanduser("~/reports/balloon-consolidation/TRIAGE.json")))


def sh(c, inp=None):
    r = subprocess.run(c, shell=True, capture_output=True, text=True, cwd=WT, input=inp)
    return r.returncode, r.stdout, r.stderr


print("branch                            already-applied conflicted-files")
rows = []
for b in d["branches"]:
    ref = "github/" + b["branch"]
    rc, base, _ = sh('git merge-base HEAD "%s"' % ref)
    base = base.strip()
    hit = []
    for f in b["files"]:
        p = f["path"]
        rc, patch, _ = sh('git diff "%s" "%s" -- "%s"' % (base, ref, p))
        if not patch.strip():
            hit.append((p, "same-as-trunk"))
            continue
        rc, _, err = sh('git apply --check -R -', inp=patch)
        if rc == 0:
            hit.append((p, "already-applied"))
    rows.append((b["branch"], len(hit), len(b["files"]), hit))

for br, n, tot, hit in sorted(rows, key=lambda r: (-r[1], r[0])):
    flag = "  <== EFFECT-SUPERSEDED" if tot and n >= max(1, tot // 2) else ""
    print(f'{br:<33} {n:>2}/{tot:<2}{flag}')
    for p, why in hit:
        print(f'        [{why}] {p}')

js = {br: {"applied": n, "total": tot, "files": [p for p, _ in h]}
      for br, n, tot, h in rows}
json.dump(js, open(os.path.expanduser("~/reports/balloon-consolidation/applied.json"), "w"), indent=1)
print("\nwrote ~/reports/balloon-consolidation/applied.json")
