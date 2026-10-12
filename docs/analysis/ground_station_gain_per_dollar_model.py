#!/usr/bin/env python3
"""
Gain-per-dollar / link-budget-per-dollar model for the balloon ground station.

Prints every numeric table in
  docs/analysis/ground-station-gain-per-dollar.md

Rules
-----
* NO price, gain or datasheet value is invented here. Every constant carries its
  provenance in PROV / the candidate tuples; anything unsourced is marked
  TODO(unverified) in the markdown and is never fed into a conclusion as if sourced.
* The candidate table is the OUTPUT of this script, so the comparison in the
  markdown is reproducible with one command.

Run:  python3 docs/analysis/ground_station_gain_per_dollar_model.py
"""

from __future__ import annotations
import math

# --------------------------------------------------------------------------
# PROVENANCE
# --------------------------------------------------------------------------
PROV = {
    "S_FLRC_2600": (-100.5, "Semtech LR2021 datasheet Table 3-12, sub-GHz FLRC 1% PER @915 MHz"),
    "S_FLRC_1040": (-105.0, "same, FLRC_1040_CR05"),
    "S_FLRC_650":  (-107.0, "same, FLRC_650_CR05"),
    "S_LORA_62":   (-143.0, "Semtech Table 3-17 LORA_SUB_62_SF12 (also NiceRF V1.3 module)"),
    "P_chip_max":  (22.0, "Semtech Table 3-22 TXOPLF typ (sub-GHz PA)"),
    "P_le":        (12.15, "ADR-039/041: 10 mW ERP integral antenna = +10 dBm ERP = +12.15 dBm EIRP"),
    "P_F33":       (33.0, "NiceRF LoRa2021F33-2G4 module +33 dBm (docs/F33-MODULE-PLAN.md)"),
}

LAMBDA = 0.69233          # m, 433.05 MHz (COMPUTED)
FSPL_CONST = 25.18        # dB, 20*log10(4*pi/lambda) (COMPUTED)
G_BALLOON = 0.0           # dBi, conservative (docs/LINK-BUDGET-LICENCE-EXEMPT.md)
L_IMPL = 2.6              # dB, coax+connectors+polarisation+pointing (ESTIMATE, see markdown)
FADE_MARGIN = 6.0         # dB, stated operating margin (ESTIMATE)

# LoRa SF12 / BW 62.5 kHz effective bit rate:
#   sym_rate = BW/2^SF = 62500/4096 = 15.259 sym/s ; bits/sym = SF = 12 ;
#   CR 4/5 -> *0.8  => 146.5 bit/s
LORA_KBPS = 0.1465

# --------------------------------------------------------------------------
# Link equation
# --------------------------------------------------------------------------
def d_max_km(G_ground_dbi: float, S_dbm: float, P_tx_dbm: float,
             margin_db: float = FADE_MARGIN) -> float:
    budget = P_tx_dbm + G_BALLOON + G_ground_dbi - S_dbm - L_IMPL - margin_db
    return 10.0 ** ((budget - FSPL_CONST) / 20.0) / 1000.0


def dish_gain_dbi(D_m: float, eta: float = 0.65) -> float:
    """G = 10*log10(eta*(pi*D/lambda)^2); eta=0.65 is RF Hamdesign's OWN published
    dish efficiency (verified against their 1296/2320 MHz tables, flrc-max §5.1)."""
    return 10.0 * math.log10(eta * (math.pi * D_m / LAMBDA) ** 2)


# --------------------------------------------------------------------------
# WIND / TORQUE classing  (stow-on-wind policy: size for 20 m/s, park for storms)
#   q = 0.5*rho*v^2 ; F = q*A*Cd ; M = F*(D/4) ; require hold >= 1.5*M
#   Cd_solid = 1.38 (DERIVED from Gibertini OP100SE 91 kg @120 km/h over 0.949 m2)
#   mesh 6 mm: sigma = 0.265 (flrc-max §4.2) -> F_mesh = F_solid * sigma  (the
#   same sigma-proportional permeability model the prior art used)
# --------------------------------------------------------------------------
RHO = 1.225
CD_SOLID = 1.38
SIGMA_MESH = 0.265
V_OP = 20.0     # m/s operating wind the structure is sized for
SF_HOLD = 1.5   # holding safety factor on the operating moment


def wind_moment_Nm(D_m: float, solid: bool, v: float = V_OP) -> float:
    A = math.pi * D_m ** 2 / 4.0
    F = 0.5 * RHO * v ** 2 * A * CD_SOLID
    if not solid:
        F *= SIGMA_MESH
    return F * (D_m / 4.0)


