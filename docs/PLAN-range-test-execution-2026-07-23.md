# RANGE TEST PLAN — Comprehensive Execution

## Overview

Systematic characterization of LR2021 FLRC link across packet size, bitrate, power, and distance. All work uses the range-tests branch in `~/worktrees/balloon-range-tests/`.

## Hardware

| Port | Board | Role |
|------|-------|------|
| /dev/ttyACM0 | ESP32 UART bridge → Pico A | RX (bridge) |
| /dev/ttyACM1 | Pico A direct USB | RX (direct, CDC may be dead) |
| /dev/ttyACM2 | ESP32 UART bridge → Pico B | TX (bridge) |
| /dev/ttyACM3 | Pico B direct USB | TX (direct) |

Flashing: 1200 baud on ACM3 for TX, ESP32 bootsel-oneshot on ACM0 for RX. See `flrc-firmware-ops` skill.

## Task 1: Packet Size Binary Search

**Goal:** Find maximum reliable packet size between 127 (works) and 160 (borderline).

**Status:** 127 ✓, 160 borderline, 192 ✗, 255 ✗. Testing 144 next.

**Binary search steps:**

| Step | Size | If WORKS → | If FAILS → |
|------|------|------------|------------|
| 1 | 144 | test 152 | test 136 |
| 2 | 152 or 136 | test 156 or 140 | test 148 or 132 |
| 3 | final | done | done |

**Method per step:**
1. Edit `TX_PKT_SIZE` in `flrc_range_tx_auto.cpp` and `RX_PKT_SIZE` in `flrc_range_rx_auto.cpp`
2. Build: `pio run -e rp2040-range-tx-auto && pio run -e rp2040-range-rx-auto`
3. Flash TX: 1200 baud on ACM3 → picotool load → picotool reboot
4. Flash RX: ESP32 bootsel-oneshot on ACM0 → picotool load → picotool reboot → restore UART bridge
5. Capture 30s of RX output via ACM0
6. Check: are seq numbers 0-499? Any garbage (202182159)? What's the PER?
7. Record result, proceed to next binary step

**Pass criteria:** PER < 5%, all seq in 0-499 range, no constant garbage
**Fail criteria:** Constant garbage seq (202182159 = 0x0C0D0E0F), PER > 10%

**Deliverable:** Commit with `pktSize=<max>` set as default, push to range-tests branch.

## Task 2: Revert to Known-Good for Range Testing

After binary search completes, set both TX and RX to the maximum reliable packet size found (or 127 if search incomplete). Build, flash both boards, verify 1m baseline: 0% loss, correct seq, RSSI -70 to -80 dBm.

## Task 3: Indoor Multi-Window Baseline

**Goal:** Verify firmware stability over 5+ minutes before going outdoors.

1. Both boards at desk distance (~2m)
2. Capture 5 min of RX output via ACM0
3. Verify: PER stable across all windows, no increasing PER trend, RSSI consistent
4. Save to `data/indoor-baseline-YYYYMMDD.csv`
5. Commit + push

## Task 4: Bitrate Sweep at Fixed Distance

**Goal:** Measure PER and throughput at 4 FLRC bitrates, indoor desk distance.

| Bitrate | TX define | RX define | Build env |
|---------|-----------|-----------|-----------|
| 2600 | `TX_BITRATE_KBPS 2600` | `RX_BITRATE_KBPS 2600` | rp2040-range-tx-auto |
| 1300 | `TX_BITRATE_KBPS 1300` | `RX_BITRATE_KBPS 1300` | rp2040-range-tx-1300 |
| 650 | `TX_BITRATE_KBPS 650` | `RX_BITRATE_KBPS 650` | rp2040-range-tx-650 |
| 325 | `TX_BITRATE_KBPS 325` | `RX_BITRATE_KBPS 325` | rp2040-range-tx-325 |

Per bitrate:
1. Build + flash both boards
2. Capture 2 min of RX output
3. Record: PER, throughput_kbps, RSSI avg/min/max
4. Save to `data/bitrate-sweep-YYYYMMDD.csv`

**Expected:** Lower bitrates → lower PER, more range, lower throughput.

## Task 5: Power Sweep at Fixed Distance

**Goal:** Quantify range gain from TX power increase.

Use serial commands (no reflash!): `POWER <dbm>` on TX board via ACM3.

| Power | Command |
|-------|---------|
| 0 dBm | `POWER 0` |
| 3 dBm | `POWER 3` |
| 6 dBm | `POWER 6` |
| 9 dBm | `POWER 9` |
| 12 dBm | `POWER 12` |
| 12.5 dBm | `POWER 12.5` |

Per power level:
1. Send `POWER <dbm>` to TX via ACM3 (or ACM2 bridge)
2. Send `RUN` to start burst
3. Capture 1 min of RX output
4. Record: PER, RSSI, throughput

**Expected:** Higher power → lower PER, higher RSSI. ~6 dB per halving of PER.

## Task 6: Outdoor Distance Sweep

**Goal:** RSSI and PER vs distance, the main missing data.

**Prerequisites:**
- Solve powerbank auto-shutoff (dummy load >50mA or direct LiPo)
- Wire dipole antennas on both boards (61mm wire at 2440 MHz)
- Laptop with full battery for RX logging

**Distances (binary steps):** 2, 4, 8, 16, 32, 64, 128, 256, 512m

Per distance:
1. Place TX at distance, antenna vertical, on powerbank
2. RX stays at base station, connected to laptop, serial logging
3. Dwell 30s (captures at least 1 full burst cycle)
4. Record GPS timestamp on arrival
5. Move to next distance

**Post-test:**
1. Export GPS track from phone (GPX)
2. Correlate RX uptime_ms with GPS timestamps
3. Plot: RSSI vs distance, PER vs distance, throughput vs distance
4. Save to `data/outdoor-sweep-YYYYMMDD.csv`
5. Commit + push

## Task 7: Commit All Findings

After all tasks complete:
1. Set default packet size to max reliable (from Task 1)
2. Commit all firmware changes with conventional messages
3. Push to both GitHub and ngit
4. Update `docs/STATUS-balloon-range-tests.md`
5. Update memory with key findings

## Execution Notes

- **Board sharing:** Only 2 boards. Flash one at a time. TX first, then RX.
- **Flashing TX:** 1200 baud on ACM3 → RPI-RP2 → picotool load → picotool reboot
- **Flashing RX:** ESP32 bootsel-oneshot on ACM0 → RPI-RP2 → picotool load → picotool reboot → restore UART bridge
- **Capture:** `timeout <seconds> cat /dev/ttyACM0 > /tmp/rx_capture.txt` (via bridge)
- **Verify TX:** `timeout 3 cat /dev/ttyACM3 | head -3` — should show BURST lines with correct pktSize
- **Kill captures before flashing:** `pkill -f 'cat /dev/ttyACM'`
- **Git:** `cd ~/worktrees/balloon-range-tests && git add ... && git commit -m "..." && git push origin range-tests && git push github range-tests`

## Task Dependencies

```
Task 1 (binary search) → Task 2 (revert to max)
Task 2 → Task 3 (indoor baseline)
Task 3 → Task 4 (bitrate sweep)
Task 3 → Task 5 (power sweep)
Task 3 → Task 6 (outdoor sweep) — needs physical action
Task 4,5,6 → Task 7 (commit all)
```

Tasks 1-5 can be done autonomously (no physical action needed, boards on desk).
Task 6 requires outdoor physical action (walking with TX board).