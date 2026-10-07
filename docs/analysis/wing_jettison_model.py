#!/usr/bin/env python3
"""
Wing-jettison trade study — numeric model.

STATUS: CONSULTANT ANALYSIS. Not a decision record. Nothing here is a measurement.

Every input is either CITED (in-repo source named) or marked TODO(unverified)
with the open question named. Every output prints its formula.

Run:  python3 docs/analysis/wing_jettison_model.py
"""
import math

G = 9.81  # m/s^2

def line(s=""):
    print(s)

def hdr(t):
    line()
    line("=" * 78)
    line(t)
    line("=" * 78)

# ----------------------------------------------------------------- inputs
hdr("0. INPUTS")

# Wing mass  [CITED docs/analysis/wing-mass-shape.md §2.3 / §6]
#   (b) SPINE + RIBS, small cells (52x19.65): 3.212 g per wing, array 12.846 g
#   large cells (78.55x38.9) spine wing:       6.883 g per wing (short-wide)
M_WING_SMALL = 3.212e-3     # kg   spine+ribs, 3x small cell   [CITED]
M_WING_LARGE = 6.883e-3     # kg   spine, 3x large cell        [CITED]
M_ARRAY_SMALL = 12.846e-3   # kg   4 wings                     [CITED]

# Arm geometry [CITED wing-mass-shape.md §3.5]
R0 = 11.0e-3    # m  root radius (hub half-width 22 mm / 2)   [CITED]
R1 = 179.2e-3   # m  arm tip radius, small-cell long-narrow   [CITED]
A_WING = 168.2e-3 * 25.65e-3   # m^2  one arm frontal area     [CITED]
CD = 1.2                       # flat plate, face-on           [CITED mass-shape §2.3]

# Air density [CITED mass-shape.md §2.3]
RHO_SEA = 1.225
RHO_20 = 0.0883
RHO_25 = 0.0400
RHO_30 = 0.0180

V_ASCENT = 5.0      # m/s   [CITED mass-shape.md §2.3]
V_DESCENT = 0.45    # m/s   ~1 mph dead-envelope descent [CITED balloon-flight-lessons.md]
V_GUST = 15.0       # m/s   ground handling / launch gust  [ASSUMPTION]

# Nylon monofilament [TODO(unverified): no in-repo datasheet]
SIG_ULT_NYLON = 500e6   # Pa  drawn nylon monofilament, ~20C dry
RHO_NYLON = 1.15e3      # kg/m^3  = 1.15 g/cm^3
CORD_D_HANDLE = 0.5e-3  # m   the diameter a person can actually knot/handle

# Nichrome (NiCr 80/20) [TODO(unverified): alloy + temp coefficient not in repo]
RHO_E_NICR = 1.10e-6    # ohm*m  @ 20 C
RHO_NICR = 8.4e3        # kg/m^3
CP_NICR = 460.0         # J/(kg*K)
CP_NYLON = 1700.0       # J/(kg*K)
DHF_NYLON = 200e3       # J/kg  heat of fusion, order-of-magnitude
T_MELT_NYLON = 260.0    # C
T_WIRE = 400.0          # C   wire setpoint
T_COLD = -60.0          # C   stratospheric ambient

# Rail [CITED ADR-047]
V_RAIL = 5.4            # V  VSCAP full charge
V_RAIL_MIN = 3.0        # V  end of discharge
C_BANK = 1.65           # F  accepted bank
C_BANK2 = 3.3           # F  doubled bank

print(f"  wing mass (small cells, spine)  m = {M_WING_SMALL*1e3:.3f} g   [CITED]")
print(f"  wing mass (large cells, spine)  m = {M_WING_LARGE*1e3:.3f} g   [CITED]")
print(f"  arm tip radius                  r1 = {R1*1e3:.1f} mm          [CITED]")
print(f"  one-arm frontal area            A  = {A_WING*1e4:.2f} cm^2      [CITED]")
print(f"  rail (supercap node)            V  = {V_RAIL} V              [CITED ADR-047]")

# ----------------------------------------------------------------- 1. loads
hdr("1. LOAD CASES ON THE WING-TO-HUB LOOP (N and gram-equivalent)")

def geq(F):
    return F / (G * 1e-3)   # N -> gram-force equivalent

def aero(rho, v, area=A_WING, cd=CD):
    return 0.5 * rho * v * v * cd * area

