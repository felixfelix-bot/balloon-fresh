#!/usr/bin/env python3
"""Triage balloon-fresh branches that diverge from the consolidation trunk.

Read-only: uses `git merge-tree --write-tree` (never touches worktree/index).
Writes full JSON to ~/reports/balloon-consolidation/triage.json and prints a
compact cluster summary.
"""
import json, os, subprocess, sys

WT = os.path.expanduser("~/worktrees/bf-consolidate")
OUT = os.path.expanduser("~/reports/balloon-consolidation/triage.json")
CODE = (".c", ".h", ".cpp", ".hpp", ".cc", ".py", ".rs", ".go", ".js", ".ts",
        ".tsx", ".jsx", ".sh", ".mk", ".cmake", ".txt.proto")


def sh(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=WT)
    return r.returncode, r.stdout, r.stderr


def kind(p):
    b = os.path.basename(p)
    if p.startswith(".github/") or p.endswith("/CMakeLists.txt") or b == "CMakeLists.txt":
        return "build"
    if "/firmware/" in p or "firmware/" in p or p.startswith("firmware"):
        return "build" if p.endswith((".mk", "sdkconfig.defaults")) else "code"
    if p.endswith(CODE):
        return "code"
    if p.endswith(".proto"):
        return "code"
    if p.endswith((".md", ".txt", ".rst", ".adoc")):
        return "docs"
    return "other"


rc, out, err = sh("git for-each-ref --format='%(refname:short)' refs/remotes/github")
refs = [r.strip() for r in out.splitlines() if r.strip()]
unmerged = []
for r in refs:
    rc, _, _ = sh(f'git merge-base --is-ancestor "{r}" HEAD')
    if rc == 0:
        continue
    rc, o, e = sh(f'git rev-list --left-right --count HEAD..."{r}"')
    try:
        behind, ahead = [int(x) for x in o.split()]
    except Exception:
        behind, ahead = -1, -1
    rc, o, e = sh(f'git merge-tree --write-tree --name-only HEAD "{r}"')
    conflicts, clean = [], (rc == 0)
    if not clean:
        lines = o.splitlines()
        for ln in lines[1:]:
            if ln.strip() == "":
                break
            conflicts.append(ln.strip())
    unmerged.append({
        "branch": r.replace("github/", ""),
        "ref": r,
        "behind": behind,
        "ahead": ahead,
        "clean": clean,
        "conflicts": conflicts,
        "kinds": sorted({kind(p) for p in conflicts}),
    })

# clusters
clusters = {}
for u in unmerged:
    for p in u["conflicts"]:
        clusters.setdefault(p, []).append(u["branch"])

json.dump({"head": sh("git rev-parse HEAD")[1].strip(), "unmerged": unmerged,
           "clusters": clusters}, open(OUT, "w"), indent=1)

print(f"HEAD {sh('git rev-parse --short HEAD')[1].strip()}   unmerged branches: {len(unmerged)}")
clean = [u for u in unmerged if u["clean"]]
print(f"\n== CLEAN (auto-mergeable, no conflicts): {len(clean)} ==")
for u in clean:
    print(f"   +{u['ahead']:>3}  {u['branch']}")

print(f"\n== CONFLICTED: {len(unmerged)-len(clean)} ==")
for u in sorted([x for x in unmerged if not x['clean']], key=lambda x: -len(x["conflicts"])):
    print(f"   +{u['ahead']:>3}  {len(u['conflicts']):>2} files  {','.join(u['kinds']):<12} {u['branch']}")

print(f"\n== FILE CLUSTERS (file -> #branches) ==")
for p, bs in sorted(clusters.items(), key=lambda kv: -len(kv[1])):
    print(f"   {len(bs):>2}x [{kind(p):<5}] {p}")
    if len(bs) > 1:
        print(f"        {'; '.join(bs)}")
print(f"\nJSON: {OUT}")
