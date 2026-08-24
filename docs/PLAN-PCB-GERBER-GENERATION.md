# PLAN: Dual-Variant Hub Board PCB Layout — Gerber Generation

**Created:** 2026-07-29
**Author:** balloon-circuit-design sub-manager
**Status:** Ready for kanban dispatch
**Worktree:** ~/worktrees/balloon-circuit-design/

---

## BACKGROUND

Two hub board variants needed for JLCPCB ordering:

| Variant | Module | Board Size | Antenna | Schematic | PCB File |
|---------|--------|-----------|---------|-----------|----------|
| V1 (non-PA) | NiceRF LoRa2021 bare | 50×40mm, 0.6mm | Wire dipole pads | hub_schematic.py ✅ | hub_board_v1.kicad_pcb ⚠️ |
| V2 (2W PA) | NiceRF LoRa2021F33-2G4 | 75×55mm, 0.8mm | SMA edge connectors | hub_schematic_f33.py ✅ | hub_board_f33.kicad_pcb ⚠️ |

Schematics are COMPLETE (0 ERC errors, valid netlists). PCB files are GENERATED with full component placement but have format bugs preventing kicad-cli from loading them.

---

## ROOT CAUSE OF GERBER BLOCKER

**Problem:** kicad-cli reports "Failed to load board" on both .kicad_pcb files.

**Root cause (identified by comparing against working KiCad 9 demo files):**

The demo files at `/usr/share/kicad/demos/stickhub/StickHub.kicad_pcb` load fine. Diff analysis found two format differences in segment/via entries:

### Bug 1: Segment net format
**WRONG (my files):**
```
(segment (start 5.00 20.00) (end 9.46 20.00) (width 0.25) (layer "F.Cu") (net 1 "3V3") (uuid "seg-001"))
```
**CORRECT (KiCad 9 format):**
```
(segment (start 5.00 20.00) (end 9.46 20.00) (width 0.25) (layer "F.Cu") (net 1) (uuid "00a04fe8-6f8f-4077-864c-7740ef9cf243"))
```
Segments use `(net N)` — number only, NO name string. Footprint pads DO use `(net N "name")` — that's fine.

### Bug 2: UUID format
**WRONG:** `(uuid "seg-001")`, `(uuid "via-002")`, `(uuid "edge-1")`
**CORRECT:** `(uuid "00a04fe8-6f8f-4077-864c-7740ef9cf243")` — must be valid UUID v4 format.

### Bug 3: Setup section
Missing mandatory fields for KiCad 9:
```
(allow_soldermask_bridges_in_footprints no)
(tenting front back)
```

---

## TASKS FOR KANBAN WORKERS

### TASK 1: Fix .kicad_pcb format bugs (both files)

**Worker:** worker-balloon (leaf)
**Estimate:** 10 minutes
**Files:**
- `tracker/hardware/gen_pcb.py` (the generator script)
- OR directly fix the output files:
  - `tracker/hardware/hub_board_v1.kicad_pcb`
  - `tracker/hardware/hub_board_f33.kicad_pcb`

**Steps:**

1. Fix the `gen_pcb.py` script's `seg()` function:
   ```python
   # CHANGE: drop net name in segments, use real UUID
   def seg(x1, y1, x2, y2, net_name, width=0.25, layer="F.Cu"):
       nonlocal seg_id
       s = f'  (segment (start {x1:.2f} {y1:.2f}) (end {x2:.2f} {y2:.2f}) (width {width}) (layer "{layer}") (net {nid[net_name]}) (uuid "{uuid.uuid4()}"))\n'
       seg_id += 1
       return s
   ```

2. Fix the `via()` function similarly — drop net name, use real UUID.

3. Fix the `header()` function's setup section — add:
   ```
   (allow_soldermask_bridges_in_footprints no)
   (tenting front back)
   ```

4. Fix ALL `(uuid "...")` entries in `board_outline()`, `ground_pour()`, silkscreen text, and footprint blocks — replace string IDs with `str(uuid.uuid4())`.

5. Regenerate both PCBs:
   ```bash
   cd tracker/hardware/
   python3 gen_pcb.py
   ```

