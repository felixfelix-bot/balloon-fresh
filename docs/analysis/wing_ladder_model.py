#!/usr/bin/env python3
"""Wing progressive-shed ladder — reproducible model.

STATUS: CONSULTANT ANALYSIS, not a decision record.

Prints every number quoted in docs/analysis/wing-ladder.md. Run:

    python3 docs/analysis/wing_ladder_model.py

No dependency beyond the stdlib. No measurement is performed.
Constants are either CITED (source named) or marked TODO(unverified).
"""

import math

# ----------------------------------------------------------------------------
# 0. Inputs (cited)
# ----------------------------------------------------------------------------

# Wing masses, small-cell build, from docs/analysis/wing-mass-shape.md §1.4
WING_SPINE = 3.212      # g, spine+ribs, 3 small cells            (CITED)
WING_FULL = 7.300       # g, full 0.6 mm FR4 carrier, 3 small     (CITED)
ARRAY_SPINE = 12.846    # g, 4-wing array                          (CITED)
ARRAY_FULL = 29.201     # g, 4-wing array                          (CITED)

# Wing masses, large-cell build (ADR-049 preferred), spine+ribs short-and-wide
WING_LARGE_SPINE = 6.883  # g (mass-shape §3.1 "short+wide")       (CITED)

# Payload mass band.  The repo has NO v9 all-up mass:
# docs/POWER-BUDGET-V9-D2BE.md:188 "Total mass cannot be stated" (11/13 lines TODO).
# Historical/representative figures: minimal tracker 9 g, Mesh V1 14 g, Mesh V2 22 g
# (docs/balloon-flight-lessons.md §Success Factor #6); literature 12-30 g.
PAYLOAD_MID = 20.0      # g, mid-band figure this analysis uses  TODO(unverified)
BALLOON_ENVELOPE = 10.5 # g, DecoGlee 18" foil envelope          (CITED balloon-test-results.md)

# Array electricals
V_NOM = 6.0             # V, 12 cells in series (4 wings x 1.5 V)  (CITED ADR-006)
V_WING = 1.5            # V per wing                                (CITED)
RADIO_MAX_W = 6.15      # W, F33 max DC draw at 5.5 V              (CITED ADR-047 §1.2)
BANK_USABLE_J = 33.264  # J, doubled 3.3 F bank, 5.4 -> 3.0 V      (CITED ADR-047 §3.2)
BANK_V_TOP = 5.4        # V                                        (CITED ADR-006/047)
BAT54_DROP = 0.3        # V                                        (CITED wing-electrical §5.1)

# Peak power, both builds
P_LARGE_ARRAY = 6.0 * 1.2   # W  = 7.2 W  (CITED ADR-049 Decision)
P_SMALL_ARRAY = 6.0 * 0.4   # W  = 2.4 W  (CITED ADR-006)

# Cell areas
A_WING_LARGE = 3 * 78.55 * 38.90 / 100.0   # cm^2 per wing
A_WING_SMALL = 3 * 52.07 * 19.65 / 100.0   # cm^2 per wing

# Cut-down channel precedent
JUNCTION_MASS = 0.5     # g per cut channel: MOSFET+nichrome+nylon
                        # (CITED docs/balloon-test-results.md:253)
BYPASS_DIODE_MASS = 0.02  # g, SS24/PMEG4020ER class (SOD-323 ~10 mg, SMA ~30 mg)

# Stratosphere
SCALE_HEIGHT = 6500.0   # m, ~stratospheric density scale height (assumption)
G = 9.81

def line(t=""):
    print(t)

def frac(part, whole):
    return part / whole

# ----------------------------------------------------------------------------
# 1. MASS ECONOMICS
# ----------------------------------------------------------------------------
line("=" * 74)
line("1. MASS ECONOMICS")
line("=" * 74)

STACK = PAYLOAD_MID + BALLOON_ENVELOPE   # g, descent-relevant total
line(f"payload mid-band used        = {PAYLOAD_MID:.2f} g   TODO(unverified)")
line(f"balloon envelope (DecoGlee)  = {BALLOON_ENVELOPE:.2f} g  (CITED)")
line(f"stack (payload+envelope)     = {STACK:.2f} g")
line()

