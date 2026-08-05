# PCB Auto-Routing Pipeline + Dual Board Design — Worker Execution Plan V2

**Date:** 2026-08-05
**Author:** Senior Project Planner (automated)
**Status:** READY FOR KANBAN SCHEDULING
**Critical Path:** YES — JLCPCB 2-week lead time starts when gerbers are uploaded
**Supersedes:** PCB-AUTO-ROUTE-EXECUTION-PLAN.md (V1 plan, 1,358 lines)
**Revision driver:** Consultant review (5 blockers, 11 major issues) + Felix's dual-board decision

---

## ⚠️ READ THIS FIRST — Worker Context

You are a worker agent picking up this plan from a kanban board. You do NOT have the original conversation's context. This document is your complete briefing. Read it fully before starting any phase.

### Felix's Design Decision (AUTHORITATIVE — do not question)

Felix has decided to build **TWO board variants** in the same JLCPCB order:

1. **Board V1-FAST**: Uses the current pinmap as-is. **NO supercap voltage monitoring** — ADC (GPIO8) is disabled in firmware. Ship fast, test basic functionality.
2. **Board V2-ADC**: Redesigned pinmap that frees a GPIO pin for ADC supercap voltage monitoring. Same form factor, same components except additional voltage divider.
3. **Both boards ordered in the same JLCPCB batch** so Felix can test both without waiting for a second order cycle.

This means the pipeline must produce **two sets of gerbers**: one for V1-FAST, one for V2-ADC. The pipeline code is shared; only the board creation script differs (different net lists, different component counts).

### Verified Environment Facts (do not re-verify)

| Item | Status | Details |
|------|--------|---------|
| KiCad version | 9.0.8 | `kicad-cli` at `/usr/bin/kicad-cli` |
| python3.14 + pcbnew | ✅ WORKS | **MUST use `/usr/bin/python3.14`** — NOT `python3` (3.11 segfaults) |
| `pcbnew.NewBoard()` | ✅ WORKS | Creates empty `.kicad_pcb` headless |
| `pcbnew.LoadBoard()` | ❌ NEVER USE | **Fails headless.** ALL code in this plan uses `NewBoard()` exclusively. |
| `pcbnew.SaveBoard()` | ✅ WORKS | Saves board to disk headless |
| `pcbnew.PCB_TRACK` | ✅ WORKS | `SetStart/SetEnd/SetWidth/SetLayer/SetNet` all functional |
| `pcbnew.FOOTPRINT` | ✅ WORKS | Can create footprints programmatically |
| `kicad-cli pcb drc --format json` | ✅ WORKS | Outputs parseable JSON with violations + unconnected |
| `kicad-cli pcb export gerbers` | ✅ WORKS | All layers, headless |
| `kicad-cli pcb export drill` | ✅ WORKS | Excellon format for JLCPCB |
| KiCad coordinate unit | nanometers | `pcbnew.FromMM(1.0) = 1000000` (1M nm = 1mm) |
| F_Cu layer constant | 0 | `pcbnew.F_Cu = 0` |
| B_Cu layer constant | 2 | `pcbnew.B_Cu = 2` |

### CRITICAL: LoadBoard() is BANNED

**`pcbnew.LoadBoard()` FAILS HEADLESS.** It requires a wxApp instance which doesn't exist in a headless SSH session. Every script in this plan MUST use `pcbnew.NewBoard()` to create boards and `pcbnew.SaveBoard()` to persist them. If you find yourself writing `LoadBoard()`, STOP — you are introducing a guaranteed failure. The pipeline must create the board, place footprints, route tracks, and save — all in a single script execution pass.

### CRITICAL: Quality Gates Go in Task Body Text

When creating kanban cards from this plan, ALL quality gate checks MUST be embedded in the task body (`--body` parameter at card creation time), NOT added as comments. Quality gates in comments create a race condition where a worker may complete the task without seeing the gates. Every quality gate in this plan is written as executable text that belongs in the task body.

### CRITICAL: Python Version Selection

- Use `/usr/bin/python3.14` for ALL scripts that `import pcbnew` — never `python3` (3.11 segfaults)
- Use `python3` (ESP-IDF venv, 3.11) for IDF builds, board-lock scripts, and general shell scripts
- When in doubt: if the script touches `.kicad_pcb` files via pcbnew module, use `/usr/bin/python3.14`

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

## Worker Profiles and Assignments

| Worker | Role | Model | Phases |
|--------|------|-------|--------|
| **worker-balloon** | PCB pipeline + board creation + SPI timing | kimi-k2.7-code | Phase 1, 2, 3, 4A, 5, 7 |
| **worker-inspector** | Independent DRC verification + code review | different model | Phase 4B (DRC verification) |
| **worker-admin** | CI updates + integration scripts + documentation | glm-5.2 | Phase 6, 8 |
| **worker-fips** | FIPS/mesh integration only | glm-5.2 | (not assigned to PCB plan phases) |
| **worker-tollgate** | Tollgate payment protocol | glm-5.2 | (not assigned to PCB plan phases) |
| **Felix (HUMAN)** | JLCPCB web upload + order approval | human | Phase 5 Task 5.5 (manual) |

**Reassignment notes (from consultant review):**
- Phase 6 (CI Updates) moved from worker-fips → **worker-admin** (CI is DevOps work, not FIPS)
- Phase 7 (SPI Timing) moved from worker-fips → **worker-balloon** (SPI timing is firmware work)
- Phase 4 DRC final verification moved from worker-balloon → **worker-inspector** (independent review)

---

## GPIO Pin Assignment

**Source:** `tracker/firmware/main/app_main.cpp` lines 85-94, `tracker/firmware/main/radio_task.cpp` line 34, `tracker/firmware/main/Kconfig.projbuild`

### Board V1-FAST Pin Assignment (current pinmap, ADC disabled)

| Function | GPIO | Pin Status | Notes |
|----------|------|------------|-------|
| GPS UART RX | GPIO1 | Required | NMEA from GPS module |
| GPS UART TX | GPIO0 | Optional | Config to GPS (-1 to disable in Kconfig) |
| SPI MISO | GPIO2 | Required | LR2021 → C3. **Needs 10kΩ pull-down (boot strapping)** |
| LR2021 RST | GPIO3 | Required | Active-low reset |
| LR2021 BUSY | GPIO4 | Required | IRQ/handshake |
| LR2021 DIO9 | GPIO5 | Required | IRQ pin |
| SPI SCK | GPIO6 | Required | LR2021 SPI clock |
| SPI MOSI | GPIO7 | Required | C3 → LR2021 |
| ADC (voltage divider) | GPIO8 | **DISABLED** | V1-FAST: not used, no voltage divider components |
| I2C SDA / LED | GPIO9 | LED only | Drop I2C for prototype. Route LED on GPIO9. |
| SPI NSS (CS) | GPIO10 | Required | LR2021 chip select |
| LED | GPIO18 | Available | USB D- on C3; available as GPIO if USB not used in flight |
| FEM_TX | GPIO19 | Available | USB D+ on C3; available as GPIO if USB not used in flight |

### Board V2-ADC Pin Assignment (redesigned — ADC freed)

The V2-ADC board redesigns the pinmap to free GPIO8 for supercap voltage monitoring. The key change: FEM_TX moves from GPIO19 to GPIO0 (dropping GPS TX, which is optional and already set to -1 in Kconfig). This frees GPIO19 (formerly FEM_TX) as unused, and GPIO8 remains dedicated to ADC.

| Function | GPIO | Pin Status | Notes |
|----------|------|------------|-------|
| GPS UART RX | GPIO1 | Required | NMEA from GPS module |
| GPS UART TX | GPIO0 | **DISABLED** | Freed for FEM_TX. Set GPS_UART_TX_PIN=-1 in Kconfig. |
| SPI MISO | GPIO2 | Required | LR2021 → C3. **Needs 10kΩ pull-down (boot strapping)** |
| LR2021 RST | GPIO3 | Required | Active-low reset |
| LR2021 BUSY | GPIO4 | Required | IRQ/handshake |
| LR2021 DIO9 | GPIO5 | Required | IRQ pin |
| SPI SCK | GPIO6 | Required | LR2021 SPI clock |
| SPI MOSI | GPIO7 | Required | C3 → LR2021 |
| ADC (voltage divider) | GPIO8 | **Required** | V2-ADC: supercap voltage monitor. R_DIV1 + R_DIV2 on board. |
| I2C SDA / LED | GPIO9 | LED only | Drop I2C for prototype. Route LED on GPIO9. |
| SPI NSS (CS) | GPIO10 | Required | LR2021 chip select |
| LED | GPIO18 | Available | USB D- on C3; available as GPIO if USB not used |
| FEM_TX | GPIO0 | **REDIRECTED** | Moved from GPIO19 to GPIO0 (was GPS TX, now freed) |

**V2-ADC pinmap rationale:**
- GPIO0 was GPS UART TX, which is optional (Kconfig `GPS_UART_TX_PIN=-1` disables it)
- Moving FEM_TX to GPIO0 frees GPIO19 entirely
- GPIO8 stays dedicated to ADC voltage divider for supercap monitoring
- GPS TX is not needed — we only receive NMEA from GPS, never configure it in flight

