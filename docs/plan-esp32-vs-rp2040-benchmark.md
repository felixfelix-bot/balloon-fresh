# Plan: ESP32-C3 vs RP2040 SPI Throughput Benchmark

## Date: 2026-07-30
## Status: AWAITING APPROVAL
## Scope: speed-tests (this worktree)

## Objective

Definitively measure which MCU delivers higher SPI throughput to the LR2021
radio chip, under identical conditions (same firmware logic, same payload,
same LA capture method).

## Hardware Available

- 2x ESP32-C3_Mini_V1 + LR2021 (already connected, proven working)
- 1x RP2040 + LR2021 (current test rig, proven working)
- 1x Saleae Logic logic analyzer (fx2lafw, 24 MHz)
- 1x 2W LR2021 board with amplifier (unsoldered — awaiting MCU decision)

## Test Matrix

| Test | MCU | Firmware | Payload | Duration |
|------|-----|----------|---------|----------|
| A | RP2040 | rp2040-cont-tx (255B, existing) | 255 bytes | 1s capture |
| B | ESP32-C3 #1 | esp32-cont-tx (255B, NEW) | 255 bytes | 1s capture |
| C | ESP32-C3 #2 | esp32-cont-tx (255B, NEW) | 255 bytes | 1s capture |

Tests B and C use two different ESP32 boards to rule out board-specific issues.

## Metrics Compared

- SPI clock frequency (actual, measured from SCK)
- SPI transfer time per packet
- Inter-packet gap (air time + firmware overhead)
- Bus duty cycle
- Effective throughput (kbps)
- Packets per second

## Pin Mapping

### RP2040 (existing, do not change)
```
D0=CS(GP5)  D1=SCK(GP6)  D2=MOSI(GP7)  D3=MISO(GP4)
D4=BUSY(GP8)  D5=IRQ(GP9)  D6=RST(GP10)
```

### ESP32-C3 Mini V1 (from existing firmware/esp32-c3-flrc/main/main.cpp)
```
GPIO6=SCK   GPIO2=MISO   GPIO7=MOSI   GPIO10=CS(NSS)
GPIO4=BUSY  GPIO5=IRQ    GPIO3=RST    GPIO8=LED
```

### LA Channel Mapping (SAME for both MCUs)
```
D0=CS  D1=SCK  D2=MOSI  D3=MISO  D4=BUSY  D5=IRQ  D6=RST
```

## Task Breakdown

### Task 1: ESP32-C3 Continuous TX Firmware
**Worker**: worker-balloon (leaf)
**Depends on**: nothing
**Quality gates**: TDD (compiles+flashes), build pass, docs

Create `esp32-cont-tx` firmware mode in existing ESP32-C3 codebase:
- Add `CONTINUOUS_TX` build flag to CMakeLists.txt
- In app_main: if CONTINUOUS_TX defined, run infinite TX loop (no packet count limit)
- Same 3-command pattern as RP2040: CLEAR_IRQ → WRITE_TX_FIFO → SET_TX
- Wait for TX_DONE IRQ, immediately send next packet
- Print stats every 100 packets (non-blocking, after IRQ wait)
- 255-byte payload, 20 MHz SPI, TX_POWER_DBM=12

**Deliverable**: firmware compiles with `idf.py build`, flashes to ESP32-C3
**Verification**: serial monitor shows "CONT_TX START" and TX counters incrementing

### Task 2: ESP32 Make Targets for LA Capture
**Worker**: worker-balloon (leaf)
**Depends on**: Task 1
**Quality gates**: make target runs clean, capture has data

Add to Makefile:
- `make debug-esp32` target: build → flash → start TX → capture → zip
- Uses `idf.py` for build/flash (not PlatformIO)
- Same sigrok capture command as RP2040 debug
- Same LA channel mapping
- 1200 baud BOOTSEL NOT needed — ESP32 uses `esptool` for flash
- Auto-detect ESP32 port (scan /dev/ttyACM* and /dev/ttyUSB* for CP2102/CH340/ESP32)

**Deliverable**: `make debug-esp32 PORT=/dev/ttyACM0` produces captures/esp32-test.sr
**Verification**: LA capture file is non-empty when analyzed

### Task 3: Capture Baseline RP2040 (Test A)
**Worker**: Felix (manual, 5 minutes)
**Depends on**: nothing (firmware already exists)

```bash
make debug ENV=rp2040-cont-tx DURATION=1 OUTPUT=captures/bench-rp2040.sr
```

