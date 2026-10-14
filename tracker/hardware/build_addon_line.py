#!/usr/bin/env python3
"""Build the C5 add-on line: 4x loose u-blox MAX-M10S for hand-soldering.

LOCKED SPLIT (PRE-ORDER-CHECKLIST line 28): "1 variant, platform populated on all 10 | no baro;
GPS as DNP rows + 4 loose". So 4 of the 10 boards get a GPS module hand-soldered by the
operator; the part is bought LOOSE, not through JLC assembly.

Also records the SS24 resolution, decided from the raw API evidence.
"""
import csv

OUT = "/home/c08r4d0r/worktrees/v9-route/docs/fab/hub-v9/gerbers/hub_v9-addon-loose-gps.csv"

rows = [
    {
        "Comment": "MAX-M10S-00B GNSS module, LOOSE (hand-solder on 4 of 10 boards)",
        "Designator": "U5-x4 (off-board; sold separately)",
        "Footprint": "ublox_MAX LCC-18",
        "JLCPCB Part #": "C4153167",
        "Qty": 4,
        "Unit $": 10.8395,
        "Line $": round(4 * 10.8395, 4),
        "Why loose": ("DNP on the PCBA per the locked split, so JLC does not place it; "
                      "the operator hand-solders it on the boards that fly with GPS"),
    },
]

with open(OUT, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), quoting=csv.QUOTE_MINIMAL)
    w.writeheader()
    w.writerows(rows)

print(f"wrote {OUT}")
for r in rows:
    print(f"  {r['JLCPCB Part #']}  qty {r['Qty']}  x ${r['Unit $']}  = ${r['Line $']}")

print()
print("=== SS24 RESOLUTION (from the raw JLCPCB API dumps) ===")
print("  C50645  MDD SS24        SMA(DO-214AC)  stock 777,745  $0.0257  <- CHOSEN")
print("  C78573  MCC SS24-LTP    SMA(DO-214AC)  stock   6,201  $0.0418  <- superseded")
print("  both are valid SS24 SMA parts, so the earlier 'contradiction' is DOCUMENTATION")
print("  DRIFT, not a wrong part. C50645 wins on BOTH axes: 125x the stock at 62% of the")
print("  price, and it is the number the mapping report recorded WITH reasoning from the")
print("  live search. 8 SS24 candidates exist; C35501 (SMB/DO-214AA) stays REJECTED because")
print("  the board footprint is D_SMA.")