### GPIO9 Conflict Resolution (both boards)

GPIO9 serves as LED only (Option A from V1 plan). I2C is dropped for both board variants.

**Decision: Route LED on GPIO9. No I2C on either board.**

Rationale:
- BMP280/MS5611 is optional (Kconfig `CONFIG_ENABLE_BMP280` defaults to `y` but can be set to `n`)
- Fewer nets = simpler routing = faster DRC convergence
- LED is essential for field debugging

### GPIO18/GPIO19 Verification (USB Pins)

ESP32-C3 has GPIO0-GPIO10 as primary GPIOs. GPIO18 and GPIO19 are USB D- and D+ respectively. They CAN be used as regular GPIO if USB is not needed.

**For balloon flight:** USB is not used in flight → GPIO18 is available for LED.

**For bare ESP32-C3 chip on custom PCB:** GPIO18/19 are available as regular GPIO.

**GPIO verification is assigned to Phase 2, Task 2.1** — worker-balloon must verify the ESP32-C3 module pinout before finalizing the netlist.

### GPIO8 Fallback Conflict Resolution (FIXED)

The V1 plan had a fallback table where FEM_TX fell back to GPIO8 (conflicting with ADC). This is now resolved:

- **V1-FAST board:** ADC is disabled. GPIO8 is unused. If FEM_TX cannot use GPIO19 (e.g., module has USB hardwired), FEM_TX falls back to **GPIO8** (no conflict since ADC is disabled on V1-FAST).
- **V2-ADC board:** FEM_TX is redirected to GPIO0. GPIO8 is dedicated to ADC. No conflict exists. If GPIO0 is unavailable on the specific module, FEM_TX falls back to **GPIO19** (its original assignment) and GPIO8 stays on ADC.
- The "mux" fallback from the V1 plan is removed — there is no mux component in the BOM.

---

## Net List Definitions

### V1-FAST Net List (15 nets, 15 components)

| Net # | Net Name | Connected Pads | Track Width | Layer | Notes |
|-------|----------|---------------|-------------|-------|-------|
| 1 | 3V3 | C3:VCC, LR2021:1, GPS:VCC, LDO:OUT, LED_R:1 | 0.40mm | F.Cu | Power rail |
| 2 | GND | C3:GND, LR2021:2/8/10/11/16/18, GPS:GND, LDO:GND, C1:2, C2:2, R_PD:1 | 0.40mm | B.Cu | Ground — explicit tracks, NO pour |
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
| 15 | FEM_TX | C3:GPIO19, FEM:TX | 0.25mm | F.Cu | FEM control (if FEM enabled) |
| 16 | RF_SUB_868 | LR2021:9, ANT1:1 | 0.76mm | F.Cu | Sub-GHz antenna trace (see RF note below) |
| 17 | RF_2G4_2400 | LR2021:18, ANT2:1 | 0.76mm | F.Cu | 2.4GHz antenna trace (see RF note below) |

**V1-FAST total: 17 nets, 16 components** (including R_PD pull-down, excluding voltage divider components since ADC is disabled).

### V2-ADC Net List (18 nets, 18 components)

Same as V1-FAST plus:
- **VDIV_MID**: C3:GPIO8, R_DIV1:2, R_DIV2:1 — voltage divider midpoint (0.25mm, F.Cu)
- FEM_TX connects to C3:GPIO0 instead of C3:GPIO19
- Additional components: R_DIV1 (100kΩ 0402), R_DIV2 (100kΩ 0402)

**V2-ADC total: 18 nets, 18 components** (including R_PD, R_DIV1, R_DIV2).

### RF Trace Impedance Note (FIXED from consultant review)

The V1 plan labeled 0.25mm RF traces as "50Ω approx." This is **incorrect**. On a standard 2-layer 1.6mm FR4 board, 50Ω microstrip requires approximately **0.76mm trace width** (assuming εr≈4.4, 1.6mm substrate height, 1oz copper). A 0.25mm trace is closer to 75-80Ω.

**For prototype balloon boards:** This impedance mismatch is acceptable — the LR2021 module has its own onboard matching network and the antenna traces are short (<10mm). The 0.76mm width is specified to be closer to 50Ω, but exact impedance control is not critical at this stage.

**For production:** Use JLCPCB impedance-controlled stackup or calculate exact width based on the actual stackup parameters.

---

## Component Lists

### V1-FAST Component List (16 components)

| Ref | Component | Footprint | Position (mm) | Notes |
|-----|-----------|-----------|---------------|-------|
| U1 | ESP32-C3 | Module-specific | (12, 12) | Bare chip or dev module |
| U2 | LR2021 | NiceRF castellated, 19.81×14.98mm | (25, 25) | 18 SMD pads |
| U3 | GPS (MAX-M10S) | 4-pad module | (6, 33) | UART only |
| U4 | TPS7A02 LDO | SOT-23-5 | (5, 22) | 3V3 regulator |
| D1 | BAT54 diode | SOD-123 | (4, 18) | Solar protection |
| LED1 | 0603 LED | 0603 | (16, 4) | Status indicator |
| R_LED | 330Ω 0402 | 0402 | (17.5, 4) | LED current limit |
| R_PD | 10kΩ 0402 | 0402 | (10, 14) | **GPIO2 pull-down (boot strapping)** |
| C_CAP | Supercapacitor | Radial THT | (8, 37) | Energy storage |
| SOLAR | Solar connector | 2-pin THT | (3, 37) | Solar panel input |
| ANT1 | U.FL / pad | Edge | (48, 25) | Sub-GHz antenna |
| ANT2 | U.FL / pad | Edge | (48, 30) | 2.4GHz antenna |
| C1 | 10µF 0603 | 0603 | (8, 22) | LDO input cap |
| C2 | 10µF 0603 | 0603 | (7, 24) | LDO output cap |

**V1-FAST: 14 components listed + FEM (optional) + GPS TX connector = 16 total.** No voltage divider components (ADC disabled).

### V2-ADC Component List (18 components)

All V1-FAST components plus:

| Ref | Component | Footprint | Position (mm) | Notes |
|-----|-----------|-----------|---------------|-------|
| R_DIV1 | 100kΩ 0402 | 0402 | (3, 30) | Voltage divider top |
| R_DIV2 | 100kΩ 0402 | 0402 | (3, 32) | Voltage divider bottom |

**V2-ADC: 18 components total.** FEM_TX routed to GPIO0 instead of GPIO19.

### GPIO2 Pull-Down Resistor (ADDED per consultant review)

GPIO2 MUST be LOW at boot (ESP32-C3 boot strapping pin). It's used as SPI MISO (input from LR2021). If the LR2021 has an internal pull-up on MISO, the C3 may not boot.

**R_PD (10kΩ pull-down) is added to the BOM for BOTH board variants.** It connects GPIO2 to GND. This ensures the boot strapping requirement is met regardless of the LR2021's MISO idle state.

- Net: GND (R_PD:1 connects to GND net)
- Net: SPI_MISO (R_PD:2 connects to GPIO2/SPI_MISO net — same net as MISO)
- Position: (10, 14) — near ESP32-C3, between GPIO2 pad and GND track

### LR2021 Pinout (both boards)

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

---

## PHASE BREAKDOWN

### System Constraints

- **Max 2 concurrent workers** (7GB RAM, 4 cores, 4GB swap)
- **FIPS Rust build uses 2-3GB** — do NOT run FIPS while PCB work is in progress
- **Monitor swap:** if swap > 5GB, kill all workers and run one at a time

### Phase Dependency Graph

```
Phase 1 (Pipeline Code) ──┐
                          ├──▶ Phase 2 (Board Creation V1+V2) ──▶ Phase 3 (Auto-Route V1+V2) ──▶ Phase 4A (DRC Loop V1) ──▶ Phase 4A (DRC Loop V2)
                          │                                                                    │                          │
                          │                                                                    ▼                          ▼
                          │                                                           Phase 4B (Inspector DRC V1)  Phase 4B (Inspector DRC V2)
                          │                                                                    │                          │
                          │                                                                    └──────────┬───────────────┘
                          │                                                                               ▼
                          │                                                                     Phase 5 (Gerber Export + Order)
                          │
                          ▼
                    QUALITY GATE 1
Phase 6 (CI Updates, worker-admin) ── independent ──▶ QUALITY GATE 6
Phase 7 (SPI Timing, worker-balloon) ── depends on Phase 5 gerber export (NOT board arrival) ──▶ QUALITY GATE 7
Phase 8 (Integration Scripts, worker-admin) ── independent, can start immediately ──▶ QUALITY GATE 8
```

**Phase 7 dependency clarification (FIXED):** Phase 7 depends on Phase 5 gerber export completion (not board arrival). SPI timing characterization uses the existing S3 test board as a proxy. Actual V2 board testing happens post-arrival (Day 14+). The dependency on Phase 5 is for scheduling priority only — Phase 7 can start during the JLCPCB wait period.

---

## Phase 1: Pipeline Code Implementation (worker-balloon, 2h)

### Objective

