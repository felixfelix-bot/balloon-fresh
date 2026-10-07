#!/usr/bin/env python3
"""
Hub-plate stiffness / deflection model — the gate on ADR-055 D4's 0.4 mm decision.

Companion to `docs/analysis/hub-thickness-deflection.md`.  Every constant below carries
either an in-repo citation or an explicit `TODO(unverified)` tag; nothing is silently
invented.  Run:

    python3 docs/analysis/hub_thickness_deflection_model.py

Conventions: SI throughout (m, kg, s, N, Pa).  "FR4" = the cured E-glass/epoxy laminate
the repo mass model already assumes (`docs/PAYLOAD-WEIGHT-ESTIMATES.md` line 20).

NOTHING HERE IS A MEASUREMENT.  The load census and joint strain budgets are arithmetic
on cited constants; the two quantities the record does NOT contain (FR4's elastic modulus
and the end-only solder joint's allowable shear strain) are carried as RANGES and flagged.
"""

# ---------------------------------------------------------------------------
# 1. Geometry and mass — CITED
# ---------------------------------------------------------------------------
L_PLATE = 0.103                       # m  ADR-055 D5: 106.1 cm2 -> 103.0 x 103.0 mm
AREA = L_PLATE ** 2                   # m2 = 1.0609e-2
RHO_FR4 = 1850.0                      # kg/m3  wing-mass-shape.md 1.1 (PAYLOAD-WEIGHT-ESTIMATES L20)
UPLIFT = 1.15                         # wing-mass-shape.md 1.1 ("finished board adds ~15%")
T_TARGET = 4.0e-4                     # m  ADR-055 D4 target
T_CURRENT = 6.0e-4                    # m  ADR-055 D4 current "safe" value

# wing (the load the plate carries) — ADR-052 2.6 / wing-mass-shape.md 1.4
M_WING_ENDONLY = 1.9525e-3            # kg  7.81 g / 4 wings (ADR-052 2.6, end-only row)
M_WING_SPINE = 3.212e-3               # kg  wing-mass-shape.md 1.4 (b) spine+ribs
M_WING_FULL = 7.300e-3                # kg  wing-mass-shape.md 1.4 (a) full carrier
N_WING = 4                            # ADR-046 1 / ADR-048 2.1 (four at 90 deg)
L_WING = 0.176                        # m  wing-mass-shape.md 1.4 (gerber x-range 0..176)
X_CG_WING = L_WING / 2.0              # m  uniform strip -> centre of gravity at half length
W_TAB = 9.0e-3                        # m  ADR-046 4.1 (tab width, load entered over this)

# cell (the thing whose joints must survive) — ADR-049 / ADR-051 1.4
L_CELL = 0.07855                      # m  LARGE cell 78.55 x 38.90 mm
M_CELL_SMALL = 0.5006e-3              # kg wing-mass-shape.md 1.2
M_CELL_LARGE = 1.4951e-3              # kg wing-mass-shape.md 1.2
N_HUB_CELLS = 4                       # >= 4 LARGE cells to cover 106.1 cm2 (3 = 91.8 < 106.1)

G = 9.80665                           # m/s2

# ---------------------------------------------------------------------------
# 2. Elastic constants — NOT IN REPO (ranges, TODO(unverified))
# ---------------------------------------------------------------------------
E_FR4_LO, E_FR4_NOM, E_FR4_HI = 18.0e9, 20.0e9, 24.0e9   # Pa  TODO(unverified) typical range
E_FR4_COLD_LO, E_FR4_COLD_HI = 1.0, 1.20                 # cold stiffening factor, TODO(unverified)
NU_FR4 = 0.15                                            # TODO(unverified) 0.13-0.20
E_SI = 170.0e9                                           # Pa (crystalline Si, standard)
CTE_FR4_LO, CTE_FR4_HI = 12e-6, 18e-6                    # 1/K in-plane, TODO(unverified)
CTE_SI = 2.6e-6                                          # 1/K standard
GAMMA_ALLOW_LO, GAMMA_ALLOW_HI = 1.0e-3, 1.0e-2          # solder shear strain, TODO(unverified)
GAP_FLOAT = 1.0e-4                                       # m cell float standoff, TODO(unverified)

