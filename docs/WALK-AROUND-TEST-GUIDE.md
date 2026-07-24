# Walk-Around Test Guide — LR2021 Full Characterization

## Overview

This guide walks the operator through an outdoor range test using the
14-phase multi-radio sweep firmware. One walk captures all radio paths
(HF FLRC, HF LoRa, LF LoRa, LF FLRC) in a single pass.

**Time required:** ~2 hours (including prep)
**People needed:** 1 (carry TX) + laptop at RX (can be same person if using power bank)

---

## Pre-Test Checklist (15 min)

### Hardware

- [ ] Both RP2040 boards flashed:
  - TX board (F242D): `rp2040-sweep-gps-tx` (GPS-synced) or `rp2040-sweep-tx` (no GPS)
  - RX board (8332): `rp2040-sweep-rx`
- [ ] TX board powered by power bank with dummy load (100Ω resistor — see POWERBANK-DUMMY-LOAD-FIX.md)
- [ ] Both antennas connected:
  - HF antenna on Pin 10 (2.4 GHz)
  - LF antenna on Pin 9 (868 MHz sub-GHz)
- [ ] RX board connected to laptop USB
- [ ] GPS module connected to TX board (GP0/GP1, 9600 baud) — optional but recommended

### Software

```bash
# 1. Acquire board locks
BALLOON_TRACK=range-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both

# 2. Verify boards visible
ls /dev/ttyACM*
# Note which port is RX (typically ACM2 or ACM0)

# 3. Verify 1m baseline BEFORE going outside
# (see Indoor Baseline section below)
```

---

## Flash Firmware (5 min)

```bash
cd ~/worktrees/balloon-range-tests/firmware/rp2040

# TX board (the one you'll carry — needs GPS if using GPS sync)
pio run -e rp2040-sweep-gps-tx -t upload --upload-port /dev/ttyACM<tx_port>

# RX board (stays on laptop)
pio run -e rp2040-sweep-rx -t upload --upload-port /dev/ttyACM<rx_port>
```

