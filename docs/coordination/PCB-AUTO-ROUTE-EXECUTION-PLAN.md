# PCB Auto-Routing Pipeline + Single-MCU Board Design — Worker Execution Plan

**Date:** 2026-08-05
**Author:** Senior Project Planner (automated)
**Status:** READY FOR KANBAN SCHEDULING
**Critical Path:** YES — JLCPCB 2-week lead time starts when gerbers are uploaded

---

## ⚠️ READ THIS FIRST — Worker Context

You are a worker agent picking up this plan from a kanban board. You do NOT have the original conversation's context. This document is your complete briefing. Read it fully before starting any phase.

### Verified Environment Facts (do not re-verify)

| Item | Status | Details |
|------|--------|---------|
| KiCad version | 9.0.8 | `kicad-cli` at `/usr/bin/kicad-cli` |
| python3.14 + pcbnew | ✅ WORKS | **MUST use `/usr/bin/python3.14`** — NOT `python3` (3.11 segfaults) |
| `pcbnew.NewBoard()` | ✅ WORKS | Creates empty `.kicad_pcb` headless |
| `pcbnew.LoadBoard()` | ❌ NEEDS wxApp | **Fails headless.** Cannot load existing boards in scripts. Must use `NewBoard()` |
| `pcbnew.PCB_TRACK` | ✅ WORKS | `SetStart/SetEnd/SetWidth/SetLayer/SetNet` all functional |
| `pcbnew.FOOTPRINT` | ✅ WORKS | Can create footprints programmatically |
| `kicad-cli pcb drc --format json` | ✅ WORKS | Outputs parseable JSON with violations + unconnected |
| `kicad-cli pcb export gerbers` | ✅ WORKS | All layers, headless |
| `kicad-cli pcb export drill` | ✅ WORKS | Excellon format for JLCPCB |
| KiCad coordinate unit | nanometers | `pcbnew.FromMM(1.0) = 1000000` (1M nm = 1mm) |
| F_Cu layer constant | 0 | `pcbnew.F_Cu = 0` |
| B_Cu layer constant | 2 | `pcbnew.B_Cu = 2` |

### Architecture Decision (FINAL — do not revisit)

**Single-MCU design.** ESP32-C3 directly controls LR2021 via SPI. No RP2040. No dual-MCU. No unified board. The firmware is already written and tested for this architecture (39 commits, 13 CLI commands, tests pass).

### What Went Wrong on V1 (DO NOT REPEAT)

| V1 Failure | Root Cause | This Plan's Fix |
|------------|-----------|-----------------|
| 18× 3V3↔GND shorts | Ground copper pour overlapping 3V3 pads | **No copper pours. Route GND as explicit tracks.** |
| All 4 SPI lines shorted together | `gen_pcb.py` had no net-to-net clearance | **A* router with collision grid + DRC in loop** |
| 43 unconnected nets | Router didn't complete | **DRC iteration loop until 0 unconnected** |
| Wrong architecture (dual-MCU) | V1 was C3+RP2040, firmware is single-MCU | **New board: C3 only, no RP2040 footprint** |

---

## GPIO Pin Assignment (from firmware — verified against Kconfig)

**Source:** `tracker/firmware/main/app_main.cpp` lines 85-94, `tracker/firmware/main/radio_task.cpp` line 34, `tracker/firmware/main/Kconfig.projbuild`

### Primary Pin Assignment

| Function | GPIO | Pin Status | Notes |
|----------|------|------------|-------|
| GPS UART RX | GPIO1 | Required | NMEA from GPS module |
| GPS UART TX | GPIO0 | Optional | Config to GPS (-1 to disable in Kconfig) |
| SPI MISO | GPIO2 | Required | LR2021 → C3 |
| LR2021 RST | GPIO3 | Required | Active-low reset |
| LR2021 BUSY | GPIO4 | Required | IRQ/handshake |
| LR2021 DIO9 | GPIO5 | Required | IRQ pin |
| SPI SCK | GPIO6 | Required | LR2021 SPI clock |
| SPI MOSI | GPIO7 | Required | C3 → LR2021 |
| ADC (voltage divider) | GPIO8 | Required | Supercap voltage monitor |
| I2C SDA / LED | GPIO9 | **CONFLICT** | Can only be one — see below |
| SPI NSS (CS) | GPIO10 | Required | LR2021 chip select |
| LED | GPIO18 | **VERIFY** | May be USB D- on some C3 modules |
| FEM_TX | GPIO19 | **VERIFY** | May be USB D+ on some C3 modules |

### GPIO9 Conflict Resolution

GPIO9 must serve as either I2C SDA or LED — not both. Options:

| Option | GPIO9 | I2C | LED | Recommendation |
|--------|-------|-----|-----|----------------|
| A: Drop I2C | LED | No SDA | ✅ Dedicated | **RECOMMENDED** — simplest, fewest nets |
| B: Drop LED | I2C SDA | SDA only (no SCL) | No LED | BMP280 needs SCL too — can't work with 1 pin |
| C: Software I2C | I2C SDA | Bit-banged SDA+SCL on 1 pin | No LED | Complex, unreliable |

**Decision: Option A. Drop I2C for first prototype. Route LED on GPIO9.**

Rationale:
- BMP280/MS5611 is optional (Kconfig `CONFIG_ENABLE_BMP280` defaults to `y` but can be set to `n`)
- Fewer nets = simpler routing = faster DRC convergence
- Can add I2C on V2 board if needed
- LED is essential for field debugging

### GPIO18/GPIO19 Verification (USB Pins)

ESP32-C3 has GPIO0-GPIO10 as primary GPIOs. GPIO18 and GPIO19 are USB D- and D+ respectively. They CAN be used as regular GPIO if USB is not needed.

**For balloon flight:** USB is not used in flight → GPIO18/GPIO19 are available.

**Fallback plan if GPIO18/19 are unavailable on the specific C3 module:**

| Function | Primary | Fallback 1 | Fallback 2 |
|----------|---------|------------|------------|
| LED | GPIO18 (USB D-) | GPIO9 (drop I2C) | GPIO0 (drop GPS TX) |
| FEM_TX | GPIO19 (USB D+) | GPIO8 (drop ADC) | GPIO3 (share with RST via mux) |

**Worker action:** Before finalizing the netlist, verify the ESP32-C3 module pinout. If using an ESP32-C3 Mini module, check its datasheet for GPIO18/19 availability. If using a dev kit board with USB connected, GPIO18/19 are NOT available.

**For bare ESP32-C3 chip on custom PCB:** GPIO18/19 are available as regular GPIO.

---

## Net List Definition (Single-MCU, ~12 nets)

Derived from firmware Kconfig and app_main.cpp pin assignments:

| Net # | Net Name | Connected Pads | Track Width | Layer | Notes |
|-------|----------|---------------|-------------|-------|-------|
| 1 | 3V3 | C3:VCC, LR2021:1, GPS:VCC, LDO:OUT, LED_R:1 | 0.40mm | F.Cu | Power rail |
| 2 | GND | C3:GND, LR2021:2/8/10/11/16/18, GPS:GND, LDO:GND, C1:2, C2:2 | 0.40mm | B.Cu | Ground — explicit tracks, NO pour |
| 3 | SPI_SCK | C3:GPIO6, LR2021:5 | 0.25mm | F.Cu | SPI clock |
| 4 | SPI_MOSI | C3:GPIO7, LR2021:4 | 0.25mm | F.Cu | C3 → LR2021 |
| 5 | SPI_MISO | C3:GPIO2, LR2021:3 | 0.25mm | F.Cu | LR2021 → C3 |
| 6 | SPI_NSS | C3:GPIO10, LR2021:6 | 0.25mm | F.Cu | Chip select |
| 7 | LR2021_BUSY | C3:GPIO4, LR2021:7 | 0.25mm | F.Cu | IRQ/handshake |
| 8 | LR2021_RST | C3:GPIO3, LR2021:14 | 0.25mm | F.Cu | Active-low reset |
| 9 | LR2021_DIO9 | C3:GPIO5, LR2021:13 | 0.25mm | F.Cu | IRQ |
| 10 | GPS_RX | C3:GPIO1, GPS:TX | 0.25mm | F.Cu | UART NMEA input |
| 11 | STATUS_LED | C3:GPIO9, R_LED:1 | 0.25mm | F.Cu | Debug LED |
| 12 | LED_ANODE | R_LED:2, LED1:A | 0.25mm | F.Cu | LED current path |
| 13 | VCAP | LDO:IN, BAT54:C, C_CAP:+ | 0.40mm | F.Cu | Supercap rail |
| 14 | SOLAR_IN | BAT54:A, SOLAR:1 | 0.40mm | F.Cu | Solar input |
| 15 | VDIV_MID | C3:GPIO8, R_DIV1:2, R_DIV2:1 | 0.25mm | F.Cu | Voltage divider |
| 16 | RF_SUB_868 | LR2021:9, ANT1:1 | 0.25mm | F.Cu | Sub-GHz antenna trace (50Ω) |
| 17 | RF_2G4_2400 | LR2021:18, ANT2:1 | 0.25mm | F.Cu | 2.4GHz antenna trace (50Ω) |

**Total: ~17 nets.** If FEM is disabled (Kconfig `CONFIG_ENABLE_FEM=n`), drop FEM_TX net. If GPS TX is disabled (Kconfig `GPS_UART_TX_PIN=-1`), drop GPS_TX net.

### Component List

| Ref | Component | Footprint | Position (mm) | Notes |
|-----|-----------|-----------|---------------|-------|
| U1 | ESP32-C3 | Module-specific | (12, 12) | Bare chip or dev module |
| U2 | LR2021 | NiceRF castellated, 19.81×14.98mm | (25, 25) | 18 SMD pads |
| U3 | GPS (MAX-M10S) | 4-pad module | (6, 33) | UART only |
| U4 | TPS7A02 LDO | SOT-23-5 | (5, 22) | 3V3 regulator |
| D1 | BAT54 diode | SOD-123 | (4, 18) | Solar protection |
| LED1 | 0603 LED | 0603 | (16, 4) | Status indicator |
| R_LED | 330Ω 0402 | 0402 | (17.5, 4) | LED current limit |
| R_DIV1 | 100kΩ 0402 | 0402 | (3, 30) | Voltage divider top |
| R_DIV2 | 100kΩ 0402 | 0402 | (3, 32) | Voltage divider bottom |
| C_CAP | Supercapacitor | Radial THT | (8, 37) | Energy storage |
| SOLAR | Solar connector | 2-pin THT | (3, 37) | Solar panel input |
| ANT1 | U.FL / pad | Edge | (48, 25) | Sub-GHz antenna |
| ANT2 | U.FL / pad | Edge | (48, 30) | 2.4GHz antenna |
| C1 | 10µF 0603 | 0603 | (8, 22) | LDO input cap |
| C2 | 10µF 0603 | 0603 | (7, 24) | LDO output cap |

**Total: ~15 components, ~17 nets.** Board size: 50×40mm, 2-layer.

---

## PHASE BREAKDOWN

### System Constraints

- **Max 2 concurrent workers** (7GB RAM, 4 cores, 4GB swap)
- **FIPS Rust build uses 2-3GB** — do NOT run FIPS while PCB work is in progress
- **Monitor swap:** if swap > 5GB, kill all workers and run one at a time

### Worker Assignments

| Worker | Role | Phases |
|--------|------|--------|
| **worker-balloon** | PCB pipeline + board creation | Phase 1, 2, 3, 4, 5 |
| **worker-fips** | CI updates + SPI timing | Phase 6 (CI), Phase 7 (SPI timing) |
| **worker-admin** | Integration test scripts | Phase 8 |
| **Orchestrator** | JLCPCB order approval + quality gate sign-off | All gate reviews |

### Phase Dependency Graph

```
Phase 1 (Pipeline Code) ──┐
                          ├──▶ Phase 2 (Board Creation) ──▶ Phase 3 (Auto-Route) ──▶ Phase 4 (DRC Loop) ──▶ Phase 5 (Gerber Export + Order)
                          │                                        │                        │
                          │                                        ▼                        │
                          │                                 QUALITY GATE 3            QUALITY GATE 4
                          │
                          ▼
                    QUALITY GATE 1
Phase 6 (CI Updates) ── independent ──▶ QUALITY GATE 6
Phase 7 (SPI Timing) ── depends on Phase 5 completion (needs boards) ──▶ QUALITY GATE 7
Phase 8 (Integration Scripts) ── independent, can start immediately ──▶ QUALITY GATE 8
```

---

## Phase 1: Pipeline Code Implementation (worker-balloon, 2h)

### Objective

Create the `auto_router_pipeline.py` script that implements the A* + pcbnew + DRC loop. The full code is already written and verified in `docs/coordination/LLM-AUTO-ROUTING-PIPELINE.md` (lines 354-936). Copy it to the hardware directory.

### Task 1.1: Create the pipeline script

```bash
# Create the pipeline file from the verified code
# Source: docs/coordination/LLM-AUTO-ROUTING-PIPELINE.md lines 354-936
# Target: tracker/hardware/auto_router_pipeline.py

cd ~/repos/balloon-fresh/tracker/hardware

# The code is in the markdown file. Extract lines 354-936 (the python code block)
# and write to auto_router_pipeline.py
# The code starts with #!/usr/bin/python3.14 and ends with sys.exit(main())

# Verify the file was created:
/usr/bin/python3.14 -c "
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
print('pcbnew version:', pcbnew.GetBuildVersion())
print('PCB_TRACK:', hasattr(pcbnew, 'PCB_TRACK'))
print('FOOTPRINT:', hasattr(pcbnew, 'FOOTPRINT'))
print('PCB_VIA:', hasattr(pcbnew, 'PCB_VIA'))
print('NewBoard:', hasattr(pcbnew, 'NewBoard'))
print('SaveBoard:', hasattr(pcbnew, 'SaveBoard'))
"
```

### Task 1.2: Adapt for headless NewBoard (critical fix)

The pipeline code in the markdown uses `pcbnew.LoadBoard()` which **fails headless**. Must adapt to use `NewBoard()` instead. This means:

1. The script must create footprints programmatically (can't load existing board)
2. Must create a board from scratch with all components defined in Python
3. Must assign nets to pads explicitly

**Create a new file: `tracker/hardware/create_board.py`**

This script will:
1. Call `pcbnew.NewBoard()` to create an empty board
2. Define the board outline (50×40mm rectangle on Edge.Cuts)
3. Create each footprint programmatically using `pcbnew.FOOTPRINT(board)`
4. Add pads to each footprint using `pcbnew.PAD(fp)`
5. Create nets using `board.AddNet(netname, netcode)`
6. Assign nets to pads
7. Save with `pcbnew.SaveBoard()`

Key API calls (all verified):
```python
#!/usr/bin/python3.14
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

# Create empty board
board = pcbnew.NewBoard('/tmp/balloon_v2_single_mcu.kicad_pcb')

# Create a net
net = pcbnew.NETINFO_ITEM(board, "3V3", 1)
board.Add(net)

# Create a footprint
fp = pcbnew.FOOTPRINT(board)
fp.SetReference("U1")
fp.SetValue("ESP32-C3")
fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(12.0), pcbnew.FromMM(12.0)))

# Create a pad
pad = pcbnew.PAD(fp)
pad.SetNumber(1)
pad.SetPosition(pcbnew.VECTOR2I(0, 0))
pad.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.0), pcbnew.FromMM(1.0)))
pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
pad.SetNet(net)
fp.Add(pad)

board.Add(fp)
pcbnew.SaveBoard('/tmp/balloon_v2_single_mcu.kicad_pcb', board)
```

### Task 1.3: Create the board creation script with full component list

**File:** `tracker/hardware/create_board_v2.py`

This script creates the complete single-MCU board with all components and nets defined in the Net List section above. It must:

1. Create board outline (50×40mm)
2. Create all 17 nets
3. Create all 15 component footprints with correct pad positions
4. Assign nets to pads
5. Save the board

**Component placement coordinates** (from the table above):
```
U1 (ESP32-C3):     (12, 12)  — module-specific pad layout
U2 (LR2021):       (25, 25)  — 18 SMD pads, see Appendix B of UNIFIED-PCB-DESIGN-REVIEW.md
U3 (GPS MAX-M10S): (6, 33)   — 4 pads
U4 (TPS7A02 LDO):  (5, 22)   — SOT-23-5, 6 pads
D1 (BAT54):        (4, 18)   — SOD-123, 2 pads
LED1:              (16, 4)   — 0603, 2 pads
R_LED (330Ω):      (17.5, 4) — 0402, 2 pads
R_DIV1 (100kΩ):    (3, 30)   — 0402, 2 pads
R_DIV2 (100kΩ):    (3, 32)   — 0402, 2 pads
C_CAP:             (8, 37)   — radial THT, 2 pads
SOLAR:             (3, 37)   — 2-pin THT
ANT1 (U.FL):       (48, 25)  — edge mount
ANT2 (U.FL):       (48, 30)  — edge mount
C1 (10µF):         (8, 22)   — 0603, 2 pads
C2 (10µF):         (7, 24)   — 0603, 2 pads
```

**LR2021 pinout** (from UNIFIED-PCB-DESIGN-REVIEW.md Appendix B):
```
Pin  Side  Function
1    Left  3V3 (VDD)
2    Left  GND
3    Left  SPI MISO
4    Left  SPI MOSI
5    Left  SPI SCK
6    Left  SPI NSS (CS)
7    Left  BUSY
8    Left  GND
9    Left  RF_SUB_868
10   Right GND
11   Right GND
12   Right (NC)
13   Right DIO9 (IRQ)
14   Right RST (Reset)
15   Right (NC)
16   Right GND
17   Right GND
18   Right RF_2G4_2400
```

### Task 1.4: Smoke test the pipeline

```bash
cd ~/repos/balloon-fresh/tracker/hardware

# Create the board
/usr/bin/python3.14 create_board_v2.py

# Verify board was created
kicad-cli pcb drc --format json --output /tmp/smoke_drc.json /tmp/balloon_v2_single_mcu.kicad_pcb

# Parse DRC results
/usr/bin/python3.14 -c "
import json
with open('/tmp/smoke_drc.json') as f:
    drc = json.load(f)
print(f'Violations: {len(drc.get(\"violations\", []))}')
print(f'Unconnected: {len(drc.get(\"unconnected_items\", []))}')
"

# Run the auto-router
/usr/bin/python3.14 auto_router_pipeline.py \
    --board /tmp/balloon_v2_single_mcu.kicad_pcb \
    --output /tmp/balloon_v2_routed.kicad_pcb \
    --gerber-dir /tmp/gerbers_v2/ \
    --max-iterations 5
```

### Phase 1 Quality Gate

| Check | Criteria | Command |
|-------|----------|---------|
| Pipeline script exists | `auto_router_pipeline.py` in `tracker/hardware/` | `ls -la tracker/hardware/auto_router_pipeline.py` |
| Board creation script exists | `create_board_v2.py` in `tracker/hardware/` | `ls -la tracker/hardware/create_board_v2.py` |
| Board creation works | `/tmp/balloon_v2_single_mcu.kicad_pcb` exists | `ls -la /tmp/balloon_v2_single_mcu.kicad_pcb` |
| DRC runs on created board | JSON output parseable | `kicad-cli pcb drc --format json --output /tmp/test.json /tmp/balloon_v2_single_mcu.kicad_pcb` |
| Auto-router runs | Script exits 0 or 1 (not crash) | Check exit code |
| Track segments created | At least 10 track segments in output board | Parse with pcbnew or grep .kicad_pcb |

**Rollback:** If pipeline code fails, fall back to manual KiCad GUI routing (Phase 2 alternative path).

---

## Phase 2: Board Creation + Footprint Placement (worker-balloon, 1-2h)

### Objective

Create a clean `.kicad_pcb` file with all footprints placed and nets assigned, but NO routing (no tracks). The auto-router will handle routing in Phase 3.

### Two Paths — Choose ONE

#### Path A: Programmatic (via create_board_v2.py — recommended if Phase 1 succeeded)

If `create_board_v2.py` from Phase 1 successfully creates a board with footprints and nets, use that output directly.

```bash
# Verify the board has all expected components and nets
/usr/bin/python3.14 -c "
import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

# NewBoard creates a fresh board — we can't LoadBoard headless
# Instead, verify the SAVED file by reading it as text
with open('/tmp/balloon_v2_single_mcu.kicad_pcb') as f:
    content = f.read()
    print('Footprints found:', content.count('(footprint'))
    print('Nets found:', content.count('(net'))
    print('Pads found:', content.count('(pad'))
"
```

#### Path B: KiCad GUI (fallback if programmatic fails)

If the Python board creation is too complex (footprint creation for specific modules like ESP32-C3, LR2021 is intricate), use KiCad GUI:

1. Open KiCad: `kicad &` (needs display — use VNC or local screen)
2. New project: `balloon-tracker-v2-single-mcu`
3. Draw schematic with all components from the component list
4. Assign nets in schematic (use net labels matching the Net List table)
5. Open PCB layout editor
6. Import nets from schematic
7. Place footprints at the coordinates from the component table
8. Save .kicad_pcb (do NOT route — leave unrouted)
9. Close KiCad

**Worker note:** Path B requires display access. If running headless via SSH, use `DISPLAY=:0 kicad` or VNC.

### Task 2.1: Define the board outline

```python
# In create_board_v2.py, add board outline:
# 50×40mm rectangle on Edge.Cuts layer (layer 44)

# Board outline coordinates (mm):
# (0, 0) → (50, 0) → (50, 40) → (0, 40) → (0, 0)
```

### Task 2.2: Create footprints with accurate pad positions

The most critical footprints:

**ESP32-C3** — depends on module type:
- If using ESP32-C3 Mini module: 2×7 pin header, 1.27mm pitch, pads map to GPIO0-GPIO10 + VCC + GND
- If using bare ESP32-C3 chip: QFN32 package, specific pad layout
- **Recommendation:** Use a module (Mini or SuperMini) with castellated pads for easier PCB assembly

**LR2021** — NiceRF module, 18 SMD pads:
- Left side (x=15.095 relative to center): pins 1-9
- Right side (x=34.905 relative to center): pins 10-18
- Module size: 19.81×14.98mm
- Pad pitch: 2mm

### Task 2.3: Verify net assignment

```bash
# After board creation, verify all nets are correctly assigned
/usr/bin/python3.14 -c "
import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

# Read the board file as text (can't LoadBoard headless)
with open('/tmp/balloon_v2_single_mcu.kicad_pcb') as f:
    content = f.read()

# Check for expected net names
expected_nets = ['3V3', 'GND', 'SPI_SCK', 'SPI_MOSI', 'SPI_MISO', 'SPI_NSS',
                 'LR2021_BUSY', 'LR2021_RST', 'LR2021_DIO9', 'GPS_RX',
                 'STATUS_LED', 'LED_ANODE', 'VCAP', 'SOLAR_IN', 'VDIV_MID',
                 'RF_SUB_868', 'RF_2G4_2400']

for net in expected_nets:
    if net in content:
        print(f'  ✅ {net}')
    else:
        print(f'  ❌ {net} — MISSING')
"
```

### Phase 2 Quality Gate

| Check | Criteria |
|-------|----------|
| Board file exists | `/tmp/balloon_v2_single_mcu.kicad_pcb` or project file |
| Board outline | 50×40mm rectangle on Edge.Cuts |
| Component count | ≥15 footprints |
| Net count | ≥17 nets |
| No routing | 0 tracks (footprints only) |
| DRC parseable | `kicad-cli pcb drc` runs without error |

**Rollback:** If programmatic board creation fails, fall back to KiCad GUI (Path B). If GUI also unavailable, escalate to orchestrator — manual board creation by Felix may be required.

---

## Phase 3: A* Auto-Routing (worker-balloon, 1h)

### Objective

Run the A* pathfinding router on the unrouted board to generate collision-free track paths for all nets.

### Task 3.1: Run the auto-router

```bash
cd ~/repos/balloon-fresh/tracker/hardware

/usr/bin/python3.14 auto_router_pipeline.py \
    --board /tmp/balloon_v2_single_mcu.kicad_pcb \
    --output /tmp/balloon_v2_routed.kicad_pcb \
    --max-iterations 5
```

**NOTE:** The pipeline code uses `pcbnew.LoadBoard()` which fails headless. If this is the case, the pipeline must be modified to:
1. Create the board with `NewBoard()` inside the same script
2. Add footprints and nets
3. Run A* routing
4. Write tracks
5. Save with `SaveBoard()`

This means Phase 1 and Phase 3 may need to be combined into a single script that does everything in one pass.

### Task 3.2: Combined pipeline (if LoadBoard fails)

Create a single script: `tracker/hardware/full_pipeline.py` that:

```python
#!/usr/bin/python3.14
"""
Full pipeline: Create board → Place footprints → A* route → Save → DRC → Iterate
Run with: /usr/bin/python3.14 full_pipeline.py --output /tmp/balloon_v2_routed.kicad_pcb --max-iterations 5
"""

import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew
import json
import subprocess
import os
import math
import heapq
from collections import defaultdict
from typing import Optional
from dataclasses import dataclass, field

# ... (all code from auto_router_pipeline.py, but modified to use NewBoard)
# ... (all code from create_board_v2.py to create footprints)

# The main() function should:
# 1. board = pcbnew.NewBoard(output_path)
# 2. create_footprints_and_nets(board)  # from create_board_v2.py
# 3. nets = parse_board(board)  # from auto_router_pipeline.py
# 4. routing_order = default_routing_strategy(nets)
# 5. assign_layers(nets)
# 6. router = GridRouter(); router.block_all_pads(nets)
# 7. for net_code in routing_order: router.route_net(nets[net_code])
# 8. write_tracks_to_board(board, nets)
# 9. pcbnew.SaveBoard(output_path, board)
# 10. drc_result = run_drc(output_path)
# 11. If violations > 0: adjust strategy, re-route, repeat (max 5 iterations)
```

### Task 3.3: Verify routing output

```bash
# Check that tracks were created
/usr/bin/python3.14 -c "
import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

# Can't LoadBoard headless, so read as text
with open('/tmp/balloon_v2_routed.kicad_pcb') as f:
    content = f.read()
    print('Track segments:', content.count('(segment'))
    print('Vias:', content.count('(via'))
    print('Zones:', content.count('(zone'))
"
```

### Phase 3 Quality Gate

| Check | Criteria |
|-------|----------|
| Routed board file exists | `/tmp/balloon_v2_routed.kicad_pcb` |
| Track count > 0 | At least 15 track segments (one per net minimum) |
| No zones (copper pours) | 0 zone entries — explicit tracks only |
| All nets routed | Check each net has at least one track segment |

**Rollback:** If A* fails to route all nets, identify which nets failed. Manually route the failed nets in the .kicad_pcb file (edit S-expression text directly, or use KiCad GUI). Common failures: nets that need to cross the board diagonally — may need via to switch layers.

---

## Phase 4: DRC Iteration Loop (worker-balloon, 30 min - 2h)

### Objective

Run DRC, fix violations, repeat until 0 violations and 0 unconnected.

### Task 4.1: Run DRC

```bash
kicad-cli pcb drc --format json --output /tmp/drc_v2.json /tmp/balloon_v2_routed.kicad_pcb

# Parse results
/usr/bin/python3.14 -c "
import json
with open('/tmp/drc_v2.json') as f:
    drc = json.load(f)
violations = drc.get('violations', [])
unconnected = drc.get('unconnected_items', [])
print(f'Violations: {len(violations)}')
print(f'Unconnected: {len(unconnected)}')
print()
print('Violation types:')
for v in violations:
    print(f'  {v.get(\"type\", \"unknown\")}: {v.get(\"description\", \"\")[:80]}')
"
```

### Task 4.2: DRC Iteration Loop Specification

```
REPEAT (max 10 iterations):
  1. Run kicad-cli pcb drc --format json --output /tmp/drc_iter_N.json <board>
  2. Parse JSON: count violations + unconnected
  3. IF violations == 0 AND unconnected == 0: BREAK (success!)
  4. Categorize violations:
     - SHORT: two nets touching (critical)
     - CLEARANCE: nets too close (adjust grid clearance)
     - UNCONNECTED: net not fully routed (re-route that net)
  5. For SHORT violations:
     - Identify the two nets
     - Increase clearance between them (move to different layer or increase grid clearance)
  6. For CLEARANCE violations:
     - Increase A* grid clearance_mm from 0.30 to 0.35
     - Re-route affected nets
  7. For UNCONNECTED:
     - Re-run A* on that specific net with alternate layer
  8. Modify the board (re-run create + route pipeline with adjusted parameters)
  9. Save and go to step 1
```

### Task 4.3: Common DRC Fixes

| DRC Violation | Fix |
|---------------|-----|
| Short: 3V3 ↔ GND | Check for overlapping tracks on same layer. Move GND to B.Cu, 3V3 to F.Cu |
| Short: SPI_SCK ↔ SPI_MOSI | A* clearance too small. Increase `CLEARANCE_MM` from 0.30 to 0.35 |
| Unconnected: net X | A* couldn't find path. Try alternate layer, or move component |
| Clearance: track near pad | Increase `clearance_cells` in GridRouter |
| DRC error: "pad has no net" | Footprint pad missing net assignment in create_board_v2.py |

### Task 4.4: Final DRC verification

```bash
# Final DRC check — must be 0/0
kicad-cli pcb drc --format json --output /tmp/drc_final.json /tmp/balloon_v2_routed.kicad_pcb

/usr/bin/python3.14 -c "
import json
with open('/tmp/drc_final.json') as f:
    drc = json.load(f)
v = len(drc.get('violations', []))
u = len(drc.get('unconnected_items', []))
print(f'Final DRC: {v} violations, {u} unconnected')
if v == 0 and u == 0:
    print('✅ BOARD IS READY FOR FABRICATION')
else:
    print('❌ BOARD IS NOT READY — fix remaining issues')
"
```

### Phase 4 Quality Gate (CRITICAL — must pass before gerber export)

| Check | Criteria | Gate Type |
|-------|----------|-----------|
| DRC violations | **0** | HARD GATE — no exceptions |
| Unconnected items | **0** | HARD GATE — no exceptions |
| No copper pours | 0 zones in board file | HARD GATE |
| All 17 nets routed | Each net has ≥1 track segment | HARD GATE |
| Board outline correct | 50×40mm on Edge.Cuts | SOFT GATE |
| No short circuits | 0 shorting_items in DRC | HARD GATE |

**Rollback:** If DRC doesn't converge after 10 iterations:
1. Try increasing grid resolution from 0.1mm to 0.05mm (finer A* grid)
2. Try 4-layer board (add GND and PWR planes) — costs more but routes easier
3. Manually route stubborn nets in KiCad GUI
4. Simplify the design: drop GPS or ADC to reduce net count
5. **Escalate to orchestrator** — may need Felix to manually route in KiCad

**CRITICAL:** Do NOT export gerbers or order boards that fail DRC. The V1 disaster was caused by ordering a board with 437 violations.

---

## Phase 5: Gerber Export + JLCPCB Order (worker-balloon + orchestrator, 30 min)

### Objective

Export fabrication files and prepare JLCPCB order. Orchestrator must approve before order is placed.

### Task 5.1: Export gerbers

```bash
mkdir -p ~/repos/balloon-fresh/tracker/hardware/gerbers_v2

# Export gerbers (all layers for JLCPCB)
kicad-cli pcb export gerbers \
    --output ~/repos/balloon-fresh/tracker/hardware/gerbers_v2/ \
    --layers F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts,F.Paste,B.Paste,F.Fab,B.Fab \
    /tmp/balloon_v2_routed.kicad_pcb

# Export drill files (Excellon format)
kicad-cli pcb export drill \
    --output ~/repos/balloon-fresh/tracker/hardware/gerbers_v2/ \
    --format excellon \
    /tmp/balloon_v2_routed.kicad_pcb

# List exported files
ls -la ~/repos/balloon-fresh/tracker/hardware/gerbers_v2/
```

Expected output files (~13 files):
```
*.gbr       (11 files — one per layer)
*.drl       (1 file — Excellon drill)
*.gbrjob    (1 file — gerber job file)
```

### Task 5.2: Zip for JLCPCB

```bash
cd ~/repos/balloon-fresh/tracker/hardware/gerbers_v2/
zip ../gerbers_v2_jlcpcb.zip *
ls -la ../gerbers_v2_jlcpcb.zip
```

### Task 5.3: Delete old gerbers (prevent accidental ordering of V1)

```bash
# CRITICAL: Delete V1 gerbers to prevent accidental ordering
rm -rf ~/repos/balloon-fresh/tracker/hardware/gerbers_v1/
rm -rf ~/repos/balloon-fresh/tracker/hardware/gerbers_v1_fixed/

# Verify deletion
ls ~/repos/balloon-fresh/tracker/hardware/gerbers_v1* 2>&1
# Should show: No such file or directory
```

### Task 5.4: JLCPCB Order Checklist

**Orchestrator approval required before placing order.**

| Item | Value | Notes |
|------|-------|-------|
| Board size | 50 × 40 mm | 2-layer |
| Quantity | 5 (minimum) | Or 10 if cost difference is small |
| Thickness | 1.6mm | Standard |
| Copper weight | 1oz | Standard |
| Surface finish | HASL (lead-free) | Cheapest, fine for prototype |
| Solder mask | Green (both sides) | Standard |
| Silkscreen | White (both sides) | Standard |
| Edge connector | No | |
| Edge beveling | No | |
| Castellated holes | YES — LR2021 module needs castellated pads | Check if JLCPCB supports |
| Shipping | Express (5-day) | Standard 2-week is too slow if we're already behind |
| BOM | Not needed (bare PCB) | We hand-solder |
| PCBA | No | Hand assembly |

### Task 5.5: Upload and order

1. Go to jlcpcb.com
2. Upload `gerbers_v2_jlcpcb.zip`
3. Verify preview matches 50×40mm board
4. Select options from the table above
5. Add to cart, checkout
6. Save order confirmation number

### Phase 5 Quality Gate

| Check | Criteria |
|-------|----------|
| Gerber files exist | ≥11 .gbr files + 1 .drl + 1 .gbrjob |
| ZIP file created | `gerbers_v2_jlcpcb.zip` exists |
| Old gerbers deleted | `gerbers_v1/` and `gerbers_v1_fixed/` gone |
| JLCPCB order placed | Confirmation number saved |
| Board preview verified | 50×40mm, correct layout |

**Rollback:** If JLCPCB rejects gerbers (format issue), try:
1. Re-export with `--usegerberextensions` flag
2. Use different layer set
3. Check if KiCad 9.0 gerber format is compatible with JLCPCB's current requirements

---

## Phase 6: CI Updates (worker-fips, 30 min — can run concurrently with Phase 1-5)

### Objective

Add relay pipeline and nostr_dump tests to GitHub Actions CI.

### Task 6.1: Add relay pipeline test suite

```bash
# File: ~/repos/balloon-fresh/.github/workflows/ci-host-tests.yml
# Add Suite 5: relay pipeline test (12 tests)

# The test compiles with:
gcc -Wall -O2 -I tracker/firmware/main -I tracker/firmware/components/nostr_store/include \
    -o /tmp/test_relay tracker/firmware/main/test/test_relay_pipeline.c \
    tracker/firmware/main/tollgate_payment_proto.c \
    tracker/firmware/components/nostr_store/nostr_store.c

# Add to ci-host-tests.yml as a new step
```

### Task 6.2: Add nostr_dump test suite

```bash
# Add Suite 6: nostr_dump test
# Find the test file:
find ~/repos/balloon-fresh/tracker/firmware -name "*nostr_dump*test*" -o -name "*test*nostr_dump*"
```

### Phase 6 Quality Gate

| Check | Criteria |
|-------|----------|
| CI workflow updated | `ci-host-tests.yml` has Suites 5+6 |
| CI passes | GitHub Actions run succeeds |
| All tests pass | 12 relay + 6 nostr_dump = 18 new tests |

**Rollback:** Revert the CI workflow change if it breaks existing tests.

---

## Phase 7: SPI Timing Characterization (worker-fips — during 2-week JLCPCB wait)

### Objective

Verify ESP32-C3 can drive LR2021 SPI at ≥8MHz before boards arrive.

### Task 7.1: Wire LR2021 to S3 test board

The S3 test board has SPI-accessible GPIOs. Wire:
- S3 GPIO → LR2021 SCK
- S3 GPIO → LR2021 MOSI
- S3 GPIO → LR2021 MISO
- S3 GPIO → LR2021 NSS
- S3 GPIO → LR2021 BUSY
- S3 GPIO → LR2021 RST
- S3 GPIO → LR2021 DIO9

**Use the same GPIO numbers as the C3 firmware** (6, 7, 2, 10, 4, 3, 5) if possible on the S3. If not, adjust in the test config.

### Task 7.2: Flash tracker firmware on S3

```bash
cd ~/repos/balloon-fresh/tracker/firmware

# Set target to S3
idf.py set-target esp32s3

# Configure for single-MCU, relay mode
# Edit sdkconfig: CONFIG_ENABLE_RELAY_MODE=y, CONFIG_ENABLE_MESH=y

# Build and flash
BALLOON_TRACK=balloon-hermes python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire board-a \
    --purpose "SPI timing test" --timeout 120
idf.py -p /dev/ttyACM0 flash monitor

# On serial console:
# radio_test 1 "hello"
# Check SPI clock frequency in logs
```

### Task 7.3: Test at different SPI frequencies

```bash
# The firmware SPI clock is configurable. Test at:
# 8MHz (target), 4MHz (fallback), 2MHz (minimum)

# Modify SPI frequency in firmware:
# Look for SPI clock setting in lr2021_transport or radio_task.cpp
# Try 8MHz first, verify radio_test works

# If 8MHz fails, try 4MHz
# If 4MHz fails, try 2MHz

# Record results
```

### Task 7.4: Release board lock

```bash
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release board-a
```

### Task 7.5: Log results

```
SPI Frequency | TX Success | RX Success | Data Rate | Notes
8MHz          | ?          | ?          | ?         |
4MHz          | ?          | ?          | ?         |
2MHz          | ?          | ?          | ?         |
```

If <8MHz works, adjust firmware SPI clock before V2 boards arrive.

### Phase 7 Quality Gate

| Check | Criteria |
|-------|----------|
| SPI test completed | Results logged for 8/4/2 MHz |
| Minimum viable frequency identified | ≤8MHz with reliable TX/RX |
| Firmware updated if needed | SPI clock set to verified frequency |
| Board lock released | `balloon-board-lock.py check board-a` returns exit 1 |

**Rollback:** If C3 SPI timing is insufficient (<2MHz), escalate to orchestrator. May need to reconsider dual-MCU architecture (but this is a last resort — the firmware is single-MCU).

---

## Phase 8: Integration Test Scripts (worker-admin — during 2-week JLCPCB wait)

### Objective

Write test scripts for Phases 5-7 of the integration plan so they're ready when boards arrive.

### Task 8.1: Write Phase 5 test script (raw ping)

**File:** `~/repos/balloon-fresh/tracker/tests/test_raw_ping.sh`

```bash
#!/bin/bash
# Raw ping test: Board A TX, Board B RX
# Prerequisites: 2 boards with LR2021 modules, board locks acquired

set -e

echo "=== Raw Ping Test ==="

# Flash board A (TX)
BALLOON_TRACK=balloon-hermes python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire board-a \
    --purpose "raw ping TX" --timeout 120
idf.py -p /dev/ttyACM0 flash
# Send: radio_test 1 "hello"

# Flash board B (RX)
BALLOON_TRACK=balloon-hermes python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire board-b \
    --purpose "raw ping RX" --timeout 120
idf.py -p /dev/ttyACM1 flash monitor
# Run: radio_recv 30

# Verify: Board B receives "hello" within 30s
# Swap roles, verify bidirectional

# Release locks
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release board-a
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release board-b
```

### Task 8.2: Write Phase 6 test script (nostr round-trip)

**File:** `~/repos/balloon-fresh/tracker/tests/test_nostr_roundtrip.sh`

Tests: Board A sends Nostr event → Board B receives and stores → verify with `nostr_dump` CLI.

### Task 8.3: Write Phase 7 test script (tollgate PAY→ACK)

**File:** `~/repos/balloon-fresh/tracker/tests/test_tollgate_roundtrip.sh`

Tests: Board A sends PAY → Board B decodes and ACKs → Board A receives ACK → verify seq + amount.

### Phase 8 Quality Gate

| Check | Criteria |
|-------|----------|
| 3 test scripts exist | `test_raw_ping.sh`, `test_nostr_roundtrip.sh`, `test_tollgate_roundtrip.sh` |
| Scripts are executable | `chmod +x` applied |
| Scripts use board lock | All scripts call `balloon-board-lock.py` |
| Scripts release locks | All scripts release locks on exit (trap) |

**Rollback:** Scripts can be modified when boards arrive — they're templates, not final.

---

## DRC ITERATION LOOP DETAILED SPECIFICATION

### Loop Structure

```
INPUT: unrouted_board.kicad_pcb (footprints placed, nets assigned, 0 tracks)
OUTPUT: routed_board.kicad_pcb (0 DRC violations, 0 unconnected)

max_iterations = 10
grid_resolution = 0.1mm (500×400 cells for 50×40mm board)
clearance = 0.30mm (increase to 0.35mm if clearance violations persist)

FOR iteration = 1 TO max_iterations:
    1. CREATE/LOAD board
       - Iteration 1: NewBoard() + create footprints + assign nets
       - Iteration 2+: Reload from saved board, ripup tracks, re-route

    2. A* ROUTE all nets
       - Order: GND → 3V3 → short signals → long signals → RF traces
       - Layer: power on B.Cu, signals on F.Cu
       - Width: power=0.40mm, signal=0.25mm, RF=0.25mm (50Ω approx)
       - For each net:
         a. Unblock this net's pads on the grid
         b. A* pathfind between all pad pairs (nearest-neighbor ordering)
         c. If blocked, try alternate layer (insert via)
         d. Block routed cells with clearance

    3. WRITE tracks to board
       - For each net, for each segment: board.Add(PCB_TRACK)
       - DO NOT add any zones/copper pours

    4. SAVE board with SaveBoard()

    5. RUN DRC: kicad-cli pcb drc --format json --output /tmp/drc.json <board>

    6. PARSE DRC JSON
       - violations = drc["violations"]
       - unconnected = drc["unconnected_items"]

    7. CHECK convergence
       - IF len(violations) == 0 AND len(unconnected) == 0: BREAK (SUCCESS)

    8. ANALYZE failures
       - short_violations = [v for v if "short" in v.type]
       - clearance_violations = [v for v if "clearance" in v.type]
       - For each violation: extract net name from item descriptions

    9. ADJUST strategy
       - For shorts: swap conflicting nets to different layers
       - For clearance: increase clearance_mm by 0.05mm
       - For unconnected: try alternate layer for that net

    10. REPEAT

IF NOT converged after max_iterations:
    REPORT: X violations, Y unconnected remain
    ESCALATE: manual routing needed for failed nets
```

### DRC JSON Parsing Reference

```python
import json

with open('/tmp/drc.json') as f:
    drc = json.load(f)

# Structure:
# {
#   "violations": [
#     {
#       "type": "shorting_items",
#       "description": "...",
#       "severity": "error",
#       "items": [
#         {"description": "Track [3V3] on B.Cu at ...", "pos": [x, y], "uuid": "..."},
#         {"description": "Pad [GND] of U1 at ...", "pos": [x, y], "uuid": "..."}
#       ]
#     },
#     ...
#   ],
#   "unconnected_items": [
#     {
#       "type": "unconnected_items",
#       "description": "...",
#       "items": [...]
#     },
#     ...
#   ]
# }

violations = drc.get('violations', [])
unconnected = drc.get('unconnected_items', [])

# Extract net names from descriptions
for v in violations:
    for item in v.get('items', []):
        desc = item.get('description', '')
        # Net name in brackets: "Track [3V3] on B.Cu"
        if '[' in desc and ']' in desc:
            net_name = desc[desc.index('[')+1:desc.index(']')]
```

---

## FOOTPRINT/COMPONENT PLACEMENT STRATEGY

### Placement Principles

1. **LR2021 in center** — it's the largest component and the SPI hub. Place at (25, 25)
2. **ESP32-C3 on left** — close to LR2021 left pins for short SPI traces. Place at (12, 12)
3. **GPS on bottom-left** — UART connection, relatively slow, can be farther. Place at (6, 33)
4. **Power circuitry on left edge** — LDO, diode, supercap, solar input. Place at (3-8, 18-37)
5. **LED on top edge** — visible, away from RF. Place at (16, 4)
6. **Antenna pads on right edge** — short RF traces from LR2021 right pins. Place at (48, 25/30)
7. **Decoupling caps near their loads** — C1 near LDO input, C2 near LDO output

### Routing Priority Order (for A*)

```
1. GND (most pads, widest tracks, B.Cu) — route first as it has the most endpoints
2. 3V3 (power, F.Cu) — route second, needs to reach all power pads
3. SPI_SCK (critical signal, F.Cu) — short route C3→LR2021 left side
4. SPI_MOSI (critical signal, F.Cu)
5. SPI_MISO (critical signal, F.Cu)
6. SPI_NSS (critical signal, F.Cu)
7. LR2021_BUSY (control, F.Cu)
8. LR2021_RST (control, F.Cu)
9. LR2021_DIO9 (control, F.Cu)
10. GPS_RX (UART, F.Cu) — long route from C3 to GPS module
11. STATUS_LED (F.Cu) — short route to LED
12. LED_ANODE (F.Cu) — very short, LED to resistor
13. VDIV_MID (F.Cu) — short route to voltage divider
14. VCAP (power, F.Cu) — supercap to LDO
15. SOLAR_IN (power, F.Cu) — solar connector to diode
16. RF_SUB_868 (RF, F.Cu) — LR2021 to antenna pad, keep short and direct
17. RF_2G4_2400 (RF, F.Cu) — same as above
```

### Layer Strategy

| Layer | Nets | Rationale |
|-------|------|-----------|
| F.Cu (top) | 3V3, all signals, RF traces | Signals on top for easy inspection |
| B.Cu (bottom) | GND only | Ground as explicit tracks, star topology |

**DO NOT add copper pours on either layer.** The V1 board had 18× 3V3↔GND shorts from a ground pour.

---

## WHAT HAPPENS DURING THE 2-WEEK JLCPCB WAIT

### Timeline

| Day | Activity | Worker | Duration |
|-----|----------|--------|----------|
| 1-2 | SPI timing characterization on S3 test board | worker-fips | 4h |
| 1-2 | CI updates (relay pipeline + nostr_dump tests) | worker-fips | 30 min |
| 3-5 | Integration test scripts (Phases 5-7) | worker-admin | 3h |
| 3-5 | Firmware SPI clock adjustment (if needed from timing test) | worker-balloon | 2h |
| 5-7 | Test scripts dry-run on S3 boards (no LR2021, just protocol) | worker-admin | 4h |
| 7-10 | Documentation: assembly guide, BOM, test procedures | worker-balloon | 4h |
| 10-14 | Buffer / contingency | All | — |
| 14 | Boards arrive | — | — |

### SPI Timing Characterization Details

The consultant PCB review recommended validating C3 SPI timing. We use the S3 test board as a proxy:

1. Wire LR2021 to S3 board using same GPIO pins as C3 firmware (6/7/2/10/4/3/5)
2. Flash tracker firmware on S3 with `CONFIG_ENABLE_RELAY_MODE=y`
3. Run `radio_test 1 "hello"` and verify TX
4. Run `radio_recv 30` and verify RX
5. Test SPI clock at 8MHz, 4MHz, 2MHz
6. If <8MHz is the max stable frequency, update firmware SPI clock before V2 boards arrive
7. Log results and update this plan

### Integration Test Scripts Details

Write shell scripts that will be run when boards arrive:

1. **`test_raw_ping.sh`** — Flash 2 boards, one TX one RX, verify raw bytes round-trip
2. **`test_nostr_roundtrip.sh`** — Flash 2 boards, send Nostr event, verify store on RX
3. **`test_tollgate_roundtrip.sh`** — Flash 2 boards, send PAY, verify ACK round-trip

All scripts must:
- Use `balloon-board-lock.py` for board access
- Use `BoardSerial` wrapper (not raw `serial.Serial()`)
- Release locks on exit (trap EXIT)
- Have clear pass/fail criteria
- Log results to a file

---

## ROLLBACK PLANS SUMMARY

| Phase | Failure | Rollback Action |
|-------|---------|-----------------|
| 1 (Pipeline code) | Python script crashes | Fall back to KiCad GUI manual routing |
| 2 (Board creation) | Can't create footprints programmatically | Use KiCad GUI for schematic + placement |
| 3 (Auto-route) | A* can't route all nets | Manually route failed nets in .kicad_pcb text or GUI |
| 4 (DRC loop) | Doesn't converge in 10 iterations | Increase grid resolution, try 4-layer, or manual route |
| 5 (Gerber export) | JLCPCB rejects format | Re-export with different settings, try different fab |
| 5 (Order) | Wrong board ordered | Cancel order within 24h, JLCPCB allows cancellation |
| 6 (CI) | Tests fail in CI | Revert CI change, tests pass locally |
| 7 (SPI timing) | C3 can't do 8MHz | Lower SPI clock to 4MHz or 2MHz in firmware |
| 7 (SPI timing) | C3 can't do 2MHz | Escalate — may need dual-MCU (last resort) |
| 8 (Test scripts) | Scripts wrong | Modify when boards arrive — templates only |

### Nuclear Rollback (if entire pipeline fails)

1. Delete all auto-generated PCB files
2. Use KiCad GUI to manually design the board (schematic → layout → route → DRC)
3. This takes 4-6 hours but is guaranteed to work
4. Order from JLCPCB
5. The firmware is unaffected — it's already correct for single-MCU

---

## APPENDIX A: File Paths Reference

### Source Files (read-only reference)

```
~/repos/balloon-fresh/docs/coordination/LLM-AUTO-ROUTING-PIPELINE.md   # Full pipeline code (lines 354-936)
~/repos/balloon-fresh/docs/coordination/AUTO-ROUTING-FEASIBILITY.md     # API verification results
~/repos/balloon-fresh/docs/coordination/CONSULTANT-PLAN-REVIEW-V6.md    # Architecture decision
~/repos/balloon-fresh/docs/coordination/UNIFIED-PCB-DESIGN-REVIEW.md    # Two boards recommendation + LR2021 pinout
~/repos/balloon-fresh/docs/coordination/INTEGRATION-PLAN-V3.md         # Current integration plan
~/repos/balloon-fresh/tracker/firmware/main/Kconfig.projbuild           # Firmware Kconfig (pin assignments)
~/repos/balloon-fresh/tracker/firmware/main/app_main.cpp               # GPIO pin definitions (lines 85-94)
~/repos/balloon-fresh/tracker/firmware/main/radio_task.cpp             # DIO9 pin (line 34)
~/repos/balloon-fresh/tracker/hardware/gen_pcb.py                      # Old V1 generator (DO NOT USE — broken)
~/repos/balloon-fresh/tracker/hardware/router.py                       # Old V1 router (DO NOT USE — incomplete)
```

### Output Files (to be created)

```
~/repos/balloon-fresh/tracker/hardware/auto_router_pipeline.py         # A* + DRC pipeline script
~/repos/balloon-fresh/tracker/hardware/create_board_v2.py              # Board creation script
~/repos/balloon-fresh/tracker/hardware/full_pipeline.py                # Combined create + route + DRC
~/repos/balloon-fresh/tracker/hardware/gerbers_v2/                     # Gerber output directory
~/repos/balloon-fresh/tracker/hardware/gerbers_v2_jlcpcb.zip           # JLCPCB upload zip
~/repos/balloon-fresh/tracker/tests/test_raw_ping.sh                    # Integration test: raw ping
~/repos/balloon-fresh/tracker/tests/test_nostr_roundtrip.sh            # Integration test: nostr
~/repos/balloon-fresh/tracker/tests/test_tollgate_roundtrip.sh         # Integration test: tollgate
```

### Temporary Files (working directory)

```
/tmp/balloon_v2_single_mcu.kicad_pcb     # Unrouted board (pre-routing)
/tmp/balloon_v2_routed.kicad_pcb          # Routed board (post-routing)
/tmp/drc_v2.json                          # DRC results (iterative)
/tmp/drc_final.json                       # Final DRC check
/tmp/gerbers_v2/                          # Temporary gerber output
```

---

## APPENDIX B: Key Python API Calls (verified on this system)

```python
#!/usr/bin/python3.14
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

# Board creation
board = pcbnew.NewBoard('/tmp/test.kicad_pcb')

# Net creation
net = pcbnew.NETINFO_ITEM(board, "3V3", 1)
board.Add(net)

# Footprint creation
fp = pcbnew.FOOTPRINT(board)
fp.SetReference("U1")
fp.SetValue("ESP32-C3")
fp.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(12.0), pcbnew.FromMM(12.0)))

# Pad creation
pad = pcbnew.PAD(fp)
pad.SetNumber(1)
pad.SetPosition(pcbnew.VECTOR2I(0, 0))
pad.SetSize(pcbnew.VECTOR2I(pcbnew.FromMM(1.0), pcbnew.FromMM(1.0)))
pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
pad.SetNet(net)
fp.Add(pad)
board.Add(fp)

# Track creation
track = pcbnew.PCB_TRACK(board)
track.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(10.0), pcbnew.FromMM(10.0)))
track.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(30.0), pcbnew.FromMM(10.0)))
track.SetWidth(pcbnew.FromMM(0.25))
track.SetLayer(pcbnew.F_Cu)  # F_Cu = 0
track.SetNet(net)
board.Add(track)

# Via creation
via = pcbnew.PCB_VIA(board)
via.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(30.0), pcbnew.FromMM(10.0)))
via.SetDrill(pcbnew.FromMM(0.3))
via.SetWidth(pcbnew.FromMM(0.6))
via.SetNet(net)
via.SetViaType(pcbnew.VIATYPE_THROUGH)
board.Add(via)

# Save board
pcbnew.SaveBoard('/tmp/test.kicad_pcb', board)

# Save = done. Now run DRC via kicad-cli (subprocess):
# kicad-cli pcb drc --format json --output /tmp/drc.json /tmp/test.kicad_pcb
```

---

## APPENDIX C: DRC Command Reference

```bash
# Run DRC (headless)
kicad-cli pcb drc --format json --output /tmp/drc.json /path/to/board.kicad_pcb

# Run DRC with severity filter (errors only)
kicad-cli pcb drc --format json --output /tmp/drc.json --severity-error /path/to/board.kicad_pcb

# Export gerbers
kicad-cli pcb export gerbers \
    --output /path/to/gerbers/ \
    --layers F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts,F.Paste,B.Paste,F.Fab,B.Fab \
    /path/to/board.kicad_pcb

# Export drill files
kicad-cli pcb export drill \
    --output /path/to/gerbers/ \
    --format excellon \
    /path/to/board.kicad_pcb
```

---

## APPENDIX D: ESP32-C3 GPIO Reference

### ESP32-C3 Available GPIOs

| GPIO | Function | Available for PCB? | Notes |
|------|----------|-------------------|-------|
| GPIO0 | Boot strapping | YES (with care) | Must be HIGH at boot. Can be GPS TX |
| GPIO1 | General purpose | YES | GPS RX in firmware |
| GPIO2 | Boot strapping | YES (with care) | Must be LOW at boot. SPI MISO in firmware |
| GPIO3 | General purpose | YES | LR2021 RST in firmware |
| GPIO4 | General purpose | YES | LR2021 BUSY in firmware |
| GPIO5 | General purpose | YES | LR2021 DIO9 in firmware |
| GPIO6 | General purpose | YES | SPI SCK in firmware |
| GPIO7 | General purpose | YES | SPI MOSI in firmware |
| GPIO8 | General purpose | YES | ADC voltage divider in firmware |
| GPIO9 | General purpose | YES | LED / I2C SDA (conflict) |
| GPIO10 | General purpose | YES | SPI NSS in firmware |
| GPIO18 | USB D- | **VERIFY** | LED in firmware. Available if USB not used |
| GPIO19 | USB D+ | **VERIFY** | FEM_TX in firmware. Available if USB not used |

### Boot Strapping Pins (IMPORTANT)

GPIO2 MUST be LOW at boot. It's used as SPI MISO (input from LR2021). At boot, the LR2021 MISO line should be LOW (idle). If the LR2021 has a pull-up on MISO, the C3 may not boot. **Add a 10kΩ pull-down on GPIO2 if needed.**

GPIO0 MUST be HIGH at boot for normal boot mode. It's used as GPS TX (output to GPS module). At boot, the C3 drives it — should be fine if configured as output HIGH or left floating with pull-up.

---

## APPENDIX E: Critical Reminders for Workers

1. **USE `/usr/bin/python3.14`** — NEVER `python3` (3.11 segfaults with pcbnew)
2. **USE `NewBoard()`** — NEVER `LoadBoard()` (fails headless without wxApp)
3. **NO COPPER POURS** — This caused 18× 3V3↔GND shorts on V1. Route GND as explicit tracks.
4. **DRC MUST BE 0/0** — Do NOT export gerbers or order boards with any DRC violations
5. **DELETE OLD GERBERS** — `gerbers_v1/` and `gerbers_v1_fixed/` must be deleted to prevent accidental V1 ordering
6. **SINGLE-MCU ONLY** — No RP2040. No dual-MCU. No unified board. The firmware is single-MCU.
7. **MAX 2 WORKERS** — System has 7GB RAM, 4GB swap. FIPS build uses 2-3GB. Don't run FIPS during PCB work.
8. **BOARD LOCK FOR HARDWARE** — Use `balloon-board-lock.py` for any board access. Always release.
9. **COMMIT AND PUSH** — Uncommitted work is invisible to the orchestrator. Commit after each phase.
10. **ESCALATE BLOCKERS** — If stuck for >30 min on any task, escalate to orchestrator. Don't silently spin.

---

*End of execution plan. This document is self-contained — workers need no additional context to execute.*