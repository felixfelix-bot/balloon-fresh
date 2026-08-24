# PCB Routing Plan v7.1 — Consultant-Reviewed

## Review Status: REVISED after consultant audit (18 issues found, 3 CRITICAL)

Board: `v_c3_flight_v5.kicad_pcb` (80x60mm, 4-layer)
Branch: `autonomous/mesh-baseline` | Last commit: `960a8fa`

## Key Principle (Felix)

**Place parts and vias correctly BEFORE routing. Verify placement quality with gates. Only then route.**

## Consultant Findings (incorporated)

3 CRITICAL fixes applied:
1. Decoupling cap proximity gate added to Phase 0
2. RF_OUT 50Ω impedance control — hand-routed, NOT autorouted
3. FreeROUTING (Java) fallback path added to Phase 1

5 HIGH fixes applied:
4. EN reclassified as signal (was incorrectly in POWER_NETS)
5. GND via stitching plan for high-speed signals
6. Regulator thermal management spec
7. Zero unconnected gate (no "hand-route later")
8. Trace width table by net type

## KiCad 9 API Gotchas

- `b.Zones()` NOT `b.GetZones()`
- `b.Tracks()` iterator INVALIDATES after b.Add()/b.Remove() — snapshot upfront
- `SaveBoard(PATH, b)` NOT `b.Save()`
- Zone keepout flags NOT persisted by SaveBoard — sed the .kicad_pcb directly
- `python3.14` mandatory, `sys.path.insert(0, '/usr/lib/python3/dist-packages')`
- Precompute net codes via `b.GetNetsByNetcode()` before modifications

## Net Classification (CORRECTED)

| Category | Nets | Handling |
|----------|------|----------|
| Power planes | +3V3, GND | Thermal vias to In1.Cu/In2.Cu planes |
| Routed power | VCAP, SOLAR_IN | Dedicated traces, width ≥0.4mm |
| RF (50Ω) | RF_OUT | Hand-routed microstrip, width per stackup calc |
| Signal | SPI_SCK, SPI_MISO, SPI_MOSI, SPI_NSS, I2C_SCL, I2C_SDA, GPS_TX, GPS_RX, UART0_TX, UART0_RX, LED_A, LED_DRIVE, LR_RST, LR_BUSY, LR_DIO0, EN, VDIV_MID | Collision-aware autorouter, 0.2mm width |

## Trace Width Table

| Net type | Width | Clearance | Notes |
|----------|-------|-----------|-------|
| Power (VCAP, SOLAR_IN) | 0.40mm | 0.30mm | Current capacity |
| RF (RF_OUT) | 0.35mm* | 0.50mm | *50Ω microstrip over GND plane — calculate from stackup |
| Signal (SPI, I2C, UART) | 0.20mm | 0.22mm | Standard digital |
| Power plane vias | 0.55mm/0.30mm drill | — | Thermal relief |

## Plan: 4 Phases with Quality Gates

### PHASE 0: Placement Verification (GATE — must pass before routing)

**Goal:** Verify placement is mechanically AND electrically correct.

**Worker:** glm-5.2 (upgraded from flash — needs domain reasoning for cap proximity)
**Timeout:** 180s

**Checks:**
1. Zero bbox overlaps between all footprint pairs (>0.1mm² = FAIL)
2. All footprints inside board outline with 2mm margin
3. All different-net pad pairs ≥ 1.0mm apart
4. No drill < 0.2mm (JLCPCB standard minimum — raised from 0.15mm)
5. **NEW — Decoupling cap proximity:** For each IC (U1, U2, U3, U5), find nearest cap (C1-C4, C_CAP) on the same power net (+3V3 or VCAP). Must be within 5mm of a VCC pad. FAIL if any IC lacks a nearby cap.
6. **NEW — Polarized component orientation:** Verify LED polarity, diode direction, electrolytic cap band visible on F.SilkS. Pin-1 indicator present on all ICs.
7. **NEW — Edge connector access:** J1, J2, SOLAR mechanical outlines reach board edge in correct direction.

**Quality Gate (PLACEMENT):**
- All 7 checks pass
- If decoupling cap check FAILS: move caps closer to ICs before routing

**Output:** `v_c3_flight_verified.kicad_pcb`

---

### PHASE 1A: RF + Power Routing (HAND-ROUTED — not autorouted)

**Goal:** Route RF_OUT with 50Ω impedance. Route power traces with proper width. Place GND stitching vias.

**Worker:** glm-5.2
**Timeout:** 300s

**Steps:**
1. Calculate 50Ω microstrip width from 4-layer stackup:
   - F.Cu to In1.Cu (GND): dielectric thickness + εr → width
   - Formula: W = (7.48 × h) / (Z₀ × √(εr + 1.41)) for microstrip
   - Typical: ~0.35mm for 0.2mm dielectric, εr=4.4
