# Sustained Throughput Sweep Results — 2026-07-23

## Phase 1: FLRC Sustained Sweep

| Bitrate (kbps) | Packets RX | Unique | Sustained (kbps) | % of Theoretical | RSSI avg (dBm) | PER (unique/rx) |
|----------------|-----------|--------|-------------------|-------------------|----------------|-----------------|
| 2600           | 21,923    | 21,923 | 1484.9            | 57.1%             | -71.0          | 0.00%           |
| 1300           | 11,906    | 11,904 | 806.4             | 62.0%             | -71.3          | 0.02%           |
| 650            | 6,203     | 6,203  | 420.1             | 64.6%             | -73.2          | 0.00%           |
| 325            | 3,543     | 3,543  | 240.0             | 73.8%             | -73.1          | 0.00%           |

### Key Findings — FLRC

1. **RX keeps up at ALL bitrates** — PER ~0% across the board. No RX processing ceiling hit.
2. **Sustained throughput scales linearly with bitrate** — not a fixed RX ceiling.
3. **Efficiency increases at lower bitrates**: 57% → 74% of theoretical. RX overhead is a smaller fraction of air time at lower rates.
4. **The bottleneck is TX-side** (SPI FIFO write time), not RX-side. TX sends at ~1487 kbps regardless of configured bitrate (the TX loop is dominated by SPI overhead, not air time).
5. **RSSI stable** at -71 to -73 dBm across all bitrates (close range, same power).

### TX Rate Anomaly

TX reports ~1487 kbps at ALL bitrates (2600, 1300, 650, 325). This is because the TX loop time is dominated by SPI overhead (FIFO write + command sequence), not air time. At 325 kbps, air time per packet is 3.12ms but SPI overhead is ~680µs — the TX loop sends at the same rate regardless of the radio's actual bitrate setting.

This means the sustained throughput numbers above are TX-limited, not RX-limited. The true RX capacity at each bitrate may be higher than what we measured.

### Binary-Step Monotonicity

Throughput is monotonic across all 4 steps: 1485 → 806 → 420 → 240 kbps. No anomalies. No refinement points needed.

### Efficiency Curve

| Air time/pkt (ms) | Sustained/theoretical | RX overhead fraction |
|-------------------|----------------------|---------------------|
| 0.39 (2600 kbps)  | 57.1%                | 43% lost to TX SPI   |
| 0.78 (1300 kbps)  | 62.0%                | 38% lost             |
| 1.56 (650 kbps)   | 64.6%                | 35% lost             |
| 3.12 (325 kbps)   | 73.8%                | 26% lost             |

The efficiency increases at lower bitrates because the fixed TX SPI overhead (~680µs) becomes a smaller fraction of the longer air time.

## Phase 2: LoRa Sustained Sweep

(Results to be filled after LoRa firmware testing)

## Test Configuration

- Frequency: 2440 MHz (2.4 GHz)
- Packet size: 127 bytes
- TX power: 12 dBm
- TX board: F242D (RP2040 #2)
- RX board: 8332 (RP2040 #1)
- SPI: 20 MHz
- RX window: 15s listen, 3s silence timeout
- TX: continuous (no inter-burst pause), 50,000 packet count
- Protocol: raw 2-byte opcode SPI (ADR-020, no RadioLib)