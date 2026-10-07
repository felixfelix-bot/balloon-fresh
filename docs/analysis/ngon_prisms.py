#!/usr/bin/env python3
"""
ngon_prisms.py — reproducible arithmetic for
docs/analysis/wing-ngon-prisms.md (branch analysis/wing-ngon).

Companion to insolation_factors.py (the 4-arm/rotation analysis, branch
analysis/wing-insolation) and wing_mass_model.py (mass, branch
analysis/wing-mass-shape).  This script does NOT re-derive those; it extends
them to the general regular N-gon vertical prism.

Every number quoted in wing-ngon-prisms.md is printed by this script.
Run:  python3 docs/analysis/ngon_prisms.py

MODEL (stated so the reader can attack it)
------------------------------------------
* Rotation axis is VERTICAL.  Sun vector (direction TO the sun), azimuth 0:
      s = (cos h, 0, sin h)        h = solar elevation
* A regular N-sided vertical prism has N flat faces whose normals are
  horizontal and spaced 360/N in azimuth.  A face's normal at rotation angle
  psi sits at azimuth (psi - 360 k/N):
      n_k = (cos(psi - a_k), sin(psi - a_k), 0),  a_k = 360 k / N
      cos(incidence)_k = s . n_k = cos h * cos(psi - a_k)
  Negative cosine = face turned away = 0, so every average clamps at 0.
* INSTALLED AREA of one face = w * h_face (its own rectangle).  All N faces
  are identical (a REGULAR prism), so the prism's installed area = N * w * h.
* The cells are stacked IN SERIES ALONG THE FACE'S LONG DIMENSION, which is
  the VERTICAL (blade) direction, so the blade height grows with the cells
  per face c = 12/N.  Face width w is the tangential dimension.

CELLS (operator caliper; CITED in ADR-049 "Measured inputs"):
    small 52.07 x 19.65 x 0.21 mm, 10.2318 cm2, ~0.5 V, ~0.4 A, ~0.50 g
    large 78.55 x 38.90 x 0.21 mm, 30.5559 cm2, ~0.5 V, ~1.2 A, ~1.50 g
CELL AREA = L * W ; CELL MASS = AREA * t * rho_Si (2.33 g/cm3), bare silicon.
"""

import math

R2D = 180.0 / math.pi
D2R = math.pi / 180.0

# ---------------------------------------------------------------------------
# ASSUMED SITE / SEASON (same assumption as insolation_factors.py; TODO(unverified))
# ---------------------------------------------------------------------------
PHI = 50.0            # assumed launch latitude, deg N   [ADR-049 TODO(unverified)]
DEC = -23.44          # winter-solstice declination, deg
NOON_H = 90.0 - abs(PHI - DEC)     # = 16.56 deg

# ---------------------------------------------------------------------------
# CELL / ARRAY / ELECTRICAL CONSTANTS
# ---------------------------------------------------------------------------
CELLS = {
    # name: L, W, t (mm), area (cm2), V_mp, I_mp (A), mass (g)
    "small": dict(L=52.07, W=19.65, t=0.21, area=10.2318, v=0.5, i=0.400, m=0.5006),
    "large": dict(L=78.55, W=38.90, t=0.21, area=30.5559, v=0.5, i=1.200, m=1.4951),
}
N_CELLS = 12                  # 12 cells in SERIES (ADR-046 s2.3 / ADR-049)
GAP = 6.0                     # inter-cell gap along the string, ADR-046 s3.3
M_END = 3.8                   # end margin per end, reproduces ADR-046's 176 mm
M_SIDE = 2.675                # side margin per side (ADR-046 176x25 / 52.07+2*2.675)
TAB_W, TAB_L = 9.0, 8.0       # tab width, protrusion (ADR-046 s2.1/s3.2)
FR4_G_PER_CM2 = 0.1276        # 0.6 mm FR4 x 1.85 g/cm3 x 1.15  [wing_mass_model.py]
V_BANK = 5.4                  # supercap bank (ADR-049 s3)
V_RADIO_MAX = 5.5             # radio input ceiling (ADR-047 s1.1 max row 5.5 V)
P_LOAD_MAX = 5.5 * 1.118      # = 6.1495 W  (ADR-047 s1.2)


# ===========================================================================
# (1)  N-GON EQUIVALENCE  —  harvest per unit INSTALLED area is 1/pi * cos h
# ===========================================================================
def face_cos_k(N, h_deg, psi_deg, k):
    """cos(incidence) of face k (clamped at 0) of a vertical N-gon prism."""
    return max(0.0, math.cos(h_deg * D2R) *
               math.cos((psi_deg - 360.0 * k / N) * D2R))


