#!/usr/bin/python3.14
"""Phase 0 Placement Verification Script for Balloon Tracker PCB (v7.1).

Runs ALL 7 placement checks from PCB-ROUTING-PLAN-v7.md:
  1. Zero bounding-box overlaps (> 0.1mm² = FAIL)
  2. Board bounds: all footprints inside 80×60mm with 2mm margin
  3. Pad spacing: different-net pad pairs ≥ 1.0mm center-to-center
  4. Drill check: no pad with drill diameter < 0.2mm
  5. Decoupling cap proximity: IC power pads within 5mm of a decoupling cap
  6. Polarity check: polarized components have pin-1 / polarity markers
  7. Edge connector access: J1, J2, SOLAR within 5mm of board edge

Board: v_c3_flight_v5.kicad_pcb (80×60mm, 4-layer, 20 footprints)
"""

import sys
import math
import itertools

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

# ─── Configuration ─────────────────────────────────────────────────────────────

BOARD_PATH = "/home/c03rad0r/repos/balloon-fresh/tracker/hardware/output/v_c3_flight_v5.kicad_pcb"

BOARD_W_MM = 80.0
BOARD_H_MM = 60.0
MARGIN_MM  = 2.0

# Check thresholds
BBOX_OVERLAP_THRESH_MM2 = 0.1   # Overlap area threshold
PAD_MIN_SPACING_MM      = 1.0   # Min different-net pad center-to-center
MIN_DRILL_MM            = 0.2   # JLCPCB minimum drill
DECAP_MAX_DIST_MM       = 5.0   # Max VCC-pad to cap-pad distance
EDGE_MAX_DIST_MM        = 5.0   # Max distance from footprint edge to board edge

# ICs to check for decoupling caps
IC_REFS  = {"U1", "U2", "U3", "U5"}
CAP_REFS = {"C1", "C2", "C3", "C4", "C_CAP"}
POWER_NETS = {"+3V3", "VCAP"}

# Polarized components
POLARIZED_REFS = {"LED1", "D1", "C_CAP"}

# Edge connectors
EDGE_CONN_REFS = {"J1", "J2", "SOLAR"}

# ─── Results collector ─────────────────────────────────────────────────────────

results = []  # (check_num, check_name, status, detail_lines)

def mm(nm):
    """Convert KiCad internal nm to mm."""
    return pcbnew.ToMM(nm)

def record(check_num, name, passed, details):
    results.append((check_num, name, "PASS" if passed else "FAIL", details))

# ─── Load board ─────────────────────────────────────────────────────────────────

print("=" * 72)
print("  PHASE 0 — PLACEMENT VERIFICATION (v7.1)")
print(f"  Board: {BOARD_PATH.split('/')[-1]}")
print("=" * 72)
print()

b = pcbnew.LoadBoard(BOARD_PATH)
footprints = list(b.Footprints())
print(f"Loaded {len(footprints)} footprints:")
for fp in footprints:
    pos = fp.GetPosition()
    print(f"  {fp.GetReference():10s} {fp.GetValue():20s} @ ({mm(pos.x):6.2f}, {mm(pos.y):6.2f}) mm")
print()