for name, w in (("spine+ribs", WING_SPINE), ("full carrier", WING_FULL),
                ("large-cell spine", WING_LARGE_SPINE)):
    line(f"  shed {name:18s} {w:6.3f} g = {100*frac(w,PAYLOAD_MID):5.2f} % of payload"
         f"  | {100*frac(w,STACK):5.2f} % of stack")
line()

# --- float altitude --------------------------------------------------------
line("FLOAT ALTITUDE (superpressure / constant-volume balloon):")
line("  equilibrium: rho_air(h) * V * g = m_total * g  ->  rho_air ~ m_total")
line("  rho(h) = rho0 * exp(-h/H)  =>  -dh/H = -dm/m  =>  dh = H * dm/m")
for name, w in (("spine+ribs", WING_SPINE), ("full carrier", WING_FULL)):
    dh = SCALE_HEIGHT * w / STACK
    line(f"  {name:18s}: dH = {SCALE_HEIGHT:.0f} m x {w:.3f}/{STACK:.1f}"
         f" = {dh:7.1f} m  (UPWARD)")
line("  NOTE: a zero-pressure (vented) balloon instead vents gas -> altitude")
line("  unchanged.  Either way the shed CANNOT lower the altitude.")
line()

# --- descent rate ----------------------------------------------------------
line("DESCENT RATE (terminal, drag-limited):")
line("  m g = 0.5 rho Cd A v^2  =>  v = sqrt(2 m g / (rho Cd A))")
line("  d(ln v) = 0.5 d(ln m)  ->  %dv = 0.5 * %dm   (rho, Cd, A cancel)")
V_REF = 0.447           # m/s, ~1 mph  (CITED balloon-flight-lessons.md:472)
line(f"  reference descent rate = {V_REF} m/s (Ruthroff '~1 mile per hour')")
for name, w in (("spine+ribs", WING_SPINE), ("full carrier", WING_FULL)):
    dm_frac = w / STACK
    dv_frac = 0.5 * dm_frac
    dv = V_REF * dv_frac
    t0 = 12000.0 / V_REF / 3600.0
    t1 = 12000.0 / (V_REF - dv) / 3600.0
    line(f"  {name:18s}: dm/m={100*dm_frac:5.2f}% -> dv/v={100*dv_frac:5.2f}%"
         f" -> v {V_REF:.3f}->{V_REF-dv:.3f} m/s ; 12 km fall"
         f" {t0:5.2f}->{t1:5.2f} h ( +{60*(t1-t0):4.0f} min )")
line()

# ----------------------------------------------------------------------------
# 2. POWER COST
# ----------------------------------------------------------------------------
line("=" * 74)
line("2. POWER COST OF SHEDDING")
line("=" * 74)
line(f"large-cell wing cell area  = 3 x 78.55 x 38.90 mm = {A_WING_LARGE:6.2f} cm^2")
line(f"large-cell array cell area = 4 x above           = {4*A_WING_LARGE:6.2f} cm^2")
line(f"small-cell wing cell area  = 3 x 52.07 x 19.65   = {A_WING_SMALL:6.2f} cm^2")
line(f"small-cell array cell area                        = {4*A_WING_SMALL:6.2f} cm^2")
line(f"AREA SHED PER WING = 1/4 = 25.0 %  (both builds)")
line()
line("Series string: power = sum(V) x I ; I set by the weakest wing.")
line(f"  large build  4 wings: {V_NOM:.1f} V x 1.2 A = {P_LARGE_ARRAY:.2f} W peak")
for k in (3, 2, 1):
    v = k * V_WING
    p = v * 1.2
    line(f"    after {4-k} cut(s), {k} wing(s): {v:.1f} V x 1.2 A = {p:4.2f} W"
         f"  ({100*p/P_LARGE_ARRAY:5.0f}% of peak)"
         f"  vs radio {RADIO_MAX_W} W -> {'ABOVE' if p>RADIO_MAX_W else 'BELOW'}")
line(f"  small build  4 wings: {V_NOM:.1f} V x 0.4 A = {P_SMALL_ARRAY:.2f} W peak "
     f"(already {RADIO_MAX_W/P_SMALL_ARRAY:.2f}x BELOW the radio's {RADIO_MAX_W} W)")