def total_R(N, psi_deg, h_deg=0.0):
    """Sum of the clamped cos(incidence) over all N faces.  With h_deg=0 this
    is the NORMALISED total R(psi) = sum_k max(0, cos(psi - a_k)) whose mean is
    N/pi; the real geometric total harvest is cos h * R(psi)."""
    return sum(face_cos_k(N, h_deg, psi_deg, k) for k in range(N))


def face_rot_avg_numeric(N, h_deg, k=0, n=180001):
    """Numeric mean over a full rotation of ONE face's cos(incidence)."""
    return sum(face_cos_k(N, h_deg, 360.0 * i / (n - 1), k) for i in range(n)) / n


def face_rot_avg_closed(h_deg):
    """Closed form: (1/2pi) * int_0^2pi max(0, cos h cos psi) d psi
       = cos h * (1/2pi) * int_{-pi/2}^{pi/2} cos psi d psi = cos h / pi."""
    return math.cos(h_deg * D2R) / math.pi


def cylinder_rot_avg_numeric(h_deg, n=2000001):
    """Cylinder limit.  A cylinder of radius R and height H has a uniform
    azimuthal area element (R dphi) * H, so the harvest per unit installed
    area, normalised by cos h, is the one-face integral
        (1/2pi) * int_0^{2pi} max(0, cos phi) d phi  =  1/pi ,
    evaluated here by straight numeric quadrature.  This is the SAME integral
    each flat face of an N-gon averages, which is exactly why the result is
    independent of N.  (The K-facet polygonal approximation of a cylinder is
    just the finite-N case and is proved identical the same way.)"""
    tot = 0.0
    for i in range(n):
        phi = 2.0 * math.pi * i / (n - 1)
        tot += max(0.0, math.cos(phi))
    return tot / n * math.cos(h_deg * D2R)


def part1():
    print("=" * 78)
    print("(1) N-GON EQUIVALENCE  —  mean harvest per unit INSTALLED area")
    print("=" * 78)
    print(f"winter noon elevation h = 90 - |{PHI} - ({DEC})| = {NOON_H:.4f} deg")
    cf = face_rot_avg_closed(NOON_H)
    print(f"closed form, ONE face:  (1/pi) cos h = (1/pi) cos {NOON_H:.2f}"
          f" = {cf:.6f}")
    print()
    n = 72001
    print(f"Numeric integration over a full rotation (n = {n} samples).")
    print("  per-face avg  = mean over psi of  max(0, cos h cos(psi - a_k))")
    print("  sum/N         = (mean over psi of the N-face total) / N")
    print()
    print(f"{'N':>4} {'per-face avg':>14} {'sum(N faces)/N':>15}"
          f" {'dev from closed':>16}")
    for N in (2, 3, 4, 5, 6, 8, 12):
        per_face = face_rot_avg_numeric(N, NOON_H, k=0, n=n)
        total_mean = sum(total_R(N, 360.0 * i / (n - 1), NOON_H)
                         for i in range(n)) / n
        sumN = total_mean / N
        print(f"{N:>4} {per_face:>14.9f} {sumN:>15.9f} {per_face-cf:>+16.2e}")
    cyl = cylinder_rot_avg_numeric(NOON_H)
    print(f"{'cyl':>4} {cyl:>14.9f} {cyl:>15.9f} {cyl-cf:>+16.2e}"
          "   (cylinder limit, K=3600 facets)")
    print()
    print("=> Every N (and the cylinder) gives the SAME per-installed-area mean,")
    print("   1/pi * cos h = 0.305107.  Shape choice is NOT an energy question.")
    print()


# ===========================================================================
# (2)  RIPPLE  —  instantaneous total harvest vs rotation
# ===========================================================================
def R_stats(N, n=72001):
    vals = [total_R(N, 360.0 * i / (n - 1)) for i in range(n)]
    return min(vals), max(vals), sum(vals) / n


def series_metric_N(N, h_deg, psi_deg):
    """SERIES-STRING metric for an N-gon prism (all N faces one series string,
    ideal per-face bypass fitted — ADR-046 s2.3).  The string current is the
    weakest illuminated face, the voltage is the sum of the illuminated faces:
        P/P_ideal = max_{j=1..N} ( j * cos_(j) ) / N
    where cos_(j) is the j-th LARGEST of the N instantaneous cos(incidence)
    factors."""
    fs = sorted((face_cos_k(N, h_deg, psi_deg, k) for k in range(N)), reverse=True)
    return max((j + 1) * fs[j] for j in range(N)) / N


