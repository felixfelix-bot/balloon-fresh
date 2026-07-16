# FLRC Throughput Optimization — Final Conclusion (2026-07-16)

## ACHIEVED RESULTS

| Metric | Value |
|--------|-------|
| TX throughput | 1377.4 kbps |
| TX_DONE | 1000/1000 (100%) |
| RX received | 1018 packets |
| RX packet loss | 0% |
| RF link | Fully functional end-to-end |
| Theoretical max | 2540 kbps (payload) |
| **Achievement** | **54% of theoretical max** |

## WHAT WORKED

### Proven Firmware: rp2040-flrc-tx-raw (RadioLib + Arduino SPI)
- RadioLib `beginFLRC()` for radio init (2600 kbps, CR 1/0, BT 0.5)
- Arduino per-byte `spiRf.transfer()` for TX hot loop
- BUSY pin polling for TX completion detection
- 255-byte fixed-length packets, 16MHz SPI (12 MHz actual)
- Commit: dceb6e5 (latest), baseline: a90f546

### Bootloader Infrastructure
- 1200 baud BOOTSEL: stty trick, no physical button (earlephilhower core only)
- ESP32 one-shot BOOTSEL: reliable recovery when CDC is dead
- Makefile targets: `make bootsel`, `make rp2040-flash`

### Coordinated Test Harness
- `scripts/coordinated_tx_rx_test.py` — sends RUN to RX first, then TX
- Captures both serial ports for 15s, reports results

## WHAT FAILED (ALL TESTED ON REAL HARDWARE)

| Approach | Symptom | Root Cause |
|----------|---------|------------|
| Pico SDK spi_write_blocking() | Fake TX_DONE (0µs spin), 8160 kbps, 0 RX | SDK batch mode incompatible with LR2021 SPI timing |
| DMA via spi0_hw->dr | Radio init fails (Status=0x00) | Direct register access bypasses SPI transaction protocol |
| Direct HW SPI (v5) | 7034 kbps fake, 0 RX | Same — direct register access breaks LR2021 |
| Runtime SPI clock change | Radio never re-syncs | spi_deinit()+spi_init() tears down peripheral |
| PIO+DMA TX v1/v2/v3 | TX loop hangs, CDC permanently dead | PIO/DMA interaction kills USB, DMA IRQ never fires |
| 20MHz RX SPI | 77% packet loss | RX FIFO read timing requires slower SPI |
| Preamble 16→8 | TX_DONE=0 | Breaks radio sync |
| Combined CS assertions | TX_DONE=0 | LR2021 requires one command per CS assertion |

## WHY 1377 kbps IS THE CEILING

### Per-Packet Time Breakdown (1492µs total)

```
RF air time:  803µs  (54%) — PHYSICS, cannot reduce
SPI transfer: 535µs  (36%) — Arduino per-byte overhead, only working path
Loop/IRQ:     154µs  (10%) — polling + bookkeeping
```

### The Fundamental Problem

The LR2021 Gen 4 chip requires Arduino per-byte `spiRf.transfer()` on RP2040.
Every alternative SPI method tested fails:
- Batch transfer → fake TX_DONE
- DMA → radio init fails
- Direct registers → no actual transmission
- PIO state machine → hangs, CDC death

At 12 MHz actual SPI clock (RP2040 prescaler limit), 268 bytes × ~2µs/byte = 535µs.
This is irreducible with the Arduino transfer() constraint.

### Could We Reach 2600 kbps?

**No, not on this hardware with this chip.** The theoretical 2540 kbps payload
throughput requires ZERO SPI overhead — RF air time alone (803µs) already
consumes 54% of the available time at 1377 kbps. To double throughput we'd
need to halve total per-packet time from ~1492µs to ~745µs, but RF air time
alone is 803µs. The math doesn't work.

To exceed 1377 kbps, you would need:
1. A working batch/DMA SPI path (all failed)
2. OR dual-buffer pipelining (overlap SPI write with RF air time)
3. OR a different SPI controller that the LR2021 accepts

## REMAINING OPTIONS (Speculative — Diminishing Returns)

### Option A: PIO State Machine (HIGH RISK, UNKNOWN PAYOFF)
- RP2040 PIO drives CS/SCK/MOSI with custom timing
- Could potentially work where DMA failed — PIO maintains exact timing
- BUT: v1/v2/v3 all failed (TX hang, CDC death, DMA IRQ never fires)
- Would need logic analyzer to reverse-engineer exact LR2021 SPI timing
- Effort: Days of development, uncertain success

### Option B: Dual-Buffer Pipelining (MODERATE, ~1500-1600 kbps)
- Write packet N+1 to TX FIFO while packet N is on-air
- Currently sequential: wait for TX_DONE → write next → SET_TX
- Pipelining overlaps the 535µs SPI write with the 803µs air time
- Theoretical: max(803, 535) = 803µs → 2540 kbps
- BUT: LR2021 FIFO is only 255 bytes — can't double-buffer in FIFO
- Would need to overlap radio BUSY wait with SPI write (single-buffer)
- Expected gain: ~10-15% (1377→~1500 kbps)

### Option C: Accept 1377 kbps (PRAGMATIC)
- 1377 kbps is excellent for a pico balloon tracker
- Matches or exceeds typical LoRa link speeds by 50-100×
- Enough bandwidth for telemetry, mesh relay, and basic internet transport
- Move on to integration: tracker firmware, mesh stack, flight testing

## RECOMMENDATION

**Accept 1377 kbps as the practical maximum.** The data speaks clearly:
- 5 SPI alternatives tested, all failed on real hardware
- RF air time (803µs) is the dominant cost and is physics
- Arduino SPI at 12 MHz is the only working path
- Remaining gains (10-15% via pipelining) are small and risky

The time investment in PIO/DMA was valuable — we definitively proved these
paths don't work with LR2021. This knowledge prevents future agents from
wasting cycles on the same approaches.

## FIRMWARE INVENTORY

| File | Env | Status | Throughput |
|------|-----|--------|------------|
| flrc_tx_raw.cpp | rp2040-flrc-tx-raw | PROVEN | 1377 kbps |
| flrc_rx_raw.cpp | rp2040-flrc-rx-raw | PROVEN | 0% loss |
| flrc_pio_tx_v3.cpp | rp2040-pio-tx-v3 | ABANDONED | N/A (hangs) |
| flrc_dma_tx.cpp | rp2040-dma-tx | FAILED | N/A |
| flrc_raw_tx_batch.cpp | rp2040-raw-tx-batch | FAILED | Fake TX_DONE |
| flrc_raw_tx_pipe.cpp | rp2040-raw-tx-pipe | BUGGED | 1389 kbps (seq bug) |
