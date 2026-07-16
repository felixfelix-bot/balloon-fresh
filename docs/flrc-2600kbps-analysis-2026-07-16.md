# How to Reach 2600 kbps — Bottleneck Analysis

**Date:** 2026-07-16
**Current:** 1293.6 kbps (Arduino SPI, 16MHz) — 51% of theoretical max
**Target:** 2600 kbps (air rate limit)

---

## Theoretical Maximum

FLRC config confirmed from RadioLib LR2021 source:
- **Bitrate:** 0x00 = 2600 kbps (FLRC_BR_2600)
- **Coding rate:** 0x2 = 1/0 (uncoded, zero FEC overhead)
- **Shaping:** BT 0.5

Per-packet on-air bits (255-byte payload, 16-bit preamble, 32-bit sync):
```
16 + 32 + (255 × 8) = 2088 bits
Air time = 2088 / 2,600,000 = 0.803 ms
Max payload throughput = 2040 / 0.803 = 2540 kbps
```

**2600 kbps payload throughput is physically impossible** — that's the raw air rate including preamble + sync. Real ceiling ≈ 2540 kbps. Every microsecond of SPI overhead pushes us further below.

---

## Where Time Is Lost (Current 1293.6 kbps = 1.577ms/packet)

| Component | Time (µs) | % of total |
|-----------|-----------|------------|
| RF air time | 803 | 51% |
| Arduino SPI (268 bytes @ 16MHz) | ~670 | 42% |
| rfWaitBusy ×3 (millis + digitalRead) | ~30 | 2% |
| spiDrain ×3 | ~15 | 1% |
| CS toggles + misc | ~60 | 4% |
| **Total** | **~1578** | **100%** |

**The #1 killer: Arduino SPI byte-by-byte transfer.** Each `spiRf.transfer()` call has function call overhead + per-byte transaction handling. For 268 bytes/packet, that's 670µs of pure waste.

---

## Optimization Path

### Phase 1: Direct HW SPI (COMMITTED a423d6b — untested)
- Bypass Arduino `SPIClass` entirely
- Write directly to RP2040 `spi0_hw->dr` register
- SPI clock 16→20MHz
- 268 bytes: 670µs → ~115µs (5.8× faster)
- **Expected: ~2100 kbps** (SPI overhead drops from 42% to 7%)

### Phase 2: Fast rfWaitBusy + remove spiDrain (COMMITTED THIS SESSION)
- Replace `millis()` + `digitalRead()` with `sio_hw->gpio_in` register spin
- Remove redundant `spiDrain()` — `spiWriteBurst()` already waits for TFE
- Saves ~45µs/packet
- **Expected: ~2200 kbps**

### Phase 3: DMA for TX FIFO write (NOT YET IMPLEMENTED)
- RP2040 DMA channel feeds SPI TX FIFO autonomously
- CPU sends SET_TX while DMA writes next packet's FIFO data
- Dual-buffer pipeline: prepare packet N+1 while packet N is on-air
- 255-byte FIFO write: ~115µs CPU → ~0µs CPU (DMA handles it)
- **Expected: ~2400 kbps**

### Phase 4: PIO state machine (ULTIMATE — explored in feat-rp2040-pio-dma-rx)
- RP2040 PIO handles CS toggle + SPI burst with cycle-accurate timing
- Zero CPU overhead for entire SPI transaction
- **Expected: ~2540 kbps** (theoretical maximum)

---

## Code Bottlenecks Found

### 1. rfWaitBusy() was using millis() + digitalRead() [FIXED]

**Before (line 51-56):**
```c
static inline void rfWaitBusy() {
    uint32_t timeout = millis() + 50;
    while (digitalRead(PIN_BUSY) == HIGH) {
        if (millis() > timeout) return;
    }
}
```
Each iteration calls `millis()` (64-bit atomic read) + `digitalRead()` (function call). Called 3× per packet = ~30µs overhead.

**After:**
```c
static inline void rfWaitBusy() {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 500000;
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
}
```
Direct register read. ~8ns per iteration. Called 3× = <1µs.

### 2. Redundant spiDrain() calls [FIXED]

`spiWriteBurst()` already waits for `SPI_SSPSR_TFE` (TX FIFO empty) at the end. The subsequent `spiDrain()` was redundant — it only drained the RX FIFO which nobody reads for TX operations. Removed all 3 calls in hot loop.

### 3. rfReadStatus() / rfReadIrqStatus() still use Arduino SPI [MINOR]

Lines 90-117 use `spiRf.beginTransaction()` + `spiRf.transfer()`. Only called for first 5 packets (diagnostics), so negligible in throughput test. Fix if needed later.

### 4. rfWriteTxFifo() still uses Arduino SPI [MINOR]

Lines 137-147. Only called for end-marker packet, not in hot loop. Negligible.

---

## Config Verification

| Parameter | Value | RadioLib Constant | Status |
|-----------|-------|-------------------|--------|
| FLRC bitrate | 0x00 | RADIOLIB_LR2021_FLRC_BR_2600 | ✓ Correct |
| Coding rate | 0x2 (upper nibble of 0x25) | RADIOLIB_LR2021_FLRC_CR_1_0 (uncoded) | ✓ Optimal |
| BT shaping | 0x5 (lower nibble of 0x25) | GAUSS_BT_0_5 | ✓ Correct |
| Packet size | 255 bytes | FLRC max payload | ✓ Optimal |
| SPI clock | 20 MHz | LR2021 datasheet max | ✓ Correct |
| TX power | 12 dBm (×2 = 0x18) | HF FLRC max | ✓ Correct |
| Frequency | 2440 MHz | 2.4 GHz ISM | ✓ Correct |

No config issues found. Radio params are already at maximum throughput.

---

## Next Steps (Priority Order)

1. **Flash optimized firmware** to TX board, measure actual throughput
2. **If <2200 kbps:** investigate BUSY pin timing — may need logic analyzer
3. **Implement DMA TX FIFO write** — biggest remaining win
4. **Dual-buffer pipeline** — overlap FIFO write with RF air time
5. **PIO state machine** — for theoretical maximum
