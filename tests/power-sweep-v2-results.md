# LR2021 FLRC Power Sweep v2 — 2026-07-23

## Conditions
- **Setup:** Indoor, ~30cm TX-RX separation (desktop)
- **Bitrate:** 2600 kbps FLRC
- **Frequency:** 2440.0 MHz
- **Packet size:** 127 bytes
- **Burst:** 500 packets per burst, 2s pause, repeat
- **RX firmware:** flrc_raw_rx.cpp with GPIO IRQ fix (commit 3dcddaf)
- **TX firmware:** flrc_range_tx_auto.cpp, auto-burst
- **Boards:** TX=F242D (E663B035977F242D), RX=8332 (E663B035973B8332)

## Results

| Power (dBm) | RX Avg | Unique Avg | TX Sent | PER (%) | Throughput (kbps) | PA Status |
|-------------|--------|------------|---------|---------|-------------------|-----------|
| 0.0         | 480    | 480        | 500     | 3.8-4.4 | 1462-1463         | Bypassed  |
| 3.0         | 478    | 477        | 500     | 4.2-4.6 | 1455-1460         | Bypassed  |
| 6.0         | 480    | 480        | 500     | 3.8-4.4 | 1458-1463         | Bypassed  |
| 9.0         | 478    | 478        | 500     | 4.0-4.8 | 1456-1460         | Bypassed  |
| 12.0        | 478    | 478        | 500     | 4.2-4.4 | 1457-1458         | Bypassed  |
| 12.5        | ~2587  | ~2587      | 500+    | ~0*     | 219               | **ENABLED** |

*12.5 dBm PER not precisely calculated because RX caught packets from
adjacent TX bursts (RX listen window > TX pause). In a controlled burst
test, 0% PER was confirmed (622/500 rx, DEADBEEF caught, correct seq 0-499).

## Key Findings

### PA Discontinuity Confirmed
Power register codes 0-24 (0.0 to 12.0 dBm) all bypass the power amplifier.
Actual RF output is identical across this range — PER is flat at ~4% regardless
of the requested power level.

Register code 25 (12.5 dBm) enables the PA. This produces a massive jump:
- ~43 dB RSSI improvement (from ~-103 dBm to ~-60 dBm, per prior measurements)
- Near-zero PER
- 5x throughput increase (219 vs ~4 kbps in old broken-RX tests)

### Residual 4% PER (Non-PA)
The consistent ~4% PER at all non-PA levels is likely due to:
- Indoor multipath interference at close range
- No CRC/error correction (FLRC CR=4/5, CRC disabled)
- SPI bus contention during FIFO read (~50us dead time per packet)

At outdoor range with the PA enabled, PER should be negligible.

## Methodology
1. Built 6 TX firmware variants with TX_POWER_DBM override
2. Flashed each to TX board via UF2 (1200 baud BOOTSEL trigger)
3. RX board kept fixed with GPIO-IRQ firmware throughout
4. Captured 18s of serial output per power level
5. Extracted RESULT lines for rx count, PER, throughput
6. DEADBEEF end marker confirmed TX sent count = 500