Create the `full_pipeline.py` script that implements board creation + A* routing + DRC iteration in a single headless pass. The full A* + pcbnew code is in `docs/coordination/LLM-AUTO-ROUTING-PIPELINE.md` (lines 354-936) but uses `LoadBoard()` which fails headless. The code MUST be adapted to use `NewBoard()` throughout.

### Task 1.1: Create the pipeline script (uses NewBoard, NOT LoadBoard)

```bash
cd ~/repos/balloon-fresh/tracker/hardware

# The pipeline code in LLM-AUTO-ROUTING-PIPELINE.md lines 354-936 uses
# pcbnew.LoadBoard() in TWO places (line 826 and line 872).
# LoadBoard() FAILS HEADLESS — it requires wxApp.
#
# MANDATORY MODIFICATION: Replace BOTH LoadBoard() calls with NewBoard().
# The pipeline must:
# 1. Call pcbnew.NewBoard(output_path) to create an empty board
# 2. Create footprints programmatically (can't load existing board)
# 3. Create nets with board.AddNet()
# 4. Assign nets to pads
# 5. Run A* routing
# 6. Write tracks with board.Add(PCB_TRACK)
# 7. Save with pcbnew.SaveBoard()
# 8. Run DRC via kicad-cli subprocess
# 9. If violations, adjust parameters and re-run from step 1
#
# DO NOT create any pcbnew.ZONE() calls — no copper pours.
# DO NOT use pcbnew.LoadBoard() anywhere — it will crash.
```

Create `tracker/hardware/full_pipeline.py` with the following structure:

```python
#!/usr/bin/python3.14
"""
Full pipeline: Create board → Place footprints → A* route → Save → DRC → Iterate
Run with: /usr/bin/python3.14 full_pipeline.py --board-type v1-fast --output ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_routed.kicad_pcb --max-iterations 10
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

# ... A* router code from LLM-AUTO-ROUTING-PIPELINE.md lines 354-820 ...
# MODIFIED: all LoadBoard() calls replaced with NewBoard()

def create_board_v1_fast(output_path):
    """Create V1-FAST board: 15 nets, 16 components, no ADC."""
    board = pcbnew.NewBoard(output_path)
    # Create board outline (50×40mm on Edge.Cuts)
    # Create all 15+ nets
    # Create all 16 component footprints with correct pad positions
    # Assign nets to pads
    # DO NOT add any zones
    return board

def create_board_v2_adc(output_path):
    """Create V2-ADC board: 18 nets, 18 components, with ADC voltage divider."""
    board = pcbnew.NewBoard(output_path)
    # Same as V1-FAST plus:
    # - VDIV_MID net
    # - R_DIV1, R_DIV2 components
    # - FEM_TX on GPIO0 instead of GPIO19
    # DO NOT add any zones
    return board

def main():
    # Parse args (--board-type v1-fast|v2-adc, --output, --max-iterations)
    # 1. board = create_board_vX(output_path)  # uses NewBoard()
    # 2. nets = parse_board_nets(board)
    # 3. routing_order = default_routing_strategy(nets)
    # 4. assign_layers(nets)
    # 5. router = GridRouter(); router.block_all_pads(nets)
    # 6. for net_code in routing_order: router.route_net(nets[net_code])
    # 7. write_tracks_to_board(board, nets)
    # 8. pcbnew.SaveBoard(output_path, board)
    # 9. drc_result = run_drc(output_path)  # subprocess kicad-cli
    # 10. If violations > 0: adjust strategy, re-route, repeat (max iterations)
```

### Task 1.2: Verify pcbnew API availability

```bash
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
print('LoadBoard:', hasattr(pcbnew, 'LoadBoard'), '(DO NOT USE)')
"
```

### Task 1.3: Smoke test the pipeline

```bash
cd ~/repos/balloon-fresh/tracker/hardware
mkdir -p output

# Create the V1-FAST board
/usr/bin/python3.14 full_pipeline.py \
    --board-type v1-fast \
    --output ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_routed.kicad_pcb \
    --gerber-dir ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_gerbers/ \
    --max-iterations 5

# Verify board was created
kicad-cli pcb drc --format json --output ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_smoke_drc.json ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_routed.kicad_pcb

# Parse DRC results
/usr/bin/python3.14 -c "
import json
with open('$HOME/repos/balloon-fresh/tracker/hardware/output/v1_fast_smoke_drc.json') as f:
    drc = json.load(f)
print(f'Violations: {len(drc.get(\"violations\", []))}')
print(f'Unconnected: {len(drc.get(\"unconnected_items\", []))}')
"
```

QUALITY GATES (MANDATORY — embed in task body, not comments):
[ ] Gate 1: `full_pipeline.py` exists in `tracker/hardware/` and uses `NewBoard()` — verify with: `grep -c 'NewBoard' ~/repos/balloon-fresh/tracker/hardware/full_pipeline.py` (must be ≥1)
[ ] Gate 2: `grep -c 'LoadBoard' ~/repos/balloon-fresh/tracker/hardware/full_pipeline.py` returns 0 — LoadBoard is BANNED
[ ] Gate 3: V1-FAST board file exists at `tracker/hardware/output/v1_fast_routed.kicad_pcb`
[ ] Gate 4: No copper pours — `grep -c '(zone' ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_routed.kicad_pcb` returns 0 — DO NOT create any `pcbnew.ZONE()` calls
[ ] Gate 5: DRC runs without crash — `kicad-cli pcb drc --format json --output /tmp/test.json tracker/hardware/output/v1_fast_routed.kicad_pcb` exits 0
[ ] Gate 6: Use `/usr/bin/python3.14` explicitly (NOT python3) — verify: `grep 'python3.14' ~/repos/balloon-fresh/tracker/hardware/full_pipeline.py` returns ≥1
[ ] Gate 7: Git commit + push: `cd ~/repos/balloon-fresh && git add -A && git commit -m "Phase 1: Pipeline code with NewBoard, no LoadBoard, V1-FAST smoke test" && git push github autonomous/mesh-baseline`

CIRCUIT BREAKER: If the pipeline crashes 3 times consecutively with the same error, STOP. Write a failure summary to `tracker/hardware/FAILURE_SUMMARY.md` describing the error and attempted fixes. Return BLOCKED status. Do NOT retry a 4th time.

---

## Phase 2: Board Creation + Footprint Placement (worker-balloon, 2-3h)

### Objective

Create clean `.kicad_pcb` files for BOTH board variants (V1-FAST and V2-ADC) with all footprints placed and nets assigned, but NO routing (no tracks). The auto-router handles routing in Phase 3.

### Task 2.1: Verify ESP32-C3 module pinout (ASSIGNED — was floating in V1 plan)

Before finalizing the netlist, verify the ESP32-C3 module pinout:

```bash
# Check if using a bare ESP32-C3 chip or a module
# If using ESP32-C3 Mini module: check datasheet for GPIO18/19 availability
# If using bare chip: GPIO18/19 are available as regular GPIO
# If using dev kit with USB connected: GPIO18/19 are NOT available

# Record findings in a comment in full_pipeline.py:
# # Module type: [verified module name]
# # GPIO18 available: YES/NO
# # GPIO19 available: YES/NO
# # If GPIO19 unavailable: FEM_TX falls back to GPIO8 (V1-FAST only, ADC disabled)
```

### Task 2.2: Create V1-FAST board (programmatic)

```bash
cd ~/repos/balloon-fresh/tracker/hardware

# Run the pipeline in board-creation-only mode (no routing)
/usr/bin/python3.14 full_pipeline.py \
    --board-type v1-fast \
    --output ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_unrouted.kicad_pcb \
    --route-only false \
    --max-iterations 0

# Verify board has all expected components and nets
/usr/bin/python3.14 -c "
with open('$HOME/repos/balloon-fresh/tracker/hardware/output/v1_fast_unrouted.kicad_pcb') as f:
    content = f.read()
    print('Footprints found:', content.count('(footprint'))
    print('Nets found:', content.count('(net'))
    print('Pads found:', content.count('(pad'))
    print('Zones (must be 0):', content.count('(zone'))
    print('Tracks (must be 0):', content.count('(segment'))
"
```

### Task 2.3: Create V2-ADC board (programmatic)

```bash
cd ~/repos/balloon-fresh/tracker/hardware

# Run the pipeline in board-creation-only mode for V2-ADC
/usr/bin/python3.14 full_pipeline.py \
    --board-type v2-adc \
    --output ~/repos/balloon-fresh/tracker/hardware/output/v2_adc_unrouted.kicad_pcb \
    --route-only false \
    --max-iterations 0

# Verify board has all expected components and nets (should have 2 more than V1)
/usr/bin/python3.14 -c "
with open('$HOME/repos/balloon-fresh/tracker/hardware/output/v2_adc_unrouted.kicad_pcb') as f:
    content = f.read()
    print('Footprints found:', content.count('(footprint'))
    print('Nets found:', content.count('(net'))
    print('Pads found:', content.count('(pad'))
    print('Zones (must be 0):', content.count('(zone'))
    print('Tracks (must be 0):', content.count('(segment'))
"
```

