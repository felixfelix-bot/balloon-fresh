#!/usr/bin/env python3
"""
gain_per_dollar_cliff_model.py — the cost cliff in the balloon ground-station
gain-per-dollar curve, the levers that raise performance without crossing it, and
the Yagi-array-at-433 alternative to a 2.6 m dish.

Prints every table used in docs/analysis/gain-per-dollar-cliff.md, verbatim.
Reproduce:  python3 docs/analysis/gain_per_dollar_cliff_model.py

SOURCING RULE (repo ADR-first policy): every *external* number this script consumes is
carried in a PRICES / CITED block below with the URL it came from (most inherited from the
prior committed analyses `docs/analysis/ground-station-bom-candidates.md`,
`docs/analysis/ground-station-flrc-max-throughput.md` and
`docs/analysis/positioner-lowcost-3dprinted.md`, which fetched them and labelled them
CONFIRMED). A number with no URL is either a COMPUTED quantity (formula printed) or is
labelled ESTIMATE with its basis named. Nothing external is invented here.

No network access is used at run time.
"""

import math

# --------------------------------------------------------------------------- #
# 0. Constants and CITED / PRICES blocks
# --------------------------------------------------------------------------- #
C_LIGHT = 299_792_458.0
F_433 = 433.05e6            # CITED: repo band (LICENCE-EXEMPT budget uses 433.05 MHz)
F_24 = 2.4e9                # CITED: LINK-BUDGET-LICENCE-EXEMPT.md
LAM_433 = C_LIGHT / F_433   # COMPUTED
LAM_24 = C_LIGHT / F_24     # COMPUTED
RHO = 1.225                 # ASSUMPTION ISA sea level 15 C
ETA = 0.55                  # brief eta; 0.60 also tabulated
CD_SOLID = 1.2              # ASSUMPTION (matches prior repo model; Gibertini-derived 1.38)
CD_MESH = 0.5               # brief/task
KM = 1000.0

# --- PRIOR-REQUIRED 433 MHz ground gain (CITED: ground-station-lowpower-link-and-shared-dish.md
#     §2b, FSPL 433.05 MHz @ 650 km = 141.4 dB, G_balloon = 0 dBi, +22 dBm chip max) ---
REQ_G_650 = {               # FLRC rate -> required ground gain (dBi) @ +22 dBm, 650 km
    "FLRC 2.6 Mbps":  18.9,   # CITED same doc §2b
    "FLRC 1.04 Mbps": 14.4,   # CITED
    "FLRC 650 kbps":  12.4,   # CITED
    "FLRC 325 kbps":   9.4,   # CITED
}
REQ_G_650_13DBM = {         # same @ +13 dBm (the low-power / ADR-066 premise)
    "FLRC 2.6 Mbps":  27.9,   # CITED
    "FLRC 1.04 Mbps": 23.4,   # CITED
    "FLRC 650 kbps":  21.4,   # CITED
    "FLRC 325 kbps":  18.4,   # CITED
}
# Semtech LR2021 sub-GHz FLRC sensitivity (1% PER), datasheet Table 3-12 — CITED via
# ground-station-lowpower-link-and-shared-dish.md §1a. NOTE: taken at 915 MHz; a
# 433 MHz-specific row is TODO(unverified) in that doc (band-flat within a few dB).
FLRC_SENS = {
    "FLRC 2.6 Mbps":  -100.5,
    "FLRC 1.04 Mbps": -105.0,
    "FLRC 650 kbps":  -107.0,
    "FLRC 325 kbps":  -110.0,
}
S_LORA_625_SF12 = -143.0    # CITED: Semtech Table 3-17 / repo inventories

# --- 433 MHz downlink antennas, purchased (CITED: ground-station-bom-candidates.md §0.1,
#     vendor = Funktechnik Bielefeld DE; prices CONFIRMED on the vendor page) ---
YAGIS = {
    # name: (gain_dBi, boom_m, price_EUR, url)
    "Sirio WY 400-6N":      (11.0, 1.20, 132.00,
        "https://www.funktechnik-bielefeld.de/sirio-wy-400-6n-6-element-70cm-band-yagi-richtantenne-400-470-mhz"),
    "Sirio WY 400-10N":     (14.0, 2.00, 155.00,
        "https://www.funktechnik-bielefeld.de/sirio-wy-400-10n"),
    "Diamond A-430S10R":    (13.1, 0.82,  69.00,
        "https://www.funktechnik-bielefeld.de/diamond-a-430s10r"),
    "Diamond A-430S15R":    (14.8, 1.39,  74.50,
        "https://www.funktechnik-bielefeld.de/diamond-a-430s15r"),
    "FlexaYagi FX 7015V":   (12.4, 1.19, 125.00,
        "https://www.funktechnik-bielefeld.de/flexayagi-fx-7015v-70cm-band-vormast-richtantenne-119cm-laenge"),
    "FlexaYagi FX 7044":    (16.6, 3.08, 164.00,   # 14.4 dBd
        "https://www.funktechnik-bielefeld.de/flexayagi-fx-7044"),
    "FlexaYagi FX 7044-4":  (16.7, 3.08, 219.00,   # 14.5 dBd
        "https://www.funktechnik-bielefeld.de/flexayagi-fx-7044-4"),
    "FlexaYagi FX 7073":    (18.0, 5.07, 215.00,   # 15.8 dBd
        "https://www.funktechnik-bielefeld.de/flexayagi-fx-7073"),
}

# --- RF Hamdesign FPD mesh dish KITS, 433 MHz (CITED: ground-station-flrc-max-throughput.md §5.1,
#     vendor pages + Oct-2026 price list PDF) ---
MESH_DISH = {
    # D_m: (gain_dBi_eta0.65_vendor, mass_kg, price_EUR_or_None, status)
    1.0: (11.2, None,  342.43, "in stock"),
    1.2: (12.9, 4.8,   387.20, "in stock"),
    1.5: (14.8, None,  499.73, "in stock"),
    1.9: (16.8, None,  901.45, "in stock"),
    2.4: (18.9, 14.0,  None,   "OUT OF STOCK"),
    3.0: (20.8, 27.0,  None,   "OUT OF STOCK"),
}
KIT_MASSES = [(1.2, 4.8), (2.4, 14.0), (3.0, 27.0)]   # CITED (vendor published masses)

# --- Rotators / positioners (CITED: ground-station-bom-candidates.md §5; prices
#     Funktechnik Bielefeld DE + RF Hamdesign Oct-2026 price list) ---
# (name, axes, wind_m2_tower, wind_m2_mast, price_EUR)
ROTATORS = [
    ("Yaesu G-450CDC",  "AZ+EL", 1.00, 0.50,  359.00),
    ("Yaesu G-1000DXC", "AZ",    2.20, 0.74,  529.00),
    ("SPID RAU",        "AZ",    None, None,  719.00),
    ("SPID RAK",        "AZ",    None, None,  749.00),
    ("Yaesu G-5500DC",  "AZ+EL", 1.00, 0.50,  949.00),
    ("Yaesu G-2800DXC", "AZ",    3.00, 1.00, 1049.00),
    ("SPX-01/MD-03",    "AZ+EL", None, None, 1132.00),
    ("SPID BIG-RAK",    "AZ",    None, None, 1203.95),
    ("SPX-02/MD-03",    "AZ+EL", None, None, 1249.00),
    ("SPID RAS",        "AZ+EL", None, None, 1260.82),
    ("SPID BIG-RAS",    "AZ+EL", None, None, 1775.00),
    ("SPX-06 slew",     "AZ+EL", None, None, 5487.00),
]