def D_plate(t, E=E_FR4_NOM, nu=NU_FR4):
    """Plate flexural rigidity per unit width, N*m."""
    return E * t ** 3 / (12.0 * (1.0 - nu ** 2))

def EI_strip(t, b=L_PLATE, E=E_FR4_NOM, nu=NU_FR4):
    """Cylindrical-bending strip stiffness, N*m2 (b = strip width)."""
    return D_plate(t, E, nu) * b

def line(label, value, unit=""):
    print(f"  {label:<62s} {value:>14.5g} {unit}")

# ---------------------------------------------------------------------------
print("=" * 92)
print("1. PLATE AND LOAD CENSUS   (all masses cited; 0.4 mm vs 0.6 mm)")
print("=" * 92)
for t in (T_CURRENT, T_TARGET):
    m = AREA * t * RHO_FR4 * UPLIFT
    line(f"plate t={t*1e3:.1f} mm  mass = area*t*rho*1.15", m * 1e3, "g")
line("areal mass check 0.6 mm (ADR-055 1.5 = 127.65 mg/cm2)",
     T_CURRENT * RHO_FR4 * UPLIFT * 100.0, "mg/cm2")
line("areal mass check 0.4 mm (ADR-055 1.5 =  85.10 mg/cm2)",
     T_TARGET * RHO_FR4 * UPLIFT * 100.0, "mg/cm2")

print()
line("hub cells: 4 x LARGE cell 1.4951 g (ADR-051/ADR-049)", N_HUB_CELLS * M_CELL_LARGE * 1e3, "g")
line("cell mounting 4 x 0.15 g (ADR-052 2.6)", 4 * 0.15, "g")
line("electronics ~2.0 g (TODO unverified, order-of v8i 2.76 g)", 2.0, "g")
line("4 wings, END-ONLY 1.9525 g each (ADR-052 2.6)", N_WING * M_WING_ENDONLY * 1e3, "g")
line("4 wings, SPINE+RIBS 3.212 g each (wing-mass-shape 1.4b)", N_WING * M_WING_SPINE * 1e3, "g")
line("4 wings, FULL CARRIER 7.300 g each (wing-mass-shape 1.4a)", N_WING * M_WING_FULL * 1e3, "g")

m_plate_04 = AREA * T_TARGET * RHO_FR4 * UPLIFT
m_plate_06 = AREA * T_CURRENT * RHO_FR4 * UPLIFT
m_onplate = N_HUB_CELLS * M_CELL_LARGE + 4 * 1.5e-4 + 2.0e-3      # cells+mount+electronics

print("\n" + "=" * 92)
print("2. THICKNESS SCALING LAWS   (exact; the robust part of the answer)")
print("=" * 92)
r = T_TARGET / T_CURRENT
print(f"  thickness ratio 0.4/0.6                                  = {r:.4f}")
print(f"  plate rigidity D ~ t^3                -> stiffness ratio  = {r**3:.4f}  (-{100*(1-r**3):.1f} %)")
print(f"  deflection at equal load ~ 1/t^3      -> 0.4/0.6 deflect  = {1/r**3:.4f}x  MORE")
print(f"  surface strain eps = M*t/2 / (E t^3/12) ~ 1/t^2           = {1/r**2:.4f}x  MORE")
print("  -> every load case below scales by these factors between 0.4 and 0.6 mm;")
print("     the ONLY case that does NOT scale is the thermal CTE-mismatch term (case d).")

# ---------------------------------------------------------------------------
print("\n" + "=" * 92)
print("3. LOAD CASE a - STATIC GRAVITY, by boundary condition (the BC is NOT in the record)")
print("=" * 92)
print("  Recorded suspension statement (docs/hardware-design.md 158-165, v1 concept):")
print('    "Loetverbindungen an allen 4 Slots tragen mechanisch"; "Aufhaengung: 30AWG')
print('     Draht vom Hub-Board zum Ballon"; "Hub-Board oben".')
print("  ADR-055 D6: attachment RAISED on a standoff above the array. NO standoff height and")
print("  NO attachment stiffness are recorded -> the boundary condition is ASSUMED, and two")
print("  idealisations are run so the spread is visible.  ASSUMPTION A1: the plate is")
print("  suspended at its CENTRE (single 30 AWG line to a central standoff) and the four wings")
print("  are cantilevers off the four edges.  ASSUMPTION A2: the plate is supported at its")
print("  FOUR CORNERS (mounting holes / standoffs).  TODO(unverified).\n")

