#!/usr/bin/env python3
"""Census of citations for the duplicated ADR numbers (compact, decision evidence)."""
import os
import re
import subprocess
import sys

REPO = "/home/c03rad0r/worktrees/bf-v9-renumber"
os.chdir(REPO)

tokens = ["002", "017", "018", "019", "020", "025", "028", "029"]
token_re = re.compile(r"\b0?(%s)\b" % "|".join(t.replace("0", "0") for t in tokens))

files = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()
EXT = (".md", ".py", ".sh", ".c", ".h", ".cpp", ".hpp", ".yaml", ".yml", ".json", ".toml", ".txt", ".cfg", ".ini")

hits = {t: [] for t in tokens}
for f in files:
    if not f.lower().endswith(EXT):
        continue
    if f.startswith("docs/adr/") and re.match(r"\d{3}-", os.path.basename(f)):
        continue  # skip the ADR corpus itself here
    try:
        txt = open(f, encoding="utf-8", errors="replace").read()
    except Exception:
        continue
    for i, line in enumerate(txt.splitlines(), 1):
        # ADR id in prose
        for m in re.finditer(r"ADR-?0?(\d{2,3})", line):
            n = m.group(1).zfill(3)
            if n in hits:
                hits[n].append(("PROSE", f, i, line.strip()[:150]))
        # bare filename / path
        for m in re.finditer(r"(\d{3}-[a-z0-9-]+\.md)", line):
            if m.group(1)[:3] in hits:
                hits[m.group(1)[:3]].append(("PATH", f, i, line.strip()[:150]))

for t in tokens:
    print("=" * 100)
    print("### TOKEN %s  (%d external hits)" % (t, len(hits[t])))
    for kind, f, i, line in hits[t]:
        print("  [%s] %s:%d  %s" % (kind, f, i, line))