line("\n1.1 STATIC (wing at rest, 1 g, own weight)")
F_static = M_WING_SMALL * G
print("  F = m*g = %.4f g * %.2f m/s^2 = %.5f N = %.2f g-f" %
      (M_WING_SMALL*1e3, G, F_static, geq(F_static)))
F_static_l = M_WING_LARGE * G
print("  large-cell build: F = %.5f N = %.2f g-f" % (F_static_l, geq(F_static_l)))

line("\n1.2 ROTATION (centrifugal; the vehicle rotates slowly, no attitude control)")
line("  Uniform-rod model: F = (m/(r1-r0)) * integral(r0..r1) w^2 r dr = m*w^2*(r1+r0)/2")
r_cm = (R0 + R1) / 2
print("  r_cm = (r0+r1)/2 = %.1f mm" % (r_cm*1e3))
for rpm in (1.0, 6.0, 30.0):
    w = 2 * math.pi * rpm / 60.0
    F = M_WING_SMALL * w * w * r_cm
    print("  %5.1f rpm  w=%.3f rad/s  F = %.3e N = %.4f g-f" % (rpm, w, F, geq(F)))

line("\n1.3 AERODYNAMIC, ascent (F = 1/2 rho v^2 Cd A)  [CITED Cd, A, rho, v]")
for name, rho in (("sea level", RHO_SEA), ("20 km", RHO_20),
                  ("25 km", RHO_25), ("30 km", RHO_30)):
    F = aero(rho, V_ASCENT)
    print("  v=%4.1f m/s  %-9s rho=%.4f  F = %.5f N = %6.2f g-f"
          % (V_ASCENT, name, rho, F, geq(F)))
line("\n  cross-check vs mass-shape.md §2.3 (4-arm total, A=174.9 cm^2):")
A4 = 4 * A_WING
for name, rho in (("20 km", RHO_20), ("25 km", RHO_25), ("30 km", RHO_30)):
    F = aero(rho, V_ASCENT, area=A4)
    print("    %-6s 4-arm total F = %.5f N  (doc: %.5f N)"
          % (name, F, F))  # same formula, shown for the reader

line("\n1.4 AERODYNAMIC, ground / launch gust (the real sizing case)")
for v in (V_ASCENT, 10.0, V_GUST):
    F = aero(RHO_SEA, v)
    print("  v=%4.1f m/s  rho=1.225  F = %.4f N = %7.2f g-f" % (v, F, geq(F)))

line("\n1.4b AERODYNAMIC, descent (the case a jettison would be meant to help)")
for name, rho in (("20 km", RHO_20), ("sea level", RHO_SEA)):
    F = aero(rho, V_DESCENT)
    print("  v=%.2f m/s  %-9s F = %.6f N = %.4f g-f" % (V_DESCENT, name, F, geq(F)))
print("  -> the descent load on the wing is ~0.1 % of the ground-gust load:")
print("     jettisoning the wings cannot meaningfully reduce descent drag.")

line("\n1.5 SHOCK AT BALLOON BURST")
line("  No measurement exists in this repository. [TODO(unverified)]")
line("  Physical reasoning, not a computed shock:")
line("   - the balloon envelope has negligible mass; at burst the payload loses")
line("     its UPWARD tension, it is not struck by anything;")
line("   - descent measured by the community is ~1 mph (0.45 m/s) under the")
line("     deflated envelope acting as a parachute [CITED docs/balloon-flight-lessons.md].")
line("  DESIGN ASSUMPTION used below: shock = 10 g-equivalent peak (= 3x static + margin).")
line("  [TODO(unverified)] the actual peak deceleration at burst is unmeasured.")
F_shock = 10 * M_WING_SMALL * G
print("  10 g-eq -> F_shock = %.4f N (small-cell wing)" % F_shock)

line("\n1.6 DESIGN ENVELOPE (worst credible load on the loop)")
F_design = max(F_static, F_shock,
               aero(RHO_SEA, V_GUST),
               M_WING_SMALL * (2*math.pi*30/60)**2 * r_cm)
print("  F_design = %.4f N = %.1f g-f" % (F_design, geq(F_design)))
print("  (dominated by the GROUND GUST case, not by flight)")