def yagi_wind_moment_Nm(boom_m: float, v: float = V_OP,
                        A_eff: float = 0.15, CD_lattice: float = 1.2) -> float:
    """Yagi wind moment. A_eff = 0.15 m2 is an ESTIMATE of the projected
    element+lattice area of a 70 cm Yagi (TODO(unverified): no vendor wind
    figure exists for these Yagis); the lever arm is boom/2 (centroid)."""
    F = 0.5 * RHO * v ** 2 * A_eff * CD_lattice
    return F * (boom_m / 2.0)


def eff_area_m2(D_m: float, solid: bool) -> float:
    A = math.pi * D_m ** 2 / 4.0
    return A if solid else A * SIGMA_MESH


# --------------------------------------------------------------------------
# POSITIONER MENU (sourced) and the assignment rule
#  RULE: pick the cheapest menu entry that passes EITHER
#    (a) the vendor's published wind AREA rating  A_eff <= area, OR
#    (b) the holding-torque test                hold >= SF_HOLD * M20.
#  The Yaesu figure used is the CONSERVATIVE MAST rating (0.50 m2); a tower
#  raises it to 1.00 m2 (bom-candidates §5). SPX-01 is left OUT of the menu
#  because its paper rating is TODO(unverified) - noted in the markdown only,
#  so no invented rating enters the table.
# --------------------------------------------------------------------------
# (key, label, eur, kind, area_m2(or None), hold_Nm(or None), source)
POS_MENU = [
    ("P1", "DIY NEMA23+NMRV40 20:1 (printed yoke)", 429.00, "torque", None, 40.0,
     "positioner-lowcost §10 (EUR279 mech + EUR50 ctrl + EUR100 mast) + StepperOnline NMRV40 20:1 = 40 N.m"),
    ("P2", "DIY uprated NEMA34+NMRV50 30:1",         509.00, "torque", None, 67.5,
     "same list, NEMA34 8.2 N.m + NMRV50 30:1 = 67.5 N.m (positioner-lowcost Table 5)"),
    ("P3", "Yaesu G-5500DC (AZ+EL, MAST 0.50 m2)",   949.00, "area", 0.50, None,
     "funktechnik-bielefeld.de price; DXE wind 1.00 m2 tower / 0.50 m2 mast"),
    ("P5", "SPID BIG-RAS (AZ+EL)",                  1775.00, "torque", None, 2712.0,
     "hold/brake 2712 N.m, turning 500 N.m (spid-bigras-specifications.pdf)"),
    ("P6", "SPX-06 slew drive (AZ+EL)",             5487.35, "torque", None, 716.0,
     "716 N.m rated, IP65, absolute encoders, 0.1 deg (price list)"),
]


def assign_positioner_from_moment(M, A):
    """cheapest (key,label,eur,hold,M,A) that passes the area OR the torque test."""
    for key, label, eur, kind, area, hold, src in POS_MENU:
        if kind == "area" and area is not None and A <= area:
            return key, label, eur, hold or float("nan"), M, A
        if kind == "torque" and hold is not None and hold >= SF_HOLD * M:
            return key, label, eur, hold, M, A
    return "NONE", "NO sourced AZ+EL positioner holds this", float("inf"), float("nan"), M, A


def assign_positioner(D_m, solid):
    return assign_positioner_from_moment(wind_moment_Nm(D_m, solid), eff_area_m2(D_m, solid))


def assign_positioner_yagi(boom_m):
    return assign_positioner_from_moment(yagi_wind_moment_Nm(boom_m), 0.15)


# coax + mast + build allowance
COAX_TOTAL = 97.50 + 24.00      # 15 m Airborne 10 @ EUR6.50/m + 8 N/SMA connectors
MAST = 100.00                   # ESTIMATE (mast + base) - INCLUDED inside P1/P2 DIY line
BUILD_ALLOWANCE = 30.00         # ESTIMATE: brackets, bolts, paint, misc
DIY_FEED = 50.00                # ESTIMATE: 433 MHz prime-focus feed (no vendor sells one)


def row(label, kind, g, antenna_eur, feed_eur, pos):
    key, plabel, peur, hold, M, A = pos
    total = antenna_eur + feed_eur + peur + COAX_TOTAL + BUILD_ALLOWANCE
    return dict(label=label, kind=kind, g=g, ant=antenna_eur, feed=feed_eur,
                poskey=key, pos=plabel, peur=peur, total=total, hold=hold, M=M, Aeff=A)


def yagi(label, g, price, boom_m):
    return row(label, "Yagi", g, price, 0.0, assign_positioner_yagi(boom_m))


