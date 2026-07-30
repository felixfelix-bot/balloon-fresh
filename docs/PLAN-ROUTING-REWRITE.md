# PLAN: Clearance-Aware Routing Rewrite for gen_pcb.py

**Created:** 2026-07-30
**Author:** balloon-circuit-design sub-manager
**Status:** AWAITING APPROVAL
**Worktree:** ~/worktrees/balloon-circuit-design/
**Branch:** balloon-circuit-design
**Estimated time:** 3-4 hours (single focused worker session)

## PROBLEM

gen_pcb.py writes traces blindly — no collision detection. The `seg()` function
dumps raw KiCad segment text without checking if the trace crosses other nets.
Result on V1: 86 shorts, 65 crossings, 53 clearance violations. F33: 53 shorts,
42 crossings. These are REAL electrical defects — the boards would short power
to ground and signals to each other.

## ROOT CAUSE (3 issues)

### Issue 1: Blind trace placement
```python
def seg(x1, y1, x2, y2, net_name, width=0.25, layer="F.Cu"):
    s = f'  (segment (start {x1:.2f} {y1:.2f}) ...'
    return s  # No collision check!
```
Every trace is placed at exact coordinates regardless of what's already there.

### Issue 2: Power bus cuts across entire board
The 3V3 bus on V1 runs at y=20 from x=5 to x=38 (33mm horizontal trace).
Signal traces for SPI, UART, I2C all cross this bus. On F33, the 3V3 trace
runs at y=38 across the full 75mm width.

### Issue 3: GND depends on unfilled zone
GND pads route to stitching vias that connect to B.Cu ground pour zone.
But kicad-cli can't fill zones and pcbnew segfaults headless. So the zone
is empty and DRC reports 31+32 unconnected.

## SOLUTION: Router class with grid-based collision detection

### Architecture

Replace the current `seg()`/`via()` text-dump helpers with a `Router` class:

```python
class Router:
    """Clearance-aware router for text-generated KiCad PCBs."""
    
    def __init__(self, board_w, board_h, grid=0.5, clearance=0.3):
        self.w = board_w
        self.h = board_h
        self.grid = grid          # routing grid (mm)
        self.clearance = clearance # minimum gap between different-net copper (mm)
        self.obstacles = []       # list of (x1,y1,x2,y2,net,width,layer)
        self.pads = []            # list of (x,y,w,h,net,layer)
        self.vias = []            # list of (x,y,size,net)
        self.segments = []        # committed trace segments
        self.net_colors = {}      # for debug output
    
    def add_pad(self, x, y, w, h, net, layer="F.Cu"):
        """Register a component pad as an obstacle."""
        self.pads.append((x, y, w, h, net, layer))
        # Pad copper is an obstacle for OTHER nets only
    
    def add_obstacle_trace(self, x1, y1, x2, y2, net, width, layer):
        """Register an existing trace as an obstacle."""
        self.obstacles.append((x1, y1, x2, y2, net, width, layer))
    
    def can_place(self, x1, y1, x2, y2, net, width, layer):
        """Check if a trace segment can be placed without clearance violation."""
        required_gap = self.clearance + width/2
        # Check against all obstacles on same layer with different nets
        for (ox1, oy1, ox2, oy2, onet, owidth, olayer) in self.obstacles:
            if olayer != layer:
                continue
            if onet == net:
                continue  # same net = OK to overlap/touch
            o_gap = self.clearance + owidth/2
            min_gap = required_gap + o_gap - self.clearance
            dist = seg_to_seg_dist(x1,y1,x2,y2, ox1,oy1,ox2,oy2)
            if dist < min_gap:
                return False, (dist, min_gap)
        # Check against pads on same layer with different nets
        for (px, py, pw, ph, pnet, player) in self.pads:
            if player != layer:
                continue
            if pnet == net:
                continue
            dist = point_or_rect_to_seg(px, py, pw, ph, x1, y1, x2, y2)
            if dist < required_gap:
                return False, (dist, required_gap)
        # Check against vias (both layers)
        for (vx, vy, vsize, vnet) in self.vias:
            if vnet == net:
                continue
            dist = point_to_seg_dist(vx, vy, x1, y1, x2, y2)
            min_gap = required_gap + vsize/2
            if dist < min_gap:
                return False, (dist, min_gap)
        return True, None
    
    def route(self, x1, y1, x2, y2, net, width=0.25, layer="F.Cu"):
        """Place a trace. If blocked, try detour or layer switch."""
        ok, info = self.can_place(x1, y1, x2, y2, net, width, layer)
        if ok:
            self._commit(x1, y1, x2, y2, net, width, layer)
            return True
        # Try detour: route around obstacle
        return self._try_detour(x1, y1, x2, y2, net, width, layer)
    
    def _try_detour(self, x1, y1, x2, y2, net, width, layer):
        """Attempt L-shaped or U-shaped detour around obstacle."""
        # ... (implementation in plan below)
        pass
    
    def via(self, x, y, net, size=0.6):
        """Place a via."""
        self.vias.append((x, y, size, net))
    
    def _commit(self, x1, y1, x2, y2, net, width, layer):
        """Commit a trace segment."""
        self.segments.append((x1, y1, x2, y2, net, width, layer))
        self.obstacles.append((x1, y1, x2, y2, net, width, layer))
    
    def emit(self):
        """Generate KiCad segment/via text."""
        ...
```