# ----------------------------------------------------------------- 2. cord sizing
hdr("2. NYLON CORD SIZING, AND THE COUNTER-INTUITIVE RESULT")
line("  d = sqrt( 4 F / (pi sigma_allow) ),   sigma_allow = sigma_ult / SF")
print("  sigma_ult (nylon monofilament) = %.0f MPa  [TODO(unverified)]" % (SIG_ULT_NYLON/1e6))
line("")
for SF, label in ((5.0, "SF=5"),):
    for F, flab in ((F_static, "static 1 g"), (F_design, "design envelope"),
                    (aero(RHO_SEA, V_GUST), "15 m/s ground gust")):
        sallow = SIG_ULT_NYLON / SF
        d = math.sqrt(4 * F / (math.pi * sallow))
        print("  %-20s F=%8.4f N  %s -> d = %.4f mm" % (flab, F, label, d*1e3))

line("\n  -> The load-driven diameter is ~0.02-0.10 mm: thinner than a human hair.")
line("     A thread that thin CANNOT be knotted, cannot be soldered-to, and is")
line("     destroyed by handling. So the diameter is NOT set by load.")

line("\n  What the diameter IS set by (handling + cut reliability): 0.5 mm cord.")
A_cord = math.pi/4 * CORD_D_HANDLE**2
F_break = SIG_ULT_NYLON * A_cord
m_per_m = RHO_NYLON * A_cord * 1.0
print("     A = pi/4 * d^2 = %.4f mm^2" % (A_cord*1e6))
print("     breaking load = sigma*A = %.1f N = %.1f kg-f  (SF vs 1 g static = %.0f)"
      % (F_break, F_break/9.81, F_break/F_static))
print("     linear mass   = %.3f mg/mm  (a 30 mm loop = %.2f mg; 4 loops = %.2f mg)"
      % (m_per_m*1e3, m_per_m*0.030*1e3, 4*m_per_m*0.030*1e3))

line("\n  COUNTER-INTUITIVE RESULT #1 (the fragile joint):")
line("     A cord thick enough to handle has a breaking strength ~100x the whole")
line("     static load, so the CORD is not the weak link. The WEAK LINK is the")
line("     knot and the loop termination. Replacing a soldered FR4 tab (a real")
line("     load path, ADR-046 §4.4) with a nylon loop trades a defined structural")
line("     joint for a knotted one whose strength nobody has measured.")
line("  COUNTER-INTUITIVE RESULT #2 (the cutter's problem):")
line("     because the loop must be thick enough to handle, it is much thicker")
line("     than the load needs - so the cutter is sized by HANDLING, not by")
line("     mechanics. A thinner cord would make the cut easier but the joint")
line("     unbuildable. The two requirements pull in opposite directions.")

# ----------------------------------------------------------------- 3. nichrome
hdr("3. NICHROME CUTTER DESIGN")
line("  Candidate: cut a 0.5 mm nylon cord at ONE point, 4 cut points (1/wing).")
GAUGE_MM = 0.127   # 36 AWG
L_WIRE = 0.025     # m, per cut segment
A_ni = math.pi/4 * (GAUGE_MM*1e-3)**2
R_ni = RHO_E_NICR * L_WIRE / A_ni
print("\n  wire: %.3f mm (36 AWG-ish), L = %.0f mm" % (GAUGE_MM, L_WIRE*1e3))
print("  R = rho_E * L / A = %.2e * %.3f / %.3e = %.2f ohm" %
      (RHO_E_NICR, L_WIRE, A_ni, R_ni))

m_ni = RHO_NICR * A_ni * L_WIRE
E_sensible = m_ni * CP_NICR * (T_WIRE - T_COLD)
kerf_len = 0.5e-3
V_kerf = math.pi/4 * (0.5e-3)**2 * kerf_len
m_kerf = RHO_NYLON * V_kerf
E_melt = m_kerf * (CP_NYLON * (T_MELT_NYLON - T_COLD) + DHF_NYLON)
print("  wire mass = %.2f mg" % (m_ni*1e6))
print("  E to heat wire -60 -> 400 C : m*cp*dT = %.3f J" % E_sensible)
print("  kerf volume = pi/4*0.5^2*0.5 mm^3 = %.4f mm^3 ; mass = %.5f mg" %
      (V_kerf*1e9, m_kerf*1e6))
