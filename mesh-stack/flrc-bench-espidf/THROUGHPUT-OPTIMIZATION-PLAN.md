# Throughput Optimization Plan

## Overview
Incremental optimization of the ESP32-C3 RX pipeline to maximize throughput.
Phase 2 proved SPI bus reads at 10.46 Mbps (255B in 195µs) — the bottleneck
is per-packet processing overhead (15-20ms). This plan eliminates that overhead
step by step, measuring each optimization's contribution.

## Hardware
- RX board: ESP32-C3 (MAC C6:98) + LR2021, ttyACM1
- TX board: ESP32-C3 (MAC 96:DC) + LR2021, runs from power bank (no USB needed)
- RP2040-Zero ordered for Phase D (multi-radio prototype)

## Phase C: Per-Packet Optimization (6 configs, measured independently)

| Config | Optimization | Expected Time/Pkt | Expected Throughput |
|--------|-------------|-------------------|---------------------|
| 1 | Baseline (current code) | 15-20ms | ~80 kbps |
| 2 | Skip PRBS verification | 5-10ms | ~150-200 kbps |
| 3 | + Skip getRSSI per-pkt | 4-9ms | ~200-300 kbps |
| 4 | + Fixed 255B (skip getPktLen) | 3-8ms | ~250-400 kbps |
| 5 | + Inline SPI (bypass RadioLib) | 1-4ms | ~400-800 kbps |
| 6 | + taskYIELD (no vTaskDelay) | 0.5-2ms | ~500-1000+ kbps |

## Resilient TX (runs from power bank, no USB needed)
- Loops through all burst sizes (20B, 50B, 100B, 255B × 100 pkts each)
- Logs results to NVS flash
- Data recoverable via range_dump.bin
- One-time USB flash, then disconnect and run on power

## Checklist

### Step 1: Code (no hardware needed)
- [ ] Write THROUGHPUT-OPTIMIZATION-PLAN.md
- [ ] Create fast_rx.cpp (6 optimization configs)
- [ ] Add NVS logging to fifo_tx.cpp (resilient TX)
- [ ] Add CONFIG_BENCH_MODE_FAST_RX to Kconfig
- [ ] Update CMakeLists.txt + bench_main.cpp guard
- [ ] Build fast_rx.bin and fifo_tx.bin
- [ ] Commit and push

### Step 2: Test (when TX board briefly available)
- [ ] Flash resilient fifo_tx.bin to flaky board (96:DC)
- [ ] Disconnect USB, attach power bank
- [ ] Flash fast_rx.bin to stable board (C6:98)
- [ ] Run Phase C: measure all 6 optimization configs
- [ ] Run Phase A: FIFO depth discovery (from fifo_test.bin)
- [ ] Flash range_dump.bin to both boards, recover NVS data
- [ ] Document results in RESULTS.md

### Step 3: Phase B — DMA Streaming (if Phase A shows FIFO batching)
- [ ] Create dma_rx.cpp with FIFO threshold + DMA burst read
- [ ] Configure autoTxRx() for continuous reception
- [ ] Benchmark sustained throughput
- [ ] Target: 800-2000 kbps

### Step 4: Phase D — RP2040 Multi-Radio (when RP2040-Zero arrives)
- [ ] Wire 2x LR2021 to RP2040-Zero (SPI0 + SPI1)
- [ ] Write PIO SPI master firmware for RP2040
- [ ] Test dual-radio bent-pipe relay
- [ ] Measure power consumption and latency

## RP2040-Zero Pin Assignment (for Phase D)
```
LR2021 #1:  SPI0 (GP2=CK, GP3=MOSI, GP4=MISO, GP5=CS, GP6=BUSY, GP7=IRQ, GP8=RST)
LR2021 #2:  SPI1 (GP10=CK, GP11=MOSI, GP12=MISO, GP13=CS, GP14=BUSY, GP15=IRQ, GP16=RST)
ESP32-C3:   UART (GP20=TX, GP21=RX) or SPI
Power ctrl: GP9 (MOSFET gate for ESP32-C3 wake/sleep)
```