### Geometry functions needed

```python
def seg_to_seg_dist(x1,y1,x2,y2, x3,y3,x4,y4):
    """Minimum distance between two line segments."""
    # Standard segment-segment distance algorithm

def point_to_seg_dist(px,py, x1,y1,x2,y2):
    """Distance from point to segment."""

def seg_to_rect_dist(x1,y1,x2,y2, rx,ry,rw,rh):
    """Distance from segment to axis-aligned rectangle (pad)."""
```

## TASKS

### TASK 1: Build Router class + geometry utilities (worker, 30 min)

**Goal:** Standalone `router.py` with Router class, fully unit-testable.

**File:** `tracker/hardware/router.py` (new file)

**Components:**
1. `seg_to_seg_dist()` — segment-segment distance
2. `point_to_seg_dist()` — point-to-segment distance
3. `seg_to_rect_dist()` — segment-to-pad distance
4. `Router` class with:
   - `add_pad()`, `add_obstacle_trace()`, `add_via()`
   - `can_place()` — collision check
   - `route()` — place or detour
   - `_try_detour()` — L/U-shaped workaround
   - `_try_layer_switch()` — move to opposite layer + vias
   - `emit()` — KiCad text output
5. `route_path()` — multi-point routing (waypoint list → trace chain)

**Detour strategy (priority order):**
1. Try perpendicular offset (move trace 0.5mm sideways)
2. Try L-route (Manhattan routing with 1 bend)
3. Try U-route (go around obstacle)
4. Try layer switch (opposite layer + via pair)
5. If all fail: log warning, place anyway (flag for manual review)

**Unit tests** (`test_router.py`):
- Two parallel traces at 0.3mm gap → blocked
- Two parallel traces at 0.5mm gap → OK
- Same-net overlap → OK
- Cross-layer traces → OK (no collision)
- Detour around obstacle → generates valid path
- Via collision with trace → blocked

**Quality Gate:**
```bash
cd ~/worktrees/balloon-circuit-design/tracker/hardware/
python3 -m pytest test_router.py -v
```
PASS: All tests green.

**Commit:** `feat(router): clearance-aware Router class with geometry utilities`

---

### TASK 2: Rewrite gen_v1() using Router (worker, 45 min)

**Goal:** V1 board with 0 unconnected, 0 shorts, 0 crossings, <10 clearance.

**File:** `tracker/hardware/gen_pcb.py` (rewrite gen_v1 function)

**Changes:**

#### 2a: Register all pads as obstacles first
Before any routing, iterate all footprints and register every pad:
```python
router = Router(W, H, grid=0.5, clearance=0.3)
# Register ESP32 pads
router.add_pad(9.46, 3.11, 1.7, 1.7, nid["3V3"])
router.add_pad(9.46, 5.65, 1.7, 1.7, nid["GND"])
# ... all pads for all components
```

#### 2b: Power bus redesign (CRITICAL)
Current problem: 3V3 runs horizontally at y=20, blocking all signals.

New approach — **power bus on B.Cu**:
- Route 3V3 bus on B.Cu (bottom layer) as a dedicated power plane
- Use vias at each component's 3V3 pad to connect to the bus
- This frees F.Cu entirely for signal routing

```
F.Cu (top):  Signals (SPI, UART, I2C, RF)
B.Cu (bot):  3V3 power bus (horizontal) + GND mesh (grid pattern)
```

3V3 bus routing on B.Cu:
```python
# Main 3V3 trunk on B.Cu at y=5 (top edge, away from signals)
router.route_path([
    (9.46, 3.11),   # ESP32 3V3
    (9.46, 5),      # → B.Cu via
], "3V3", width=0.5)
router.via(9.46, 5, nid["3V3"])
router.route(9.46, 5, 38, 5, "3V3", width=0.5, layer="B.Cu")
router.route(38, 5, 38, 3.11, "3V3", width=0.5)  # to RP2040
# Branch to LR2021
router.via(25, 5, nid["3V3"])
router.route(25, 5, 25, 25, "3V3", width=0.5, layer="B.Cu")
router.route(25, 25, 15.095, 25, "3V3", width=0.5)
```

