# Throughput Optimization Plan

## Overview
Incremental optimization of the RX pipeline to maximize throughput.
Three board variants (ADR-015): Board A (ESP32-C3 solo), Board B (+RP2040), Board C (+FPGA).
Board A optimization COMPLETE: 838.8 kbps achieved (8.3x improvement over baseline).
FIPS-over-FLRC bridge (Path A) in progress — bridge relay verified, handshake debugging.

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

### Board A: ESP32-C3 Solo (software optimization, FREE)
- [x] Write THROUGHPUT-OPTIMIZATION-PLAN.md
- [x] Create fast_rx.cpp (6 optimization configs)
- [x] Add NVS logging to fifo_tx.cpp (resilient TX)
- [x] Build fast_rx.bin and fifo_tx.bin
- [x] **Fix frequency: 868 MHz + 2450 MHz both confirmed working**
- [x] **Implement raw SPI bypass (14ms → 188µs per packet)**
- [x] **Implement no-STBY continuous RX (keep radio in RX mode)**
- [x] **Implement raw SPI TX (writeTxFifo + setTx + delay)**
- [x] **Implement high-priority task + task notification**
- [x] **Run Phase C test: 838.8 kbps verified (500/500 unique, 0% PER)**
- [x] Test 160 MHz CPU (no improvement, 80 MHz optimal)
- [x] Document results in RESULTS.md
- [x] Commit and push

### Board A.5: FIPS-over-FLRC Bridge (Path A)
- [x] Write fips_bridge.cpp (SLIP relay, raw SPI, 2.4 GHz)
- [x] Build FIPS binary (`cargo build`)
- [x] Create FIPS configs (node-a.yaml, node-b.yaml)
- [x] Fix SerialConfig field names (virtual_mtu, deny_unknown_fields)
- [x] Flash bridge firmware to both boards
- [x] Verify bridge relay works (manual SLIP test confirmed)
- [x] Verify FIPS A sends data through bridge (524 bytes at ACM1)
- [ ] **Fix FIPS B handshake (root cause under investigation)**
- [ ] Test ping6 end-to-end
- [ ] Test UDP throughput (iperf3)
- [ ] See FIPS-BRIDGE-STATUS.md for details

### Board B: RP2040 Coprocessor (when RP2040-Zero arrives)
- [ ] Wire RP2040 to LR2021 (SPI0) + ESP32-C3 (UART)
- [ ] Write PIO SPI master program (hardware-driven radio I/O)
- [ ] Write dual-core firmware (Core 0: radio, Core 1: protocol)
- [ ] Measure throughput with PIO handling radio
- [ ] Compare with Board A inline SPI results
- [ ] Design custom PCB for flight (optional)

### Board C: iCE40 UP5K FPGA (JLCPCB design phase)
- [ ] Design schematic: ESP32-C3 + iCE40 + LR2021 + config flash
- [ ] Design PCB layout in KiCad
- [ ] Order 5 boards from JLCPCB (~$15-20 each)
- [ ] Write Verilog: SPI master + packet queue
- [ ] Write Verilog: N×N crossbar (for multi-radio)
- [ ] Assemble and test
- [ ] Benchmark full 2600 kbps air rate

## RP2040-Zero Pin Assignment (for Phase D)
```
LR2021 #1:  SPI0 (GP2=CK, GP3=MOSI, GP4=MISO, GP5=CS, GP6=BUSY, GP7=IRQ, GP8=RST)
LR2021 #2:  SPI1 (GP10=CK, GP11=MOSI, GP12=MISO, GP13=CS, GP14=BUSY, GP15=IRQ, GP16=RST)
ESP32-C3:   UART (GP20=TX, GP21=RX) or SPI
Power ctrl: GP9 (MOSFET gate for ESP32-C3 wake/sleep)
```
