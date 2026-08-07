# ROADMAP: PCB v5 Completion — Placement-First, Quality-Gated

## 1. Current State

**Best board:** v5 (`output/v_c3_flight_v5.kicad_pcb`)
- 80x60mm, 4-layer (F.Cu, In1.Cu, In2.Cu, B.Cu)
- 0 track crossings, 0 keepout violations
- 8 DRC violations: 1 LR_RST short, 1 SPI_NSS clearance, 5 dangling power vias, 1 other
- 20 unconnected nets

**Root causes of routing failures:**
1. Script-based Manhattan router can't handle dense boards — L-routes always collide
2. Power net routing ignored collision detection — tracks through pads
3. Thermal via placement was blind — vias on pads, on THT holes, too close together
4. Zone creation via python3.14 API segfaults (KiCad 9 SWIG bug)

**What works:**
- Grid placement script (0 pad overlaps, all 30 footprints)
- kicad-cli DRC verification
- python3.14 pcbnew API for tracks, vias, footprint manipulation
- Zone creation via create_4layer.py reference (needs different API call)

## 2. Assumptions and Invariants

- Board size 80x60mm (v5 has more room than original 50x40mm)
- 30 footprints, 20 nets (GND=23 pads, 3V3=16 pads, 18 signal nets)
- 4 copper layers available
- kicad-cli pcb drc is the source of truth for verification
- python3.14 mandatory (python3 segfaults with pcbnew)
- SaveBoard(path, board) NOT board.Save(path)
- FreeRouting not installed (no .jar found) — must download or use alternative

## 3. Failure Modes to Avoid

| Failure | How it happened | Prevention |
|---------|----------------|------------|
| Parts overlapping | Grid placement didn't check bbox | **GATE P1**: verify 0 pad overlaps before routing |
| Vias on pads | Blind offset placement | **GATE P2**: verify 0 via-pad collisions |
| Vias on THT holes | No drill hole check | **GATE P2**: verify 0 holes_co_located |
| Tracks through pads | No collision detection in power routing | **GATE R1**: collision check EVERY segment |
| Zone creation crash | KiCad 9 SWIG bug on pcbnew.ZONE | Use kicad-cli or text-edit .kicad_pcb for zones |
| Unconnected nets | Router gives up on hard routes | **GATE R2**: report unconnected, iterate |

## 4. Phased Plan with Quality Gates

### PHASE P1: PLACEMENT VERIFICATION (Worker: glm-4.5-flash, leaf)

**Input:** `output/v_c3_flight_v5.kicad_pcb`
**Task:** Verify placement is clean. Fix if not.

Steps:
1. Load board with python3.14
2. Check ALL 30 footprints present
3. Check 0 pad-to-pad overlaps between different footprints
4. Check 0 footprints out of bounds (board edge)
5. Check 0 footprint courtyard overlaps (informational, not blocking)

**GATE P1 (must pass before P2):**
- [ ] 30 footprints
- [ ] 0 pad overlaps
- [ ] 0 OOB
- Evidence: python3.14 script output pasted

**Timeout:** 120s (simple inspection)

---

### PHASE P2: VIA PLACEMENT AND VERIFICATION (Worker: glm-5.2, leaf)

**Input:** P1-verified board
**Task:** Remove ALL existing vias. Place thermal vias for GND and 3V3 pads using collision-aware algorithm.

Rules:
- Via center must be ≥0.6mm from nearest pad edge (pad_radius + 0.6mm)
- Via center must be ≥0.8mm from any THT drill hole center
- Via center must be ≥0.6mm from any other via center
- Skip THT pads entirely (they connect through plating)
- Try 8 offset directions: N, S, E, W, NE, NW, SE, SW at 1.0mm distance
- If no clear position found, SKIP that pad (better unrouted than shorted)
- For SMD pads on F.Cu only: via connects F.Cu → In1.Cu (GND) or In2.Cu (3V3)
- Use PCB_VIA with SetLayerPair(F_Cu, In2_Cu) for power access