def dsh(label, D, price, mesh=True):
    pos = assign_positioner(D, not mesh)
    return row(label, f"dish {D:.2f} m {'mesh' if mesh else 'solid'}",
               dish_gain_dbi(D), price, DIY_FEED, pos)


CANDIDATES = [
    # --- Yagis (gain/price: ground-station-bom-candidates.md §0.1/§1) -------
    yagi("Diamond A-430S10R 10el",  13.1,  69.00, 0.82),
    yagi("Diamond A-430S15R 15el",  14.8,  74.50, 1.39),
    yagi("Sirio WY 400-6N 6el",     11.0, 132.00, 1.20),
    yagi("Sirio WY 400-10N 10el",   14.0, 155.00, 2.00),
    yagi("FlexaYagi FX 7015V",      12.4, 125.00, 1.19),
    yagi("FlexaYagi FX 7044",       16.6, 164.00, 3.08),
    yagi("FlexaYagi FX 7073",       18.0, 215.00, 5.07),
    yagi("2x Sirio WY 400-10N stacked", 17.0, 310.00, 2.00),
    # --- Dishes (kit price: RF Hamdesign Oct-2026 list; gain: computed eta 0.65)
    dsh("0.90 m SOLID (Gibertini 85 SE)", 0.90, 104.90, mesh=False),
    dsh("0.90 m mesh (same dish, meshed)", 0.90, 154.90),
    dsh("1.20 m mesh (RFH FPD 1M2)",      1.20, 387.20),
    dsh("1.50 m mesh (RFH FPD 1M5)",      1.50, 499.73),
    dsh("1.90 m mesh (RFH FPD 1M9)",      1.90, 901.45),
    dsh("2.40 m mesh (DIY, frame TODO)",  2.40, 1000.00),
    dsh("2.60 m mesh (DIY, frame TODO)",  2.60, 1100.00),
    dsh("3.00 m mesh (DIY, frame TODO)",  3.00, 1400.00),
    dsh("3.50 m mesh (DIY, frame TODO)",  3.50, 1700.00),
    dsh("2.40 m SOLID (DIY)",             2.40, 1000.00, mesh=False),
]


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
def best_capability(g, P_tx):
    """best (rate_kbps, d_km, Q=kbps*km, rate_name) over the FLRC ladder."""
    best = None
    for name, (S, _src), kbps in [("FLRC 2.6 Mbps", PROV["S_FLRC_2600"], 2600),
                                  ("FLRC 1.04 Mbps", PROV["S_FLRC_1040"], 1040),
                                  ("FLRC 650 kbps", PROV["S_FLRC_650"], 650)]:
        d = d_max_km(g, S, P_tx)
        q = kbps * d
        if best is None or q > best[2]:
            best = (kbps, d, q, name)
    return best


def table(P_tx, title):
    print("=" * 130)
    print(f"{title}   (P_tx={P_tx:+.2f} dBm, G_balloon={G_BALLOON:.0f} dBi, margin={FADE_MARGIN:.0f} dB)")
    print("=" * 130)
    hdr = (f"{'candidate':32s} {'G433':>6s} {'ant€':>8s} {'pos€':>8s} {'tot€':>8s} "
           f"{'€/dB':>6s} {'M20 Nm':>7s} {'best':>10s} {'d_km':>7s} {'Q kbps·km':>11s} "
           f"{'€/(kbps·km)':>12s} {'€/km@650':>9s} {'d_LoRa km':>10s}")
    print(hdr); print("-" * len(hdr))
    out = []
    for c in CANDIDATES:
        g, tot = c["g"], c["total"]
        kbps, d, q, rname = best_capability(g, P_tx)
        d650 = d_max_km(g, PROV["S_FLRC_650"][0], P_tx)
        dlor = d_max_km(g, PROV["S_LORA_62"][0], P_tx)
        m1 = tot / g
        m2 = tot / q if q > 0 else float("inf")
        m3 = tot / d650 if d650 > 0 else float("inf")
        print(f"{c['label']:32s} {g:6.2f} {c['ant']:8.2f} {c['peur']:8.2f} {tot:8.2f} "
              f"{m1:6.1f} {c['M']:7.1f} {rname:>10s} {d:7.1f} {q:11.0f} "
              f"{m2:12.4f} {m3:9.1f} {dlor:10.0f}")
        out.append((c, m1, m2, m3, dlor, q, d))
    print()
    return out


