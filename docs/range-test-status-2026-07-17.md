# Range Testing Track — Status & Infrastructure Review

**Date:** 2026-07-17
**Worktree:** ~/worktrees/track-range-testing (branch: track/range-testing)
**Author:** Range testing agent (Hermes)

---

## What Exists — Infrastructure

### Mutex Lock

**Tool:** `~/repos/balloon-fresh/tools/balloon-board-lock.py`
- File-based locks in `~/.hermes/peripheral_locks/balloon-{tx,rx}.lock`
- `BALLOON_TRACK=range-test` identifies our session
- 15-min stale timeout auto-release
- Per-board locks: TX and RX are independent (can hold one while speed track holds the other)
- **MANDATORY**: Acquire before ANY board operation, release immediately after

```
export BALLOON_TRACK=range-test
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire both \
    --purpose "range test: baseline verification" --timeout 120
# ... do work ...
python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release both
```

### Hardware

Two RP2040 Pico + NiceRF LoRa2021 (Semtech LR2021 Gen 4) combos:

| Role | Serial | Board ID | Current Port |
|------|--------|----------|-------------|
| TX | E663B035977F242D | F242D | /dev/ttyACM0 |
| RX | E663B035973B8332 | 8332 | /dev/ttyACM3 |

Port assignments SWAP after every BOOTSEL flash. Always re-discover:
```
for d in /dev/ttyACM*; do echo -n "$d: "; udevadm info -q property "$d" | grep ID_SERIAL_SHORT; done
```

### Firmware (17 PlatformIO envs, 4 relevant to range testing)

| Env | Source File | Description | Status |
|-----|-----------|-------------|--------|
| rp2040-raw-tx | flrc_raw_tx.cpp | CANONICAL TX (pure raw SPI, +12 dBm, 255 bytes) | Working |
| rp2040-raw-rx | flrc_raw_rx.cpp | CANONICAL RX (0% loss) | Working |
| rp2040-flrc-tx-raw | flrc_tx_raw.cpp | RadioLib init + raw SPI hot loop | Has PWR=22 (invalid for 2.4GHz) |
| rp2040-flrc-rx-raw | flrc_rx_raw.cpp | RadioLib-based RX | Working |

Additional envs exist from speed track experiments (DMA, PIO, timing profiler, sweep, batch, pipe) — not relevant to range testing.

### Test Harness

**Script:** `scripts/coordinated_tx_rx_test.py`
- Arms RX first (2s head start), triggers TX, captures both serial ports for 15s
- Saves results to `/tmp/coordinated_results.txt`
- Uses serial substring matching ("8332"/"F242D") — works but fragile

---

## What Worked — Proven Results

### End-to-End RF Link (2026-07-16)

| Metric | Value |
|--------|-------|
| Throughput | 1377 kbps |
| TX_DONE | 1000/1000 (100%) |
| RX packet loss | 0% (1000 unique received) |
| Frequency | 2440 MHz |
| Modulation | FLRC 2600 kbps, CR=1/0 (uncoded) |
| BT shaping | 0.5 |
| Packet size | 255 bytes |
| TX power | +12 dBm |
| Sync word | 0x12AD101B (both boards matched) |
| Preamble | 16 bits |
| SPI clock | 16 MHz (Arduino per-byte transfer) |

All verified at bench distance (centimeters). Real packets over real radio — not simulated.

### Key Fixes That Made It Work

1. **IRQ pin polling fix** (commit eee6147): BUSY-pin based TX completion detection → 1000/1000 TX_DONE
2. **CDC DTR fix**: `delay(2000)` in firmware or pyserial `dtr=True` for TinyUSB enumeration
3. **earlephilhower core** mandatory — Mbed core produces zero USB CDC output
4. **yield() in tight loops** — without it TinyUSB starves and USB CDC dies
5. **1200 baud BOOTSEL trigger** — reliable method for board reflashing

---

## What Didn't Work — Dead Ends (from speed/throughput track)

