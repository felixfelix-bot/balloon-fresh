# LR2021 FLRC Throughput Optimization — Progress Report

**Date:** 2026-07-16
**Goal:** 2600+ kbps throughput between two RP2040 + LR2021 boards
**Status:** RF link working. TX 1293.6 kbps confirmed. Direct HW SPI optimization committed but untested.

---

## Hardware Setup

| Component | Board F242D (TX) | Board 8332 (RX) |
|-----------|------------------|-----------------|
| RP2040 serial | E663B035977F242D | E663B035973B8332 |
| Radio | LR2021 Gen 4, 2.4 GHz FLRC | LR2021 Gen 4, 2.4 GHz FLRC |
| ESP32-C3 | BOOTSEL control + UART bridge | BOOTSEL control + UART bridge |
| UART bridge | GPIO3(RX)/GPIO2(TX) | GPIO3(RX)/GPIO2(TX) |

---

## Results Summary

| Metric | Value | Status |
|--------|-------|--------|
| TX_DONE rate | 1000/1000 (100%) | CONFIRMED |
| TX throughput | 1293.6 kbps (Arduino SPI, 16MHz) | CONFIRMED |
| RX packet rate | 997/1000 (99.7%) | CONFIRMED |
| RX throughput | 1302.9 kbps | CONFIRMED |
| Packet error rate | 0.30% | CONFIRMED |
| Direct HW SPI throughput | UNTESTED (expected 1800+) | COMMITTED, NOT RUN |

---

## Root Causes Found and Fixed

Six root causes were identified and fixed to get the RF link working:

1. **Missing CLEAR_ERRORS before init** — stale errors blocked radio startup
2. **PA config byte 0x01 → 0x80** — HF PA select must be bit 7, not bit 0
3. **SET_RX/SET_TX 6→5 bytes** — extra trailing byte caused CMD_ERROR
4. **IRQ status cleared during TX poll** — GET_AND_CLEAR_IRQ_STATUS in wait loop cleared TX_DONE prematurely
5. **CALIBRATE bitmask 0x2F→0x6F** — wrong calibration image bitmask
6. **TX power not ×2** — LR2021 expects power register value doubled

Additional fixes applied in the optimization chain:
- Frequency overflow: `2440e6 / 0.00390625` overflowed uint32_t → send freq_Hz directly
- STDBY_XOSC → STDBY_RC between TX packets (STDBY_XOSC caused intermittent failures)
- Fs(0x03) fallback mode when XOSC calibration fails
- CALIBRATE 0x5F (TX image calibration) added per TX cycle
- DIO_IRQ re-armed per TX cycle

---

## Optimization Timeline

### Phase 1: Raw SPI Firmware (b9f9c93 → 68e98c9)
- Built raw SPI TX+RX firmware without RadioLib dependency
- Fixed 8 init bugs (frequency overflow, wrong opcodes, DIO/IRQ config)
- ESP32 UART bridge verified bidirectional (GPIO3(RX)/GPIO2(TX))

### Phase 2: RadioLib Integration (a73a0d3 → f902c83)
- Rewrote TX to use RadioLib beginFLRC() matching RX
- Measured TX 3172 kbps (but RX received 0 packets — frequency mismatch)
- Documented LR2021 SPI protocol reference from Rust driver + TheClams apps

### Phase 3: Root Cause Fixes (14be375 → eee6147)
- PA config bit 7 select + power×2
- CLEAR_ERRORS between TX cycles
- RX: SET_RX 5-byte command + CALIBRATE 0x6F
- RX: FIFO buffer check + CLEAR_ERRORS
- TX: STDBY_RC between TX + fix power to 12dBm HF max
- TX: Fs fallback + simplified TX loop + CALIBRATE 0x5F
- **TX: IRQ pin-only polling → 1000/1000 TX_DONE** (eee6147)

### Phase 4: RF Link Confirmed (87b8599)
- TX: 1000/1000 TX_DONE, 1292.8 kbps
- RX: 997/1000 received (99.7%), 1302.9 kbps
- Packet data verified: sequential seq numbers + correct payload

### Phase 5: Direct Hardware SPI (a423d6b) — COMMITTED, NOT TESTED
- Bypass Arduino byte-by-byte SPI overhead
- Write directly to RP2040 `spi0_hw` TX FIFO (8-deep HW FIFO)
- SPI clock 16MHz → 20MHz (LR2021 datasheet max)
- Tight GPIO register spin for IRQ (replaces millis() timeout)
- Pre-build packet payload once, update only 4 seq bytes per iteration
- Expected: 1800+ kbps

---

## Key Firmware Files

| File | Description |
|------|-------------|
| `firmware/rp2040/src/flrc_raw_tx.cpp` | TX firmware with direct HW SPI (latest) |
| `firmware/rp2040/src/flrc_tx_raw.cpp` | TX firmware (Arduino SPI baseline) |
| `firmware/rp2040/src/flrc_rx_raw.cpp` | RX firmware |

---

## Commit Chain (master)

```
a423d6b perf(flrc-tx): direct hardware SPI + 20MHz clock + register IRQ polling
87b8599 docs: FLRC RF LINK WORKING — 997/1000 RX, 1302.9 kbps
eee6147 fix(flrc-tx): IRQ pin polling — 1000/1000 TX_DONE
a99b64c fix(flrc-tx): Fs fallback mode + simplified TX loop + CALIBRATE 0x5F
bfcfcc5 fix(flrc-tx): STDBY_XOSC→STDBY_RC + re-set DIO_IRQ per TX cycle
45d419a docs: FLRC status update — RF link confirmed, TX CMD_ERROR analysis
df662ae fix(flrc-tx): restore STDBY between TX + fix power to 12dBm HF max
21b457c fix(flrc-rx): FIFO buffer check + CLEAR_ERRORS + doc root cause #3
5b108b4 fix(flrc-rx): SET_RX 5-byte command + CALIBRATE 0x6F + STDBY_RC fallback
5ed617c fix(flrc-tx): add CLEAR_ERRORS between TX cycles
0ec0288 docs: root cause #2 — PA select bit wrong (0x01 vs 0x80)
14be375 fix(flrc-tx): PA config bit 7 select + power×2 + TX diagnostics
f902c83 docs: FLRC throughput test results 2026-07-15
00f7565 docs: raw SPI test results — TX 3172kbps, RX 0 pkts, -707 root cause
```

---

## Next Steps

1. **Test direct HW SPI on hardware** — flash a423d6b to TX board, measure throughput
2. **If 1800+ kbps achieved** — update this doc with confirmed results
3. **RX optimization** — apply same HW SPI techniques to RX path
4. **PIO+DMA** — ultimate goal: gapless SPI via RP2040 PIO state machines
5. **Target: 2600+ kbps** with combined TX+RX optimizations
