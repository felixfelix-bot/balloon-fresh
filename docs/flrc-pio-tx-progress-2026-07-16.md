# FLRC PIO+DMA TX Firmware — Progress & Learnings

**Date:** 2026-07-16
**Commit:** a7be8ba (PIO+DMA firmware), CDC fix pending commit

## What Was Built

`flrc_pio_tx.cpp` — PIO state machine + DMA SPI master for LR2021 FLRC TX.

- Uses existing `lr2021_rx` PIO program (2-instruction SPI Mode 0 master)
- DMA feeds PIO TX FIFO (32-bit, BSWAP, DREQ-paced)
- CS framing via DMA completion ISR
- 20.83 MHz SCK (div=3, sysclk=125MHz)
- `rfWaitBusy()` before every command (MANDATORY)
- IRQ pin poll for TX_DONE
- Spin count printed for first 5 packets (fake result smoke test)
- Build: `pio run -e rp2040-pio-tx` — SUCCESS (75KB flash, 3.7% RAM)

## Expected Performance

- SPI overhead: 535µs (Arduino per-byte) → ~103µs (PIO+DMA at 20.83MHz)
- Target throughput: ~1900 kbps (up from 1367 kbps v4 baseline)
- Theoretical max: ~2540 kbps (2600 kbps air rate minus preamble+sync overhead)

## What Happened On Hardware

1. Flashed UF2 to TX board (ACM0, serial E663B035973B8332) via BOOTSEL mass storage
2. Board disappeared after flash — USB CDC serial port not enumerating
3. **Root cause:** `delay(100)` after `Serial.begin(115200)` too short for TinyUSB CDC enumeration
4. **Fix:** Changed to `delay(2000)` — known CDC fix from previous session (commit eee6147 era)
5. Rebuilt — SUCCESS. Ready to reflash.

## Key Learnings

1. **CDC delay is critical:** RP2040 TinyUSB CDC needs ≥2s delay after `Serial.begin()` before first `Serial.print()`. Without it, USB CDC port never enumerates. This was already documented from earlier session work but was missing in the PIO firmware.

2. **UF2 flash via mass storage works:** When picotool can't connect (permissions), BOOTSEL mode → mount /dev/sdX1 → `sudo cp firmware.uf2 /mnt/` → sync → umount. Board auto-reboots.

3. **Dual output (Serial + Serial1):** PIO firmware outputs to both USB CDC (`Serial`) and hardware UART (`Serial1` on GP0/GP1). Useful when CDC fails — but no USB-UART bridge connected to read Serial1.

## Next Steps

- [ ] Reflash patched PIO+DMA firmware (with delay(2000) fix) to TX board
- [ ] Verify USB CDC serial output appears
- [ ] Run TX test — check TX_DONE count + throughput
- [ ] If TX works, run simultaneous TX+RX test with RX board (ACM2)
- [ ] Verify throughput is real (not exceeding 2600 kbps air rate = fake TX_DONE)
- [ ] If fake: investigate IRQ pin timing, PIO CS framing
- [ ] Commit test results + documentation, push to both remotes

## Board Configuration

| Board | Serial | Port | Role | Current Firmware |
|-------|--------|------|------|------------------|
| RP2040 #1 | E663B035973B8332 | /dev/ttyACM0 | TX | PIO+DMA (pending reflash with CDC fix) |
| RP2040 #2 | E663B035977F242D | /dev/ttyACM2 | RX | v4 baseline (proven 1367 kbps, 0% loss) |
| ESP32-C3 #1 | 70:AF:09:13:21:00 | /dev/ttyACM1 | — | — |
| ESP32-C3 #2 | 70:AF:09:21:FB:18 | /dev/ttyACM3 | — | — |