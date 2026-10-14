#!/usr/bin/env python3
"""Float-altitude analysis, done honestly.

Physics: a sealed gas mass keeps CONSTANT net lift while the envelope can still
expand (gas stays at ambient pressure). Once the envelope reaches its fully
stretched volume, it cannot expand further -> superpressure -> the effective
lift DROPS as air density keeps falling with altitude. Float happens where
lift(all-up mass) crosses zero ON THE DESCENDING side, i.e. where the
fully-inflated envelope's displacement equals the all-up mass.

The 32-inch "rating" is the fill-form diameter. Latex stretches well beyond it;
chloroprene is less elastic. So we present BOTH: float at nominal full volume,
and the stretch factor needed for the proven 11-13.7 km band.
"""
import math

D_MM = 32 * 25.4
V_FULL = (4/3)*math.pi*(D_MM/2000)**3  # m3

def rho(a):
    pts=[(0,1.225),(2000,1.007),(4000,0.819),(5000,0.736),(6000,0.660),
         (8000,0.526),(10000,0.414),(11000,0.365),(12000,0.312),
         (13000,0.266),(14000,0.227),(15000,0.195)]
    for (a1,r1),(a2,r2) in zip(pts,pts[1:]):
        if a1<=a<=a2: return r1+(a-a1)/(a2-a1)*(r2-r1)
    return pts[-1][1]

HE_FRAC = 0.166/1.225  # helium density ratio vs air at same T/P

ALLUP = (108, 154)  # g, (light, heavy) from the mass budget

print(f"Fully-stretched volume (nominal 32 in): {V_FULL*1000:.0f} L")
print()
for name, m in (("LIGHT all-up 108 g", 108), ("HEAVY all-up 154 g", 154)):
    print(f"--- {name} ---")
    # float at nominal volume: (rho*(1-HE_FRAC))*V = m/1000 kg
    rho_need = (m/1000) / (V_FULL*(1-HE_FRAC))
    # find altitude
    alt = None
    for a in range(0, 16001, 100):
        if rho(a) <= rho_need:
            alt = a; break
    print(f"  float at NOMINAL volume: {alt/1000 if alt else '>16'} km"
          if alt else "  float at nominal volume: above 16 km (no float)")
    # volume needed to float at 11 and 13.7 km
    for target in (11000, 13700):
        r = rho(target)
        v = (m/1000)/((r - r*HE_FRAC))
        stretch = v/V_FULL
        d = (v/V_FULL)**(1/3)*32
        print(f"  to float at {target/1000:.1f} km: need {v*1000:.0f} L "
              f"= {stretch:.2f}x nominal volume (sphere {d:.0f} in)")
    print()

print("INTERPRETATION:")
print(" - Chloroprene sphere balloons do not stretch 1.7-2.6x; that is latex")
print("   territory. At nominal volume the float is ~6.5-9.3 km: BELOW the")
print("   proven 11-13.7 km pico band, but still above weather and fine for")
print("   comms experiments (radio horizon at 8 km ~ 320 km).")
print(" - Options: (a) accept 7-9 km float; (b) lighten payload; (c) switch to")
print("   36-40 inch LATEX (community standard: stretches ~2x, floats 11-13 km")
print("   with 20-50 g all-up... but our all-up is 108-154 g = heavier than")
print("   typical pico payloads by 2-3x, so even latex needs the big size).")