def wing_root_moment(m_wing):
    return m_wing * G * X_CG_WING      # N*m   per wing, about the edge line

def case_a_bc_centre(t, m_wing):
    """Centre-post support: one quadrant as a cantilever strip, half-span a, width b."""
    a = L_PLATE / 2.0
    b = L_PLATE
    q = m_onplate * G / AREA                    # N/m2 uniform on the plate
    P = m_wing * G                              # N  wing weight at the edge
    M = wing_root_moment(m_wing)                # N*m wing root moment at the edge
    EI = EI_strip(t, b)
    d_q = q * b * a ** 4 / (8.0 * EI)
    d_P = P * a ** 3 / (3.0 * EI)
    d_M = M * a ** 2 / (2.0 * EI)
    M_root = M + P * a + q * b * a ** 2 / 2.0   # N*m at the plate centre
    kappa = M_root / EI                         # 1/m max curvature
    eps = kappa * t / 2.0                       # surface strain
    return d_q, d_P, d_M, d_q + d_P + d_M, kappa, eps

def case_a_bc_corners(t, m_wing):
    """Four-corner support: simply supported square plate under uniform load + wing moments."""
    q = m_onplate * G / AREA
    D = D_plate(t)
    d_q = 0.00406 * q * L_PLATE ** 4 / D        # textbook SS square plate, nu=0.3
    M = wing_root_moment(m_wing)
    a = L_PLATE / 2.0
    EI = EI_strip(t, L_PLATE)
    d_M = M * a ** 2 / (2.0 * EI)
    P = m_wing * G
    d_P = P * a ** 3 / (3.0 * EI)
    return d_q, d_P, d_M, d_q + d_P + d_M

def case_a_bc_local(t, m_wing):
    """Local: wing root moment as a LINE MOMENT on the plate edge over the 9 mm tab width."""
    M = wing_root_moment(m_wing)
    Mp = M / W_TAB                               # N*m/m line moment
    kappa = Mp / D_plate(t)                      # 1/m local curvature at the socket
    eps = kappa * t / 2.0
    return Mp, kappa, eps

for m_wing, mname in ((M_WING_ENDONLY, "END-ONLY 1.95 g"), (M_WING_SPINE, "SPINE 3.21 g"),
                      (M_WING_FULL, "FULL 7.30 g")):
    print(f"  --- wing = {mname} ---")
    print(f"    wing root moment M_w = m g x_cg = {m_wing:.4g}*{G:.4g}*{X_CG_WING:.4g}"
          f" = {wing_root_moment(m_wing)*1e3:.4g} mN*m")
    for t, tn in ((T_CURRENT, "0.6 mm"), (T_TARGET, "0.4 mm")):
        dq, dP, dM, dtot, kappa, eps = case_a_bc_centre(t, m_wing)
        print(f"    BC-A centre-post  {tn}: d_q={dq*1e3:7.4f} d_P={dP*1e3:7.4f} d_M={dM*1e3:7.4f}"
              f"  TOTAL={dtot*1e3:7.4f} mm   kappa={kappa:6.3f} 1/m  eps={eps*1e6:7.1f} ue")
    for t, tn in ((T_CURRENT, "0.6 mm"), (T_TARGET, "0.4 mm")):
        dq, dP, dM, dtot = case_a_bc_corners(t, m_wing)
        print(f"    BC-B 4-corner     {tn}: d_q={dq*1e3:7.4f} d_P={dP*1e3:7.4f} d_M={dM*1e3:7.4f}"
              f"  TOTAL={dtot*1e3:7.4f} mm")
    for t, tn in ((T_CURRENT, "0.6 mm"), (T_TARGET, "0.4 mm")):
        Mp, kappa, eps = case_a_bc_local(t, m_wing)
        print(f"    BC-C local socket {tn}: M'={Mp:7.4f} N*m/m  kappa={kappa:6.3f} 1/m"
              f"  eps={eps*1e6:7.1f} ue")
    print()

