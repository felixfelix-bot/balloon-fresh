#!/usr/bin/env python3
"""vertical_hub_load_cases.py — arithmetic and figure behind
docs/analysis/vertical-hub-load-cases.md (branch pr/vertical-hub-loads).

Question: does hanging the hub array carrier VERTICALLY remove the ADR-063 D4
`pitch <= S_crack` constraint, or merely relocate it?

Method: the ADR-063 D4 demand formula sigma = 3 rho g S^2 / (4 t)
(docs/analysis/hub_array_overhang_model.py, lines 103-107) is evaluated for
transverse gravity components g_perp = g * k(theta), where theta is the
rotation of the effective gravity vector away from its static direction
(pendulum swing + any lateral acceleration). For a HORIZONTAL panel the
static direction is transverse (k=1); for a VERTICAL panel it is in-plane
(k=0), so a vertical panel sees k = sin(theta) and a horizontal one
k = cos(theta).

NO ALLOWABLE IS ASSUMED: no flexural strength for the 0.21 mm cell exists
in the repo (ADR-063 D4). All stresses are DEMAND. Pendulum angles and
g-loads marked TODO(unverified) are illustrative, not flight data.

Constants are cited to in-repo sources exactly as in
hub_array_overhang_model.py; the Si CTE (2.6e-6/K) and the 130-170 GPa
modulus range are standard literature values (MatWeb / Ioffe NSM),
TODO(unverified) — no URL fetched in the writing session.

Run:  python3 docs/analysis/vertical_hub_load_cases.py
Writes: docs/analysis/vertical-hub-load-cases.png (the figure the doc shows)
"""
from __future__ import annotations

import math
import os

# ---------------------------------------------------------------- constants
G = 9.80665            # m/s^2  (physical constant; hub_array_overhang_model.py L19)
RHO_SI = 2330.0        # kg/m^3 crystalline Si (physical constant; same, L20)
E_SI_LOW, E_SI_HIGH = 130e9, 170e9   # Pa, literature range, TODO(unverified)
CTE_SI = 2.6e-6        # 1/K, literature value, TODO(unverified)
NU_SI = 0.28           # Poisson ratio, literature value, TODO(unverified)
T_CELL = 0.21e-3       # m      operator caliper (same, L22)
L_CELL = 78.55e-3      # m      LARGE cell long side (ADR-049 measured inputs)
DT_COLD = -80.0        # K      +25 C assembly -> -55 C cold soak (assumed ref, TODO)

# ------------------------------------------------------------ demand formula
def ss_stress(span_m: float, g_perp_over_g: float = 1.0,
              t: float = T_CELL, rho: float = RHO_SI, g: float = G) -> float:
    """Max surface bending stress, simply-supported under own weight,
    scaled by the transverse gravity fraction. sigma = 3 rho g L^2/(4 t)."""
    return 3.0 * rho * g * span_m ** 2 / (4.0 * t) * g_perp_over_g


def main() -> None:
    print("=" * 74)
    print("VERTICAL vs HORIZONTAL hub array — unsupported-span bending DEMAND")
    print("  cell 78.55 x 38.90 x 0.21 mm ; formula per ADR-063 D4 /")
    print("  hub_array_overhang_model.py ; NO allowable assumed anywhere")
    print("=" * 74)

    # sanity: reproduce the ADR-063 calibration numbers
    print("\n[cross-check vs ADR-063 D4]")
    print(f"  sigma@1g, 78.55 mm = {ss_stress(L_CELL)/1e6:.3f} MPa   (ADR-063: 0.504)")
    print(f"  sigma@2g, 78.55 mm = {2*ss_stress(L_CELL)/1e6:.3f} MPa   (ADR-063: 1.007)")

    print("\n[case 1 static 1 g]")
    print(f"  horizontal: transverse 1.000 g -> {ss_stress(L_CELL,1.0)/1e6:.3f} MPa")
    print(f"  vertical  : transverse 0.000 g -> {ss_stress(L_CELL,0.0)/1e6:.3f} MPa"
          "  (gravity in-plane; beam bending formula gives zero transverse demand)")

    print("\n[case 2 pendulum swing — theta = rotation of effective gravity]")
    print("  (illustrative angles; theta_max in flight is TODO(unverified))")
    print("    theta   horiz k=cos   vert k=sin   horiz MPa   vert MPa")
    for deg in (0.0, 10.0, 30.0, 45.0, 60.0, 90.0):
        th = math.radians(deg)
        kh, kv = math.cos(th), math.sin(th)
        print(f"    {deg:5.1f}   {kh:9.3f}    {kv:8.3f}"
              f"   {ss_stress(L_CELL,kh)/1e6:8.3f}  {ss_stress(L_CELL,kv)/1e6:8.3f}")
    print("  -> at theta=90 deg the VERTICAL panel sees the FULL 1 g transverse")
    print("     demand (0.504 MPa); orientation alone cannot remove the constraint.")
    print("  pitch scaling IF a coupon gives S_crack and theta_max is measured:")
    for deg in (10.0, 30.0, 45.0, 60.0):
        print(f"    theta_max={deg:4.1f} deg -> S_vert_max = S_crack /"
              f" sqrt(sin(theta)) = {1/math.sqrt(math.sin(math.radians(deg))):.3f} x S_crack")

    print("\n[case 3 ascent/descent acceleration]")
    print("  N_g flight g-load: TODO(unverified) — no measured/specified value in")
    print("  repo (wing-jettison.md 2.1 gives 5 m/s ascent SPEED, not acceleration;")
    print("  its 10 g burst shock is explicitly an assumption). Demand if a")
    print("  transverse component n g acts:")
    for n in (1.0, 2.0, 5.0, 10.0):
        print(f"    n={n:4.1f} g transverse -> {n*ss_stress(L_CELL,1.0)/1e6:7.3f} MPa"
              "  (same for either mounting if the vector is transverse)")

    print("\n[case 4 thermal, -55 C cold soak]")
    eps = CTE_SI * DT_COLD
    print(f"  free strain eps = alpha*dT = {CTE_SI:.1e} * {DT_COLD:.0f} = {eps*1e6:.0f} microstrain")
    print("  fully-restrained uniaxial stress E*alpha*|dT| (orientation-independent):")
    print(f"    E=130 GPa -> {abs(E_SI_LOW*eps)/1e6:.1f} MPa ; E=170 GPa -> {abs(E_SI_HIGH*eps)/1e6:.1f} MPa")
    print("  -> 1-2 orders above any self-weight bending number; depends on restraint,")
    print("     NOT on panel orientation. Real value set by end joints/frame compliance")
    print("     (unmeasured). Cold soak also lowers Si fracture toughness (literature,")
    print("     TODO(unverified)).")

    print("\n[case 5 vibration/buffet]")
    print("  OMITTED — no citable spectrum in repo (qualitative jetstream notes only).")

    print("\n[VERDICT]")
    print("  Vertical mounting zeroes ONLY the static transverse term. Pendulum,")
    print("  acceleration and thermal cases survive the rotation and are NOT")
    print("  covered by the horizontal 1 g coupon. S_crack must still be measured;")
    print("  pitch <= S_crack stands unless a bounded theta_max + accel envelope is")
    print("  measured first.")

    render_figure()