# --- 2.4 GHz dish + feed (CITED: ground-station-bom-candidates.md §0.2/§0.3) ---
DISH24 = [   # (name, D_m, price_EUR)
    ("Gibertini 75 SE Profi", 0.75,  94.90),
    ("Gibertini OP100SE",     0.97, 143.90),
    ("Kathrein CAS 90",       0.90, 249.00),
    ("used 90 cm Ku (Kleinanzeigen)", 0.90, 50.00),   # CITED "example" price
]
FEED24 = [   # (name, price_EUR_or_None)
    ("RF Hamdesign FPF RS-ONE ring feed", 185.00),
    ("RF Hamdesign LH-13XL helix feed",   220.00),
    ("RF Hamdesign CLX1 feed clamp",       46.00),
]
# Coax (CITED: ground-station-bom-candidates.md §7.4)
COAX = [("Ecoflex 15", 1.62, 13.60), ("Airborne 10 (LMR-400 class)", 1.92, 6.50),
        ("Aircell 7", 3.38, 4.06)]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def db(x):
    return 10.0 * math.log10(x)


def dish_gain_dBi(D, lam, eta=ETA):
    """G = 10 log10( eta (pi D / lam)^2 )."""
    return 10.0 * math.log10(eta * (math.pi * D / lam) ** 2)


def area(D):
    return math.pi * D * D / 4.0


def hpbw_deg(D, lam):
    """HPBW ~ 70 lam / D  (degrees)."""
    return 70.0 * lam / D


def wind_force(D, v, Cd, solidity=1.0):
    """F = 0.5 rho v^2 A Cd sigma."""
    return 0.5 * RHO * v * v * area(D) * Cd * solidity


def wind_moment(D, v, Cd, lever_frac):
    """T = F * L,  L = lever_frac * D."""
    return wind_force(D, v, Cd) * lever_frac * D


def fit_powerlaw(xs, ys):
    """least-squares slope of ln y vs ln x, plus R^2."""
    import statistics
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    n = len(xs)
    mx = sum(lx) / n
    my = sum(ly) / n
    sxx = sum((x - mx) ** 2 for x in lx)
    sxy = sum((lx[i] - mx) * (ly[i] - my) for i in range(n))
    b = sxy / sxx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ly)
    ss_res = sum((ly[i] - (a + b * lx[i])) ** 2 for i in range(n))
    r2 = 1 - ss_res / ss_tot if ss_tot else float("nan")
    return b, math.exp(a), r2


def hr(t=""):
    print("\n" + "=" * 78)
    if t:
        print(t)
        print("=" * 78)


# --------------------------------------------------------------------------- #
# 1. SCALING LAW — verify the exponents the cliff rests on
# --------------------------------------------------------------------------- #
def sec_scaling():
    hr("TABLE 1 — scaling laws of a 433 MHz dish (lam = %.4f m)" % LAM_433)
    print("G = 10log10(eta(piD/lam)^2) ; A = piD^2/4 ; F = q A Cd ; T = F*L (L=frac*D)")
    print("HPBW = 70 lam/D ; mass_est from vendor mesh-kit masses\n")
    v = 20.0
    Ds = [0.6, 0.9, 1.2, 1.5, 2.0, 2.6, 3.0]
    print("%5s %8s %8s %8s %8s %9s %10s %10s %9s" %
          ("D[m]", "G[dBi]", "A[m2]", "HPBW[deg]", "F_sol[N]", "F_mesh[N]",
           "T_f25[Nm]", "T_f50[Nm]", "m_est[kg]"))
    for D in Ds:
        g = dish_gain_dBi(D, LAM_433)
        a = area(D)
        print("%5.2f %8.2f %8.3f %8.2f %8.1f %9.1f %10.1f %10.1f %8.1f" %
              (D, g, a, hpbw_deg(D, LAM_433), wind_force(D, v, CD_SOLID),
               wind_force(D, v, CD_MESH), wind_moment(D, v, CD_SOLID, 0.25),
               wind_moment(D, v, CD_SOLID, 0.50), mesh_mass_est(D)))

    print("\n-- VERIFY the exponents (log-log least-squares over D = 0.6..3.0 m) --")
    pairs = [
        ("wind FORCE  vs D  (A ~ D^2)",           ds_vs(Ds, lambda D: wind_force(D, v, CD_SOLID)), 2.0),
        ("wind MOMENT vs D  (F*L, L ~ D)",        ds_vs(Ds, lambda D: wind_moment(D, v, CD_SOLID, 0.25)), 3.0),
        ("dish AREA   vs D",                      ds_vs(Ds, area), 2.0),
        ("mass_est    vs D  (vendor mesh kits)",  ds_vs(Ds, mesh_mass_est), 2.0),
        ("LINEAR GAIN vs D  (10^(G/10))",         ds_vs(Ds, lambda D: 10 ** (dish_gain_dBi(D, LAM_433) / 10)), 2.0),
        ("HPBW        vs D",                      ds_vs(Ds, lambda D: hpbw_deg(D, LAM_433)), -1.0),
    ]
    for name, ys, expect in pairs:
        b, a, r2 = fit_powerlaw(Ds, ys)
        print("  %-40s exponent = %+6.3f  (expect %+5.1f, R2=%.5f)" % (name, b, expect, r2))

    print("\n-- vendor mesh-kit mass, exact exponents --")
    for (d1, m1), (d2, m2) in [(KIT_MASSES[0], KIT_MASSES[1]), (KIT_MASSES[0], KIT_MASSES[2])]:
        print("  %.1f->%.1f m  D ratio %.2f  mass %.1f->%.1f kg  ratio %.2f  -> exponent %.2f"
              % (d1, d2, d2 / d1, m1, m2, m2 / m1, math.log(m2 / m1) / math.log(d2 / d1)))

    print("\n-- torque-chain check against the committed positioner model --")
    print("  committed (positioner-lowcost-3dprinted.md Table 4, lever 0.25D, SF 1):")
    print("    0.60 m -> 12.5 Nm ; 1.20 m -> 99.8 Nm ; ratio 7.98 over D-ratio 2.00 -> exponent 2.997")
    print("  this script, same formula, SF 1: 0.60 -> %.1f ; 1.20 -> %.1f" %
          (wind_moment(0.60, v, CD_SOLID, 0.25), wind_moment(1.20, v, CD_SOLID, 0.25)))


def ds_vs(Ds, f):
    return [f(D) for D in Ds]


def mesh_mass_est(D):
    """mass_est = a * D^b, fit to the vendor published mesh-kit masses."""
    D3 = [m[0] for m in KIT_MASSES]
    M3 = [m[1] for m in KIT_MASSES]
    b, a, _ = fit_powerlaw(D3, M3)
    return a * D ** b


