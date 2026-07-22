# ADR 018: Multi-Mode Range Characterization Protocol

## Status
Accepted (2026-07-22)

## Context
The LR2021 supports FLRC, LoRa, and GFSK modulations across sub-GHz and 2.4 GHz bands. We have no comparative data on which configurations perform best at different ranges and environments. Previous range testing used only a single FLRC config (650 kbps) and all data was invalidated by the RSSI bug.

We need a systematic sweep that:
1. Tests ALL modulation types at their extreme settings
2. Uses log-spaced distance markers (binary: 2, 4, 8, 16, 32, 64, 128, 256m)
3. Completes fast enough that the operator can stand still during a full sweep (~50 seconds)
4. Produces directly comparable RSSI + packet delivery data across modes

## Decision

### 10-Config Sweep Table

Each config represents an extreme point or log-spaced midpoint of the LR2021's dynamic range.

| Slot | Mode  | Config             | Band    | Frequency | Airtime/pkt | Window |
|------|-------|--------------------|---------|-----------|-------------|--------|
| 1    | FLRC  | 2600 kbps          | 2.4 GHz | 2440 MHz  | ~0.1ms      | 1s     |
| 2    | FLRC  | 1300 kbps          | 2.4 GHz | 2440 MHz  | ~0.2ms      | 1s     |
| 3    | FLRC  | 650 kbps           | 2.4 GHz | 2440 MHz  | ~0.4ms      | 1s     |
| 4    | FLRC  | 260 kbps           | 2.4 GHz | 2440 MHz  | ~1.5ms      | 1s     |
| 5    | GFSK  | 1000 kbps          | 2.4 GHz | 2440 MHz  | ~0.3ms      | 1s     |
| 6    | GFSK  | 4.8 kbps           | 2.4 GHz | 2440 MHz  | ~40ms       | 5s     |
| 7    | LoRa  | SF5, BW=1000 kHz   | 2.4 GHz | 2440 MHz  | ~2ms        | 2s     |
| 8    | LoRa  | SF7, BW=250 kHz    | 2.4 GHz | 2440 MHz  | ~15ms       | 3s     |
| 9    | LoRa  | SF9, BW=125 kHz    | 2.4 GHz | 2440 MHz  | ~100ms      | 8s     |
| 10   | LoRa  | SF12, BW=31.25 kHz | 2.4 GHz | 2440 MHz  | ~10000ms    | 30s    |

Total sweep time: ~53 seconds + ~2s switching overhead = ~55 seconds.

### Distance Protocol

Binary-spaced positions: 2m, 4m, 8m, 16m, 32m, 64m, 128m, 256m.

At each position:
1. Operator stands still
2. Presses TX button to start sweep
3. TX and RX run all 10 configs in synchronized order
4. Operator moves to next position

### Band Selection

Phase 1: 2.4 GHz only (both boards have 2.4 GHz antennas connected).
Phase 2: Sub-GHz (868 MHz) with Sub-GHz antennas connected (Pin 9 on NiceRF module).

### Why These Specific Configs

- FLRC covers 260-2600 kbps in log steps (10x range, 4 points)
- GFSK covers the extremes: 4.8 kbps (chip default, very slow) and 1000 kbps
- LoRa covers SF5-SF12 at decreasing BW: the full processing-gain range
- SF12+BW=31.25kHz is the absolute sensitivity floor of the LR2021

### Dynamic Range Covered

| Parameter         | Min        | Max        | Range  |
|-------------------|------------|------------|--------|
| FLRC bitrate      | 260 kbps   | 2600 kbps  | 10x    |
| LoRa airtime      | 2ms        | 10000ms    | 5000x  |
| LoRa processing   | SF5 (+0dB) | SF12 (+21dB) | 21dB |
| GFSK bitrate      | 4.8 kbps   | 1000 kbps  | 208x   |

This is the complete dynamic range of the chip. No useful configuration is left out.

## Consequences
- Firmware must support runtime mode switching (beginFLRC/beginLoRa/beginGFSK)
- TX and RX must be synchronized (GPS time sync or button-triggered)
- Logger must tag each packet with current mode/config
- Plotting script must bin by both distance AND mode