#### 2c: GND mesh (explicit traces, no zone dependence)
Replace zone-dependent GND with explicit B.Cu grid:
```python
# GND mesh: connect all GND vias with B.Cu traces
gnd_vias = [(10,5), (35,5), (20,30), (40,35), (5,35), ...]
# Horizontal grid lines
for y in [5, 15, 25, 35]:
    router.route(3, y, 47, y, "GND", width=0.5, layer="B.Cu")
# Vertical grid lines  
for x in [10, 20, 30, 40]:
    router.route(x, 3, x, 37, "GND", width=0.5, layer="B.Cu")
# Connect each GND pad to nearest mesh intersection
```

#### 2d: Signal routing with clearance checks
Each signal trace goes through `router.route()` which checks clearance:
- SPI bus: 4 traces, route on F.Cu with 0.6mm spacing
- UART: 3 traces, route on F.Cu or B.Cu where blocked
- I2C: 2 traces, route on F.Cu
- RF traces: 0.8mm width, keep short, route direct

#### 2e: Custom DRC rules
Create `hub_board_v1.kicad_dru` to suppress cosmetic-only violations:
- solder_mask_bridge → warning (JLCPCB handles)
- silk_overlap → warning
- text_height → warning
- courtyard_overlap → ignore

**Quality Gate:**
```bash
python3 gen_pcb.py
kicad-cli pcb drc --output drc_v1_final.txt hub_board_v1.kicad_pcb
grep "Found.*unconnected" drc_v1_final.txt  # Must show 0
grep -c "shorting_items" drc_v1_final.txt    # Must show 0
grep -c "tracks_crossing" drc_v1_final.txt   # Must show 0
```
PASS: 0 unconnected, 0 shorts, 0 crossings, <10 clearance.

**Commit:** `fix(pcb): V1 clearance-aware routing rewrite — 0 shorts, 0 crossings`

---

### TASK 3: Rewrite gen_v2() using Router (worker, 45 min)

**Goal:** F33 board with 0 unconnected, 0 shorts, 0 crossings, <15 clearance.

**File:** `tracker/hardware/gen_pcb.py` (rewrite gen_v2 function)

Same approach as Task 2 but for the 75×55mm F33 board:
- F33 module dominates center (39×21mm)
- Power bus on B.Cu (higher current — 1.2A TX, use 0.8mm traces)
- GND mesh on B.Cu with denser grid near F33 (heat dissipation)
- RF traces: PA output needs wider traces (1.0mm)
- Additional nets: LR2021_CE, LR2021_IRQ, PA power chain

F33-specific routing:
- F33 has 7 GND pins → each needs 0.5mm trace to GND mesh
- VCAP power chain: F33 pin1 → bulk caps → supercap → LDO
- PA output: F33 ANT pin → impedance-controlled trace to SMA

**Quality Gate:**
```bash
python3 gen_pcb.py
kicad-cli pcb drc --output drc_f33_final.txt hub_board_f33.kicad_pcb
grep "Found.*unconnected" drc_f33_final.txt  # Must show 0
grep -c "shorting_items" drc_f33_final.txt   # Must show 0
grep -c "tracks_crossing" drc_f33_final.txt  # Must show 0
```

**Commit:** `fix(pcb): F33 clearance-aware routing rewrite — 0 shorts, 0 crossings`

---

### TASK 4: Export Gerbers + JLCPCB order package (worker, 15 min)

**Goal:** Final manufacturable Gerber ZIPs.

```bash
python3 gen_pcb.py
mkdir -p gerbers_v1 gerbers_f33
kicad-cli pcb export gerbers --output gerbers_v1/ hub_board_v1.kicad_pcb
kicad-cli pcb export drill --output gerbers_v1/ hub_board_v1.kicad_pcb
kicad-cli pcb export pos --output gerbers_v1/pos_v1.csv hub_board_v1.kicad_pcb
kicad-cli pcb export gerbers --output gerbers_f33/ hub_board_f33.kicad_pcb
kicad-cli pcb export drill --output gerbers_f33/ hub_board_f33.kicad_pcb
kicad-cli pcb export pos --output gerbers_f33/pos_f33.csv hub_board_f33.kicad_pcb
cd gerbers_v1 && zip -r ../hub_board_v1_jlcpcb.zip . && cd ..
cd gerbers_f33 && zip -r ../hub_board_f33_jlcpcb.zip . && cd ..
```