def series_stats(N, h_deg, n=3601):
    vals = [series_metric_N(N, h_deg, 360.0 * i / (n - 1)) for i in range(n)]
    return min(vals), max(vals), sum(vals) / len(vals)


def part2():
    print("=" * 78)
    print("(2) RIPPLE  —  total harvest vs rotation, winter noon "
          f"(h = {NOON_H:.2f} deg)")
    print("=" * 78)
    print("For VERTICAL faces total(psi) = cos h * R(psi) with R = sum of clamped")
    print("cos(psi - a_k); cos h is a common factor, so the % ripple of the total")
    print("is INDEPENDENT of elevation (only the mean scales with cos h).")
    print()
    print(f"{'N':>4} {'R_min':>9} {'R_max':>9} {'R_mean':>9} {'N/pi':>9}"
          f" {'ripple pk-pk %':>15} {'+/- %':>8}")
    for N in (2, 3, 4, 5, 6, 8, 12):
        lo, hi, mean = R_stats(N)
        pkpk = (hi - lo) / mean * 100.0
        print(f"{N:>4} {lo:>9.5f} {hi:>9.5f} {mean:>9.5f} {N/math.pi:>9.5f}"
              f" {pkpk:>15.2f} {pkpk/2:>8.2f}")
    print("  (R_mean must equal N/pi exactly; the sampler confirms it.)")
    print()
    lo3, hi3, m3 = R_stats(3)
    lo4, hi4, m4 = R_stats(4)
    print(f"N=3 ripple {((hi3-lo3)/m3*100):.2f} %  vs  N=4 ripple "
          f"{((hi4-lo4)/m4*100):.2f} %  -> N=3 has LESS ripple: "
          f"{(hi3-lo3)/m3 < (hi4-lo4)/m4}")
    print("  why: a square reaches psi=45 deg with TWO faces at cos45 = 0.707")
    print("  (R = 1.414) but psi=0 with one face at 1.0 and two exactly edge-on")
    print("  (R = 1.0) -> a 41 % swing.  A triangle's normals are 120 deg apart,")
    print("  so the best face is never more than 60 deg off the sun (cos >= 0.5)")
    print("  and the second face can never be strongly lit at the same time:")
    print("  R stays in [0.866, 1.000] -> a 14 % swing.")
    print()
    print("SERIES metric (the string as actually wired, ideal bypass fitted):")
    print(f"{'N':>4} {'S_min':>9} {'S_max':>9} {'S_mean':>9} {'ripple pk-pk %':>15}")
    for N in (2, 3, 4, 5, 6):
        lo, hi, mean = series_stats(N, NOON_H)
        print(f"{N:>4} {lo:>9.5f} {hi:>9.5f} {mean:>9.5f} {(hi-lo)/mean*100:>15.2f}")
    print()


# ===========================================================================
# (3)  THE SERIES ARITHMETIC  —  the hard constraint
# ===========================================================================
COLD_OCV_PER_CELL = 9.3 / 12.0     # ADR-049 s3: 12-cell string ~9.3 V at -60 C