### Task 2.4: Verify net assignment for both boards

```bash
/usr/bin/python3.14 -c "
# V1-FAST expected nets (no VDIV_MID)
v1_expected = ['3V3', 'GND', 'SPI_SCK', 'SPI_MOSI', 'SPI_MISO', 'SPI_NSS',
               'LR2021_BUSY', 'LR2021_RST', 'LR2021_DIO9', 'GPS_RX',
               'STATUS_LED', 'LED_ANODE', 'VCAP', 'SOLAR_IN',
               'RF_SUB_868', 'RF_2G4_2400']

# V2-ADC expected nets (includes VDIV_MID)
v2_expected = v1_expected + ['VDIV_MID']

for board_name, path, expected in [
    ('V1-FAST', '$HOME/repos/balloon-fresh/tracker/hardware/output/v1_fast_unrouted.kicad_pcb', v1_expected),
    ('V2-ADC', '$HOME/repos/balloon-fresh/tracker/hardware/output/v2_adc_unrouted.kicad_pcb', v2_expected)
]:
    with open(path) as f:
        content = f.read()
    print(f'=== {board_name} ===')
    for net in expected:
        status = '✅' if net in content else '❌ MISSING'
        print(f'  {status} {net}')
"
```

QUALITY GATES (MANDATORY — embed in task body, not comments):
[ ] Gate 1: V1-FAST board file exists at `tracker/hardware/output/v1_fast_unrouted.kicad_pcb`
[ ] Gate 2: V2-ADC board file exists at `tracker/hardware/output/v2_adc_unrouted.kicad_pcb`
[ ] Gate 3: V1-FAST has ≥14 footprints, ≥15 nets, 0 zones, 0 tracks — verify by parsing .kicad_pcb text
[ ] Gate 4: V2-ADC has ≥16 footprints, ≥18 nets, 0 zones, 0 tracks — verify by parsing .kicad_pcb text
[ ] Gate 5: No copper pours — `grep -c '(zone' ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_unrouted.kicad_pcb` returns 0 AND same for v2_adc — DO NOT create any `pcbnew.ZONE()` calls
[ ] Gate 6: All expected nets present (run verification script in Task 2.4)
[ ] Gate 7: DRC parseable — `kicad-cli pcb drc --format json --output /tmp/v1_test.json ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_unrouted.kicad_pcb` exits 0
[ ] Gate 8: Use `/usr/bin/python3.14` explicitly (NOT python3) for all pcbnew scripts
[ ] Gate 9: Git commit + push: `cd ~/repos/balloon-fresh && git add -A && git commit -m "Phase 2: V1-FAST + V2-ADC boards created, footprints placed, nets assigned, no routing" && git push github autonomous/mesh-baseline`

CIRCUIT BREAKER: If board creation fails 3 times consecutively with the same error (e.g., footprint creation error, pad assignment error), STOP. Write failure summary to `tracker/hardware/FAILURE_SUMMARY.md`. Return BLOCKED status. Do NOT retry.

---

## Phase 3: A* Auto-Routing (worker-balloon, 1-2h)

### Objective

Run the A* pathfinding router on BOTH unrouted boards to generate collision-free track paths for all nets.

### Task 3.1: Run auto-router on V1-FAST board

```bash
cd ~/repos/balloon-fresh/tracker/hardware

/usr/bin/python3.14 full_pipeline.py \
    --board-type v1-fast \
    --output ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_routed.kicad_pcb \
    --max-iterations 5
```

**NOTE:** The pipeline uses `NewBoard()` — it creates the board, places footprints, routes, and saves in a single pass. There is no separate "load unrouted board" step. If the pipeline needs to iterate, it re-creates the board from scratch each iteration with adjusted parameters.

### Task 3.2: Run auto-router on V2-ADC board

```bash
cd ~/repos/balloon-fresh/tracker/hardware

/usr/bin/python3.14 full_pipeline.py \
    --board-type v2-adc \
    --output ~/repos/balloon-fresh/tracker/hardware/output/v2_adc_routed.kicad_pcb \
    --max-iterations 5
```

### Task 3.3: Verify routing output for both boards

```bash
/usr/bin/python3.14 -c "
for board_name, path in [
    ('V1-FAST', '$HOME/repos/balloon-fresh/tracker/hardware/output/v1_fast_routed.kicad_pcb'),
    ('V2-ADC', '$HOME/repos/balloon-fresh/tracker/hardware/output/v2_adc_routed.kicad_pcb')
]:
    with open(path) as f:
        content = f.read()
    print(f'=== {board_name} ===')
    print(f'  Track segments: {content.count(\"(segment\")}')
    print(f'  Vias: {content.count(\"(via\")}')
    print(f'  Zones (must be 0): {content.count(\"(zone\")}')
"
```

QUALITY GATES (MANDATORY — embed in task body, not comments):
[ ] Gate 1: V1-FAST routed board exists at `tracker/hardware/output/v1_fast_routed.kicad_pcb`
[ ] Gate 2: V2-ADC routed board exists at `tracker/hardware/output/v2_adc_routed.kicad_pcb`
[ ] Gate 3: V1-FAST has ≥15 track segments (one per net minimum) — verify by parsing .kicad_pcb text
[ ] Gate 4: V2-ADC has ≥18 track segments — verify by parsing .kicad_pcb text
[ ] Gate 5: No zones (copper pours) — `grep -c '(zone'` returns 0 for BOTH board files — DO NOT create any `pcbnew.ZONE()` calls — explicit GND tracks only
[ ] Gate 6: Use `/usr/bin/python3.14` explicitly (NOT python3)
[ ] Gate 7: Git commit + push: `cd ~/repos/balloon-fresh && git add -A && git commit -m "Phase 3: A* auto-routing complete for V1-FAST and V2-ADC boards" && git push github autonomous/mesh-baseline`

CIRCUIT BREAKER: If the A* router fails to route the same net 3 times consecutively, STOP. Write failure summary identifying which net(s) failed and why. Return BLOCKED status. Do NOT retry — escalate to orchestrator.

---

## Phase 4A: DRC Iteration Loop (worker-balloon, 30 min - 2h per board)

### Objective

Run DRC, fix violations, repeat until 0 violations and 0 unconnected for EACH board variant. worker-balloon does the iterative fixing. Phase 4B (worker-inspector) does the final independent verification.

### Task 4A.1: Run DRC on V1-FAST board

```bash
kicad-cli pcb drc --format json \
    --output ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_drc.json \
    ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_routed.kicad_pcb

/usr/bin/python3.14 -c "
import json
with open('$HOME/repos/balloon-fresh/tracker/hardware/output/v1_fast_drc.json') as f:
    drc = json.load(f)
violations = drc.get('violations', [])
unconnected = drc.get('unconnected_items', [])
print(f'V1-FAST DRC: {len(violations)} violations, {len(unconnected)} unconnected')
print()
print('Violation types:')
for v in violations:
    print(f'  {v.get(\"type\", \"unknown\")}: {v.get(\"description\", \"\")[:80]}')
"
```

### Task 4A.2: DRC Iteration Loop Specification

```
REPEAT (max 10 iterations per board):
  1. Run kicad-cli pcb drc --format json --output <board>_drc_iter_N.json <board>
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
  8. Re-run full_pipeline.py with adjusted parameters (NewBoard → route → save)
  9. Go to step 1

INTERMEDIATE ESCALATION CRITERIA:
  - If after 3 iterations the violation count is NOT decreasing → escalate (circuit breaker)
  - If after 5 iterations there are still SHORTS → escalate (shorts are harder to fix than clearance)
  - If only unconnected items remain (0 violations) → try manual routing of those specific nets by editing the .kicad_pcb S-expression text directly
```

### Task 4A.3: Run DRC on V2-ADC board

Same process as Task 4A.1 but for V2-ADC:
```bash
kicad-cli pcb drc --format json \
    --output ~/repos/balloon-fresh/tracker/hardware/output/v2_adc_drc.json \
    ~/repos/balloon-fresh/tracker/hardware/output/v2_adc_routed.kicad_pcb

/usr/bin/python3.14 -c "
import json
with open('$HOME/repos/balloon-fresh/tracker/hardware/output/v2_adc_drc.json') as f:
    drc = json.load(f)
violations = drc.get('violations', [])
unconnected = drc.get('unconnected_items', [])
print(f'V2-ADC DRC: {len(violations)} violations, {len(unconnected)} unconnected')
"
```

### Task 4A.4: Common DRC Fixes

| DRC Violation | Fix |
|---------------|-----|
| Short: 3V3 ↔ GND | Check for overlapping tracks on same layer. Move GND to B.Cu, 3V3 to F.Cu |
| Short: SPI_SCK ↔ SPI_MOSI | A* clearance too small. Increase `CLEARANCE_MM` from 0.30 to 0.35 |
| Unconnected: net X | A* couldn't find path. Try alternate layer, or move component |
| Clearance: track near pad | Increase `clearance_cells` in GridRouter |
| DRC error: "pad has no net" | Footprint pad missing net assignment in create_board function |

