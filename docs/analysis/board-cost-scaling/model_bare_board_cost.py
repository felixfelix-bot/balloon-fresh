#!/usr/bin/env python3
"""model_bare_board_cost.py -- per-board cost vs order quantity, for BARE-board orders.

WHY A SEPARATE MODEL FROM model_board_cost.py. That one prices an ASSEMBLED board: components
from LCSC ladders, a per-joint assembly fee, a placement engineering fee, extended-part reel fees.
None of those apply to a bare-board order, and reusing it would have produced a confident number
for a purchase that does not include any of those costs.

WHAT THIS MODELS, and the one finding that reverses the operator's intuition:

  The operator asked "would it cost a similar amount to make 25?" expecting a flat setup to
  amortise. Measured against JLCPCB's published tier table, **it does not**: quantity is the one
  field that behaves BACKWARDS up to ~qty 30.

      5 boards   $2.00 total   $0.400/board   <- promotional entry price
     10 boards   $5.00 total   $0.500/board
     30 boards  $32.70 total   $1.090/board
    100 boards $109.50 total   $1.095/board

  So 25 boards is not "similar" to 10 -- it is roughly 5-6x the total. The $2 and $5 headline
  prices are loss-leaders for a 5-board prototype and sit BELOW the real panel cost. The true
  per-board price is ~$1.09 and you reach it at qty 30 and stay there.

  This is the opposite of the usual amortisation story, and it is why the plot is worth drawing:
  the curve is CONVEX (rising per-board) up to 30, then flat.
  [CITED comparepcb.com/articles/six-fields-set-your-pcb-price, verified against jlcpcb.com's
  published $2/5pcs and $55/m^2 rows]

WHAT IS AND IS NOT INCLUDED
  included     : bare PCB fabrication at the quoted tier, ENIG where mandatory, the 0.4 mm
                 thin-board manual-review risk flagged separately (it is a LEAD-TIME risk, not a
                 price input we can compute)
  NOT included : shipping (dominates at these prices -- 10 tiny boards ship for more than they
                 cost), VAT/duty, and the SS24 diodes the operator hand-solders
  SS24 cost IS included as a separate line, because it is a real per-board part cost even though
  no assembler touches it: 3 x SMA SS24 per board.

Stdlib only. Every figure printed here is quoted in the study doc.
"""
import math

# ---------------------------------------------------------------- boards under consideration
# Geometry from the repo, measured (see ORDER-SHEET-solar-connector.md).
BOARDS = [
    # name,                     w_mm,  h_mm, layers, thickness_mm, note
    ("solar connector",          34.60, 20.00, 2, 0.4, "wing interconnect, bare order"),
    ("v11 hub",                  72.00, 80.00, 4, 1.6, "spec only, no board file"),
    ("base station + inflator",  70.00, 70.00, 4, 1.6, "ADR-150 combined, no layout"),
    ("pre-stretch rig",          65.00, 50.00, 2, 1.6, "unmerged candidate, 77 opens"),
]

# ---------------------------------------------------------------- JLCPCB published tiers
# [CITED comparepcb.com, cross-checked against jlcpcb.com's own "$2 for 5pcs / $55 per m^2" rows]
# These are 2-layer, <=100x100 mm, 1 oz, HASL, quantity TIERS -- total order price in USD.
TIERS_2L = [(5, 2.00), (10, 5.00), (30, 32.70), (100, 109.50)]

# ENIG is mandatory for the 0.4 mm board (JLC: thickness <= 0.4 mm does not support HASL) and is
# the single most expensive checkbox on a 2-layer prototype. [CITED: HASL $5.00 vs ENIG $23.80 on
# the same quote form] -- that is a +$18.80 one-off, NOT per board.
ENIG_SURCHARGE = 18.80

# 4-layer has a completely different price structure: not "double", roughly 19x on the entry
# point, because lamination and a second drill/lamination pass dominate. [CITED: 2L $5.00 ->
# 4L $95.94 at the same quantity]
FOUR_LAYER_MULTIPLIER = 95.94 / 5.00

# SS24 in SMA, LCSC C50645. 3 per solar connector board. Unit price from the repo's cached ladder
# is ~$0.05-0.09 depending on quantity; use the qty-1 ladder value as the honest upper bound.
SS24_UNIT = 0.09          # [APPROX -- replace with the live LCSC ladder before ordering]
SS24_PER_BOARD = 3


def tier_price(q: int) -> float:
    """Total bare-PCB order price for `q` boards at the 2-layer tier table.

    Below 5 the minimum order applies (JLC will not sell fewer than 5 at this tier), so 1-5 all
    cost the qty-5 price.

    BETWEEN tiers we INTERPOLATE LINEARLY on total price. The first version of this function
    returned the next tier's whole-order price for anything up to that tier, which made qty 50
    cost the qty-100 price ($109.50) and produced a NON-MONOTONIC per-board curve: $2.19/board at
    50, then $1.095 at 100. Per-board cost rising then falling is a pricing artefact, not pricing
    behaviour, and a plot of it would have been a lie about how JLC bills. Quoting a tier's price
    for a quantity below that tier overstates the order.

    Above the last published break we extend on the marginal rate from the final two tiers --
    flagged APPROX, because a real 250-board order should be quoted, not modelled.
    """
    lad = sorted(TIERS_2L)
    if q <= lad[0][0]:
        return lad[0][1]
    for i in range(len(lad) - 1):
        q0, p0 = lad[i]
        q1, p1 = lad[i + 1]
        if q <= q1:
            # linear between the two bracketing tier points, on TOTAL price
            return p0 + (q - q0) * (p1 - p0) / (q1 - q0)
    (q0, p0), (q1, p1) = lad[-2], lad[-1]
    return p1 + (q - q1) * (p1 - p0) / (q1 - q0)