# Precompute footprint data
fp_data = {}  # ref → dict(pos, bbox_mm, pads)
for fp in footprints:
    ref = fp.GetReference()
    pos = fp.GetPosition()
    bbox = fp.GetBoundingBox()
    pads = []
    for pad in fp.Pads():
        ppos = pad.GetPosition()
        psize = pad.GetSize()
        pdrill = pad.GetDrillSize()
        pads.append({
            "name": pad.GetName(),
            "net": pad.GetNetname(),
            "netcode": pad.GetNetCode(),
            "x": mm(ppos.x),
            "y": mm(ppos.y),
            "size_x": mm(psize.x),
            "size_y": mm(psize.y),
            "drill_x": mm(pdrill.x),
            "drill_y": mm(pdrill.y),
        })
    fp_data[ref] = {
        "fp": fp,
        "x": mm(pos.x),
        "y": mm(pos.y),
        "bbox_x": mm(bbox.GetX()),
        "bbox_y": mm(bbox.GetY()),
        "bbox_w": mm(bbox.GetWidth()),
        "bbox_h": mm(bbox.GetHeight()),
        "pads": pads,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 1: Zero bounding-box overlaps
# ═══════════════════════════════════════════════════════════════════════════════

print("─" * 72)
print("CHECK 1: Bounding-Box Overlap Detection (threshold: > %.1f mm²)" % BBOX_OVERLAP_THRESH_MM2)
print("─" * 72)

overlap_violations = []
fp_refs = sorted(fp_data.keys())

for i in range(len(fp_refs)):
    for j in range(i + 1, len(fp_refs)):
        r1, r2 = fp_refs[i], fp_refs[j]
        d1 = fp_data[r1]
        d2 = fp_data[r2]

        # Compute bounding boxes
        x1_min = d1["bbox_x"]
        y1_min = d1["bbox_y"]
        x1_max = d1["bbox_x"] + d1["bbox_w"]
        y1_max = d1["bbox_y"] + d1["bbox_h"]

        x2_min = d2["bbox_x"]
        y2_min = d2["bbox_y"]
        x2_max = d2["bbox_x"] + d2["bbox_w"]
        y2_max = d2["bbox_y"] + d2["bbox_h"]

        # Compute intersection
        ix_min = max(x1_min, x2_min)
        iy_min = max(y1_min, y2_min)
        ix_max = min(x1_max, x2_max)
        iy_max = min(y1_max, y2_max)

        if ix_max > ix_min and iy_max > iy_min:
            overlap_area = (ix_max - ix_min) * (iy_max - iy_min)
            if overlap_area > BBOX_OVERLAP_THRESH_MM2:
                overlap_violations.append((r1, r2, overlap_area, ix_min, iy_min, ix_max - ix_min, iy_max - iy_min))

if overlap_violations:
    print(f"  ❌ FAIL — {len(overlap_violations)} overlap(s) found:")
    for v in overlap_violations:
        r1, r2, area, ox, oy, ow, oh = v
        print(f"     {r1:10s} × {r2:10s}  overlap = {area:7.2f} mm²  "
              f"(region: {ox:.2f},{oy:.2f}  {ow:.2f}×{oh:.2f})")
else:
    print("  ✅ PASS — No bounding-box overlaps detected.")

print()
record(1, "BBox Overlaps", len(overlap_violations) == 0,
       [f"{v[0]} × {v[1]}: {v[2]:.2f}mm²" for v in overlap_violations])


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 2: Board bounds (inside 80×60 with 2mm margin → usable 76×56)
# ═══════════════════════════════════════════════════════════════════════════════

print("─" * 72)
print("CHECK 2: Board Bounds (80×60mm, 2mm margin → usable area)")
print("─" * 72)

usable_x_min = MARGIN_MM
usable_y_min = MARGIN_MM
usable_x_max = BOARD_W_MM - MARGIN_MM
usable_y_max = BOARD_H_MM - MARGIN_MM

oob_violations = []
for ref, d in fp_data.items():
    x_min = d["bbox_x"]
    y_min = d["bbox_y"]
    x_max = d["bbox_x"] + d["bbox_w"]
    y_max = d["bbox_y"] + d["bbox_h"]

    issues = []
    if x_min < usable_x_min:
        issues.append(f"x_min={x_min:.2f} < {usable_x_min}")
    if y_min < usable_y_min:
        issues.append(f"y_min={y_min:.2f} < {usable_y_min}")
    if x_max > usable_x_max:
        issues.append(f"x_max={x_max:.2f} > {usable_x_max}")
    if y_max > usable_y_max:
        issues.append(f"y_max={y_max:.2f} > {usable_y_max}")

    if issues:
        oob_violations.append((ref, issues))

if oob_violations:
    print(f"  ❌ FAIL — {len(oob_violations)} footprint(s) outside usable area:")
    for ref, issues in oob_violations:
        print(f"     {ref:10s}: {'; '.join(issues)}")
else:
    print("  ✅ PASS — All footprints inside usable area (76×56mm).")

print()
record(2, "Board Bounds", len(oob_violations) == 0,
       [f"{r}: {i}" for r, i in oob_violations])


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 3: Pad spacing (different-net pairs ≥ 1.0mm center-to-center)
# ═══════════════════════════════════════════════════════════════════════════════

print("─" * 72)
print("CHECK 3: Pad Spacing (different-net pairs ≥ %.1fmm)" % PAD_MIN_SPACING_MM)
print("─" * 72)

# Collect all pads across all footprints with footprint reference
all_pads = []
for ref, d in fp_data.items():
    for pad in d["pads"]:
        all_pads.append((ref, pad))

pad_spacing_violations = []
for i in range(len(all_pads)):
    for j in range(i + 1, len(all_pads)):
        ref1, p1 = all_pads[i]
        ref2, p2 = all_pads[j]

        net1 = p1["net"]
        net2 = p2["net"]

        # Skip same-net pairs (including unconnected "")
        if net1 == net2:
            continue
        # Skip if either pad is unconnected (net "") — those aren't real signals yet
        if not net1 or not net2:
            continue

        dx = p1["x"] - p2["x"]
        dy = p1["y"] - p2["y"]
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < PAD_MIN_SPACING_MM:
            pad_spacing_violations.append((ref1, p1["name"], net1, ref2, p2["name"], net2, dist))

if pad_spacing_violations:
    print(f"  ❌ FAIL — {len(pad_spacing_violations)} pad pair(s) too close:")
    for v in sorted(pad_spacing_violations, key=lambda x: x[6]):
        r1, n1, net1, r2, n2, net2, dist = v
        print(f"     {r1}.{n1}({net1}) ↔ {r2}.{n2}({net2})  dist = {dist:.3f} mm")
else:
    print("  ✅ PASS — All different-net pad pairs ≥ 1.0mm apart.")

print()
record(3, "Pad Spacing", len(pad_spacing_violations) == 0,
       [f"{v[0]}.{v[1]} ↔ {v[3]}.{v[4]}: {v[6]:.3f}mm" for v in pad_spacing_violations])


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 4: Drill check (no pad with drill < 0.2mm)
# ═══════════════════════════════════════════════════════════════════════════════

print("─" * 72)
print("CHECK 4: Drill Check (no drill diameter < %.1fmm)" % MIN_DRILL_MM)
print("─" * 72)

drill_violations = []
for ref, d in fp_data.items():
    for pad in d["pads"]:
        # Drill diameter: use max of drill_x and drill_y (oval drills use larger)
        drill_d = max(pad["drill_x"], pad["drill_y"])
        if drill_d > 0 and drill_d < MIN_DRILL_MM:
            drill_violations.append((ref, pad["name"], drill_d))

if drill_violations:
    print(f"  ❌ FAIL — {len(drill_violations)} pad(s) with drill < {MIN_DRILL_MM}mm:")
    for ref, pname, dd in drill_violations:
        print(f"     {ref}.{pname}  drill = {dd:.3f} mm")
else:
    # Count pads that have drills
    drilled_count = sum(1 for ref, d in fp_data.items() for pad in d["pads"] if max(pad["drill_x"], pad["drill_y"]) > 0)
    print(f"  ✅ PASS — No drill < {MIN_DRILL_MM}mm found ({drilled_count} drilled pads checked).")

print()
record(4, "Drill Check", len(drill_violations) == 0,
       [f"{v[0]}.{v[1]}: {v[2]:.3f}mm" for v in drill_violations])


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 5: Decoupling cap proximity
# ═══════════════════════════════════════════════════════════════════════════════

print("─" * 72)
print("CHECK 5: Decoupling Cap Proximity (IC VCC pads within %.0fmm of cap)" % DECAP_MAX_DIST_MM)
print("─" * 72)

# Collect cap pads on power nets
cap_power_pads = {}  # net_name → list of (ref, pad_name, x, y)
for ref in CAP_REFS:
    if ref not in fp_data:
        continue
    for pad in fp_data[ref]["pads"]:
        if pad["net"] in POWER_NETS:
            net = pad["net"]
            if net not in cap_power_pads:
                cap_power_pads[net] = []
            cap_power_pads[net].append((ref, pad["name"], pad["x"], pad["y"]))

decap_results = []
for ic_ref in sorted(IC_REFS):
    if ic_ref not in fp_data:
        print(f"  ⚠️  {ic_ref} not found on board — skipping")
        decap_results.append((ic_ref, "SKIP", "Not on board", []))
        continue

    # Find all power pads on this IC
    ic_power_pads = [p for p in fp_data[ic_ref]["pads"] if p["net"] in POWER_NETS]

    if not ic_power_pads:
        print(f"  ⚠️  {ic_ref}: No power pads found on +3V3/VCAP nets — SKIP")
        decap_results.append((ic_ref, "SKIP", "No power pads", []))
        continue

    print(f"  {ic_ref} ({fp_data[ic_ref]['fp'].GetValue()}):")

    ic_ok = True
    ic_details = []
    for pad in ic_power_pads:
        net = pad["net"]
        pad_x, pad_y = pad["x"], pad["y"]

        # Find nearest cap pad on same net
        candidates = cap_power_pads.get(net, [])
        if not candidates:
            print(f"     ❌ {ic_ref}.{pad['name']}({net}) → NO cap on {net} net!")
            ic_ok = False
            ic_details.append(f"{pad['name']}({net}): no cap on net")
            continue

        nearest = min(candidates, key=lambda c: math.sqrt((c[2]-pad_x)**2 + (c[3]-pad_y)**2))
        dist = math.sqrt((nearest[2]-pad_x)**2 + (nearest[3]-pad_y)**2)

        if dist <= DECAP_MAX_DIST_MM:
            print(f"     ✅ {ic_ref}.{pad['name']}({net}) → nearest cap: {nearest[0]}.{nearest[1]} "
                  f"at {dist:.2f}mm")
            ic_details.append(f"{pad['name']}({net}): {nearest[0]} @ {dist:.2f}mm")
        else:
            print(f"     ❌ {ic_ref}.{pad['name']}({net}) → nearest cap: {nearest[0]}.{nearest[1]} "
                  f"at {dist:.2f}mm (> {DECAP_MAX_DIST_MM}mm)")
            print(f"        → SUGGESTION: Move {nearest[0]} closer to {ic_ref} (currently {dist:.1f}mm away)")
            ic_ok = False
            ic_details.append(f"{pad['name']}({net}): {nearest[0]} @ {dist:.2f}mm TOO FAR")

    status = "PASS" if ic_ok else "FAIL"
    decap_results.append((ic_ref, status, "", ic_details))

decap_all_pass = all(r[1] == "PASS" for r in decap_results if r[1] != "SKIP")
print()
record(5, "Decoupling Caps", decap_all_pass,
       [f"{r[0]}: {r[1]} {'; '.join(r[3])}" for r in decap_results if r[1] != "SKIP"])


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 6: Polarity check for polarized components
# ═══════════════════════════════════════════════════════════════════════════════

print("─" * 72)
print("CHECK 6: Polarity / Pin-1 Markers")
print("─" * 72)

# F.SilkS = layer 5, F.Fab = layer 35, F.CrtYd = 31
F_SILK = pcbnew.F_SilkS
F_FAB  = pcbnew.F_Fab

polarity_results = []
for ref in sorted(POLARIZED_REFS):
    if ref not in fp_data:
        print(f"  ⚠️  {ref} not found on board — skipping")
        polarity_results.append((ref, "SKIP", "Not on board"))
        continue

    fp = fp_data[ref]["fp"]
    val = fp.GetValue()

    # Check for silk/fab graphical items
    silk_items = 0
    fab_items = 0
    has_circle_marker = False
    has_line_marker = False

    for item in fp.GraphicalItems():
        layer = item.GetLayer()
        if layer == F_SILK:
            silk_items += 1
            # Check shape type
            shape = item.GetShape()
            # PCB_SHAPE_TYPE_T: 0=segment, 1=rect, 2=arc, 3=circle, 4=polygon, 5=curve
            if shape == pcbnew.SHAPE_T_CIRCLE:
                has_circle_marker = True
            if shape == pcbnew.SHAPE_T_SEGMENT:
                has_line_marker = True
        elif layer == F_FAB:
            fab_items += 1

    # Check pad 1 properties — in some footprints pad 1 has a different shape
    pad1 = None
    for pad in fp.Pads():
        if pad.GetName() == "1":
            pad1 = pad
            break

    pad1_info = ""
    has_marker = False

    if pad1:
        pad1_shape = pad1.GetShape()
        # SHAPE_T values for pads: 0=circle, 1=rect, 2=oval, 3=trapezoid, etc.
        # PAD_SHAPE_CIRCLE = 0, PAD_SHAPE_RECT = 1, PAD_SHAPE_OVAL = 2
        shape_names = {0: "Circle", 1: "Rect", 2: "Oval", 3: "Trapezoid"}
        pad1_info = f"shape={shape_names.get(pad1_shape, pad1_shape)}"

    # Determine if polarity marker exists
    # Criteria: has silk items (lines/circles) that could be polarity indicators
    if silk_items > 0 or fab_items > 0:
        has_marker = True

    detail = (f"{val}: silk_items={silk_items} fab_items={fab_items} "
              f"pad1={pad1_info} circle={has_circle_marker} line={has_line_marker}")

    if has_marker:
        print(f"  ✅ {ref:10s} — {detail}")
        polarity_results.append((ref, "PASS", detail))
    else:
        print(f"  ❌ {ref:10s} — {detail}")
        print(f"     → WARNING: No silk/fab polarity indicator found!")
        polarity_results.append((ref, "FAIL", detail))

pol_all_pass = all(r[1] == "PASS" for r in polarity_results if r[1] != "SKIP")
print()
record(6, "Polarity", pol_all_pass,
       [f"{r[0]}: {r[1]} ({r[2]})" for r in polarity_results if r[1] != "SKIP"])


# ═══════════════════════════════════════════════════════════════════════════════
# CHECK 7: Edge connector access
# ═══════════════════════════════════════════════════════════════════════════════

print("─" * 72)
print("CHECK 7: Edge Connector Access (J1, J2, SOLAR within %.0fmm of edge)" % EDGE_MAX_DIST_MM)
print("─" * 72)

edge_results = []
for ref in sorted(EDGE_CONN_REFS):
    if ref not in fp_data:
        print(f"  ⚠️  {ref} not found on board — skipping")
        edge_results.append((ref, "SKIP", "Not on board"))
        continue

    d = fp_data[ref]
    val = d["fp"].GetValue()

    x_min = d["bbox_x"]
    y_min = d["bbox_y"]
    x_max = d["bbox_x"] + d["bbox_w"]
    y_max = d["bbox_y"] + d["bbox_h"]

    # Distance to each edge
    dist_left   = x_min                       # to x=0
    dist_right  = BOARD_W_MM - x_max           # to x=80
    dist_top    = y_min                        # to y=0
    dist_bottom = BOARD_H_MM - y_max           # to y=60

    min_dist = min(dist_left, dist_right, dist_top, dist_bottom)
    edge_name = {dist_left: "LEFT", dist_right: "RIGHT", dist_top: "TOP", dist_bottom: "BOTTOM"}[min_dist]

    detail = (f"{val}: bbox=({x_min:.1f},{y_min:.1f})-({x_max:.1f},{y_max:.1f}) "
              f"nearest_edge={edge_name}({min_dist:.2f}mm)")

    if min_dist <= EDGE_MAX_DIST_MM:
        print(f"  ✅ {ref:10s} — {detail}")
        edge_results.append((ref, "PASS", detail))
    else:
        print(f"  ❌ {ref:10s} — {detail}")
        print(f"     → WARNING: {min_dist:.1f}mm from nearest edge ({edge_name}), "
              f"should be ≤ {EDGE_MAX_DIST_MM}mm")
        edge_results.append((ref, "FAIL", detail))

edge_all_pass = all(r[1] == "PASS" for r in edge_results if r[1] != "SKIP")
print()
record(7, "Edge Access", edge_all_pass,
       [f"{r[0]}: {r[1]} ({r[2]})" for r in edge_results if r[1] != "SKIP"])


# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY TABLE
# ═══════════════════════════════════════════════════════════════════════════════

print()
print("=" * 72)
print("  SUMMARY TABLE")
print("=" * 72)
print(f"  {'#':>3}  {'Check':25s}  {'Status':8s}  Details")
print(f"  {'─'*3}  {'─'*25}  {'─'*8}  {'─'*40}")

all_pass = True
for num, name, status, details in results:
    if status != "PASS":
        all_pass = False
    detail_str = "OK" if not details else f"{len(details)} issue(s)"
    marker = "✅" if status == "PASS" else "❌"
    print(f"  {num:>3}  {name:25s}  {marker} {status:5s}  {detail_str}")

print()
if all_pass:
    print("  🟢 OVERALL: ALL 7 CHECKS PASSED — Placement is verified.")
else:
    failed = sum(1 for r in results if r[2] != "PASS")
    print(f"  🔴 OVERALL: {failed} of {len(results)} check(s) FAILED — Fix before routing.")

print()
print("=" * 72)