**Non-GPS fallback** (if no GPS module or can't get fix):
```bash
pio run -e rp2040-sweep-tx -t upload --upload-port /dev/ttyACM<tx_port>
```

> If flash fails: USB CDC may have died. Power-cycle the board
> (unplug/replug USB). If still stuck, see board recovery protocol in AGENTS.md.

---

## Indoor Baseline (5 min)

Before going outside, verify both boards communicate:

```bash
# Start capture at 1m distance
python3 scripts/sweep_capture.py \
    --port /dev/ttyACM<rx_port> \
    --distance 1 \
    --env indoor \
    --cycles 1
```

Wait ~4 minutes for one complete cycle (14 phases). Check output:

- **PER should be 0-5%** for all FLRC phases at 1m
- **RSSI should be -30 to -70 dBm** (may saturate at -8 dBm at very close range — normal)
- **LoRa phases should show 0% PER** with RSSI -40 to -60 dBm

If all phases show `rx=0`: TX/RX not synchronized. Power-cycle both boards and try again.
The 8-second LED countdown should start simultaneously on both.

---

## Outdoor Test Procedure

### Setup (at base station / RX position)

1. Place RX board + laptop at a fixed position with USB cable
2. Open terminal, ready to run capture script
3. Position TX board at starting distance with power bank connected
4. Verify both boards have started their 8-second LED countdown

### Distance Points

Standard outdoor sweep distances:

| Point | Distance | Dwell Time | Notes |
|-------|----------|------------|-------|
| 1 | 10m | 1 cycle (~4 min) | Close range, expect 0% PER |
| 2 | 25m | 1 cycle | |
| 3 | 50m | 1 cycle | |
| 4 | 100m | 1 cycle | FLRC may start dropping |
| 5 | 200m | 1 cycle | FLRC likely failing, LoRa should hold |
| 6 | 500m | 1 cycle | LoRa SF7 may fail, SF12 should work |
| 7 | 1000m | 2 cycles | Stretch goal — only if 500m has signal |

> **Dwell = 1 full sweep cycle** (~4 min = 14 phases × ~17s avg).
> For LoRa SF12 phases (50s each), the cycle is ~4 min total.

### At Each Distance Point

```bash
python3 scripts/sweep_capture.py \
    --port /dev/ttyACM<rx_port> \
    --distance <meters> \
    --env outdoor_los \
    --cycles 1 \
    --notes "antenna vertical, clear LOS"
```

Watch the terminal output. You should see:

```
=== CYCLE 0 START ===
  Phase 0: HF-LoRa-SF7 ...
  [0] Phase  0 HF-LoRa-SF7     rx= 50/50   PER=  0.0%  RSSI= -65dBm  (min -67)
  Phase 1: HF-LoRa-SF9 ...
  [0] Phase  1 HF-LoRa-SF9     rx= 50/50   PER=  0.0%  RSSI= -68dBm  (min -70)
  ...
=== CYCLE 0 COMPLETE (1 done) ===
```

Move to next distance point when you see "CYCLE COMPLETE".

### Antenna Orientation

- **HF (2.4 GHz):** Use the PCB antenna or wire dipole on Pin 10. Keep vertical for omnidirectional coverage.
- **LF (868 MHz):** Wire antenna on Pin 9. Also vertical.
- Both TX and RX antennas should be same orientation (both vertical recommended).

---

## PA Characterization (Optional — If Time Permits)

To characterize PA-on vs PA-off at each distance:

1. Flash TX with PA-on firmware: `rp2040-sweep-gps-tx` (default 12.5 dBm)
2. Run full sweep at each distance
3. Reflash TX with PA-off: `rp2040-sweep-tx` + `-D TX_POWER_DBM=0.0f` build flag
4. Repeat sweep at same distances

> PA is binary on this chip: codes 0-24 = PA off (~0 dBm), code 25 = PA on (12.5 dBm).
> PA-off is useful for close-range measurements where PA-on saturates the receiver.

---

## Post-Test Data Processing

```bash
cd ~/worktrees/balloon-range-tests

# All CSV files are in data/
ls data/

# Merge all captures into one dataset
cat data/char_dist_*.csv > data/all_results.csv

# Generate plots (requires matplotlib)
/opt/miniconda/bin/python3.13 tools/plot_characterization.py data/all_results.csv --output-dir plots/

# View plots
ls plots/
```

### Expected Results

| Distance | HF FLRC 2600 | HF LoRa SF7 | LF LoRa SF7 | LF LoRa SF12 |
|----------|-------------|------------|------------|-------------|
| 10m | 0% PER, -47 dBm | 0% PER, -47 dBm | 0% PER, -38 dBm | 0% PER, -38 dBm |
| 100m | ~50% PER, -67 dBm | 0% PER, -67 dBm | 0% PER, -58 dBm | 0% PER, -58 dBm |
| 500m | 100% PER | ~50% PER, -81 dBm | ~10% PER, -72 dBm | 0% PER, -72 dBm |

> These are theoretical estimates based on free-space path loss.
> Actual results will vary with antenna gain, multipath, and ground reflection.

---

## Troubleshooting

### No packets received (rx=0 for all phases)

1. Check TX board is powered (LED should be blinking)
2. Check TX started its sweep cycle (LED was blinking countdown, now solid during TX)
3. Power bank may have shut off — check dummy load resistor is installed
4. Try non-GPS firmware if GPS sync is failing

### Only some phases receive packets

- **FLRC works, LoRa doesn't:** Check LF antenna on Pin 9
- **LoRa works, FLRC doesn't:** Check HF antenna on Pin 10
- **HF works, LF doesn't:** Antenna or path issue on sub-GHz

### Serial port disappears

- USB cable loose — reconnect
- ESP32 bridge watchdog crash — physical replug of ESP32 USB
- See board recovery protocol in AGENTS.md

### Capture script can't open port

```bash
# Check who holds the lock
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py status

# Acquire if needed
BALLOON_TRACK=range-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both
```

---

## Sweep Cycle Timing

The 14-phase cycle takes approximately:

| Phase | Duration |
|-------|----------|
| HF-LoRa-SF7 | 15s |
| HF-LoRa-SF9 | 15s |
| HF-LoRa-SF12 | 30s |
| HF-FLRC-2600 | 8s |
| HF-FLRC-1300 | 8s |
| HF-FLRC-650 | 8s |
| HF-FLRC-325 | 8s |
| LF-LoRa-SF7 | 8s |
| LF-LoRa-SF9 | 20s |
| LF-LoRa-SF12 | 50s |
| LF-FLRC-2600 | 8s |
| LF-FLRC-1300 | 8s |
| LF-FLRC-650 | 8s |
| LF-FLRC-325 | 8s |
| **Total** | **~4 min** |

---

## Quick Reference Commands

```bash
# Flash TX (GPS version)
cd ~/worktrees/balloon-range-tests/firmware/rp2040
pio run -e rp2040-sweep-gps-tx -t upload --upload-port /dev/ttyACM0

# Flash RX
pio run -e rp2040-sweep-rx -t upload --upload-port /dev/ttyACM2

# Capture at 50m outdoor
cd ~/worktrees/balloon-range-tests
python3 scripts/sweep_capture.py --port /dev/ttyACM2 --distance 50 --env outdoor_los --cycles 1

# Plot results
/opt/miniconda/bin/python3.13 tools/plot_characterization.py data/all_results.csv
```
