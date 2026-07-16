# FLRC TX Throughput — Session Progress 2026-07-16

## Chip: LR2021 Gen 4 (Semtech SX1281 derivative)

**NOT LR10xx.** LR2021 is a 2.4 GHz FLRC/LoRa chip with SPI interface.
NiceRF LoRa2021 module, driven by RP2040 via SPI.

## Commit History (this session)

| Commit | Description | Result |
|--------|-------------|--------|
| a99b64c | Fs fallback + CALIBRATE 0x5F + simplified TX loop | 1294 kbps baseline |
| eee6147 | IRQ pin polling fix | 1000/1000 TX_DONE confirmed |
| 87b8599 | RF link working doc | 997/1000 RX, 1302.9 kbps |
| b7511b5 | Progress report doc | — |
| c80713a | Fast rfWaitBusy + remove spiDrain + analysis | Build OK |
| ce95dde | DMA TX firmware (subagent, Phase 3) | Build OK, untested |
| a423d6b | Direct HW SPI + 20MHz + register IRQ polling | Build OK, untested |
| 95e9ecf | CDC fix + SPI clock + FIFO pipelining | **CDC alive! TX_DONE=0/1000** |
| bd79ed3 | v4 pure Arduino SPI revert to proven baseline | Build OK, untested |

## What Works (proven, commit eee6147)
- TX_DONE: 1000/1000 (100%)
- TX throughput: 1293.6 kbps
- RF link confirmed (RX received 997/1000)
- Arduino SPI at 16MHz, sequential loop, IRQ pin poll

## What Broke (commit 95e9ecf)
Three regressions caused TX_DONE=0/1000:
1. **Preamble 16→8**: RX expects 16 symbols. Mismatch = no sync = no TX_DONE
2. **beginTransaction left open**: Arduino SPI internal state corrupted when
   rfReadStatus() also calls beginTransaction — nested/re-entrant calls break
3. **FIFO pipelining**: Skipped the proven CLR_IRQ→WRITE_FIFO→SET_TX sequence
   by priming first packet and overlapping commands. The overlap broke timing.

## What Works for CDC
- No `Serial.flush()` — blocks if no host has CDC port open
- Heartbeat loop during wait period (prints "WAIT 8", "WAIT 7"...)
- `spiRf.begin()` early, before radio init
- Reading `sio_hw->gpio_in` for IRQ poll is safe (GPIO read, no SPI conflict)

## Current Status (commit bd79ed3)
v4 is a clean rewrite that combines:
- Proven TX loop from eee6147 (sequential, IRQ poll)
- CDC fix from 95e9ecf (no flush, heartbeat)
- Pure Arduino SPI (no direct spi0_hw register access)
- 16MHz clock (proven, not 20MHz)
- Preamble=16 (matches RX)

**Build: OK. Hardware test: PENDING.**

## Next Steps
1. Flash v4 to 8332 (TX board) via ESP32 BOOTSEL one-shot
2. Read serial — verify WAIT heartbeats + TX_DONE count
3. If TX_DONE=1000: baseline confirmed. Measure throughput.
4. If throughput still ~1294 kbps: optimize ONE thing at a time:
   a. 16MHz → 20MHz SPI (measure delta)
   b. Remove per-packet CLR_ERR (not in proven baseline)
   c. Reduce delays between SPI commands
   d. Try FIFO pipelining WITH correct preamble + proper begin/end
5. Commit + push after each tested change
6. Update this doc with results

## Hardware Setup
- TX: RP2040 serial E663B035973B8332 (/dev/ttyACM0, PID 000a)
- RX: RP2040 serial E663B035977F242D (/dev/ttyACM2, PID 000a)
- ESP32 #1: serial 70:AF:09:13:21:00 (/dev/ttyACM1) — BOOTSEL controller
- ESP32 #2: serial 70:AF:09:21:FB:18 (/dev/ttyACM3) — BOOTSEL controller
- All 4 boards connected via USB hub

## Pin Mapping (RP2040 → LR2021)
```
GP2  = SCK
GP3  = MOSI
GP4  = MISO
GP5  = CS (NSS)
GP6  = BUSY
GP7  = IRQ (DIO9)
GP8  = RST
GP12 = UART TX (debug)
GP13 = UART RX (debug)
GP25 = LED
GP16 = LED ALT
```