**Deliverable**: captures/bench-rp2040.zip sent to speed-tests group

### Task 4: Capture ESP32-C3 #1 (Test B)
**Worker**: Felix (manual, 5 minutes)
**Depends on**: Tasks 1+2 complete and pushed

```bash
make debug-esp32 PORT=/dev/ttyACM0 OUTPUT=captures/bench-esp32-1.sr
```

**Deliverable**: captures/bench-esp32-1.zip sent to speed-tests group

### Task 5: Capture ESP32-C3 #2 (Test C)
**Worker**: Felix (manual, 5 minutes)
**Depends on**: Tasks 1+2 complete and pushed

```bash
make debug-esp32 PORT=/dev/ttyACM1 OUTPUT=captures/bench-esp32-2.sr
```

**Deliverable**: captures/bench-esp32-2.zip sent to speed-tests group

### Task 6: Analyze + Document Results
**Worker**: speed-tests manager (me)
**Depends on**: Tests A, B, C all captured

- Run analyze_spi.py on all 3 captures
- Write comparison table (SPI clock, throughput, duty cycle, gaps)
- Update docs/mcu-assessment-rp2040-vs-esp32.md with empirical results
- Write decision recommendation (threshold: >15% improvement = switch)

**Quality gates**: docs committed + pushed, analysis reproducible

### Task 7: MCU Decision
**Worker**: Felix (human decision)
**Depends on**: Task 6

Based on empirical data:
- **ESP32-C3 wins by >15%**: solder 2W board to ESP32-C3
- **RP2040 within 15%**: solder 2W board to RP2040 (dual core advantage)
- **Tie or inconclusive**: stay on RP2040 (toolchain ready)

## Dependency Graph

```
Task 1 (ESP32 firmware) ─┐
                          ├─→ Task 2 (make targets) ─┐
Task 3 (RP2040 capture) ──┤                          ├─→ Task 6 (analyze) ──→ Task 7 (decision)
                          │                          │
Task 4 (ESP32 #1)  ───────┤◄─────────────────────────┘
Task 5 (ESP32 #2)  ───────┘
```

Tasks 1+2 can run in parallel with Task 3 (RP2040 capture).
Tasks 4+5 require Tasks 1+2 complete.

## Quality Gates (All Tasks)

1. **TDD**: Firmware compiles before any capture. Build is the test.
2. **Tests pass**: LA capture is non-empty (has SPI transactions).
3. **Docs updated**: Each task commits analysis/findings in same commit as code.
4. **Atomic commits**: One concern per commit, conventional messages.
5. **Pushed**: `git push github rf-tests` exit 0.

## Scheduling

Tasks 1+2 can be dispatched to worker-balloon immediately (kanban or delegate_task).
Tasks 3-5 are manual Felix work (~15 minutes total).
Task 6 is automatic once captures arrive.
Task 7 is Felix's decision.

### Recommended dispatch sequence:

1. **NOW**: Dispatch Tasks 1+2 to worker-balloon (parallel)
2. **NOW**: Felix captures RP2040 baseline (Task 3) while worker builds firmware
3. **WHEN WORKER DONE**: Felix captures both ESP32 boards (Tasks 4+5)
4. **AUTO**: Speed-tests manager analyzes all 3 (Task 6)
5. **FELIX**: Decision (Task 7)

## Risk: LA Probe Rewiring

The LA probes are currently clipped to RP2040 pins. For ESP32 tests, they need
to be moved to ESP32-C3 pins. Pin mapping:

```
LA D0 (CS)   → ESP32 GPIO10
LA D1 (SCK)  → ESP32 GPIO6
LA D2 (MOSI) → ESP32 GPIO7
LA D3 (MISO) → ESP32 GPIO2
LA D4 (BUSY) → ESP32 GPIO4
LA D5 (IRQ)  → ESP32 GPIO5
LA D6 (RST)  → ESP32 GPIO3
LA GND       → ESP32 GND
```

This is manual work (~5 minutes). No make target can automate probe rewiring.

## Estimated Timeline

| Phase | Duration | Who |
|-------|----------|-----|
| Firmware + make targets | 30 min | worker-balloon |
| RP2040 baseline capture | 5 min | Felix |
| ESP32 probe rewire | 5 min | Felix |
| ESP32 captures (x2) | 10 min | Felix |
| Analysis + docs | 10 min | speed-tests manager |
| **Total** | **~60 min** | |