6. Verify kicad-cli loads them:
   ```bash
   kicad-cli pcb drc --output drc_v1.txt hub_board_v1.kicad_pcb
   kicad-cli pcb drc --output drc_f33.txt hub_board_f33.kicad_pcb
   ```
   Both should report "Found N violations" (not "Failed to load board").

**Success criteria:** `kicad-cli pcb drc` runs without "Failed to load board" error.

**Commit:**
```bash
git add tracker/hardware/gen_pcb.py tracker/hardware/hub_board_v1.kicad_pcb tracker/hardware/hub_board_f33.kicad_pcb
git commit -m "fix(pcb): KiCad 9 format — correct segment net format + UUIDs + setup section"
```

---

### TASK 2: Auto-route remaining nets + DRC cleanup (V1 board)

**Worker:** worker-balloon (leaf)
**Estimate:** 20 minutes
**Depends on:** Task 1
**File:** `tracker/hardware/hub_board_v1.kicad_pcb`

**Steps:**

1. Export DSN file for freerouting:
   ```bash
   kicad-cli pcb export dsn --output hub_board_v1.dsn hub_board_v1.kicad_pcb
   ```
   If `kicad-cli pcb export dsn` doesn't exist, use this alternative:
   ```bash
   # Write a Python script that reads the .kicad_pcb and generates Specctra DSN format
   # See: https://dev-docs.kicad.org/en/apis-and-binding/pcbnew/
   ```

2. Run freerouting (Java 25 required):
   ```bash
   /usr/lib/jvm/java-25-openjdk-amd64/bin/java -jar /home/c03rad0r/esp32-balloon-integration/freerouting.jar \
     -di hub_board_v1.dsn \
     -do hub_board_v1_routed.dsn \
     -dz hub_board_v1.session
   ```
   Check exact CLI args first:
   ```bash
   /usr/lib/jvm/java-25-openjdk-amd64/bin/java -jar /home/c03rad0r/esp32-balloon-integration/freerouting.jar 2>&1 | head -20
   ```

3. If freerouting works, import the session back:
   ```bash
   # Import the .session file back into KiCad (may need pcbnew API or manual merge)
   # If pcbnew Python segfaults, merge routing manually by parsing the session file
   ```

4. If freerouting fails or is too complex, route remaining nets MANUALLY in gen_pcb.py:
   - Add segment entries for each unrouted net
   - Use Manhattan routing (horizontal + vertical segments only)
   - Use vias to jump between layers when paths cross
   - Priority: SPI nets (SCK, MOSI, MISO, NSS) shortest path between RP2040 and LR2021
   - Then: control nets (BUSY, IRQ, RST)
   - Then: UART (ESP↔RP2040, GPS→ESP)
   - Then: I2C (SDA, SCL)
   - Power nets already routed, verify GND pour connects all GND pads

5. Run DRC:
   ```bash
   kicad-cli pcb drc --output drc_v1_final.txt hub_board_v1.kicad_pcb
   ```

6. Fix DRC violations (common ones):
   - Clearance violations → increase trace spacing or reroute
   - Unconnected nets → add missing segments
   - Copper pour islands → adjust pour boundary

**Success criteria:** DRC shows 0 violations, 0 unconnected items.

**Commit:**
```bash
git add tracker/hardware/hub_board_v1.kicad_pcb
git commit -m "feat(pcb): V1 non-PA — all nets routed, DRC clean"
```

---

### TASK 3: Auto-route remaining nets + DRC cleanup (V2 F33 board)

**Worker:** worker-balloon (leaf)
**Estimate:** 25 minutes
**Depends on:** Task 1
**File:** `tracker/hardware/hub_board_f33.kicad_pcb`

Same as Task 2 but for V2. Additional constraints:

- F33 VCC trace: 0.8mm minimum width (1.2A peak current)
- RF traces (antenna → SMA): 1.2mm width, SHORT and STRAIGHT, no bends
- All 7 F33 GND pins need ground vias stitching to B.Cu pour
- 100µF bulk cap must connect to F33 pin 1 with short fat trace

