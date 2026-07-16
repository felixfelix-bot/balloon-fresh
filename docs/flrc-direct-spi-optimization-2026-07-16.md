# FLRC Direct Hardware SPI Optimization — 2026-07-16

## Status: UNTESTED ON HARDWARE

Code committed but not yet run on RP2040. Previous baseline (Arduino SPI):
1000/1000 TX_DONE, 1293.6 kbps.

## What Changed

### 1. Direct Hardware SPI (bypass Arduino overhead)
- New `spiWriteBurst()` — writes directly to RP2040 `spi0_hw` TX FIFO (8-deep HW FIFO)
- No `spi.beginTransaction()` / `transfer()` byte-by-byte overhead
- `spiDrain()` flushes RX FIFO after each CS cycle
- All `rfWriteCmd()` calls now use hardware registers, not Arduino SPI class

### 2. SPI Clock 16MHz → 20MHz
- `#define SPI_FREQ_HZ 20000000UL` (was 16MHz)
- LR2021 datasheet: SPI max 20MHz

### 3. Tight GPIO Spin for IRQ
- Replaced `millis()` timeout loop with `sio_hw->gpio_in` register poll
- Spin counter (500000 iterations max) — no function call overhead in hot loop
- Direct register read: `sio_hw->gpio_in & irqMask`

### 4. Hot Loop Optimizations
- Pre-build packet payload ONCE, only update 4 seq bytes per iteration
- Static const command arrays (avoid stack alloc per iteration)
- Inline CLR_IRQ + WRITE_TX_FIFO + SET_TX as direct SPI bursts (no function calls)
- Progress output every 500 (was 100) — less Serial overhead
- Status read only for first 5 packets (diagnostic)

## Expected Improvement
- Baseline: 1293.6 kbps (50% of 2600 kbps FLRC max)
- Bottleneck was Arduino SPI byte-by-byte + function call overhead
- Hardware SPI FIFO + 20MHz clock should push toward 1800+ kbps
- Pre-built packet + register polling removes remaining per-packet overhead

## What Needs Testing
1. Flash optimized firmware to TX Pico (F242D)
2. Run 1000-packet TX burst
3. Verify TX_DONE count still 1000/1000
4. Measure new throughput
5. If working, run TX→RX full test with RX Pico (8332)

## Files Changed
- `firmware/rp2040/src/flrc_raw_tx.cpp` — direct SPI + 20MHz + register polling