def monotonicity(P_tx):
    print("=" * 112)
    print("NON-MONOTONICITY of the dish ladder: marginal EUR per dB "
          "(positioner class jumps included)")
    print("=" * 112)
    print(f"{'rung':34s} {'G433':>6s} {'tot€':>8s} {'€/dB avg':>9s} {'pos€':>8s} "
          f"{'dG':>5s} {'d€':>8s} {'marginal €/dB':>14s}")
    print("-" * 112)
    prev = None
    for c in CANDIDATES:
        g, tot = c["g"], c["total"]
        marg = ""
        if prev:
            dg = g - prev[0]
            de = tot - prev[1]
            marg = f"{de/dg:14.1f}" if dg else "  (same G)"
        print(f"{c['label']:34s} {g:6.2f} {tot:8.2f} {tot/g:9.1f} {c['peur']:8.2f} "
              f"{'':>5s} {'':>8s} {marg}")
        prev = (g, tot)
    print()


def pos_class_table():
    print("=" * 118)
    print("WIND/TORQUE CLASSIFICATION and the positioner the assignment rule picks "
          f"(V_OP={V_OP:.0f} m/s, SF={SF_HOLD})")
    print("=" * 118)
    print(f"{'candidate':32s} {'kind':12s} {'A_eff m2':>9s} {'M20 N.m':>8s} "
          f"{'1.5xM20':>8s} | {'picked positioner':38s} {'€':>8s} {'hold N.m':>9s}")
    print("-" * 118)
    for c in CANDIDATES:
        print(f"{c['label']:32s} {c['kind']:12s} {c['Aeff']:9.3f} {c['M']:8.1f} "
              f"{SF_HOLD*c['M']:8.1f} | {c['pos']:38s} {c['peur']:8.2f} {c['hold']:9.1f}")
    print()


def marginal_table(P_tx):
    """THE DECISION-RELEVANT VIEW: the 433 side shares the positioner with the
    2.4 GHz uplink, which needs only a 0.6-0.75 m dish (positioner-lowcost §3).
    So the baseline rig already pays for a DIY P1 tracker (EUR429). The marginal
    433 cost is the antenna + its 433 feed + any POSITIONER UPGRADE over P1."""
    BASE = POS_MENU[0][2]   # EUR429 DIY P1, already paid for the 2.4 GHz side
    print("=" * 122)
    print("D. MARGINAL 433 cost over a SHARED rig (2.4 GHz uplink already pays for the "
          "DIY P1 tracker)")
    print(f"   baseline positioner = EUR{BASE:.0f}; marginal = antenna + 433 feed + "
          f"positioner upgrade.  P_tx={P_tx:+.2f} dBm")
    print("=" * 122)
    hdr = (f"{'candidate':32s} {'G433':>6s} {'ant+feed€':>10s} {'pos up€':>8s} "
           f"{'marg€':>8s} {'d_km':>7s} {'Q kbps·km':>11s} {'€/dB marg':>10s} "
           f"{'€/(kbps·km) marg':>18s}")
    print(hdr); print("-" * len(hdr))
    for c in CANDIDATES:
        g = c["g"]
        marg = c["ant"] + c["feed"] + max(0.0, c["peur"] - BASE)
        kbps, d, q, rname = best_capability(g, P_tx)
        m1 = marg / g
        m2 = marg / q if q > 0 else float("inf")
        print(f"{c['label']:32s} {g:6.2f} {c['ant']+c['feed']:10.2f} "
              f"{max(0.0, c['peur']-BASE):8.2f} {marg:8.2f} {d:7.1f} {q:11.0f} "
              f"{m1:10.1f} {m2:18.6f}")
    print()


if __name__ == "__main__":
    table(PROV["P_chip_max"][0],
          "A. WORST CASE = LOW-POWER LR2021 board at its chip max (+22 dBm, DE amateur regime)")
    table(PROV["P_le"][0],
          "B. LOW-POWER LR2021 under the LICENCE-EXEMPT cap (+12.15 dBm EIRP, ADR-039/041)")
    table(PROV["P_F33"][0],
          "C. HIGH-POWER F33 board (+33 dBm) - the same table, shifted")
    marginal_table(PROV["P_chip_max"][0])
    monotonicity(PROV["P_chip_max"][0])
    pos_class_table()
    print("DIY tracker reference build (positioner-lowcost §10):")
    print("  P1 = EUR279 mechanics+electronics + EUR50 controller + EUR100 mast  = EUR429")
    print("  P2 = P1 with NEMA34 + NMRV50 30:1 instead of NEMA23 + NMRV40      = EUR509")
    print(f"  coax+connectors = EUR{COAX_TOTAL:.2f} ; build allowance = EUR{BUILD_ALLOWANCE:.2f} ;"
          f" 433 feed allowance = EUR{DIY_FEED:.2f} (ESTIMATE)")
    print()
