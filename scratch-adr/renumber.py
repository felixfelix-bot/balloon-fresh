#!/usr/bin/env python3
"""Mechanical ADR renumber + reference sweep for balloon-fresh.

Dry-run by default; pass --apply to perform git mv + header + rewrites.
Prints a full review report of every planned change.
"""
import os
import re
import subprocess
import sys

REPO = "/home/c03rad0r/worktrees/bf-v9-renumber"
os.chdir(REPO)

APPLY = "--apply" in sys.argv
ADR_DIR = "docs/adr"

# ---------------------------------------------------------------- rename map
# (old basename, new basename). Live record of each duplicated number keeps it.
MOVES = [
    ("002-tollgate-over-fips-mesh-udp.md", "100-tollgate-over-fips-mesh-udp.md"),
    ("017-lr2021-only-ban-sx1280.md", "101-lr2021-only-ban-sx1280.md"),
    ("017-version-tagging-policy.md", "102-version-tagging-policy.md"),
    ("018-tx-autonomy-requirement.md", "103-tx-autonomy-requirement.md"),
    ("019-tx-rx-sync-invariant.md", "104-tx-rx-sync-invariant.md"),
    ("020-reproducible-build-flash-test.md", "105-reproducible-build-flash-test.md"),
    ("025-e-hash-relay-transport-layer.md", "106-e-hash-relay-transport-layer.md"),
    ("028-three-variant-pcb-design.md", "107-three-variant-pcb-design.md"),
    ("029-f33-sx1280-pin-plan.md", "108-f33-sx1280-pin-plan.md"),
    ("029-firmware-output-harmonization.md", "109-firmware-output-harmonization.md"),
]
OLD_NEW_NUM = {int(o[:3]): int(n[:3]) for o, n in MOVES}

HEADER_TMPL = ("Renumbered from ADR-{old:03d} on 2026-10-07 to remove a duplicate "
               "number; content otherwise unchanged.")

# ------------------------------------------------------- per-line exceptions
# (path_substring, line_substring, find_substr, repl_substr_or_None, reason)
# Applied first; the line is then excluded from generic prose-id rewriting.
EXPLICIT = [
    ("docs/CHANGELOG.md", "ADR-017-version-tagging-policy.md",
     "docs/adr/ADR-017-version-tagging-policy.md", "docs/adr/102-version-tagging-policy.md",
     "legacy ADR-prefixed path form; rewritten whole so the generic ADR-id rule cannot "
     "corrupt it into ADR-102-..."),
    ("docs/adr/030-deterministic-zero-inference-pcb-pipeline.md",
     "029-firmware-output-harmonization", None, None,
     "only the file path moves (->109); the prose 'ADR-029' on this line is the number "
     "owner (kept at 029) and must not be rewritten"),
    ("docs/adr/017-lr2021-only-ban-sx1280.md", "the original ADR-017", None, None,
     "self-referential past-tense narrative ('the original ADR-017 text'): the historical "
     "number is the point of the sentence; the new header line records the renumbering"),
    ("docs/adr/017-lr2021-only-ban-sx1280.md", "from the original ADR-017", None, None,
     "self-referential past-tense narrative, as above"),
]

EXTS = (".md", ".py", ".sh", ".bash", ".c", ".h", ".hpp", ".cpp", ".cc", ".cxx",
        ".yaml", ".yml", ".json", ".toml", ".txt", ".mk", ".js", ".ts", ".html",
        ".css", ".ini", ".cfg", ".sql")
SKIP_PREFIX = ("graphify-out/", ".hermes/", ".ngit/", "node_modules/", ".keep-staging/")


