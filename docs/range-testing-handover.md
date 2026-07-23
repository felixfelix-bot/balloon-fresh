# Range Testing Handover — Next Phase

**Prerequisite:** All software tasks complete. All bugs fixed. All firmware builds. Test runner ready.
**Status:** READY for interactive range testing with operator.

---

## What We Have

### Firmware (17 envs, all build)
- LoRa TX: SF7/SF9/SF12 at 12 dBm + SF7 at 0/3/6/12 dBm
- LoRa RX: SF7/SF9/SF12 (with cumulativeRx PER fix)
- FLRC TX+RX: 2600/1300/650/325 kbps

### Tools
- `tools/test_runner.py` — flash, capture, sweep, parse
- `tools/sweep-config-flrc.json` — FLRC sweep config template

### Verified Baseline (indoor 1-2m)
- FLRC: all 4 bitrates, 0% PER, 195-602 kbps throughput
- LoRa: all 3 SFs, 0-3% PER, 1.5-30.9 kbps TX rate
- Power: all 4 levels show identical RSSI (-8 dBm) — receiver saturated at close range

---

## What We Need To Do (Interactive)

### Phase A: Outdoor Range Characterization

**Goal:** Map PER vs distance for each modulation.

**Setup:**
- Operator carries TX board outdoors
- RX board stays at fixed position (laptop + USB)
- Test at: 10m, 25m, 50m, 100m, 200m+ (line of sight)
- Record GPS coordinates at each position

**Procedure per distance:**
1. Acquire mutex: `BALLOON_TRACK=speed-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both`
2. Flash desired firmware (e.g., FLRC 2600 TX+RX)
3. Run: `python3 tools/test_runner.py capture --duration 20`
4. Note distance, environment (clear LOS, partial obstruction, etc.)
5. Repeat for each modulation at each distance

**Priority order:**
1. FLRC 2600 (fastest, shortest range expected)
2. LoRa SF7 (medium range)
3. LoRa SF12 (longest range)
4. FLRC 325 (slowest FLRC, longer range than 2600)

### Phase B: TX Power vs Distance

**Goal:** Find minimum TX power for reliable link at each distance.

**Setup:** Same as Phase A but sweep power levels at each distance.

**At each distance where PER > 0%:**
- Re-run with higher TX power
- Find the power threshold where PER drops to 0%
- This defines the link budget curve

### Phase C: Interference Testing

**Goal:** Characterize WiFi/BLE coexistence.

**Setup:**
- Active WiFi on 2.4 GHz (channel overlap with 2440 MHz)
- Active BLE devices nearby
- Compare PER with and without interference

### Phase D: Antenna Comparison

**Goal:** Compare PCB antenna vs dipole vs Yagi.

**Setup:** Same distance, different antennas on TX side.
- PCB antenna (current dev board)
- Wire dipole (planned V1)
- PCB Yagi (planned V2)

---

## Hardware Checklist for Field Testing

- [ ] 2x RP2040 + LR2021 dev boards (TX + RX)
- [ ] 2x ESP32-C3 UART bridges (for stable serial)
- [ ] USB cables (data + power)
- [ ] Laptop with PlatformIO + pyserial installed
- [ ] Portable USB battery (for TX board power)
- [ ] GPS phone app (for distance measurement)
- [ ] Antennas to test
- [ ] Notepad / spreadsheet for field notes

## Software Checklist

- [x] All firmware builds (17 envs)
- [x] test_runner.py (flash/capture/sweep/parse)
- [x] Bugs fixed (CR, RSSI/SNR, PER)
- [x] Mutex lock tool
- [ ] Create sweep config for range tests (distance parameter)

## Known Issues for Field Testing

1. **Direct USB ports swap on reboot** — Always use bridge ports (ACM1/ACM3) or verify board identity before each test.
2. **USB CDC dies during TX burst** — Can't send serial commands mid-transmission. Use "RUN" to trigger before burst starts.
3. **TX auto-starts after 8s countdown** — Have RX listening before countdown ends.
4. **RSSI saturates at close range** — Need >10m for meaningful RSSI vs power data.
5. **LoRa SF12 takes ~2 min per 200-packet test** — Budget time accordingly.
6. **picotool requires sudo** — Or use UF2 mass storage method (no sudo needed).

## Quick Commands

```bash
# Acquire/release boards
BALLOON_TRACK=speed-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both
BALLOON_TRACK=speed-tests python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release both

# Flash both boards
python3 tools/test_runner.py flash --tx rp2040-flrc-tx-2600 --rx rp2040-flrc-rx-2600

# Capture 20 seconds
python3 tools/test_runner.py capture --duration 20 -o results/distance-10m-flrc2600.txt

# Parse saved log
python3 tools/test_runner.py parse --file results/distance-10m-flrc2600.txt

# Run full sweep from config
python3 tools/test_runner.py sweep --config tools/sweep-config-flrc.json --output-dir results/
```