**GATE P2 (must pass before R1):**
- [ ] 0 vias on pads (via center inside pad bbox)
- [ ] 0 vias within 0.6mm of THT drill holes
- [ ] 0 via-via collisions (centers < 0.6mm apart)
- [ ] kicad-cli drc shows 0 holes_co_located
- Evidence: verification script + DRC hole_clearance count

**Timeout:** 300s background

---

### PHASE R1: POWER NET ROUTING (Worker: glm-5.2, leaf)

**Input:** P2-verified board (placement + vias clean)
**Task:** Route GND and 3V3 as explicit tracks on B.Cu. No inner-plane zones yet.

Strategy:
- GND: star topology from a central GND pad to each GND pad, B.Cu only
- 3V3: star topology from a central 3V3 pad, B.Cu only
- Track width: 0.40mm
- Collision check: EVERY segment against existing tracks, pads, vias
- If collision: try detour (midpoint shift) or skip segment
- Assign correct net codes to every track

**GATE R1 (must pass before R2):**
- [ ] Every GND track has GND netcode
- [ ] Every 3V3 track has 3V3 netcode
- [ ] kicad-cli drc shows 0 shorting_items for power nets
- [ ] kicad-cli drc tracks_crossing count for B.Cu < 5
- Evidence: DRC report breakdown

**Timeout:** 300s background

---

### PHASE R2: SIGNAL NET ROUTING (Worker: glm-5.2, leaf)

**Input:** R1-verified board (placement + vias + power clean)
**Task:** Route all 18 signal nets on F.Cu, with B.Cu fallback via layer switching.

Signal nets (from netlist):
```
SPI0_SCK, SPI0_MOSI, SPI0_MISO, SPI0_NSS (4-wire SPI to radio)
ESP_TX_RP2040_RX, RP2040_TX_ESP_RX (UART)
LR2021_BUSY, LR2021_RST, LR2021_DIO9 (radio control)
GPS_TX_ESP_RX (GPS UART)
I2C_SDA (I2C data)
LED_ANODE, STATUS_LED (LED control)
SOLAR_IN, VCAP, VDIV_MID (power monitoring)
RF_SUB_868, RF_2G4_2400 (RF antenna traces)
```

Strategy:
- RF traces (RF_SUB_868, RF_2G4_2400): direct track, shortest path, F.Cu, 0.15mm width
- SPI bus: route together on F.Cu, 0.20mm width, parallel routing
- UART/I2C/control: Manhattan L-routes on F.Cu, 0.20mm width
- Power monitoring (SOLAR_IN, VCAP, VDIV_MID): route on F.Cu, 0.40mm width
- For each segment: collision check against ALL existing copper
- If collision on F.Cu: via to B.Cu for that segment, via back
- Via placement follows P2 rules (≥0.6mm clearance)
- Assign correct net codes

**GATE R2 (must pass before R3):**
- [ ] All signal nets have at least 1 track connecting their pads
- [ ] kicad-cli drc unconnected_items < 5
- [ ] kicad-cli drc tracks_crossing < 10
- [ ] kicad-cli drc shorting_items = 0
- Evidence: DRC report + net-by-net routing summary

**Timeout:** 300s background

---

### PHASE R3: DRC CLEANUP AND ZONE ADDITION (Worker: glm-5.2, leaf)

**Input:** R2-verified board
**Task:** Fix remaining DRC violations. Add GND/3V3 zones on inner layers.

Steps:
1. Run kicad-cli pcb drc — categorize all remaining violations
2. Fix tracks_crossing: reroute colliding segments to alternate layer
3. Fix clearance violations: move tracks/vias further from pads
4. Fix shorting_items: separate touching different-net copper
5. Add GND zone on In1.Cu via .kicad_pcb text edit (not API — API segfaults)
6. Add 3V3 zone on In2.Cu via .kicad_pcb text edit
7. Fill zones: kicad-cli pcb fill zones or reload in python3.14

