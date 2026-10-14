#!/usr/bin/env python3
"""FIX the CPL/BOM contradiction: make the CPL carry an explicit DNP flag, derived FROM the BOM.

The CPL is the file JLC reads to decide what to PLACE. The BOM is where DNP is recorded. Measured
2026-10-14: the BOM flags 14 designators DNP and the CPL lists 12 of them as placements, with NO DNP
column at all -- so handed to JLC as-is, 12 DNP parts would be POPULATED.

This script makes the state MACHINE-READABLE and SINGLE-SOURCED:
  * reads the DNP set from the BOM (the authority)
  * rewrites the CPL with an added `DNP` column, `Y` for those designators, empty otherwise
  * writes a JSON record of what it changed, so the change is auditable and diffable

It does NOT invent a DNP decision. It propagates the BOM's existing flags. The operator still owes
a FUNCTIONAL ruling on C_CAP1/C_CAP2 (stored energy), which this makes visible rather than solves.

Usage:
    python3 tracker/hardware/fix_cpl_dnp.py --check   # report only, change nothing
    python3 tracker/hardware/fix_cpl_dnp.py --write    # rewrite the CPL
"""
import argparse
import json
import os

WT = "/home/c08r4d0r/worktrees/v9-route"
BOM = os.path.join(WT, "docs/fab/hub-v9/gerbers/hub_v9-bom-jlc.csv")
CPL = os.path.join(WT, "docs/fab/hub-v9/gerbers/hub_v9-cpl-jlcpcb.csv")


def parse_rows(text):
    rows = []
    for line in text.splitlines():
        if not line.strip():
            continue
        cells, cur, inq = [], "", False
        for ch in line:
            if ch == '"':
                inq = not inq
            elif ch == "," and not inq:
                cells.append(cur)
                cur = ""
            else:
                cur += ch
        cells.append(cur)
        rows.append(cells)
    return rows


def dnp_from_bom():
    """The BOM is the single authority for DNP."""
    refs = set()
    notes = {}
    for r in parse_rows(open(BOM, encoding="utf-8", errors="replace").read()):
        if any(c.strip().upper() == "DNP" for c in r) and len(r) > 1:
            for ref in r[1].split(","):
                ref = ref.strip().strip('"')
                if ref:
                    refs.add(ref)
                    notes[ref] = r[0].strip().strip('"')
    return refs, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    dnp, notes = dnp_from_bom()
    raw = open(CPL, encoding="utf-8", errors="replace").read()
    newline = "\r\n" if "\r\n" in raw else "\n"
    rows = parse_rows(raw)
    hdr = [c.strip().strip('"') for c in rows[0]]

    if "DNP" in hdr:
        print("CPL already carries a DNP column -- nothing to add.")
        return 0

    out_rows = [hdr + ["DNP"]]
    flagged = []
    for r in rows[1:]:
        if not r:
            continue
        ref = r[0].strip().strip('"')
        is_dnp = ref in dnp
        if is_dnp:
            flagged.append(ref)
        out_rows.append([c.strip().strip('"') for c in r] + ["Y" if is_dnp else ""])

    print(f"BOM flags {len(dnp)} designators DNP.")
    print(f"CPL places {len(rows) - 1} designators; adding a DNP column.")
    print(f"Flagged in the CPL: {len(flagged)} -> {sorted(flagged)}")
    print()

    if a.check or not a.write:
        print("(check mode -- nothing written. Re-run with --write to apply.)")
        return 0

    with open(CPL, "w", encoding="utf-8", newline="") as f:
        for r in out_rows:
            f.write(",".join(r) + newline)

    record = {
        "_why": ("The CPL is what JLC reads to PLACE parts; the BOM is where DNP is recorded. "
                 "The CPL had no DNP column, so 12 designators flagged DNP in the BOM were listed "
                 "as placements. This adds the column, derived FROM the BOM, so the state is "
                 "machine-readable and single-sourced."),
        "source_of_truth": os.path.relpath(BOM, WT),
        "cpl": os.path.relpath(CPL, WT),
        "dnp_designators": sorted(flagged),
        "dnp_notes": {r: notes[r] for r in sorted(flagged) if r in notes},
        "still_operator_owned": (
            "C_CAP1/C_CAP2: the BOM's DNP flag is now visible in the CPL, but whether the supercaps "
            "should be DNP on the FLIGHT board is a FUNCTIONAL ruling -- it changes stored energy, "
            "not just the placement list. This change makes the existing BOM state explicit; it "
            "does not decide it."
        ),
    }
    rec_path = os.path.join(os.path.dirname(CPL), "hub_v9-cpl-dnp-record.json")
    with open(rec_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, sort_keys=True)
    print(f"wrote {os.path.relpath(CPL, WT)}")
    print(f"wrote {os.path.relpath(rec_path, WT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
