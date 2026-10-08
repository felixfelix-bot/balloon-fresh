#!/usr/bin/env python3
"""Ground-station 433 MHz FLRC max-throughput model (design/ground-station-flrc-max).

Prints every numeric table in
`docs/analysis/ground-station-flrc-max-throughput.md`.

Inputs and their provenance are inline.  Nothing here is a datasheet value:
the datasheet values (sensitivities, TX powers) are quoted in the document with
their table numbers; this script only does arithmetic on them.

Run:  python3 docs/analysis/ground_station_flrc_max_model.py
"""

import math

# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
C = 299_792_458.0            # m/s
F = 433.05e6                 # Hz  (433 ISM / EU 70 cm band centre, ADR-034)
LAM = C / F                  # 0.6924 m  (task-given lambda for 433 MHz)
ETA = 0.55                   # aperture efficiency used for the TRADE (task)
ETA_VENDOR = 0.65            # RF Hamdesign's own published mesh-dish efficiency
FSPL_650 = 141.4             # dB, FSPL(433.05 MHz, 650 km)  (prior study)

# Sub-GHz FLRC 1% PER sensitivities, Semtech LR2021/LR2022/LR2012 datasheet
# v2.2 Table 3-12 ("FLRC Sub-GHz 1% PER (LR2021)"), G13 rx_boost=7 @915 MHz.
# Using the 915 MHz rows at 433 MHz is the honest characterisation; the
# 433-specific row is TODO(unverified) (inherited from the prior study).
FLRC = {
    "2.6 Mbps (2600)": -100.5,
    "2.08 Mbps (2080)": None,      # TODO(unverified) — no datasheet row quoted
    "1.3 Mbps (1300)": None,       # TODO(unverified) — no datasheet row quoted
    "1.04 Mbps (1040)": -105.0,
    "650 kbps (650)": -107.0,
    "520 kbps (520)": -108.5,
    "325 kbps (325)": -110.0,
    "260 kbps (260)": -111.0,
}

G_BALLOON = 0.0              # dBi — no balloon attitude control (conservative)

# Air density and the drag coefficient derived from a *vendor* wind-load figure
RHO = 1.225                  # kg/m3
GIBERTINI_AREA = 0.94 * 1.01   # m2 — Gibertini OP100SE working surface (vendor)
GIBERTINI_KG_120 = 91.0        # kg — vendor-stated wind load at 120 km/h
V120 = 120.0 / 3.6             # 33.333 m/s
Q120 = 0.5 * RHO * V120 ** 2
CD_DISH = GIBERTINI_KG_120 * 9.80665 / (Q120 * GIBERTINI_AREA)   # ~1.38


def req_gain(sens_dbm, p_tx_dbm, fspl=FSPL_650, g_b=G_BALLOON):
    """required ground gain (dBi) = S + FSPL - P_tx - G_balloon."""
    return sens_dbm + fspl - p_tx_dbm - g_b


def dish_diameter(g_dbi, eta=ETA, lam=LAM):
    """paraboloid diameter (m) for a gain, G = 10log10(eta (pi D / lam)^2)."""
    return (lam / math.pi) * math.sqrt(10 ** (g_dbi / 10.0) / eta)


def dish_area(d):
    return math.pi * (d / 2.0) ** 2


def max_range_km(g_dish, p_tx, sens, g_b=G_BALLOON):
    """max free-space slant range (km) for a link that is exactly closed."""
    fspl = p_tx + g_b + g_dish - sens
    d = (C / (4.0 * math.pi * F)) * 10 ** (fspl / 20.0)
    return d / 1000.0


def wind_force(d, v, cd=CD_DISH, solidity=1.0):
    """normal-incidence wind force (N) on a dish of diameter d at wind speed v."""
    q = 0.5 * RHO * v ** 2
    return q * dish_area(d) * cd * solidity


def wind_moment(d, v, lever_frac=0.5, cd=CD_DISH, solidity=1.0):
    """wind moment (N.m) about the mount, lever arm = lever_frac * diameter."""
    return wind_force(d, v, cd, solidity) * (lever_frac * d)


def mesh_solidity(aperture_mm, wire_mm):
    """solid fraction of a square woven/welded mesh."""
    return 1.0 - (aperture_mm / (aperture_mm + wire_mm)) ** 2


# ----------------------------------------------------------------------------
def hdr(t):
    print("\n" + "=" * 78)
    print(t)
    print("=" * 78)