def main() -> int:
    print("=" * 78)
    print("1. THE TIER TABLE, AND WHY 25 IS NOT 'SIMILAR' TO 10")
    print("=" * 78)
    print(f"  {'qty':>5s}{'total':>10s}{'per board':>12s}{'vs qty-5':>12s}")
    print("  " + "-" * 42)
    base = tier_price(5) / 5
    for q in (5, 10, 25, 30, 50, 100):
        t = tier_price(q)
        per = t / q
        print(f"  {q:5d}{t:10.2f}{per:12.3f}{per / base:11.1f}x")
    print()
    print("  The per-board cost RISES 2.7x from qty 5 to qty 30, then flattens.")
    print("  Quantity is the one field that behaves backwards below ~30 boards.")
    print()
    t10, t25 = tier_price(10), tier_price(25)
    print(f"  qty 10 -> ${t10:.2f} total.  qty 25 -> ${t25:.2f} total.")
    print(f"  => 25 boards costs {t25 / t10:.1f}x what 10 costs, for {25/10:.1f}x the boards.")
    print("  => NOT a similar amount. Buying 15 more boards costs "
          f"${t25 - t10:.2f} more than the first 10.")

    print()
    print("=" * 78)
    print("2. PER-BOARD COST, BARE ORDER, ENIG WHERE NEEDED")
    print("=" * 78)
    for name, w, h, layers, thick, note in BOARDS:
        mult = FOUR_LAYER_MULTIPLIER if layers == 4 else 1.0
        enig = ENIG_SURCHARGE if thick <= 0.4 else 0.0
        ss24 = SS24_UNIT * SS24_PER_BOARD if "solar" in name else 0.0
        print(f"\n  {name}  ({w:.1f} x {h:.1f} mm, {layers}L, {thick} mm)  -- {note}")
        print(f"  {'qty':>5s}{'fab total':>12s}{'per board':>11s}{'w/ SS24':>10s}")
        for q in (5, 10, 25, 100):
            fab = tier_price(q) * mult + enig
            per = fab / q + ss24
            print(f"  {q:5d}{fab:12.2f}{fab / q:11.3f}{per:10.3f}")
        if layers == 4:
            print(f"     (4-layer multiplier {mult:.2f}x from the cited entry prices)")

    print()
    print("=" * 78)
    print("3. THE DECISION FOR THE SOLAR CONNECTOR (the only orderable board)")
    print("=" * 78)
    enig = ENIG_SURCHARGE
    ss = SS24_UNIT * SS24_PER_BOARD
    for q in (10, 25):
        fab = tier_price(q) + enig
        total_parts = ss * q
        print(f"  qty {q:3d}: fab ${fab:6.2f} + ENIG included + SS24 ${total_parts:5.2f}"
              f" = ${fab + total_parts:6.2f} total, ${(fab + total_parts) / q:5.2f}/board")
    d = (tier_price(25) + enig + ss * 25) - (tier_price(10) + enig + ss * 10)
    ratio = (tier_price(25) + enig) / (tier_price(10) + enig)
    print(f"\n  25 - 10 = ${d:.2f} more for 15 extra boards "
          f"(${d / 15:.2f} per extra board).")
    print(f"  That IS cheap per extra board -- but the ORDER is {ratio:.1f}x the qty-10 price.")
    print("  'Similar amount' is the wrong model: per-board gets WORSE to qty 30, then flat.")
    print("  The honest framing: the boards are cheap, the ORDER is not free, and SHIPPING")
    print("  probably costs more than either. Confirm with a live JLCONE quote.")

    print()
    print("=" * 78)
    print("4. MARGINAL COST -- where 'one more board is nearly free' actually starts")
    print("=" * 78)
    print(f"  {'qty':>5s}{'marginal $/board':>20s}")
    prev = tier_price(1)
    for q in list(range(5, 31, 5)) + [50, 75, 100, 150]:
        cur = tier_price(q)
        step = q - (q - 5 if q > 5 else 1)
        marg = (cur - prev) / max(step, 1)
        print(f"  {q:5d}{marg:20.2f}")
        prev = cur
    print()
    print("  Marginal cost is at its LOWEST at the small quantities and highest at ~30.")
    print("  The conventional 'flat setup then cheap incremental' story does not hold here.")

    print()
    print("=" * 78)
    print("5. WHAT THIS MODEL CANNOT TELL YOU")
    print("=" * 78)
    print("  1. SHIPPING. At $2-30 order values, freight dominates every number above.")
    print("  2. The 0.4 mm thin-board MANUAL REVIEW (lead time, possibly a surcharge).")
    print("  3. Whether a 34.6 x 20 mm board panels -- PANELIZATION.md is arithmetic only.")
    print("  4. Real 250-board pricing: quote it, do not extrapolate.")
    print("  5. SS24 unit price is APPROX; fetch the live LCSC ladder before ordering.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
