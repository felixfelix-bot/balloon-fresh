# ESP32 FLRC Speed Test Plan — 2026-07-27

## Goal
Exceed RP2040's 1377 kbps on ESP32-C3. Target: 2000+ kbps, ideally air-time ceiling (2540 kbps).

## Hardware
- 2x ESP32-C3 Mini V1 boards connected
  - /dev/ttyACM0 (serial: B0:A6:04:00:96:DC)
  - /dev/ttyACM1 (serial: 88:56:A6:7B:C6:98)
- Both have LR2021 radios wired (SCK=6, MISO=2, MOSI=7, NSS=10, BUSY=4, RST=3, DIO9=5)

## What Already Exists
1. `mesh-stack/flrc-bench-espidf/main/fifo_tx.cpp` — raw SPI FLRC TX (bypasses RadioLib hot path)
2. `mesh-stack/flrc-bench-espidf/main/fast_rx.cpp` — raw SPI FLRC RX with ISR task notification
3. `mesh-stack/flrc-bench-espidf/main/EspHalC3.h` — ESP32 HAL (needs GDMA upgrade from feat/esp32-spi-gdma)
4. Kconfig build system for selecting TX/RX modes
5. `feat/esp32-spi-gdma` branch has optimized HAL: 40 MHz SPI, batch DMA, async queue

## Plan

### Phase 1: Merge GDMA HAL
- Cherry-pick GDMA EspHalC3.h from feat/esp32-spi-gdma into speed-sustained-sweep branch
- Verify the HAL is compatible with fifo_tx.cpp and fast_rx.cpp (same API surface)

### Phase 2: Build TX Firmware
- Configure: CONFIG_BENCH_MODE_FIFO_TX=y
- Build: `idf.py build`
- Flash to /dev/ttyACM0 (TX board)

### Phase 3: Build RX Firmware
- Configure: CONFIG_BENCH_MODE_FAST_RX=y
- Build: `idf.py build`
- Flash to /dev/ttyACM1 (RX board)

### Phase 4: Run Coordinated Test
- Start RX first (serial command or auto-start)
- Start TX (auto-start after 5s delay)
- Capture serial output from both
- Measure: TX throughput, RX packet count, RX throughput

### Phase 5: Analyze + Iterate
- If throughput < 2000 kbps: identify bottleneck
- If GDMA fails with LR2021: fall back to raw SPI at 20 MHz (still > RP2040)
- If working: increase packet count, measure sustained throughput

## Success Criteria
- TX throughput > 1377 kbps (RP2040 baseline)
- RX receives > 0 packets (RF link works)
- Ideally: RX throughput > 1377 kbps

## Key Metrics to Report
- TX packets sent / TX_DONE count
- RX packets received / RX throughput
- Per-packet timing (if profiler mode available)
- Packet loss rate