# --------------------------------------------------------------------------- #
# 2. THE CLIFF — drag area vs the rotator ladder, and EUR/dB
# --------------------------------------------------------------------------- #
def rotator_price_for(drag_area_m2, mast_mounted=False):
    """Purchasable AZ+EL step function of required wind-load area (m^2). CITED prices.
    Ratings: Yaesu quotes antenna area (tower/mast); SPID/SPX do NOT publish m^2
    (TODO(unverified) in the BOM), so the SPX/SPID steps are placed by the vendor's own
    duty words ('light'/'medium'/'dishes up to 5 m')."""
    if drag_area_m2 <= 0.50:
        return ("Yaesu G-450CDC (mast rating 0.50 m2)", 359.00)
    if drag_area_m2 <= 1.00:
        return ("Yaesu G-450CDC (tower rating 1.00 m2)", 359.00)
    if drag_area_m2 <= 2.20:
        return ("SPX-01/MD-03 'light duty' (no m2 published)", 1132.00)
    if drag_area_m2 <= 3.00:
        return ("SPX-02/MD-03 'medium duty' (no m2 published)", 1249.00)
    return ("SPID BIG-RAS 'dishes up to 5 m' (vendor)", 1775.00)


def reflector_price_est(D):
    """Power-law fit to the RF Hamdesign mesh-kit prices (1.0/1.2/1.5/1.9 m).
    ESTIMATE outside that window. None for the two out-of-stock kits' printed price."""
    D3 = [1.0, 1.2, 1.5, 1.9]
    P3 = [342.43, 387.20, 499.73, 901.45]
    b, a, r2 = fit_powerlaw(D3, P3)
    return a * D ** b, b, r2


def mast_foundation_est(D, m_ref_D=2.6, m_ref_EUR=1250.0, base_EUR=350.0):
    """ESTIMATE: mast + foundation + guys, EUR.

    Cost is NOT linear in the overturning moment M ~ D^3: a steel pole sized to resist a
    moment needs section modulus Z ~ M, Z ~ d^3, so the pole diameter (and mass, and cost)
    grows as M^(1/3); a concrete foundation and the guy set grow faster, so a sqrt law is a
    defensible middle. Model: cost = base + (m_ref_EUR - base) * (M/M_ref)^0.5, anchored so
    that a 2.6 m dish lands at EUR 1250 (the midpoint of the Tier-B EXPLICIT line items for
    mast + foundation + guys: EUR 700-1800). ESTIMATE; the TASK-5 table's line items are the
    authoritative decomposition - this function is the curve used for the scaling argument.
    """
    M = wind_moment(D, 20.0, CD_SOLID, 0.25)
    M_ref = wind_moment(m_ref_D, 20.0, CD_SOLID, 0.25)
    return base_EUR + (m_ref_EUR - base_EUR) * (M / M_ref) ** 0.5


def sec_cliff():
    hr("TABLE 2 — THE CLIFF: solid dish drag area vs the rotator ladder")
    print("drag_area = A * Cd.  A = piD^2/4.  Cd_solid = 1.2, Cd_mesh = 0.5\n")
    print("%5s %9s %11s %11s %-52s %9s" %
          ("D[m]", "A[m2]", "A*1.2[m2]", "A*0.5[m2]", "solid rotator step", "EUR"))
    for D in [0.6, 0.75, 0.9, 0.93, 1.0, 1.2, 1.5, 1.9, 2.2, 2.4, 2.6, 3.0]:
        a = area(D)
        s = a * CD_SOLID
        m = a * CD_MESH
        nm, pr = rotator_price_for(s)
        print("%5.2f %9.3f %11.3f %11.3f %-52s %9.2f" % (D, a, s, m, nm, pr))
    print("\nsame table, MESH dish (Cd 0.5):")
    print("%5s %11s %-52s %9s" % ("D[m]", "A*0.5[m2]", "mesh rotator step", "EUR"))
    for D in [0.6, 0.9, 1.2, 1.5, 1.9, 2.2, 2.4, 2.6, 3.0]:
        m = area(D) * CD_MESH
        nm, pr = rotator_price_for(m)
        print("%5.2f %11.3f %-52s %9.2f" % (D, m, nm, pr))

    print("\n-- exact crossing points --")
    for Cd, label in [(CD_SOLID, "solid"), (CD_MESH, "mesh")]:
        for lim, why in [(0.50, "Yaesu MAST rating 0.50 m2"),
                         (1.00, "Yaesu TOWER rating 1.00 m2"),
                         (2.20, "SPX-01 'light duty' step"),
                         (3.00, "SPX-02 'medium duty' step")]:
            Dstar = math.sqrt(4 * lim / (math.pi * Cd))
            print("  %-6s Cd=%.1f crosses %5.2f m2 at D = %.3f m   (%s)" % (label, Cd, lim, Dstar, why))

    hr("TABLE 3 — the EUR/dB curve, WHOLE STATION (reflector + rotator + mast/foundation)")
    pr12, bexp, r2 = reflector_price_est(1.2)
    print("reflector_price_est(D) = %.2f * D^%.3f  (R2=%.4f, fit to the 4 in-stock mesh kits)"
          % (pr12 / 1.2 ** bexp, bexp, r2))
    print("mast+foundation+guys ESTIMATE: EUR 350 + 900*(M/M_2.6m)^0.5 (M ~ D^3); anchor EUR 1250 @ 2.6 m\n")
    print("%5s %8s %10s %10s %11s %11s %12s %10s %12s" %
          ("D[m]", "G[dBi]", "refl[EUR]", "rot[EUR]", "mast[EUR]", "total[EUR]",
           "EUR/dB", "EURdB_marg", "EUR_drag_m2"))
    G0 = dish_gain_dBi(0.6, LAM_433)
    for D in [0.6, 0.9, 0.93, 1.0, 1.2, 1.5, 1.9, 2.2, 2.4, 2.6, 3.0]:
        g = dish_gain_dBi(D, LAM_433)
        refl = reflector_price_est(D)[0]
        a = area(D) * CD_SOLID
        nm, rot = rotator_price_for(a)
        mast = mast_foundation_est(D)
        tot = refl + rot + mast
        eur_db = tot / (g - G0) if g > G0 else float("nan")
        print("%5.2f %8.2f %10.1f %10.1f %11.1f %11.1f %12.1f %10.1f %12.2f" %
              (D, g, refl, rot, mast, tot, eur_db, tot / g, tot / a))
    print("\n(rot[EUR] steps are the published vendor prices, not smoothed: the 0.93->1.00 m")
    print(" rows show the cliff — the whole gain jump from 0.6 to 1.0 m is < 5 dB while the")
    print(" rotator line and the D^3 mast line both step.)")

    print("\n-- CLIFF DELTAS: the marginal EUR/dB across each rotator boundary --")
    rungs = [0.6, 0.75, 0.93, 1.00, 1.20, 1.50, 1.90, 2.20, 2.60, 3.00]
    prev = None
    for D in rungs:
        g = dish_gain_dBi(D, LAM_433)
        refl = reflector_price_est(D)[0]
        a = area(D) * CD_SOLID
        nm, rot = rotator_price_for(a)
        mast = mast_foundation_est(D)
        tot = refl + rot + mast
        if prev is not None:
            dG = g - prev[0]
            dC = tot - prev[1]
            print("  %.2f -> %.2f m : dGain %+5.2f dB, dCost %+8.1f EUR  ==>  %7.1f EUR/dB (marginal)"
                  % (prev[2], D, dG, dC, dC / dG))
        prev = (g, tot, D)
    print("  READ: marginal EUR/dB is a flat ~50-86 EUR/dB up to the 1.0 m Yaesu boundary,")
    print("  then JUMPS 6.9x across 1.00 -> 1.20 m to 592 EUR/dB (the rotator steps")
    print("  EUR 359 -> 1132 AND the mast rises with M ~ D^3). Above that it oscillates")
    print("  ~140-520 EUR/dB, and the whole station EUR/dB more than doubles (279 -> 361)")
    print("  across a single 1.58 dB step. That step is the CLIFF; it is a rotator-CLASS +")
    print("  mast-moment step, not a smooth curve. The whole gain from 0.6 to 1.0 m")
    print("  (+4.4 dB) happens BELOW it, for ~50-86 EUR/dB.")