**Commit:**
```bash
git add tracker/hardware/hub_board_f33.kicad_pcb
git commit -m "feat(pcb): V2 F33 2W PA — all nets routed, DRC clean"
```

---

### TASK 4: Generate Gerbers + SVG previews (both boards)

**Worker:** worker-balloon (leaf)
**Estimate:** 10 minutes
**Depends on:** Tasks 2 + 3

**Steps:**

1. Create output directories:
   ```bash
   mkdir -p tracker/hardware/gerbers_v1/
   mkdir -p tracker/hardware/gerbers_f33/
   ```

2. V1 Gerbers:
   ```bash
   kicad-cli pcb export gerbers --output gerbers_v1/ hub_board_v1.kicad_pcb
   kicad-cli pcb export drill --output gerbers_v1/ hub_board_v1.kicad_pcb
   kicad-cli pcb export svg --output hub_board_v1_top.svg --layers "F.Cu,Edge.Cuts,F.SilkS" hub_board_v1.kicad_pcb
   kicad-cli pcb export svg --output hub_board_v1_bottom.svg --layers "B.Cu,Edge.Cuts,B.SilkS" hub_board_v1.kicad_pcb
   ```

3. V2 Gerbers (same commands, different files):
   ```bash
   kicad-cli pcb export gerbers --output gerbers_f33/ hub_board_f33.kicad_pcb
   kicad-cli pcb export drill --output gerbers_f33/ hub_board_f33.kicad_pcb
   kicad-cli pcb export svg --output hub_board_f33_top.svg --layers "F.Cu,Edge.Cuts,F.SilkS" hub_board_f33.kicad_pcb
   kicad-cli pcb export svg --output hub_board_f33_bottom.svg --layers "B.Cu,Edge.Cuts,B.SilkS" hub_board_f33.kicad_pcb
   ```

4. Verify Gerber files exist (should be ~10 per board):
   ```bash
   ls -la gerbers_v1/
   ls -la gerbers_f33/
   ```
   Expected files: .GTL (top copper), .GBL (bottom copper), .GTS (top solder mask), .GBS (bottom solder mask), .GTO (top silkscreen), .GBO (bottom silkscreen), .GKO (board outline), .TXT (drill), .DRL (drill NC), .GML (mechanical).

**Success criteria:** Gerber zip ready for JLCPCB upload.

**Commit:**
```bash
git add tracker/hardware/gerbers_v1/ tracker/hardware/gerbers_f33/ tracker/hardware/hub_board_v1*.svg tracker/hardware/hub_board_f33*.svg
git commit -m "feat(pcb): Gerber files + SVG previews for both hub board variants"
git push github balloon-circuit-design
```

---

### TASK 5: Generate BOM + Pick-and-Place files

**Worker:** worker-balloon (leaf)
**Estimate:** 10 minutes
**Depends on:** Task 4

**Steps:**

1. Export position files (for JLCPCB pick-and-place / SMT assembly):
   ```bash
   kicad-cli pcb export pos --output gerbers_v1/pos_v1.csv hub_board_v1.kicad_pcb
   kicad-cli pcb export pos --output gerbers_f33/pos_f33.csv hub_board_f33.kicad_pcb
   ```

2. Write BOM files manually (cross-reference with docs/component-guide.md):
   - `tracker/hardware/BOM-v1.csv` — non-PA variant
   - `tracker/hardware/BOM-f33.csv` — F33 2W PA variant
   - Include: reference designator, part number, LCSC part #, quantity, unit price, total price

3. Cross-check LCSC part numbers (Felix buys from LCSC/JLCPCB):
   - Check availability at lcsc.com for: TPS7A0233DBVR, BAT54, 100µF 1206, MS5611

**Commit:**
```bash
git add tracker/hardware/BOM-v1.csv tracker/hardware/BOM-f33.csv tracker/hardware/gerbers_v1/pos_v1.csv tracker/hardware/gerbers_f33/pos_f33.csv
git commit -m "feat(bom): BOM + pick-and-place files for both variants"
git push github balloon-circuit-design
```

---

## FILE INVENTORY