QUALITY GATES (MANDATORY — embed in task body, not comments):
[ ] Gate 1: V1-FAST DRC violations == 0 — verify: `/usr/bin/python3.14 -c "import json; d=json.load(open('$HOME/repos/balloon-fresh/tracker/hardware/output/v1_fast_drc.json')); print(len(d.get('violations',[])))"` returns 0
[ ] Gate 2: V1-FAST unconnected == 0 — same script, check `unconnected_items`
[ ] Gate 3: V2-ADC DRC violations == 0 — same check for v2_adc_drc.json
[ ] Gate 4: V2-ADC unconnected == 0
[ ] Gate 5: No copper pours — `grep -c '(zone'` returns 0 for BOTH routed board files — DO NOT create any `pcbnew.ZONE()` calls — explicit GND tracks only
[ ] Gate 6: All nets routed — each net has ≥1 track segment in BOTH board files
[ ] Gate 7: Use `/usr/bin/python3.14` explicitly (NOT python3)
[ ] Gate 8: Git commit + push: `cd ~/repos/balloon-fresh && git add -A && git commit -m "Phase 4A: DRC iteration complete — V1-FAST and V2-ADC both at 0 violations / 0 unconnected" && git push github autonomous/mesh-baseline`

CIRCUIT BREAKER: If the same DRC violation persists for 3 consecutive iterations, STOP. Write failure summary identifying the persistent violation and attempted fixes. Return BLOCKED status. Do NOT retry — escalate to orchestrator.

**Rollback (HEADLESS ONLY — no KiCad GUI):** If DRC doesn't converge after 10 iterations:
1. Try increasing grid resolution from 0.1mm to 0.05mm (finer A* grid)
2. Try 4-layer board (add GND and PWR planes) — costs more but routes easier
3. Edit the .kicad_pcb S-expression text directly to manually route stubborn nets
4. Simplify the design: drop GPS or non-essential nets to reduce complexity
5. Escalate to orchestrator — Felix may manually route on a machine with a display

**CRITICAL:** Do NOT export gerbers or order boards that fail DRC. The V1 disaster was caused by ordering a board with 437 violations.

---

## Phase 4B: Independent DRC Verification (worker-inspector, 30 min)

### Objective

Independent DRC verification by a DIFFERENT worker (worker-inspector) using a DIFFERENT model. worker-balloon did the routing and iterative DRC fixing. worker-inspector confirms the 0/0 result is real and the board files are not empty/false-passes.

This separation of concerns is MANDATORY. worker-balloon has incentive to declare "DRC passes" to move forward. worker-inspector has no such bias.

### Task 4B.1: Verify V1-FAST board independently

```bash
# worker-inspector runs DRC from scratch — does NOT trust worker-balloon's results
kicad-cli pcb drc --format json \
    --output ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_inspector_drc.json \
    ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_routed.kicad_pcb

/usr/bin/python3.14 -c "
import json

# 1. Check DRC results
with open('$HOME/repos/balloon-fresh/tracker/hardware/output/v1_fast_inspector_drc.json') as f:
    drc = json.load(f)
v = len(drc.get('violations', []))
u = len(drc.get('unconnected_items', []))
print(f'V1-FAST Inspector DRC: {v} violations, {u} unconnected')

# 2. Verify board is not empty (false-pass detection)
with open('$HOME/repos/balloon-fresh/tracker/hardware/output/v1_fast_routed.kicad_pcb') as f:
    content = f.read()
fp_count = content.count('(footprint')
net_count = content.count('(net')
track_count = content.count('(segment')
zone_count = content.count('(zone')
print(f'Footprints: {fp_count} (expect ≥14)')
print(f'Nets: {net_count} (expect ≥15)')
print(f'Tracks: {track_count} (expect ≥15)')
print(f'Zones: {zone_count} (expect 0)')

# 3. Final verdict
if v == 0 and u == 0 and fp_count >= 14 and net_count >= 15 and track_count >= 15 and zone_count == 0:
    print('✅ V1-FAST BOARD IS READY FOR FABRICATION')
else:
    print('❌ V1-FAST BOARD IS NOT READY — fix remaining issues')
"
```

### Task 4B.2: Verify V2-ADC board independently

```bash
kicad-cli pcb drc --format json \
    --output ~/repos/balloon-fresh/tracker/hardware/output/v2_adc_inspector_drc.json \
    ~/repos/balloon-fresh/tracker/hardware/output/v2_adc_routed.kicad_pcb

/usr/bin/python3.14 -c "
import json

with open('$HOME/repos/balloon-fresh/tracker/hardware/output/v2_adc_inspector_drc.json') as f:
    drc = json.load(f)
v = len(drc.get('violations', []))
u = len(drc.get('unconnected_items', []))
print(f'V2-ADC Inspector DRC: {v} violations, {u} unconnected')

with open('$HOME/repos/balloon-fresh/tracker/hardware/output/v2_adc_routed.kicad_pcb') as f:
    content = f.read()
fp_count = content.count('(footprint')
net_count = content.count('(net')
track_count = content.count('(segment')
zone_count = content.count('(zone')
print(f'Footprints: {fp_count} (expect ≥16)')
print(f'Nets: {net_count} (expect ≥18)')
print(f'Tracks: {track_count} (expect ≥18)')
print(f'Zones: {zone_count} (expect 0)')

if v == 0 and u == 0 and fp_count >= 16 and net_count >= 18 and track_count >= 18 and zone_count == 0:
    print('✅ V2-ADC BOARD IS READY FOR FABRICATION')
else:
    print('❌ V2-ADC BOARD IS NOT READY — fix remaining issues')
"
```

QUALITY GATES (MANDATORY — embed in task body, not comments):
[ ] Gate 1: V1-FAST inspector DRC: 0 violations, 0 unconnected — verified independently by worker-inspector
[ ] Gate 2: V2-ADC inspector DRC: 0 violations, 0 unconnected — verified independently by worker-inspector
[ ] Gate 3: V1-FAST board has ≥14 footprints, ≥15 nets, ≥15 tracks, 0 zones (false-pass detection)
[ ] Gate 4: V2-ADC board has ≥16 footprints, ≥18 nets, ≥18 tracks, 0 zones (false-pass detection)
[ ] Gate 5: No copper pours — 0 zones in BOTH board files — explicit GND tracks only
[ ] Gate 6: Use `/usr/bin/python3.14` explicitly (NOT python3)
[ ] Gate 7: Git commit + push: `cd ~/repos/balloon-fresh && git add -A && git commit -m "Phase 4B: Independent DRC verification PASSED — V1-FAST and V2-ADC confirmed 0/0 by worker-inspector" && git push github autonomous/mesh-baseline`

CIRCUIT BREAKER: If the same DRC discrepancy is found 3 times (e.g., worker-balloon says 0/0 but worker-inspector finds violations), STOP. Write failure summary. Return BLOCKED status. This indicates a systematic issue with worker-balloon's DRC process.

---

## Phase 5: Gerber Export + JLCPCB Order Preparation (worker-balloon + Felix HUMAN, 30 min)

### Objective

Export fabrication files for BOTH board variants and prepare JLCPCB order. worker-balloon creates the gerbers and zip files. Felix (human) does the actual JLCPCB web upload and ordering.

### Task 5.1: Export gerbers for V1-FAST

```bash
mkdir -p ~/repos/balloon-fresh/tracker/hardware/gerbers_v1_fast

# Export gerbers (all layers for JLCPCB)
kicad-cli pcb export gerbers \
    --output ~/repos/balloon-fresh/tracker/hardware/gerbers_v1_fast/ \
    --layers F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts,F.Paste,B.Paste,F.Fab,B.Fab \
    ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_routed.kicad_pcb

# Export drill files (Excellon format)
kicad-cli pcb export drill \
    --output ~/repos/balloon-fresh/tracker/hardware/gerbers_v1_fast/ \
    --format excellon \
    ~/repos/balloon-fresh/tracker/hardware/output/v1_fast_routed.kicad_pcb

# List exported files
ls -la ~/repos/balloon-fresh/tracker/hardware/gerbers_v1_fast/
```

### Task 5.2: Export gerbers for V2-ADC

```bash
mkdir -p ~/repos/balloon-fresh/tracker/hardware/gerbers_v2_adc

# Export gerbers (all layers for JLCPCB)
kicad-cli pcb export gerbers \
    --output ~/repos/balloon-fresh/tracker/hardware/gerbers_v2_adc/ \
    --layers F.Cu,B.Cu,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts,F.Paste,B.Paste,F.Fab,B.Fab \
    ~/repos/balloon-fresh/tracker/hardware/output/v2_adc_routed.kicad_pcb

# Export drill files (Excellon format)
kicad-cli pcb export drill \
    --output ~/repos/balloon-fresh/tracker/hardware/gerbers_v2_adc/ \
    --format excellon \
    ~/repos/balloon-fresh/tracker/hardware/output/v2_adc_routed.kicad_pcb

# List exported files
ls -la ~/repos/balloon-fresh/tracker/hardware/gerbers_v2_adc/
```

### Task 5.3: Zip both gerber sets for JLCPCB