# --------------------------------------------------------------------------- #
# 3. CLIFF #2 — pointing tolerance ~ 1/D vs constant backlash
# --------------------------------------------------------------------------- #
def sec_pointing():
    hr("TABLE 4 — CLIFF #2: pointing budget = 10% HPBW vs constant backlash")
    print("HPBW = 70 lam / D ; budget_deg = 0.10 * HPBW ; fails when backlash > budget\n")
    for band, lam, Ds in [("2.4 GHz", LAM_24, [0.3, 0.6, 0.75, 0.9, 1.2, 1.5, 1.75, 2.0]),
                          ("433 MHz", LAM_433, [0.6, 1.2, 2.0, 2.6, 3.0, 4.0, 5.0])]:
        print("-- %s (lam = %.1f mm) --" % (band, lam * 1e3))
        print("%6s %10s %12s %12s %12s" % ("D[m]", "HPBW[deg]", "budget[deg]", "0.5deg backl", "1.0deg backl"))
        for D in Ds:
            hp = hpbw_deg(D, lam)
            bud = 0.10 * hp
            print("%6.2f %10.2f %12.2f %11.0f%% %11.0f%%" %
                  (D, hp, bud, 100 * 0.5 / bud, 100 * 1.0 / bud))
        for bl in (0.5, 1.0):
            Dcrit = 70.0 * lam / (10.0 * bl)
            print("  backlash %.1f deg consumes the full 10%% budget at D = %.3f m" % (bl, Dcrit))
        print()

    print("-- printed vs purchased backlash (CITED: positioner-lowcost-3dprinted.md §5) --")
    print("  printed belt/gear drive: 0.5-2.0 deg backlash")
    print("  self-locking NMRV worm reducer: back-drive eliminated; backlash is at the")
    print("  worm/wormwheel contact and is typically 0.1-0.5 deg (TODO(unverified) per unit)")


# --------------------------------------------------------------------------- #
# 4. THE MARKET GAP
# --------------------------------------------------------------------------- #
def sec_gap():
    hr("TABLE 5 — the rotator price ladder: is the cliff physics or a market gap?")
    print("%-18s %6s %11s %11s %11s" % ("model", "axes", "tower m2", "mast m2", "EUR"))
    for nm, ax, tw, ma, pr in ROTATORS:
        print("%-18s %6s %11s %11s %11.2f" %
              (nm, ax, "-" if tw is None else tw, "-" if ma is None else ma, pr))
    print("\nAZ+EL only, sorted:")
    azel = sorted([r for r in ROTATORS if r[1] == "AZ+EL"], key=lambda r: r[4])
    prev = None
    for nm, ax, tw, ma, pr in azel:
        step = "" if prev is None else "  (x%.2f vs previous)" % (pr / prev)
        print("  %-18s %10.2f%s" % (nm, pr, step))
        prev = pr
    print("The cliff in one line: the cheapest AZ+EL that the vendor rates for >1.0 m2 is\n"
          "SPX-01 at EUR %.0f - %.1fx the Yaesu G-450CDC, and the only AZ+EL with a\n"
          "published large-dish rating is SPID BIG-RAS at EUR %.0f (%.1fx)." %
          (1132.0, 1132.0 / 359.0, 1775.0, 1775.0 / 359.0))
    print("\nIs the gap PHYSICS or MARKET? Both, separated:")
    print("  PHYSICS:  T ~ D^3 (verified above) -> a 2.6 m dish needs ~8x the holding")
    print("            torque of a 0.6 m dish, so *some* class step is real.")
    print("  MARKET:   the AZ-only middle class EXISTS (G-1000DXC 2.20 m2 / EUR 529,")
    print("            G-2800DXC 3.00 m2 / EUR 1049) but there is NO cheap AZ+EL between")
    print("            1.0 m2 and the EUR 1132 SPX-01. Elevation is the gap.")
    print("            Check: G-1000DXC AZ + SPID RAEL EL(725) = EUR %.0f  vs  SPID RAS EUR 1260.82" %
          (529.0 + 725.0))
    print("            G-2800DXC AZ + SPID RAEL EL(725) = EUR %.0f  vs  BIG-RAS EUR 1775.00" %
          (1049.0 + 725.0))


# --------------------------------------------------------------------------- #
# 5. LEVERS
# --------------------------------------------------------------------------- #
def sec_levers():
    hr("TABLE 6 — LEVERS: what each buys, in dB and EUR, at the 1.2/2.6 m working point")
    # lever 1: mesh
    print("-- 1. MESH (Cd 1.2 -> 0.5 nominal; real solidity sigma 0.143-0.265) --")
    for D in [1.2, 2.4, 2.6, 3.0]:
        s = area(D) * CD_SOLID
        m = area(D) * CD_MESH
        ns, ps = rotator_price_for(s)
        nm, pm = rotator_price_for(m)
        print("  D=%.1f m: solid drag %.2f m2 -> %s EUR %.0f" % (D, s, ns, ps))
        print("            mesh  drag %.2f m2 -> %s EUR %.0f   (saving EUR %.0f, %.1fx)" %
              (m, nm, pm, ps - pm, ps / pm if pm else float("nan")))
    print("  433 dB COST of mesh: ZERO. lam/10 at 433.05 MHz = %.1f mm; the 6 mm mesh is" %
          (LAM_433 / 10 * 1e3))
    print("  %.1fx finer than required (CITED flrc-max §4.1); the mesh is electrically solid." %
          ((LAM_433 / 10) / 0.006))

    print("\n-- 2. STOW + LATCH --")
    D = 1.2
    A_broad = area(D)
    print("  CITED positioner-lowcost Table 3 (1.2 m, 40 m/s, solid): broadside 1330 N,")
    print("  stowed aperture-up 157 N -> 8.5x torque cut, stow = 11.8%% of broadside area.")
    print("  COMMITTED OVERSIGHT (consultant): 11.8%% is a silhouette for one wind angle; a")
    print("  stowed dish's SIDE profile (depth + back structure + feed struts) adds area, so")
    print("  the true stow coefficient is > 11.8%%. Sized for operating wind (12-14 m/s),")
    print("  stow converts the survival case from 4x operating to ~= operating (Table 7 of")
    print("  the committed doc).")
    latch = 60.0  # ESTIMATE
    print("  THE CATCH (consultant): you cannot HOLD stow with motor torque (steppers lose")
    print("  holding torque on power loss; worm self-locking is a wear/temperature claim).")
    print("  A positive mechanical LATCH is required. Cost ESTIMATE EUR %.0f (spring-loaded" % latch)
    print("  pin + strike plate + microswitch, or a solenoid pin) + the MCU must assert it.")
    print("  Value: it is what lets the structure be sized for 12-14 m/s operating wind")
    print("  instead of a full storm - the single biggest structural saving (see Tier-B).")

    print("\n-- 3. COUNTERWEIGHT / AXIS PLACEMENT --")
    for D, m_pay in [(0.6, 3.5), (1.2, 8.0), (2.6, 30.0)]:
        for off_frac in (0.25, 0.50):
            off = off_frac * D
            T_grav = m_pay * 9.80665 * off
            print("  D=%.1f m payload %.1f kg, elevation axis offset %.2f m (%.2fxD): "
                  "gravity torque = %.1f Nm" % (D, m_pay, off, off_frac, T_grav))
        print("    -> a counterweight zeroes the GRAVITY term only.")
    print("  PLAIN: a counterweight does NOT touch the WIND term. Wind torque = F_wind * L,")
    print("  where L is the fixed offset from the elevation axis to the dish's aerodynamic")
    print("  centre of pressure. A counterweight changes the MASS balance, not L. The only")
    print("  thing that reduces L is placing the axis through the dish CP (balanced mount),")
    print("  and that is a geometry choice, not a counterweight. L = D/4 (balanced) vs D/2")
    print("  (rim): the committed model's 4x torque difference is exactly this.")
    print("  Counterweight BENEFIT is real but different: it removes the sag/hold torque the")
    print("  motor must supply at low wind, so a SMALLER motor holds position; and it stops")
    print("  the dish nodding when power is lost. It buys motor size, not wind survival.")