### Already committed (don't touch unless fixing bugs):
| File | Purpose | Status |
|------|---------|--------|
| `tracker/hardware/hub_board/hub_schematic.py` | V1 SKiDL schematic | ✅ Complete |
| `tracker/hardware/hub_board/hub_schematic_f33.py` | V2 SKiDL schematic | ✅ Complete |
| `tracker/hardware/hub_board/hub_board.net` | V1 netlist | ✅ Complete |
| `tracker/hardware/hub_board/hub_board_f33.net` | V2 netlist | ✅ Complete |
| `tracker/hardware/gen_pcb.py` | PCB generator script | ⚠️ Needs format fix (Task 1) |
| `docs/f33-module/LoRa2021F33-2G4-datasheet-v1.1.pdf` | F33 datasheet | ✅ Committed |
| `docs/DUAL-VARIANT-DESIGN.md` | Design spec | ✅ Committed |

### To be created by workers:
| File | Task |
|------|------|
| `tracker/hardware/hub_board_v1.kicad_pcb` (fixed) | Task 1 |
| `tracker/hardware/hub_board_f33.kicad_pcb` (fixed) | Task 1 |
| `tracker/hardware/gerbers_v1/*` | Task 4 |
| `tracker/hardware/gerbers_f33/*` | Task 4 |
| `tracker/hardware/BOM-v1.csv` | Task 5 |
| `tracker/hardware/BOM-f33.csv` | Task 5 |

---

## TOOL REFERENCE

```bash
# KiCad CLI (works headless, confirmed):
kicad-cli pcb drc --output report.txt input.kicad_pcb
kicad-cli pcb export gerbers --output gerbers/ input.kicad_pcb
kicad-cli pcb export drill --output gerbers/ input.kicad_pcb
kicad-cli pcb export svg --output out.svg --layers "F.Cu,Edge.Cuts" input.kicad_pcb
kicad-cli pcb export pos --output pos.csv input.kicad_pcb

# Freerouting (needs Java 25):
/usr/lib/jvm/java-25-openjdk-amd64/bin/java -jar /home/c03rad0r/esp32-balloon-integration/freerouting.jar

# Custom footprints (already exist, don't recreate):
ls tracker/hardware/hub_board_diy/custom.pretty/
# → LoRa2021_Castellated.kicad_mod
# → LoRa2021F33_2G4.kicad_mod
# → ESP32-C3_Mini_V1_Header.kicad_mod
# → SolderBridge_2Pad.kicad_mod

# Netlists (import reference):
cat tracker/hardware/hub_board/hub_board.net       # V1
cat tracker/hardware/hub_board/hub_board_f33.net   # V2
```

**NOTE:** pcbnew Python module SEGFAULTS on this machine (headless). Do NOT use it. Use text generation + kicad-cli only.

---

## PIN MAP QUICK REFERENCE

### V1: RP2040 → bare LoRa2021
| RP2040 | Function | LR2021 Pin |
|--------|----------|------------|
| GP2 | SPI0 SCK | 5 |
| GP3 | SPI0 MOSI | 4 |
| GP4 | SPI0 MISO | 3 |
| GP5 | NSS (CS) | 6 |
| GP6 | BUSY | 7 |
| GP7 | IRQ (DIO9) | 15 |
| GP8 | RST | 14 |
| LR2021 GND pins | 2, 8, 11, 12, 18 |

### V2: RP2040 → F33 (DIFFERENT pinout!)
| RP2040 | Function | F33 Pin |
|--------|----------|---------|
| GP2 | SPI0 SCK | 12 |
| GP3 | SPI0 MOSI | 15 |
| GP4 | SPI0 MISO | 16 |
| GP5 | NSS (CS) | 13 |
| GP6 | BUSY | 14 |
| GP7 | IRQ | 18 |
| GP8 | RST | 17 |
| GP9 | CE (NEW) | 5 |
| F33 GND pins | 2, 3, 4, 6, 7, 8, 11 (7 pins!) |
| F33 VCC pin 1 | 5V from supercap (NOT 3V3) |
| F33 ANT pin 9 | Sub-GHz → SMA connector |
| F33 ANT-2G4 pin 10 | 2.4GHz → SMA connector |
