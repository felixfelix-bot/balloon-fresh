# ROADMAP: PCB v5 Completion — Two-Stage Quality-Gated (Placement → Routing)

> **Core principle:** Placement is a COMPLETE stage with hard quality gates.
> Routing is a SEPARATE stage that CANNOT START until placement passes ALL gates.
> Quality gates between stages are EXPLICIT and BLOCKING.

---

## 1. Current State

**Best board:** `output/v5_routed.kicad_pcb`
- 50x40mm, 4-layer (F.Cu, In1.Cu, In2.Cu, B.Cu)
- 30 footprints, 16 nets (GND, 3V3, 14 signal nets)
- GND zone on In1.Cu, 3V3 zone on In2.Cu
- 15/16 nets routed, 0 track crossings
- **Known defect:** thermal vias cause zone shorts (through-vias short to inner-plane zones)

**Root causes of routing failures:**
1. Script-based Manhattan router can't handle dense boards — L-routes always collide
2. Power net routing ignored collision detection — tracks through pads
3. Thermal via placement was blind — vias on pads, on THT holes, too close together
4. **Through-vias on 4-layer with inner-plane zones short to those zones** — signals must route without vias
5. 300s timeout too short for KiCad scripting — 6 delegate_task timeouts

**What works:**
- Grid placement script (0 pad overlaps, all 30 footprints)
- kicad-cli DRC verification
- python3.14 pcbnew API for tracks, vias, footprint manipulation
- Zone creation via .kicad_pcb text edit (python3.14 API segfaults on ZONE)

**Key insight:** Through-vias on 4-layer boards with inner-plane zones (GND on In1.Cu, 3V3 on In2.Cu) will short to those zones. Signals MUST route without through-vias — use layer alternation per net instead.

---

## 2. Assumptions and Invariants

- Board size **50x40mm**, 4-layer (F.Cu, In1.Cu, In2.Cu, B.Cu)
- 30 footprints, 16 nets (GND, 3V3, 14 signal nets)
- GND zone on In1.Cu (inner layer 1)
- 3V3 zone on In2.Cu (inner layer 2)
- kicad-cli pcb drc is the source of truth for verification
- python3.14 mandatory (python3 segfaults with pcbnew)
- `SaveBoard(path, board)` NOT `board.Save(path)`
- FreeRouting not installed — use script-based Manhattan routing with per-segment collision detection
- **worker-pcb profile** exists: kimi-k2.7-code, 1800s timeout (via kanban or background terminal)
- **300s is too short** for KiCad scripting — all PCB work uses worker-pcb (1800s) or background terminal

---

