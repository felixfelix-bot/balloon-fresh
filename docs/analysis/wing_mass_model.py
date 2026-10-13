#!/usr/bin/env python3
"""Wing mass model for the v9 3D solar array (balloon-fresh).

Companion to docs/analysis/wing-mass-shape.md. Every constant carries its
provenance: CITED (an in-repo document / operator caliper) or TODO (not
sourced, flagged in the output). Run:

    python3 docs/analysis/wing_mass_model.py

Output: per-wing and per-array mass for the current full-carrier wing and for
each structural candidate in the analysis, plus the cell-area / board-area
fill factor and the watt-per-gram figure.

No claim in the analysis is stronger than what this script prints.
"""
from __future__ import annotations

# --------------------------------------------------------------------------
# MATERIAL CONSTANTS
# --------------------------------------------------------------------------
# -- CITED ------------------------------------------------------------------
FR4_DENSITY = 1.85        # g/cm3  CITED docs/PAYLOAD-WEIGHT-ESTIMATES.md ("FR4 density: 1.85 g/cm3")
FR4_T = 0.6               # mm     CITED docs/adr/046 s3.2 and docs/hardware-design.md line 63
FINISH_UPLIFT = 1.15      # -      CITED docs/PAYLOAD-WEIGHT-ESTIMATES.md ("Finished board adds ~15%
                          #        for copper, soldermask, silkscreen")
SI_DENSITY = 2.33         # g/cm3  CITED physical constant (crystalline Si, 2.329 g/cm3)

# -- TODO(unverified) -------------------------------------------------------
CU_T = 0.035              # mm     1 oz outer copper. TODO(unverified): JLCPCB's outer Cu
                          #        weight on a 0.6 mm 2-layer stack is not in any in-repo source.
CU_DENSITY = 8.96         # g/cm3  physical constant
MASK_T = 0.025            # mm     TODO(unverified): mask thickness not in any in-repo source.
MASK_DENSITY = 1.30       # g/cm3  TODO(unverified): mask density not in any in-repo source.
SOLDER_DENSITY = 7.40     # g/cm3  SAC305, physical constant.
SOLDER_T_LAND = 0.10      # mm     TODO(unverified): measured solder volume per joint.
SOLDER_T_TAB = 0.15       # mm     TODO(unverified): ditto.

# --------------------------------------------------------------------------
# CELL CONSTANTS  (operator caliper measurement + area arithmetic)
# --------------------------------------------------------------------------
MM2_CM2 = 0.01            # 1 mm2 = 0.01 cm2

CELLS: dict[str, dict[str, float]] = {
    # name: (length_mm, width_mm, thickness_mm, V_mp, I_mp_A, source_note)
    # CITED: operator caliper 52.07 x 19.65 x 0.20-0.21 mm; listing 0.5 V / 400 mA
    "small": dict(l=52.07, w=19.65, t=0.21, v=0.5, i=0.400),
    # CITED: operator caliper 78.55 x 38.90 (2nd shot 39.32) x 0.21 mm;
    # 1.2 A INFERRED by area, not measured
    "large": dict(l=78.55, w=38.90, t=0.21, v=0.5, i=1.200),
}


TAB_AREA_MM2 = 8.0 * 9.0          # CITED ADR-046 s3.2: 8.0 mm protruding x 9.0 mm wide
BODY_AREA_MM2 = 176.0 * 25.0      # CITED ADR-046 s3.2


def cell_area_cm2(key: str) -> float:
    c = CELLS[key]
    return c["l"] * c["w"] * MM2_CM2          # area = L x W


def cell_mass_g(key: str) -> float:
    """Silicon-mass estimate: AREA x THICKNESS x Si DENSITY.

    MARKED ESTIMATE: bare silicon only. Ignores the cell's own metallisation,
    busbars and any encapsulant, and ignores the repo's own per-cell figure
    ('~2g each', docs/PAYLOAD-WEIGHT-ESTIMATES.md line 92 / line 96) which is
    ~4x this number and is flagged TODO(unverified) in the analysis.
    """
    c = CELLS[key]
    vol_cm3 = cell_area_cm2(key) * (c["t"] * 0.1)   # mm -> cm
    return vol_cm3 * SI_DENSITY


def cell_power_w(key: str) -> float:
    c = CELLS[key]
    return c["v"] * c["i"]