def render_figure() -> None:
    """Stress vs span for each case, horizontal vs vertical."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n[figure] matplotlib unavailable — skipped")
        return

    spans_mm = [s for s in range(0, 101, 1)]
    S = [s * 1e-3 for s in spans_mm]

    def series(k):
        return [ss_stress(s, k) / 1e6 for s in S]

    fig, ax = plt.subplots(figsize=(9, 6))
    ax.plot(spans_mm, series(1.0), "r-", lw=2,
            label="HORIZONTAL static 1 g (k=1) — the D4 coupon case")
    ax.plot(spans_mm, series(0.0), "g-", lw=2,
            label="VERTICAL static (k=0) — self-weight bending zeroed")
    ax.plot(spans_mm, series(math.sin(math.radians(30))), "b--", lw=1.5,
            label="VERTICAL pendulum 30° (k=sin30=0.50) — illustrative")
    ax.plot(spans_mm, series(math.sin(math.radians(60))), "c--", lw=1.5,
            label="VERTICAL pendulum 60° (k=sin60=0.866, shown rounded 0.87) — illustrative")
    ax.plot(spans_mm, series(1.0), "k:", lw=1.2,
            label="VERTICAL pendulum 90° / horizontal 1 g (k=1.00) — the killer")
    ax.plot(spans_mm, series(2.0), "m-.", lw=1.2,
            label="either mounting, 2 g transverse — ILLUSTRATIVE, not a validated envelope")

    # thermal band (orientation-independent), shown as horizontal lines
    for E, lbl in ((E_SI_LOW, "130"), (E_SI_HIGH, "170")):
        sig = abs(E * CTE_SI * DT_COLD) / 1e6
        ax.axhline(sig, color="0.4", lw=0.8, ls=(0, (1, 4)),
                   label=f"uniaxial fully restrained thermal, E={lbl} GPa: {sig:.1f} MPa")
        ax.text(2, sig + 0.5, f"fully-restrained thermal -55 C, E={lbl} GPa: {sig:.1f} MPa",
                fontsize=7, color="0.3")
    # equal-biaxial plane-stress thermal estimate E*alpha*|dT|/(1-nu)
    # (consultant challenge 2026-10-09 item 3): ~37.6 MPa for E=130 GPa, nu=0.28
    sig_bi = abs(E_SI_LOW * CTE_SI * DT_COLD) / (1.0 - NU_SI) / 1e6
    ax.axhline(sig_bi, color="0.55", lw=0.8, ls=(0, (4, 2)),
               label=f"equal-biaxial plane-stress thermal, E=130 GPa, nu={NU_SI}: {sig_bi:.1f} MPa")
    ax.text(2, sig_bi + 0.5,
            f"equal-biaxial E*a*|dT|/(1-nu), nu={NU_SI}, E=130 GPa: {sig_bi:.1f} MPa",
            fontsize=7, color="0.3")

    ax.axvline(L_CELL * 1e3, color="0.5", lw=0.8)
    ax.text(L_CELL * 1e3 + 1, 0.5, "cell length\n78.55 mm", fontsize=7, color="0.4")
    ax.axhline(0.504, color="r", lw=0.6, alpha=0.5)
    ax.text(80, 0.15, "0.504 MPa = D4 demand @1 g, 78.55 mm", fontsize=7, color="r")

    ax.set_xlabel("unsupported span S (mm)")
    ax.set_ylabel("transverse bending stress demand (MPa)")
    ax.set_title("Vertical vs horizontal hub array: bending DEMAND vs span\n"
                 "(no allowable assumed; S_crack is the unmeasured boundary)")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 40)
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(alpha=0.3)
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "vertical-hub-load-cases.png")
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    print(f"\n[figure] wrote {out}")


if __name__ == "__main__":
    main()