hdr("0. Constants")
print(f"c                = {C:.0f} m/s")
print(f"f                = {F/1e6:.2f} MHz")
print(f"lambda           = {LAM:.4f} m   (= {LAM*1000:.1f} mm)")
print(f"lambda/10 (mesh) = {LAM/10*1000:.1f} mm   <- max mesh hole at 433 MHz")
print(f"lambda/20 (surf) = {LAM/20*1000:.1f} mm   <- RMS surface tolerance")
print(f"FSPL(433.05 MHz, 650 km) = {FSPL_650} dB (given)")
print(f"eta (trade)      = {ETA}   eta (RF Hamdesign published) = {ETA_VENDOR}")
print(f"Cd derived from Gibertini OP100SE: {CD_DISH:.2f} "
      f"(= {GIBERTINI_KG_120} kg*9.80665 / ({Q120:.0f} Pa * {GIBERTINI_AREA:.4f} m2))")

# ----------------------------------------------------------------------------
hdr("1. THE TRADE: required ground gain and the dish diameter it implies")
print("req_G = S + FSPL - P_tx - G_balloon   (G_balloon = 0 dBi)")
print("D     = (lambda/pi) * sqrt(10^(req_G/10) / eta),  eta = 0.55\n")
print(f"{'P_tx':>6} {'rate':>18} {'S dBm':>8} {'reqG dBi':>9} {'D m':>7} "
      f"{'area m2':>8} {'mass~kg':>8}")
rows = []
for p in (13, 22, 33):
    for name, s in FLRC.items():
        if s is None:
            continue
        g = req_gain(s, p)
        d = dish_diameter(g)
        # mass: scale the RF Hamdesign mesh-dish masses by area, shell/mesh only
        # (vendor: 1.2 m = 4.8 kg, 2.4 m = 14 kg, 3.0 m = 27 kg)
        rows.append((p, name, s, g, d))
        print(f"{p:>6} {name:>18} {s:>8.1f} {g:>9.1f} {d:>7.2f} "
              f"{dish_area(d):>8.2f}")

hdr("1b. The 2x2 grid the operator asked for (P_tx x rate)")
print(f"{'P_tx':>6} | {'2.6 Mbps':>26} | {'650 kbps':>26}")
print(f"{'dBm':>6} | {'reqG dBi / D m  (area m2)':>26} | "
      f"{'reqG dBi / D m  (area m2)':>26}")
for p in (13, 22, 33):
    out = []
    for name, s in (("2.6", FLRC["2.6 Mbps (2600)"]), ("650", FLRC["650 kbps (650)"])):
        g = req_gain(s, p)
        d = dish_diameter(g)
        out.append(f"{g:>7.1f} / {d:>4.2f}  ({dish_area(d):>5.2f})")
    print(f"{p:>6} | {out[0]:>26} | {out[1]:>26}")

hdr("1c. What the F33's +20 dB buys (factor in dish diameter and area)")
for rname, s in (("2.6 Mbps", FLRC["2.6 Mbps (2600)"]),
                 ("650 kbps", FLRC["650 kbps (650)"])):
    d13 = dish_diameter(req_gain(s, 13))
    d33 = dish_diameter(req_gain(s, 33))
    print(f"{rname}: +13 dBm -> {d13:5.2f} m ({dish_area(d13):6.2f} m2)  |  "
          f"+33 dBm -> {d33:5.2f} m ({dish_area(d33):5.2f} m2)  |  "
          f"diameter x{d13/d33:.1f}, area x{dish_area(d13)/dish_area(d33):.0f}")

# ----------------------------------------------------------------------------
hdr("2. RATE ADAPTATION: rate vs range for candidate dishes (G_balloon = 0)")

# candidate dish gains at 433 MHz (paraboloid), eta = 0.55 as instructed
CANDIDATES = [0.74, 1.24, 1.90, 2.40, 2.62, 3.00, 3.49]
print("\nCandidate dish gains (eta=0.55) and (eta=0.65, RF Hamdesign published):")
cand_g = {}
for d in CANDIDATES:
    g55 = 10 * math.log10(ETA * (math.pi * d / LAM) ** 2)
    g65 = 10 * math.log10(ETA_VENDOR * (math.pi * d / LAM) ** 2)
    cand_g[d] = g55
    print(f"  D = {d:4.2f} m : G = {g55:5.1f} dBi (eta 0.55) | "
          f"{g65:5.1f} dBi (eta 0.65)")