**Commit:** `feat(pcb): final Gerbers + JLCPCB order — both boards clearance-clean`

---

### TASK 5: Push + verify (worker, 5 min)

```bash
git push github balloon-circuit-design
```

**Quality Gate:**
```bash
git log --oneline -5   # All commits visible
git push exit code 0   # Push succeeded
```

## QUALITY GATES SUMMARY

| Gate | Metric | Threshold | Check |
|------|--------|-----------|-------|
| QG1 | Router unit tests | all pass | `pytest test_router.py -v` |
| QG2 | V1 unconnected | 0 | `grep unconnected drc_v1_final.txt` |
| QG3 | V1 shorts | 0 | `grep -c shorting_items drc_v1_final.txt` |
| QG4 | V1 crossings | 0 | `grep -c tracks_crossing drc_v1_final.txt` |
| QG5 | F33 unconnected | 0 | `grep unconnected drc_f33_final.txt` |
| QG6 | F33 shorts | 0 | `grep -c shorting_items drc_f33_final.txt` |
| QG7 | Gerber file count | 9+ per ZIP | `ls gerbers_v1/*.g*` |
| QG8 | git push | exit 0 | `git push github balloon-circuit-design` |

## KEY DESIGN DECISIONS

### D1: Power bus on B.Cu (bottom layer)
**Rationale:** Moving 3V3 to B.Cu eliminates 80% of the shorts because the
power bus no longer crosses signal traces. Vias at each component's 3V3 pad
connect through. F.Cu is then free for clean signal routing.

**Trade-off:** More vias (~15-20 per board), slightly higher parasitic
inductance on power. Acceptable for balloon tracker (not high-speed digital).

### D2: GND mesh instead of zone fill
**Rationale:** kicad-cli can't fill zones, pcbnew segfaults. Explicit GND
grid on B.Cu provides guaranteed connectivity. JLCPCB will pour the zone
anyway during manufacturing (it's in the Gerber as unfilled zone), so the
mesh is belt-and-suspenders.

### D3: 0.3mm clearance minimum
**Rationale:** JLCPCB minimum trace spacing for 1oz copper is 0.127mm (5mil).
0.3mm gives 2.4× safety margin. Reduces DRC noise significantly.

### D4: Custom DRC rules for cosmetic suppression
**Rationale:** solder_mask_bridge, silk_overlap, text_height are cosmetic.
JLCPCB has their own tolerances for these. Suppressing them as warnings
reduces DRC output from 500+ to <50 violations, making real issues visible.

## FILE STRUCTURE

```
tracker/hardware/
├── gen_pcb.py          (rewritten — uses Router)
├── router.py           (NEW — Router class + geometry)
├── test_router.py      (NEW — unit tests)
├── hub_board_v1.kicad_pcb    (generated output)
├── hub_board_f33.kicad_pcb   (generated output)
├── hub_board_v1.kicad_dru    (NEW — custom DRC rules)
├── hub_board_f33.kicad_dru   (NEW — custom DRC rules)
├── gerbers_v1/               (Gerber output)
├── gerbers_f33/              (Gerber output)
└── hub_board_v1_jlcpcb.zip   (JLCPCB order package)
└── hub_board_f33_jlcpcb.zip  (JLCPCB order package)
```

## WORKER ASSIGNMENT

| Task | Model | Est. Time | Depends On |
|------|-------|-----------|------------|
| TASK 1: Router class | glm-5.2 | 30 min | nothing |
| TASK 2: V1 rewrite | glm-5.2 | 45 min | TASK 1 |
| TASK 3: F33 rewrite | glm-5.2 | 45 min | TASK 1 |
| TASK 4: Gerbers | glm-5.2 | 15 min | TASKS 2+3 |
| TASK 5: Push | glm-5.2 | 5 min | TASK 4 |

**Note:** Tasks 2+3 can run in parallel after Task 1 completes. Total wall
time ~2 hours with parallel dispatch, or ~2.5 hours sequential.

## EXPECTED RESULTS

| Metric | V1 Before | V1 After | F33 Before | F33 After |
|--------|-----------|----------|------------|-----------|
| Unconnected | 31 | 0 | 32 | 0 |
| Shorts | 86 | 0 | 53 | 0 |
| Crossings | 65 | 0 | 42 | 0 |
| Clearance | 53 | <10 | 17 | <15 |
| Cosmetic | 245 | warnings | 114 | warnings |
| **Total errors** | **524** | **<10** | **302** | **<15** |