def part3():
    print("=" * 78)
    print("(3) SERIES ARITHMETIC  —  12 cells in SERIES, IDENTICAL faces")
    print("=" * 78)
    print(f"cell V_mp ~ 0.5 V and is SIZE-INDEPENDENT (ADR-049), so array V = "
          f"n_series * 0.5 V")
    print(f"bank {V_BANK} V (ADR-049 s3); radio ceiling {V_RADIO_MAX} V "
          f"(ADR-047 s1.1); load max = 5.5 V x 1.118 A = {P_LOAD_MAX:.3f} W "
          f"~ 6.15 W (ADR-047 s1.2)")
    print(f"cold (-60 C) OCV of the accepted 12-cell string ~ 9.3 V "
          f"(ADR-049 s3) -> {COLD_OCV_PER_CELL:.4f} V/cell")
    print()
    print(f"{'N':>3} {'c=12/N':>7} {'uniform?':>9} {'cells (uniform)':>15}"
          f" {'V nom':>7} {'cold OCV':>9}  verdict")
    for N in range(2, 7):
        c = N_CELLS / N
        if abs(c - round(c)) < 1e-9:
            c = int(round(c))
            tot = N * c
            v = tot * 0.5
            ocv = tot * COLD_OCV_PER_CELL
            print(f"{N:>3} {c:>7} {'yes':>9} {tot:>15} {v:>7.2f} {ocv:>9.2f}"
                  f"  COMPATIBLE" + ("  (but N=2 is a FLAT PLATE: the two faces"
                                    " are back-to-back and shade each other)"
                                    if N == 2 else ""))
        else:
            v10, ocv10 = 10 * 0.5, 10 * COLD_OCV_PER_CELL
            v15, ocv15 = 15 * 0.5, 15 * COLD_OCV_PER_CELL
            print(f"{N:>3} {c:>7.1f} {'NO':>9} {10:>15} {v10:>7.2f} {ocv10:>9.2f}"
                  f"  FAIL: {v10:.1f} V < {V_BANK} V bank -> cannot charge")
            print(f"{'':>3} {'':>7} {'':>9} {15:>15} {v15:>7.2f} {ocv15:>9.2f}"
                  f"  FAIL: {v15:.1f} V > {V_RADIO_MAX} V ceiling (nominal)")
            print(f"{'':>3} {'':>7} {'':>9} {12:>15} {6.0:>7.2f} {9.3:>9.2f}"
                  f"  only NON-UNIFORM (2,2,2,3,3) -> violates ADR-049 s'identical'")
    print()
    print("Honest note: even the accepted 12-cell/6.0 V string EXCEEDS the 5.5 V")
    print("radio ceiling in nominal terms; ADR-049 s3 makes the rated shunt clamp")
    print("MANDATORY for exactly that reason ('no series count satisfies both').")
    print("So '<= 5.5 V' is unreachable at any N; the criterion that actually")
    print("selects is 12/N INTEGER with the array at 6.0 V.")
    print()


# ===========================================================================
# (4)  PHYSICAL CONSEQUENCES PER SURVIVING N
# ===========================================================================
def face_len(c, L):
    return c * L + (c - 1) * GAP + 2 * M_END


def part4():
    print("=" * 78)
    print("(4) PHYSICAL CONSEQUENCES PER SURVIVING N  (N = 3, 4, 6)")
    print("=" * 78)
    print("face height  = c*L + (c-1)*gap + 2*m_end      (cells stacked along the")
    print("               blade/height; c = 12/N)")
    print("face width   = W + 2*m_side                   (tangential)")
    print("outer diam   = face_width / sin(pi/N)         (regular N-gon: s=a/sin(pi/N))")
    print("board area   = face_w * face_h + tab(8x9)     per face, full-face carrier")
    print("board mass   = board_area_cm2 * 0.1276 g/cm2  (0.6 mm FR4 x1.15)")
    print("aspect ratio = face height / outer diameter   (HIGHER = taller/narrower)")
    print()
    survivors = (3, 4, 6)
    for key in ("small", "large"):
        C = CELLS[key]
        fw = C["W"] + 2 * M_SIDE
        print(f"--- {key.upper()} cell ({C['L']} x {C['W']} mm) ---")
        print(f"face width (all N) = {C['W']} + 2*{M_SIDE} = {fw:.2f} mm")
        print(f"{'N':>3} {'c':>3} {'face (mm)':>17} {'height':>8} {'diam':>8}"
              f" {'tabs':>5} {'seams':>6} {'AR':>6} {'board cm2':>10}"
              f" {'board g':>8} {'cells g':>8} {'area cm2':>9}")
        for N in survivors:
            c = N_CELLS // N
            h = face_len(c, C["L"])
            diam = fw / math.sin(math.pi / N)
            board_cm2 = (h * fw + TAB_W * TAB_L) * N * 0.01
            board_g = board_cm2 * FR4_G_PER_CM2
            cells_g = N_CELLS * C["m"]
            area_cm2 = N_CELLS * C["area"]
            print(f"{N:>3} {c:>3} {h:>7.2f}x{fw:>7.2f} {h:>8.2f} {diam:>8.2f}"
                  f" {N:>5} {N:>6} {h/diam:>6.2f} {board_cm2:>10.2f}"
                  f" {board_g:>8.3f} {cells_g:>8.2f} {area_cm2:>9.2f}")
        print(f"  (cell area and cell mass are IDENTICAL for every N: 12 cells;")
        print(f"   only the board geometry differs.  'seams' = vertical edge joins")
        print(f"   a CLOSED prism needs; a folded one-piece board needs N-1 folds.)")
        print()
    print("RANKINGS (small cell, full-face carrier — spine+ribs is ~28.4 % of this,")
    print("wing_mass_model.py):")
    for key in ("small",):
        C = CELLS[key]
        fw = C["W"] + 2 * M_SIDE
        rows = []
        for N in survivors:
            c = N_CELLS // N
            h = face_len(c, C["L"])
            diam = fw / math.sin(math.pi / N)
            board_g = (h * fw + TAB_W * TAB_L) * N * 0.01 * FR4_G_PER_CM2
            rows.append((N, h, diam, board_g, h / diam))
        print(f"  shortest blade   : N={min(rows,key=lambda r:r[1])[0]}"
              f" ({min(r[1] for r in rows):.2f} mm)")
        print(f"  largest diameter : N={max(rows,key=lambda r:r[2])[0]}"
              f" ({max(r[2] for r in rows):.2f} mm)")
        print(f"  lightest board   : N={min(rows,key=lambda r:r[3])[0]}"
              f" ({min(r[3] for r in rows):.3f} g)")
        print(f"  fewest tabs      : N={survivors[0]} ({survivors[0]})")
        print(f"  lowest aspect AR : N={min(rows,key=lambda r:r[4])[0]}"
              f" ({min(r[4] for r in rows):.2f})  <- most stable (short+wide)")
        print(f"  highest aspect AR: N={max(rows,key=lambda r:r[4])[0]}"
              f" ({max(r[4] for r in rows):.2f})  <- least stable (tall+narrow)")
        print(f"  board mass spread across N: {min(r[3] for r in rows):.3f} .."
              f" {max(r[3] for r in rows):.3f} g "
              f"({(max(r[3] for r in rows)-min(r[3] for r in rows)):.3f} g)")
    print()
    print("fold (bend) angle at a prism's vertical seam = exterior angle = 360/N deg:")
    for N in survivors:
        print(f"  N={N}: interior {(N-2)*180//N} deg, seam turn {360//N} deg")
    print()


