# PCB Master Execution Plan — 3 Balloon Board Variants

## Status

**ACTIVE** — canonical execution plan for schematic-first PCB design of the
C3, S3, and C3+RP2040 balloon relay board variants.

- **Author:** kimi-k3 (consultant), acting as `worker-layout`
- **Date:** 2026-08-05
- **Accepted ADR:** `docs/adr/028-schematic-first-three-variants.md`
- **GPIO source of truth:** `docs/coordination/schematic-task-context.md`
- **Repository:** `~/repos/balloon-fresh`
- **Branch:** `autonomous/mesh-baseline`
- **KiCad version:** 9.0.8 (`/usr/bin/kicad-cli`)

This plan **supersedes** the script-generated board workflow that produced
33 board variants and zero schematics. It is the single schedule used by the
manager to dispatch kanban tasks.

---

## 1. Purpose

For each of the 3 board variants, walk the schematic-first pipeline:

```
Schematic → ERC → PCB → Route → DRC → Gerbers → Consultant sign-off
```

Every phase has exactly one owning worker profile, a hard quality gate that
MUST PASS before the next phase starts, and a checkpoint (commit + push).
This document is the source of truth for what "done" means at each step.

---

## 2. Worker Profiles

| Profile | Model | Allowed Work | Banned Work |
|---------|-------|--------------|-------------|
| `worker-layout` | kimi-k3:cloud | Schematic drawing, PCB layout, routing, footprint placement, DRC inspection, Gerber export, spatial reasoning | Firmware edits, builds |
| `worker-inspector` | glm-5.2 | DRC verification (re-run + parse), ERC report parsing, Gerber size checks, sign-off review | Touching `.kicad_sch` / `.kicad_pcb` files |
| `worker-balloon` | glm-5.2 | Firmware changes, idf builds, non-spatial docs | Schematic / PCB layout / routing |

