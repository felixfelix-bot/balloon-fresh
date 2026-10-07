#!/usr/bin/env python3
"""Docs link check: every reference to a docs/adr/*.md file must resolve.

Checks two forms:
  * markdown link target containing '/adr/'  -> resolved relative to the linking file
  * a backticked / bare path 'docs/adr/<file>.md' -> resolved from the repo root
"""
import os
import re
import subprocess

REPO = "/home/c03rad0r/worktrees/bf-v9-renumber"
os.chdir(REPO)

MDLINK = re.compile(r"\]\(([^)\s]*?/adr/[^)\s]*?\.md)(#[^)]*)?\)")
BARE = re.compile(r"(docs/adr/[A-Za-z0-9._-]+\.md)")

files = [f for f in subprocess.run(["git", "ls-files"], capture_output=True,
                                   text=True).stdout.split() if f.endswith(".md")]

bad = []
checked = 0
for f in files:
    txt = open(f, encoding="utf-8", errors="replace").read()
    for m in MDLINK.finditer(txt):
        target = m.group(1)
        resolved = os.path.normpath(os.path.join(os.path.dirname(f), target))
        checked += 1
        if not os.path.exists(resolved):
            bad.append((f, target, resolved, "relative link"))
    for m in BARE.finditer(txt):
        target = m.group(1)
        checked += 1
        if not os.path.exists(target):
            bad.append((f, target, target, "root-relative path"))

print("checked %d docs/adr reference(s) across %d markdown file(s)" % (checked, len(files)))
if bad:
    print("BROKEN (%d):" % len(bad))
    for f, t, r, kind in bad:
        print("  %s -> %s  [%s]" % (f, t, kind))
else:
    print("OK: every docs/adr/*.md reference resolves")