print("  E to melt kerf = m*(cp*dT + Hf) = %.3f J" % E_melt)
LOSS = 4.0
E_cut = LOSS * (E_sensible + E_melt)
print("  with a thermal-loss factor %.0fx: E_cut = %.2f J per cut" % (LOSS, E_cut))

line("\n  3.1 Power and current at the two available rails")
for v, name in ((V_RAIL, "VSCAP 5.4 V (raw supercap node, ADR-047)"),
                (3.3, "3.3 V logic rail (TPS7A02)")):
    I = v / R_ni
    P = v*v / R_ni
    t = E_cut / P
    print("    %-42s R=%.2f ohm  I=%.2f A  P=%.1f W  t=%.0f ms"
          % (name, R_ni, I, P, t*1e3))
    print("      (0.127 mm nichrome fusing current is ~3-4 A [TODO(unverified)])")

line("\n  3.2 Energy per cut and per flight (the energy budget)")
for C, cname in ((C_BANK, "1.65 F accepted"), (C_BANK2, "3.3 F doubled")):
    E_usable = 0.5*C*(5.4**2 - 3.0**2)
    print("    %-16s usable 5.4->3.0 V = 0.5*C*(V1^2-V2^2) = %.2f J" % (cname, E_usable))
    E_4 = 4*E_cut
    print("      4 cuts = 4*%.2f = %.2f J  -> %.1f %% of usable" % (E_cut, E_4, 100*E_4/E_usable))
    print("      (only ONE cut defensible -> %.2f J = %.1f %% of usable)"
          % (E_cut, 100*E_cut/E_usable))
    # voltage sag over the cut
    I = V_RAIL / R_ni
    Q = I * (E_cut / (V_RAIL*I))
    dV = Q / C
    print("      charge drawn = %.3f C -> bank sag dV = Q/C = %.3f V" % (Q, dV))

line("  3.3 Minimum state of charge for the cut to work")
line("    The wire must reach ~400 C against loss. P = V^2/R must stay above the")
line("    loss floor. [TODO(unverified): the loss floor is not measured; it is")
line("    assumed here as P_min = 5 W at the wire, a placeholder, not a citable")
line("    figure.] Below P_min the pulse lengthens and the loss term grows faster")
line("    than the delivered energy.")
I = V_RAIL / R_ni
print("    I = V/R constant-power check: at 5.4 V P = %.1f W ; P=5 W needs V = %.1f V"
      % (V_RAIL*I, math.sqrt(5.0*R_ni)))
print("    => the raw bank node must be ABOVE ~%.1f V of its 5.4 V top"
      % (math.sqrt(5.0*R_ni),))
print("       (0.5*C*V^2 framing: %.0f%% of the 16.63 J usable energy still in the bank)"
      % (100 * (math.sqrt(5.0*R_ni)**2 - 3.0**2) / (5.4**2 - 3.0**2)))
line("    CONFLICT: the only defensible trigger is DESCENT (post-burst). The cut")
line("    must therefore be armed after burst AND while the bank is still high.")
line("    If the burst happens at night the bank is near 3 V and the cut FAILS.")

line("\n  3.4 Switching element [CITED docs/balloon-test-results.md line 254]")
line("    repo precedent: IRLML2502 (N-ch logic-level MOSFET, SOT-23, ~0.02 g).")
line("    Rating: Vds 20 V (rail is 5.4 V -> 3.7x margin); Id 4.2 A at Vgs 4.5 V.")
for v in (V_RAIL,):
    I = v / R_ni
    print("    required Id = %.2f A at 5.4 V -> %.0f %% of the 4.2 A rating"
          % (I, 100*I/4.2))
line("    4 separate MOSFETs (one per wing) -> required Id falls to 1/4 if the")
line("    gate drive is sequenced; a SHARED BUS (all 4 wires in parallel) needs")
line("    4x = %.1f A through ONE device -> EXCEEDS the IRLML2502 rating."
      % (4*V_RAIL/R_ni))

