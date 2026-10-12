#!/usr/bin/env python3
"""
positioner_lowcost_model.py — computed tables for the low-cost AZ/EL positioner
study (dish right-sizing, torque chain, stow geometry, backlash/pointing,
and the 2.4 GHz uplink required-gain question).

Companion to docs/analysis/positioner-lowcost-3dprinted.md.
Every number marked COMPUTED in the doc is this script's own printed output.

    python3 docs/analysis/positioner_lowcost_model.py

stdlib only (math).  Every constant carries its basis inline:
  [CITED <path> §]  = repo-committed value
  [VENDOR <url>]    = vendor datasheet/page figure
  [ASSUMPTION]      = declared design assumption
  [ESTIMATE]        = labelled estimate, not a datasheet figure
  TODO(unverified)  = cannot source; never presented as sourced.
"""

import math

# ---------------------------------------------------------------------------
# 0. Physical constants and design assumptions
# ---------------------------------------------------------------------------
C       = 299792458.0          # m/s
F_24    = 2.4e9                # Hz, 2.4 GHz uplink band  [CITED ADR-034/ADR-039]
F_433   = 433.05e6             # Hz, 433 MHz downlink band [CITED ADR-039]
LAM24   = C / F_24             # m
LAM433  = C / F_433            # m
RHO     = 1.225                # kg/m^3 sea level 15 C ISA       [ASSUMPTION]
CD_SOLID= 1.2                  # solid reflector drag coeff      [CITED brief/task]
CD_MESH = 0.5                  # mesh/grid reflector drag coeff  [CITED brief/task]
SF      = 2.0                  # holding/hold safety factor      [ASSUMPTION]
K_DYN   = 0.6                  # stepper pull-out / holding derate [ESTIMATE]
V_REF   = 20.0                 # m/s reference wind (task figure)  [CITED task]


def dish_gain_dbi(D, lam, eta):
    return 10.0 * math.log10(eta * (math.pi * D / lam) ** 2)


def hpbw_deg(D, lam):
    # uniform-aperture approximation, as used by the repo's own rf model
    return 70.0 * lam / D


def area(D):
    return math.pi * D * D / 4.0


def wind_force(D, v, Cd):
    return 0.5 * RHO * v * v * area(D) * Cd


def print_header(t):
    print()
    print("=" * 78)
    print(t)
    print("=" * 78)


# ---------------------------------------------------------------------------
# 1. DISH RIGHT-SIZING  (the dominant cost lever)
# ---------------------------------------------------------------------------
def t_rightsizing():
    print_header("TABLE 1 — DISH RIGHT-SIZING: gain, swept area, wind force")
    print("G = 10*log10(eta*(pi*D/lambda)^2);  HPBW = 70*lambda/D;")
    print("A = pi*D^2/4;  F = 0.5*rho*v^2*A*Cd   with rho=1.225, v=%g m/s" % V_REF)
    print("lambda(2.4 GHz) = %.4f m = %.1f mm" % (LAM24, LAM24 * 1000))
    print()
    print("%6s %10s %10s %10s %10s %10s %10s %10s" % (
        "D[m]", "G[0.55]", "G[0.60]", "HPBW[deg]", "A[m^2]",
        "F_solid[N]", "F_mesh[N]", "F_solid[kgf]"))
    for D in (0.6, 0.9, 1.2, 1.5):
        g55 = dish_gain_dbi(D, LAM24, 0.55)
        g60 = dish_gain_dbi(D, LAM24, 0.60)
        print("%6.2f %10.2f %10.2f %10.2f %10.4f %10.1f %10.1f %10.2f" % (
            D, g55, g60, hpbw_deg(D, LAM24), area(D),
            wind_force(D, V_REF, CD_SOLID), wind_force(D, V_REF, CD_MESH),
            wind_force(D, V_REF, CD_SOLID) / 9.80665))
    print()
    print("Ratio of 1.2 m to 0.6 m:  area = %.2fx, wind force = %.2fx (D^2 law)" % (
        area(1.2) / area(0.6), wind_force(1.2, V_REF, CD_SOLID) / wind_force(0.6, V_REF, CD_SOLID)))
    print("Ratio of 1.2 m to 0.9 m:  area = %.2fx, wind force = %.2fx" % (
        area(1.2) / area(0.9), wind_force(1.2, V_REF, CD_SOLID) / wind_force(0.9, V_REF, CD_SOLID)))