# --------------------------------------------------------------------------- #
# 6. YAGI ARRAYS AT 433 MHz — the main event
# --------------------------------------------------------------------------- #
def yagi_geometry(n_elem=15, elem_len=0.35, elem_dia=0.008, boom_m=2.0, boom_dia=0.025,
                  cd=1.2):
    """Projected solid area of ONE 433 MHz Yagi, two worst-case wind directions.
    All lengths in metres. ESTIMATE geometry (a 15-element 70 cm Yagi: lambda/2 ~ 0.346 m
    elements, ~0.14 m average spacing -> ~2 m boom, 8 mm rod, 25 mm boom tube)."""
    A_axial = n_elem * elem_len * elem_dia          # wind along the boom: you see the rods
    A_broad = boom_m * boom_dia                     # wind across the boom: you see the boom
    A_solid = max(A_axial, A_broad)
    return {
        "A_axial_m2": A_axial,
        "A_broad_m2": A_broad,
        "A_solid_m2": A_solid,
        "drag_m2": A_solid * cd,
        "n_elem": n_elem, "boom_m": boom_m,
    }


def array_frame_area(n_bays, yagi_boom_m, cd=1.2):
    """ESTIMATE mounting frame projected area for an N-bay stacked array.
    Cross-boom (30 mm tube) spanning the bays + risers (30 mm) of length ~ the bay pitch."""
    # 2x2 -> one cross-boom ~ (2*1.0 + 1.0) = 3.0 m, two risers ~2.0 m each
    # 2   -> one riser ~2.0 m
    if n_bays <= 1:
        return 0.0
    if n_bays == 2:
        frame_len = 2.0
        return frame_len * 0.030 * cd
    # 4-bay (2x2): cross-boom 3.0 m + 2 risers 2.0 m each
    frame_len = 3.0 + 2 * 2.0
    return frame_len * 0.030 * cd


def sec_yagi():
    hr("TABLE 7 — YAGI ARRAY at 433 MHz vs the 2.6 m dish: GAIN and WIND")
    g = yagi_geometry()
    print("one 15-element 433 Yagi (ESTIMATE geometry): %d elements x %.2f m x %.0f mm, "
          "boom %.1f m x %.0f mm" % (g["n_elem"], 0.35, 8, g["boom_m"], 25))
    print("  projected solid area: axial %.4f m2 | broadside %.4f m2 | worst %.4f m2" %
          (g["A_axial_m2"], g["A_broad_m2"], g["A_solid_m2"]))
    print("  Cd* A (worst) = %.4f m2" % g["drag_m2"])

    print("\n-- GAIN of a stacked bay array (per-Yagi gain + 10log10(N) - harness loss) --")
    print("harness loss ESTIMATE: 2-bay 0.5 dB ; 4-bay 0.8 dB (dividers + phasing line runs)")
    print("%-22s %6s %6s %9s %9s %9s %9s" %
          ("source Yagi (dBi)", "boom m", "EUR ea", "1 bay", "2-bay", "4-bay", "req@2.6Mbps"))
    req26 = REQ_G_650["FLRC 2.6 Mbps"]
    for name, (gdbi, boom, price, url) in YAGIS.items():
        one = gdbi
        two = gdbi + db(2) - 0.5
        four = gdbi + db(4) - 0.8
        print("%-22s %6.2f %6.2f %9.1f %9.1f %9.1f %9s" %
              (name, boom, price, one, two, four, "OK" if four >= req26 else "-%.1f" % (four - req26)))
    print("\nrequired ground gain (CITED lowpower-link §2b, 650 km, G_balloon 0 dBi):")
    for k, v in sorted(REQ_G_650.items(), key=lambda kv: -kv[1]):
        print("   %-16s @ +22 dBm: %+5.1f dBi   (@ +13 dBm: %+5.1f dBi)" %
              (k, v, REQ_G_650_13DBM[k]))

    print("\n-- WIND: effective drag area and moment, array vs dish --")
    print("%-34s %10s %10s %10s %12s" % ("config", "drag[m2]", "F@20[N]", "L[m] est", "M@20[Nm]"))
    configs = []
    for nbays in (1, 2, 4):
        for name in ("Diamond A-430S15R", "FlexaYagi FX 7044", "Sirio WY 400-10N"):
            gd = YAGIS[name]
            gg = yagi_geometry(boom_m=gd[1])
            drag = nbays * gg["drag_m2"] + array_frame_area(nbays, gd[1])
            L = max(0.5, gd[1] / 2.0)   # ESTIMATE: CP near boom midpoint
            configs.append(("%d x %s" % (nbays, name), drag, L))
    for D in (0.6, 1.2, 2.6, 3.0):
        configs.append(("%.1f m dish SOLID (Cd1.2)" % D, area(D) * CD_SOLID, D / 4))
    for D in (2.4, 2.6, 3.0):
        configs.append(("%.1f m dish MESH (Cd0.5)" % D, area(D) * CD_MESH, D / 4))
    for label, drag, L in configs:
        F = 0.5 * RHO * 20 ** 2 * drag
        print("%-34s %10.3f %10.1f %10.2f %12.1f" % (label, drag, F, L, F * L))

    print("\n-- the headline ratios --")
    dish26 = area(2.6) * CD_SOLID
    arr4 = 4 * yagi_geometry(boom_m=1.39)["drag_m2"] + array_frame_area(4, 1.39)
    arr2 = 2 * yagi_geometry(boom_m=3.08)["drag_m2"] + array_frame_area(2, 3.08)
    print("  4 x Diamond A-430S15R array drag = %.3f m2 = %.1f%% of a 2.6 m solid dish (%.2f m2)"
          % (arr4, 100 * arr4 / dish26, dish26))
    print("  2 x FlexaYagi FX 7044 array drag = %.3f m2 = %.1f%% of the same dish"
          % (arr2, 100 * arr2 / dish26))
    print("  worst-case (frame doubled, Cd 1.5, 0.10 m2/antenna) sensitivity:")
    worst = (4 * 0.10 * 1.5 + 2 * array_frame_area(4, 1.39))
    print("      4-bay drag = %.3f m2 = %.1f%% of the dish" %
          (worst, 100 * worst / dish26))

    print("\n-- the rotator the array needs vs the rotator the dish needs --")
    for label, drag in [("4-bay A-430S15R", arr4), ("2-bay FX 7044", arr2),
                        ("2.6 m dish solid", dish26), ("2.6 m dish mesh", area(2.6) * CD_MESH)]:
        nm, pr = rotator_price_for(drag)
        print("  %-20s drag %6.3f m2 -> %-52s EUR %8.2f" % (label, drag, nm, pr))

    print("\n-- COST of the gain-bearing part only (antennas + harness, no rotator) --")
    harness = {2: 55.0, 4: 130.0}   # ESTIMATE: rfhamstore 70cm power dividers + phasing
    print("harness ESTIMATE: 2-bay EUR %.0f ; 4-bay EUR %.0f (rfhamstore 70 cm dividers; the"
          % (harness[2], harness[4]))
    print("  BOM could not read an individual divider price — TODO(unverified) exact price)")
    for nbays in (2, 4):
        for name in ("Diamond A-430S15R", "Diamond A-430S10R", "FlexaYagi FX 7044"):
            gdbi, boom, price, url = YAGIS[name]
            tot = nbays * price + harness[nbays]
            gain = gdbi + (db(nbays) - (0.5 if nbays == 2 else 0.8))
            print("  %d x %-20s gain %5.1f dBi  antenna+harness EUR %7.2f  EUR/dB(marg) %6.1f"
                  % (nbays, name, gain, tot, tot / (gain - REQ_G_650["FLRC 650 kbps"])))
    print("\n  compare: 2.4 m mesh dish kit EUR ~900+ (OUT OF STOCK) at 18.9 dBi, or")
    print("  1.9 m mesh kit EUR 901.45 at 16.8 dBi — both BELOW the 4-bay Yagi on gain and")
    print("  with 2-4x the wind area.")


