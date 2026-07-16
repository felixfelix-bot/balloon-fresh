# SPI Frequency Sweep Results — 2026-07-16

## Methodology

Runtime sweep firmware (flrc_raw_tx_sweep.cpp) accepts `SETSPI <freq>` command to change SPI clock at runtime, then `RUN` to execute 1000-packet TX burst.

## Results

| Requested | Actual (Pico SDK) | Elapsed | Throughput | spin=0? | Real? |
|-----------|-------------------|---------|------------|---------|-------|
| 6.25 MHz  | 6.0 MHz           | 447 ms  | 4564 kbps  | Yes (pkt 1+) | NO — radio broken by SETSPI re-init |
| 7.81 MHz  | 6.0 MHz           | 445 ms  | 4584 kbps  | Yes     | NO |
| 10.42 MHz | 8.0 MHz           | 340 ms  | 6000 kbps  | Yes     | NO |
| 12.50 MHz | 12.0 MHz          | 235 ms  | 8681 kbps  | Yes     | NO |
| 15.62 MHz | 12.0 MHz          | 234 ms  | 8718 kbps  | Yes     | NO |
| 18.00 MHz | 12.0 MHz          | 234 ms  | 8718 kbps  | Yes     | NO |
| 20.83 MHz | 12.0 MHz          | 234 ms  | 8718 kbps  | Yes     | NO |

## Critical Findings

### 1. Runtime SETSPI breaks radio
ALL sweep results are FAKE. spin=0 on every packet after packet 0 means the IRQ pin fires instantly — the radio is not actually transmitting. The `SETSPI` command calls `spi_deinit()` + `spi_init()` which tears down and rebuilds the SPI peripheral, breaking the LR2021's SPI connection. The radio never re-syncs.

**RX board received ZERO packets during the entire sweep — confirmed no actual RF transmission.**

### 2. Pico SDK baudrate capping
The RP2040 Pico SDK `spi_set_baudrate()` doesn't achieve all requested frequencies:
- Requests ≥12 MHz all map to 12.0 MHz actual
- The prescaler+postdiv calculation caps at 12 MHz for this peripheral configuration
- This means our "16MHz" v4 firmware was actually running at 12 MHz, not 15.625 MHz

### 3. Compile-time SPI frequency is required
Runtime SPI clock changes break the LR2021 radio. To test different SPI frequencies, each must be a separate firmware build with a different compile-time `#define SPI_FREQ_HZ`.

## Proven Data Points (compile-time, no runtime re-init)

| Compile-time | Actual (Pico SDK) | TX Throughput | RX Loss | Verified? |
|-------------|-------------------|---------------|---------|-----------|
| 16 MHz | 12.0 MHz* | 1367 kbps | 0% (1000/1000) | YES — v4 baseline |
| 20 MHz | 12.0 MHz* | 1377 kbps | 0% (1091 unique) | YES — 20MHz variant |

*Both likely achieved the same 12 MHz actual clock, explaining the negligible 10 kbps difference.

## Conclusion

**SPI clock is NOT the throughput bottleneck.** Both 16MHz and 20MHz requests map to 12 MHz actual, and the difference is within measurement noise. The bottleneck is the per-byte Arduino `transfer()` function call overhead + the IRQ pin polling loop + the sequential CLR_IRQ→WRITE_FIFO→SET_TX→wait command sequence.

To improve throughput beyond ~1370 kbps, need:
1. Batch SPI transfer (Phase 3 — UF2 built, not yet tested)
2. FIFO pipelining (Phase 4 — UF2 built, not yet tested)
3. Reduced command overhead (combined CS assertions)