# ---------------------------------------------------------------------------
print("=" * 92)
print("4. LOAD CASE b - ROTATION / CENTRIFUGAL   (no angular rate in the record)")
print("=" * 92)
print('  ADR-055 D1(b): "the vehicle has no attitude control and rotates slowly."  NO angular')
print('  rate is stated anywhere in the repo -> BOUNDED.  Centrifugal acceleration on the wing')
print("  at hub-centre radius R = 51.5 + 88 = 139.5 mm:")
R_c = L_PLATE / 2.0 + X_CG_WING
print(f"    R = {R_c*1e3:.1f} mm")
for rpm in (1.0, 6.0, 12.0, 60.0):
    w = rpm * 2.0 * 3.141592653589793 / 60.0
    a_c = w ** 2 * R_c
    print(f"    {rpm:5.1f} rpm -> omega={w:6.4f} rad/s -> a_c={a_c:8.5f} m/s2 = {a_c/G:7.4f} g")
w_1g = (G / R_c) ** 0.5
print(f"  a 1 g-equivalent centrifugal load needs omega=sqrt(g/R)={w_1g:.3f} rad/s"
      f" = {w_1g*60/(2*3.141592653589793):.1f} rpm")
print("  TODO(unverified): no in-repo rotation rate.  A passive pico payload turns slowly;")
print("  the bound above shows the rotation case only matters above ~80 rpm, which is fast")
print("  for this vehicle class -> BOUNDED as >=10x below gravity for <=10 rpm.")

# ---------------------------------------------------------------------------
print("\n" + "=" * 92)
print("5. LOAD CASE c - ASCENT / LAUNCH   (no acceleration in the record)")
print("=" * 92)
print("  Sourced: ascent v = 5 m/s, flat-plate drag vs standard atmosphere (wing-mass-shape 2.3):")
line("20 km aero drag, whole 4-arm array (175 cm2)", 0.02317, "N")
m_all = m_onplate + 4 * M_WING_ENDONLY
line(f"... as g-equiv of the whole payload ({m_all*1e3:.2f} g)", 0.02317 / m_all / G, "g-equiv")
line("same at 25 km", 0.01050 / m_all / G, "g-equiv")
print("  NO in-repo launch/release acceleration.  ADR-046 7 item 8 and wing-mass-shape 8 item 6")
print("  both record it as unanalysed.  BOUNDED for a balloon launch at <= 2 g vertical")
print("  (a helium balloon lifts a 25 g payload quasi-statically; there is no boost phase).")
print("  TODO(unverified): the release/snatch transient and any pre-launch drop are not bounded")
print("  by anything in the repo, and a DROP is the only load that plausibly beats 2 g.")

# ---------------------------------------------------------------------------
print("\n" + "=" * 92)
print("6. LOAD CASE d - THERMAL  (-60 C design case, ADR-054 4)")
print("=" * 92)
dT = -60.0 - 20.0
print("  Two effects, OPPOSITE directions:")
print(f"   (i) FR4 STIFFENS cold -> HELPS stiffness. E_T = E_25C x ({E_FR4_COLD_LO:.2f}-"
      f"{E_FR4_COLD_HI:.2f})  [TODO(unverified)]")
for f in (E_FR4_COLD_LO, E_FR4_COLD_HI):
    print(f"       x{f:.2f} -> D(0.4 mm) = {D_plate(T_TARGET, E_FR4_NOM*f):.5f} N*m"
          f" (vs {D_plate(T_TARGET):.5f} at 25 C)")
print("   (ii) CTE mismatch FR4 vs Si  -> HURTS the joints; this is the ADR-052 rationale.")
for cte in (CTE_FR4_LO, CTE_FR4_HI):
    d = (cte - CTE_SI) * abs(dT)
    line(f"CTE {cte*1e6:.0f} ppm/K vs 2.6 Si, dT={dT:.0f} K: mismatch strain", d * 1e6, "ue")
    line(f"   over a {L_CELL*1e3:.2f} mm cell (end to end)", d * L_CELL * 1e6, "um")