# ===========================================================================
# (5) ALTERNATIVE READING (blades as RADIAL fins at 360/N) — cross-check only
# ===========================================================================
def part5_alt():
    print("=" * 78)
    print("(5) CROSS-CHECK ONLY — the other reading: N radial fins at 360/N")
    print("=" * 78)
    print("If the 'polygon' instead means N RADIAL FIN blades (like the accepted")
    print("design) at 360/N, the faces are long and the outer diameter = 2 x blade")
    print("length (the blade length grows as cells/face = 12/N grow):")
    print(f"{'N':>3} {'c':>3} {'blade (mm)':>17} {'outer diam mm':>14}")
    for N in (3, 4, 6):
        c = N_CELLS // N
        L = face_len(c, 52.07)
        print(f"{N:>3} {c:>3} {L:>7.2f}x{25.0:<7.2f} {2*(L):>14.2f}")
    print("  -> under THIS reading the triangle is the WIDEST (4 cells/fin), which")
    print("     is a different trade (bigger inertia, bigger drag) but the same")
    print("     verdict: no energy gain, and no case for switching away from N=4.")
    print()


def part6_seams():
    print("=" * 78)
    print("(6) CLOSED-PRISM SEAM COST  (joining the faces along their long edges)")
    print("=" * 78)
    print("A CLOSED prism must join adjacent faces along the vertical (long) edge of")
    print("length = the face height.  Solder fillet cross-section A_f is an ASSUMPTION")
    print("-> TODO(unverified); 1 oz Cu + SAC305 at 7.4 mg/mm3.")
    A_F = 0.30        # mm2 fillet cross-section  TODO(unverified)
    print(f"seam mass = A_f * face_height * 7.4e-3 g/mm3   (A_f = {A_F} mm2)")
    print(f"{'N':>3} {'height mm':>10} {'seams':>6} {'g/seam':>8} {'seam g':>8}"
          f" {'vs current (0 seams)':>22}")
    for N in (3, 4, 6):
        h = face_len(12 // N, CELLS["small"]["L"])
        per = A_F * h * 0.0074
        print(f"{N:>3} {h:>10.2f} {N:>6} {per:>8.3f} {per*N:>8.3f}"
              f" {'+%.2f g' % (per*N):>22}")
    print("  (total seam length ~ 2 x the total cell-string length, so the seam")
    print("   MASS is nearly N-independent; what changes is the JOINT COUNT and,")
    print("   critically, the number of brittle hand-joints on a 118-340 mm seam.")
    print()


def main():
    print("#" * 78)
    print("# ngon_prisms.py — N-gon vertical prism analysis (balloon-fresh)")
    print("#" * 78)
    print()
    part1()
    part2()
    part3()
    part4()
    part5_alt()
    part6_seams()


if __name__ == "__main__":
    main()