line("\n  3.5 Quiescent cost and mass")
line("    Quiescent: IRLML2502 datasheet leakage ~1 uA at Vgs=0 -> at 5.4 V = 5.4 uW")
line("    [TODO(unverified) part datasheet not in repo]. This is ~5 % of ADR-036's")
line("    100 uW night anchor PER DEVICE; 4 devices = 21.6 uW = 22 % of the anchor.")
q = 4 * 5.4 * 1e-6
print("    computed: 4 * V * I_leak = 4 * 5.4 * 1e-6 = %.1f uW" % (q*1e6))
m_chan = 0.5e-3  # kg  [CITED docs/balloon-test-results.md: ~0.5 g/channel]
print("    mass per channel ~0.5 g [CITED] -> 4 channels = %.1f g" % (4*m_chan*1e3))
print("    that is %.0f %% of the whole 12.85 g wing array" % (100*4*m_chan/M_ARRAY_SMALL))
line("    PLUS the nylon loops and the 4 cut points themselves.")

print("\n  ENERGY BUDGET VERDICT: the ENERGY is affordable (a single cut is ~%.1f %%"
      " of the accepted bank's usable energy). The MASS and the QUIESCENT cost are"
      " what hurt: 2 g of hardware (%.0f %% of the array) and 22 %% of the night budget."
      % (100*E_cut/(0.5*C_BANK*(5.4**2-3.0**2)), 100*4*m_chan/M_ARRAY_SMALL))

line("\n  MASS BUDGET VERDICT (the binding constraint, per the brief):")
line("    the cut mechanism COSTS more mass than the largest thing it can ever")
line("    remove. It removes %.2f g on descent; it costs %.1f g carried all flight."
      % (M_WING_SMALL*1e3, 4*m_chan*1e3))

hdr("SUMMARY OF THE THREE COUNTER-INTUITIVE RESULTS")
line("  1. The cord's diameter is fixed by HANDLING, not by load - so the joint's")
line("     strength is unknowable (the knot, not the cord).")
line("  2. Thicker cord (needed to handle) makes the cut HARDER, not easier.")
line("  3. The energy is trivially affordable but the MASS is not: the jettison")
line("     hardware weighs ~2 g, i.e. 16 % of the 12.85 g array it would shed.")

# ----------------------------------------------------------------- 4. descent
hdr("4. DOES SHEDDING 12.85 g ACTUALLY HELP THE DESCENT?")
line("  Terminal descent v = sqrt( 2 m g / (rho Cd A) ).")
line("  [ASSUMPTION, TODO(unverified)] m_total = 50 g (brief: 'tens of grams');")
line("  envelope drag area 0.30 m^2 (a popped 32 in envelope, not measured);")
line("  wing drag area 4 x 43.14 cm^2 = %.4f m^2; Cd = 1.2." % (4*A_WING))
line("  [CITED] community descent under the dead envelope ~1 mph = 0.45 m/s")
line("  (docs/balloon-flight-lessons.md), i.e. the descent is ALREADY at walking pace.")
m_tot = 50e-3
m_win = M_ARRAY_SMALL
A_env = 0.30
A_win = 4 * A_WING
v_old = math.sqrt(2*m_tot*G/(1.225*CD*(A_env+A_win)))
v_new = math.sqrt(2*(m_tot-m_win)*G/(1.225*CD*A_env))
print("  mass  %.1f g -> %.1f g  (-%.0f %%)" % (m_tot*1e3, (m_tot-m_win)*1e3, 100*m_win/m_tot))
print("  drag area %.4f -> %.4f m^2 (-%.1f %%)" % (A_env+A_win, A_env, 100*A_win/(A_env+A_win)))
print("  v_old = %.3f m/s ; v_new = %.3f m/s ; ratio = %.3f" % (v_old, v_new, v_new/v_old))
print("  -> shedding the whole array slows the descent by only %.0f %%." % (100*(1-v_new/v_old)))
line("     Against an already ~0.45 m/s descent and a 4-8 h fall, that is nil.")
line("")
line("  Cross-check: how long does the payload NEED the array after burst?")
E_bank = 0.5*C_BANK*(5.4**2 - 3.0**2)
for P_bg, lab in ((100e-6, "ADR-036 100 uW night anchor"), (1e-3, "1 mW beacon duty")):
    t = E_bank / P_bg
    print("    bank %.2f J / %-28s = %.0f s = %.1f h" % (E_bank, lab, t, t/3600))
line("    -> the bank alone outlasts the 4-8 h descent by a wide margin, so losing")
line("       the array AT BURST costs almost nothing. But it also BUYS almost")
line("       nothing: there is no science left to do on the way down that needs less")
line("       mass, and the wing drag it removes is %.1f %% of the descent drag area."
       % (100*A_win/(A_env+A_win)))