```bash
# Zip V1-FAST gerbers
cd ~/repos/balloon-fresh/tracker/hardware/gerbers_v1_fast/
zip ../gerbers_v1_fast_jlcpcb.zip *
ls -la ../gerbers_v1_fast_jlcpcb.zip

# Zip V2-ADC gerbers
cd ~/repos/balloon-fresh/tracker/hardware/gerbers_v2_adc/
zip ../gerbers_v2_adc_jlcpcb.zip *
ls -la ../gerbers_v2_adc_jlcpcb.zip
```

### Task 5.4: Delete old V1 gerbers (prevent accidental ordering of broken board)

```bash
# CRITICAL: Delete old V1 gerbers to prevent accidental ordering of the broken board
rm -rf ~/repos/balloon-fresh/tracker/hardware/gerbers_v1/
rm -rf ~/repos/balloon-fresh/tracker/hardware/gerbers_v1_fixed/

# Verify deletion
ls ~/repos/balloon-fresh/tracker/hardware/gerbers_v1* 2>&1
# Should show: No such file or directory (except gerbers_v1_fast/)
```

### Task 5.5: JLCPCB Order — MANUAL HUMAN STEP (Felix)

**⚠️ This is a FELIX ACTION ITEM. No worker agent can do this. **

Felix must:
1. Go to jlcpcb.com
2. Upload `gerbers_v1_fast_jlcpcb.zip` as one design
3. Upload `gerbers_v2_adc_jlcpcb.zip` as a second design
4. Verify both previews match 50×40mm boards
5. Select options from the table below for BOTH designs
6. Add both to cart, checkout in same order
7. Save order confirmation number

**JLCPCB Order Checklist (both boards, same order):**

| Item | V1-FAST | V2-ADC | Notes |
|------|---------|--------|-------|
| Board size | 50 × 40 mm | 50 × 40 mm | 2-layer |
| Quantity | 5 (minimum) | 5 (minimum) | Or 10 if cost difference is small |
| Thickness | 1.6mm | 1.6mm | Standard |
| Copper weight | 1oz | 1oz | Standard |
| Surface finish | HASL (lead-free) | HASL (lead-free) | Cheapest, fine for prototype |
| Solder mask | Green | Green | Standard |
| Silkscreen | White | White | Standard |
| Castellated holes | YES | YES | LR2021 module needs castellated pads |
| Shipping | Express (5-day) | Express (5-day) | Both in same shipment |
| BOM | Not needed | Not needed | Bare PCB, hand-solder |
| PCBA | No | No | Hand assembly |

QUALITY GATES (MANDATORY — embed in task body, not comments):
[ ] Gate 1: V1-FAST gerber files exist — ≥11 .gbr files + 1 .drl + 1 .gbrjob in `gerbers_v1_fast/`
[ ] Gate 2: V2-ADC gerber files exist — ≥11 .gbr files + 1 .drl + 1 .gbrjob in `gerbers_v2_adc/`
[ ] Gate 3: V1-FAST zip created — `gerbers_v1_fast_jlcpcb.zip` exists
[ ] Gate 4: V2-ADC zip created — `gerbers_v2_adc_jlcpcb.zip` exists
[ ] Gate 5: Old gerbers deleted — `gerbers_v1/` and `gerbers_v1_fixed/` no longer exist
[ ] Gate 6: No copper pours in either board — 0 zones in both .kicad_pcb files — explicit GND tracks only
[ ] Gate 7: Use `/usr/bin/python3.14` explicitly (NOT python3) for any pcbnew verification
[ ] Gate 8: Git commit + push: `cd ~/repos/balloon-fresh && git add -A && git commit -m "Phase 5: Gerbers exported for V1-FAST and V2-ADC, old V1 gerbers deleted, ready for JLCPCB order" && git push github autonomous/mesh-baseline`

CIRCUIT BREAKER: If gerber export fails 3 times consecutively with the same error, STOP. Write failure summary. Return BLOCKED status.

**Rollback (HEADLESS ONLY — no KiCad GUI):** If JLCPCB rejects gerbers (format issue):
1. Re-export with `--usegerberextensions` flag
2. Use different layer set
3. Check if KiCad 9.0 gerber format is compatible with JLCPCB's current requirements
4. Escalate to Felix for manual gerber inspection

---

## Phase 6: CI Updates (worker-admin, 30 min — can run concurrently with Phase 1-5)

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

QUALITY GATES (MANDATORY — embed in task body, not comments):
[ ] Gate 1: CI workflow updated — `ci-host-tests.yml` has Suites 5+6
[ ] Gate 2: Tests pass — run: `cd ~/repos/balloon-fresh && act -W .github/workflows/ci-host-tests.yml` (or push and check GitHub Actions)
[ ] Gate 3: All tests pass — 12 relay + 6 nostr_dump = 18 new tests
[ ] Gate 4: Git commit + push: `cd ~/repos/balloon-fresh && git add -A && git commit -m "Phase 6: CI updates — relay pipeline + nostr_dump test suites added" && git push github autonomous/mesh-baseline`

CIRCUIT BREAKER: If CI fails 3 times consecutively with the same error, STOP. Write failure summary. Return BLOCKED status.

**Rollback:** Revert the CI workflow change with `git revert HEAD` if it breaks existing tests.

---

## Phase 7: SPI Timing Characterization (worker-balloon — during 2-week JLCPCB wait)

### Objective

Verify ESP32-C3 can drive LR2021 SPI at ≥8MHz before boards arrive. Uses existing S3 test board as proxy.

**Dependency clarification (FIXED):** Phase 7 depends on Phase 5 gerber export completion for scheduling priority only. It does NOT depend on board arrival. SPI timing uses the S3 test board which already exists. Actual V2 board testing happens post-arrival (Day 14+).

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

# Acquire board lock (use python3 for board-lock script, NOT python3.14)
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
# Use python3 (not python3.14) for board-lock scripts
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

QUALITY GATES (MANDATORY — embed in task body, not comments):
[ ] Gate 1: SPI test completed — results logged for 8/4/2 MHz
[ ] Gate 2: Minimum viable frequency identified — ≤8MHz with reliable TX/RX
[ ] Gate 3: Firmware updated if needed — SPI clock set to verified frequency
[ ] Gate 4: Board lock released — `python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py check board-a` returns exit 1
[ ] Gate 5: Use `/usr/bin/python3.14` for pcbnew scripts; use `python3` (ESP-IDF venv) for IDF and board-lock scripts
[ ] Gate 6: Git commit + push: `cd ~/repos/balloon-fresh && git add -A && git commit -m "Phase 7: SPI timing characterization complete — results logged, firmware adjusted if needed" && git push github autonomous/mesh-baseline`

CIRCUIT BREAKER: If SPI communication fails 3 times consecutively at the same frequency with the same error, STOP. Write failure summary. Return BLOCKED status. Do NOT retry at that frequency — try a lower frequency or escalate.

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

# Trap to ensure locks are released on ANY exit (including errors)
trap 'python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release board-a 2>/dev/null; \
      python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release board-b 2>/dev/null' EXIT

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

# Locks released by trap on EXIT
```

### Task 8.2: Write Phase 6 test script (nostr round-trip)

**File:** `~/repos/balloon-fresh/tracker/tests/test_nostr_roundtrip.sh`

Tests: Board A sends Nostr event → Board B receives and stores → verify with `nostr_dump` CLI.

Must include `trap EXIT` for lock release (same pattern as Task 8.1).

### Task 8.3: Write Phase 7 test script (tollgate PAY→ACK)

**File:** `~/repos/balloon-fresh/tracker/tests/test_tollgate_roundtrip.sh`

Tests: Board A sends PAY → Board B decodes and ACKs → Board A receives ACK → verify seq + amount.

Must include `trap EXIT` for lock release (same pattern as Task 8.1).

QUALITY GATES (MANDATORY — embed in task body, not comments):
[ ] Gate 1: 3 test scripts exist — `test_raw_ping.sh`, `test_nostr_roundtrip.sh`, `test_tollgate_roundtrip.sh` in `tracker/tests/`
[ ] Gate 2: Scripts are executable — `chmod +x` applied to all 3 scripts
[ ] Gate 3: Scripts use board lock — all scripts call `balloon-board-lock.py acquire` before board access
[ ] Gate 4: Scripts release locks on exit — all scripts have `trap '...' EXIT` for lock release on any exit condition
[ ] Gate 5: Scripts use BoardSerial wrapper — all Python serial access uses `BoardSerial` not raw `serial.Serial()`
[ ] Gate 6: Git commit + push: `cd ~/repos/balloon-fresh && git add -A && git commit -m "Phase 8: Integration test scripts written — raw ping, nostr roundtrip, tollgate roundtrip" && git push github autonomous/mesh-baseline`

CIRCUIT BREAKER: If a test script fails to run 3 times consecutively with the same error, STOP. Write failure summary. Return BLOCKED status.

**Rollback:** Scripts can be modified when boards arrive — they're templates, not final.

---

## DRC ITERATION LOOP DETAILED SPECIFICATION

### Loop Structure

```
INPUT: board_type (v1-fast or v2-adc)
OUTPUT: routed_board.kicad_pcb (0 DRC violations, 0 unconnected)