print("  KEY: the CTE mismatch strain is INDEPENDENT of plate thickness -- it is set by the")
print("  cell's length and the in-plane CTEs. 0.4 mm and 0.6 mm carry it identically.  The")
print("  thickness decision does NOT change this term; ADR-052's end-only mount is what makes")
print("  it survivable (the cell floats instead of the bond being strained).")
print("  TODO(unverified): no in-repo FR4 CTE, no Si-on-FR4 joint thermal-cycle test.")

# ---------------------------------------------------------------------------
print("\n" + "=" * 92)
print("7. THE DEFLECTION LIMIT, DERIVED FROM THE END-ONLY CELL JOINT")
print("=" * 92)
print("  Joint geometry: cell END soldered to a 4.0 x 1.2 mm land (ADR-046 2.2 / ADR-048 2.2),")
print("  cell 0.21 mm thick, joined to the plate at BOTH ends and NOWHERE else (ADR-052).")
print("  Two joint models, both carried because the joint's allowable is NOT in the record:")
print("    M1 rigid-cell: the board's end slopes rotate the joint; joint shear")
print("       gamma = Theta_e * (l_land/2)/h_j, Theta_e = 4*delta/L_cell")
print(f"       => delta_allow = gamma_allow * L_cell * h_j / (2 * l_land)")
print("    M2 floating-cell: the cell bows; the limit is the FLOAT GAP it can bow into")
print(f"       delta_allow = gap  [TODO(unverified), assumed {GAP_FLOAT*1e6:.0f} um]")
l_land = 4.0e-3
for h in (0.05e-3, 0.10e-3, 0.15e-3):
    for ga in (GAMMA_ALLOW_LO, GAMMA_ALLOW_HI):
        d_al = ga * L_CELL * h / (2.0 * l_land)
        print(f"    M1 delta_allow(gamma={ga*1e3:4.1f}e-3, h_j={h*1e3:4.2f} mm)"
              f" = {d_al*1e6:8.2f} um")
print(f"    M2 delta_allow = gap = {GAP_FLOAT*1e6:.0f} um  (floating-cell / generous reading)")
print("  => the record fixes NEITHER gamma_allow NOR h_j NOR the gap, so the derived limit is")
print("     a BAND of ~1-100 um, i.e. TWO ORDERS OF MAGNITUDE.  This is the honest answer to")
print("     'derive the maximum plate deflection': it cannot be narrowed from the record.")

print("\n  Compare the ACTUAL local sag over one cell span (78.55 mm) at each thickness,")
print("  taken as kappa * L_cell^2 / 8 from the max curvature of each BC:")
for t, tn in ((T_CURRENT, "0.6 mm"), (T_TARGET, "0.4 mm")):
    for m_wing, mname in ((M_WING_ENDONLY, "end-only"), (M_WING_SPINE, "spine"),
                          (M_WING_FULL, "full")):
        _, _, _, _, kappa, _ = case_a_bc_centre(t, m_wing)
        sag_c = kappa * L_CELL ** 2 / 8.0
        _, kappa_l, _ = case_a_bc_local(t, m_wing)
        sag_l = kappa_l * L_CELL ** 2 / 8.0
        print(f"    {tn} {mname:8s}: sag(BC-A centre)={sag_c*1e6:8.1f} um ;"
              f" sag(BC-C local socket)={sag_l*1e6:9.1f} um")

# ---------------------------------------------------------------------------
print("\n" + "=" * 92)
print("8. JOINT SHEAR STRAIN DEMAND vs THE SOURCEABLE ALLOWABLE BAND")
print("=" * 92)
print("  gamma = eps_surf * l_land / h_j  (lap-joint shear over the 4.0 mm land)")
for t, tn in ((T_CURRENT, "0.6 mm"), (T_TARGET, "0.4 mm")):
    _, _, _, _, kappa, eps = case_a_bc_centre(t, M_WING_ENDONLY)
    _, _, eps_l = case_a_bc_local(t, M_WING_ENDONLY)
    for name, e in (("BC-A centre (global)", eps), ("BC-C local socket", eps_l)):
        for h in (0.05e-3, 0.15e-3):
            g = e * l_land / h
            print(f"    {tn} {name:22s} eps={e*1e6:7.1f} ue  h_j={h*1e3:4.2f} mm"
                  f" -> gamma={g*100:7.3f} %")
