# FLRC Throughput Benchmark

Measure actual FLRC and LoRa throughput between two NiceRF LR2021 + ESP32-C3 SuperMini boards.

## Hardware

- 2x ESP32-C3 SuperMini V1 (Maker go, USB-C)
- 2x NiceRF LoRa2021 (LR2021 Gen4, 18-pin)
- Wire dipole antennas: 8.6 cm legs for 868 MHz, 5.8 cm for 2.4 GHz

## Wiring (same as MeshCore project)

| LR2021 Pin | ESP32 GPIO | SuperMini Pin |
|------------|------------|---------------|
| Pin 1 (VCC) | 3.3V | 3V3 |
| Pin 2,8,11,12,18 (GND) | GND | GND |
| Pin 3 (MISO) | GPIO2 | D2 |
| Pin 4 (MOSI) | GPIO7 | D7 |
| Pin 5 (SCK) | GPIO6 | D6 |
| Pin 6 (NSS) | GPIO10 | D10 |
| Pin 7 (BUSY) | GPIO4 | D4 |
| Pin 14 (RST) | GPIO3 | D3 |
| Pin 15 (DIO9/IRQ) | GPIO5 | D5 |
| Pin 9 (ANT) | wire antenna | 868 MHz |

## Setup

```bash
bash setup.sh          # Install board definition + variant into PlatformIO
pio run                # Build default (flrc_tx)
make build-all         # Build all 12 targets
```

## Build Environments (12 targets)

| Environment | Band | Freq | Modulation | Bit Rate | Power |
|---|---|---|---|---|---|
| `flrc_tx` / `flrc_rx` | 868 MHz | 868.0 | FLRC | 325 kbps | +22 dBm |
| `flrc_tx_650` / `flrc_rx_650` | 868 MHz | 868.0 | FLRC | 650 kbps | +22 dBm |
| `flrc_tx_24` / `flrc_rx_24` | 2.4 GHz | 2450.0 | FLRC | 1300 kbps | +12 dBm |
| `flrc_tx_24_max` / `flrc_rx_24_max` | 2.4 GHz | 2450.0 | FLRC | 2600 kbps | +12 dBm |
| `lora_tx` / `lora_rx` | 868 MHz | 868.0 | LoRa SF9/BW125 | ~1.8 kbps | +22 dBm |
| `lora_tx_sf8` / `lora_rx_sf8` | 868 MHz | 869.618 | LoRa SF8/BW62.5 | ~4.5 kbps | +22 dBm |

## Test Procedure

1. Flash TX on Board 1: `make flash-tx PORT1=/dev/ttyACM2`
2. Flash RX on Board 2: `make flash-rx PORT2=/dev/ttyACM3`
3. Monitor RX output: `make monitor2`
4. TX starts sending after 3-second countdown
5. RX prints results when it receives the end marker (0xDEADBEEF)
6. Record results in `../two-device-test-plan.md`

For 2.4 GHz tests, switch antenna to LR2021 Pin 10 (2.4G output).

## EU Regulatory Note

- 868 MHz ISM: BW ≤ 125 kHz, 10% duty cycle — only LoRa is legal
- FLRC at 868 MHz exceeds BW limits — lab testing only
- 2.4 GHz: No BW restriction, FLRC is legal — use for real deployment
- FLRC 2.4 GHz @ +12 dBm: max legal TX power for this band

## Expected Results (Theoretical)

| Test | Raw Bit Rate | Expected Effective | Range (est.) |
|---|---|---|---|
| FLRC 868 @ 325 kbps | 325 kbps | ~100-200 kbps | 20-50 km |
| FLRC 868 @ 650 kbps | 650 kbps | ~200-400 kbps | 10-30 km |
| FLRC 2.4G @ 1300 kbps | 1300 kbps | ~400-800 kbps | 3-10 km |
| FLRC 2.4G @ 2600 kbps | 2600 kbps | ~800-1600 kbps | 1-5 km |
| LoRa SF9/BW125 | 1.8 kbps | ~1.5 kbps | 300+ km |
| LoRa SF8/BW62.5 | 4.5 kbps | ~3-4 kbps | 200+ km |
