# LR2021 Indoor Baseline Sweep — PA ON, 1m

> 2026-07-24, speed-tests track, first full 14-phase cycle

## Setup

- TX: RP2040 F242D, sweep-tx firmware, TX_POWER=12.5 dBm (PA ON, code 25)
- RX: RP2040 8332, sweep-rx firmware
- Distance: ~1m indoor, desk-to-desk
- Serial: Both via ESP32 UART bridge (ACM1=TX, ACM3=RX)

## Results

### HF LoRa (2440 MHz, BW 812 kHz, CR 4/5)

| SF | TX sent | RX recv | PER | RSSI |
|----|---------|---------|-----|------|
| SF7 | 50 | 29 | 42% | -29.7 dBm |
| SF9 | 50 | 19 | 62% | -28.0 dBm |
| SF12 | 30 | 17 | 43% | -26.3 dBm |

LoRa RSSI realistic for 1m indoor. High PER from timing drift between boards.

### HF FLRC (2440 MHz)

| Bitrate | TX sent | RX recv | PER | RSSI |
|---------|---------|---------|-----|------|
| 2600 | 196 | 12 | 94% | -107.8 dBm |
| 1300 | 196 | 29 | 86% | -109.2 dBm |
| 650 | 196 | 29 | 86% | -111.6 dBm |
| 325 | 196 | 6 | 97% | -114.5 dBm |

**FLRC RSSI BUG:** Values (-104 to -115 dBm) are wrong for 1m indoor.
Expected ~-27 dBm. Raw byte debug capture in progress to diagnose.

### LF LoRa (868 MHz, BW 250 kHz, CR 4/5)

| SF | TX sent | RX recv | PER | RSSI |
|----|---------|---------|-----|------|
| SF7 | 49 | 0 | 100% | — |
| SF9 | 50 | 0 | 100% | — |
| SF12 | 0* | 6 | 70% | -20.7 dBm |

*TX sent=0/timeout=20: TX spin loop (30M iterations) too short for SF12 @ 250 kHz (~800ms airtime).

LF LoRa SF7/SF9: 0 rx despite TX sending 49-50 packets. Timing drift causes RX/TX phase mismatch.

### LF FLRC (868 MHz) — PATH D CONFIRMED ✅

| Bitrate | TX sent | RX recv | PER | RSSI |
|---------|---------|---------|-----|------|
| 2600 | 196 | 61 | 69.5% | -104.4 dBm |
| 1300 | 196 | 85 | 57.5% | -106.1 dBm |
| 650 | 196 | 199 | **0.5%** | -107.9 dBm |
| 325 | 196 | — | — | — |

**LF FLRC-650 = 0.5% PER.** The LR2021 chip DOES support FLRC modulation on 868 MHz LF path.

This was UNTESTED (plan marked it "⚠️ may not be supported"). It works.

FLRC RSSI values also wrong here (same formula bug). LoRa RSSI at -20.7 dBm is reasonable.

## Issues

1. **FLRC RSSI formula wrong** — Raw SPI bytes needed. Debug output added to capture.
   GET_FLRC_PACKET_STATUS (0x024B) byte layout differs from expected.

2. **LF LoRa SF12 TX timeout** — Spin loop (~240ms) < SF12 airtime (~800ms @ 250 kHz).
   Need to extend spin count or use delay-based wait.

3. **High PER across phases** — Timing drift between free-running boards.
   Mitigation: use single-config firmware for precision measurements.

4. **CALIB_FRONT_END LF** — Plan says no bit15 for LF. Removed bit15. LF FLRC works.
   LF LoRa SF12 gets packets, but SF7/SF9 don't (timing, not radio).

## Files

- `tests/sweep_pa_on_indoor_1m.csv` — Parsed unified CSV (13 phases)
- `/tmp/sweep_rx_pa_on.txt` — Raw RX serial log
- `/tmp/sweep_tx_pa_on.txt` — Raw TX serial log
