# Multi-Radio Research Plan

## Overview
Research track for achieving high throughput (target: 2.6 Mbps per link, 5.2+ Mbps aggregate)
using the LR2021's native FIFO, DMA streaming, and multi-radio architectures with FPGA/RP2040
coprocessors for bent-pipe bridging between balloons.

## Key Discovery: LR2021 ≠ SX1280
The LR2021 has native FIFO capabilities the SX1280 lacks:
- Dedicated RX/TX FIFOs with level monitoring (`getRxFifoLevel` returns uint16_t)
- FIFO threshold interrupts (EMPTY/LOW/HIGH/FULL/OVERFLOW/UNDERFLOW)
- Auto-RX-TX mode (radio auto-returns to RX after packet)
- Single-frame FIFO read (faster than SX1280's multi-step read)

## Architecture: Control Plane / Data Plane Separation
```
Application:  Nostr (store-and-forward messaging)
Payment:      TollGate (Cashu token verification)
Control:      FIPS (Noise XK encryption, mesh routing) — runs on ESP32-C3
Data:         FPGA/RP2040 crossbar (bent-pipe relay, ~1µs) — transparent to all layers above
Physical:     N× LR2021 radios (FLRC/LoRa, dual-band)
```

## Antenna Strategy
- Ground stations: Yagi or dish antennas (directional, high gain)
- Balloons: Omnidirectional wire dipoles or patch antennas

## Checklist

### Phase 1: Documentation
- [ ] Write ADR-014: Bent-Pipe FPGA/RP2040 Bridging
- [ ] Update ROADMAP.md with V2 multi-radio research track
- [ ] Document 3+ radio topologies (linear chain, star, full mesh, cross-altitude)
- [ ] Document power/weight analysis for 1-6 radio configurations

### Phase 2: LR2021 FIFO Characterization (immediate priority)
- [ ] Create fifo_test.cpp using native LR2021 FIFO API
- [ ] Add CONFIG_BENCH_MODE_FIFO_TEST to Kconfig
- [ ] Update CMakeLists.txt
- [ ] Build fifo_test.bin
- [ ] Test with 4 packet sizes: 20B, 50B, 100B, 255B
- [ ] Answer: Can FIFO accumulate multiple packets before MCU read?
- [ ] Measure: FIFO level at threshold, DMA read time, max throughput
- [ ] Document findings in RESULTS.md

### Phase 3: DMA Streaming on ESP32-C3
- [ ] Implement raw register access (bypass RadioLib for hot path)
- [ ] Implement DMA burst read from LR2021 FIFO
- [ ] Implement FIFO threshold-based interrupt handler
- [ ] Benchmark per-packet processing time (profile_rx.cpp)
- [ ] Benchmark sustained throughput with DMA + no PRBS
- [ ] Target: 800 kbps - 2.6 Mbps on single radio

### Phase 4: Multi-Radio Prototype
- [ ] Design 2x LR2021 + RP2040 schematic
- [ ] Build prototype on perfboard
- [ ] Test dual-radio bent-pipe relay
- [ ] Measure power consumption
- [ ] Test 3+ radio configurations with FPGA

### Phase 5: Balloon-to-Balloon Bridge
- [ ] Design bent-pipe packet routing in FPGA/RP2040
- [ ] Design frequency diversity scheme (2.4G + 868M simultaneously)
- [ ] Latency measurement: FPGA path vs MCU path
- [ ] Protocol: How does TDMA work with 2+ independent radios?
- [ ] Test multi-hop relay chain (2-3 balloons)

## Throughput Projections
| Architecture | Per-Link | 2-Radio Aggregate | Power |
|-------------|----------|-------------------|-------|
| Current (RadioLib, PRBS) | 80 kbps | 80 kbps | 134 mW |
| DMA + skip PRBS + FIFO batch | ~800 kbps | ~800 kbps | 134 mW |
| + RP2040 dual-radio | ~800 kbps × 2 | ~1.6 Mbps | ~175 mW |
| + FPGA dual-radio | ~2.6 Mbps × 2 | ~5.2 Mbps | ~89 mW |

## Multi-Radio Weight/Power Budget
| Config | Radios | Weight Added | Total Weight | Avg Power |
|--------|--------|-------------|-------------|-----------|
| 1 radio (V2 current) | 1× LR2021 | — | 18-22g | ~431 mW |
| 2 radio + RP2040 | 2× LR2021 + RP2040 | +1.3g | 19-23g | ~175 mW |
| 3 radio + RP2040 | 3× LR2021 + RP2040 | +1.8g | 20-24g | ~230 mW |
| 4 radio + FPGA | 4× LR2021 + iCE40 | +2.8g | 21-25g | ~89 mW |