2. Route RF_OUT pad → ANT1 pad on F.Cu with calculated width, shortest path
3. Place 2 GND stitching vias flanking the RF feed point (within 1mm)
4. Route VCAP and SOLAR_IN as dedicated traces (0.4mm width)
5. Place thermal vias under regulator (U4): minimum 4 vias to In1.Cu GND
6. Place GND stitching vias near each high-speed signal pad (SPI, I2C endpoints)

**Quality Gate (RF + POWER):**
- RF_OUT trace has calculated width, not default
- ≥2 GND vias flanking RF feed
- ≥4 thermal vias under regulator
- GND stitching vias at signal endpoints

**Output:** `v_c3_flight_rf_power.kicad_pcb`

---

### PHASE 1B: Signal Net Routing (AUTOROUTER with FreeROUTING fallback)

**Goal:** Route all remaining signal nets collision-free.

**Worker:** glm-5.2 for script writing; terminal background for execution
**Timeout:** 300s per attempt

#### Strategy A: Python collision-aware router (route_v7.py)

1. Snapshot all tracks/vias from Phase 1A
2. For each signal net, try collision-free Manhattan routing on F.Cu then B.Cu
3. Use Liang-Barsky bbox intersection for pad collision
4. Per-segment via hopping for stubborn nets (3-segment offset, each segment picks layer)
5. Fill zones, rebuild connectivity, save

#### Strategy B: FreeROUTING fallback (if Strategy A leaves >0 unconnected)

1. Export DSN: `/usr/bin/python3.14 -c "import pcbnew; b=pcbnew.LoadBoard('board.kicad_pcb'); pcbnew.ExportSpecctraDSN('board.dsn', b)"` or `kicad-cli pcb export dsn`
2. Run FreeROUTING: `java -jar freerouting.jar -de board.dsn -do board.ses -dl 2`
3. Import SES: `pcbnew.ImportSpecctraSES('board.ses', b)`
4. Fill zones, rebuild connectivity, save

**Decision point:** If Strategy A achieves ≤2 unconnected items, accept. Otherwise, Strategy B.

**Quality Gate (ROUTING):**
- 0 tracks_crossing
- 0 shorting_items
- 0 solder_mask_bridge
- 0 clearance violations
- **0 unconnected_items** (tightened from 5 — no "hand-route later")
- ≤3 dangling POWER vias (acceptable if zone fill connects)

**Output:** `v_c3_flight_v7_routed.kicad_pcb`

---

### PHASE 2: DRC + Manufacturing Prep

**Goal:** Clean DRC, generate gerbers + drill files + BOM.

**Worker:** glm-5.2
**Timeout:** 300s

**Steps:**
1. Run `kicad-cli pcb drc --output /tmp/drc_v7.txt v_c3_flight_v7_routed.kicad_pcb`
2. Parse violations. If ANY electrical errors → back to Phase 1B.
3. If ≤3 cosmetic warnings (silk/courtyard) → acceptable
4. Generate gerbers: `kicad-cli pcb export gerbers --output gerbers_v7/`
5. Generate drill: `kicad-cli pcb export drill --output gerbers_v7/`
6. Export 3D step: `kicad-cli pcb export step --output v7_board.step` (enclosure fit check)

**Quality Gate (DRC):**
- 0 electrical errors
- ≤3 cosmetic warnings
- 0 unconnected items
- Gerbers + drill generated

**Output:** Clean board + gerbers_v7/ + v7_board.step

---

## Worker Delegation Matrix

| Phase | Task | Model | Role | Timeout |
|-------|------|-------|------|---------|
| 0 | Placement verification (mechanical + electrical) | glm-5.2 | leaf | 180s |
| 1A | RF + power + thermal hand-routing | glm-5.2 | leaf | 300s |
| 1B-strat-A | Write + run Python autorouter | glm-5.2 + bg | leaf | 300s |
| 1B-strat-B | FreeROUTING fallback (if needed) | glm-5.2 | leaf | 300s |
| 2 | DRC + gerbers + step export | glm-5.2 | leaf | 300s |

## Quality Gates Summary

| Gate | Phase | Criteria |
|------|-------|----------|
| PLACEMENT | Phase 0 | Zero overlaps, zero OOB, cap proximity, polarity, edge access |
| RF_POWER | Phase 1A | 50Ω RF, thermal vias, GND stitching, power trace widths |
| ROUTING | Phase 1B | Zero crossings, zero shorts, zero unconnected |
| DRC | Phase 2 | Zero electrical errors, ≤3 cosmetic, gerbers generated |

## Risk Mitigation

1. **Python router fails again** → FreeROUTING Java fallback (explicit branch, not ad-hoc)
2. **Decoupling caps too far from ICs** → Phase 0 gate catches this BEFORE routing
3. **RF range degradation** → RF_OUT hand-routed with 50Ω width, not autorouted
4. **Regulator overheating** → ≥4 thermal vias + copper pour spec in Phase 1A
5. **Signal integrity** → GND stitching vias at every signal endpoint
