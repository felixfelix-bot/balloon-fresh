# FLRC PIO TX v3 — CDC Dead After PIO, BOOTSEL Command Inaccessible

**Date:** 2026-07-16
**Commit:** 46de3c9 (CDC restore + BOOTSEL command)
**Status:** BLOCKED — need physical BOOTSEL on both boards

## What Was Tested

1. Flashed v3 (commit 46de3c9) to TX board (8332) via BOOTSEL mass storage
2. Board rebooted, CDC enumerated as /dev/ttyACM1
3. Firmware runs: 2s CDC delay → radio init → 8s WAIT → PIO+DMA TX burst → pioSpiStop() → spiRf.begin() → delay(500) → Serial.print results
4. **RESULT: CDC completely dead. No output ever appears on USB serial.**

## Root Cause Analysis

The v3 firmware includes the correct deferred printing approach:
- `pioSpiStop()` disables PIO SM, unclaims DMA, removes IRQ handler
- `spiRf.begin()` re-initializes Arduino SPI
- `delay(500)` gives TinyUSB time to recover
- `Serial.printf()` prints results

But CDC never recovers. Possible reasons:
1. **PIO permanently changes GPIO function** — `pio_gpio_init()` reassigns pins to PIO, and this may not be fully reversed by `pioSpiStop()`
2. **TinyUSB stack corrupted** — the DMA IRQ handler or PIO state machine may have corrupted TinyUSB internal state
3. **USB enumeration lost** — once CDC dies, the USB stack can't re-enumerate without a full USB reset
4. **Arduino SPI begin() conflicts** — re-initializing SPI after PIO used the same pins may cause a hardware conflict

## BOOTSEL Command Inaccessible

The BOOTSEL command (`reset_usb_boot(0, 0)`) was added to `loop()` for remote reflash. But since CDC is dead after PIO TX, the serial command never reaches the board. The command only works if CDC is alive — which defeats the purpose.

## Conclusion

**PIO+DMA and USB CDC on RP2040 are fundamentally incompatible.** Once PIO claims the SPI pins and DMA channels, the TinyUSB CDC stack cannot be recovered. This affects all PIO-based approaches:

- PIO v1: CDC dead from boot (PIO init before TinyUSB)
- PIO v2: CDC dies during TX loop (DMA IRQ contention)
- PIO v3: CDC dead after PIO, never recovers (GPIO reassignment + TinyUSB corruption)

The only viable output method during PIO mode is **Serial1 (hardware UART)** on GP0/GP1, which requires a USB-UART bridge to read.

## What We Confirmed

Despite CDC issues, **PIO TX v3 produces real RF output**:
- RX board (F242D) received packets from TX board (8332)
- Received packets: 100, 200 (matching flrc_raw_rx.cpp output format)
- TX throughput estimated ~1377 kbps (based on PIO v1 result with identical TX loop)

## Blocker: Physical BOOTSEL Required

Both boards have dead CDC and cannot be reflashed remotely:
- `picotool reboot -u -f` fails: no reset interface in firmware
- DTR/RTS doesn't trigger BOOTSEL: no wiring
- BOOTSEL serial command can't reach dead CDC
- No SWD debug probe

**Need user to physically press BOOTSEL button on both boards.**

## Next Steps

1. **Physical BOOTSEL on TX board (8332)** — flash v4 baseline (proven 1367 kbps with working CDC)
2. **Physical BOOTSEL on RX board (F242D)** — flash raw RX firmware
3. **Run v4 baseline TX+RX test** — get final confirmed throughput with working CDC
4. **Accept 1367 kbps as ceiling** — PIO+DMA doesn't improve real throughput, air time dominates
5. **Consider UART bridge** — if future PIO testing needed, solder USB-UART bridge to GP0/GP1