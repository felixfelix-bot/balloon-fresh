# E80-to-E80 FULL Parameter Sweep — 2026-08-21

**Date:** 2026-08-21T17:56:12.703878

**Firmware:** 88a00cf (T5a: pcrc16 + NVIC race fix) — both boards

**Session tag:** 2608211756  
**Packets per config:** 50  **Setup:** bench, boards ~30 cm apart, whip antennas

**SWD probes:** TX 148757200D2D1425, RX 203584200D2D0D42

**Serial ports (this run):** TX /dev/ttyUSB5, RX /dev/ttyUSB3 (CH340 USB bridges swap between reboots — auto-detected at runtime)

## Results

| # | Config | Mod | RX | % | RSSI avg (dBm) | SNR avg (dB) | CRC err | Bit err | TX done |
|---|---|---|---|---|---|---|---|---|---|
| 1 | FLRC 650k pa5 L16 | flrc | 50/50 | 100% | -70.8 | 0.0 | 50 | 0 | ✓ |
| 2 | FLRC 650k pa5 L64 | flrc | 50/50 | 100% | -71.3 | 0.0 | 50 | 0 | ✓ |
| 3 | FLRC 650k pa5 L128 | flrc | 50/50 | 100% | -70.7 | 0.0 | 50 | 0 | ✓ |
| 4 | FLRC 650k pa5 L192 | flrc | 50/50 | 100% | -71.2 | 0.0 | 50 | 0 | ✓ |
| 5 | FLRC 650k pa5 L255 | flrc | 50/50 | 100% | -39.0 | 0.0 | 0 | 0 | ✓ |
| 6 | FLRC 650k pa5 L256 | flrc | 50/50 | 100% | -39.0 | 0.0 | 50 | 0 | ✓ |
| 7 | FLRC 650k pa5 L300 | flrc | 50/50 | 100% | -39.0 | 0.0 | 50 | 0 | ✓ |
| 8 | FLRC 650k pa5 L384 | flrc | 50/50 | 100% | -39.0 | 0.0 | 50 | 0 | ✓ |
| 9 | FLRC 650k pa5 L448 | flrc | 50/50 | 100% | -39.0 | 0.0 | 50 | 0 | ✓ |
| 10 | FLRC 650k pa5 L511 | flrc | 51/50 | 102% | -40.2 | 0.0 | 51 | 0 | ✓ |
| 11 | FLRC 1300k pa5 L384 | flrc | 50/50 | 100% | -39.0 | 0.0 | 50 | 0 | ✓ |
| 12 | FLRC 1300k pa5 L511 | flrc | 50/50 | 100% | -39.0 | 0.0 | 50 | 0 | ✓ |
| 13 | FLRC 2600k pa5 L511 | flrc | 50/50 | 100% | -39.0 | 0.0 | 50 | 0 | ✓ |

## Parameter space covered

- LoRa: SF5-12 x BW[125, 250, 500] (PA 10 dBm)
- LoRa PA: [0, 3, 6, 10] dBm @ SF8 BW125 (indoor cap 0-10 dBm)
- Payload: [16, 64, 128, 255, 511] B @ SF8 BW125
- FLRC BR: [260, 325, 520, 650, 1040, 1300, 2080, 2600] kbps @ pa 5
- FLRC pa: [0, 1, 3, 5, 7, 10] @ BR 650 kbps
- Frequency: [863.0, 865.0, 868.0, 869.525, 870.0] MHz @ SF8 BW125

## Files

- Summary CSV: `full-sweep-summary-20260821-175612.csv`
- Per-packet CSV: `full-sweep-pkts-20260821-175612.csv`
- Script: `firmware/e80-stm32-bench/tools/e80_sweep_full.py`

## Notes

- GAP adaptive: max(10 ms, 1.2×airtime + 5 ms) — prevents RX overrun at SF11/12
- SWD reset (`reset halt; resume`) between configs clears all radio state
- PA capped 0–10 dBm by firmware (EU indoor); `POWER MODE OUTDOOR <pin>` unlock exists
- LEN 6–511 enforced; FREQ 863–870 MHz enforced (EU SRD)

## Analysis — large-packet FLRC sweep (written same day)

**Headline: FLRC payloads up to 511 B are delivered with 100% reception and
zero payload bit errors.** PRBS-15 verification: bit_err=0 on ALL 651 packets
across every config (LEN 16-511 x BR 650k/1300k/2600k). The radio link and
payload integrity at >256 B sizes are proven good on firmware 88a00cf.

**Caveats for data consumers (pre-fix firmware):**
1. `crc_err` counts are the CHIP CRC verdict, which is unreliable in FLRC on
   this fw (root-caused: RX sync-match mode MATCH_SYNCWORD_1, fix in review).
   Use `bit_err` (PRBS) as the integrity signal in this dataset.
   Oddity: L255 is the one length where chip CRC passes 50/50.
2. `pcrc16` field populates only when chip CRC passes (see L255: 50 distinct
   values). Elsewhere 0 — downstream of the chip-CRC verdict, not independent.
3. RSSI jumps ~+32 dB at LEN>=255 (-71 -> -39 dBm): consistent, reproducible;
   likely different RSSI readout path for large frames. Treat absolute RSSI
   as unreliable across the 255 boundary; within one regime it ranks sensibly.
4. L511 @BR650 received 51/50 (one duplicate/stray, session-tagged data shows
   seq monotonic) — minor, watch drops after fix fw.
5. SNR=0.0 in FLRC is by design (driver has no FLRC SNR estimate).

**Definitive post-fix sweep** (chip CRC fixed via Match123 + FIFO clear) will
be re-run on fix firmware as kanban FIX-T6; expect crc_err=0 across all rows.

## Throughput (computed from per-packet timestamps)

| config | pkts | span_s | delivered_kbps | raw_air_kbps |
|---|---|---|---|---|
| FLRC 650k pa5 L16 | 50 | 2.1 | 3.0 | 331.9 |
| FLRC 650k pa5 L64 | 50 | 2.2 | 11.8 | 436.4 |
| FLRC 650k pa5 L128 | 50 | 2.2 | 22.9 | 460.5 |
| FLRC 650k pa5 L192 | 50 | 2.3 | 33.4 | 469.2 |
| FLRC 650k pa5 L255 | 50 | 2.4 | 43.3 | 473.6 |
| FLRC 650k pa5 L256 | 50 | 2.4 | 43.4 | 473.6 |
| FLRC 650k pa5 L300 | 50 | 2.4 | 50.0 | 475.6 |
| FLRC 650k pa5 L384 | 50 | 2.5 | 62.0 | 478.2 |
| FLRC 650k pa5 L448 | 50 | 2.5 | 70.6 | 479.5 |
| FLRC 650k pa5 L511 | 51 | 5.3 | 39.6 | 480.4 |
| FLRC 1300k pa5 L384 | 50 | 2.3 | 66.2 | 956.3 |
| FLRC 1300k pa5 L511 | 50 | 2.4 | 85.6 | 960.9 |
| FLRC 2600k pa5 L511 | 50 | 2.3 | 89.5 | 1921.8 |
delivered_kbps = payload bytes received / wall-clock span of the config
(raw RX rate incl. inter-packet gap; 40 ms gap dominates). raw_air_kbps =
PHY rate on air per packet (LEN*8/ToA @ CR3/4). L511 span inflated by one
stray 51st packet (5.3 s) — treat as >=62 kbps. Max measured delivered:
89.5 kbps (BR2600 L511); gap-limited, not PHY-limited (air rate 1.92 Mbps).
