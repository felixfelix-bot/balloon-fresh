# PCB TASK PIPELINE — kimi-k3 Worker

All spatial PCB work delegated to kimi-k3 (worker-layout profile).
Manager does NOT do spatial work. Consultant defines quality gates.

## TASK BREAKDOWN

### TASK A: V2-ADC Final Board Preparation (RUNNING — deleg_8db72ceb)
**Input:** v2_adc_fixed3.kicad_pcb (populated, routed, 0 unconnected, missing outline)
**Steps:**
1. Add Edge.Cuts board outline (0,0)→(50,40)
2. Fix thickness to 0.6mm
3. Fill GND zone
4. Verify DRC = 0 violations, 0 unconnected
5. Verify board NOT EMPTY (footprints > 0, tracks > 0)
6. Export gerbers
7. Commit + push

**Quality Gates (consultant-defined):**
- GATE 1: Board has >10 footprints, >50 tracks (not empty)
- GATE 2: DRC = 0 violations, 0 unconnected
- GATE 3: Board thickness = 0.6mm
- GATE 4: Gerbers F_Cu.gtl > 1KB, B_Cu.gbl > 1KB
- GATE 5: Committed + pushed

### TASK B: V1-FAST Board (PENDING — after A completes)
**Input:** hub_board_v1_clean.kicad_pcb (populated, unrouted)
**Steps:**
1. Redesign placement: cluster power islands
2. Export DSN → Freerouting → Import SES
3. Add outline, thickness, zone fill
4. Verify DRC, export gerbers
5. Commit + push

**Quality Gates:**
- GATE 1: Placement clusters decoupling caps within 3mm of IC power pins
- GATE 2: SES import succeeds (footprints preserved)
- GATE 3: DRC < 10 violations (cosmetic only), 0 unconnected
- GATE 4: Board thickness = 0.6mm
- GATE 5: Gerbers non-empty
- GATE 6: Committed + pushed

### TASK C: Consultant Final Review (PENDING — after A+B complete)
**Input:** Both final boards
**Steps:**
1. Independent DRC verification
2. GPIO assignment check (LED=GPIO9, no FEM, ADC disabled on V1)
3. Gerber completeness check
4. Write APPROVE/REJECT verdict

## ANTI-PATTERNS (learned the hard way)
- ❌ Manual DSN track parsing (Y-axis coordinate bug)
- ❌ glm-5.2 doing placement work (can't reason spatially)
- ❌ SaveBoard() creating empty boards (always verify footprint count after save)
- ❌ Straight power tracks through signal pads (creates shorts)
- ✅ ImportSpecctraSES() for all routing import
- ✅ kimi-k3 for all placement decisions
- ✅ ZONE_FILLER for GND copper pour
- ✅ Verify footprints > 0 BEFORE committing