# ---------------------------------------------------------------------------
# 2. WIND FORCE vs WIND SPEED  (operating vs storm/stow)
# ---------------------------------------------------------------------------
def t_wind_vs_v():
    print_header("TABLE 2 — WIND FORCE vs SPEED, solid (Cd 1.2) and mesh (Cd 0.5)")
    print("F = 0.5*rho*v^2*A*Cd;  A = pi*D^2/4   (rho=1.225)")
    print()
    print("%6s %10s | %-32s | %-32s" % ("v[m/s]", "v[km/h]", "F_solid[N]: 0.6 / 0.9 / 1.2 m",
                                        "F_mesh[N]: 0.6 / 0.9 / 1.2 m"))
    for v in (10.0, 14.0, 20.0, 30.0, 40.0):
        s = " ".join("%7.1f" % wind_force(D, v, CD_SOLID) for D in (0.6, 0.9, 1.2))
        m = " ".join("%7.1f" % wind_force(D, v, CD_MESH) for D in (0.6, 0.9, 1.2))
        print("%6.0f %10.0f | %-32s | %-32s" % (v, v * 3.6, s, m))


# ---------------------------------------------------------------------------
# 3. STOW GEOMETRY — silhouette of a dish parked at the zenith
# ---------------------------------------------------------------------------
def stow_silhouette(D, fod):
    """Vertical-plane silhouette area of a paraboloid whose aperture faces the
    zenith (elevation 90 deg), wind horizontal.
      surface: z = r^2/(4f)  (aperture up)
      silhouette from the side: x extent = +/- r at each height z
      A_sil = integral_0^sag 2*r(z) dz = (4/3)*sqrt(4f)*sag^(3/2)
      sag = D^2/(16f)
    """
    f = fod * D
    sag = D * D / (16.0 * f)
    return (4.0 / 3.0) * math.sqrt(4.0 * f) * sag ** 1.5, sag, f


def t_stow():
    print_header("TABLE 3 — STOW GEOMETRY: aperture-up silhouette vs full aperture")
    print("A_sil = (4/3)*sqrt(4f)*sag^1.5 ;  sag = D^2/(16f)  (f = (f/D)*D)")
    print()
    print("%6s %6s %8s %8s %12s %12s %10s" % (
        "D[m]", "f/D", "f[m]", "sag[m]", "A_full[m^2]", "A_stow[m^2]", "ratio"))
    for D in (0.6, 0.9, 1.2):
        for fod in (0.40, 0.45):
            a_sil, sag, f = stow_silhouette(D, fod)
            print("%6.2f %6.2f %8.3f %8.4f %12.4f %12.4f %10.3f" % (
                D, fod, f, sag, area(D), a_sil, a_sil / area(D)))
    print()
    print("Wind-torque reduction from stowing (aperture up) vs worst case (aperture")
    print("broadside), D=1.2 m, f/D=0.45, 40 m/s, solid:")
    a_sil, sag, f = stow_silhouette(1.2, 0.45)
    F_full = 0.5 * RHO * 40.0 ** 2 * area(1.2) * CD_SOLID
    F_stow = 0.5 * RHO * 40.0 ** 2 * a_sil * CD_SOLID
    print("  F_broadside = %.0f N   F_stowed = %.0f N   reduction = %.1fx" % (
        F_full, F_stow, F_full / F_stow))


# ---------------------------------------------------------------------------
# 4. TORQUE CHAIN — wind torque, required output, reduction ratio
# ---------------------------------------------------------------------------
STEPPERS = [
    ("NEMA17 17HS19-2004S1", 0.59, 8.75,
     "https://www.omc-stepperonline.com/nema-17-bipolar-59ncm-84oz-in-2a-42x48mm-4-wires-w-1m-cable-connector-17hs19-2004s1"),
    ("NEMA23 23HE45-4204S", 3.0, 23.02,
     "https://www.omc-stepperonline.com/e-series-nema-23-bipolar-1-8deg-3-0-nm-425oz-in-4-2a-57x57x113mm-4-wires-23he45-4204s"),
    ("NEMA34 34HE45-6004S", 8.2, 36.36,
     "https://www.omc-stepperonline.com/e-series-nema-34-stepper-motor-bipolar-1-8deg-8-2-nm-1161-45oz-in-6-0a-86x86x114mm-4-wires-34he45-6004s"),
]
WORM = [
    ("NMRV30 15:1", 15, 18.0, "9 mm",
     "https://www.omc-stepperonline.com/15-1-worm-gearbox-nmrv30-worm-gear-speed-reducer-9mm-input-shaft-diameter-nmrv30-g15-d9"),
    ("NMRV40 20:1", 20, 40.0, "14 mm",
     "https://www.omc-stepperonline.com/20-1-worm-gearbox-nmrv40-worm-gear-speed-reducer-14mm-input-shaft-diameter-nmrv40-g20-d14"),
    ("NMRV50 30:1", 30, 85.0, "19 mm",
     "https://www.omc-stepperonline.com/30-1-worm-gearbox-nmrv50-worm-gear-speed-reducer-19mm-input-shaft-diameter-nmrv50-g30-d19"),
    ("NMRV50 50:1", 50, 74.0, "19 mm",
     "https://www.omc-stepperonline.com/50-1-worm-gearbox-nmrv50-worm-gear-speed-reducer-19mm-input-shaft-diameter-nmrv50-g50-d19"),
]


