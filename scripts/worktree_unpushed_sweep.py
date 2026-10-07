#!/usr/bin/env python3
"""Sweep every balloon-fresh worktree for UNPUSHED work (fast variant).

Risk model: an unpushed commit or an uncommitted edit inside a worktree is
destroyed if that worktree is pruned. This reports both, per worktree.

Fast: ONE fetch, then compare against the remote-tracking ref
`refs/remotes/github/<branch>` instead of a `git ls-remote` per worktree.

Reads only. Never pushes, never commits, never mutates a worktree.
"""
import subprocess
import os
import sys

MAIN = os.path.expanduser("~/repos/balloon-fresh")


def git(args, cwd):
    p = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def main():
    print("fetching github (once)...", flush=True)
    git(["fetch", "-q", "github"], MAIN)

    rc, out, err = git(["worktree", "list", "--porcelain"], MAIN)
    if rc != 0:
        print("cannot list worktrees:", err)
        return 1

    wts, cur = [], {}
    for line in out.splitlines():
        if line.startswith("worktree "):
            if cur:
                wts.append(cur)
            cur = {"path": line.split(" ", 1)[1]}
        elif line.startswith("branch "):
            cur["ref"] = line.split(" ", 1)[1]
        elif line.strip() == "detached":
            cur["ref"] = "refs/heads/(detached)"
    if cur:
        wts.append(cur)

    # cache each branch's tip once (worktrees often share a branch or are unique)
    tips = {}
    for w in wts:
        b = w.get("ref", "").replace("refs/heads/", "")
        if b and b not in tips:
            _, sha, _ = git(["rev-parse", "refs/remotes/github/" + b], MAIN)
            tips[b] = sha

    at_risk = []
    print()
    print("%-44s %-30s %5s %5s %s" % ("WORKTREE", "BRANCH", "DIRTY", "AHEAD", "PUSHED"))
    print("-" * 104)
    for w in wts:
        path = w["path"]
        branch = w.get("ref", "?").replace("refs/heads/", "")
        if not os.path.isdir(path):
            continue
        _, st, _ = git(["status", "--porcelain"], path)
        lines = [l for l in st.splitlines() if l.strip()]
        dirty = len([l for l in lines if not l.startswith("??")])
        untracked = len([l for l in lines if l.startswith("??")])

        if branch == "(detached)":
            ahead, pushed = "?", "DETACHED"
        else:
            remote_sha = tips.get(branch, "")
            _, head, _ = git(["rev-parse", "HEAD"], path)
            if not remote_sha:
                pushed = "NO-REMOTE-REF"
                _, cnt, _ = git(["rev-list", "--count", "HEAD"], path)
                ahead = cnt
            else:
                _, cnt, _ = git(["rev-list", "--count", remote_sha + "..HEAD"], path)
                ahead = cnt
                pushed = "yes" if cnt == "0" else "NO"

        risky = pushed in ("NO", "NO-REMOTE-REF", "DETACHED") or dirty > 0 or untracked > 0
        if risky:
            at_risk.append((path, branch, dirty, untracked, ahead, pushed))
        print("%-44s %-30s %5d %5s %s" % (path[-44:], branch[:30], dirty, ahead, pushed))

    print()
    print("=" * 104)
    if not at_risk:
        print("NOTHING AT RISK: every worktree is clean and its branch is fully pushed.")
        return 0
    print("%d WORKTREE(S) HOLD UNPUSHED OR UNCOMMITTED WORK:" % len(at_risk))
    for path, branch, dirty, untracked, ahead, pushed in at_risk:
        print("  - %s" % path)
        print("      branch=%s  uncommitted=%d  untracked=%d  ahead=%s  pushed=%s"
              % (branch, dirty, untracked, ahead, pushed))
    return 2


if __name__ == "__main__":
    sys.exit(main())