max_iterations = 10
grid_resolution = 0.1mm (500×400 cells for 50×40mm board)
clearance = 0.30mm (increase to 0.35mm if clearance violations persist)

FOR iteration = 1 TO max_iterations:
    1. CREATE board
       - board = pcbnew.NewBoard(output_path)  # ALWAYS NewBoard, NEVER LoadBoard
       - Create footprints and nets programmatically
       - DO NOT add any zones/copper pours

    2. A* ROUTE all nets
       - Order: GND → 3V3 → short signals → long signals → RF traces
       - Layer: power on B.Cu, signals on F.Cu
       - Width: power=0.40mm, signal=0.25mm, RF=0.76mm (closer to 50Ω on 1.6mm FR4)
       - For each net:
         a. Unblock this net's pads on the grid
         b. A* pathfind between all pad pairs (nearest-neighbor ordering)
         c. If blocked, try alternate layer (insert via)
         d. Block routed cells with clearance

    3. WRITE tracks to board
       - For each net, for each segment: board.Add(PCB_TRACK)
       - DO NOT add any zones/copper pours

    4. SAVE board with pcbnew.SaveBoard(output_path, board)

    5. RUN DRC: kicad-cli pcb drc --format json --output <board>_drc.json <board>

    6. PARSE DRC JSON
       - violations = drc["violations"]
       - unconnected = drc["unconnected_items"]

    7. CHECK convergence
       - IF len(violations) == 0 AND len(unconnected) == 0: BREAK (SUCCESS)

    8. CHECK circuit breaker
       - IF same violation type persists 3 consecutive iterations: STOP, BLOCKED

    9. CHECK intermediate escalation
       - IF iteration >= 3 AND violation count not decreasing: escalate
       - IF iteration >= 5 AND shorts still present: escalate

    10. ANALYZE failures
       - short_violations = [v for v if "short" in v.type]
       - clearance_violations = [v for v if "clearance" in v.type]
       - For each violation: extract net name from item descriptions

    11. ADJUST strategy
       - For shorts: swap conflicting nets to different layers
       - For clearance: increase clearance_mm by 0.05mm
       - For unconnected: try alternate layer for that net

    12. REPEAT

IF NOT converged after max_iterations:
    REPORT: X violations, Y unconnected remain
    ESCALATE: manual routing needed for failed nets
    BLOCKED status
```

### DRC JSON Parsing Reference

```python
import json

with open('/path/to/drc.json') as f:
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
8. **R_PD near ESP32-C3 GPIO2 pad** — Place at (10, 14), short track to GPIO2 and GND

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
13. VCAP (power, F.Cu) — supercap to LDO
14. SOLAR_IN (power, F.Cu) — solar connector to diode
15. VDIV_MID (F.Cu, V2-ADC only) — short route to voltage divider
16. FEM_TX (F.Cu) — FEM control, GPIO19 (V1-FAST) or GPIO0 (V2-ADC)
17. RF_SUB_868 (RF, F.Cu) — LR2021 to antenna pad, keep short and direct, 0.76mm width
18. RF_2G4_2400 (RF, F.Cu) — same as above, 0.76mm width
```

### Layer Strategy

| Layer | Nets | Rationale |
|-------|------|-----------|
| F.Cu (top) | 3V3, all signals, RF traces | Signals on top for easy inspection |
| B.Cu (bottom) | GND only | Ground as explicit tracks, star topology |

**DO NOT add copper pours on either layer.** The V1 board had 18× 3V3↔GND shorts from a ground pour. This applies to BOTH board variants.

---

## WHAT HAPPENS DURING THE 2-WEEK JLCPCB WAIT

### Timeline (FIXED — worker assignments corrected)

| Day | Activity | Worker | Duration |
|-----|----------|--------|----------|
| 1-2 | SPI timing characterization on S3 test board | **worker-balloon** | 4h |
| 1-2 | CI updates (relay pipeline + nostr_dump tests) | **worker-admin** | 30 min |
| 3-5 | Integration test scripts (Phases 5-7) | **worker-admin** | 3h |
| 3-5 | Firmware SPI clock adjustment (if needed from timing test) | **worker-balloon** | 2h |
| 5-7 | Test scripts dry-run on S3 boards (no LR2021, just protocol) | **worker-admin** | 4h |
| 7-10 | Documentation: assembly guide, BOM, test procedures | **worker-balloon** | 4h |
| 10-14 | Buffer / contingency | All | — |
| 14 | Both boards arrive (V1-FAST + V2-ADC in same shipment) | — | — |

---

## ROLLBACK PLANS SUMMARY (HEADLESS ONLY — NO KiCad GUI)

| Phase | Failure | Rollback Action (HEADLESS) |
|-------|---------|---------------------------|
| 1 (Pipeline code) | Python script crashes | Edit .kicad_pcb S-expression text directly; adjust A* grid parameters; simplify design by dropping non-essential nets |
| 2 (Board creation) | Can't create footprints programmatically | Edit .kicad_pcb text file manually (it's S-expression based); escalate to Felix for manual board creation on a machine with a display |
| 3 (Auto-route) | A* can't route all nets | Edit .kicad_pcb S-expression text to manually add track segments; adjust A* parameters; simplify design |
| 4A (DRC loop) | Doesn't converge in 10 iterations | Increase grid resolution to 0.05mm; try 4-layer board; edit .kicad_pcb text directly for stubborn nets; drop non-essential nets |
| 4B (Inspector DRC) | Inspector finds violations worker missed | Return to Phase 4A with specific violation list; worker-balloon fixes and resubmits |
| 5 (Gerber export) | JLCPCB rejects format | Re-export with `--usegerberextensions`; try different layer set; escalate to Felix for manual gerber inspection |
| 5 (Order) | Wrong board ordered | Cancel order within 24h, JLCPCB allows cancellation |
| 6 (CI) | Tests fail in CI | Revert CI change with `git revert HEAD`, tests pass locally |
| 7 (SPI timing) | C3 can't do 8MHz | Lower SPI clock to 4MHz or 2MHz in firmware |
| 7 (SPI timing) | C3 can't do 2MHz | Escalate — may need dual-MCU (last resort) |
| 8 (Test scripts) | Scripts wrong | Modify when boards arrive — templates only |

### Nuclear Rollback (if entire pipeline fails)

1. Delete all auto-generated PCB files
2. Edit the .kicad_pcb S-expression text file manually (it's a text-based format — no GUI needed)
3. Create a minimal board with fewer nets (drop GPS, drop FEM, keep only SPI + power + LED)
4. Escalate to Felix — he may manually design the board on a machine with a display (this is the only GUI-allowed path, and it requires Felix's personal machine, not the headless server)
5. The firmware is unaffected — it's already correct for single-MCU

**ALL rollback plans are headless-compatible.** No rollback requires KiCad GUI on this server. The only GUI reference is Felix's personal machine as a last resort.

---

## APPENDIX A: File Paths Reference

### Source Files (read-only reference)

```
~/repos/balloon-fresh/docs/coordination/LLM-AUTO-ROUTING-PIPELINE.md   # Full pipeline code (lines 354-936) — WARNING: uses LoadBoard(), must be adapted
~/repos/balloon-fresh/docs/coordination/AUTO-ROUTING-FEASIBILITY.md     # API verification results
~/repos/balloon-fresh/docs/coordination/PCB-PLAN-CONSULTANT-REVIEW.md   # Consultant review (5 blockers, 11 major issues)
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
~/repos/balloon-fresh/tracker/hardware/full_pipeline.py                          # Combined create + route + DRC pipeline
~/repos/balloon-fresh/tracker/hardware/output/v1_fast_unrouted.kicad_pcb         # V1-FAST unrated board
~/repos/balloon-fresh/tracker/hardware/output/v1_fast_routed.kicad_pcb           # V1-FAST routed board
~/repos/balloon-fresh/tracker/hardware/output/v2_adc_unrouted.kicad_pcb          # V2-ADC unrouted board
~/repos/balloon-fresh/tracker/hardware/output/v2_adc_routed.kicad_pcb            # V2-ADC routed board
~/repos/balloon-fresh/tracker/hardware/gerbers_v1_fast/                          # V1-FAST gerber output directory
~/repos/balloon-fresh/tracker/hardware/gerbers_v1_fast_jlcpcb.zip                # V1-FAST JLCPCB upload zip
~/repos/balloon-fresh/tracker/hardware/gerbers_v2_adc/                           # V2-ADC gerber output directory
~/repos/balloon-fresh/tracker/hardware/gerbers_v2_adc_jlcpcb.zip                 # V2-ADC JLCPCB upload zip
~/repos/balloon-fresh/tracker/tests/test_raw_ping.sh                            # Integration test: raw ping
~/repos/balloon-fresh/tracker/tests/test_nostr_roundtrip.sh                     # Integration test: nostr
~/repos/balloon-fresh/tracker/tests/test_tollgate_roundtrip.sh                  # Integration test: tollgate
```

### Working Directory (NOT /tmp — files persist across reboots)

All board files are stored in the repository under `tracker/hardware/output/` instead of `/tmp/` to prevent loss on reboot. Intermediate DRC JSON files are also stored there.

---

## APPENDIX B: Key Python API Calls (verified on this system)

```python
#!/usr/bin/python3.14
import sys
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

