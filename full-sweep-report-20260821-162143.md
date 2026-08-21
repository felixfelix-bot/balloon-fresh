# E80-to-E80 FULL Parameter Sweep — 2026-08-21

**Date:** 2026-08-21T16:21:43.262609

**Firmware:** 88a00cf (T5a: pcrc16 + NVIC race fix) — both boards

**Session tag:** 2608211621  
**Packets per config:** 50  **Setup:** bench, boards ~30 cm apart, whip antennas

**SWD probes:** TX 148757200D2D1425, RX 203584200D2D0D42

**Serial ports (this run):** TX /dev/ttyUSB3, RX /dev/ttyUSB5 (CH340 USB bridges swap between reboots — auto-detected at runtime)

## Results

| # | Config | Mod | RX | % | RSSI avg (dBm) | SNR avg (dB) | CRC err | Bit err | TX done |
|---|---|---|---|---|---|---|---|---|---|
| 1 | SF5 BW125 PA10 | lora | 50/50 | 100% | -32.0 | 10.1 | 0 | 0 | ✓ |
| 2 | SF6 BW125 PA10 | lora | 50/50 | 100% | -32.0 | 13.0 | 0 | 0 | ✓ |
| 3 | SF7 BW125 PA10 | lora | 50/50 | 100% | -32.0 | 15.1 | 0 | 0 | ✓ |
| 4 | SF8 BW125 PA10 | lora | 50/50 | 100% | -32.0 | 16.8 | 0 | 0 | ✓ |
| 5 | SF9 BW125 PA10 | lora | 50/50 | 100% | -32.0 | 14.0 | 0 | 0 | ✓ |
| 6 | SF10 BW125 PA10 | lora | 50/50 | 100% | -32.0 | 15.4 | 0 | 0 | ✓ |
| 7 | SF11 BW125 PA10 | lora | 50/50 | 100% | -32.0 | 11.3 | 0 | 0 | ✓ |
| 8 | SF12 BW125 PA10 | lora | 50/50 | 100% | -32.0 | 14.0 | 0 | 0 | ✓ |
| 9 | SF5 BW250 PA10 | lora | 50/50 | 100% | -32.0 | 10.1 | 0 | 0 | ✓ |
| 10 | SF6 BW250 PA10 | lora | 50/50 | 100% | -32.0 | 13.0 | 0 | 0 | ✓ |
| 11 | SF7 BW250 PA10 | lora | 50/50 | 100% | -32.0 | 15.0 | 0 | 0 | ✓ |
| 12 | SF8 BW250 PA10 | lora | 50/50 | 100% | -32.0 | 16.7 | 0 | 0 | ✓ |
| 13 | SF9 BW250 PA10 | lora | 50/50 | 100% | -32.1 | 13.2 | 0 | 0 | ✓ |
| 14 | SF10 BW250 PA10 | lora | 50/50 | 100% | -32.2 | 14.5 | 0 | 0 | ✓ |
| 15 | SF11 BW250 PA10 | lora | 50/50 | 100% | -32.1 | 10.9 | 0 | 0 | ✓ |
| 16 | SF12 BW250 PA10 | lora | 50/50 | 100% | -32.0 | 13.5 | 0 | 0 | ✓ |
| 17 | SF5 BW500 PA10 | lora | 50/50 | 100% | -32.0 | 10.0 | 0 | 0 | ✓ |
| 18 | SF6 BW500 PA10 | lora | 50/50 | 100% | -32.0 | 12.9 | 0 | 0 | ✓ |
| 19 | SF7 BW500 PA10 | lora | 50/50 | 100% | -32.0 | 15.0 | 0 | 0 | ✓ |
| 20 | SF8 BW500 PA10 | lora | 50/50 | 100% | -33.0 | 15.6 | 0 | 0 | ✓ |
| 21 | SF9 BW500 PA10 | lora | 50/50 | 100% | -33.3 | 12.8 | 0 | 0 | ✓ |
| 22 | SF10 BW500 PA10 | lora | 50/50 | 100% | -33.7 | 12.9 | 0 | 0 | ✓ |
| 23 | SF11 BW500 PA10 | lora | 50/50 | 100% | -33.9 | 8.8 | 0 | 0 | ✓ |
| 24 | SF12 BW500 PA10 | lora | 50/50 | 100% | -33.9 | 10.1 | 0 | 0 | ✓ |
| 25 | SF8 BW125 PA0 | lora | 50/50 | 100% | -43.9 | 16.5 | 0 | 0 | ✓ |
| 26 | SF8 BW125 PA3 | lora | 50/50 | 100% | -41.0 | 16.5 | 0 | 0 | ✓ |
| 27 | SF8 BW125 PA6 | lora | 50/50 | 100% | -37.9 | 16.6 | 0 | 0 | ✓ |
| 28 | SF8 BW125 PA10 L16 | lora | 50/50 | 100% | -34.0 | 15.4 | 0 | 0 | ✓ |
| 29 | SF8 BW125 PA10 L128 | lora | 50/50 | 100% | -34.0 | 15.1 | 0 | 0 | ✓ |
| 30 | SF8 BW125 PA10 L255 | lora | 50/50 | 100% | -34.0 | 16.0 | 0 | 0 | ✓ |
| 31 | SF8 BW125 PA10 L511 | lora | 0/50 | 0% | - | - | 0 | 0 | ✗ |
| 32 | FLRC 260k pa5 | flrc | 50/50 | 100% | -77.8 | 0.0 | 50 | 0 | ✓ |
| 33 | FLRC 325k pa5 | flrc | 50/50 | 100% | -77.6 | 0.0 | 50 | 0 | ✓ |
| 34 | FLRC 520k pa5 | flrc | 50/50 | 100% | -75.8 | 0.0 | 50 | 0 | ✓ |
| 35 | FLRC 650k pa5 | flrc | 50/50 | 100% | -70.9 | 0.0 | 50 | 0 | ✓ |
| 36 | FLRC 1040k pa5 | flrc | 50/50 | 100% | -68.7 | 0.0 | 50 | 0 | ✓ |
| 37 | FLRC 1300k pa5 | flrc | 50/50 | 100% | -68.7 | 0.0 | 50 | 0 | ✓ |
| 38 | FLRC 2080k pa5 | flrc | 50/50 | 100% | -66.4 | 0.0 | 50 | 0 | ✓ |
| 39 | FLRC 2600k pa5 | flrc | 50/50 | 100% | -66.1 | 0.0 | 50 | 0 | ✓ |
| 40 | FLRC 650k pa0 | flrc | 50/50 | 100% | -70.8 | 0.0 | 50 | 0 | ✓ |
| 41 | FLRC 650k pa1 | flrc | 50/50 | 100% | -70.8 | 0.0 | 50 | 0 | ✓ |
| 42 | FLRC 650k pa3 | flrc | 50/50 | 100% | -71.1 | 0.0 | 50 | 0 | ✓ |
| 43 | FLRC 650k pa7 | flrc | 50/50 | 100% | -69.9 | 0.0 | 50 | 0 | ✓ |
| 44 | FLRC 650k pa10 | flrc | 50/50 | 100% | -72.4 | 0.0 | 50 | 0 | ✓ |
| 45 | SF8 BW125 @ 863.000MHz | lora | 50/50 | 100% | -37.7 | 16.3 | 0 | 0 | ✓ |
| 46 | SF8 BW125 @ 865.000MHz | lora | 50/50 | 100% | -35.6 | 16.2 | 0 | 0 | ✓ |
| 47 | SF8 BW125 @ 869.525MHz | lora | 50/50 | 100% | -32.6 | 15.9 | 0 | 0 | ✓ |
| 48 | SF8 BW125 @ 870.000MHz | lora | 50/50 | 100% | -32.2 | 16.0 | 0 | 0 | ✓ |

