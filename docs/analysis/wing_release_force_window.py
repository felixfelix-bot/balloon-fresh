#!/usr/bin/env python3
"""Force window for the wing joint, driven by a MEASURED wing mass.

Companion to docs/MEASUREMENT-REQUEST-WING-RELEASE.md.

The wing mass is an ESTIMATE in the repo (3.2 g, docs/analysis/wing-jettison.md
s7). Every force in the release design is proportional to it, so this script
takes the measured value and prints the window the joint must live in:

    lower bound = ascent vibration + 10 g burst shock, x1.5 margin
    upper bound = what the keeper actuator can open

Usage:
    python3 docs/analysis/wing_release_force_window.py                 # estimate
    python3 docs/analysis/wing_release_force_window.py 4.15            # measured
    python3 docs/analysis/wing_release_force_window.py 4.15 4.22       # two wings
"""

from __future__ import annotations

import sys

G = 9.80665
SHOCK_G = 10.0        # docs/analysis/wing-jettison.md s2.1 (assumed)
DESIGN_MARGIN = 1.5   # study convention
WING_MASS_ESTIMATE_G = 3.2   # jettison study s7 -- AN ESTIMATE

I_HARVEST_A = 0.4     # ADR-046 s2.3, per-wing daytime current
V_STACK = 6.0         # ADR-046 s2.3
P_HARVEST_W = 2.4     # 6.0 V x 0.4 A


def window(mass_g: float) -> tuple[float, float, float]:
    """Return (1g load, 10g shock, design lower bound) in millinewtons."""
    m = mass_g / 1000.0
    base = m * G * 1000.0
    shock = base * SHOCK_G
    return base, shock, shock * DESIGN_MARGIN


def main(argv: list[str]) -> int:
    masses: list[float] = []
    for a in argv[1:]:
        try:
            masses.append(float(a))
        except ValueError:
            print(f"not a number: {a!r}", file=sys.stderr)
            return 2
    if not masses:
        masses = [WING_MASS_ESTIMATE_G]
        print(f"no mass given -> using the repo ESTIMATE ({WING_MASS_ESTIMATE_G} g).")
        print("Replace it with a real weighing: pass the measured grams as an argument.\n")
    else:
        print(f"using MEASURED wing mass: {', '.join(f'{m:g} g' for m in masses)}\n")

    # spread across the supplied wings, if more than one
    if len(masses) > 1:
        lo, hi = min(masses), max(masses)
        spread = (hi - lo) / lo * 100.0
        print(f"weighed {len(masses)} wings: spread {hi - lo:.3f} g "
              f"({spread:.1f} % of the lighter one)")
        print("-> a spread above ~5 % means the build, not the design, "
              "is the dominant uncertainty\n")

    print("=" * 72)
    print(f"{'wing mass':>10} {'1 g load':>11} {'10 g shock':>12} "
          f"{'x1.5 lower bound':>18}")
    print(f"{'(g)':>10} {'(mN)':>11} {'(mN)':>12} {'(mN)':>18}")
    print("-" * 72)

    for m_g in masses:
        base, shock, design = window(m_g)
        print(f"{m_g:10.3f} {base:11.1f} {shock:12.1f} {design:18.1f}")

    # reference rows so the reader can see the sensitivity
    print("-" * 72)
    print("sensitivity (what the estimate costs us):")
    for m_g in (3.2, 4.0, 5.0, 6.0):
        _, _, design = window(m_g)
        tag = "  <- repo estimate" if m_g == WING_MASS_ESTIMATE_G else ""
        print(f"{m_g:10.1f} {'':11} {'':12} {design:18.1f}{tag}")

    lo_bound = window(min(masses))[2]
    hi_bound = window(max(masses))[2]
    if len(masses) > 1 and hi_bound > lo_bound:
        print(f"\nthe window MOVES by {hi_bound - lo_bound:.0f} mN "
              f"({(hi_bound / lo_bound - 1) * 100:.0f} %) across the weighed wings")

    # the actuator side
    _, shock, _ = window(max(masses))
    print("\n-- the UPPER bound (what the keeper must be able to open) " + "-" * 15)
    print(f"  the nylon loop carries the joint load: ~{shock:.0f} mN at 10 g")
    print("  nichrome+nylon channel: ~0.5 g, 2.59 J/cut (ADR-051 s2.5)")
    print("  -> if a knot-able cord cannot carry this, the concept needs a")
    print("     different keeper BEFORE any layout (measurement B).")

    print("\n-- contact-resistance budget (the electrical side) " + "-" * 20)
    print(f"  harvest {V_STACK:.1f} V x {I_HARVEST_A:.1f} A = {P_HARVEST_W:.1f} W")
    print(f"  {'R (mohm)':>9} {'loss (mW)':>10} {'% of harvest':>13} {'drop (mV)':>10}")
    for r_mohm in (20, 50, 100, 200, 500):
        r = r_mohm / 1000.0
        p = I_HARVEST_A ** 2 * r
        v = I_HARVEST_A * r
        print(f"  {r_mohm:9d} {p * 1000:10.1f} {p / P_HARVEST_W * 100:12.2f}% "
              f"{v * 1000:10.1f}")
    print("\n  target < 100 mohm (0.67 % loss, 40 mV). Above ~500 mohm it eats")
    print("  the MPPT headroom.")

    # sanity
    assert lo_bound > 0.0
    assert hi_bound >= lo_bound
    print("\n" + "=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