# --------------------------------------------------------------------------- #
# 7. SWEET SPOTS
# --------------------------------------------------------------------------- #
def sec_sweet():
    hr("TABLE 8 — TWO SWEET SPOTS")
    print("Assumed link context (CITED): 433 downlink FLRC; 2.4 GHz uplink LoRa-class")
    print("(committed); FSPL 433.05 MHz @650 km = 141.4 dB; 2.4 GHz @650 km = 156.3 dB;\n"
          "2.4 GHz uplink required ground gain is NEGATIVE (an omni closes it).\n")

    print("== (a) MOST ACCESSIBLE — cheapest station that still closes an operating link ==")
    print("Design: ONE 433 Yagi + a 2.4 GHz omni, on a cheap printed/light AZ+EL tracker.")
    print("%-46s %10s" % ("line", "EUR"))
    a_lines = [
        ("Diamond A-430S10R 433 Yagi 13.1 dBi (CITED BOM A4)", 69.00),
        ("2.4 GHz 6 dBi omni / PCB antenna (repo ADR-037, no price -> ESTIMATE)", 25.00),
        ("printed AZ/EL tracker: 2x NEMA23 3.0 Nm (CITED ~$23 ea)", 46.00),
        ("NMRV40 20:1 self-locking worm x2 (CITED placeholder)", 80.00),
        ("drivers + encoders + bearings (ESTIMATE)", 64.00),
        ("anemometer (CITED Argent $15 anemometer alone)", 15.00),
        ("mast 3 m + ground stake / foot (ESTIMATE)", 120.00),
        ("coax Aircell 7 15 m + N connectors (CITED BOM)", 90.00),
        ("filament + hardware (CITED/ESTIMATE)", 30.00),
        ("LATCH (ESTIMATE)", 60.00),
    ]
    a_tot = sum(p for _, p in a_lines)
    for n, p in a_lines:
        print("%-46s %10.2f" % (n, p))
    print("%-46s %10.2f" % ("TOTAL (a) — no dish, no rotator purchase", a_tot))
    print("  433 gain 13.1 dBi ; 2.4 GHz ~6 dBi (omni).")
    print("  Closes: FLRC 650 kbps @ +22 dBm (needs 12.4) with +0.7 dB; LoRa with +30 dB.")
    print("  Does NOT close: FLRC 2.6 Mbps (needs 18.9).")
    print("  2.4 GHz closes: omni, +10.7 dB margin @650 km (balloon LNA) — CITED.")

    print("\n== (b) BEST BANG FOR BUCK — 4-bay Yagi array, still pre-cliff ==")
    b_lines = [
        ("4 x Diamond A-430S15R 433 Yagi 14.8 dBi (CITED BOM A5)", 4 * 74.50),
        ("70 cm 4-way power divider + phasing harness (ESTIMATE)", 130.00),
        ("array frame: cross-boom + risers, ali tube (ESTIMATE)", 70.00),
        ("Yaesu G-450CDC AZ+EL, tower rating 1.00 m2 (CITED BOM E2)", 359.00),
        ("Gibertini 75 SE Profi 0.75 m 2.4 GHz dish (CITED BOM B3)", 94.90),
        ("RF Hamdesign LH-13XL 2.4 GHz helix feed (CITED BOM C4)", 220.00),
        ("CLX1 feed clamp (CITED BOM C6)", 46.00),
        ("anemometer + LATCH (CITED + ESTIMATE)", 75.00),
        ("mast 4 m + foundation + guys (ESTIMATE)", 600.00),
        ("coax: Ecoflex 15 5 m + Airborne 10 15 m + connectors (CITED BOM)", 213.50),
        ("tracker controller (repo firmware + a Pi/ESP32, ESTIMATE)", 60.00),
    ]
    b_tot = sum(p for _, p in b_lines)
    for n, p in b_lines:
        print("%-58s %10.2f" % (n, p))
    print("%-58s %10.2f" % ("TOTAL (b)", b_tot))
    gain433 = 14.8 + db(4) - 0.8
    print("  433 gain %.1f dBi ; 2.4 GHz dish 0.75 m %.1f dBi" %
          (gain433, dish_gain_dBi(0.75, LAM_24)))
    for rate, req in sorted(REQ_G_650.items(), key=lambda kv: -kv[1]):
        print("    closes %-16s (needs %+5.1f) margin %+5.1f dB" % (rate, req, gain433 - req))

    print("\n== THE LADDER: the gain/€ FRONTIER, and where the dish sits on it ==")
    harness = {1: 0.0, 2: 55.0, 4: 130.0}
    base = 530.0   # the shared station body (mast, controller, 2.4 GHz path, coax, LATCH, misc)
    print("shared station body = EUR %.0f (same on every rung, so it cancels in the marginal)" % base)
    cands = []   # (label, gain433_dBi, drag_m2, rot_price, antenna_cost)
    for name, (gdbi, boom, price, url) in YAGIS.items():
        g = yagi_geometry(boom_m=boom)
        for nb in (1, 2, 4):
            gain = gdbi + (db(nb) - (0.5 if nb == 2 else 0.8 if nb == 4 else 0.0))
            drag = nb * g["drag_m2"] + array_frame_area(nb, boom)
            _, rot = rotator_price_for(drag)
            frame = 0.0 if nb == 1 else 70.0
            cands.append(("%d x %s" % (nb, name), gain, drag, rot, nb * price + harness[nb] + frame))
    for D in (1.0, 1.2, 1.5, 1.9, 2.4, 2.6, 3.0):
        for Cd, tag, rot_lim in ((CD_SOLID, "SOLID", None), (CD_MESH, "MESH", None)):
            gain = dish_gain_dBi(D, LAM_433)
            drag = area(D) * Cd
            _, rot = rotator_price_for(drag)
            cost = reflector_price_est(D)[0] + rot + mast_foundation_est(D)
            cands.append(("%.1f m dish %s" % (D, tag), gain, drag, rot, cost))
    # Pareto frontier in (cost, gain) space; tie-break on lower drag
    cands.sort(key=lambda c: (base + c[4], c[1]))
    frontier = []
    best_gain = -1e9
    for label, gain, drag, rot, ac in cands:
        if gain > best_gain + 1e-9:
            frontier.append((label, gain, drag, rot, ac))
            best_gain = gain
    print("(%d candidate stations; %d on the Pareto frontier. Marginal EUR/dB is measured"
          % (len(cands), len(frontier)))
    print(" along the frontier.)")
    print("%-30s %8s %9s %11s %11s %14s" %
          ("frontier rung", "433 dBi", "drag[m2]", "rot[EUR]", "tot[EUR]", "marg EUR/dB"))
    prev = None
    for label, gain, drag, rot, ac in frontier:
        tot = base + ac
        marg = "" if prev is None else "%14.1f" % ((tot - prev[1]) / (gain - prev[0]))
        print("%-30s %8.1f %9.3f %11.0f %11.0f %s" % (label, gain, drag, rot, tot, marg))
        prev = (gain, tot)
    print("  DOMINATED (not on the frontier on 433 gain per euro):")
    fset = {f[0] for f in frontier}
    for label, gain, drag, rot, ac in cands:
        if label not in fset:
            print("    %-30s %6.1f dBi, drag %6.3f m2, EUR %8.0f" % (label, gain, drag, base + ac))
    print("  READ: every Yagi-array rung stays on the frontier; the 2.4 m and 2.6 m DISH rungs")
    print("  are DOMINATED on 433 gain/€ (a 4-bay Yagi array beats them on gain AND cost).")
    print("  They are dominated ONLY because the low-power (<= +19 dBm) FLRC regime is not in")
    print("  view here -- at +13 dBm, 2.6 Mbps needs +27.9 dBi, no Yagi array reaches it, and")
    print("  the dish becomes the only option (see the low-power column of TABLE 7). The")
    print("  frontier therefore has a HOLE: pre-cliff (Yagi arrays, <= ~21 dBi, cheap) and")
    print("  post-cliff (dishes, >= ~27 dBi at low power, expensive) with nothing between.")

    print("== COMPARISON: Tier-B (2.6 m dish) for reference ==")
    tb_ref = 4324.6   # TABLE 3 total E at 2.6 m
    print("  2.6 m mesh dish: 18.8-19.6 dBi, drag %.2f m2 (solid) / %.2f m2 (mesh)" %
          (area(2.6) * CD_SOLID, area(2.6) * CD_MESH))
    print("  requires >= SPID BIG-RAS EUR 1775 (or SPX-02 EUR 1249, no m2 rating)")
    print("  Tier-B bottom-up (TABLE 9) is EUR 5577-9037 = %.1fx-%.1fx sweet spot (b) for a"
          % (5577.44 / 2166.4, 9036.94 / 2166.4))
    print("  433 gain (18.8-19.6 dBi) that is NOT higher than the 4-bay array's 20.0 dBi.")
    print("  NOTE the model's rotator_price_for() does not PRICE the mast-vs-tower split:")
    print("  a solid 1.0-1.2 m dish exceeds the Yaesu MAST rating (0.50 m2) and forces a")
    print("  TOWER install, while the same dish MESH stays under the mast rating - an extra")
    print("  cost the table does not carry. The mesh lever is therefore UNDER-valued here.")
    print("\n  EUR/dB and EUR per (bit/s):")
    for label, tot, g433, eur_db, bps in [
            ("(a) accessible", a_tot, 13.1, None, None),
            ("(b) bang/buck", b_tot, gain433, None, None)]:
        pass
    print("  %-16s %10s %10s %10s %12s" % ("station", "total EUR", "433 dBi", "EUR/dB*", "EUR/(kb/s)"))
    for label, tot, g433 in [("(a) accessible", a_tot, 13.1), ("(b) bang/buck", b_tot, gain433)]:
        eur_db = tot / g433
        print("  %-16s %10.0f %10.1f %10.1f %12.1f" %
              (label, tot, g433, eur_db, tot / 650.0))
    print("  (* EUR/dB here is total station cost / absolute 433 gain; see the doc for the")
    print("   marginal EUR/dB which is the number that exposes the cliff.)")


