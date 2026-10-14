#!/usr/bin/env python3
"""DETERMINISTIC PRICE-vs-QUANTITY SWEEP for the ground-station PCBA.

Repeatable and version-controlled: same inputs -> same table, every time. No network calls and no
dated prices are invented -- the inputs come from a committed JSON file so the sweep can be re-run
byte-identically and re-priced when the inputs change.

Usage:
    python3 tracker/hardware/base_station/sweep_price_qty.py
    python3 tracker/hardware/base_station/sweep_price_qty.py --json   # machine-readable table

Inputs: tracker/hardware/base_station/price_qty_inputs.json
Output: a table + (with --json) a JSON block for diffing.

WHY THIS SHAPE: the operator asked for a price-vs-quantity sweep "like the contextvm one for the hub
board", deterministic and repeatable. Determinism comes from (a) inputs in a committed file, (b) a
pure function, (c) explicit rounding. Nothing here reads the clock or the network.
"""
import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
INPUTS = os.path.join(HERE, "price_qty_inputs.json")

# ---------------------------------------------------------------------------------------------
# JLC pricing model. Terms are named so each can be challenged with evidence.
#
# PCB: JLC's 4-layer 0.8mm pricing is TIERED and the per-board price falls until the panel (or the
#      order) is full, then the engineering/setup cost amortises away.
# PCBA: a per-order setup (stencil + first-article) PLUS a per-joint cost PLUS per-part feeder
#      loading. The per-joint fee is the one figure the campaign had NOT measured (flagged open).
# ---------------------------------------------------------------------------------------------
def pcb_cost(qty, p):
    """PCB only. Tiered unit price, then the fixed engineering fee once."""
    unit = None
    for tier in sorted(p["pcb_tiers"], key=lambda t: t["max_qty"]):
        if qty <= tier["max_qty"]:
            unit = tier["unit_usd"]
            break
    if unit is None:
        unit = p["pcb_tiers"][-1]["unit_usd"]
    return qty * unit + p["pcb_engineering_usd"]


def pcba_cost(qty, p):
    """Assembly: setup (stencil + first article) + per-joint + per-feeder-load."""
    joints = p["placements"] * p["joints_per_placement"]
    per_board = joints * p["per_joint_usd"] + p["placements"] * p["per_feeder_usd"]
    return p["pcba_setup_usd"] + qty * per_board


def bom_cost(qty, p):
    """Components. Per-unit BOM times an attrition factor (spares for handling loss)."""
    return qty * p["bom_unit_usd"] * p["attrition"]


def total(qty, p):
    pcb = pcb_cost(qty, p)
    asm = pcba_cost(qty, p)
    bom = bom_cost(qty, p)
    return dict(qty=qty, pcb=pcb, assembly=asm, bom=bom, total=pcb + asm + bom,
                per_board=(pcb + asm + bom) / qty)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="emit a machine-readable table")
    ap.add_argument("--inputs", default=INPUTS)
    a = ap.parse_args()

    p = json.load(open(a.inputs, encoding="utf-8"))
    qtys = p["sweep_quantities"]
    rows = [total(q, p) for q in qtys]

    if a.json:
        print(json.dumps({"inputs": p, "rows": rows}, indent=2, sort_keys=True))
        return 0

    print("GROUND-STATION PCBA v1 -- PRICE vs QUANTITY")
    print(f"inputs: {os.path.relpath(a.inputs)}")
    print(f"  placements {p['placements']}  joints/placement {p['joints_per_placement']}  "
          f"-> {p['placements'] * p['joints_per_placement']} joints/board")
    print(f"  BOM ${p['bom_unit_usd']:.2f}/board  attrition x{p['attrition']:.2f}  "
          f"per-joint ${p['per_joint_usd']:.4f}  per-feeder ${p['per_feeder_usd']:.4f}")
    print()
    print(f"{'qty':>4} | {'PCB':>9} | {'assembly':>9} | {'BOM':>9} | {'TOTAL':>10} | {'per board':>10}")
    print("-" * 68)
    for r in rows:
        print(f"{r['qty']:>4} | {r['pcb']:>9.2f} | {r['assembly']:>9.2f} | {r['bom']:>9.2f} | "
              f"{r['total']:>10.2f} | {r['per_board']:>10.2f}")

    base = rows[0]
    print()
    print("=== marginal analysis (vs the smallest quantity) ===")
    print(f"{'qty':>4} | {'added cost':>11} | {'added boards':>13} | {'marginal $/board':>17}")
    print("-" * 56)
    for r in rows[1:]:
        dq = r["qty"] - base["qty"]
        dc = r["total"] - base["total"]
        print(f"{r['qty']:>4} | {dc:>11.2f} | {dq:>13} | {dc / dq:>17.2f}")

    print()
    print("=== the operator's requirement ===")
    print(f"  at least TWO stations. spares recommended.")
    for r in rows:
        print(f"  qty {r['qty']:>3}: ${r['total']:>8.2f} total, ${r['per_board']:>6.2f}/board"
              f"{'   <-- 2 stations' if r['qty'] == 2 else ''}"
              f"{'   <-- 2 stations + 2 spares' if r['qty'] == 4 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