print("\nMax free-space slant range (km) at +33 dBm / G_balloon 0 dBi:")
line = f"{'rate':>18} {'S':>7} | " + " | ".join(f"{d:>6.2f}m" for d in CANDIDATES)
print(line)
for name, s in FLRC.items():
    if s is None:
        continue
    cells = []
    for d in CANDIDATES:
        cells.append(f"{max_range_km(cand_g[d], 33, s):>7.0f}")
    print(f"{name:>18} {s:>7.1f} | " + " | ".join(cells))

print("\nMax free-space slant range (km) at +22 dBm (chip max, no F33) / "
      "G_balloon 0 dBi:")
print(line)
for name, s in FLRC.items():
    if s is None:
        continue
    cells = [f"{max_range_km(cand_g[d], 22, s):>7.0f}" for d in CANDIDATES]
    print(f"{name:>18} {s:>7.1f} | " + " | ".join(cells))

print("\nDish needed for a 650 km close at +33 dBm (reqG / D):")
for name, s in FLRC.items():
    if s is None:
        continue
    g = req_gain(s, 33)
    print(f"  {name:>18}: {g:>6.1f} dBi -> D = {dish_diameter(g):5.2f} m")
print("\nDish needed for a 650 km close at +22 dBm (reqG / D):")
for name, s in FLRC.items():
    if s is None:
        continue
    g = req_gain(s, 22)
    print(f"  {name:>18}: {g:>6.1f} dBi -> D = {dish_diameter(g):5.2f} m")

# ----------------------------------------------------------------------------
hdr("3. MESH WIND ANALYSIS")
print("Wind force F = q * A * Cd * solidity ;  q = 0.5 rho v^2")
print(f"Cd(dish, solid) = {CD_DISH:.2f} (derived from the Gibertini OP100SE vendor figure)")
print("Solidity of a square mesh: sigma = 1 - (aperture/(aperture+wire))^2")
MESHES = {
    "6 mm sq, 1.0 mm wire (RFH kit mesh)": mesh_solidity(6, 1.0),
    "25 mm sq, 2.0 mm wire (welded wire)": mesh_solidity(25, 2.0),
    "50 mm sq, 3.0 mm wire (open weld mesh)": mesh_solidity(50, 3.0),
    "13 mm sq, 1.6 mm wire (AViary wire)": mesh_solidity(13, 1.6),
}
for k, v in MESHES.items():
    print(f"  sigma = {v*100:5.1f} % solid   <- {k}")

print("\nWind moment about the mount (N.m), lever arm = 0.5 * D, at 120 km/h "
      "(33.3 m/s):")
print(f"{'D m':>6} {'A m2':>7} {'F solid N':>10} {'M solid':>9} | "
      f"{'sigma .265':>10} {'M mesh':>9} | {'sigma .143':>10} {'M mesh':>9}")
for d in CANDIDATES:
    ms = wind_moment(d, V120, solidity=1.0)
    m6 = wind_moment(d, V120, solidity=MESHES["6 mm sq, 1.0 mm wire (RFH kit mesh)"])
    m25 = wind_moment(d, V120, solidity=MESHES["25 mm sq, 2.0 mm wire (welded wire)"])
    print(f"{d:>6.2f} {dish_area(d):>7.2f} {wind_force(d, V120):>10.0f} "
          f"{ms:>9.0f} | {MESHES['6 mm sq, 1.0 mm wire (RFH kit mesh)']:>10.3f} "
          f"{m6:>9.0f} | {MESHES['25 mm sq, 2.0 mm wire (welded wire)']:>10.3f} "
          f"{m25:>9.0f}")

print("\nSPID BIG-RAS holding (brake) torque = 2,712 N.m  "
      "(rfhamdesign BIG-RAS spec sheet); turning torque 500 N.m;")
print("vertical load > 318 kg.  Ratio M/2712 = 1.00 is the rating line:")
for d in CANDIDATES:
    ms = wind_moment(d, V120, solidity=1.0)
    m6 = wind_moment(d, V120, solidity=MESHES["6 mm sq, 1.0 mm wire (RFH kit mesh)"])
    m25 = wind_moment(d, V120, solidity=MESHES["25 mm sq, 2.0 mm wire (welded wire)"])
    print(f"  D={d:4.2f} m : solid {ms/2712:5.2f}x | 6mm mesh {m6/2712:5.2f}x | "
          f"25mm mesh {m25/2712:5.2f}x")