## 3. Two-Stage Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  STAGE A: PLACEMENT                                          │
│                                                             │
│  A1: Footprint placement                                    │
│  A2: ★ PLACEMENT GATE (BLOCKING)                            │
│  A3: Zone creation (GND In1.Cu, 3V3 In2.Cu)                │
│  A4: ★ ZONE GATE (BLOCKING)                                 │
│                                                             │
│  ═════════ ALL OF STAGE A MUST PASS ═════════               │
│  ═════════ BEFORE STAGE B STARTS ═════════                  │
│                                                             │
│  STAGE B: ROUTING                                           │
│                                                             │
│  B1: Via placement (thermal vias)                           │
│  B2: ★ VIA GATE (BLOCKING)                                  │
│  B3: RF routing (50Ω, ground stitching)                     │
│  B4: Signal routing (Manhattan, no through-vias)            │
│  B5: ★ ROUTING GATE (BLOCKING)                              │
└─────────────────────────────────────────────────────────────┘
```

### Why two stages?

Previous plans interleaved placement and routing phases loosely. Routing (R0/R2) started before placement was truly verified. The result: vias landed on pads, tracks crossed each other, zones shorted through vias. **Placement must be locked before routing starts.** This is now enforced by blocking gates.

---

## STAGE A: PLACEMENT

> **All Stage A tasks → worker-pcb profile** (kimi-k2.7-code, 1800s timeout)
> **Quality gate checks → any profile** (runs DRC + python3.14 checks)

### A1: Footprint Placement

**Input:** `output/v5_routed.kicad_pcb` (or clean netlist)
**Task:** Place all 30 parts on grid, no overlaps.

Steps:
1. Load board with python3.14
2. Verify all 30 footprints present
3. Place all footprints on 0.5mm grid
4. Check for pad-to-pad overlaps between different footprints
5. Check all footprints within 50x40mm board boundary
6. Advisory: connected parts should be near each other (R near IC, C near IC)

**Worker:** worker-pcb (kimi-k2.7-code, 1800s timeout)
**Output:** `output/v5.A1-placement.kicad_pcb` (snapshot)

---

### A2: PLACEMENT VERIFICATION GATE ★ BLOCKING

> **Stage B CANNOT START until this gate passes.**

**Verified by:** Any profile (runs DRC + python3.14 checks)

Check list:
- [ ] **0 pad-to-pad overlaps** between different footprints — **BLOCKING**
- [ ] **0 footprints out of bounds** (board edge) — **BLOCKING**
- [ ] **All parts within 50x40mm board** — **BLOCKING**
- [ ] Connected parts near each other (R near IC, C near IC) — **ADVISORY** (informational, not blocking)

Verification method:
```bash
python3.14 scripts/verify_placement.py output/v5.A1-placement.kicad_pcb
kicad-cli pcb drc --output - output/v5.A1-placement.kicad_pcb
```

**Gate pass criteria:** All BLOCKING checks = 0 failures.
If any BLOCKING check fails → return to A1, fix, re-verify. **Do not proceed.**

---

### A3: Zone Creation

**Input:** `output/v5.A1-placement.kicad_pcb` (A2-verified)
**Task:** Create GND and 3V3 zones on inner layers.

Steps:
1. Add GND zone on In1.Cu via .kicad_pcb text edit (python3.14 API segfaults on ZONE)
2. Add 3V3 zone on In2.Cu via .kicad_pcb text edit
3. Fill zones: `kicad-cli pcb fill zones` or reload in python3.14
4. Verify zones exist, correct layers, correct nets

**Worker:** worker-pcb (kimi-k2.7-code, 1800s timeout)
**Output:** `output/v5.A3-zones.kicad_pcb` (snapshot)

---

### A4: ZONE VERIFICATION GATE ★ BLOCKING

> **Stage B CANNOT START until this gate passes.**

**Verified by:** Any profile (runs DRC + python3.14 checks)

Check list:
- [ ] **2 zones exist** — **BLOCKING**
- [ ] **Correct layers** (GND on In1.Cu, 3V3 on In2.Cu) — **BLOCKING**
- [ ] **Correct nets** (zone netname matches net) — **BLOCKING**
- [ ] **0 zones_intersect** (zones don't overlap or short) — **BLOCKING**

Verification method:
```bash
python3.14 scripts/verify_zones.py output/v5.A3-zones.kicad_pcb
kicad-cli pcb drc --output - output/v5.A3-zones.kicad_pcb
```

**Gate pass criteria:** All BLOCKING checks pass.
If any BLOCKING check fails → return to A3, fix, re-verify. **Do not proceed.**

---

### ════════ STAGE A COMPLETE ════════

All four sub-stages (A1–A4) must pass before Stage B begins.
**Commit point:** `git commit -m "feat(hardware): v5 Stage A complete — placement + zones verified"`

---

## STAGE B: ROUTING

> **All Stage B tasks → worker-pcb profile** (kimi-k2.7-code, 1800s timeout)
> **Quality gate checks → any profile** (runs DRC + python3.14 checks)
> **PREREQUISITE:** Stage A fully passed (A1–A4 all green)

### B1: Via Placement

**Input:** `output/v5.A3-zones.kicad_pcb` (Stage A verified — placement locked, zones exist)
**Task:** Remove ALL existing vias. Place thermal vias for GND and 3V3 SMD pads using collision-aware algorithm.

Rules:
- Via center must be ≥0.6mm from nearest pad edge (edge-to-edge ≥0.25mm)
- Via center must be ≥0.25mm edge-to-edge from any THT drill hole
- Via center must be ≥0.25mm edge-to-edge from any other via
- Skip THT pads entirely (they connect through plating)
- Try 8 offset directions: N, S, E, W, NE, NW, SE, SW at 1.0mm distance
- If no clear position found, SKIP that pad (better unrouted than shorted)
- For SMD pads on F.Cu only: via connects F.Cu → In1.Cu (GND) or In2.Cu (3V3)

**Worker:** worker-pcb (kimi-k2.7-code, 1800s timeout)
**Output:** `output/v5.B1-vias.kicad_pcb` (snapshot)

---

### B2: VIA VERIFICATION GATE ★ BLOCKING

> **B3/B4 CANNOT START until this gate passes.**

**Verified by:** Any profile (runs DRC + python3.14 checks)

Check list:
- [ ] **0 vias on pads** (via center inside pad bbox) — **BLOCKING**
- [ ] **0 holes_co_located** (via overlaps THT drill) — **BLOCKING**
- [ ] **Edge-to-edge clearance ≥0.25mm** (via-to-pad, via-to-via, via-to-hole) — **BLOCKING**

Verification method:
```bash
python3.14 scripts/verify_vias.py output/v5.B1-vias.kicad_pcb
kicad-cli pcb drc --output - output/v5.B1-vias.kicad_pcb
```

**Gate pass criteria:** All BLOCKING checks = 0 failures.
If any BLOCKING check fails → return to B1, fix, re-verify. **Do not proceed.**

---

### B3: RF Routing

**Input:** `output/v5.B1-vias.kicad_pcb` (B2-verified)
**Task:** Route RF traces with proper impedance control and ground stitching.

Strategy:
- Compute 50Ω microstrip width from 4-layer stackup (dielectric thickness, Er)
- RF traces (RF_SUB_868, RF_2G4_2400): direct track, shortest path, F.Cu
- Require solid GND on In1.Cu beneath entire RF path (no cuts, no slots)
- Ground via stitching at both ends of every RF trace
- RF traces shortest path with zero stub length past matching components
- 2.4GHz: consider coplanar waveguide (gap-to-ground on sides)
- Collision check EVERY segment against existing copper

**Worker:** worker-pcb (kimi-k2.7-code, 1800s timeout)
**Output:** `output/v5.B3-rf.kicad_pcb` (snapshot)

---

### B4: Signal Routing

**Input:** `output/v5.B3-rf.kicad_pcb` (RF routed)
**Task:** Route all signal nets using Manhattan routing with layer alternation. **No through-vias.**

**CRITICAL:** Through-vias on 4-layer with inner-plane zones (GND In1.Cu, 3V3 In2.Cu) SHORT to those zones. Signals MUST route without through-vias. Use layer alternation per net instead.

Signal nets (from netlist):
```
SPI0_SCK, SPI0_MOSI, SPI0_MISO, SPI0_NSS (4-wire SPI to radio)
ESP_TX_RP2040_RX, RP2040_TX_ESP_RX (UART)
LR2021_BUSY, LR2021_RST, LR2021_DIO9 (radio control)
GPS TX_ESP_RX (GPS UART)
I2C_SDA (I2C data)
LED_ANODE, STATUS_LED (LED control)
SOLAR_IN, VCAP, VDIV_MID (power monitoring)
```

Strategy:
- SPI bus: route together on F.Cu, 0.20mm width, parallel routing (proof of concept first)
- UART/I2C/control: Manhattan L-routes on F.Cu, 0.20mm width
- Power monitoring (SOLAR_IN, VCAP, VDIV_MID): route on F.Cu, 0.40mm width
- **Per-segment collision detection** against ALL existing copper (tracks, pads, vias, zones)
- If collision on F.Cu: switch net to B.Cu for that segment (layer alternation, NO through-vias)
- Manhattan router needs collision detection per segment — check each L-route segment independently
- Assign correct net codes to every track

**Worker:** worker-pcb (kimi-k2.7-code, 1800s timeout)
**Output:** `output/v5.B4-signals.kicad_pcb` (snapshot)

---

### B5: ROUTING VERIFICATION GATE ★ BLOCKING

> **Final gate — must pass before commit.**

**Verified by:** Any profile (runs DRC + python3.14 checks)

Check list:
- [ ] **0 shorting_items** — **BLOCKING**
- [ ] **0 tracks_crossing** — **BLOCKING**
- [ ] **unconnected_items reported** — target: 0, accept < 3 — **BLOCKING** (if ≥3)

Verification method:
```bash
python3.14 scripts/verify_routing.py output/v5.B4-signals.kicad_pcb
kicad-cli pcb drc --output - output/v5.B4-signals.kicad_pcb
```

**Gate pass criteria:** All BLOCKING checks pass. unconnected < 3.
If BLOCKING checks fail → return to B3/B4, fix, re-verify. **Do not proceed.**

---

### ════════ STAGE B COMPLETE ════════

All five sub-stages (B1–B5) must pass.
**Commit point:** `git commit -m "feat(hardware): v5 Stage B complete — routing verified, DRC clean"`

---

## 4. Post-Routing: Review and Commit

### Q1: Cross-Family Review

**Input:** Stage B verified board
**Task:** Cold review by opposite-model-family subagent.

Dispatch reviewer to check:
- DRC report
- Board .kicad_pcb (via text inspection of track/via/zone sections)
- Placement verification output
- Are the remaining violations acceptable for manufacturing?
- Are there signal integrity risks (RF trace length, SPI bus skew)?
- Are power nets properly connected (no starved thermals)?
- Is the via strategy sound (enough vias, proper clearance)?

**Gate Q1:**
- [ ] Review verdict = APPROVED or issues addressed
- Evidence: Review subagent output

### C1: Commit and Push

- `git add -A`
- `git commit -m "feat(hardware): v5 PCB complete — two-stage quality-gated, 4-layer, DRC-clean"`
- `git push`

**Gate C1:**
- [ ] git push exit code 0
- [ ] git status clean

---

## 5. Worker Profile Assignments

| Stage/Task | Profile | Model | Timeout | Why |
|------------|---------|-------|---------|-----|
| A1: Placement | worker-pcb | kimi-k2.7-code | 1800s | Grid placement scripting |
| A2: Placement gate | any | any | 120s | DRC + python3.14 verification |
| A3: Zones | worker-pcb | kimi-k2.7-code | 1800s | .kicad_pcb text edit for zones |
| A4: Zone gate | any | any | 120s | DRC + python3.14 verification |
| B1: Vias | worker-pcb | kimi-k2.7-code | 1800s | Collision-aware via algorithm |
| B2: Via gate | any | any | 120s | DRC + python3.14 verification |
| B3: RF routing | worker-pcb | kimi-k2.7-code | 1800s | Impedance computation + routing |
| B4: Signal routing | worker-pcb | kimi-k2.7-code | 1800s | Manhattan routing with collision detection |
| B5: Routing gate | any | any | 120s | DRC + python3.14 verification |
| Q1: Cold review | any (cross-family) | any | 120s | Adversarial audit |
| C1: Commit | manager | — | 30s | Direct |

**Timeout rationale:** Previous 300s timeout caused 6 delegate_task failures doing PCB work. KiCad scripting (loading board, running API calls, saving) routinely exceeds 300s. worker-pcb profile via kanban provides 1800s timeout. Alternatively, use background terminal with `notify_on_complete=true`.

---

## 6. Per-Phase Versioning

- Each task saves to `output/v5.<task>.kicad_pcb` snapshot (A1, A3, B1, B3, B4)
- Each gate pass → `git commit`
- If task fails → revert to previous snapshot, escalate
- **Never mutate board in-place without backup**

---

## 7. Acceptance Criteria for "Done"

- [ ] 30 footprints, 0 pad overlaps (Stage A)
- [ ] All parts within 50x40mm board (Stage A)
- [ ] GND zone on In1.Cu, 3V3 zone on In2.Cu, 0 zones_intersect (Stage A)
- [ ] 0 vias on pads, 0 holes_co_located, clearance ≥0.25mm (Stage B)
- [ ] 0 shorting_items (Stage B)
- [ ] 0 tracks_crossing (Stage B)
- [ ] unconnected_items < 3 (Stage B)
- [ ] Cross-family review passed
- [ ] Committed and pushed
- [ ] Board opens in KiCad GUI without errors

---

## LESSONS LEARNED

1. **300s timeout is too short for KiCad scripting.** Six delegate_task calls timed out at 300s doing PCB work (placement, via placement, routing). KiCad board loading + python3.14 pcbnew API + SaveBoard routinely exceeds 300s. **Solution:** Use worker-pcb profile (1800s timeout) via kanban, or background terminal with notify_on_complete=true.

2. **Through-vias short through inner-plane zones.** On a 4-layer board with GND on In1.Cu and 3V3 on In2.Cu, any through-via that passes through those layers will electrically connect to those nets. A signal via from F.Cu to B.Cu shorts to GND and 3V3. **Solution:** Signals must route WITHOUT through-vias. Use layer alternation per net (route entire net on F.Cu, or entire net on B.Cu). Thermal vias for power are intentional (they connect pads to the power planes).

3. **Manhattan router needs collision detection per segment.** An L-route consists of two segments. The router must check each segment independently against ALL existing copper (tracks, pads, vias, zones). Previous implementations checked the route as a whole or skipped collision checks entirely, causing tracks through pads and track crossings. **Solution:** Per-segment collision detection with bounding-box intersection test. If a segment collides, try detour (midpoint shift) or switch that net to the opposite layer.

4. **Placement must be locked before routing starts.** Previous plans interleaved placement verification (P1) and routing (R0/R2) too loosely — routing started before placement was truly verified. The result: vias landed on misplaced pads, tracks crossed because parts were too close, zones were added after vias causing unexpected shorts. **Solution:** This two-stage plan. Stage A (placement + zones) is a COMPLETE stage with hard blocking gates. Stage B (routing) CANNOT START until Stage A passes ALL gates. Once placement is locked, it does not change during routing.

---

## Adversarial Review Findings (GLM-5.2 cold review, 2026-08-07)

### BLOCKERS (must fix before execution):

**B1: RF trace strategy ignores impedance/reference plane/matching**
- 0.15mm width is arbitrary — RF needs 50Ω controlled impedance from stackup
- No reference plane under RF traces — In1.Cu GND zone must be SOLID under RF path
- No ground via stitching along RF traces for return current
- 2.4GHz needs coplanar waveguide geometry, not free-floating microstrip
- FIX: RF routing becomes its own phase (B3) with computed impedance, solid GND pour requirement, matching component placement

**B2: No rollback/versioning between phases**
- Every phase mutates board in-place — no snapshot to revert to
- C1 is the ONLY commit (at the very end) — bad phase cascades
- FIX: Snapshot board file per phase (`v5.A1.kicad_pcb`, `v5.B1.kicad_pcb`, etc.) + git commit per gate pass

### MAJORS (should fix):

**M1: Star-topology power routing contradicts zone pours**
- Previous R1 routed power as B.Cu star tracks, R3 added inner-plane zones — philosophically incompatible
- Thermal vias (P2) placed before zones exist (R3) = open circuits until R3 succeeds
- FIX: Zones FIRST (A3, in Stage A), then vias to stitch pads to planes (B1, in Stage B). No explicit B.Cu power tracks — zones handle power distribution.

**M2: Quality gates accept non-zero failures**
- `unconnected < 5` = 22% net failure rate. Must be 0.
- `tracks_crossing < 10` = accepting shorts. Must be 0.
- Total violations lumps cosmetic with electrical
- FIX: Separate electrical DRC (must be 0) from cosmetic DRC (informational). Gates now require 0 shorting_items, 0 tracks_crossing. unconnected target: 0, accept < 3.

**M3: THT clearance math wrong + collision detection unproven**
- "Via center ≥0.8mm from THT drill hole center" — with 1.0mm hole, edge clearance is negative
- Must be EDGE-TO-EDGE ≥0.25mm
- O(n²) collision check will hit 300s timeout
- FIX: Edge-to-edge clearance (B2 gate). Per-segment collision detection (B4). Use 1800s timeout via worker-pcb profile.