# Board creation — ALWAYS use NewBoard, NEVER LoadBoard
board = pcbnew.NewBoard('/path/to/output.kicad_pcb')

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

# Save board — ALWAYS use SaveBoard, NEVER LoadBoard to re-open
pcbnew.SaveBoard('/path/to/output.kicad_pcb', board)

# Save = done. Now run DRC via kicad-cli (subprocess):
# kicad-cli pcb drc --format json --output /path/to/drc.json /path/to/board.kicad_pcb
```

---

## APPENDIX C: DRC Command Reference

```bash
# Run DRC (headless)
kicad-cli pcb drc --format json --output /path/to/drc.json /path/to/board.kicad_pcb

# Run DRC with severity filter (errors only)
kicad-cli pcb drc --format json --output /path/to/drc.json --severity-error /path/to/board.kicad_pcb

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
| GPIO0 | Boot strapping | YES (with care) | Must be HIGH at boot for normal boot. GPS TX (V1) or FEM_TX (V2). |
| GPIO1 | General purpose | YES | GPS RX in firmware |
| GPIO2 | Boot strapping | YES (with pull-down) | Must be LOW at boot. SPI MISO. **10kΩ pull-down REQUIRED (R_PD in BOM)** |
| GPIO3 | General purpose | YES | LR2021 RST in firmware |
| GPIO4 | General purpose | YES | LR2021 BUSY in firmware |
| GPIO5 | General purpose | YES | LR2021 DIO9 in firmware |
| GPIO6 | General purpose | YES | SPI SCK in firmware |
| GPIO7 | General purpose | YES | SPI MOSI in firmware |
| GPIO8 | General purpose | YES | ADC voltage divider (V2-ADC only). Unused on V1-FAST. |
| GPIO9 | General purpose | YES | LED (I2C dropped) |
| GPIO10 | General purpose | YES | SPI NSS in firmware |
| GPIO18 | USB D- | Available | LED in firmware. Available if USB not used in flight |
| GPIO19 | USB D+ | Available | FEM_TX (V1-FAST). Unused on V2-ADC (FEM_TX moved to GPIO0). |

### Boot Strapping Pins (IMPORTANT)

**GPIO2 MUST be LOW at boot.** It's used as SPI MISO (input from LR2021). At boot, the LR2021 MISO line should be LOW (idle). If the LR2021 has a pull-up on MISO, the C3 may not boot. **A 10kΩ pull-down resistor (R_PD) is included in the BOM for BOTH board variants** and connects GPIO2 to GND.

GPIO0 MUST be HIGH at boot for normal boot mode. On V1-FAST it's GPS TX (output to GPS module, driven by C3 — should be fine). On V2-ADC it's FEM_TX (output — should be fine if configured as output HIGH or left floating with pull-up).

---

## APPENDIX E: Critical Reminders for Workers

1. **USE `/usr/bin/python3.14`** for ALL pcbnew scripts — NEVER `python3` (3.11 segfaults with pcbnew). Use `python3` (ESP-IDF venv) only for IDF builds and board-lock scripts.
2. **USE `NewBoard()`** — NEVER `LoadBoard()` (fails headless without wxApp). This is non-negotiable.
3. **NO COPPER POURS** — This caused 18× 3V3↔GND shorts on V1. Route GND as explicit tracks. DO NOT create any `pcbnew.ZONE()` calls.
4. **DRC MUST BE 0/0** — Do NOT export gerbers or order boards with any DRC violations. Confirmed by worker-inspector (independent), not worker-balloon.
5. **DELETE OLD GERBERS** — `gerbers_v1/` and `gerbers_v1_fixed/` must be deleted to prevent accidental V1 ordering
6. **SINGLE-MCU ONLY** — No RP2040. No dual-MCU. The firmware is single-MCU.
7. **MAX 2 WORKERS** — System has 7GB RAM, 4GB swap. FIPS build uses 2-3GB. Don't run FIPS during PCB work.
8. **BOARD LOCK FOR HARDWARE** — Use `balloon-board-lock.py` for any board access. Always release. Use `trap EXIT` in scripts.
9. **COMMIT AND PUSH** — Uncommitted work is invisible to the orchestrator. Commit after EACH phase with the exact git command in the quality gates.
10. **ESCALATE BLOCKERS** — If stuck for >30 min on any task, or if circuit breaker triggers, escalate to orchestrator. Don't silently spin.
11. **CIRCUIT BREAKER** — 3 consecutive failures on the same error = STOP, write failure summary, return BLOCKED. Do NOT retry.
12. **QUALITY GATES IN TASK BODY** — All quality gates are mandatory task body content, not comments or metadata. Embed them in `--body` at kanban card creation.
13. **TWO BOARDS** — V1-FAST (no ADC) and V2-ADC (with ADC). Both in same JLCPCB order. Both must pass DRC independently.
14. **NO KICAD GUI** — This server is headless. All rollback plans use .kicad_pcb text editing or parameter adjustment, not GUI. The only GUI path is Felix's personal machine as a last resort.
15. **JLCPCB UPLOAD IS HUMAN** — Task 5.5 (JLCPCB web upload and ordering) is a Felix action item. Workers produce the zip files; Felix does the upload.

---

## APPENDIX F: Changes from V1 Plan (Revision Summary)

### 5 Blockers Fixed

| # | Blocker | Fix |
|---|---------|-----|
| 1 | LoadBoard() used in pipeline code | ALL references changed to NewBoard(). Pipeline code explicitly warns against LoadBoard(). Combined create+route+save in single script. |
| 2 | DRC verification by same worker who routed | Phase 4 split into 4A (worker-balloon iteration) and 4B (worker-inspector independent verification). Different worker, different model. |
| 3 | Quality gates in tables, not task bodies | All quality gates rewritten as checkbox lists in task body text with explicit shell commands. Instructions added: embed in `--body` at kanban card creation. |
| 4 | No circuit breaker in iterative tasks | Circuit breaker added to EVERY task body: "3 consecutive failures on same error = STOP, write failure summary, return BLOCKED." |
| 5 | No git commit + push in task bodies | Every task body now ends with: `Git commit + push: cd ~/repos/balloon-fresh && git add -A && git commit -m "Phase N: ..." && git push github autonomous/mesh-baseline` |

### 11 Major Issues Fixed

| # | Major Issue | Fix |
|---|-------------|-----|
| 1 | worker-fips assigned CI updates | Reassigned Phase 6 to worker-admin |
| 2 | worker-fips assigned SPI timing | Reassigned Phase 7 to worker-balloon |
| 3 | GPIO8 fallback conflict with ADC | Resolved: V1-FAST disables ADC (GPIO8 free for FEM_TX fallback). V2-ADC redirects FEM_TX to GPIO0. Removed fake "mux" fallback. |
| 4 | GPIO2 pull-down not in BOM | R_PD (10kΩ 0402) added to BOM for BOTH board variants. Position (10, 14). Connected to GND net. |
| 5 | Rollback plans reference KiCad GUI | ALL GUI references removed. Rollback plans now use .kicad_pcb S-expression text editing, parameter adjustment, or design simplification. Only Felix's personal machine as last resort. |
| 6 | JLCPCB web upload as worker task | Task 5.5 explicitly marked as "MANUAL HUMAN STEP (Felix)". Workers produce zip files only. |
| 7 | Phase 7 timeline contradiction | Dependency clarified: Phase 7 depends on Phase 5 gerber export for scheduling, not board arrival. Timeline corrected to show worker-balloon (not worker-fips). |
| 8 | RF trace impedance claim wrong | 0.25mm is NOT 50Ω on 1.6mm FR4. Corrected to 0.76mm (closer to 50Ω). Note added: LR2021 has onboard matching, exact impedance not critical for prototype. |
| 9 | Missing V2 board section | Full V2-ADC board section added: redesigned pinmap (FEM_TX→GPIO0, GPIO8 dedicated to ADC), separate net list (18 nets), separate component list (18 components), separate gerber export. |
| 10 | Both boards in same JLCPCB order | Phase 5 produces two gerber zips. Task 5.5 instructs Felix to upload both as separate designs in same JLCPCB cart. |
| 11 | Board files in /tmp (lost on reboot) | All board files moved to `tracker/hardware/output/` in the repository. Committed to git. |

### Additional Fixes (Minor issues from consultant review)

| # | Minor Issue | Fix |
|---|-------------|-----|
| 1 | Net list header said ~12 nets | Corrected to exact counts (17 for V1-FAST, 18 for V2-ADC) |
| 2 | Component count approximate | Changed to exact counts (16 for V1-FAST, 18 for V2-ADC) |
| 3 | Phase 8 test scripts missing trap | Added `trap '...' EXIT` to test script template |
| 4 | Board files in /tmp | Moved to `tracker/hardware/output/` |

---

*End of V2 execution plan. This document supersedes PCB-AUTO-ROUTE-EXECUTION-PLAN.md.*