line()
line("Charging ceiling of the bank: needs V_mp > V_bank + BAT54 drop")
V_FLOOR = BANK_V_TOP + BAT54_DROP
line(f"  floor to charge 5.4 V bank = {BANK_V_TOP} + {BAT54_DROP} = {V_FLOOR:.1f} V")
for k in (4, 3, 2, 1):
    v = k * V_WING
    ceiling = min(v - BAT54_DROP, BANK_V_TOP)   # bank tops out at 5.4 V
    usable = 0.5 * 3.3 * (ceiling**2 - 3.0**2) if ceiling > 3.0 else 0.0
    ok = "charges" if v > V_FLOOR else "CANNOT charge to top"
    line(f"  {k} wing(s) = {v:.1f} V -> bank ceiling {ceiling:.1f} V"
         f" -> usable {usable:6.2f} J ({100*usable/BANK_USABLE_J:4.0f}%)  [{ok}]")
line()

# ----------------------------------------------------------------------------
# 3. SERIES-STRING PROBLEM
# ----------------------------------------------------------------------------
line("=" * 74)
line("3. SERIES-STRING PROBLEM")
line("=" * 74)
line("Four wings in ONE series string (ADR-046 §2.3): stack_top W1.P ... W4.N.")
line("Physically cutting one wing away = OPEN CIRCUIT -> string current = 0")
line("  => array output falls to 0 W, NOT to 3/4 = 5.4 W.")
line("A bypass path across the removed wing's terminals is MANDATORY to keep")
line("the remaining string alive.")
line()
line("Hardware options per junction (each wing-slot junction on the hub):")
line("  (i)  passive Schottky across SOLAR_P-SOLAR_N, fitted  -> 1 device")
line("       = exactly the D_BP provision ADR-046 §2.3 already specifies (DNP)")
line(f"       mass ~{BYPASS_DIODE_MASS*1000:.0f} mg ; must be rated >=2 A / 40 V (ADR-049)")
line("  (ii) shorting MOSFET (normally-OFF) + control line  -> needs 1 MOSFET")
line("       PLUS a sense/trigger that survives the cut; a single 2-terminal")
line("       MOSFET cannot both pass the wing's own current and bypass it.")
line("  (iii) make-before-break connector -> mechanical, no active part.")
line()
line("=> a SINGLE MOSFET per junction (the operator's proposal) is NOT sufficient.")
line("   Minimum passive part: 1 Schottky. If active gating is wanted: 2 devices")
line("   (1 series pass MOSFET + 1 bypass Schottky) + a surviving gate drive.")
line()
line("Topology that is electrically clean: keep the string whole and BYPASS each")
line("level (option i). Making each hanging level a PARALLEL group instead gives")
line(f"   {V_WING:.1f} V total from N groups in parallel, vs {V_NOM:.1f} V series")
line(f"   cost = a {V_NOM/V_WING:.0f}x voltage collapse, far below the {V_FLOOR:.1f} V")
line("   charge floor -> needs a boost converter, which ADR-047 refuses.")
line()

# ----------------------------------------------------------------------------
# 4. SHADING PENALTY
# ----------------------------------------------------------------------------
line("=" * 74)
line("4. SHADING PENALTY OF A HANGING CHAIN")
line("=" * 74)
H_NOON = 16.56          # deg, 50 N winter solstice noon (wing-insolation §1)
line(f"winter noon elevation h = {H_NOON} deg at 50 N ; tan h = {math.tan(math.radians(H_NOON)):.4f}")
line("model: ray drops s between levels, drifting horizontally dx = s / tan(h).")
line("  shadow of the upper plate (width W) lands on the lower plate offset dx.")
line("  shaded fraction f = max(0, 1 - s/(W tan h))   [worst case: sun in chain plane]")
for label, W in (("small wing W=176 mm (long axis horizontal)", 176.0),
                 ("small wing W=25 mm (long axis vertical)", 25.0)):
    line(f"\n  {label}")
    for h in (16.56, 10.0, 5.0, 2.0):
        th = math.tan(math.radians(h))
        s10 = 0.9 * W * th
        s0 = W * th
        line(f"    h={h:5.2f} deg:  s for f<=10% = {s10:6.1f} mm ; s for f=0 = {s0:6.1f} mm")