def el_torque(D, v, Cd, lever_frac):
    """lever_frac = L/D.  0.25 = balanced (axis through dish CP), 0.5 = axis at rim."""
    return wind_force(D, v, Cd) * lever_frac * D


def t_torque_chain():
    print_header("TABLE 4 — TORQUE CHAIN: wind torque -> required output -> ratio")
    print("T = F * L,  L = lever_frac * D;  T_req = T * SF (SF=%.1f)" % SF)
    print("lever_frac 0.25 = balanced elevation axis through the dish CP;")
    print("lever_frac 0.50 = worst case (elevation axis at the rim plane).")
    print("n_hold = T_req / T_hold ;  n_move = T_wind / (K_dyn * T_hold), K_dyn=%g" % K_DYN)
    print()
    for lever_frac in (0.25, 0.50):
        print("---- lever_frac = %.2f ----" % lever_frac)
        print("%6s %9s %11s %13s | %s" % (
            "D[m]", "F[N]", "T_wind[Nm]", "T_req[Nm]",
            "  ".join("n(%s)" % s[0].split()[0] for s in STEPPERS)))
        for D in (0.6, 0.9, 1.2):
            F = wind_force(D, V_REF, CD_SOLID)
            T = el_torque(D, V_REF, CD_SOLID, lever_frac)
            row = "  ".join("%9.1f" % (T * SF / s[1]) for s in STEPPERS)
            print("%6.2f %9.1f %11.1f %13.1f | %s" % (D, F, T, T * SF, row))
        print()


def t_worm_sizing():
    print_header("TABLE 5 — PURCHASED WORM REDUCER SIZING (print structure, buy gearing)")
    print("Output capability = min(T_hold * ratio * eff, gearbox rated max torque), eff=0.75 [ESTIMATE]")
    print()
    print("%-12s %6s %8s %10s %14s" % ("gearbox", "ratio", "rated[Nm]", "in-shaft", "with NEMA23(3.0Nm)"))
    for name, ratio, rated, shaft, url in WORM:
        cap = min(3.0 * ratio * 0.75, rated)
        print("%-12s %6d %8.1f %10s %14.1f" % (name, ratio, rated, shaft, cap))
    print()
    print("Requirement (balanced, SF=2, 20 m/s solid):")
    for D in (0.6, 0.9, 1.2):
        T = el_torque(D, V_REF, CD_SOLID, 0.25)
        print("  D=%.1f m -> T_req = %.1f Nm  (worst-case L=D/2 -> %.1f Nm)" % (
            D, T * SF, el_torque(D, V_REF, CD_SOLID, 0.5) * SF))
    print()
    print("NMRV40 20:1 (rated 40 Nm) with a NEMA23 3.0 Nm motor:")
    print("  min(3.0*20*0.75, 40) = %.1f Nm" % min(3.0 * 20 * 0.75, 40.0))
    print("NMRV50 30:1 (rated 85 Nm) with a NEMA23 3.0 Nm motor:")
    print("  min(3.0*30*0.75, 85) = %.1f Nm" % min(3.0 * 30 * 0.75, 85.0))


