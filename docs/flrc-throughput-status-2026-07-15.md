# FLRC Throughput Status — 2026-07-15 (final update)

## Current Blocker: RadioLib beginFLRC() returns -707

**Error code -707 = RADIOLIB_ERR_SPI_CMD_FAILED**

The LR2021 chip's status byte reports CMD_FAIL after an SPI command.
RadioLib's `SPIparseStatus()` checks bits 3:1 of the status byte:
- `0b000` = CMD_FAIL → returns -707
- `0b010` = CMD_PERR → returns -706
- 0x00 or 0xFF → CHIP_NOT_FOUND (-711)

### Root cause (from RadioLib source analysis)

LR2021.h explicitly states:
> "If you are seeing -706/-707 error codes, it likely means you are using
> non-0 value for module with XTAL. To use XTAL, either set this value to 0,
> or set LR2021::XTAL to true."

Our firmware already passes `tcxoVoltage=0.0f`. So either:
1. The firmware needs `LR2021::XTAL = true` explicitly set
2. SPI communication is broken (chip not responding to getVersion())
3. Hardware issue: RST/BUSY/SPI wiring problem on the carrier board

### What was verified

Sent INIT command to RP2040 via UART bridge:
- `beginFLRC code: -707` — radio init fails
- Radio status: NOT_INIT
- All other config correct (freq=2440, BR=2600, CR=uncoded, pins match)

## Hardware Setup (verified)

### Boards
| Board | Serial | USB Port | Role |
|-------|--------|----------|------|
| RP2040-Zero #1 | E663B035973B8332 | ACM0 | RX (8332) |
| RP2040-Zero #2 | E663B035977F242D | ACM2 | TX (F242D) |
| ESP32-C3 SuperMini #1 | 70:AF:09:13:21:00 | ACM1 | UART bridge for 8332 |
| ESP32-C3 SuperMini #2 | 70:AF:09:21:FB:18 | ACM3 | UART bridge for F242D |

### UART bridge wiring (VERIFIED BIDIRECTIONAL)
```
RP2040 GP12 (UART0 TX) ──→ ESP32 GPIO3 (UART1 RX)
RP2040 GP13 (UART0 RX) ←── ESP32 GPIO2 (UART1 TX)
GND ───────────────────── GND
```
Bridge firmware: `Serial1.begin(115200, SERIAL_8N1, GPIO_NUM_3, GPIO_NUM_2)`

### LR2021 SPI wiring (RP2040 pins.h)
```
GP2 = SPI0 SCK → LR2021 Pin 5
GP3 = SPI0 MOSI → LR2021 Pin 4
GP4 = SPI0 MISO ← LR2021 Pin 3
GP5 = SPI CS → LR2021 Pin 6 (NSS)
GP6 = BUSY ← LR2021 Pin 7
GP7 = IRQ ← LR2021 Pin 15 (DIO9)
GP8 = RST → LR2021 Pin 14
```

## Firmware Status

All source files committed and pushed. Both TX and RX build clean.

| File | Env | Status |
|------|-----|--------|
| flrc_tx_raw.cpp | rp2040-flrc-tx-raw | Builds OK, radio init untested (USB CDC dies) |
| flrc_rx_main.cpp | rp2040-flrc-rx | Builds OK, radio init fails (-707) |
| flrc_rx_raw.cpp | rp2040-flrc-rx-raw | Builds OK, deprecated (no RadioLib) |
| esp32-uart-bridge/main.cpp | — | Working, bidirectional verified |

### TX/RX config comparison (IDENTICAL)
Both use the same RadioLib beginFLRC() call:
- Freq: 2440.0 MHz
- Bit rate: 2600 kbps
- Coding rate: CR_1_0 (uncoded)
- TX power: 22 dBm
- Preamble: 16
- BT shaping: 0.5
- TCXO: 0.0V (crystal)
- Packet size: 255 bytes (fixed)
- SPI: 16 MHz
- IRQ: DIO9

No config mismatch between TX and RX.

## What works
- 1200 baud BOOTSEL trigger on both RP2040s (fully autonomous, no physical access)
- UART bridge: bidirectional RP2040↔ESP32 communication
- PlatformIO builds for all environments
- Serial1 (UART0 on GP12/GP13) survives RadioLib SPI traffic
- Bridge forwards commands (CONFIG, INIT) from PC to RP2040

## What doesn't work
- RadioLib beginFLRC() fails with -707 on RX board (8332)
- TX board (F242D) USB CDC dies after boot (expected), radio status unknown
- 0 packets received in any test run
- ACM3 bridge doesn't see RP2040 UART data from F242D

## Next steps to debug -707

1. Try `LR2021::XTAL = true` before beginFLRC() — forces XTAL mode explicitly
2. Add raw SPI diagnostic: read GET_STATUS (0x0100) before beginFLRC() to check if chip responds at all
3. Check if firmware version matches expected 1.18 (findChip() requirement)
4. Toggle RST pin (GP8) LOW→HIGH with delay before beginFLRC()
5. Lower SPI clock from 16 MHz to 8 MHz to rule out signal integrity
6. If chip returns 0x00/0xFF on status → CHIP_NOT_FOUND, check wiring continuity

## Git log (last 5 commits)
```
4bb3c7b docs: honest UART bridge pin verification report
1cb0bbf fix: UART bridge GPIO3(RX)/GPIO4(TX) VERIFIED — RP2040 data flowing
35fffb0 fix: ESP32 UART bridge uses GPIO3(RX)/GPIO4(TX) — matches actual wiring
39e3366 feat: ESP32 flash recovery targets + GPIO swap fix + skill update
b1d968a feat(firmware): add esp-recover make target for corrupted ESP32 flash
```
