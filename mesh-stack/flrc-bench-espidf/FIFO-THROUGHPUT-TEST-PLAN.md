# FIFO Throughput Test Plan

## Overview
Test the LR2021's native FIFO capabilities to determine if high throughput (800+ kbps)
is achievable on ESP32-C3 without extra hardware. Uses RADIOLIB_GODMODE to access
private FIFO API methods.

## Zero-Patch Solution
RadioLib has built-in `RADIOLIB_GODMODE` flag. Define it as 1 before including RadioLib.h
to make all private/protected methods public. No RadioLib file modifications needed.

## Native FIFO API (available via GODMODE)
- `readRadioRxFifo(data, len)` — single-frame FIFO read
- `getRxFifoLevel(&level)` — returns uint16_t (may be >256 bytes!)
- `clearRxFifo()` — clear RX FIFO
- `configFifoIrq(rxIrq, txIrq, rxHighThresh, txHighThresh)` — set threshold interrupts
- `getFifoIrqFlags(&rxFlags, &txFlags)` — read FIFO interrupt flags
- `autoTxRx(delay, mode, timeout)` — auto RX-TX mode
- `getRxPktLength(&len)` — get packet length

## Test Phases

### Phase 1: FIFO Depth Discovery
- TX sends burst of N packets (no delay)
- RX waits 3s, queries getRxFifoLevel()
- Question: Is FIFO level > 1 packet size?
- Sizes: 20B, 50B, 100B, 255B

### Phase 2: FIFO Read Speed
- Time readRadioRxFifo() for 20B to 256B
- Calculate effective SPI throughput

### Phase 3: Auto-RX Mode
- Configure autoTxRx()
- TX sends burst
- Does radio stay in RX and accumulate without MCU intervention?

### Phase 4: FIFO Threshold Interrupt
- Configure configFifoIrq() with HIGH threshold
- Measure threshold-to-read latency

### Phase 5: End-to-End Throughput
- FIFO batch + no PRBS + 255B packets
- Sustained throughput measurement

## Checklist

- [ ] Write FIFO-THROUGHPUT-TEST-PLAN.md
- [ ] Rewrite fifo_test.cpp with RADIOLIB_GODMODE + native FIFO API
- [ ] Create fifo_tx.cpp burst transmitter
- [ ] Add CONFIG_BENCH_MODE_FIFO_TX to Kconfig
- [ ] Update CMakeLists.txt with fifo_tx.cpp
- [ ] Update bench_main.cpp guard
- [ ] Build fifo_test.bin (RX)
- [ ] Build fifo_tx.bin (TX)
- [ ] Flash fifo_test.bin to stable board (C6:98)
- [ ] Flash fifo_tx.bin to TX board when available
- [ ] Run Phase 1: FIFO depth discovery
- [ ] Run Phase 2: FIFO read speed
- [ ] Run Phase 3: Auto-RX mode
- [ ] Run Phase 5: End-to-end throughput
- [ ] Document results in RESULTS.md
- [ ] Commit and push

## Expected Outcomes
| Outcome | Meaning | Next Step |
|---------|---------|-----------|
| FIFO > 1 pkt | FIFO batches! | DMA streaming → 800+ kbps |
| FIFO = 1 pkt | Single-pkt buffer | Need RP2040/FPGA coprocessor |
| readRadioRxFifo fast | SPI not bottleneck | Reduce round-trips |
| autoTxRx works | No manual RX restart | Major RX pipeline simplification |
