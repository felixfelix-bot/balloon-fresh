#!/usr/bin/env python3
"""Numbers behind docs/analysis/wing-release-electrical-contacts.md.

Extends docs/analysis/wing-jettison.md (the primary release-mechanism study).
Every figure quoted in that analysis is printed here. stdlib only, no args.

Run:  python3 docs/analysis/wing_release_electrical.py
"""

from __future__ import annotations

import math

G = 9.80665

# --- inputs, each traced to a source -----------------------------------------
M_WING_KG = 3.2e-3      # wing-jettison.md s7 (3.2 g shed per release)
SHOCK_G = 10.0          # wing-jettison.md s2.1 (assumed burst shock)
DESIGN_MARGIN = 1.5     # study convention
NICHROME_CUT_J = 2.59   # wing-jettison.md s3.2
NIGHT_BUDGET_W = 100e-6 # ADR-036 (100 uW night budget)

# magnetic materials
NDFEB_TEMPCO_K = -0.0011    # reversible Br coefficient, ~-0.11 %/K
COLD_C, WARM_C = -60.0, 20.0

# thermal constants (physical, not measured cuts)
NYLON_MELT_C, NYLON_K = 260.0, 0.25
COPPER_MELT_C, COPPER_K = 1085.0, 400.0

# power classes (commercial figures -> TODO(unverified) in the doc)
HOLD_CLASSES_W = {
    "passive magnetic hold": 0.0,
    "reed + coil (while energised)": 20e-3,
    "bucking electromagnet": 350e-3,
    "non-latching solenoid": 250e-3,
}

# pulse energy to release a latching mechanism (ms, W)
PULSES = [(10, 0.15), (50, 0.15), (100, 0.30), (500, 0.30)]


def mN(x: float) -> float:
    return x * 1000.0


def main() -> None:
    print("=" * 78)
    print("WING RELEASE -- MAGNETIC/SOLENOID TRADEOFF ARITHMETIC")
    print("=" * 78)

    print("\n-- 1. HOLDING FORCE REQUIRED (wing mass 3.2 g) " + "-" * 30)
    w = M_WING_KG * G
    print(f"  wing weight at 1 g                = {mN(w):8.2f} mN")
    print(f"  burst shock {SHOCK_G:.0f} g-equivalent          = {mN(w*SHOCK_G):8.2f} mN")
    print(f"  x{DESIGN_MARGIN} design margin            = {mN(w*SHOCK_G*DESIGN_MARGIN):8.2f} mN"
          f"  (~{mN(w*SHOCK_G*DESIGN_MARGIN)/G:.1f} gf)")
    print("  -> a 3x1 mm NdFeB disc already covers this. Force is NOT the problem.")

    print("\n-- 2. NdFeB COLD BEHAVIOUR (the tradeoff that works against you) " + "-" * 15)
    dT = COLD_C - WARM_C
    factor = 1.0 + NDFEB_TEMPCO_K * dT
    print(f"  dT from {WARM_C:.0f} C to {COLD_C:.0f} C   = {dT:+.0f} K")
    print(f"  Br ratio (1 + a*dT)               = {factor:.4f}  ({(factor-1)*100:+.1f} %)")
    print(f"  holding force at -60 C            = {mN(w*SHOCK_G*DESIGN_MARGIN*factor):8.2f} mN")
    print("  -> force INCREASES in the cold: more certain to HOLD,")
    print("     less certain to RELEASE, exactly when the rail is weakest.")

    print("\n-- 3. STATIC POWER vs THE NIGHT BUDGET (the disqualifier) " + "-" * 18)
    print(f"  ADR-036 night budget              = {NIGHT_BUDGET_W*1e6:8.0f} uW")
    for name, p in HOLD_CLASSES_W.items():
        if p == 0.0:
            print(f"  {name:32s} = {p*1e3:8.0f} mW   (no penalty)")
        else:
            print(f"  {name:32s} = {p*1e3:8.0f} mW   = {p/NIGHT_BUDGET_W:6.0f}x the night budget")
    print("  -> wing-jettison.md s3.5 already rejected nichrome partly because its")
    print("     LEAKAGE alone was 22 % of 100 uW. Solenoid hold is 3-4 ORDERS worse.")

    print("\n-- 4. PULSE ENERGY IS NOT THE PROBLEM " + "-" * 38)
    print(f"  nichrome cut (reference)          = {NICHROME_CUT_J:8.2f} J")
    for ms, p in PULSES:
        j = p * ms / 1000.0
        print(f"  solenoid pulse {ms:4d} ms @ {p:4.2f} W     = {j:8.3f} J"
              f"   ({j/NICHROME_CUT_J*100:5.1f} % of nichrome)")
    print("  -> 17-100x CHEAPER per shot. The problem is the HOLD, not the shot.")

    print("\n-- 5. NYLON vs COPPER (why cutting the conductor is a different job) " + "-" * 10)
    print(f"  nylon melt {NYLON_MELT_C:.0f} C, k ~ {NYLON_K:.2f} W/(m*K)")
    print(f"  copper melt {COPPER_MELT_C:.0f} C, k ~ {COPPER_K:.0f} W/(m*K)")
    print(f"  melt-point ratio                  = {COPPER_MELT_C/NYLON_MELT_C:8.1f}x")
    print(f"  conductivity ratio                = {COPPER_K/NYLON_K:8.0f}x")
    print("  -> nichrome sized for nylon conducts INTO the copper instead of")
    print("     severing it. TODO(unverified): no in-repo nichrome-vs-copper test.")

    print("\n-- 6. THE DECISIVE CONSTRAINT: ARRAY TOPOLOGY (ADR-046 s2.3) " + "-" * 14)
    print("  topology: wing1 -- wing2 -- wing3 -- wing4  (ONE series string)")
    print("  per-wing bypass diodes: DNP")
    print("  opening ONE wing's contact -> string OPEN -> array = 0 W")
    print(f"  lost power                        ={'100.0':>8} % (all four, not one)")
    print("  -> this is wing-jettison.md failure mode #1, severity 5, mission-ending.")
    print("     Electrical severance is not a sub-problem of a good idea; it IS")
    print("     the failure that makes the idea bad.")

    print("\n-- 7. MASS BALANCE " + "-" * 60)
    rows = [
        ("nichrome + nylon (jettison study)", 2.0, 3.2),
        ("magnetic/solenoid (this study)", 4.6, 3.2),
        ("do nothing (recommended)", 0.0, 0.0),
    ]
    print(f"  {'design':36s} {'carried':>8s} {'shed':>7s} {'net':>8s}")
    for name, carried, shed in rows:
        print(f"  {name:36s} {carried:7.1f}g {shed:6.1f}g {carried-shed:+7.1f}g")
    print("  -> magnetic family is 3.2-6.0 g carried; compare jettison study's 2.0 g")
    print("     for a design it ALREADY rejected. Mass-negative.")

    print("\n-- 8. RECOMMENDATION " + "-" * 57)
    print("  Option 1 (do nothing). If a release is mandated: keeper + slip-fit")
    print("  (Option 4) -- never cut the copper. Highest-leverage single change if")
    print("  a release is ever wanted: FIT the per-wing bypass diodes (currently DNP).")
    print("\n" + "=" * 78)

    # sanity: the force arithmetic must be self-consistent
    assert 0.30 < w * SHOCK_G * DESIGN_MARGIN < 0.55, "holding-force sanity"
    assert factor > 1.0, "NdFeB flux must increase in the cold"


if __name__ == "__main__":
    main()
