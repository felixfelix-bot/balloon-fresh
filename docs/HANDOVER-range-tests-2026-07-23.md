# Handover: Range Tests — 2026-07-23

## Context for Next Session

You are continuing work on LR2021 FLRC range testing for a pico balloon tracker project.
Two RP2040+LR2021 boards on a desktop breadboard. The critical bug (FIFO race) is solved.
Power characterization is done. Next phase is outdoor range testing.

## What Just Happened

### Bug Fix (commit 3dcddaf)
RX IRQ polling switched from SPI to GPIO. This was the root cause of 8+ sessions
of sequence number corruption. Full details in `docs/lr2021-complete-learnings-2026-07-23.md`.

### Power Sweep (commit 5b439f3)
Swept 6 power levels (0, 3, 6, 9, 12, 12.5 dBm). Finding: LR2021 PA is binary.
Codes 0-24 bypass PA (identical ~4% PER). Code 25 enables PA (~0% PER). Raw data
in `tests/raw-captures/`. Summary in `tests/power-sweep-v2-results.md`.

### Board Lock
Released. Both boards free.

## Current Git State
- Branch: `range-tests`
- Last commit: `5b439f3`
- Pushed to: ngit + GitHub (felixfelix-bot/balloon-fresh)
- Working tree: clean (about to commit this documentation)

## Firmware State

### TX: flrc_range_tx_auto.cpp
- Auto-burst: 500 packets, 2s pause, repeat
- Configurable via build flags: TX_POWER_DBM, TX_BITRATE_KBPS, TX_FREQ_MHZ, TX_PKT_SIZE
- 6 power envs built: rp2040-range-tx-p0 through p125
- 3 bitrate envs: 2600 (default), 1300, 650 kbps

### RX: flrc_raw_rx.cpp
- Continuous RX with 12s windows (auto re-arm)
- GPIO IRQ polling (fixed)
- DEADBEEF end marker detection for TX count
- Hex dump debug mode (RX_DEBUG_HEX flag)
- 2 envs: rp2040-raw-rx-127 (20MHz), rp2040-raw-rx-debug (10MHz + hex dump)

### Board Recovery
If a board's USB CDC port disappears (radio init hang):
1. Try 1200 baud serial trigger
2. If that fails, flash ESP32 loop trigger to paired ESP32 (ACM1 or ACM3)
3. ESP32 pulses RUN pin every 5s → board enters BOOTSEL

## What Needs to Happen Next

### Priority 1: Outdoor Range Test
All testing so far was at ~30cm on a desk. Need real distances:
- 10m, 50m, 100m+ line of sight
- TX on battery (power bank), RX on laptop
- Test at 12.5 dBm (PA on) primarily
- Capture PER at each distance

### Priority 2: RSSI Fix
Register 0x022A always returns -127 dBm. Without RSSI, range characterization
is incomplete (can't build link budget from measurement). Possible approaches:
- Different register address for FLRC mode
- Read during RX (not after packet received)
- Use GET_RX_BUFFER_STATUS or packet status commands

### Priority 3: Lower Bitrate Range Test
1300 and 650 kbps envs are built but untested. Lower bitrate = more processing
gain = better sensitivity. May significantly extend range.

### Priority 4: CRC Investigation
The ~4% PER at non-PA power levels is consistent. Need to determine if packets
are truly lost (not received) or corrupted (received but bad). Enabling CRC
would distinguish these cases.

## Key Files
```
firmware/rp2040/src/flrc_range_tx_auto.cpp   — TX firmware
firmware/rp2040/src/flrc_raw_rx.cpp          — RX firmware (FIXED)
firmware/rp2040/platformio.ini               — all build envs
tests/power-sweep-v2-results.md              — sweep summary
tests/raw-captures/                           — raw serial captures
docs/lr2021-complete-learnings-2026-07-23.md  — all technical learnings
docs/STATUS-balloon-range-tests.md           — quick status
```

## Reasoning Prompts for Next Session

1. "The RSSI register 0x022A returns -127 dBm always. The Semtech LR2021
   datasheet may reference RSSI at a different address for FLRC mode. What
   register sequence reads valid RSSI for FLRC packets?"

2. "At 1300 kbps, processing gain should double vs 2600 kbps. Test this by
   flashing the 1300 kbps envs and comparing PER at the same power/distance."

3. "The consistent 4% PER at non-PA power may be from indoor multipath or
   from FIFO read timing. Enable CRC in the modem config to distinguish
   corrupted packets from truly lost packets."

4. "For outdoor range testing, the TX needs battery power and the RX needs
   to log data. Can we log to the RP2040 flash, or relay through the ESP32
   to a phone?"
