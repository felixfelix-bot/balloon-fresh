# FLRC Throughput Debugging Progress

## Goal
2600 kbps (2.6 Mbps) throughput between two RP2040 + LR2021 boards.

## Hardware
- Board 8332 (serial E663B035973B8332): RX board
- Board F242D (serial E663B035977F242D): TX board
- Each RP2040 has paired ESP32-C3 for BOOTSEL control + UART bridge
- LR2021 radio on 2.4 GHz FLRC mode

## Previous Achievement (2026-07-13)
- TX throughput measured: 3283 kbps (exceeds 2600 target)
- Used RadioLib beginFLRC() — killed USB CDC on RP2040 (known bug)

## Current Session (2026-07-15)

### Root Cause: Frequency Overflow Bug (FIXED)
Raw SPI init divided freq by step_size (0.00390625):
```
rfFreq = 2440e6 / 0.00390625 = 624,640,000,000  ← OVERFLOWS uint32_t
```
Radio tuned to garbage frequency → CMD_ERROR (IRQ=0x00230000) → 0 packets.

**Fix:** Send freq_Hz directly (radio does internal conversion):
```
rfFreq = (uint32_t)(FLRC_FREQ_HZ * 1000000.0f) = 2440000000
```

### Additional Fixes Applied
1. Added Rx/Tx fallback mode STBY_RC (0x0206) — RadioLib config() does this
2. Reset wait increased 10ms → 50ms (crystal stabilization)
3. Created flrc_tx_raw.cpp — identical radio config as RX
4. Same sync word {0x12, 0xAD, 0x10, 0x1B} in both TX and RX

### Commits
- `0392713` feat: UART bridge + RX dual-output firmware
- `b9f9c93` feat: raw SPI TX+RX firmware, no RadioLib dependency
- `7018730` fix: 4 critical bugs in raw SPI FLRC firmware
- `68e98c9` fix: raw SPI FLRC init bugs 5-8 + DIO/IRQ config corrections

### Still 0 Packets
After all fixes, TX transmits but RX still receives 0. Suspects:
1. USB port chaos — ACM numbers swap on every reboot
2. TX raw SPI may not actually transmit (USB CDC dies, can't verify)
3. IRQ config may be wrong for TX mode (bit 19 TX_DONE vs bit 18 RX_DONE)

### Next Steps
1. Make TX wait for "RUN" command (like RX) instead of auto-transmitting
2. Add status read after init to verify radio actually initialized
3. Verify TX_DONE IRQ fires during transmission
4. Consider using RadioLib on TX (USB death doesn't matter for TX — throughput is deterministic)

## Remote BOOTSEL Workflow (PROVEN WORKING)
No physical access needed:
1. Flash one-shot BOOTSEL trigger to paired ESP32 (`esp32-bootsel-oneshot` env)
2. ESP32 pulls GPIO1 (RESET) + GPIO8 (BOOTSEL) → RP2040 enters BOOTSEL
3. Mount RPI-RP2, copy UF2, unmount
4. RP2040 reboots with new firmware
5. Re-flash ESP32 as UART bridge if needed

## Build/Flash Commands
```bash
cd ~/repos/balloon-fresh/firmware/rp2040
pio run -e rp2040-flrc-rx-raw
pio run -e rp2040-flrc-tx-raw

# Flash RX (8332): trigger via ESP32 on ACM1
pio run -e esp32-bootsel-oneshot -t upload --upload-port /dev/ttyACM1
# Then mount + copy UF2

# Flash TX (F242D): trigger via ESP32 on ACM3
pio run -e esp32-bootsel-oneshot -t upload --upload-port /dev/ttyACM3
# Then mount + copy UF2
```
