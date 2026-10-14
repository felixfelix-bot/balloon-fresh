#!/usr/bin/env python3
"""Lift budget for the Yokohama 32-inch sphere balloon + hub v9 assembly.

Method: honest bounds, every assumption stated, worst case named.

ENVELOPE (from the product page): "Sphere Balloon(32inch), 1 bag 10 pieces".
32 inch = 812.8 mm DIAMETER when fully inflated/filled-form. Material is not
stated on the page; Yokohama Balloon sells latex and chloroprene; for a 32-inch
sphere we assume chloroprene (heavier than party latex, standard for HAB).

GAS: hydrogen or helium. We compute with helium (safer assumption; H2 lifts ~8%
more). Free-air density from the 1976 standard atmosphere at launch (sea level)
and at float (11-13 km).

PAYLOAD MASS: computed from the board file facts (115x103 mm, thickness choice
0.8 mm) + component masses from datasheets/typical values, then the wings.
"""
import math

# --- envelope --------------------------------------------------------------
D_IN = 32
D_MM = D_IN * 25.4
R = D_MM / 2 / 10 / 1000 / 100  # not used; keep mm
r_m = (D_MM / 2) / 1000
V_m3 = (4 / 3) * math.pi * r_m ** 3

# chloroprene envelope mass: 32-inch spheres run 60-100 g; we bound it.
ENVELOPE_MASS_G = (60, 100)  # (light, heavy) bound

# --- atmosphere (1976 STD, approximate densities) ---------------------------
def rho_alt(alt_m):
    # piecewise-ish: sea 1.225, 5km 0.736, 10km 0.414, 11km 0.365, 12km 0.312,
    # 13km 0.266, 14km 0.227 kg/m3 (linear interp)
    pts = [(0,1.225),(2000,1.007),(4000,0.819),(5000,0.736),(6000,0.660),
           (8000,0.526),(10000,0.414),(11000,0.365),(12000,0.312),
           (13000,0.266),(14000,0.227),(15000,0.195),(16000,0.167)]
    for (a1,r1),(a2,r2) in zip(pts,pts[1:]):
        if a1 <= alt_m <= a2:
            f=(alt_m-a1)/(a2-a1); return r1+f*(r2-r1)
    return pts[-1][1]

# gas densities at altitude (He 0.166 kg/m3 scaled by same density ratio as air)
def rho_he(alt_m):
    return 0.166 * (rho_alt(alt_m)/1.225)

# --- payload masses ---------------------------------------------------------
# Board 115x103 mm FR4: 1.85 g/cm3, ~+15% for copper/mask
def board_mass_g(thickness_mm):
    area_cm2 = 11.5*10.3
    vol = area_cm2 * thickness_mm/10  # cm3
    return vol*1.85*1.15

PCB_08 = board_mass_g(0.8)
# Components (typical datasheet/package masses):
COMPONENTS_G = {
    "ESP32-S3-WROOM-1U (3.2g module + solder)": 3.6,
    "SX1280 QFN24 + solder": 0.3,
    "MAX-M10S (flight boards only, avg 4/10)": 0.6*4/10 + 1.3*0,  # module 1.3g on 4 of 10
    "MAX-M10S actual avg (1.3g * 4/10)": 0.52,
    "U.FL x4": 4*0.12,
    "TPS7A02 + passives": 0.15,
    "SS24 x6 + BAT54W": 7*0.02,
}
# fix: use single clean list
COMPONENTS_G = {
    "ESP32-S3-WROOM-1U module": 3.2,
    "solder/reflow estimate (all SMD)": 0.5,
    "MAX-M10S avg over fleet (1.3g x 4/10)": 0.52,
    "SX1280 + LDO + passives + diodes": 0.6,
    "U.FL x 4": 0.48,
}
COMP_TOTAL = sum(COMPONENTS_G.values())

# Wings: 2 x (25x184 mm PCB 0.8? no -> wings are 2-layer, assume 1.0mm? use 0.8)
WING_PCB_G = 2 * (2.5*18.4*0.08*1.85*1.15)  # 2 wings, 0.8mm FR4
# solar cells 52x19mm x ~0.2mm silicon+encapsulant: ~1.2 g each; wings carry N cells.
# We do not have the cell count; bound 4..8 cells total.
SOLAR_CELLS_G = (4*1.2, 8*1.2)
# interconnects, solder joints, heat-seal tape, kevlar/thread loop
MISC_G = 2.0

