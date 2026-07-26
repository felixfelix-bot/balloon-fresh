# Morning Handover — V4 Walk Test Ready

**Date:** 2025-07-25
**Commit:** b4636a8 (pushed to GitHub)
**Boards:** TX (F242D) + RX (8332) both running V4 firmware

---

## WHAT'S READY

Both boards flashed with V4 firmware. 255-byte packets verified:
- LF-LoRa-SF12 255B: 5/10 pkts, 50% PER, -26 dBm, zero CRC errors
- HF-LoRa-SF12 255B: 3/15 pkts, 80% PER, -121 dBm, zero CRC errors

CRC pass = content verified bit-for-bit. Zero false positives.

## TWO WALK OPTIONS

### OPTION A — Base Mode (recommended, simplest)
All 14 modes at 255B. One walk = full characterization.

1. Plug in both boards
2. Flash V4 (already done, but reflash if power was lost)
3. SET_TIME both boards simultaneously
4. Run: `~/worktrees/balloon-range-tests/tools/walk-capture.sh /dev/ttyACM4 600`
5. Walk with TX board + GPS module + battery

### OPTION B — Interleave Mode (comprehensive, 4 sizes)
56 phases: 14 modes × 4 sizes (32/64/128/255B). One walk = size tradeoff map.

1. Flash V4 (same firmware)
2. Send: `SET_INTERLEAVE 1` to both boards
3. SET_TIME both boards
4. Run walk-capture.sh
5. Walk — cycle takes ~400s (6.5 min)

## TIME SYNC — NO DRIFT

- TX: uses GPS time (auto-updates from $GNRMC)
- RX: laptop sends SET_TIME every 10 seconds during walk (walk-capture.sh does this)
- No bidirectional RF sync needed
- No drift possible

## WHAT INTERLEAVE MEANS

NOT: one packet from test A, one from B, one from C
IS: run ALL packets for combo A, then ALL for combo B, then C, etc.

Example: HF-LoRa-SF7 runs at 32B (8s), then 64B (8s), then 128B (8s), then 255B (15s).
Then next radio mode. Sequential, not packet-by-packet mixing.

## FILES

- Firmware: firmware/rp2040/src/multi_radio_sweep_{gps,rx}_v4.cpp
- Docs: docs/V4-WALK-TEST-QA.md, docs/V4-DYNAMIC-PKTSIZE-SWEEP-PLAN.md
- Capture: tools/walk-capture.sh
- Plots: scripts/plot_v4_interleave.py

## AT THE DOOR

```bash
# 1. Verify boards are running V4
echo "FW_QUERY" > /dev/ttyACM2  # TX
echo "FW_QUERY" > /dev/ttyACM4  # RX
# Look for "v4" in output

# 2. For base mode (recommended):
# Both boards already in default mode (255B, 14 phases)

# For interleave mode:
printf "SET_INTERLEAVE 1\n" > /dev/ttyACM2
printf "SET_INTERLEAVE 1\n" > /dev/ttyACM4

# 3. Sync both boards
NOW=$(date +%s)
printf "SET_TIME %s\n" "$NOW" > /dev/ttyACM2
printf "SET_TIME %s\n" "$NOW" > /dev/ttyACM4

# 4. Start capture (walk-capture.sh handles re-sync)
~/worktrees/balloon-range-tests/tools/walk-capture.sh /dev/ttyACM4 600

# 5. Walk! TX board goes in rucksack with GPS + battery
```