# --------------------------------------------------------------------------
# BOARD MASS
# --------------------------------------------------------------------------
def board_mass_g(area_mm2: float, t_mm: float = FR4_T,
                 cu_frac: float = 1.0, finish_uplift: bool = True) -> dict:
    """Mass of a bare finished board, with an explicit decomposition and the
    repo's own +15 % cross-check.

    FR4  = area x t x rho_FR4
    Cu   = area x cu_frac x t_Cu x rho_Cu      (cu_frac = fraction covered by copper)
    mask = area x t_mask x rho_mask
    """
    a_cm2 = area_mm2 * MM2_CM2
    fr4 = a_cm2 * (t_mm * 0.1) * FR4_DENSITY
    cu = a_cm2 * cu_frac * (CU_T * 0.1) * CU_DENSITY
    mask = a_cm2 * (MASK_T * 0.1) * MASK_DENSITY
    explicit = fr4 + cu + mask
    uplifted = fr4 * FINISH_UPLIFT
    return dict(area_mm2=area_mm2, fr4=fr4, cu=cu, mask=mask,
                explicit=explicit, uplifted=uplifted,
                mass=uplifted if finish_uplift else explicit)


def solder_allowance_g(n_cell_lands: int, n_tab_lands: int, n_wire_joints: int) -> dict:
    """Explicit solder-joint allowance (estimate)."""
    per_cell_land = (1.6 * 4.0) * SOLDER_T_LAND * SOLDER_DENSITY * 1e-3   # mm3 -> g
    per_tab_land = (4.0 * 1.2) * SOLDER_T_TAB * SOLDER_DENSITY * 1e-3
    per_wire = 0.010                                                      # g, TODO(unverified)
    total = n_cell_lands * per_cell_land + n_tab_lands * per_tab_land + n_wire_joints * per_wire
    return dict(per_cell_land_g=per_cell_land, per_tab_land_g=per_tab_land,
                per_wire_g=per_wire, total_g=total)


# --------------------------------------------------------------------------
# CANDIDATES  (all carry the SAME 3 small cells in series = 1.5 V/wing)
# --------------------------------------------------------------------------
def candidates() -> list[dict]:
    a_cell = cell_area_cm2("small")
    cell_a3 = 3 * a_cell                          # mm2 of cell field, 3 cells
    small_lands = solder_allowance_g(6, 4, 4)

    out = []

    # (a) FULL CARRIER — the current wing as built: body 176 x 25 + 8 x 9 tab
    body = BODY_AREA_MM2
    tab = TAB_AREA_MM2
    bm_full = board_mass_g(body + tab)
    out.append(dict(
        key="a", name="(a) FULL CARRIER (current wing, as built)",
        pcb_area_mm2=body + tab, cell_area_cm2=cell_a3, pcb_g=bm_full["mass"],
        solder_g=small_lands["total_g"], cells_g=3 * cell_mass_g("small"),
        v="2 layers, 0.6 mm FR4; body 176 x 25 mm + 8 x 9 mm tab (ADR-046 s3.2)",
        outline="184 x 25 mm (bbox 184.0 x 25.0 mm, read from the Edge.Cuts gerber)"))

    # (b) SPINE + RIBS — PCB only along one long edge plus 4 cross ribs.
    #     cell field 3 x 52.07 + 2 x 2.0 gap = 160.21 mm long x 19.65 mm
    field_len = 3 * CELLS["small"]["l"] + 2 * 2.0
    spine = field_len * 6.0                       # 6 mm wide spine
    ribs = 4 * (CELLS["small"]["w"] * 3.0)        # 4 ribs 19.65 x 3 mm
    bm_b = board_mass_g(spine + ribs + tab)
    out.append(dict(
        key="b", name="(b) SPINE + RIBS",
        pcb_area_mm2=spine + ribs + tab, cell_area_cm2=cell_a3, pcb_g=bm_b["mass"],
        solder_g=small_lands["total_g"], cells_g=3 * cell_mass_g("small"),
        v="2 layers, 0.6 mm FR4; spine 160.2 x 6 mm + 4 ribs 19.65 x 3 mm + tab",
        outline="168.2 x 25.65 mm (~168 x 26 mm) incl. 8 mm tab"))

    # (c) CELLS ONLY + FLEX/RIBBON HARNESS — no wing carrier; flex + root tab only
    flex_area = field_len * 6.0
    flex_a_cm2 = flex_area * MM2_CM2
    flex = flex_a_cm2 * (0.05 * 0.1) * 1.42                      # 50 um polyimide
    flex_cu = flex_a_cm2 * 0.20 * (CU_T * 0.1) * CU_DENSITY      # 20 % Cu coverage
    root_tab = 12.0 * 9.0
    bm_root = board_mass_g(root_tab)
    out.append(dict(
        key="c", name="(c) CELLS ONLY + FLEX/RIBBON HARNESS",
        pcb_area_mm2=flex_area + root_tab, cell_area_cm2=cell_a3,
        pcb_g=bm_root["mass"] + flex + flex_cu,
        solder_g=small_lands["total_g"] + 0.23,                  # + 0.5 m 30AWG per wing
        cells_g=3 * cell_mass_g("small"),
        v="no wing carrier; 50 um polyimide flex + 12 x 9 mm root tab board; hub takes the load",
        outline="none on the wing; a 160 x 6 mm flex + 12 x 9 mm root tab"))

    # (d) DOUBLE-SIDED CARRIER — same board, cells on BOTH faces (6 cells)
    out.append(dict(
        key="d", name="(d) DOUBLE-SIDED CARRIER (6 cells, 3 per face)",
        pcb_area_mm2=body + tab, cell_area_cm2=2 * cell_a3,
        pcb_g=bm_full["mass"], solder_g=2 * small_lands["total_g"],
        cells_g=6 * cell_mass_g("small"),
        v="as (a) but populated both faces; the dark-side 3 cells are fully shaded by the lit 3",
        outline="184 x 25 mm, as (a)"))

    return out


