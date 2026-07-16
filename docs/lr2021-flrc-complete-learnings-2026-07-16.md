# LR2021 FLRC Throughput Optimization — Complete Learnings

**Date:** 2026-07-16
**Repo:** balloon-fresh/firmware/rp2040/
**Hardware:** 2x RP2040 Pico + NiceRF LoRa2021 (Semtech LR2021 Gen 4)
**Board serials:** TX=F242D (E663B035977F242D), RX=8332 (E663B035973B8332)

---

## 1. Proven Results

| Firmware | SPI Clock | TX Throughput | TX_DONE | RX Unique | RX Loss | Commit |
|----------|-----------|---------------|---------|-----------|---------|--------|
| v4 baseline | 16MHz (12MHz actual) | 1367 kbps | 1000/1000 | 1000 | 0% | a90f546 |
| v4 20MHz TX | 20MHz (12MHz actual) | 1377 kbps | 1000/1000 | 1091 | 0% | d3bfba1 |
| Pipe (pipelining) | 16MHz (12MHz actual) | 1389 kbps | 1000/1000 | 162* | 0% | 0bbd179 |

*Pipe has seq number encoding bug (938 dups, 162 unique) — throughput measurement valid, seq needs fix.

## 2. What FAILED (tested on real hardware)

### 2.1 Pico SDK spi_write_blocking() — INCOMPATIBLE with LR2021
- **Approach:** Replace per-byte `spiRf.transfer(byte)` with batch `spiRf.transfer(buf, nullptr, len)`
- **Symptom:** Fake TX_DONE (spin=0 on first packets), 8160 kbps reported (exceeds 2600 air rate 3×), 0 RX packets
- **Root cause:** Pico SDK `spi_write_blocking()` uses different FIFO management than Arduino `transfer()`. The SDK fills the TX FIFO and waits for drain, but the LR2021 SPI peripheral requires specific inter-byte timing or CS handling that the SDK batch mode violates.
- **Lesson:** ONLY per-byte Arduino `transfer()` reliably drives LR2021 SPI on RP2040.

### 2.2 DMA via spi0_hw->dr — Radio Init Fails
- **Approach:** RP2040 DMA channel feeding spi0 TX FIFO data register directly
- **Symptom:** Radio init fails (Status=0x00, IRQ=0x21000200), "RADIO_INIT_FAIL"
- **Root cause:** Direct hardware register access bypasses Arduino SPI transaction protocol (mode/clock/CS setup). Even with `beginTransaction()` called beforehand, the DMA path doesn't maintain the SPI peripheral in the correct state for LR2021.
- **Lesson:** No direct spi0_hw->dr access — neither CPU writes nor DMA. Arduino SPI only.

### 2.3 Direct HW SPI (v5) — No Actual Transmission
- **Approach:** CPU writes to spi0_hw->dr in tight loop, bypassing Arduino overhead
- **Symptom:** 7034 kbps reported (fake), spin=0, radio never transmits, 0 RX
- **Root cause:** Same as 2.2 — direct register access doesn't drive LR2021 correctly
- **Lesson:** Arduino `transfer()` is the ONLY working SPI path for LR2021 on RP2040.

### 2.4 Runtime SPI Clock Change — Kills Radio
- **Approach:** Accept `SETSPI <freq>` serial command, call `spi_deinit()+spi_init()` to change clock
- **Symptom:** All subsequent TX bursts produce fake results (spin=0, 0 RX), radio never re-syncs
- **Root cause:** `spi_deinit()` tears down the entire SPI peripheral. When `spi_init()` rebuilds it, the LR2021 doesn't re-sync to the new SPI state. The radio chip requires a full hardware reset (RST pin toggle) after any SPI peripheral reconfiguration.
- **Lesson:** SPI clock must be compile-time `#define SPI_FREQ_HZ`. Never change at runtime.

### 2.5 20MHz RX SPI — Massive Packet Loss
- **Approach:** Run RX firmware at 20MHz SPI clock
- **Symptom:** 231/1000 packets received, 77% packet loss
- **Root cause:** RX side is more sensitive to SPI clock — the LR2021 RX FIFO read timing requires slower SPI. TX side tolerates 20MHz because it's pushing data out; RX must pull data in within tighter timing windows.
- **Lesson:** RX SPI must stay at 16MHz (12 MHz actual). TX can go to 20MHz but gains nothing (same actual clock).