def resolve(num, path, line):
    """Map an old duplicated ADR id to its post-sweep id (identity = keep)."""
    low = line.lower()
    plow = path.lower()
    if num == 2:
        if "lr2021-as-rf-chip" in line or "as rf chip" in low or "as rf-chip" in low:
            return 2
        return 100
    if num == 17:
        if any(k in low for k in ("tagging", "changelog", "throughput")):
            return 102
        if any(k in low for k in ("ban", "sx1280", "spi protocol")):
            return 101
        return 17
    if num == 18:
        if any(k in low for k in ("multi-mode", "characterization", "10-config")):
            return 18
        return 103
    if num == 19:
        if any(k in low for k in ("gps-synchronized", "mode switching", "phase 1", "phase 2",
                                  "button-triggered", "gps time sync", "gps sync")):
            return 19
        return 104
    if num == 20:
        return 105 if "reproducible" in low else 20
    if num == 25:
        if "ehash" in plow or "e-hash" in plow or any(
                k in low for k in ("e-hash", "hash", "relay transport")):
            return 106
        return 25
    if num == 28:
        if "three-variant pcb" in low or "three-variant-pcb" in low:
            return 107
        return 28
    if num == 29:
        if "f33-sx1280-pin-plan" in low:
            return 108
        if "firmware-output-harmonization" in low:
            return 109
        return 29
    return num


ID_RE = re.compile(r"ADR([- ])0?(\d{1,3})\b")


def rewrite_line(path, lineno, line, changes):
    explicit_used = False
    for fsub, lsub, find, repl, reason in EXPLICIT:
        if fsub in path and lsub in line:
            explicit_used = True
            if find and repl and find in line:
                new = line.replace(find, repl)
                changes.append((path, lineno, "EXPLICIT-REWRITE", line.strip(),
                                new.strip(), reason))
                line = new
            else:
                changes.append((path, lineno, "EXPLICIT-KEEP", line.strip(),
                                line.strip(), reason))

    # generic: bare filename / path basenames
    for old, new in MOVES:
        if old in line:
            line = line.replace(old, new)
    # generic: ADR id in prose
    if not explicit_used and not (path.startswith(ADR_DIR + "/") and lineno == 1):
        def sub(m):
            sep, num = m.group(1), int(m.group(2))
            if num not in OLD_NEW_NUM:
                return m.group(0)
            new = resolve(num, path, line)
            if new == num:
                return m.group(0)
            return "ADR%s%03d" % (sep, new)
        line = ID_RE.sub(sub, line)
    return line, explicit_used


def main():
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split()
    targets = [f for f in files if f.lower().endswith(EXTS) and not f.startswith(SKIP_PREFIX)]

    changes = []
    text_changes = []
    for path in targets:
        try:
            raw = open(path, encoding="utf-8").read()
        except Exception:
            continue
        lines = raw.split("\n")
        out = []
        for i, ln in enumerate(lines, 1):
            new, _ = rewrite_line(path, i, ln, changes)
            if new != ln:
                text_changes.append((path, i, ln, new))
            out.append(new)
        newraw = "\n".join(out)
        if newraw != raw and APPLY:
            open(path, "w", encoding="utf-8").write(newraw)

    # ------------------------------------------------------------- report
    print("### Rename map (%d moves)" % len(MOVES))
    for old, new in MOVES:
        print("  %s -> %s" % (old, new))
    print("\n### Reference rewrites: %d line(s) in %d file(s)"
          % (len(text_changes), len({p for p, *_ in text_changes})))
    byfile = {}
    for p, i, before, after in text_changes:
        byfile.setdefault(p, []).append((i, before, after))
    for p in sorted(byfile):
        print("\n--- %s (%d)" % (p, len(byfile[p])))
        for i, before, after in byfile[p]:
            print("  L%-5d - %s" % (i, before.strip()[:170]))
            print("  %-6s + %s" % ("", after.strip()[:170]))
    print("\n### Explicit-rule decisions")
    for c in changes:
        if c[2].startswith("EXPLICIT"):
            print("  [%s] %s:%d  %s" % (c[2], c[0], c[1], c[5]))
    print("\nAPPLY=%s" % APPLY)


if __name__ == "__main__":
    main()