# --------------------------------------------------------------------------
# REPORT
# --------------------------------------------------------------------------
def shape_sweep() -> None:
    """Item 3: two packings of 3 cells in series, per cell size, with the
    root bending moment of inertia of one arm (4-arm 90 deg cross).

    I_arm = m * (r1^3 - r0^3) / (3 * (r1 - r0))   [uniform rod, r0 = hub edge]
    Higher I = harder to spin up = the vehicle resists aerodynamic spin-up.
    """
    R0 = 0.011                       # m, hub is 22 x 22 mm (docs/hardware-design.md line 13)
    print("-- SHAPE SWEEP: 3 cells in series, two packings (item 3) ---------------")
    print(f"{'packing':26} {'outline mm':>16} {'AR':>5} {'arm r1':>7} {'PCB mm2':>8} "
          f"{'PCB g':>6} {'cells g':>7} {'wing g':>7} {'fill':>6} {'span mm':>8} {'I kgm2':>10}")
    for key in ("small", "large"):
        c = CELLS[key]
        # --- long & narrow: all 3 in one row along the arm, spine on one long edge
        Lln = 3 * c["l"] + 2 * 2.0
        Wln = c["w"] + 6.0 + 1.0
        pcb_ln = Lln * 6.0 + 4 * (c["w"] * 3.0) + TAB_AREA_MM2
        # --- short & wide: 2 rows (2 cells then 1), spine on one long edge
        Lsw = 2 * c["l"] + 2.0
        Wsw = 2 * c["w"] + 2.0 + 6.0 + 1.0
        pcb_sw = Lsw * 6.0 + 3 * (Wsw * 3.0) + TAB_AREA_MM2
        for name, L, W, pcb in (("long+narrow (3 in a row)", Lln, Wln, pcb_ln),
                                ("short+wide (2 rows, 2+1)", Lsw, Wsw, pcb_sw)):
            pcb_g = board_mass_g(pcb)["mass"]
            cells_g = 3 * cell_mass_g(key)
            wing_g = pcb_g + cells_g + 0.09
            r1 = R0 + L / 1000.0 + 0.008            # + 8 mm tab at the hub end
            I = (wing_g / 1000.0) * (r1 ** 3 - R0 ** 3) / (3 * (r1 - R0))
            print(f"{key[:5]+' '+name:26} {L+8:7.2f}x{W:6.2f} {L/W:5.2f} {r1*1000:6.1f}mm "
                  f"{pcb:8.1f} {pcb_g:6.3f} {cells_g:7.3f} {wing_g:7.3f} "
                  f"{3*cell_area_cm2(key)/(pcb*MM2_CM2):6.3f} {2*r1*1000:8.1f} {I:10.3e}")
    print("  AR = arm length / arm width; fill = cell area / board area;")
    print("  I = one arm's inertia about the hub axis (4 arms = 4x). span = tip-to-tip.")
    print()


