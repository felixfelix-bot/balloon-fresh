# RP2040 LR2021 Baseline — v1.0.0

**Date:** 2026-07-29 (captures) / 2026-07-30 (documentation)
**Hardware:** RP2040 + NiceRF LoRa2021 (Semtech LR2021 Gen 4)
**Firmware:** flrc_raw_tx.cpp (raw 2-byte opcode SPI, NOT RadioLib)
**LA:** 8-channel logic analyzer, sigrok captures

## Purpose

This is the reference baseline for RP2040 SPI performance with the LR2021 radio.
All future ESP32-C3 measurements will be compared against these numbers.

## SPI Bus Metrics

| Metric | Value | Notes |
|--------|-------|-------|
| SPI clock requested | 20 MHz | maxgerhardt PIO firmware target |
| SPI clock actual | 10.40 MHz | 52% of target — PIO divider limitation |
| CS-low overhead | Single CS-low per txn | combined SPI reads (fix applied) |
| Bus utilization | 67% | gap between SPI bandwidth and PHY max |

## Throughput

| Metric | Value | Notes |
|--------|-------|-------|
| End-to-end throughput | 1745 kbps | verified, bidirectional |
| PHY max theoretical | ~2600 kbps | FLRC mode, 2.4 GHz |
| Efficiency | 67% of PHY max | SPI clock limited |
| Packet loss | 0% (1000/1000) | bench test, 1m distance |
| Optimal payload | 255 bytes | largest single-frame payload |

## Payload Sweep Results

Captured at 4 payload sizes via logic analyzer:

| Payload | .sr File | Status |
|---------|----------|--------|
| 32 B | sweep-32.sr | Captured |
| 64 B | sweep-64.sr | Captured |
| 128 B | sweep-128.sr | Captured |
| 255 B | sweep-255.sr | Captured (optimal) |
| Baseline | bench-rp2040.sr | Reference capture |

## Power Sweep

| Power (dBm) | Packets RX | RSSI avg | RSSI min | RSSI max |
|-------------|-----------|----------|----------|----------|
| 0 | 0 | — | — | — |
| 3 | 4 | -103.2 | -104 | -103 |
| 6 | 2 | -104.0 | -104 | -104 |
| 9 | (captured) | — | — | — |

## Range / Walk Tests

- Indoor baseline: 534 lines of characterization data
- GPS-synced outdoor walks: phone-gps-walk-20260724.csv (441 lines)
- Walk test logs: 7+ walk captures in data/range-tests/20260725/
- Overnight stability: overnight-stability.log
- Characterization: char_dist_1m_env_indoor_* (multiple runs)

## Key Findings

1. **SPI clock is the bottleneck** — RP2040 PIO achieves 10.40MHz, not the 20MHz target
2. **Single CS-low fix critical** — combining SPI reads into one CS-low txn boosted throughput
3. **255B payload optimal** — fills single FLRC frame, minimal overhead
4. **0% packet loss achievable** — radio link is solid at bench distance
5. **Power sweep shows sensitivity** — at 0dBm no packets received, 3dBm minimum for reliable RX

## ESP32-C3 Comparison Plan

When ESP32-C3 + LR2021 is ready, measure the same metrics:
- SPI clock actual (ESP32 hardware SPI, no PIO limitation)
- End-to-end throughput (kbps)
- Packet loss at 1000 packets
- Payload sweep (32/64/128/255B)
- CS-low timing

**Decision criteria:** If ESP32-C3 SPI clock > 10.40MHz, throughput should scale proportionally.
ESP32-C3 has hardware SPI (no PIO bottleneck), potentially reaching 20MHz+ clock.

## File Locations

- LA captures: `captures/*.sr`
- Serial logs: `data/*.txt`, `data/*.csv`
- Range tests: `data/range-tests/20260725/`
- Walk tests: `data/walk-tests/`
- Power sweep: `data/power-sweep-*.csv`, `data/power-sweep-raw-*.txt`
- Firmware: `firmware/rp2040/src/flrc_raw_tx.cpp`
- Protocol docs: `docs/lr2021-spi-protocol-reference.md`, `docs/lr2021-spi-command-reference.md`