### 2.6 SPI Frequency Sweep — Invalid Data
- **Approach:** Test SPI clocks from 6.25 MHz to 20.83 MHz
- **Symptom:** All results fake (spin=0, 0 RX) because runtime SETSPI breaks radio (see 2.4)
- **Valid data from compile-time tests only:** 16MHz→1367 kbps, 20MHz→1377 kbps (both 12 MHz actual, difference is noise)
- **Lesson:** Pico SDK `spi_set_baudrate()` caps at 12 MHz for requests ≥12 MHz. SPI clock is NOT the throughput bottleneck.

## 3. Bottleneck Analysis

### Per-Packet Breakdown (v4 at 1367 kbps, 1492µs total)
| Component | Time | % | Reducible? |
|-----------|------|---|------------|
| RF air time | 803µs | 54% | NO — physics |
| SPI per-byte transfer() × 268 bytes | 535µs | 36% | Difficult — only Arduino transfer() works |
| IRQ polling + loop overhead | 154µs | 10% | Partially — combined CS saves ~24µs |

### Why Per-Byte transfer() is the Bottleneck
- Each `spiRf.transfer(byte)` call: function entry → beginTransaction check → hardware register write → wait for TX complete → read RX FIFO → return. ~2µs per byte.
- 268 bytes per packet (6 CLR_IRQ + 2 CLR_FIFO + 4 CLR_ERR + 257 FIFO write + 5 SET_TX) × 2µs = 536µs
- Pico SDK batch alternative (`spi_write_blocking`) doesn't work with LR2021 (see 2.1)
- DMA doesn't work (see 2.2)
- PIO state machine is untested — could bypass both Arduino and SDK limitations

## 4. Key Technical Facts (LR2021 Gen 4)

### Chip Identity
- Semtech LR2021 = Gen 4 "LoRa Plus™" — NOT LR11x0, NOT SX1280
- FLRC modulation: coherent GMSK, 260 kbps to 2.6 Mbps
- Supports Sub-GHz (150-960 MHz) + 2.4 GHz ISM + S-Band (satellite)
- SPI: 4-wire with BUSY, IRQ, NSS (CS) lines

### IRQ Pin Behavior
- DIO9 (IRQ pin) fires on ALL enabled IRQ bits, not just TX_DONE
- IRQ status 0x000A080A = TX_FIFO (bit 1) + TX_TIMESTAMP (bit 3) + PA_OCP_OVP (bit 11) + TX_DONE (bit 19)
- All fire together at packet completion — works in practice (0% RX loss) but makes IRQ-based timing unreliable
- BUSY pin (GP6) is ground truth for TX completion — goes LOW when chip returns to STDBY

### RP2040 SPI Clock Reality
- System clock: 125 MHz
- SPI prescaler: even integer 2-254, post-divider 1-256
- Actual SCK = 125,000,000 / (prescale × postdiv)
- Requests ≥12 MHz all map to 12 MHz actual (prescaler limitation)
- "16MHz" and "20MHz" firmware both run at 12 MHz actual

### USB CDC Fix (Critical)
- `Serial.begin(115200)` alone produces no USB output
- Must assert DTR via pyserial: `s.dtr = True` after opening port
- Or use `delay(2000)` after `Serial.begin()` in firmware for TinyUSB enumeration
- `Serial.flush()` blocks CDC — never call it in hot paths

## 5. Approaches for Future Improvement

### 5.1 PIO State Machine SPI (Untested — Highest Potential)
- Use RP2040 PIO to drive SPI at hardware level with custom timing
- PIO can maintain exact CS/SCK/MOSI timing that LR2021 requires
- Bypasses both Arduino transfer() overhead and Pico SDK incompatibility
- Expected: 2000+ kbps if PIO timing matches LR2021 requirements
- Risk: Complex implementation, need to reverse-engineer exact SPI timing requirements