line()
line("Chain length and pendulum effect (n=4 levels, board height t=25 mm, W=176 case):")
for s in (47.1, 100.0):
    L = 3 * s + 4 * 25.0
    Lm = L / 1000.0
    T = 2 * math.pi * math.sqrt(Lm / G)
    line(f"  spacing {s:5.1f} mm -> chain length {L:6.1f} mm ->"
         f" pendulum period T = 2pi sqrt(L/g) = {T:.2f} s")
line("  (current coplanar cross has a vertical extent ~25 mm; T ~ 0.45 s)")
line()
line("Swing moment of inertia about the suspension point, 4 equal masses m=3.212 g")
line("  I = sum m r_i^2 ,  r_i = d0 + k*s  (d0 = 0.10 m suspension, s = 47.1 mm)")
m = WING_SPINE / 1000.0
for d0, s in ((0.10, 0.0471), (0.10, 0.0)):
    rs = [d0 + k * s for k in range(4)]
    I = m * sum(r * r for r in rs)
    line(f"  d0={d0*1000:.0f} mm s={s*1000:5.1f} mm -> r={['%.3f'%r for r in rs]}"
         f" -> I = {I:.3e} kg m^2")
line("  (a compact 4-arm cross at ~0.09 m arm radius is I ~ 1.4e-4 kg m^2, per")
line("   wing-mass-shape §3.1: 4 x 3.662e-5)")
line()

# ----------------------------------------------------------------------------
# 5. MECHANICAL / FLIGHT RISKS — junction mass ledger
# ----------------------------------------------------------------------------
line("=" * 74)
line("5. ADDED MASS PER JUNCTION")
line("=" * 74)
conn = 0.20   # g, 4-way flexible interconnect across a hanging junction (ESTIMATE)
jboard = 0.15 # g, small junction carrier board carrying cutter+diode (ESTIMATE)
per_j = JUNCTION_MASS + BYPASS_DIODE_MASS + conn + jboard
line(f"  cut channel (MOSFET+nichrome, CITED)      {JUNCTION_MASS:5.2f} g")
line(f"  bypass Schottky                           {BYPASS_DIODE_MASS:5.2f} g")
line(f"  4-way flexible interconnect  ESTIMATE     {conn:5.2f} g")
line(f"  junction carrier board       ESTIMATE     {jboard:5.2f} g")
line(f"  PER JUNCTION TOTAL                        {per_j:5.2f} g")
for n_j, cut in ((1, 1), (3, 3)):
    add = n_j * per_j
    net = cut * WING_SPINE - add
    line(f"  {n_j} junction(s) carried -> +{add:.2f} g all flight;"
         f" shed {cut}x{WING_SPINE:.3f}={cut*WING_SPINE:.2f} g ->"
         f" net {net:+.2f} g")
line()
line("=" * 74)
line("6. OPTION MASS LEDGER")
line("=" * 74)
line(f"(a) progressive ladder  : array {ARRAY_SPINE:.2f} g + 3 junctions {3*per_j:.2f} g"
     f" ; max shed 3x{WING_SPINE:.3f} = {3*WING_SPINE:.2f} g, only after 3 cuts")
line(f"(b) single cut whole array: array {ARRAY_SPINE:.2f} g + 1 junction {per_j:.2f} g")
line(f"(c) stowed+deployed      : array {ARRAY_SPINE:.2f} g + hinges/latches (unquantified)")
line(f"(d) lighter frame (ADR-049 spine+ribs, no hardware): array {ARRAY_SPINE:.2f} g"
     f"  vs full carrier {ARRAY_FULL:.2f} g  =  {ARRAY_FULL-ARRAY_SPINE:+.2f} g saved, pre-flight")
line(f"(e) do nothing           : array {ARRAY_FULL:.2f} g if a full carrier is kept")
line()
line("KEY: option (d) saves 16.35 g BEFORE LAUNCH with zero hardware, zero actuators,")
line("zero strings and zero cut risk -- 1.27x the ENTIRE 4-wing array's mass.")
line("=" * 74)
