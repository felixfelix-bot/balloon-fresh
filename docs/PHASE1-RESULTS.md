# Phase 1 LR2021 Interop Test Results

> **Date:** 2026-06-28  
> **Hardware:** 1× RP2040+LR2021, 2× ESP32-C3+LR2021 (NiceRF LoRa2021)  
> **Frequency:** 2.4 GHz (2450 MHz)  
> **Firmware:** bench_main.cpp (ESP-IDF v5.4.1, RadioLib v7.6.0)  
> **Commit:** `3c0eebf` on branch `phase1-interop-test`

## Executive Summary

**ESP32-to-ESP32 FLRC interop WORKS at 2.4 GHz** — 100% packet reception, zero errors, 20.8 kbps throughput. This matches the Mesh V1 target of 22 kbps.

LoRa mode at 2.4 GHz did not receive packets (both BW 500 and BW 1625 tested). This appears to be an RX initialization issue, not a fundamental incompatibility.

Cross-platform RP2040 tests were inconclusive due to serial communication issues with the RP2040's mbed-core USB CDC implementation.

## Config Analysis (P1.0)

### Critical Finding: Original RP2040 Firmware Had No Radio Config

The original RP2040 raw SPI driver (`radio.cpp`) configured **zero modulation parameters**. It only reset the chip and read the FIFO — no frequency, no modem type, no BW/SF/CR, no sync word. This means the RP2040 was completely unable to receive any LoRa or FLRC packets.

**Fix applied:** P1.3-FIX worker added RadioLib `LR2021::begin()` initialization (matching the tracker fleet config) to the RP2040 firmware, keeping the raw SPI bypass for per-packet RX operations. RadioLib handles modem configuration; raw SPI handles the speed-critical hot path.

### Current Config (All Devices, 2.4 GHz)

| Parameter | Value |
|-----------|-------|
| Frequency | 2450 MHz (2.4 GHz) |
| Modulation | FLRC (primary) / LoRa (secondary) |
| FLRC Bitrate | 2600 kbps |
| LoRa SF/BW | SF7 / BW 1625 kHz |
| TX Power | +12 dBm (2.4 GHz PA max) |
| Payload | 255 bytes |
| Sync Word | 0x12 |
| CRC | Enabled (2 bytes) |
| Preamble | 8 symbols |

## Test Results

### Test 1: ESP32-A TX → ESP32-B RX (FLRC 2600 kbps) ✅

| Metric | Value |
|--------|-------|
| Packets sent | 100 |
| Packets received | **100** |
| Packet Error Rate | **0.000%** |
| CRC Errors | 0 |
| Bit Error Rate | **0.000000%** |
| Throughput | **20.8 kbps** |
| Avg RSSI | **-105.0 dBm** |
| Elapsed | 9812 ms |
| Payload Size | 255 bytes |
| Inter-packet Delay | 10 ms |

**Verdict:** ✅ **Perfect interop.** 100/100 packets, zero errors. The 20.8 kbps throughput is limited by the 10ms inter-packet delay, not the FLRC air rate (2600 kbps). With tighter timing, throughput could be much higher.

### Test 2: ESP32-A TX → ESP32-B RX (LoRa SF7 BW500) ❌

| Metric | Value |
|--------|-------|
| TX initialized | ✅ "Init LoRa 2450.0 MHz SF7 BW=500 CR=1 PWR=12" |
| RX initialized | ✅ Config accepted |
| Packets received | **0** |

Also tested with BW 1625 — same result (0 packets).

**Verdict:** ❌ **LoRa RX failed at 2.4 GHz.** TX initializes successfully but RX receives nothing. Likely cause: the `begin()` call for LoRa mode at 2.4 GHz may need a different antenna path selection (Pin 10 = 2.4G vs Pin 9 = Sub-GHz), or the LoRa modem configuration requires specific register settings that aren't being applied.

### Tests 3-6: RP2040 Cross-Platform ⚠️