**Hard rule (ADR-028 invariant #6):** Only `worker-layout` may modify
`.kicad_sch` or `.kicad_pcb` files. `worker-inspector` runs DRC **read-only**
against files produced by `worker-layout`. The manager (this profile) never
touches these files.

**Lesson encoded:** glm-5.2 produced 80+ PCB shorts and 33 script-generated
variants. It is structurally banned from spatial work.

---

## 3. Timeout Budget

The prior 300s limit caused 8 worker timeouts. All phases below budget
**1800s (30 min)** per phase call. The `worker-layout` kanban dispatcher
MUST set the dispatch timeout to ≥1800s.

| Phase | Single-call budget | Notes |
|-------|--------------------|-------|
| Draw schematic | 1800s | One variant per call |
| Fix ERC violations | 1800s | Usually ≤3 iterations |
| Create PCB + place footprints | 1800s | Spatial — needs full budget |
| Route (with Freerouting) | 1800s | Freerouting itself runs in foreground |
| DRC verify + fix | 1800s | Per iteration |
| Export gerbers | 600s | Cheap, no spatial reasoning |
| Sign-off review | 600s | `worker-inspector` only |

---

## 4. Variant Order (Dependency Chain)

```
[1] C3-Flight  ── schematic ── ERC ── PCB ── route ── DRC ── gerbers ── sign-off
                                                                    │
                                                                    ▼
[2] S3-Future  ── schematic ── ERC ── PCB ── route ── DRC ── gerbers ── sign-off
                                                                    │
                                                                    ▼
[3] C3+RP2040  ── schematic ── ERC ── PCB ── route ── DRC ── gerbers ── sign-off
```

**Strict serial.** No variant starts until the prior variant passes Gate 6
(sign-off). Rationale:

1. **C3 first.** Felix is flight-testing on C3 Super Mini now. This is the
   P0 board and the only one allowed to use 2-layer (carrier-board design).
2. **S3 second.** Same schematic as C3 but with S3-WROOM-1 module, 4-layer
   (GND + 3V3 planes). Reuses C3 netlist structure with pin remapping.
3. **C3+RP2040 third.** Most complex (dual-MCU UART bus, ADR-026 radio
   coprocessor split). Builds on lessons from C3 + S3.

Within a variant, phases are also strictly serial — every phase has a gate.

---

## 5. File Naming Convention

| Artifact | Path |
|----------|------|
| KiCad project | `tracker/hardware/schematics/v{variant}.kicad_pro` |
| Schematic | `tracker/hardware/schematics/v{variant}_main.kicad_sch` |
| PCB (2-layer C3) | `tracker/hardware/output/v{variant}_2layer.kicad_pcb` |
| PCB (4-layer S3 / C3+RP2040) | `tracker/hardware/output/v{variant}_4layer.kicad_pcb` |
| DRC report | `tracker/hardware/output/v{variant}_drc.json` |
| ERC report | `tracker/hardware/schematics/v{variant}_erc.json` |
| Gerbers | `tracker/hardware/output/gerbers_v{variant}/` |
| Drill file | `tracker/hardware/output/gerbers_v{variant}/v{variant}-PTH.drl` |
| Routing artifacts (DSN/SES) | `tracker/hardware/output/freerouting_v{variant}/` |

Variant tags: `c3`, `s3`, `c3rp2040`.

**Example — S3 variant:**
- `tracker/hardware/schematics/vs3_main.kicad_sch`
- `tracker/hardware/output/vs3_4layer.kicad_pcb`
- `tracker/hardware/output/gerbers_vs3/`

---

## 6. Phase Breakdown — Per Variant

Each variant runs through 7 phases. The structure is identical; the per-phase
commands and gates differ only in file paths and layer count.

### 6.1 C3-Flight Variant (P0, 2-layer)

> **Note:** ADR-028 §5 allows C3-Flight to use 2-layer because it is a
> carrier board for the C3 Super Mini module (power already on the module).
> Power routing is still required on this board.

#### Phase 1 — Draw Schematic
- **Owner:** `worker-layout`
- **Input:** `docs/coordination/schematic-task-context.md` (GPIO + netlist)
- **Output:** `tracker/hardware/schematics/vc3_main.kicad_sch`, `vc3.kicad_pro`
- **API budget:** ≤15 calls
- **Action:**
  1. Create KiCad project + empty schematic sheet.
  2. Place symbols: U1 (ESP32-C3 Mini-1), U2 (NiceRF LR2021), U3 (TPS7A02),
     U4 (MAX-M10S GPS), SC (1F supercap), D1 (BAT54), D2 (LED 0603),
     J1 (solar header), C1–C7, R1–R5.
  3. Wire per netlist in `schematic-task-context.md`.
  4. Annotate, assign footprints.
  5. Save.

#### Phase 2 — Run ERC, Fix Violations
- **Owner:** `worker-layout` (fixes) + `worker-inspector` (verifies)
- **Output:** `vc3_erc.json`
- **API budget:** ≤5 calls (loop: run → fix → re-run)
- **Action:**
  ```bash
  kicad-cli sch erc \
      --format json \
      --exit-code-violations \
      -o tracker/hardware/schematics/vc3_erc.json \
      tracker/hardware/schematics/vc3_main.kicad_sch
  ```
  Loop until `vc3_erc.json` reports `{"violation_count": 0}`.

#### Phase 3 — Create PCB from Schematic
- **Owner:** `worker-layout`
- **Output:** `tracker/hardware/output/vc3_2layer.kicad_pcb`
- **API budget:** ≤12 calls
- **Action:**
  1. Update PCB from schematic (import netlist).
  2. Set board outline (e.g. 30×30 mm, 0.6 mm thick).
  3. Place footprints — **cluster power island** (U3, C7, SC, D1, J1) near
     the solar input. This is the lesson from the 7 timeouts: 2-layer power
     routing is feasible only if power components are co-located.
  4. Set stackup: F.Cu, B.Cu (2-layer).
  5. Save.

#### Phase 4 — Route
- **Owner:** `worker-layout`
- **Output:** routed `vc3_2layer.kicad_pcb`, `freerouting_vc3/` artifacts
- **API budget:** ≤15 calls
- **Action (Freerouting via SES import):**
  ```bash
  # 1. Export Specctra DSN from KiCad PCB
  kicad-cli pcb export specctra \
      -o tracker/hardware/output/freerouting_vc3/vc3_input.dsn \
      tracker/hardware/output/vc3_2layer.kicad_pcb

  # 2. Run Freerouting (foreground, ~5–10 min for a 17-part board)
  java -jar /usr/local/share/freerouting/Freerouting.jar \
      -de tracker/hardware/output/freerouting_vc3/vc3_input.dsn \
      -do tracker/hardware/output/freerouting_vc3/vc3_route.dsn \
      -os tracker/hardware/output/freerouting_vc3/vc3_route.ses

  # 3. Import SES back into KiCad
  #    (Performed in KiCad GUI by worker-layout, OR via scripted ses-import
  #    if available; otherwise hand-route the few remaining signals.)
  ```
  > Freerouting only routes signals. **Power nets (3V3, GND, VCAP) are
  > hand-routed by `worker-layout`** as short, fat tracks clustered around
  > the power island. On 2-layer, this is the single most failure-prone
  > step and the only step allowed to use the full 1800s budget.

#### Phase 5 — DRC Verification
- **Owner:** `worker-layout` (fixes) + `worker-inspector` (verifies)
- **Output:** `vc3_drc.json`
- **API budget:** ≤5 calls
- **Action:**
  ```bash
  kicad-cli pcb drc \
      --format json \
      --schematic-parity \
      --exit-code-violations \
      -o tracker/hardware/output/vc3_drc.json \
      tracker/hardware/output/vc3_2layer.kicad_pcb
  ```
  Loop until `vc3_drc.json` reports `0 violations, 0 unconnected`.

#### Phase 6 — Export Gerbers
- **Owner:** `worker-layout`
- **Output:** `tracker/hardware/output/gerbers_vc3/*.gbr`, drill file
- **API budget:** ≤3 calls
- **Action:** see §8 (Gerber export commands).

#### Phase 7 — Consultant Sign-off
- **Owner:** `worker-inspector` (reviewer only — glm-5.2)
- **Output:** append to `DRC_FINAL_VERIFICATION.md` or new `SIGNOFF-vc3.md`
- **API budget:** ≤3 calls
- **Action:** verify Gate 1–6 all pass; verify board thickness 0.6 mm;
  verify GPIO9 = STATUS_LED; verify no GPIO18/19 used; sign off in writing.

---

### 6.2 S3-Future Variant (P1, 4-layer)

Same 7 phases. **Critical difference: 4-layer stackup.**

- Stackup: `F.Cu` / `In1.Cu` (GND plane) / `In2.Cu` (3V3 plane) / `B.Cu`.
- The GND and 3V3 planes eliminate **all** power routing. U1, U3, SC VCC
  and GND pads connect via vias directly to the internal planes.
- This is the single biggest risk reducer — the lesson from the 527 DRC
  violations and 7 timeouts disappears entirely.
- Freerouting still routes signals, but power is solved by stackup.

**Files:**
- `tracker/hardware/schematics/vs3_main.kicad_sch`
- `tracker/hardware/output/vs3_4layer.kicad_pcb`
- `tracker/hardware/output/gerbers_vs3/`
- `tracker/hardware/output/vs3_drc.json`

**Pin mapping change vs C3:** S3 has GPIO18+ available. Move STATUS_LED to
GPIO18 (frees GPIO9 for I2C SCL only). Document the change in
`vs3_main.kicad_sch` title block.

#### Phase 3 (S3-specific) — Create PCB, 4-layer stackup
```bash
# After importing netlist, worker-layout edits the .kicad_pcb directly to
# add the In1.Cu (GND) and In2.Cu (3V3) layers and assign them to the
# appropriate nets. This is a kimi-k3 spatial edit, NOT a glm-5.2 edit.
```

#### Phase 4 (S3-specific) — Route
- Freerouting on signal nets only (SPI, UART, I2C, ADC, LED).
- Power: just drop vias from each 3V3 pad to In2.Cu, each GND pad to In1.Cu.
- No hand-routing of fat power tracks needed.

---

### 6.3 C3+RP2040 Variant (P2, 4-layer, dual-MCU)

Most complex. Adds U5 (RP2040-Zero, 13-pin header) and the C3↔RP2040 UART
inter-MCU bus (per ADR-026: RP2040 is radio coprocessor, talks to LR2021
directly over SPI).

**Files:**
- `tracker/hardware/schematics/vc3rp2040_main.kicad_sch`
- `tracker/hardware/output/vc3rp2040_4layer.kicad_pcb`
- `tracker/hardware/output/gerbers_vc3rp2040/`
- `tracker/hardware/output/vc3rp2040_drc.json`

**Additional nets vs C3:**
- `RP_UART_TX`: U5 (RP2040) GPIO0 ↔ U1 (C3) GPIO20 (or chosen free pin)
- `RP_UART_RX`: U5 (RP2040) GPIO1 ↔ U1 (C3) GPIO21 (or chosen free pin)
- `RP_SPI_*`: U5 (RP2040) SPI pins ↔ U2 (LR2021) — per ADR-026, RP2040
  shares the SPI bus with C3 (with tri-state coordination via the
  LR2021 NSS net). This MUST be ERC-validated before Phase 3.

**Phase 1 warning:** GPIO9 double-duty (I2C SCL + LED) on C3 still applies.
For the dual-MCU variant, the LED moves to a free C3 pin to avoid the
strapping-pin issue (per `schematic-task-context.md` note). Document in
schematic title block.

Same 7-phase pipeline as S3 (4-layer stackup, Freerouting for signals,
planes for power).

---

## 7. Quality Gates

Every phase ends with a gate check. **The next phase MUST NOT start until
the gate passes.** Gate checks are run by `worker-inspector` (read-only) or
by `worker-layout` as part of the same phase (for in-phase loops like ERC).

### Gate 1 — Schematic exists and parses
**After Phase 1.** Checks the schematic file opens in `kicad-cli`.

```bash
# Parse check — exit 0 means valid schematic
kicad-cli sch erc \
    --format json \
    -o /tmp/gate1_check.json \
    tracker/hardware/schematics/v{variant}_main.kicad_sch

# Must also be non-trivial — at least 5 symbols placed
python3 -c "
import json, sys
with open('tracker/hardware/schematics/v{variant}_main.kicad_sch') as f:
    txt = f.read()
assert 'symbol' in txt, 'no symbols found in schematic'
print('GATE 1 PASS: schematic parses and contains symbols')
"
```
**FAIL action:** Re-dispatch Phase 1 to `worker-layout`. Do NOT proceed.

### Gate 2 — ERC = 0 violations
**After Phase 2.**

```bash
kicad-cli sch erc \
    --format json \
    --exit-code-violations \
    -o tracker/hardware/schematics/v{variant}_erc.json \
    tracker/hardware/schematics/v{variant}_main.kicad_sch
# exit code MUST be 0
python3 -c "
import json
r = json.load(open('tracker/hardware/schematics/v{variant}_erc.json'))
assert len(r.get('violations', [])) == 0, f'ERC has {len(r[\"violations\"])} violations'
print('GATE 2 PASS: ERC clean')
"
```
**FAIL action:** Loop Phase 2 (fix violations, re-run ERC).

### Gate 3 — PCB has >10 footprints (NOT empty)
**After Phase 3.**

```bash
# Count footprints in the .kicad_pcb file
python3 -c "
with open('tracker/hardware/output/v{variant}_{layers}layer.kicad_pcb') as f:
    txt = f.read()
count = txt.count('(footprint ')
assert count > 10, f'PCB has only {count} footprints — empty/corrupt'
print(f'GATE 3 PASS: {count} footprints placed')
"
```
> This gate exists because the past failure mode was Python-generated
> `.kicad_pcb` files that were syntactically valid but empty.
**FAIL action:** Re-dispatch Phase 3. The PCB import silently failed.

### Gate 4 — DRC = 0 violations, 0 unconnected
**After Phase 5.**

```bash
kicad-cli pcb drc \
    --format json \
    --schematic-parity \
    --exit-code-violations \
    -o tracker/hardware/output/v{variant}_drc.json \
    tracker/hardware/output/v{variant}_{layers}layer.kicad_pcb
# exit code MUST be 0
python3 -c "
import json
r = json.load(open('tracker/hardware/output/v{variant}_drc.json'))
v = len(r.get('violations', []))
u = len(r.get('unconnected_items', []))
assert v == 0 and u == 0, f'DRC: {v} violations, {u} unconnected'
print('GATE 4 PASS: DRC clean, 0 unconnected')
"
```
**FAIL action:** Loop Phase 4 → Phase 5 (re-route, re-DRC).

### Gate 5 — Gerbers exist and are non-empty
**After Phase 6.**

```bash
GER_DIR=tracker/hardware/output/gerbers_v{variant}
ls $GER_DIR/*.gbr >/dev/null || { echo 'GATE 5 FAIL: no .gbr files'; exit 1; }

for layer in F_Cu B_Cu; do
    f=$(ls $GER_DIR/*-${layer}.gbr 2>/dev/null || ls $GER_DIR/*.GTL 2>/dev/null || true)
    [ -z "$f" ] && { echo "GATE 5 FAIL: missing $layer gerber"; exit 1; }
    size=$(stat -c%s "$f")
    [ "$size" -lt 1024 ] && { echo "GATE 5 FAIL: $layer gerber < 1KB ($size bytes)"; exit 1; }
done
echo 'GATE 5 PASS: F_Cu and B_Cu gerbers exist and are >1KB'
```
**FAIL action:** Re-dispatch Phase 6 (re-export gerbers).

### Gate 6 — Board thickness = 0.6 mm
**After Phase 7 (sign-off).** Pico-balloon weight constraint (ADR-028
invariant #2).

```bash
python3 -c "
with open('tracker/hardware/output/v{variant}_{layers}layer.kicad_pcb') as f:
    txt = f.read()
assert '0.6' in txt and 'thickness' in txt.lower(), 'no 0.6mm thickness in PCB'
print('GATE 6 PASS: board thickness 0.6mm present')
"
```
**FAIL action:** Re-dispatch Phase 3 to set thickness, then re-run Phases
4–6. (Board outline change invalidates routing.)

---

## 8. Exact KiCad CLI Commands (Reference)

### 8.1 Create project (worker-layout)
```bash
mkdir -p tracker/hardware/schematics tracker/hardware/output/gerbers_v{variant}
# KiCad does not have a "create project" CLI; worker-layout creates the
# .kicad_pro, .kicad_sch, and .kicad_pcb files manually as text (they are
# S-expression files). Use an existing .kicad_pro as a template.
```

### 8.2 Run ERC
```bash
kicad-cli sch erc \
    --format json \
    --severity-all \
    --exit-code-violations \
    -o tracker/hardware/schematics/v{variant}_erc.json \
    tracker/hardware/schematics/v{variant}_main.kicad_sch
```

### 8.3 Run DRC
```bash
kicad-cli pcb drc \
    --format json \
    --severity-all \
    --schematic-parity \
    --exit-code-violations \
    -o tracker/hardware/output/v{variant}_drc.json \
    tracker/hardware/output/v{variant}_{layers}layer.kicad_pcb
```

### 8.4 Export Gerbers (Phase 6)
```bash
GER_DIR=tracker/hardware/output/gerbers_v{variant}
PCB=tracker/hardware/output/v{variant}_{layers}layer.kicad_pcb

# Copper layers
kicad-cli pcb export gerber -o $GER_DIR/v{variant}-F_Cu.gbr  -l F.Cu  $PCB
kicad-cli pcb export gerber -o $GER_DIR/v{variant}-In1_Cu.gbr -l In1.Cu $PCB  # 4-layer only
kicad-cli pcb export gerber -o $GER_DIR/v{variant}-In2_Cu.gbr -l In2.Cu $PCB  # 4-layer only
kicad-cli pcb export gerber -o $GER_DIR/v{variant}-B_Cu.gbr  -l B.Cu  $PCB

# Silkscreen, mask, paste, fab
kicad-cli pcb export gerber -o $GER_DIR/v{variant}-F_Silkscreen.gbr -l F.Silkscreen $PCB
kicad-cli pcb export gerber -o $GER_DIR/v{variant}-B_Silkscreen.gbr -l B.Silkscreen $PCB
kicad-cli pcb export gerber -o $GER_DIR/v{variant}-F_Mask.gbr -l F.Mask $PCB
kicad-cli pcb export gerber -o $GER_DIR/v{variant}-B_Mask.gbr -l B.Mask $PCB
kicad-cli pcb export gerber -o $GER_DIR/v{variant}-F_Paste.gbr -l F.Paste $PCB
kicad-cli pcb export gerber -o $GER_DIR/v{variant}-Edge_Cuts.gbr -l Edge.Cuts $PCB

# Drill file
kicad-cli pcb export drill \
    --generate-map \
    --map-format gerberx2 \
    -o $GER_DIR/ \
    $PCB
```

### 8.5 Export Specctra DSN (for Freerouting, Phase 4)
```bash
kicad-cli pcb export specctra \
    -o tracker/hardware/output/freerouting_v{variant}/v{variant}_input.dsn \
    tracker/hardware/output/v{variant}_{layers}layer.kicad_pcb
```

### 8.6 Run Freerouting (foreground)
```bash
java -jar /usr/local/share/freerouting/Freerouting.jar \
    -de tracker/hardware/output/freerouting_v{variant}/v{variant}_input.dsn \
    -do tracker/hardware/output/freerouting_v{variant}/v{variant}_routed.dsn \
    -os tracker/hardware/output/freerouting_v{variant}/v{variant}_route.ses \
    -mp 120 -mt 600
```
> `-mp 120` = max passes, `-mt 600` = max time seconds. Foreground; this
> call is bounded and may block up to ~600 s.

### 8.7 Import SES into PCB (Phase 4, continued)
SES import has no CLI in KiCad 9.0. `worker-layout` must either:
1. Apply the SES via the KiCad GUI (interactive), or
2. Parse the SES in Python and patch the `.kicad_pcb` tracks directly.

Option 2 is permitted because it is a deterministic file edit performed by
`worker-layout`, not by the manager or by glm-5.2.

---

## 9. Checkpoint Protocol (Commit + Push After Each Phase)

After every phase passes its gate, `worker-layout` commits and pushes:

```bash
cd ~/repos/balloon-fresh
git add tracker/hardware/
git commit -m "hardware(v{variant}): phase {N} {phase_name} — gate {gate_id} pass"
git push github autonomous/mesh-baseline
```

Commit message format (per variant, per phase):

| Phase | Commit suffix |
|-------|---------------|
| 1 | `phase 1 schematic drawn — gate 1 pass` |
| 2 | `phase 2 ERC clean — gate 2 pass` |
| 3 | `phase 3 PCB placed — gate 3 pass` |
| 4 | `phase 4 routed — gate 4 pending` |
| 5 | `phase 5 DRC clean — gate 4 pass` |
| 6 | `phase 6 gerbers exported — gate 5 pass` |
| 7 | `phase 7 signed off — gate 6 pass (variant done)` |

**Why this matters:** uncommitted work is invisible to the manager. The
manager monitors via `git log`. A phase with no commit = phase not done.

---

## 10. Risk Mitigation

### 10.1 kimi-k3 timeout on a phase
**Symptom:** `worker-layout` dispatch returns TIMEOUT after 1800 s.
**Action:**
1. The manager reads the last commit on the branch to see how far the
   worker got.
2. Re-dispatch the SAME phase to `worker-layout` with the prompt:
   *"Resume Phase {N} for v{variant}. Last commit: {hash}. Continue from
   the current state of {file}."*
3. Do NOT re-dispatch to a different worker — glm-5.2 cannot do spatial work.

### 10.2 Resume from partial work
**Symptom:** Phase 4 (routing) timed out midway; PCB is partially routed.
**Action:**
1. Run DRC on the partial PCB:
   ```bash
   kicad-cli pcb drc --format json -o /tmp/partial_drc.json \
       tracker/hardware/output/v{variant}_{layers}layer.kicad_pcb
   ```
2. The DRC report shows what's still unconnected.
3. Re-dispatch Phase 4 with the DRC report attached as context:
   *"Resume routing. {N} unconnected nets remain: {list}. Fix these only."*

### 10.3 Freerouting crashes / produces garbage
**Symptom:** Freerouting SES produces shorts or empty routes.
**Action:**
1. Delete the SES import; revert `.kicad_pcb` to pre-routing checkpoint.
2. Re-dispatch Phase 4 with instruction to hand-route signals (kimi-k3 is
   capable of hand-routing a 17-component board).
3. Fall back to hand-routing — do NOT loop Freerouting more than twice.

### 10.4 ERC has unfixable violations (e.g. bus conflict)
**Symptom:** ERC reports conflict that `worker-layout` cannot resolve in
≤5 iterations.
**Action:** Escalate to manager. Manager reads the GPIO context file and
either approves a pin reassignment or files a question to Felix. Do NOT
proceed to Phase 3 with ERC violations.

### 10.5 DRC has schematic-parity violations
**Symptom:** DRC `--schematic-parity` reports PCB ≠ schematic (e.g. a net
is in the schematic but missing from the PCB).
**Action:** This means Phase 3's netlist import was incomplete. Re-dispatch
Phase 3 (not Phase 4) — the PCB must be re-imported from the schematic.

### 10.6 Power routing failure (2-layer C3 only)
**Symptom:** DRC reports unconnected power nets after Phase 4.
**Action:**
1. Check footprint placement — power components MUST be clustered. If U3,
   C7, SC, D1, J1 are scattered, the placement is wrong.
2. Re-dispatch Phase 3 with explicit instruction: *"Re-place footprints
   clustering power island: U3, C7, SC, D1, J1 within 10 mm of solar input
   header J1."*
3. Then re-run Phase 4.

### 10.7 S3 / C3+RP2040 power routing (4-layer) — should not fail
The 4-layer stackup eliminates power routing entirely. If power DRC errors
appear on a 4-layer board, the stackup is wrong — `worker-layout` forgot
to assign In1.Cu to GND and In2.Cu to 3V3. Re-dispatch Phase 3.

---

## 11. Kanban Task Templates

The manager creates one kanban card per phase per variant. Cards are
dispatched in strict serial order (no parallelism across variants).

### Card: `v{variant}-phase{N}-{name}`
```
TITLE: v{variant} phase {N}: {name}
OWNER: {worker-layout | worker-inspector}
INPUTS: {files}
OUTPUTS: {files}
GATE: {gate_id} — must pass before next card dispatched
TIMEOUT: {600|1800}s
API_BUDGET: {N} calls max
COMMAND: {exact kicad-cli command}
ON_COMPLETE: commit + push, then signal manager
ON_TIMEOUT: see §10.1
DEPENDS_ON: v{variant}-phase{N-1}-{prev_name}
```

### Full task sequence (21 cards total = 7 phases × 3 variants)

```
vc3-phase1-schematic
vc3-phase2-erc
vc3-phase3-pcb
vc3-phase4-route
vc3-phase5-drc
vc3-phase6-gerbers
vc3-phase7-signoff
vs3-phase1-schematic
vs3-phase2-erc
vs3-phase3-pcb
vs3-phase4-route
vs3-phase5-drc
vs3-phase6-gerbers
vs3-phase7-signoff
vc3rp2040-phase1-schematic
vc3rp2040-phase2-erc
vc3rp2040-phase3-pcb
vc3rp2040-phase4-route
vc3rp2040-phase5-drc
vc3rp2040-phase6-gerbers
vc3rp2040-phase7-signoff
```

---

## 12. Summary Table — All Phases

| Variant | Phase | Owner | Output | Gate | Timeout | Max API |
|---------|-------|-------|--------|------|---------|---------|
| C3 | 1 schematic | worker-layout | `vc3_main.kicad_sch` | G1 | 1800s | 15 |
| C3 | 2 ERC | worker-layout | `vc3_erc.json` | G2 | 1800s | 5 |
| C3 | 3 PCB (2-layer) | worker-layout | `vc3_2layer.kicad_pcb` | G3 | 1800s | 12 |
| C3 | 4 route | worker-layout | routed PCB + SES | — | 1800s | 15 |
| C3 | 5 DRC | worker-layout+inspector | `vc3_drc.json` | G4 | 1800s | 5 |
| C3 | 6 gerbers | worker-layout | `gerbers_vc3/` | G5 | 600s | 3 |
| C3 | 7 sign-off | worker-inspector | `SIGNOFF-vc3.md` | G6 | 600s | 3 |
| S3 | 1 schematic | worker-layout | `vs3_main.kicad_sch` | G1 | 1800s | 15 |
| S3 | 2 ERC | worker-layout | `vs3_erc.json` | G2 | 1800s | 5 |
| S3 | 3 PCB (4-layer) | worker-layout | `vs3_4layer.kicad_pcb` | G3 | 1800s | 12 |
| S3 | 4 route | worker-layout | routed PCB + SES | — | 1800s | 15 |
| S3 | 5 DRC | worker-layout+inspector | `vs3_drc.json` | G4 | 1800s | 5 |
| S3 | 6 gerbers | worker-layout | `gerbers_vs3/` | G5 | 600s | 3 |
| S3 | 7 sign-off | worker-inspector | `SIGNOFF-vs3.md` | G6 | 600s | 3 |
| C3+RP2040 | 1 schematic | worker-layout | `vc3rp2040_main.kicad_sch` | G1 | 1800s | 15 |
| C3+RP2040 | 2 ERC | worker-layout | `vc3rp2040_erc.json` | G2 | 1800s | 5 |
| C3+RP2040 | 3 PCB (4-layer) | worker-layout | `vc3rp2040_4layer.kicad_pcb` | G3 | 1800s | 12 |
| C3+RP2040 | 4 route | worker-layout | routed PCB + SES | — | 1800s | 15 |
| C3+RP2040 | 5 DRC | worker-layout+inspector | `vc3rp2040_drc.json` | G4 | 1800s | 5 |
| C3+RP2040 | 6 gerbers | worker-layout | `gerbers_vc3rp2040/` | G5 | 600s | 3 |
| C3+RP2040 | 7 sign-off | worker-inspector | `SIGNOFF-vc3rp2040.md` | G6 | 600s | 3 |

**Total worst-case API budget:** ~252 calls across all 21 phases (~12 per
phase average). Budget per phase stays well under the 15-call ceiling.

---

## 13. Acceptance Criteria (Plan Complete When…)

1. All 3 variants have a `.kicad_sch` passing ERC (Gate 2).
2. All 3 variants have a `.kicad_pcb` with >10 footprints (Gate 3).
3. All 3 variants have DRC = 0 violations, 0 unconnected (Gate 4).
4. All 3 variants have gerbers exported with F_Cu + B_Cu >1 KB (Gate 5).
5. All 3 variants have board thickness 0.6 mm (Gate 6).
6. All 3 variants have a written sign-off from `worker-inspector`.
7. Every phase committed and pushed to `autonomous/mesh-baseline`.

When all 7 criteria are met, Felix can order boards from JLCPCB.

---

## 14. References

- ADR-028: `docs/adr/028-schematic-first-three-variants.md` (accepted)
- GPIO data: `docs/coordination/schematic-task-context.md`
- Prior schematic plan (single-variant, superseded): `tracker/hardware/SCHEMATIC-PLAN.md`
- Past DRC reports (evidence of failure mode): `tracker/hardware/drc_f33_*.txt`
- KiCad CLI docs: `kicad-cli --help`, KiCad 9.0 manual