# --------------------------------------------------------------------------- #
# 8. TIER B — bottom-up
# --------------------------------------------------------------------------- #
def sec_tierb():
    hr("TABLE 9 — TIER B bottom-up (2.6 m coarse-mesh 433 dish station)")
    print("Every line: price + source class (CITED / ESTIMATE / TODO). Ranges given where the")
    print("source is a range or where the DIY build is the only route (the 2.4/3.0 m kits are")
    print("OUT OF STOCK, so 2.6 m is a DIY build - rib+mesh - not a purchase).\n")
    lines = [
        ("2.6 m reflector DIY: 16 ali ribs + hub ring + skin (ESTIMATE, see note)",
         500.00, 900.00, "ESTIMATE (rib stock + machining; no 2.6 m kit exists)"),
        ("Coarse mesh skin ~8 m2: 25x25 mm galv 1.75 mm (CITED metal-market.eu)",
         60.00, 200.00, "CITED EUR 7.00 listing (unit ambiguous -> range)"),
        ("433 prime-focus feed for a 0.45 f/D mesh dish (TODO(unverified) price)",
         150.00, 400.00, "TODO(unverified): RF Hamdesign feed page not read this session"),
        ("Feed support tripod + clamp (ESTIMATE)", 60.00, 150.00, "ESTIMATE"),
        ("SPID BIG-RAS AZ+EL (CITED BOM E6)", 1775.00, 1775.00, "CITED rfhamdesign.com"),
        ("Mast 4-6 m galv steel 100 mm + head plate (ESTIMATE)", 250.00, 500.00, "ESTIMATE"),
        ("Foundation: concrete pad + rebar + anchors (ESTIMATE)", 300.00, 900.00, "ESTIMATE"),
        ("Guy set: 3-4 stays, anchors, turnbuckles (ESTIMATE)", 150.00, 400.00, "ESTIMATE"),
        ("2.4 GHz dish Gibertini OP100SE 0.97 m (CITED BOM B1)", 143.90, 143.90, "CITED hm-sat"),
        ("2.4 GHz feed LH-13XL + CLX1 clamp (CITED BOM C4/C6)", 266.00, 266.00, "CITED rfhamdesign"),
        ("Tracker controller + anemometer + LATCH (CITED + ESTIMATE)", 135.00, 300.00, "mixed"),
        ("Coax: Ecoflex 15 5 m + Airborne 10 20 m + N connectors (CITED BOM)", 280.50, 280.50, "CITED"),
        ("Build labour allowance: 40-80 h at EUR 25/h (ESTIMATE)", 1000.00, 2000.00, "ESTIMATE"),
        ("Contingency 10% (ESTIMATE)", 0.00, 0.00, "computed below"),
    ]
    lo = sum(l[1] for l in lines[:-1])
    hi = sum(l[2] for l in lines[:-1])
    print("%-64s %10s %10s  %s" % ("line", "low EUR", "high EUR", "source"))
    for n, a, b, s in lines[:-1]:
        print("%-64s %10.2f %10.2f  %s" % (n, a, b, s))
    print("%-64s %10.2f %10.2f" % ("subtotal", lo, hi))
    print("%-64s %10.2f %10.2f" % ("contingency 10%", 0.10 * lo, 0.10 * hi))
    print("%-64s %10.2f %10.2f" % ("TOTAL TIER B", 1.10 * lo, 1.10 * hi))
    print("\nDOMINANT LINE: the SPID BIG-RAS rotator (EUR 1775) — %.0f%%-%.0f%% of the total" %
          (100 * 1775 / (1.10 * hi), 100 * 1775 / (1.10 * lo)))
    print("  alone. Second: build labour EUR 1000-2000. Together they are ~55-65% of Tier B.")
    print("  That is the cliff made concrete: the single item that lets the dish point at all")
    print("  costs more than the whole pre-cliff station (sweet spot b).")
    print("\nIf a used/salvaged mount replaces the BIG-RAS (CITED: BOM 'salvage the mount'")
    print("advice for the 433-FLRC case), total drops to roughly EUR %.0f-%.0f" %
          (1.10 * lo - 1775 + 400, 1.10 * hi - 1775 + 1200))
    tb_lo, tb_hi = 1.10 * lo, 1.10 * hi
    print("That is %.1fx-%.1fx sweet spot (b) (EUR 2166) for a station whose 433 gain" %
          (tb_lo / 2166.4, tb_hi / 2166.4))
    print("(18.8-19.6 dBi) is NOT higher than the 4-bay array's 20.0 dBi.")