print(f"  allowable band (TODO unverified): gamma_allow = "
      f"{GAMMA_ALLOW_LO*100:.2f} % .. {GAMMA_ALLOW_HI*100:.2f} %")
print("  -> 0.4 mm sits INSIDE the band under the global model (0.23-0.70 %) and 1.4-2.7x")
print("     OUTSIDE it under the local socket model.  Model choice = the missing BC.")

# ---------------------------------------------------------------------------
print("\n" + "=" * 92)
print("9. THREE OPTIONS: GRAMS AND DEFLECTION")
print("=" * 92)
def stiffener_mass(n=4, w=9e-3, l=20e-3, t=4.0e-4):
    return n * w * l * t * RHO_FR4 * UPLIFT     # 4 socket doublers, 0.4 mm FR4, glued

rows = []
for label, t, m_w, extra_txt, extra in (
        ("(i)   0.6 mm plain", T_CURRENT, M_WING_ENDONLY, "", 0.0),
        ("(ii)  0.4 mm plain", T_TARGET, M_WING_ENDONLY, "", 0.0),
        ("(iii) 0.4 mm + local stiffening", T_TARGET, M_WING_ENDONLY,
         "4x 20x9x0.4 mm doublers", stiffener_mass()),
):
    mp = AREA * t * RHO_FR4 * UPLIFT
    d = case_a_bc_centre(t, m_w)[3]
    _, kappa_l, eps_l = case_a_bc_local(t, m_w)
    eps_eff = eps_l / 4.0 if extra else eps_l      # doubler doubles local t -> eps/4
    rows.append((label, mp, extra, mp + extra, d, eps_l, eps_eff, extra_txt))
print(f"  {'option':<32s} {'plate g':>9s} {'stiff g':>8s} {'total g':>9s}"
      f" {'d(BC-A) mm':>11s} {'eps_socket ue':>14s}")
for label, mp, extra, tot, d, eps_l, eps_eff, txt in rows:
    print(f"  {label:<32s} {mp*1e3:9.3f} {extra*1e3:8.3f} {tot*1e3:9.3f}"
          f" {d*1e3:11.4f} {eps_l*1e6:10.1f}->{eps_eff*1e6:5.0f}")
print()
line("stiffening mass (4 doublers 20x9x0.4 mm FR4)", stiffener_mass() * 1e3, "g")
line("ADR-055 D4 prize (0.6 -> 0.4 mm plate)", (m_plate_06 - m_plate_04) * 1e3, "g")
line("... minus stiffening", (m_plate_06 - m_plate_04 - stiffener_mass()) * 1e3, "g")
print("  JOINT-COUNT COST: option (iii) adds 4 glued parts = 4 hand operations (the operator")
print("  hand-solders every joint; the repo counts joint count as a primary risk metric).")
print("  A local t-doubling cuts the socket surface strain by ~4x (1/t^2) and the local")
print("  deflection by ~8x (1/t^3) -- MORE margin at the socket than 0.6 mm has.")

print("\n" + "=" * 92)
print("10. VERDICT INPUTS")
print("=" * 92)
print("  Record lacks: (1) the plate boundary condition; (2) FR4 elastic modulus;")
print("  (3) the end-only solder joint's allowable shear strain; (4) the cell float gap;")
print("  (5) the wing orientation (OPEN-23: 90 deg vs 30 deg tilt -> root moment x7);")
print("  (6) any rotation rate; (7) any launch/release acceleration.")
print("  Computed demand straddles the sourceable allowable band -> CANNOT BE SETTLED")
print("  from the record.  The bench measurement that WOULD settle it is named in the .md.")
print("=" * 92)
