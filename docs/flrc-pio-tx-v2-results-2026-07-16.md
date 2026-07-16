# FLRC PIO TX v2 — CDC-Safe Hybrid Init Results

**Date:** 2026-07-16
**Commit:** ea0aead (firmware), this doc pending commit
**Firmware:** `flrc_pio_tx_v2.cpp` — hybrid Arduino SPI init + PIO+DMA TX hot loop

## Architecture

V2 solves the v1 problem (CDC dies on PIO init) by splitting init into two phases:

1. **Phase 1 (Arduino SPI):** Radio init via standard `spiRf.begin()` + Arduino `transfer()` calls
   - CDC stays alive because Arduino core manages USB TinyUSB stack
   - All LR2021 radio config commands sent through safe Arduino SPI
   - Radio fully configured before PIO touches anything

2. **Phase 2 (PIO+DMA):** After 8-second WAIT window (CDC confirmed alive):
   - `spiRf.end()` releases Arduino SPI peripheral
   - PIO state machine + DMA initialized on same SPI pins
   - TX hot loop uses PIO+DMA for SPI transfers at 20.83 MHz
   - IRQ pin polled for TX_DONE

## What Works

- Arduino SPI radio init → CDC alive ✓
- 8-second WAIT window → CDC output confirmed ✓
- `spiRf.end()` → releases Arduino SPI cleanly ✓
- PIO+DMA init AFTER CDC established → "PIO INIT OK" printed on USB CDC ✓
- TX loop starts → "TX_START count=1000" printed ✓
- Board survives TX loop (USB PID 0x000a, not crashed) ✓

## What Breaks

**CDC output DIES during PIO TX loop.** No PKT/spin/throughput results appear on serial.

After "TX_START count=1000" prints, the board continues running (USB device stays connected) but no further serial output appears. The TX loop executes (board doesn't crash) but CDC is dead for the duration.

## Root Cause Analysis

The PIO+DMA TX loop steals the SPI peripheral from the Arduino core. This likely also interferes with the TinyUSB CDC stack because:

1. **PIO claims GPIO pins** — the SPI pins (GP2,3,4,6) are reassigned to PIO state machine, breaking any Arduino core polling of those pins
2. **DMA channel busy** — DMA transfers block CPU access to SPI FIFO, preventing TinyUSB from servicing USB interrupts that share DMA infrastructure
3. **Tight TX loop** — no `yield()` or TinyUSB poll in the hot loop, so CDC buffer never flushes
4. **Arduino core USB stack** — earlephilhower core runs TinyUSB in `loop()` yield — but the TX function runs in `setup()` before `loop()` is ever called

## Key Learnings

1. **PIO steals GPIO from Arduino core** — once PIO claims pins, Arduino SPI is dead. Cannot mix PIO SPI and Arduino SPI on same pins without re-claiming.

2. **CDC needs TinyUSB polling** — USB CDC output requires the TinyUSB stack to be serviced regularly. In a tight TX loop with no yield, CDC buffer fills and output is lost.

3. **Hybrid init works but hybrid runtime doesn't** — using Arduino SPI for init then PIO for TX is valid for initialization, but the transition breaks CDC output for the TX duration.

4. **Board doesn't crash** — USB device stays enumerated (PID 0x000a). CDC just stops outputting. Data may be in the CDC buffer but never flushed.

## Possible Fixes (Future Work)

1. **Add `Serial.flush()` after each packet** — force CDC buffer drain. Risk: `Serial.flush()` is blocking, may add latency.
2. **Use Serial1 (UART) for TX loop output** — bypass CDC entirely, output via hardware UART on GP0/GP1. Requires USB-UART bridge to read.
3. **Add `yield()` in TX loop** — let Arduino core service TinyUSB. Risk: may break PIO timing.
4. **Print results AFTER TX loop completes** — buffer all results in memory, print after PIO is stopped and Arduino SPI is restored. Simplest fix.
5. **Use IRQ-based TX_DONE** instead of polling — frees CPU to service CDC between packets.

## Test Results

- TX_DONE count: **UNKNOWN** (CDC died before results printed)
- Throughput: **UNKNOWN** (CDC died before results printed)
- Board survival: ✓ (USB stayed connected)
- Radio init: ✓ (Arduino SPI confirmed working)
- PIO init: ✓ ("PIO INIT OK" printed)

## Comparison Across All TX Firmware

| Firmware | SPI Method | TX_DONE | Throughput | CDC | Notes |
|----------|-----------|---------|-----------|-----|-------|
| v4 baseline | Arduino per-byte 16MHz | 1000/1000 | 1367 kbps | ✓ | PROVEN ceiling |
| PIO v1 | PIO+DMA 20.83MHz all-in | 1000/1000 | 1377 kbps | ✗ | CDC dies on init, results via stty |
| PIO v2 hybrid | Arduino init + PIO TX | UNKNOWN | UNKNOWN | ✗† | CDC dies during TX loop, not init |
| Pipe | Arduino + FIFO pipeline | 1000/1000 | 2943 kbps** | ✓ | **FAKE — exceeds air rate, 0 RX |

† CDC alive during init, dies during TX loop
** Fake result: TX_DONE firing before packet complete

## Next Steps

1. **Fix v2 CDC** — add deferred results printing (fix #4 above), or use Serial1 UART
2. **Reflash + test** — capture actual TX_DONE count + throughput
3. **RX verification** — run simultaneous TX+RX to confirm real packets
4. **If PIO v2 throughput still ~1377 kbps** — confirms SPI is NOT the bottleneck, air time dominates
5. **Document final conclusion** — 1367 kbps is the ceiling, optimization exhausted

## Flash Method That Works

```bash
# Force BOOTSEL from USB CDC mode using picotool
PICOTOOL=~/.platformio/packages/tool-picotool-rp2040-earlephilhower/picotool
sudo $PICOTOOL reboot -u -f --ser E663B035973B8332   # TX board
sleep 2
# Board appears as mass storage — copy UF2
sudo mount /dev/sdX1 /mnt
sudo cp .pio/build/rp2040-pio-tx-v2/firmware.uf2 /mnt/
sync
sudo umount /mnt
# Board auto-reboots with new firmware
```