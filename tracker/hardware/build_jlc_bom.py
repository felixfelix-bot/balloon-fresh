#!/usr/bin/env python3
"""Build the CORRECTED JLCPCB PCBA BOM for the v9 hub, verified against the shipped board.

TWO DEFECTS IN THE EXISTING CSV ARE FIXED HERE:
 1. LINE 6 IS MALFORMED: `BAT54W (sub for BAT54, SOD-123),D1,...` has an UNQUOTED comma
    inside the Comment field, shifting Kommentar/Designator/Footprint/LCSC columns. A parser
    reads Designator as "SOD-123)" and loses D1 entirely -- so **D1, the Schottky, would not
    be assembled**. Fixed by quoting the field.
 2. FOUR DNP ROWS NAME PARTS THAT ARE NOT ON THE BOARD: FID1, FID3, TH1, TH2 come from the
    superseded F33 board. Harmless but they are noise JLC must resolve; removed.

THIRD, A CONFLICT WITH THE LOCKED ORDER SPLIT (reported, not silently resolved):
 The existing BOM has U5 (MAX-M10S GPS) and U6 (MS5611 baro) as POPULATED lines with LCSC
 numbers. The LOCKED SPLIT says "no baro; GPS as DNP rows + 4 loose". I set the DNP flags to
 match the LOCKED SPLIT, so this script emits them as DNP rows and records the conflict.
"""
import csv

SRC = "/home/c08r4d0r/jlc-pcba-work/hub_v9_bom_pcba.csv"
OUT = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9-bom-jlc.csv"

NOT_ON_BOARD = {"FID1", "FID3", "TH1", "TH2"}
PER_LOCKED_SPLIT_DNP = {"U5", "U6"}   # GPS + baro
HAND_INSTALL_DNP = {"C_CAP1", "C_CAP2", "D_CLAMP", "R_NTC1", "TH_NTC1",
                    "U2", "U3", "J_VCC", "J_W1", "J_W2", "J_W3", "J_W4"}

rows_raw = list(csv.reader(open(SRC)))
hdr = rows_raw[0]
rows = []
for r in rows_raw[1:]:
    if len(r) == 4:
        rows.append(dict(zip(hdr, r)))
    elif len(r) == 5:
        # DEFECT 1: the unquoted comma in the Comment field splits this row into 5.
        # Re-join the first two fields and recover the real Designator (D1).
        comment = r[0] + "," + r[1]
        rows.append({hdr[0]: comment, hdr[1]: r[2], hdr[2]: r[3], hdr[3]: r[4]})
        print(f"repaired malformed row: Comment={comment!r} Designator={r[2]!r} LCSC={r[4]!r}")
    else:
        raise SystemExit(f"unexpected field count {len(r)}: {r}")

out = []
dropped_refs = set()
retagged = []

for r in rows:
    refs = [d.strip() for d in r["Designator"].split(",")]
    # drop the not-on-board noise rows entirely
    keep = [d for d in refs if d not in NOT_ON_BOARD]
    dropped_refs |= (set(refs) - set(keep))
    if not keep:
        continue
    lcsc = r["LCSC Part #"].strip()
    # re-tag U5/U6 as DNP per the LOCKED SPLIT (the board flags already say DNP)
    if set(keep) & PER_LOCKED_SPLIT_DNP and lcsc.upper() != "DNP":
        retagged.append((keep, r["Comment"], lcsc))
        lcsc = "DNP"
        r["Comment"] = r["Comment"] + " [LOCKED SPLIT: no baro; GPS as DNP rows + 4 loose]"
    out.append({
        "Comment": r["Comment"],          # csv writer QUOTES this, fixing defect 1
        "Designator": ",".join(keep),
        "Footprint": r["Footprint"],
        "LCSC Part #": lcsc,
    })

with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["Comment", "Designator", "Footprint", "LCSC Part #"],
                       quoting=csv.QUOTE_MINIMAL)
    w.writeheader()
    w.writerows(out)

print(f"wrote {OUT}: {len(out)} lines")
print(f"dropped not-on-board refs: {sorted(dropped_refs)}")
print(f"re-tagged DNP per the LOCKED SPLIT: {[(r, c, l) for r, c, l in retagged]}")
print()
# verify the file parses with exactly 4 fields per row
bad = 0
for i, line in enumerate(open(OUT), 1):
    q = False
    c = 0
    for ch in line:
        if ch == '"':
            q = not q
        elif ch == "," and not q:
            c += 1
    if c != 3:
        bad += 1
        print(f"  MALFORMED line {i}: {line.rstrip()[:80]}")
print(f"malformed rows: {bad}")
print()
assemble = [r for r in out if r["LCSC Part #"].upper() != "DNP"]
print(f"lines to ASSEMBLE: {len(assemble)}")
for r in assemble:
    print(f"  {r['LCSC Part #']:10s} {r['Comment'][:42]:42s} {r['Designator'][:44]}")
