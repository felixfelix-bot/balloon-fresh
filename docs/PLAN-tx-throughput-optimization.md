# TX Throughput Optimization Plan

## Goal
Push sustained FLRC throughput at 2600 kbps from 1485 kbps (57%) toward 2600 kbps (100%).

## Current State (Baseline)
- Per-packet cycle: 680 µs
- Air time: 390 µs (57%)
- Overhead: 290 µs (43%)
  - SPI bus: 57 µs (4 transactions, 142 bytes total)
  - SDK overhead: 20 µs (beginTransaction/endTransaction × 4)
  - Chip processing: 213 µs (BUSY wait: PLL settle, PA ramp, state machine)

## Optimization Steps (Binary/Exponential — measure each independently)

### Step 1: Skip rfClearTxFifo() per packet
- After TX_DONE, TX FIFO is auto-cleared by chip
- Remove `rfClearTxFifo()` call from TX loop
- Saves: 1 SPI round-trip (~15-20 µs)
- Risk: LOW — datasheet says FIFO auto-clears on TX_DONE

### Step 2: Skip rfClearIrq() per packet
- Instead of clearing IRQ flags via SPI each packet, just poll the IRQ GPIO pin
- Clear IRQ once at start, then use `rfReadIrqStatus()` only for error checking
- Actually: simpler — just poll IRQ pin for TX_DONE, clear IRQ via SPI only every N packets
- Saves: 1 SPI round-trip (~15-20 µs)
- Risk: LOW — IRQ pin stays high until cleared, we just re-read it

### Step 3: Batch SPI commands
- Combine remaining commands (WRITE_FIFO + SET_TX) into single CS-low session
- Send: [WRITE_FIFO header + data] [SET_TX] in one SPI transfer
- Saves: 1 CS toggle + 1 beginTransaction/endTransaction (~10 µs)
- Risk: MEDIUM — chip may need BUSY check between FIFO write and SET_TX

### Step 4: Increase SPI clock
- Try 40 MHz (RP2040 supports up to 62.5 MHz)
- Check LR2021 datasheet for max SPI clock
- Saves: ~50% of SPI bus time (~28 µs → ~14 µs)
- Risk: LOW — if chip supports it, pure win

### Step 5: Auto-TX / FIFO auto-refill
- Check if LR2021 supports continuous TX mode or FIFO auto-refill
- If chip can auto-transmit when FIFO has data, skip SET_TX command entirely
- Saves: 1 SPI round-trip + chip state machine time (~100+ µs)
- Risk: MEDIUM — need to verify chip capability

### Step 6: Double-buffer (write next packet during current TX)
- While chip is transmitting packet N, write packet N+1 to FIFO
- Only wait for TX_DONE if FIFO is full
- Saves: overlaps SPI write with air time (~57 µs hidden behind 390 µs air time)
- Risk: MEDIUM — need to manage FIFO depth, avoid overflow

### Step 7: Minimize SDK overhead
- Replace beginTransaction/endTransaction with direct register writes
- Use DMA for SPI transfers (non-blocking)
- Saves: ~20 µs SDK overhead
- Risk: MEDIUM — bypasses SPI library safety

## Measurement Protocol
Each step: flash optimized firmware, run 10s sustained test at 2600 kbps, record:
- TX throughput (kbps)
- Per-packet cycle time (µs)
- Packet count
- 0% PER confirmed

Only proceed to next step if previous step shows improvement.
If step shows no improvement or breaks, revert and note.

## Expected Cumulative Improvement
| Step | Savings (µs) | Cumulative cycle (µs) | Expected throughput (kbps) |
|------|-------------|----------------------|---------------------------|
| Baseline | 0 | 680 | 1485 |
| 1 (skip clearFIFO) | 15 | 665 | 1520 |
| 2 (skip clearIRQ) | 15 | 650 | 1555 |
| 3 (batch commands) | 10 | 640 | 1580 |
| 4 (40 MHz SPI) | 14 | 626 | 1615 |
| 5 (auto-TX) | 100 | 526 | 1920 |
| 6 (double-buffer) | 57 | 469 | 2155 |
| 7 (DMA SPI) | 20 | 449 | 2250 |

Theoretical floor: 390 µs (air time only) = 2600 kbps.
Chip processing floor: ~200 µs (PA ramp + PLL) = ~1600 kbps with full optimization.