# ---------------------------------------------------------------------------
# 5. BACKLASH vs POINTING
# ---------------------------------------------------------------------------
def t_backlash():
    print_header("TABLE 6 — BACKLASH vs POINTING")
    print("pointing budget = 10% of HPBW [CITED task/brief];  HPBW = 70*lambda/D")
    print("printed belt/gear backlash 0.5-2.0 deg [CITED brief];")
    print("AS5600 magnetic encoder 12 bit = 360/4096 = %.3f deg [VENDOR datasheet]" % (360.0 / 4096))
    print("MT6701 14 bit = 360/16384 = %.3f deg [VENDOR datasheet]" % (360.0 / 16384))
    print()
    print("%6s %12s %14s %12s %12s" % ("D[m]", "HPBW[deg]", "budget[deg]",
                                        "bl 0.5deg/bud", "bl 2.0deg/bud"))
    for D in (0.6, 0.9, 1.2):
        h = hpbw_deg(D, LAM24)
        b = 0.1 * h
        print("%6.2f %12.2f %14.3f %12.2f %12.2f" % (D, h, b, 0.5 / b, 2.0 / b))
    print()
    print("Slant-range lateral error at 300 km for a given angular error:")
    for a in (0.1, 0.5, 0.73, 1.0, 2.0):
        print("  %5.2f deg -> %8.0f m at 300 km" % (a, 300000 * math.tan(math.radians(a))))


# ---------------------------------------------------------------------------
# 6. 2.4 GHz UPLINK — required ground gain
# ---------------------------------------------------------------------------
def fspl_db(d_km, f_mhz):
    return 20.0 * math.log10(d_km) + 20.0 * math.log10(f_mhz) + 32.45


def t_uplink():
    print_header("TABLE 7 — 2.4 GHz UPLINK: what ground gain is actually REQUIRED")
    print("required_G_ground = S_balloon + FSPL - P_tx_conducted - G_balloon_rx")
    print("Sensitivity: bare LR2021 2.4 GHz SF12 -137 dBm [CITED LINK-BUDGET-LICENCE-EXEMPT §0]")
    print("             F33-2G4 with LNA -136 / without LNA -124 dBm [CITED same]")
    print("Balloon RX antenna: 10 dBi (ADR-037) / 6 dBi (PCB Yagi) [CITED same]")
    print()
    print("FSPL: 2.4 GHz 300 km = %.1f dB ; 650 km = %.1f dB ; 433 MHz 300 km = %.1f dB" % (
        fspl_db(300, 2400), fspl_db(650, 2400), fspl_db(300, 433)))
    print()
    for d in (300, 650):
        print("---- range %d km ----" % d)
        print("%10s %10s %14s %14s %14s" % (
            "P_tx[dBm]", "G_rx[dBi]", "reqG@-137", "reqG@-136", "reqG@-124"))
        for ptx in (0, 12, 20, 30):
            row = " ".join("%14.1f" % (S + fspl_db(d, 2400) - ptx - 10)
                           for S in (-137, -136, -124))
            print("%10d %10d %s" % (ptx, 10, row))
        print()
    print("EIRP-CAPPED REGIME (licence-exempt 100 mW EIRP = 20 dBm total):")
    print("  an EIRP cap makes antenna GAIN irrelevant to closure -- the cap, not the")
    print("  aperture, sets the link.  Margin = EIRP - FSPL + G_rx - S:")
    for d in (300, 650):
        for S in (-137, -136, -124):
            m = 20.0 - fspl_db(d, 2400) + 10 - S
            print("    %d km, EIRP 20 dBm, G_rx 10 dBi, S=%4d dBm -> margin %+6.1f dB" % (d, S, m))
    print()
    g06 = dish_gain_dbi(0.6, LAM24, 0.55)
    print("A 0.6 m dish = %.1f dBi gain: with a 0 dBm PA that is a 20.0 dBm EIRP" % g06)
    print("(exactly the licence-exempt cap) -> still %+.1f dB margin at 300 km, %+.1f dB at 650 km." % (
        20.0 - fspl_db(300, 2400) + 10 + 137, 20.0 - fspl_db(650, 2400) + 10 + 137))
    print()
    print("SMALLEST DISH THAT CLOSES (licence-exempt, 20 dBm EIRP, balloon LNA, 10 dBi):")
    print("  required gain is NEGATIVE at 300 km and 650 km -> the honest answer is")
    print("  NO DISH IS REQUIRED to close the link (an omni closes it).")
    print("  Smallest dish worth building for margin + low-power PA + beam discipline:")
    for D in (0.3, 0.6, 0.9):
        print("    D=%.1f m -> %.1f dBi ; margin at 300 km with a 0 dBm PA = %+.1f dB" % (
            D, dish_gain_dbi(D, LAM24, 0.55),
            dish_gain_dbi(D, LAM24, 0.55) + 0 - fspl_db(300, 2400) + 10 + 137))


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    t_rightsizing()
    t_wind_vs_v()
    t_stow()
    t_torque_chain()
    t_worm_sizing()
    t_backlash()
    t_uplink()
    print()
    print("=== end of positioner_lowcost_model.py output ===")