**GATE R3 (FINAL — must pass before commit):**
- [ ] kicad-cli drc: 0 shorting_items
- [ ] kicad-cli drc: 0 tracks_crossing
- [ ] kicad-cli drc: unconnected_items < 5
- [ ] kicad-cli drc: total violations < 20 (solder_mask/silk/text are cosmetic)
- [ ] GND zone present on In1.Cu
- [ ] 3V3 zone present on In2.Cu
- Evidence: Full DRC report breakdown

**Timeout:** 300s background

---

### PHASE Q1: CROSS-FAMILY REVIEW (Gate 2.5)

**Input:** R3-verified board
**Task:** Cold review by opposite-model-family subagent.

Dispatch kimi-k2.7-code (local ollama, free) to review:
- DRC report
- Board .kicad_pcb (via text inspection of track/via/zone sections)
- Placement verification output

Reviewer checks:
- Are the remaining violations acceptable for manufacturing?
- Are there signal integrity risks (RF trace length, SPI bus skew)?
- Are power nets properly connected (no starved thermals)?
- Is the via strategy sound (enough vias, proper clearance)?

**GATE Q1:**
- [ ] Review verdict = APPROVED or issues addressed
- Evidence: Review subagent output

---

### PHASE C1: COMMIT AND PUSH

- git add -A
- git commit -m "feat(hardware): v5 PCB complete — placement-first, 4-layer, DRC-clean routing"
- git push

**GATE 5:**
- [ ] git push exit code 0
- [ ] git status clean

---

## 5. Trade-offs and Open Questions

### Q1: FreeRouting vs script-based routing?
Script-based Manhattan routing has failed 5+ times. FreeRouting is a real autorouter but requires downloading a .jar and Java setup. 

**Decision:** Try FreeRouting first (download jar). If it works, use its output directly. If not, fall back to the phased script approach above with aggressive collision detection.

### Q2: Inner plane zones vs explicit power routing?
Zones (copper pours) provide better power distribution but the KiCad 9 python API segfaults on zone creation. Text-editing the .kicad_pcb file works but is fragile.

**Decision:** Route power explicitly in R1 (tracks), then ADD zones in R3 as a bonus. If zones can't be filled via API, leave them as unfilled outlines (they work in KiCad GUI).

### Q3: Board size — 50x40mm or 80x60mm?
v5 is 80x60mm which gives more routing space. Original spec was 50x40mm.

**Decision:** Use 80x60mm for v5. It's a prototype board, not a final product. More space = easier routing = faster to manufacturing.

### Q4: Worker timeout problem?
Every delegate_task with routing scripts has timed out at 300s.

**Decision:** Split into small phases (this plan). Each phase is independently verifiable. Background dispatch with notify_on_complete. Manager runs verification scripts directly (fast, no delegation).

## 6. Worker Profile Assignments

| Phase | Model | Role | Toolsets | Timeout | Why |
|-------|-------|------|----------|---------|-----|
| P1 (placement verify) | glm-4.5-flash | leaf | terminal, file | 120s | Simple inspection |
| P2 (via placement) | glm-5.2 | leaf | terminal, file | 300s bg | Algorithmic placement |
| R1 (power routing) | glm-5.2 | leaf | terminal, file | 300s bg | Collision detection |
| R2 (signal routing) | glm-5.2 | leaf | terminal, file | 300s bg | Complex routing |
| R3 (DRC cleanup) | glm-5.2 | leaf | terminal, file | 300s bg | Iterative fixes |
| Q1 (cold review) | kimi-k2.7-code | leaf | terminal | 120s | Cross-family audit |
| C1 (commit) | manager | - | terminal | 30s | Direct |

## 7. Acceptance Criteria for "Done"

- [ ] 30 footprints, 0 pad overlaps
- [ ] 0 vias on pads, 0 holes_co_located
- [ ] 0 shorting_items
- [ ] 0 tracks_crossing
- [ ] < 5 unconnected_items
- [ ] < 20 total DRC violations
- [ ] GND zone on In1.Cu, 3V3 zone on In2.Cu
- [ ] Cross-family review passed
- [ ] Committed and pushed
- [ ] Board opens in KiCad GUI without errors

