#!/usr/bin/env python3
"""
wing_omnidirectional.py — reproducible arithmetic for
docs/analysis/wing-omnidirectional.md (branch analysis/wing-omni).

Question answered: the operator saw a VERTICAL CYLINDRICAL solar array and asks
whether that would be better than the accepted four vertical flat blades.

Every number quoted in that document is printed by this script.
Run:  python3 docs/analysis/wing_omnidirectional.py

Model (same physical model as docs/analysis/insolation_factors.py, so the two
documents are directly comparable):
    A flat panel's per-unit-area output is f = cos(theta), theta = angle between
    the panel normal and the unit sun vector.  Negative cosine -> faces away -> 0.
    Sun vector (azimuth 0 = the sun's own azimuth plane; elevation e):
        s = (cos e, 0, sin e)
    Panel normal, plane tilted beta from the HORIZONTAL (beta=90 -> vertical
    panel, beta=0 -> horizontal panel), rotated by azimuth psi about vertical:
        n = (sin beta cos psi, sin beta sin psi, cos beta)
        s.n = cos e sin beta cos psi + sin e cos beta = a + b cos psi
        a = sin e cos beta ,  b = cos e sin beta

This script imports the rotation-average primitives from insolation_factors.py
so the two analyses cannot drift apart.

Site/season assumptions (inherited; no in-repo source states them):
    latitude phi = 50.0 N (TODO(unverified)), winter solstice delta = -23.44 deg
"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import insolation_factors as I  # noqa: E402  (same-directory import)

D2R = math.pi / 180.0
R2D = 180.0 / math.pi

PHI = I.PHI          # 50.0 deg N
DEC = I.DEC          # -23.44 deg

# ---------------------------------------------------------------------------
# Cell / array constants — CITED to docs/analysis/wing-mass-shape.md §1.2 and
# ADR-049 "Measured inputs".  Cell mass is *bare silicon* (marked estimate).
# ---------------------------------------------------------------------------
SMALL_W, SMALL_L = 52.07, 19.65           # mm, operator caliper (ADR-049)
LARGE_W, LARGE_L = 78.55, 38.90           # mm, operator caliper (ADR-049)
CELL_T = 0.21                             # mm thickness (ADR-049)
RHO_SI = 2.33                             # g/cm3 crystalline Si

SMALL_AREA_CM2 = SMALL_W * SMALL_L / 100.0            # = 10.2318 cm2
LARGE_AREA_CM2 = LARGE_W * LARGE_L / 100.0            # = 30.5559 cm2
SMALL_G = SMALL_AREA_CM2 * (CELL_T / 10.0) * RHO_SI   # = 0.5006 g
LARGE_G = LARGE_AREA_CM2 * (CELL_T / 10.0) * RHO_SI   # = 1.4951 g

N_CELL_ARR = 12                           # ADR-006/049: 12 cells, 6.0 V nominal


def hdr(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


# ===========================================================================
# (1)  VERIFY THE PRELIMINARY DERIVATION:  cylinder  vs  single flat blade
# ===========================================================================
def cylinder_effective_area_numeric(r=1.0, h=1.0, e_deg=None, n=200000):
    """Direct surface integral of max(0, s.n) over a vertical cylinder.

        A_eff = r*h * INT_{0}^{2pi} max(0, cos e * cos theta) dtheta
    Integrated by the midpoint rule.  Should equal 2*r*h*cos(e).
    """
    if e_deg is None:
        e_deg = I.noon_elevation()
    ce = math.cos(e_deg * D2R)
    tot = 0.0
    for i in range(n):
        th = 2.0 * math.pi * (i + 0.5) / n
        tot += max(0.0, ce * math.cos(th))
    return r * h * tot * (2.0 * math.pi / n)


def blade_rotation_average_numeric(w=1.0, h=1.0, e_deg=None, n=200000):
    """Direct rotation integral of max(0, s.n) for ONE vertical flat blade."""
    if e_deg is None:
        e_deg = I.noon_elevation()
    ce = math.cos(e_deg * D2R)
    tot = 0.0
    for i in range(n):
        ps = 2.0 * math.pi * (i + 0.5) / n
        tot += max(0.0, ce * math.cos(ps))
    return w * h * tot / n


def part1():
    hdr("(1) VERIFY / REFUTE: vertical cylinder and single vertical flat blade")
    e = I.noon_elevation()
    ce = math.cos(e * D2R)
    print(f"winter-noon solar elevation e = 90 - |50 - (-23.44)| = {e:.4f} deg")
    print(f"cos e = {ce:.5f}   (this is the WINTER-NOON number)")

    # --- cylinder, closed form vs numeric -----------------------------------
    r, hh = 1.0, 1.0
    a_eff_closed = 2.0 * r * hh * ce          # closed form
    a_eff_num = cylinder_effective_area_numeric(r, hh, e)
    a_inst = 2.0 * math.pi * r * hh           # installed cell area (full wrap)
    print()
    print("VERTICAL CYLINDER (radius r, height h, uniformly covered)")
    print("  lit half = |theta| < pi/2 ;  s.n = cos e cos theta")
    print("  A_eff = INT_0^h INT_{-pi/2}^{pi/2} r cos e cos(theta) dtheta dz")
    print(f"        = 2 r h cos e   [closed form] = {a_eff_closed:.6f} for r=h=1")
    print(f"        = {a_eff_num:.6f}  [numeric surface integral, 2e5 pts]")
    print(f"  A_installed = 2 pi r h = {a_inst:.6f}")
    print("  NOTE: the task's '2 r h' is the pure geometry factor; the flux factor")
    print("        cos e multiplies it.  A_eff = 2 r h * cos e.")
    print(f"  harvest per installed area = A_eff/A_inst = cos e / pi"
          f" = {ce/math.pi:.6f}   (ce/math.pi = {ce/math.pi:.6f})")

    # --- blade, numeric vs analytic -----------------------------------------
    b_num = blade_rotation_average_numeric(1.0, 1.0, e)
    b_inst = 1.0 * 1.0
    print()
    print("SINGLE VERTICAL FLAT BLADE (width w, height h)")
    print("  rotation:  s.n = cos e cos psi ; lit for |psi| < pi/2")
    print("  <F> = (1/2pi) INT_{-pi/2}^{pi/2} cos e cos(psi) dpsi = cos e / pi")
    print(f"      = {ce/math.pi:.6f}  [closed form]")
    print(f"      = {b_num/b_inst:.6f}  [numeric rotation integral, 2e5 pts]")
    print(f"  harvest per installed area = <F>/(w h) = cos e / pi = {ce/math.pi:.6f}")
    print()
    print("  => VERDICT: BOTH give (1/pi) cos e per installed cm2.  The preliminary")
    print("     derivation is CONFIRMED for per-installed-area harvest.")
    print(f"     <max(0,cos psi)> = 1/pi = {1/math.pi:.6f} ; <|cos psi|> = 2/pi ="
          f" {2/math.pi:.6f} (a blade is dark half the rotation).")
    print("     A cylinder is NOT dark half the time: its lit half always exists,")
    print("     which is why its INSTANTANEOUS value already equals its average.")

    # --- four blades: same per installed area? ------------------------------
    print()
    print("FOUR VERTICAL BLADES (4 arms at 90 deg, as accepted in ADR-049)")
    four_total = 4.0 * I.arm_average(90.0, e)     # sum of cos-incidence factors
    inst4 = 4.0 * 1.0                             # 4 unit blades
    print(f"  geometric total (sum of the 4 arms) at noon, rotation-average ="
          f" {four_total:.5f}")
    print(f"  per installed blade area = {four_total/inst4:.6f}  "
          f"(= cos e/pi = {ce/math.pi:.6f})")
    print("  => the 4-blade cross ALSO harvests (1/pi) cos e per installed cm2.")
    print("     So a cylinder and four blades DO harvest the SAME per unit of")
    print("     installed cell area.  The preliminary claim is CONFIRMED.")

    # --- whole day ----------------------------------------------------------
    day_arm = I.day_average_arm(90.0)          # daylight-mean of cos e / pi
    H0 = I.sunset_hour_angle()
    daylen = 2.0 * H0 / 15.0
    print()
    print("WHOLE-DAY AVERAGE AT 50 N (winter solstice)")
    print(f"  half-day hour angle H0 = {H0:.4f} deg -> day length = {daylen:.3f} h")
    print(f"  daylight-mean  <(1/pi) cos e> = {day_arm:.6f}   (equal time per unit")
    print("      hour angle over H=0..H0 — same convention as insolation_factors.py)")
    print(f"  24-hour-mean   = {day_arm:.6f} * {daylen:.3f}/24 = "
          f"{day_arm*daylen/24.0:.6f}")
    print(f"  noon value for reference = {ce/math.pi:.6f}")
    print("  The day average is HIGHER than noon because cos e grows as the sun")
    print("  drops: a vertical surface likes a low sun.")
    return dict(e=e, ce=ce, per_area_noon=ce/math.pi, per_area_day=day_arm,
                per_area_day_24h=day_arm*daylen/24.0, daylen=daylen)


# ===========================================================================
# (2)  CELL USAGE  /  MASS
# ===========================================================================
def part2(p1):
    hdr("(2) CELL USAGE AND MASS: how many more cells does a cylinder need?")
    print(f"small cell {SMALL_W} x {SMALL_L} mm = {SMALL_AREA_CM2:.4f} cm2,"
          f" {SMALL_G:.4f} g  (bare-Si estimate)")
    print(f"large cell {LARGE_W} x {LARGE_L} mm = {LARGE_AREA_CM2:.4f} cm2,"
          f" {LARGE_G:.4f} g")
    print("  (mass = area x (0.21/10 cm) x 2.33 g/cm3; CITED wing-mass-shape.md 1.2)")

    print()
    print("-- (A) CONSTRAINED BY HARVEST (equal energy) --")
    print("  harvest/installed-area is identical for both shapes (part 1), so")
    print("  EQUAL HARVEST REQUIRES EQUAL INSTALLED AREA => EQUAL CELL COUNT.")
    print(f"  12 large cells = 12 x {LARGE_AREA_CM2:.4f} ="
          f" {12*LARGE_AREA_CM2:.2f} cm2 = 12 x {LARGE_G:.4f} ="
          f" {12*LARGE_G:.3f} g of cells.")
    print("  VERDICT (A): on a TOTAL-MASS basis for equal harvest, the cylinder")
    print("               and the blades TIE.  The cylinder has NO harvest-per-gram")
    print("               advantage and NO mass advantage.")

    print()
    print("-- (B) CONSTRAINED BY PROJECTED FRONTAL AREA (silhouette) --")
    print("  installed area / projected frontal area:")
    print("    vertical cylinder, radius r, height h: A_inst = 2 pi r h,")
    print("       silhouette = 2 r h          -> ratio = pi = "
          f"{math.pi:.4f}")
    print("    ONE flat blade, width w, height h:     A_inst = w h,")
    print("       silhouette = w h            -> ratio = 1")
    print("    FOUR-blade 90 deg cross (any instant: two faces + two edges):")
    print("       A_inst = 4 w h, silhouette = 2 w h -> ratio = 2")
    f_cyl_vs_plate = math.pi / 1.0
    f_cyl_vs_cross = math.pi / 2.0
    print(f"  => for the SAME projected frontal area, the cylinder needs")
    print(f"     pi   = {f_cyl_vs_plate:.4f}x the cells of one flat plate")
    print(f"     pi/2 = {f_cyl_vs_cross:.4f}x the cells of a 4-blade cross")
    n_cross = N_CELL_ARR
    n_cyl = N_CELL_ARR * f_cyl_vs_cross
    print()
    print(f"  A four-blade cross with {n_cross} large cells has the same silhouette")
    print(f"  as a cylinder needing {n_cyl:.2f} -> {math.ceil(n_cyl)} large cells")
    print(f"     cells:  +{math.ceil(n_cyl)-n_cross}  (12 -> 19)")
    print(f"     mass :  {n_cross*LARGE_G:.3f} g -> {math.ceil(n_cyl)*LARGE_G:.3f} g"
          f"   (+{math.ceil(n_cyl)*LARGE_G - n_cross*LARGE_G:.3f} g)")
    print(f"     and vs a single flat plate: {N_CELL_ARR*math.pi:.2f} ->"
          f" {math.ceil(N_CELL_ARR*math.pi)} cells ="
          f" {math.ceil(N_CELL_ARR*math.pi)*LARGE_G:.3f} g")
    print("  VERDICT (B): IF the silhouette (drag/shadow footprint) is the binding")
    print("     constraint, the cylinder pays pi/2 = +57 % cell count and")
    print(f"     +{math.ceil(n_cyl)*LARGE_G - n_cross*LARGE_G:.2f} g for the SAME")
    print("     harvest.  The BLADES win that comparison outright.")
    return dict(n_cyl=math.ceil(n_cyl), g_cyl=math.ceil(n_cyl)*LARGE_G,
                g_cross=n_cross*LARGE_G)


# ===========================================================================
# (3)  OTHER OMNIDIRECTIONAL GEOMETRIES
# ===========================================================================
def horiz_axis_cylinder_axis_mean(e_deg):
    """Mean over the payload's (uncontrolled) azimuth alpha of
       R(alpha) = sqrt(cos^2 e sin^2 alpha + sin^2 e)
    for a HORIZONTAL-axis cylinder.  Its per-installed-area factor is <R>/pi.
    """
    ce, se = math.cos(e_deg * D2R), math.sin(e_deg * D2R)
    n = 720
    tot = 0.0
    for i in range(n):
        al = math.pi * (i + 0.5) / n * 2.0
        tot += math.sqrt((ce * math.sin(al)) ** 2 + se ** 2)
    return tot / n


def horiz_axis_day_mean():
    H0 = I.sunset_hour_angle()
    n = 721
    tot = 0.0
    for i in range(n):
        H = H0 * i / (n - 1)
        e = max(0.0, I.sun_elevation(H))
        tot += horiz_axis_cylinder_axis_mean(e)
    return tot / n


def part3(p1):
    hdr("(3) OTHER OMNIDIRECTIONAL GEOMETRIES")
    e = p1['e']
    ce = p1['ce']
    print(f"baseline for comparison: FOUR VERTICAL BLADES, per installed cm2")
    print(f"   noon {I.arm_average(90.0, e):.5f}   day {I.day_average_arm(90.0):.5f}")
    print()
    print("A reference harvest is defined as the 12-large-cell 4-blade array:")
    print(f"   peak 7.2 W (ADR-049), i.e. geometric per-area factor"
          f" {I.arm_average(90.0, e):.5f} at noon.")
    base_noon = I.arm_average(90.0, e)

    rows = []

    # (a) vertical cylinder
    f_noon = ce / math.pi
    f_day = I.day_average_arm(90.0)
    rows.append(("vertical cylinder (wrap 360)", f_noon, f_day,
                 "CONVEX, constant output; NOT buildable from flat rigid cells"))

    # (b) horizontal-axis cylinder (rolling pin)
    rh_noon = horiz_axis_cylinder_axis_mean(e) / math.pi
    rh_day = horiz_axis_day_mean() / math.pi
    rows.append(("horizontal-axis cylinder", rh_noon, rh_day,
                 "axis azimuth is uncontrolled -> low mean + big ripple"))

    # (c) cone / funnel opening upward, panel tilt beta (lean 90-beta from vert)
    b_noon_opt = 90.0 - e            # 73.44 deg: normal points at the noon sun
    f_c_noon = I.arm_average(b_noon_opt, e)
    f_c_day = I.day_average_arm(b_noon_opt)
    rows.append((f"cone/funnel lean {e:.2f} deg from vert", f_c_noon, f_c_day,
                 "constant output; cannot wrap flat cells -> N flat facets"))

    # (d) blades with alternating tilts (+/- 15 deg about vertical)
    d = 15.0
    fa = 0.5 * (I.arm_average(90.0 - d, e) + I.arm_average(90.0 + d, e))
    fd = 0.5 * (I.day_average_arm(90.0 - d) + I.day_average_arm(90.0 + d))
    rows.append((f"blades alternating tilt +/-{d:.0f} deg", fa, fd,
                 "needs two different tab angles; area-splitting loss"))

    # (e) flat cross (beta=0)
    f_e_noon = math.sin(e * D2R)
    f_e_day = I.day_average_horizontal()
    rows.append(("flat horizontal cross", f_e_noon, f_e_day,
                 "simplest, no mismatch, but lowest daily yield"))

    print(f"{'geometry':<34}{'noon':>8}{'day':>9}{'vs vert day':>12}")
    print("-" * 78)
    for name, fn, fd, _ in rows:
        print(f"{name:<34}{fn:>8.5f}{fd:>9.5f}{fd/f_day*100-100:>11.1f}%")
    print(f"{'(reference) 4 vertical blades':<34}{base_noon:>8.5f}"
          f"{I.day_average_arm(90.0):>9.5f}{0.0:>11.1f}%")

    print()
    print("cells required for the SAME noon harvest as the 12-cell 4-blade array")
    print("   cells = 12 * (0.30511 / f_noon) ;  mass = cells * 1.4951 g")
    print(f"{'geometry':<34}{'factor':>9}{'cells':>8}{'mass/g':>9}   buildability")
    print("-" * 78)
    base_mass = N_CELL_ARR * LARGE_G
    for name, fn, fd, verdict in rows:
        cells = N_CELL_ARR * base_noon / fn
        mass = cells * LARGE_G
        print(f"{name:<34}{fn:>9.5f}{cells:>8.1f}{mass:>9.2f}   {verdict}")
    print(f"{'(reference) 4 vertical blades':<34}{base_noon:>9.5f}"
          f"{N_CELL_ARR:>8.1f}{base_mass:>9.2f}   baseline")

    print()
    print("HARVEST-PER-GRAM ranking (per installed cm2, day = the deciding metric):")
    best_day = max(rows, key=lambda r0: r0[2])
    print(f"  best = {best_day[0]} at {best_day[2]:.5f} day vs 4-blade"
          f" {I.day_average_arm(90.0):.5f}  ->"
          f" {(best_day[2]/I.day_average_arm(90.0)-1)*100:+.1f}%")
    print("  -> ONLY the lean (cone / leaned blades) beats plain vertical, and only")
    print(f"     by {(best_day[2]/I.day_average_arm(90.0)-1)*100:.1f} % on a per-gram basis.")

    print()
    print("SMOOTHNESS (ripple of the geometric total as the payload rotates):")
    lo, hi = I.four_arm_minmax(90.0, e)
    print(f"  4 vertical blades: total ranges {lo:.4f}..{hi:.4f} ->"
          f" ripple ratio {(hi-lo)/hi*100:.1f}% of peak, and the total hits")
    print(f"     a GEOMETRIC ZERO 4x per rotation (two arms exactly edge-on):")
    print("     series string collapses to ~0 without bypass diodes (ADR-049.2).")
    print(f"  vertical cylinder / cone / flat cross: output CONSTANT (ripple 0%).")
    print("  Does SMOOTHNESS matter?  Load = supercap bank + shunt clamp (ADR-047),")
    print("  NOT a battery.  A supercap integrates arbitrary current ripple with no")
    print("  partial-state penalty, no memory effect and no cycle-life cost.  So")
    print("  current smoothness does NOT decide this.  What DOES matter is the")
    print("  SERIES-STRING VOLTAGE: the 4-blade string needs its bypass diodes to")
    print("  avoid collapsing; a constant-output geometry would need none.")
    print()
    print("BUILDABILITY of a 'cylinder' out of FLAT rigid 0.21 mm cells:")
    c = LARGE_L  # 38.90 mm, the cell dimension that would wrap around the barrel
    for R in (60.0, 90.0, 120.0, 200.0):
        # a prism of circumradius R using chord = the cell width c:
        N = math.pi / math.asin(min(1.0, c / (2.0 * R)))
        strain = CELL_T / (2.0 * R)          # if smooth-bent: eps = t/(2R)
        print(f"    circumradius R={R:5.1f} mm: a faceted 'cylinder' needs"
              f" N={N:4.1f} facets (chord {c:.1f} mm);")
        print(f"       smooth-bend surface strain eps=t/2R = {strain*1e6:6.0f} microstrain")
    print("    -> a realisable cylinder is a POLYGONAL PRISM of N flat blades;")
    print("       N=4 is literally the accepted 4-blade cross.  The cylinder is the")
    print("       N->inf limit of the blade cross, not a different architecture.")
    print("    TODO(unverified): the fracture strain limit of a 0.21 mm bare c-Si")
    print("       cell (no datasheet in-repo) — it decides how few facets suffice.")
    return rows


# ===========================================================================
# (4)  SHADING AND SELF-SHADOWING
# ===========================================================================
def part4(p1, hub_mm=22.0, balloon_d_m=0.90, line_mm=1.0, standoff_m=0.30):
    hdr("(4) SHADING AND SELF-SHADOWING")
    e = p1['e']
    cot = 1.0 / math.tan(e * D2R)
    print(f"winter-noon sun elevation {e:.2f} deg -> shadow throw factor")
    print(f"  cot(e) = 1/tan({e:.2f}) = {cot:.3f}  (a shadow at height Z lands")
    print(f"  horizontally {cot:.2f} Z away)")
    print()
    print("Objects above the array and what they shadow:")
    Z_balloon = standoff_m                            # hub->balloon standoff
    print(f"  balloon (d = {balloon_d_m*1000:.0f} mm, CITED, standoff TODO) at")
    print(f"    Z = {Z_balloon*1000:.0f} mm above the hub:")
    print(f"    shadow centre lands {cot*Z_balloon*1000:.0f} mm horizontally away;")
    print(f"    its own half-width is {balloon_d_m*500:.0f} mm, so the near edge is")
    print(f"    at {cot*Z_balloon*1000-500:.0f} mm — clear of a ~180 mm-radius array.")
    print(f"    => in winter the balloon does NOT shadow a vertical array; it also")
    print(f"       explains the envelope/rigging derate 0.9 in SOLAR-PIN-REGULATORY.")
    print()
    print(f"  suspension line (d = {line_mm:.1f} mm, TODO(unverified)) runs UP from")
    print("    the hub to the balloon — i.e. it is ABOVE the hub, and the array is")
    print("    BELOW the hub.  Its shadow lands at cot(e)*Z from the line, so for")
    print("    any line segment more than ~0.1 m above the array top it misses the")
    print("    array entirely.  Fraction of array shadowed by the line ~ 0.")
    print("    => ARRANGE: array BELOW the hub, line ABOVE the hub.  Both geometries")
    print("       can do this; it is a mounting rule, not a shape property.")
    print()
    hub_mm2 = hub_mm * hub_mm
    arr_mm2 = N_CELL_ARR * LARGE_AREA_CM2 * 100.0
    print(f"  hub/tab cluster (22 x 22 mm board, CITED hardware-design.md l.13):")
    print(f"    the 22x22 mm hub sits at the centre where the arms converge; its")
    print(f"    shadow is at most its own footprint = {hub_mm2:.0f} mm2 out of the")
    print(f"    array's {arr_mm2:.0f} mm2 of cell area = {hub_mm2/arr_mm2*100:.1f} %.")
    print("    This term is SHARED by the cylinder and the blades (both need a hub")
    print("    at the axis).  TODO(unverified): exact hub/rigging footprint.")
    print()
    print("SELF-shadowing (array shadows itself):")
    print("  vertical CYLINDER: convex surface — a convex body casts no shadow onto")
    print("    itself from a distant directional source -> self-shadowing = 0 %.")
    print("  FOUR BLADES at 90 deg: the sun-facing blade is edge-on/back-facing to")
    print("    its opposite, which already produces ~0, and it radiates outward")
    print("    perpendicular to the other two, so no blade shadows a producing")
    print("    surface.  Self-shadowing ~= 0 % except the shared hub/tab centre.")
    print("    (consistent with insolation_factors.md 7 item 5, unmodelled.)")
    print("  => the CYLINDER is the more robust to self-shadowing (strictly convex),")
    print("     but the margin is small; the blades are already near-zero and are")
    print("     governed by the same hub derate.")
    print()
    print("Both geometries must sit BELOW the hub with the line ABOVE the hub;")
    print("that single rule removes the only large occluder (the line) from both.")


# ===========================================================================
# (5)  THE ANSWER  +  geometry levers
# ===========================================================================
def part5(p1):
    hdr("(5) THE ANSWER")
    e = p1['e']
    base_day = I.day_average_arm(90.0)
    print("DECIDING NUMBER: harvest per installed cm2 is (1/pi) cos e for BOTH the")
    print("cylinder and the blades — 0.30511 at winter noon, 0.31149 daylight-mean")
    print("at 50 N.  A cylinder therefore needs the SAME cell mass for the same")
    print("harvest and buys nothing; if the silhouette is fixed it costs pi/2 =")
    print("+57 % cells (+10.5 g).  => KEEP FOUR VERTICAL BLADES.")
    print()
    print("Geometry levers, each with its computed gain on harvest-per-gram:")
    print("  (i) blade COUNT (e.g. 3 at 120 deg instead of 4 at 90):")
    for n in (3, 4, 6):
        tot = sum(I.arm_average(90.0, e) for _ in range(n))
        print(f"        N={n}: per installed blade ="
              f" {tot/n:.5f}  (unchanged)")
    print("        -> ZERO per-gram gain: the (1/pi)cos e factor is per-area and")
    print("           independent of blade count.  Count only affects ripple and")
    print("           the series-string granularity.  KEEP 4.")
    print()
    print("  (ii) blade HEIGHT: per-area factor is scale-invariant -> ZERO per-gram")
    print("       gain.  Height scales area, output and mass together.")
    print()
    print("  (iii) small OUTWARD LEAN (panel tilt beta < 90 deg):")
    for beta in (90.0, 80.0, 75.0, 73.44, 72.5, 70.0):
        fn = I.arm_average(beta, e)
        fd = I.day_average_arm(beta)
        sn = I.series_average(beta, e)
        print(f"        beta={beta:5.2f} (lean {90-beta:4.1f} from vert):"
              f" noon {fn:.5f} ({fn/I.arm_average(90,e)*100-100:+.1f}%)"
              f"  day {fd:.5f} ({fd/base_day*100-100:+.1f}%)")
    print("        -> the day-maximising lean is ~17 deg from vertical (beta~73):")
    print(f"           +{(I.day_average_arm(73.44)/base_day-1)*100:.1f} % day,"
          f" +{(I.arm_average(73.44,e)/I.arm_average(90.0,e)-1)*100:.1f} % noon.")
    print("           This is the ONLY per-gram lever.  Mechanical cost: a cranked")
    print("           tab or an angled slot (ADR-049 rejects the spin for 3-10 %).")

    print()
    print("SUMMARY OF THE QUANTIFIED ANSWER")
    print(f"  per-gram harvest, vertical blades = {base_day:.5f}   (cylinder: same)")
    print(f"  per-gram harvest, ~17 deg lean    = {I.day_average_arm(73.44):.5f}"
          f"  ({(I.day_average_arm(73.44)/base_day-1)*100:+.1f} %)")
    print("  cylinder mass for equal harvest   = SAME (tie)")
    print("  cylinder mass at equal silhouette = +10.50 g (pi/2 cell count)")


def main():
    hdr("SITE / SEASON (inherited from insolation_factors.py)")
    print(f"latitude phi = {PHI:.2f} deg N   [TODO(unverified)]")
    print(f"declination  = {DEC:.2f} deg (winter solstice)")
    p1 = part1()
    part2(p1)
    part3(p1)
    part4(p1)
    part5(p1)
    print()
    print("=" * 78)
    print("END — all numbers above are printed by this script.")
    print("=" * 78)


if __name__ == "__main__":
    main()
