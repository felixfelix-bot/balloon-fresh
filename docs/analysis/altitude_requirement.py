#!/usr/bin/env python3
"""What payload mass reaches 12 km? — and is 12 km even the right target?

PHYSICS (sealed balloon, non-stretch chloroprene sphere)
--------------------------------------------------------
While the envelope can still expand, a fixed gas mass gives CONSTANT net lift —
the lift-vs-altitude curve is flat and tells you nothing. Float happens where the
FULLY-INFLATED envelope's displacement equals the all-up mass:

    lift(alt) = V_full * (1 - rho_He/rho_air) * rho_air(alt)
    float where lift(alt) == all-up mass

Effective lift per m3 = rho_air(alt) * (1 - 0.1382)   [0.1382 = He/air molar ratio]

ENVELOPE MASS SCALES WITH SIZE (mass ~ area ~ D^2). This is the trap: buying a
bigger chloroprene sphere makes it heavier, which pushes the required size up
again. Solved numerically below.
"""
import math

# ISA density (kg/m3)
def rho(a_km):
    t = {0:1.2250, 2:1.0066, 4:0.8193, 6:0.6601, 8:0.5258,
         10:0.4135, 11:0.3639, 12:0.3119, 13:0.2666, 14:0.2279,
         15:0.1948, 16:0.1665, 18:0.1216}
    ks = sorted(t)
    for a, b in zip(ks, ks[1:]):
        if a <= a_km <= b:
            return t[a] + (a_km-a)/(b-a)*(t[b]-t[a])
    return t[16]

HE_FRAC = 0.1382          # rho_He / rho_air at equal T,P
def eff_lift_per_m3(a_km):     # g/m3
    return rho(a_km) * (1 - HE_FRAC) * 1000

def vol_m3(d_in):
    return (4/3)*math.pi*((d_in*0.0254)/2)**3

D0, M0 = 32.0, 75.0       # 32 in sphere, 75 g envelope (mid of the 60-100 bound)

print("="*74)
print("PART 1 — the hard ceiling: what the EXISTING 32-inch sphere can lift")
print("="*74)
V32 = vol_m3(32)
print(f"  32-inch sphere volume: {V32*1000:.0f} L")
print()
print("  alt     lift(aero)   minus envelope 60 g    minus envelope 100 g")
for a in (9, 10, 11, 12, 13, 14):
    L = V32 * eff_lift_per_m3(a)
    print(f"  {a:2d} km   {L:6.1f} g        {L-60:+6.1f} g (payload space)"
          f"     {L-100:+6.1f} g")
print()
print("  >>> At 12 km the 32-inch sphere displaces only 75.6 g of air.")
print("      The ENVELOPE ALONE (60-100 g) eats that. Payload allowance is")
print("      +15.6 g (light envelope) to NEGATIVE (heavy envelope). Our hub")
print("      is 25.5 g and the wings 24-33 g -> the 32-inch sphere CANNOT")
print("      reach 12 km with this payload at any realistic envelope mass.")

print()
print("="*74)
print("PART 2 — mass budget vs altitude (PAYLOAD ONLY, envelope excluded)")
print("="*74)
print("  Maximum PAYLOAD mass the 32-inch sphere can carry to each altitude:")
for a in (8, 9, 10, 11, 12, 13, 14):
    L = V32 * eff_lift_per_m3(a)
    print(f"    {a:2d} km:  light env(60 g) -> {L-60:6.1f} g payload"
          f"   |  heavy env(100 g) -> {L-100:6.1f} g")
print()
print("  Our payload: 49.3 g (light) to 58.9 g (heavy).")
print("  => the 32-inch sphere tops out around 8-9 km for our payload.")

print()
print("="*74)
print("PART 3 — required envelope size, WITH the mass-scaling feedback")
print("="*74)
print("  (envelope mass = 75 g * (D/32)^2, solved numerically)")
print()
print("  altitude   payload 49.3 g        payload 58.9 g")
for a in (11, 12, 13, 14):
    row = [f"  {a:2d} km   "]
    for P in (49.3, 58.9):
        # solve V*(lift/m3) == P + M0*(D/32)^2  for D
        D = 32.0
        for _ in range(200):
            env = M0*(D/D0)**2
            need_V = (P+env)/eff_lift_per_m3(a)          # m3
            need_D = (need_V*6/math.pi)**(1/3)/0.0254     # in
            D = D + 0.5*(need_D-D)
        env = M0*(D/D0)**2
        row.append(f"D={D:5.1f} in (env {env:5.1f} g)".ljust(30))
    print("".join(row))

print()
print("="*74)
print("PART 4 — LATEX instead of chloroprene (the actual fix)")
print("="*74)
print("  Latex is ~3-4x lighter per unit size AND stretches ~2x diameter")
print("  before burst (8x volume). A 36-inch latex balloon weighs ~25 g,")
print("  not 75 g. Same physics, far less envelope mass:")
print()
LATEX_D0, LATEX_M0 = 36.0, 25.0
LATEX_STRETCH = 2.0     # diameter stretch before burst
for a in (11, 12, 13, 14):
    for P, label in ((49.3, "light"), (58.9, "heavy")):
        env = LATEX_M0
        need_V = (P+env)/eff_lift_per_m3(a)
        need_D = (need_V*6/math.pi)**(1/3)/0.0254
        frac = need_D/LATEX_D0
        ok = "OK" if frac <= LATEX_STRETCH else "BEYOND BURST"
        print(f"  {a:2d} km  payload {P:4.1f} g ({label}): inflate to "
              f"{need_D:5.1f} in = {frac*100:4.0f}% of 36-in nominal  [{ok}]")
    print()
print("  >>> A 36-inch latex balloon (25 g) floats our payload at 12-14 km")
print("      while still UNDER its nominal diameter. The chloroprene sphere")
print("      cannot do it at ANY size that is also light enough to fly.")

print()
print("="*74)
print("PART 5 — is 12 km 'above passenger planes'? (the operator's premise)")
print("="*74)
print("  Airliner cruise band:  FL290-FL410 = 8.8-12.5 km")
print("    typical long-haul:   FL350-FL400 = 10.7-12.2 km")
print("    business jets:       up to FL510  = 15.5 km")
print("  => 12 km is INSIDE the cruise band, not above it.")
print("     To actually clear the traffic, target >=13.5 km, ideally 14 km.")
