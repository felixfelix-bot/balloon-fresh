# LR2021 ESP-IDF Benchmarker Results

Date: 2026-06-11
Firmware: benchmarker v1.1 (ESP-IDF, RadioLib 7.6.0 with calibration patch)
Hardware: 2x ESP32-C3 SuperMini V1 + NiceRF LoRa2021, wire dipoles, bench range (~1m)
Antennas: 868 MHz wire dipole on Pin 9 (Sub-GHz), 2.4 GHz wire dipole on Pin 10

## Critical Fix

The benchmarker TX was failing because `radio->irqDioNum = 9` was not set.
Without this, the LR2021 DIO mapping is not configured and interrupts don't fire on GPIO5.
This MUST be set before calling `begin()` or `beginFLRC()`.

## Key Discovery: LR2021 Power Limits

| Band | Frequency Range | Max TX Power |
|------|----------------|--------------|
| Sub-GHz (LF) | 150-1090 MHz | +22 dBm |
| Mid (HF) | 1900-2200 MHz | +12 dBm |
| 2.4 GHz (HF) | 2400-2500 MHz | +12 dBm |

The `checkOutputPower()` method enforces different limits based on `highFreq` flag (>1500 MHz).

## Test Results

### LoRa Baseline (868 MHz)

| Test | SF | BW | CR | PWR | Pkt Size | Count | Sent | Received | PER | BER | TX Tput | Avg RSSI |
|------|-----|-----|-----|------|----------|-------|------|----------|-----|-----|---------|----------|
| L1 | 9 | 125 | 4/7 | +22 | 28 | 10 | 10 | 10 | 0.000% | 0.000000% | 0.2 kbps | -96.6 dBm |

### FLRC Baseline (868 MHz, Sub-GHz)

| Test | BR (kbps) | CR | PWR | Pkt Size | Count | Sent | Received | PER | BER | TX Tput | Avg RSSI |
|------|-----------|-----|------|----------|-------|------|----------|-----|-----|---------|----------|
| F1 | 325 | 3/4 | +22 | 50 | 100 | 100 | 100 | 0.000% | 0.000000% | 4.0 kbps | -101.2 dBm |
| F2 | 650 | 3/4 | +22 | 50 | 100 | 100 | 100 | 0.000% | 0.000000% | 8.0 kbps | -104.2 dBm |
| F3 | 1300 | 3/4 | +22 | 50 | 100 | 100 | 100 | 0.000% | 0.000000% | 20.0 kbps | -109.5 dBm |
| F4 | 2600 | 3/4 | +22 | 50 | 100 | 100 | 100 | 0.000% | 0.000000% | 40.0 kbps | -104.2 dBm |

### FLRC Burst Tests (868 MHz, 2600 kbps, 200-byte packets)

| Delay | Sent | Received | PER | BER | TX Tput | RX Tput | Notes |
|-------|------|----------|-----|-----|---------|---------|-------|
| 0 ms | 200 | 100 | 50.0% | 0.000000% | 167.1 kbps | 16.1 kbps | Every other pkt lost (RX can't keep up) |
| 5 ms | 200 | 100 | 50.0% | 0.000000% | 167.0 kbps | 16.1 kbps | Same (5ms rounds to 0 ticks) |
| 10 ms | 200 | 100 | 50.0% | 0.000000% | 160.0 kbps | 16.0 kbps | Same (total ~10ms/pkt, RX needs >10ms) |
| 20 ms | 200 | 200 | 0.000% | 0.000000% | 80.0 kbps | 26.7 kbps | Perfect! RX processing needs ~15-20ms |

### FLRC 2.4 GHz Tests

| Test | BR (kbps) | PWR | Pkt Size | Count | Sent | Received | PER | BER | TX Tput | Avg RSSI |
|------|-----------|------|----------|-------|------|----------|-----|-----|---------|----------|
| 2G4-1 | 1300 | +12 | 100 | 100 | 100 | 100 | 0.000% | 0.000000% | 40.0 kbps | -108.9 dBm |
| 2G4-2 | 2600 | +12 | 100 | 100 | 100 | 100 | 0.000% | 0.000000% | 40.0 kbps | -105.4 dBm |

## Analysis

### RX Processing Bottleneck

The RX needs ~15-20ms per packet to process:
1. IRQ fires -> getPacketLength() SPI command
2. readData() SPI transfer (50-200 bytes)
3. PRBS-15 verification (CPU-intensive)
4. standby() SPI command
5. startReceive() SPI command

At 2600 kbps with 200-byte packets and no delay, TX sends every ~10ms.
RX can only process every other packet, giving 50% PER.
With 20ms spacing, 0% PER is achieved at 80 kbps sustainable throughput.

For production mesh: reduce PRBS overhead, consider DMA SPI, or use 1300 kbps with 10ms spacing.

### Throughput Summary

| Config | Band | Rate | Sustained Tput | Target Use |
|--------|------|------|---------------|------------|
| LoRa SF9 | 868 | ~1 kbps | 0.2 kbps | Telemetry, MeshCore |
| FLRC 325 | 868 | 325 kbps | 4.0 kbps | Sub-GHz data |
| FLRC 650 | 868 | 650 kbps | 8.0 kbps | Sub-GHz data |
| FLRC 1300 | 868 | 1300 kbps | 20.0 kbps | Lab-only (exceeds EU ISM BW) |
| FLRC 2600 | 868 | 2600 kbps | 80.0 kbps | Lab-only (exceeds EU ISM BW) |
| FLRC 1300 | 2450 | 1300 kbps | 40.0 kbps | 2.4 GHz mesh transport |
| FLRC 2600 | 2450 | 2600 kbps | 80.0 kbps | 2.4 GHz mesh transport (deploy) |

### Link Budget Implications

At bench range (~1m), RSSI at 868 MHz/+22 dBm is ~-100 dBm.
Expected path loss at 300 km: ~130 dB additional loss.
Expected RSSI at 300 km: ~-230 dBm (well below receiver sensitivity).

Receiver sensitivity for FLRC 2600 kbps on SX1280: approximately -90 to -95 dBm.
Link margin at 300 km: not enough without directional antennas or higher power.

For 2.4 GHz at +12 dBm: even less margin. Directional PCB Yagis (+10-15 dBi) would help.
Mesh V2 with SKY66114 (+30 dBm on 2.4 GHz) would provide adequate margin.

## Next Steps

- [ ] Power level sweep: find receiver sensitivity floor at each bit rate
- [ ] Range test: outdoor line-of-sight test at 100m, 500m, 1km, 5km
- [ ] Packet size sweep: optimize for throughput vs latency
- [ ] 2.4 GHz antenna comparison: wire dipole vs PCB Yagi
- [ ] Multi-node test: 3+ boards TX simultaneously
- [ ] Duty cycle stress test: continuous operation for 1+ hours