## Adversarial Review Findings (GLM-5.2 cold review, 2026-08-07)

### BLOCKERS (must fix before execution):

**B1: RF trace strategy ignores impedance/reference plane/matching**
- 0.15mm width is arbitrary — RF needs 50Ω controlled impedance from stackup
- No reference plane under RF traces — In1.Cu GND zone must be SOLID under RF path
- No ground via stitching along RF traces for return current
- 2.4GHz needs coplanar waveguide geometry, not free-floating microstrip
- FIX: RF routing becomes its own phase with computed impedance, solid GND pour requirement, matching component placement

**B2: No rollback/versioning between phases**
- Every phase mutates board in-place — no snapshot to revert to
- C1 is the ONLY commit (at the very end) — bad phase cascades
- FIX: Snapshot board file per phase (`v5.P1.kicad_pcb`, `v5.P2.kicad_pcb`, etc.) + git commit per phase gate pass

### MAJORS (should fix):

**M1: Star-topology power routing contradicts zone pours**
- R1 routes power as B.Cu star tracks, R3 adds inner-plane zones — philosophically incompatible
- Thermal vias (P2) placed before zones exist (R3) = open circuits until R3 succeeds
- FIX: Zones FIRST (before vias), then vias to stitch pads to planes. Delete explicit B.Cu power tracks.

**M2: Quality gates accept non-zero failures**
- `unconnected < 5` = 22% net failure rate. Must be 0.
- `tracks_crossing < 10` = accepting shorts. Must be 0.
- Total violations lumps cosmetic with electrical
- FIX: Separate electrical DRC (must be 0) from cosmetic DRC (informational)

**M3: THT clearance math wrong + collision detection unproven**
- "Via center ≥0.8mm from THT drill hole center" — with 1.0mm hole, edge clearance is negative
- Must be EDGE-TO-EDGE ≥0.25mm
- O(n²) collision check will hit 300s timeout
- FIX: Edge-to-edge clearance. Prove algorithm on SPI bus before scaling.

---

## REVISED PLAN (addressing review findings)

### Phase ordering change:
1. P1: Placement verify (unchanged)
2. **P2Z: ZONES FIRST** — add GND zone on In1.Cu, 3V3 zone on In2.Cu via .kicad_pcb text edit (API segfaults)
3. P2V: Via placement (thermal vias stitching SMD pads to inner planes — zones already exist now)
4. **R0: RF ROUTING** — dedicated phase: compute 50Ω width, solid GND pour check, ground via stitching, matching components pad-to-pad
5. R1: Power routing (REMOVED — zones handle power, vias handle stitching)
6. R2: Signal routing (SPI bus first as proof-of-concept, then remaining signals)
7. R3: DRC cleanup (tightened: 0 shorts, 0 crossings, 0 unconnected)
8. Q1: Cold review
9. C1: Commit + push (one commit PER PHASE, not just at end)

### Per-phase versioning:
- Each phase saves to `v5.<phase>.kicad_pcb` snapshot
- Each phase gate pass → git commit
- If phase fails → revert to previous snapshot, escalate
- Never mutate board in-place without backup

### Tightened gates:
- Electrical DRC: 0 shorting, 0 crossing, 0 unconnected (BLOCKING)
- Cosmetic DRC (silk, soldermask, text): informational only (NON-BLOCKING)
- THT clearance: edge-to-edge ≥0.25mm (not center-to-center)
- Via-to-via: edge-to-edge ≥0.25mm

### RF engineering (NEW):
- Compute 50Ω microstrip width from 4-layer stackup (dielectric thickness, Er)
- Require solid GND on In1.Cu beneath entire RF path (no cuts, no slots)
- Ground via stitching at both ends of every RF trace
- RF traces shortest path with zero stub length past matching components
- 2.4GHz: consider coplanar waveguide (gap-to-ground on sides)