## Parameter space covered

- LoRa: SF5-12 x BW[125, 250, 500] (PA 10 dBm)
- LoRa PA: [0, 3, 6, 10] dBm @ SF8 BW125 (indoor cap 0-10 dBm)
- Payload: [16, 64, 128, 255, 511] B @ SF8 BW125
- FLRC BR: [260, 325, 520, 650, 1040, 1300, 2080, 2600] kbps @ pa 5
- FLRC pa: [0, 1, 3, 5, 7, 10] @ BR 650 kbps
- Frequency: [863.0, 865.0, 868.0, 869.525, 870.0] MHz @ SF8 BW125

## Files

- Summary CSV: `full-sweep-summary-20260821-162143.csv`
- Per-packet CSV: `full-sweep-pkts-20260821-162143.csv`
- Script: `firmware/e80-stm32-bench/tools/e80_sweep_full.py`

## Notes

- GAP adaptive: max(10 ms, 1.2×airtime + 5 ms) — prevents RX overrun at SF11/12
- SWD reset (`reset halt; resume`) between configs clears all radio state
- PA capped 0–10 dBm by firmware (EU indoor); `POWER MODE OUTDOOR <pin>` unlock exists
- LEN 6–511 enforced; FREQ 863–870 MHz enforced (EU SRD)

## Anomalies (open issues)

1. **LEN=511 @ SF8 BW125: 0/50 RX, TX never reported DONE.** LEN is firmware-valid
   (512 rejected, 511 accepted at parse) and gap was adaptive (1.64 s for 1.36 s
   airtime). Either a TX-side buffer limit at max payload or LEN 511 + PRBS
   interaction. LEN 255 works perfectly (50/50, CRC 0). Needs firmware-side
   investigation before trusting max-length payload numbers.

2. **FLRC: all packets received (50/50 at radio level) but 100% CRC errors,
   SNR reports 0.0.** RSSI behaves sensibly (-66 to -78 dBm, improves with BR).
   This matches the known FLRC byte-alignment issue documented in
   balloon-range-tests (commit 9b740aa) — RX payload bytes are shifted so
   payload CRC never matches. Radio link itself works; data integrity broken.
   FLRC RSSI values are usable; FLRC PER/CRC stats are not until alignment fix.

3. **RSSI varies across band** (-37.7 @ 863 MHz to -32.2 @ 870 MHz, same config):
   whip antenna response + possible TX power flatness. Normal, but frequency-
   dependent comparisons should use same-frequency baselines.