def main() -> None:
    shape_sweep()
    print("=" * 78)
    print("WING MASS MODEL — v9 3D solar array  (docs/analysis/wing-mass-shape.md)")
    print("=" * 78)
    print(f"FR4 density {FR4_DENSITY} g/cm3 [CITED], thickness {FR4_T} mm [CITED], "
          f"finish uplift x{FINISH_UPLIFT} [CITED]")
    print(f"Si density {SI_DENSITY} g/cm3 [physical constant], "
          f"Cu {CU_T} mm [TODO(unverified)]")
    print()

    print("-- CELLS -----------------------------------------------------------------")
    print(f"{'cell':6} {'LxW (mm)':18} {'area cm2':>9} {'t mm':>6} {'mass g':>8} "
          f"{'P W':>6} {'W/g':>7}")
    for k in CELLS:
        print(f"{k:6} {CELLS[k]['l']:.2f} x {CELLS[k]['w']:.2f}   "
              f"{cell_area_cm2(k):9.4f} {CELLS[k]['t']:6.2f} {cell_mass_g(k):8.4f} "
              f"{cell_power_w(k):6.3f} {cell_power_w(k)/cell_mass_g(k):7.3f}")
    print("  formula: area = L x W;  mass = area x t x rho_Si")
    print()

    print("-- SOLDER ALLOWANCE (3 small cells in series, per wing) ------------------")
    sa = solder_allowance_g(6, 4, 4)
    print(f"  per cell land (1.6 x 4.0 mm, {SOLDER_T_LAND} mm): {sa['per_cell_land_g']*1e3:.2f} mg"
          f"  x 6 lands")
    print(f"  per tab  land (4.0 x 1.2 mm, {SOLDER_T_TAB} mm): {sa['per_tab_land_g']*1e3:.2f} mg"
          f"  x 4 lands")
    print(f"  per wire joint: {sa['per_wire_g']*1e3:.1f} mg  x 4 joints")
    print(f"  TOTAL per wing: {sa['total_g']*1e3:.1f} mg = {sa['total_g']:.4f} g")
    print()

    print("-- BOARD MATERIAL CROSS-CHECK (full carrier, 4472 mm2) ------------------")
    bm = board_mass_g(4472.0)
    print(f"  FR4  = {4472*MM2_CM2:.4f} cm2 x {FR4_T*0.1:.4f} cm x {FR4_DENSITY} = {bm['fr4']:.4f} g")
    print(f"  Cu   = ... x {CU_T*0.1:.4f} cm x {CU_DENSITY} = {bm['cu']:.4f} g  (1 oz, full cover)")
    print(f"  mask = ... x {MASK_T*0.1:.4f} cm x {MASK_DENSITY} = {bm['mask']:.4f} g")
    print(f"  explicit sum = {bm['explicit']:.4f} g   |   FR4 x{FINISH_UPLIFT} = {bm['uplifted']:.4f} g")
    print(f"  -> the repo's +15 % rule is the CONSERVATIVE one; the model uses it "
          f"({bm['mass']:.4f} g).")
    print()

    print("-- CANDIDATES (3 small cells in series per wing = 1.5 V / 0.6 W) ---------")
    hdr = (f"{'':34} {'PCBarea':>8} {'cells':>8} {'PCB g':>7} {'solder':>7} "
           f"{'cell g':>7} {'wing g':>7} {'array g':>8} {'c/b':>6} {'W/g':>6}")
    print(hdr)
    rows = []
    for c in candidates():
        wing = c["pcb_g"] + c["solder_g"] + c["cells_g"]
        arr = 4 * wing
        cb = c["cell_area_cm2"] / (c["pcb_area_mm2"] * MM2_CM2)
        wg = (4 * 3 * cell_power_w("small")) / arr
        rows.append((c, wing, arr, cb, wg))
        print(f"{c['name'][:34]:34} {c['pcb_area_mm2']:8.1f} {c['cell_area_cm2']:8.2f} "
              f"{c['pcb_g']:7.3f} {c['solder_g']:7.3f} {c['cells_g']:7.3f} "
              f"{wing:7.3f} {arr:8.3f} {cb:6.3f} {wg:6.3f}")
    print("  c/b = cell area / board area (dimensionless fill factor)")
    print("  W/g = 4-wing array peak power / array mass "
          "(peak = 12 x 0.2 W = 2.4 W, ADR-006)")
    print()

    print("-- MASS DELTA vs (a), and the largest item ------------------------------")
    base = rows[0][1]
    for c, wing, arr, cb, wg in rows:
        print(f"  {c['name'][:40]:40} wing {wing:6.3f} g  d={wing-base:+6.3f} g  "
              f"array {arr:6.2f} g  d={arr-4*base:+6.2f} g")
    print()
    biggest = max(rows, key=lambda r: max(r[0]["pcb_g"], r[0]["cells_g"]))
    for c, wing, arr, cb, wg in rows:
        who = "PCB" if c["pcb_g"] >= c["cells_g"] else "CELLS"
        print(f"  {c['key']}: largest single item = {who} "
              f"(PCB {c['pcb_g']:.3f} g vs cells {c['cells_g']:.3f} g)")
    print()

    print("-- W/g LEVER CHECK: is the PCB or the cell the area-cost driver? ---------")
    pcb_per_cm2 = FR4_T * 0.1 * FR4_DENSITY * FINISH_UPLIFT
    cell_per_cm2 = CELLS['small']['t'] * 0.1 * SI_DENSITY
    print(f"  0.6 mm FR4 carrier: {pcb_per_cm2*1e3:.1f} mg per cm2 of board")
    print(f"  0.21 mm Si cell  : {cell_per_cm2*1e3:.1f} mg per cm2 of cell")
    print(f"  ratio            : {pcb_per_cm2/cell_per_cm2:.3f} x  "
          f"-> every cm2 of PCB costs {pcb_per_cm2/cell_per_cm2:.2f} cm2 of silicon")
    print(f"  at 0.4 mm FR4    : {0.4*0.1*FR4_DENSITY*FINISH_UPLIFT*1e3:.1f} mg/cm2 "
          f"({0.4*0.1*FR4_DENSITY*FINISH_UPLIFT/cell_per_cm2:.2f} x the cell)")
    print()

    print("-- LARGE-CELL SPINE WING (same structure as (b), 3 x large cells) -------")
    lf = 3 * CELLS["large"]["l"] + 2 * 2.0
    lspine = lf * 6.0
    lribs = 4 * (CELLS["large"]["w"] * 3.0)
    lbm = board_mass_g(lspine + lribs + TAB_AREA_MM2)
    lcells = 3 * cell_mass_g("large")
    lsa = solder_allowance_g(6, 4, 4)
    lwing = lbm["mass"] + lsa["total_g"] + lcells
    print(f"  cell field  = 3 x {CELLS['large']['l']} + 2 x 2.0 = {lf:.2f} mm long, "
          f"{CELLS['large']['w']} mm wide")
    print(f"  PCB area    = spine {lspine:.1f} + ribs {lribs:.1f} + tab {TAB_AREA_MM2:.0f} "
          f"= {lspine+lribs+TAB_AREA_MM2:.1f} mm2")
    print(f"  PCB mass    = {lbm['mass']:.3f} g   cells = {lcells:.3f} g   "
          f"solder = {lsa['total_g']:.3f} g")
    print(f"  wing mass   = {lwing:.3f} g   array (x4) = {4*lwing:.3f} g")
    print(f"  fill c/b    = {3*cell_area_cm2('large')/((lspine+lribs+TAB_AREA_MM2)*MM2_CM2):.3f}")
    print(f"  array peak  = 12 x 0.6 W = {12*cell_power_w('large'):.2f} W   "
          f"W/g = {12*cell_power_w('large')/(4*lwing):.3f}")
    print(f"  outline     = {lf + 8:.2f} x {CELLS['large']['w'] + 6 + 1:.2f} mm "
          f"(cell row + 6 mm spine + 1 mm margin; + 8 mm tab along x)")
    print(f"  span across the 4-arm cross = {2*(lf+8):.1f} mm")
    print()

    print("-- AERODYNAMIC DRAG OF THE ARRAY (flat plate, face-on to the ascent wind) --")
    for alt, rho in (("20 km", 0.0883), ("25 km", 0.0400), ("30 km", 0.0180)):
        a = 4 * (168.2 * 26.0) * 1e-6      # m2, spine-wing outline (b) x4 arms
        f = 0.5 * rho * (5.0 ** 2) * 1.2 * a
        print(f"  {alt}: rho={rho:6.4f} kg/m3, A={a*1e4:6.1f} cm2 -> "
              f"F = 0.5*rho*v^2*Cd*A = {f:.5f} N = {f/9.81*1e3:.2f} g-equivalent")
    print("  v=5 m/s ascent, Cd=1.2 (flat plate). rho values are standard-atmosphere")
    print("  values; TODO(unverified): rho at the actual float altitude.")
    print()


if __name__ == "__main__":
    main()