print("\nThe IMPRACTICAL case: the low-power (+13 dBm) / 2.6 Mbps dish (7.38 m)")
D_IMP = 7.38
for v, lab in ((20.0, "20 m/s"), (V120, "120 km/h")):
    fs = wind_force(D_IMP, v)
    print(f"  v={lab:>8}: A={dish_area(D_IMP):.1f} m2  F_solid={fs:,.0f} N  "
          f"M_solid={wind_moment(D_IMP, v):,.0f} N.m "
          f"({wind_moment(D_IMP, v)/2712:,.1f}x BIG-RAS brake)")
    m6 = wind_moment(D_IMP, v, solidity=mesh_solidity(6, 1.0))
    print(f"             6mm-mesh: M={m6:,.0f} N.m ({m6/2712:,.1f}x)")
print("  mass scaling from the RF Hamdesign 3.0 m kit (27 kg): "
      f"~{27*(D_IMP/3.0)**2:,.0f} kg of dish structure alone")

print("\nSame at a 20 m/s (72 km/h) operating wind:")
for d in CANDIDATES:
    ms = wind_moment(d, 20.0, solidity=1.0)
    m6 = wind_moment(d, 20.0, solidity=MESHES["6 mm sq, 1.0 mm wire (RFH kit mesh)"])
    print(f"  D={d:4.2f} m : solid {ms:7.0f} N.m ({ms/2712:4.2f}x) | "
          f"6mm mesh {m6:7.0f} N.m ({m6/2712:4.2f}x)")

# ----------------------------------------------------------------------------
hdr("4. F33 balloon-side cost (all figures from the repo, cited in the doc)")
print("F33 TX at 433 MHz: 5.0 V / +33.0 dBm / 1100 mA  "
      "(docs/adr/047-v9-power-provisioning.md line 67)")
print(f"  P_DC = 5.0 V * 1.100 A = {5.0*1.100:.2f} W")
print("F33 TX worst case: 5.5 V / +33.3 dBm / 1118 mA (ADR-047 sec 1.1-1.2)")
print(f"  P_DC = 5.5 V * 1.118 A = {5.5*1.118:.2f} W")
print("Solar array peak: 4 wings x 3 cells = 12 series = 6.0 V @ 1.2 A = 7.2 W "
      "(docs/v9-BOM.md line 101; ADR-049/051)")
print("Solar array nominal (ADR-006/044): 6.0 V @ 400 mA = 2.4 W")
print("Mass: LR2021F33 2W module = 4.0 g ; bare LR2021 module = 1.2 g "
      "(docs/PAYLOAD-WEIGHT-ESTIMATES.md lines 62/119/177)")
print(f"  module mass delta (F33 - bare) = {4.0-1.2:.1f} g")
print("Full V2/F33 board reference mass = 20.6 g incl 4 thin-film cells, and the "
      "repo classes it 'Ground Station Only / not a pico balloon target' "
      "(docs/PAYLOAD-WEIGHT-ESTIMATES.md lines 168-182/195)")

hdr("5. Mesh-hole rule check (433 MHz)")
for fghz, name in ((0.433, "433 MHz"), (2.4, "2.4 GHz"), (6.0, "6 GHz"),
                   (11.0, "11 GHz")):
    lam = C / (fghz * 1e9)
    print(f"  {name:>8}: lambda = {lam*1000:6.1f} mm  lambda/10 = {lam*100:6.1f} mm")
print("\nRF Hamdesign 6 mm square mesh is advertised usable to 6 GHz, and the "
      "2.8 mm mesh option to 11 GHz:")
print(f"  at 6 GHz lambda/10 = {C/6e9*100:.1f} mm  (6 mm mesh = {6/(C/6e9*100):.2f} x lambda/10)")
print(f"  at 11 GHz lambda/10 = {C/11e9*100:.1f} mm (2.8 mm mesh = {2.8/(C/11e9*100):.2f} x lambda/10)")
print("At 433 MHz lambda/10 = "
      f"{LAM*100:.1f} mm, so a 6 mm mesh is {LAM*100/6:.1f}x finer than needed "
      "-> electrically solid with a large margin.")