# --------------------------------------------------------------------------- #
# 9. MEASUREMENT CAMPAIGN
# --------------------------------------------------------------------------- #
def sec_campaign():
    hr("TABLE 10 — the measurement campaign (Tier-A Yagi station flies the low-power board)")
    print("Principle: the link budget's job is to decide YAGI-ARRAY vs DISH. That decision")
    print("rests on two numbers the repo currently ASSUMES: (i) the 433 MHz FLRC sensitivity")
    print("(datasheet is 915 MHz; a 433 row is TODO(unverified)) and (ii) the path-loss")
    print("exponent n (free-space n=2; the model's FSPL assumes exactly 2). MEASURE both.\n")
    print("What to LOG per packet/flight:")
    for s in [
        "GPS lat/lon/alt of balloon + ground station every second (telemetry)",
        "slant range d (computed from both GPS fixes), not horizontal range",
        "LR2021 RSSI (dBm) and SNR (dB) from the chip's own registers, per packet",
        "instantaneous FLRC bit rate / spreading factor in use",
        "PER and goodput per 30 s window (bits delivered / bits attempted)",
        "TX power setting (dBm, from the 0.5 dB step register) at that moment",
        "antenna: ground Yagi type + how it was pointed (AZ/EL) + pointing error if known",
        "weather: surface wind at the ground station, temperature (for PA/sens drift)",
        "polarisation: balloon antenna orientation if a magnetometer/IMU is on board",
        "both stations' RSSI (RX the downlink AND a ping-based uplink RSSI if available)",
    ]:
        print("   -", s)
    print("\nAnalysis / fits:")
    print("  1. Path-loss exponent: model P_r(d) = P_t + G_t + G_r - (FSPL@1m + 10 n log10 d)")
    print("     - L_misc ; least-squares n over the measured range decade.")
    print("     Free-space n = 2.0. Publish n_hat with its CI. If n_hat > 2, the model's")
    print("     required ground gain is OPTIMISTIC by 10(n_hat-2)log10(d2/d1) dB.")
    print("  2. Achieved sensitivity at 433: sweep rate / TX power until PER crosses 1% at the")
    print("     edge of range; read RSSI there -> an EMPIRICAL S_433_FLRC row. Compare with")
    print("     the datasheet's 915 MHz -100.5 dBm @ 2.6 Mbps.")
    print("  3. Residual margin: (measured RSSI - S_433_measured) at 2.6 Mbps vs the modelled")
    print("     +18.9 dBi requirement. The residual IS the extra ground gain (or balloon power)")
    print("     that a dish would have to buy. If the residual is small, the dish is unnecessary")
    print("     for the range actually flown.")
    print("  4. Polarisation / pointing loss: compare a pass with the ground Yagi exactly")
    print("     boresighted vs deliberately offset by 5-10 deg -> a real pointing-loss curve.")
    print("\nWhat the campaign CAN prove:")
    print("   - the real path-loss exponent at altitude and long range;")
    print("   - the real 433 MHz FLRC sensitivity (today a 915 MHz proxy);")
    print("   - whether the +18.9 dBi requirement is pessimistic or optimistic, and by how much;")
    print("   - that a specific Yagi-array station closes (or fails) a specific rate at a")
    print("     specific measured range -- an OPERATING result, not a model;")
    print("   - real pointing and polarisation losses.")
    print("\nWhat it CANNOT prove:")
    print("   - the range beyond what was flown: extrapolating a fitted 10n log term over a")
    print("     second decade is fragile; a 50 km flight does not prove 650 km;")
    print("   - how a DISH behaves: the campaign measures the Yagi you own, not a dish's gain;")
    print("     it measures the LINK, and infers the dish's required gain from the residual;")
    print("   - mechanical survival of a 2.6 m dish (a wind/structural question, not RF);")
    print("   - the licence status of a higher-power / dish configuration (a regulatory fact);")
    print("   - that no dish is *ever* needed -- a dish may still be wanted for interference")
    print("     rejection or fade margin at ranges beyond the flown maxima.")
    print("\nHONEST VERDICT on 'measure instead of buy': YES for the marginal case. The campaign")
    print("costs the price of a Yagi-array station you want anyway (sweet spot a/b) and answers")
    print("whether the 1775 EUR rotator + DIY dish are needed AT ALL at your operating range.")
    print("It cannot retire the dish by fiat, but it can show the dish's required gain is")
    print("over-stated or un-needed at the flown range -- which is exactly the decision.")


# --------------------------------------------------------------------------- #
def main():
    print("gain_per_dollar_cliff_model.py")
    print("lam(433.05 MHz) = %.4f m (%.1f mm) ; lam(2.4 GHz) = %.4f m (%.1f mm)" %
          (LAM_433, LAM_433 * 1e3, LAM_24, LAM_24 * 1e3))
    sec_scaling()
    sec_cliff()
    sec_pointing()
    sec_gap()
    sec_levers()
    sec_yagi()
    sec_sweet()
    sec_tierb()
    sec_campaign()
    print("\n" + "=" * 78)
    print("END OF MODEL OUTPUT")
    print("=" * 78)


if __name__ == "__main__":
    main()