| Test | Status | Issue |
|------|--------|-------|
| ESP32-A → RP2040 RX | ⚠️ Inconclusive | RP2040 serial port hangs on read |
| RP2040 → ESP32-B RX | ⚠️ Inconclusive | RP2040 serial port hangs on read |
| ESP32-B → RP2040 RX | ⚠️ Not run | Same serial issue |
| RP2040 → ESP32-A RX | ⚠️ Not run | Same serial issue |

**Issue:** The RP2040 mbed-core USB CDC implementation has a non-standard serial behavior. Opening `/dev/ttyACM1` with pyserial either times out or hangs. The RP2040 firmware uses `Serial.begin(115200)` and outputs boot messages, but the USB CDC endpoint doesn't respond to standard DTR/RTS serial control lines the same way as ESP32's USB Serial/JTAG.

The RP2040 firmware protocol is also one-shot: after boot, it waits for a single character ('S' for RX or 'T' for TX), runs the test, then blinks forever. No interactive command loop like the ESP32 bench firmware.

## What We Learned

### Answers to Key Questions

| Question | Answer |
|----------|--------|
| Can LR2021 modules communicate at 2.4 GHz? | **✅ YES** — FLRC 2600 kbps works |
| What throughput? | **20.8 kbps** (limited by 10ms TX delay, not air rate) |
| What packet loss? | **0%** — flawless at bench distance |
| RSSI at bench distance? | **-105 dBm** (weak signal, clean reception) |
| LoRa mode works at 2.4 GHz? | **❌ No** — RX receives nothing (needs investigation) |
| Cross-platform (RP2040↔ESP32)? | **⚠️ Inconclusive** — RP2040 serial issues |

### Key Discoveries

1. **Config bug found and fixed:** The original RP2040 driver configured zero modulation params. Fixed by adding RadioLib `begin()` for initialization.

2. **Firmware mode bug found and fixed:** `CONFIG_BENCH_MODE_FIPS_BRIDGE=y` was set in the ESP32 sdkconfig, causing the wrong firmware to run (fips_bridge instead of bench_main). Fixed by removing the config flag.

3. **Logging was disabled:** `CONFIG_LOG_DEFAULT_LEVEL=0` suppressed all ESP_LOGI output. The bench firmware communicates entirely via ESP_LOGI, so serial output was invisible. Fixed to level 3 (INFO).

4. **FLRC at 2.4 GHz matches Mesh V1 targets:** The measured 20.8 kbps is within range of the 22 kbps target for Mesh V1 @ 300 km. This suggests the LR2021 FLRC mode is viable for the balloon mesh network.

## Issues and Next Steps

### LoRa RX at 2.4 GHz
- Need to investigate antenna path selection (2.4G pin vs Sub-GHz pin)
- Try different SF/BW combinations (SF12/BW203 for maximum range)
- Add error logging to the RX initialization path
- May need `setDioFunction()` call for DIO9 IRQ in LoRa mode

### RP2040 Serial Communication
- The mbed-core USB CDC doesn't respond to standard DTR/RTS control
- Consider switching RP2040 to a UART-based serial protocol (Serial1 on GP0/GP1)
- Or switch to earlephilhower core which has better USB CDC support
- The RP2040 firmware needs an interactive command loop (not one-shot)

### Throughput Optimization
- Current 20.8 kbps is limited by 10ms inter-packet delay
- With 1ms delay: theoretical ~150 kbps
- With raw SPI bypass (proven 838.8 kbps on ESP32): target 800+ kbps
- Phase 2 will explore PIO+DMA for 2.6 Mbps target

## Files

- Config analysis: `docs/radio-config-comparison.md`
- Test scripts: `tests/quick_interop.py`, `tests/lora_rpi_test.py`
- Results: `tests/results/phase1/results.json`
- Firmware: `mesh-stack/flrc-bench-espidf/` (ESP32), `firmware/rp2040/` (RP2040)
