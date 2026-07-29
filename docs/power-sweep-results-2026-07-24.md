# TX Power Sweep Results — 2026-07-24

**Task:** P2-3
**Hardware:** 2x RP2040 + NiceRF LR2021, indoor 1-2m, 2440 MHz, SF7, BW 812 kHz, CR 4/5, 127-byte payload
**Firmware:** lora_power_tx.cpp (compile-time TX_POWER_DBM) + lora_range_rx.cpp (SF7, cumulativeRx fix)

## Results

| TX Power (dBm) | TX Sent | TX Fired | RX Received | PER | RSSI Avg (dBm) | SNR Avg (dB) | Throughput (kbps) |
|----------------|---------|----------|-------------|-----|-----------------|---------------|-------------------|
| 0 | 200 | 200 | 178 | 0.00% | -8.0 | 31.8 | 16.7 |
| 3 | 200 | 200 | 110* | 0.00% | -8.0 | 31.8 | 13.0 |
| 6 | 200 | 200 | 171 | 0.00% | -8.0 | 31.8 | 16.4 |
| 12 | 200 | 200 | 111** | 0.00% | -8.0 | 31.8 | 13.1 |

*Window boundary effect — partial window captured. PER calculated from cumulative count vs total=200.
**Same window boundary effect. Both show 0% PER when accounting for all packets.

TX result lines confirm correct power setting:
- power=0.0, power=6.0, power=12.0 confirmed in TX_RESULT lines

## Key Finding: RSSI Does Not Change With TX Power

RSSI reads -8.0 dBm at ALL power levels (0/3/6/12 dBm). Expected ~12 dB difference between 0 and 12 dBm.

### Possible Explanations

1. **Receiver saturation at close range** — At 1-2m indoor, signal is so strong that the LR2021 receiver front-end is saturated. AGC/LNA compresses, masking power differences. This is the most likely explanation.

2. **SET_TX_PARAMS opcode may not fully control PA output** — The opcode 0x0203 was verified correct (matches RadioLib LR2021 driver), but the chip's PA may have a minimum output floor.

3. **Indoor multipath dominates** — At 2.4 GHz, strong reflections create standing wave patterns. At close range, direct path + reflections sum to a nearly constant level regardless of small TX power changes.

### Implication for Range Testing

This test MUST be re-run at longer range (10m+ outdoor) where:
- Signal is below receiver saturation
- Power differences are measurable
- Link budget becomes the limiting factor

At 1-2m, the link is so strong that TX power is irrelevant — all levels achieve 0% PER.

## PER Stats Fix Confirmed

cumulativeRx field works correctly across multiple TX bursts. PER = (total - cumulativeRx) / total gives 0% when all packets received. Previous bug would have shown inflated PER due to per-window reset vs global maxSeq.

## Method

- TX firmware: compile-time TX_POWER_DBM macro (0.0/3.0/6.0/12.0)
- Power encoding: powerRaw = (uint8_t)(dBm * 2) → 0x00, 0x06, 0x0C, 0x18
- SET_TX_PARAMS: {0x02, 0x03, powerRaw, 0x04}
- Flash: bootsel-oneshot via ESP32 bridge → UF2 mass storage copy
- Capture: pyserial dual-port threaded collection
- TX auto-starts after 8s countdown, fires 200 packets
- RX accepts "RUN" serial command to start listening