| Approach | Result | Root Cause |
|----------|--------|------------|
| Pico SDK spi_write_blocking() | Fake TX_DONE, 0 RX | Batch FIFO incompatible with LR2021 timing |
| DMA via spi0_hw->dr | Radio init fails entirely | Bypasses Arduino SPI transaction protocol |
| Direct HW SPI tight loop | No transmission | Same as above |
| Runtime SPI clock change | Kills radio | SPI peripheral teardown breaks LR2021 sync |
| PIO state machine TX (v1/v2/v3) | USB CDC death every time | DMA_IRQ_0 starves USB IRQ |
| 20 MHz RX SPI | 77% packet loss | RX FIFO read timing requires slower SPI |
| RADIOLIB_GODMODE on RX | Silently corrupts radio config | Undocumented side effects |

**Bottom line:** Arduino per-byte `SPI.transfer()` at 16 MHz is the ONLY reliable SPI method on RP2040 with LR2021.

---

## What We Learned

### RF/Radio Knowledge

1. **All testing = bench distance.** ZERO outdoor range data exists. Every distance data point will be new.
2. **LR2021 has native FIFO API** (readRadioRxFifo, getRxFifoLevel, configFifoIrq, autoTxRx) — accessible via RADIOLIB_GODMODE on TX side only (breaks RX).
3. **572µs blind window** in RX processing — packets arriving during FIFO read can be missed.
4. **FLRC has no spreading gain** like LoRa. Shorter packets = lower collision probability, not better sensitivity.
5. **LR2021 is NOT SX1280** — different chip, different architecture, different FIFO model.
6. **Power limits:** 2.4 GHz = -19 to +12 dBm max. Sub-GHz = -9 to +22 dBm.

### Firmware/Platform Knowledge

7. **SPI clock = compile-time only.** Changing it at runtime kills the radio.
8. **RX must stay at 16 MHz SPI.** 20 MHz causes 77% packet loss.
9. **No RSSI readback firmware exists yet** — would be valuable for range characterization.
10. **Board serials differ between BOOTSEL and application mode** — use USB sysfs path for reliable identification.

---

## What Still Needs Doing

### Priority 1: Baseline + Configurable Firmware

1. **Verify baseline** — Reflash both boards, run coordinated test at 1m, confirm 0% loss still holds
2. **Write configurable TX firmware** — Accept serial commands (POWER, PKTLEN, FREQ, COUNT, RUN) to avoid reflashing between every test point. This is the highest-value firmware to write.

### Priority 2: Distance Sweep (Primary Data)

3. **Outdoor LOS distance sweep**: 10m, 25m, 50m, 100m
   - Fix TX at waist height, antenna vertical
   - 1000-packet burst at each distance
   - Record: packets received, packet loss %, RSSI if available
   - Mark distance where loss exceeds 1%, 5%, 10%, 50%

### Priority 3: Parameter Sweeps

4. **TX power sweep**: 0, 3, 6, 9, 12, 12.5 dBm at fixed distance (50m)
5. **Packet size sweep**: 16, 32, 64, 128, 255 bytes at fixed distance
6. **Modulation comparison**: FLRC 2600/1300/650/325 kbps vs LoRa SF5/SF7/SF12 at 100m
7. **Antenna testing**: PCB trace vs wire dipole, polarization mismatch, rotation simulation
8. **Frequency sweep**: 2400, 2412, 2422, 2440, 2462, 2480 MHz (WiFi interference mapping)

### Priority 4: Advanced

9. **RSSI readback firmware** — Read RSSI from LR2021 for range characterization
10. **Mobile/flight conditions** — Moving RX, elevated TX, rotating antenna, temperature effects

---

## Data Recording Format

Every test result recorded as:
```
RANGE_TEST,date=YYYY-MM-DD,distance_m=X,power_dbm=Y,pkt_size=Z,\
mode=FLRC2600,freq_mhz=2440,antenna=TYPE,orientation=ORIENT,\
packets_sent=N,packets_rx=M,loss_pct=P,throughput_kbps=K,notes=ENV
```

Save to: `docs/range-test-results-2026-07-XX.md`