print("="*72)
print(f"ENVELOPE: 32 inch sphere, D={D_MM:.0f} mm, V={V_m3:.3f} m3")
print(f"  chloroprene envelope mass bound: {ENVELOPE_MASS_G[0]}-{ENVELOPE_MASS_G[1]} g")
print()
print(f"PAYLOAD (hub v9, thickness 0.8 mm):")
print(f"  bare PCB 0.8 mm:      {PCB_08:6.1f} g")
for k,v in COMPONENTS_G.items():
    print(f"  {k:36s} {v:5.2f} g")
print(f"  components total:     {COMP_TOTAL:6.2f} g")
print(f"  hub populated:        {PCB_08+COMP_TOTAL:6.1f} g")
print()
wing_lo = WING_PCB_G + SOLAR_CELLS_G[0] + MISC_G
wing_hi = WING_PCB_G + SOLAR_CELLS_G[1] + MISC_G + 1.0
print(f"WINGS: 2x(25x184mm PCB) = {WING_PCB_G:.1f} g + solar cells {SOLAR_CELLS_G[0]:.0f}-{SOLAR_CELLS_G[1]:.0f} g + misc {MISC_G} g")
print(f"  wings total bound:    {wing_lo:6.1f} - {wing_hi:6.1f} g")
print()
TOTAL_LO = PCB_08+COMP_TOTAL+wing_lo
TOTAL_HI = PCB_08+COMP_TOTAL+wing_hi
print(f"PAYLOAD TOTAL (hub+wings): {TOTAL_LO:.0f} - {TOTAL_HI:.0f} g")
print()

# --- launch lift at sea level with helium -----------------------------------
rho0 = rho_alt(0); he0 = rho_he(0)
buoy = (rho0-he0)*V_m3*1000  # grams of lift at sea level, full sphere
print(f"SEA-LEVEL LIFT if filled to a FULL 32-inch sphere (He): {buoy:.0f} g")
print(f"  vs payload {TOTAL_LO:.0f}-{TOTAL_HI:.0f} g + envelope {ENVELOPE_MASS_G[0]}-{ENVELOPE_MASS_G[1]} g")
allup_lo = TOTAL_LO+ENVELOPE_MASS_G[0]; allup_hi = TOTAL_HI+ENVELOPE_MASS_G[1]
print(f"  all-up mass: {allup_lo:.0f} - {allup_hi:.0f} g")
print(f"  NET LIFT at launch if 100% filled: {buoy-allup_hi:.0f} to {buoy-allup_lo:.0f} g")
print()
# fill fraction needed for 5-7 g free lift (pico community standard)
for free in (5,7):
    need = (allup_hi+free)/ (rho0-he0)/1000  # m3 gas needed
    frac = need/V_m3
    print(f"  for {free} g free lift (heavy case): gas volume {need*1000:.0f} L = {frac*100:.0f}% of full sphere")

# --- float altitude check -----------------------------------------------------
print()
print("FLOAT CHECK: gas expands as it rises; envelope is elastic (chloroprene).")
print("  At float, lift = all-up mass. Solving for neutral buoyancy altitude")
print("  with a FIXED gas mass (sealed, no superpressure until full stretch):")
gas_mass = need*rho_he(0)  # kg (use the volume needed for 5g free at launch, heavy case)
for alt in range(0, 16001, 1000):
    rho = rho_alt(alt)
    # gas volume at this altitude (same mass, local pressure/temp approx via density ratio)
    vol = gas_mass / rho_he(alt)
    lift_g = (rho - rho_he(alt))*vol*1000
    net = lift_g - allup_hi
    if alt % 2000 == 0:
        print(f"   alt {alt/1000:5.1f} km: lift {lift_g:6.0f} g vs all-up {allup_hi:.0f} g -> net {net:+5.0f} g")
    if net <= 0:
        print(f"   >>> neutral buoyancy (float) at ~{alt/1000:.1f} km")
        break
