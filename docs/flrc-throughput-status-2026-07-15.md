# FLRC Throughput Status — 2026-07-15

## CRITICAL: Lost Source Files

These files achieved 1546 kbps but were NEVER committed to git. They are LOST:

| File | Achievement | Status |
|------|-------------|--------|
| tx_fast.cpp | 393 kbps, USB-stable, 30s verified | **LOST** — never committed |
| tx_overlap.cpp | 1546 kbps (best), double-buffered | **LOST** — never committed |
| rx_fast.cpp | 758 pkts/s RX, DIO9 polling | **LOST** — never committed |
| rx_ab_b.cpp | 2-txn RX variant | **LOST** — never committed |

### How to recreate (from skill documentation)

**tx_fast.cpp**: RadioLib-based TX. Standard beginFLRC(), then loop:
- Write TX FIFO (255 bytes), SET_TX, wait BUSY LOW, yield()
- 800 pkts/s, USB CDC stable
- Key: yield() per-packet, NOT per-heartbeat

**tx_overlap.cpp**: Double-buffered TX for maximum speed.
- While radio transmits packet N, pre-load FIFO for packet N+1
- Uses raw SPI for FIFO write, RadioLib for SET_TX
- 800+ pkts/s, ~1546 kbps
- USB CDC DIES (Mode A boot-time death on mbed core)
- Yield-in-wait fix merged (commit 80a4894) but unverified

**rx_fast.cpp**: RadioLib init + raw SPI hot loop.
- beginFLRC() for init (convenience), then raw SPI for receive
- Poll DIO9 pin (not IRQ status register)
- Per-packet: READ_FIFO → CLEAR_IRQ → SET_RX (3 SPI transactions)
- 758 pkts/s catch rate at 18 MHz SPI
- USB CDC stable on RX side (plenty idle CPU)

## What We Have NOW (committed + pushed)

### RP2040 RX: flrc_rx_raw.cpp ✅ WORKING
- Raw SPI init (12-step paced sequence, no RadioLib)
- Radio reports READY, status 0x03/0x05
- USB CDC survives (no Mode A death)
- Serial commands: RUN, CONFIG, INIT, RESULTS, HELP
- Dual output: USB Serial + UART GP12/GP13
- Path: firmware/rp2040/src/flrc_rx_raw.cpp
- Build: `pio run -e rp2040-flrc-rx-raw`
- Flash: `make rp2040-flash ENV=rp2040-flrc-rx-raw PORT=/dev/ttyACM0`

### ESP32 TX: fifo_tx.cpp ⚠️ UNTESTED
- ESP-IDF + RadioLib, CONFIG_BENCH_MODE_FIFO_TX
- Pin config matches hardware wiring (verified)
- Freq 2440 MHz, BR 2600, CR_1_0
- Uses raw SPI for FIFO write (gpio level, not RadioLib SPI)
- Path: mesh-stack/flrc-bench-espidf/main/fifo_tx.cpp
- Build: `source ~/esp/esp-idf/export.sh && idf.py build`
- Flash: `python -m esptool --chip esp32c3 -p /dev/ttyACM3 write_flash ...`

### RP2040 TX: rp2040-flrc-max/main.cpp ✅ BUILT (untested with new RX)
- RadioLib-based, achieved 3283 kbps TX-only (Jul 13)
- Uses RadioLib beginFLRC() — USB dies (Mode A)
- Could be used as TX if we flash via 1200 baud and read results from RX side only

## Current Blocker: 0 Packets Received

Both boards initialize correctly but no packets flow TX→RX.

### Likely cause: Sync word mismatch
- ESP32 TX uses RadioLib default sync word
- RP2040 raw SPI RX doesn't explicitly set sync word
- LR2021 default sync word may differ from RadioLib default

### Next steps to debug:
1. Check RadioLib default FLRC sync word (in LR2021 source)
2. Add sync word set command to raw SPI init sequence
3. Verify preamble length matches (ESP32=? vs RP2040=12)
4. Test with both boards at close range

## Architecture

```
ESP32-C3 (TX)                    RP2040 (RX)
fifo_tx.cpp                      flrc_rx_raw.cpp
  RadioLib beginFLRC()             Raw SPI init (12 steps, paced)
  Raw SPI FIFO write               Poll DIO9 → READ_FIFO → CLR_IRQ → SET_RX
  2440 MHz, 2600 kbps, CR_1_0     2440 MHz, 2600 kbps, CR_1_0
  LR2021 module                    LR2021 module
         |                              |
         +---- 2.4 GHz FLRC link -------+
```

## Preventing Future Data Loss

1. **ALL source files MUST be committed immediately after creation**
2. Use `write_file` tool (not /tmp heredocs) — creates in repo tree
3. Commit after every build success, not just at session end
4. Push to ngit after every commit
5. Session-notes.md tracks current state across resets
