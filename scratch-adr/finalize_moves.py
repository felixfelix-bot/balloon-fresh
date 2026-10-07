#!/usr/bin/env python3
"""Insert the renumber header under the title of each moved ADR, then git mv it."""
import os
import subprocess
import sys

REPO = "/home/c03rad0r/worktrees/bf-v9-renumber"
os.chdir(REPO)

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
HDR = ("Renumbered from ADR-{old:03d} on 2026-10-07 to remove a duplicate number; "
       "content otherwise unchanged.")


def main():
    for old, new in MOVES:
        src = os.path.join("docs/adr", old)
        lines = open(src, encoding="utf-8").read().split("\n")
        if not lines[0].startswith("# "):
            sys.exit("!! %s: line 1 is not an H1 title" % src)
        if HDR.format(old=int(old[:3])) in "\n".join(lines[:5]):
            print("already headered: %s" % src)
            continue
        insert = ["", HDR.format(old=int(old[:3])), ""]
        # keep exactly one blank line between title and the new line
        rest = lines[1:]
        while rest and rest[0].strip() == "":
            rest = rest[1:]
        newlines = [lines[0]] + insert + rest
        open(src, "w", encoding="utf-8").write("\n".join(newlines))
        print("headered: %s (+1 line)" % src)

    for old, new in MOVES:
        r = subprocess.run(["git", "mv", "docs/adr/" + old, "docs/adr/" + new],
                           capture_output=True, text=True)
        print("git mv %s -> %s : rc=%d %s" % (old, new, r.returncode, r.stderr.strip()))


if __name__ == "__main__":
    main()