### 5.2 Fix Pipe Firmware Seq Bug + Adopt as Canonical (Quick Win)
- Pipe firmware gives 1389 kbps (1.6% over baseline) with 0% loss
- Bug: sequence number byte encoding wrong → 938 duplicates
- Fix: correct the pkt[0..3] byte assignment in hot loop
- Adopt as new canonical TX firmware

### 5.3 Reduce Packet Overhead (Small Gain)
- Current: 16-bit preamble + 32-bit sync + 255-byte payload = 2088 bits
- Reduce preamble to 8 bits: saves ~3µs/packet (0.2%)
- Both TX and RX must match — requires dual reflash
- Risk: shorter preamble may reduce sync reliability

### 5.4 Investigate Pico SDK SPI Mode Differences
- Why does per-byte `transfer()` work but `spi_write_blocking()` doesn't?
- Check: SPI mode (0 vs 0'), CS assertion timing, inter-byte gaps, FIFO flush behavior
- May reveal a configuration change that makes batch transfer work
- If fixable: 535µs → ~100µs per packet = ~2200 kbps

## 6. Firmware Inventory

| File | Env | Status | Purpose |
|------|-----|--------|---------|
| flrc_raw_tx.cpp | rp2040-raw-tx | ✅ PROVEN | v4 baseline (1367 kbps) |
| flrc_raw_rx.cpp | rp2040-raw-rx | ✅ PROVEN | RX (16MHz, CDC fixed) |
| flrc_raw_tx_20mhz.cpp | rp2040-raw-tx-20mhz | ✅ Tested | 20MHz TX (1377 kbps, marginal) |
| flrc_raw_rx_20mhz.cpp | rp2040-raw-rx-20mhz | ❌ Failed | 20MHz RX (77% loss) |
| flrc_dma_tx.cpp | rp2040-dma-tx | ❌ Failed | DMA TX (radio init fails) |
| flrc_raw_tx_batch.cpp | rp2040-raw-tx-batch | ❌ Failed | Batch transfer (fake TX_DONE) |
| flrc_raw_tx_pipe.cpp | rp2040-raw-tx-pipe | ✅ Best | Pipelining (1389 kbps, seq bug) |
| flrc_raw_tx_sweep.cpp | rp2040-raw-tx-sweep | ❌ Failed | Runtime sweep (breaks radio) |

## 7. Commit History (This Session)

```
e31217e docs: FLRC optimization results — 5 phases tested, pipelining best
83beab2 docs: FLRC TX optimization session summary
0bbd179 docs+sweep: LR2021 reference + SPI frequency sweep + batch/pipe firmware
f5170b8 Revert "opt(flrc-tx): Stage 3 — direct HW SPI hot loop"
d52e42a opt(flrc-tx): Stage 3 — direct HW SPI hot loop + skip 2 rfWaitBusy
b59c8f9 docs: add LR2021 research findings and SPI frequency sweep plan
d3bfba1 feat(flrc): 20MHz TX variant + DMA TX BUSY-pin fix + test results
a90f546 fix(flrc-tx): revert to v4 (16MHz Arduino SPI) as canonical TX
f5cf1fc diag(flrc-rx): add CDC diagnostic markers (delay+DTR fix)
0fca3d1 fix(flrc-dma-tx): CDC-safe init
7cb0b07 fix(flrc-tx): CDC DTR fix + 1366 kbps TX throughput confirmed
390c606 diag(flrc-tx): add boot/SPI/init diagnostic markers
bd79ed3 v4 firmware: pure Arduino SPI revert to proven baseline
616cc24 progress doc with full session history
100c163 docs: FLRC TX/RX verified results — 1000/1000, 0% loss
3ea5eee fix(flrc-tx): BUSY-pin TX completion + per-packet error/FIFO clear
95e9ecf fix(flrc-tx): CDC-safe USB init + SPI clock config + FIFO pipelining
c80713a perf(flrc-tx): fast rfWaitBusy + remove redundant spiDrain + analysis
ce95dde feat(flrc): DMA-based SPI TX firmware (Phase 3)
b7511b5 docs: FLRC progress report
```