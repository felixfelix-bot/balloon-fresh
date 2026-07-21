# Single-Batch SPI Technique — Cross-Reference

## What

Single-batch SPI = pre-concatenate the 2-byte FIFO header + payload into ONE contiguous buffer, then call `spiRf.transfer(buf, nullptr, len)` ONCE. This ensures SCK runs continuously for the entire transfer — no gap between header and payload bytes.

The previous per-byte approach called `spiRf.transfer(buf[i])` in a loop, one byte at a time. Each call drains the SPI FIFO, causing SCK to stop briefly between bytes. The single-batch approach eliminates these gaps entirely.

## Why

| Metric | Per-byte SPI | Single-batch SPI | Delta |
|--------|-------------|-------------------|-------|
| Throughput | 1377 kbps | 1733 kbps | **+25.9%** |
| TX_DONE | — | 1000/1000 | ✅ Proven |

Proven in balloon-speed-tests with TX_DONE=1000/1000 — zero packet loss, confirming that batch SPI works with the LR2021 as long as SCK is continuous.

## How

Reference implementation: `firmware/rp2040/src/flrc_raw_tx_single_batch.cpp` (balloon-speed-tests, commit 9514610, branch `speed-optimization`).

### Key changes (3 functions):

1. **`rfWriteCmd`** — Replace per-byte loop with single batch:
   ```cpp
   // OLD: for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
   // NEW:
   spiRf.transfer(buf, nullptr, len);  // SINGLE BATCH — continuous SCK
   ```

2. **`rfWriteTxFifo`** — Pre-concatenate header + payload into `fifoCmd[]`, then one transfer:
   ```cpp
   static uint8_t fifoCmd[2 + 255];  // pre-allocated near top of file

   static void rfWriteTxFifo(const uint8_t *data, size_t len) {
       fifoCmd[0] = 0x00;  // header MSB
       fifoCmd[1] = 0x02;  // header LSB (WRITE_TX_FIFO)
       memcpy(fifoCmd + 2, data, len);

       rfWaitBusy();
       spiRf.beginTransaction(spiSettings);
       digitalWrite(PIN_CS, LOW);
       spiRf.transfer(fifoCmd, nullptr, 2 + len);  // SINGLE BATCH
       digitalWrite(PIN_CS, HIGH);
       spiRf.endTransaction();
   }
   ```

3. **`rfReadIrqStatus`** — Use batch transfer for both the command write and the data read:
   ```cpp
   // Command write: batch
   uint8_t cmd[2] = { 0x01, 0x17 };
   spiRf.transfer(cmd, nullptr, 2);
   // Data read: batch
   uint8_t dummy[6] = {0, 0, 0, 0, 0, 0};
   spiRf.transfer(dummy, buf, 6);  // batch read
   ```

### Why not two separate `transfer()` calls?

Two separate `transfer()` calls (one for header, one for payload) cause SCK discontinuity. The RP2040 `spi_write_blocking` function drains the SPI FIFO between calls, so SCK stops briefly. The LR2021 may reject transfers with SCK gaps. Pre-concatenating into one buffer and calling `transfer()` once ensures SCK runs continuously for the entire 257-byte transfer.

## Where

| Repository | Branch | Commit | File | Status |
|-----------|--------|--------|------|--------|
| balloon-speed-tests | `speed-optimization` | `9514610` | `firmware/rp2040/src/flrc_raw_tx_single_batch.cpp` | **Proven** (1733 kbps, 1000/1000) |
| balloon-range-tests | `range-tests` | this commit | `firmware/rp2040/src/flrc_range_tx_auto.cpp` | **Ported** |

## Impact for Range Tests

Higher TX throughput means more packets per burst at each distance, giving better statistical confidence in range measurements.

### The range test question

**"What throughput at what distance?"**

The single-batch technique raises the throughput ceiling. At close range (10m), throughput should be near the single-batch maximum (~1733 kbps). As distance increases, packet loss increases and effective throughput drops. The distance-vs-throughput curve tells us the practical range of the FLRC link.

### Recommended test matrix

| Bitrate (kbps) | Distances to test |
|-----------------|-------------------|
| 1300 | 10m, 25m, 50m, 100m |
| 2600 | 10m, 25m, 50m, 100m |

At each distance/bitrate combination, run a 500-packet burst and record:
- `fired` (TX_DONE count)
- `timeout` count
- `elapsed_ms`
- `throughput_kbps`

This builds a distance-vs-throughput curve for each bitrate, showing the practical range envelope.

### Why bitrate matters

Lower bitrates (1300 kbps) have better sensitivity and should work at longer distances. Higher bitrates (2600 kbps) maximize throughput but may degrade sooner with distance. Testing both gives a complete picture of the FLRC range/throughput tradeoff.

## Summary

The single-batch SPI technique is a proven, zero-cost firmware optimization that increases TX throughput by 25.9%. It has been ported from balloon-speed-tests to balloon-range-tests to maximize the number of packets per burst, improving statistical confidence in outdoor range measurements.