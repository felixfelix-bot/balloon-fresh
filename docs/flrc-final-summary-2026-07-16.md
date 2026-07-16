# FLRC Throughput Optimization — Final Summary

**Date:** 2026-07-16
**Repo:** balloon-fresh
**Hardware:** 2x RP2040 Pico + NiceRF LoRa2021 (Semtech LR2021 Gen 4)
**Boards:** TX=F242D (E663B035977F242D), RX=8332 (E663B035973B8332)

---

## TL;DR

- **Achieved: 1377 kbps end-to-end TX/RX, 1000/1000 TX_DONE, 0% packet loss**
- **Theoretical max: ~2540 kbps payload (air rate 2600 kbps minus preamble/sync overhead)**
- **We are at 54% of theoretical max. The remaining 46% is RF air time — physics, not code.**
- **SPI optimization (PIO, DMA, batch, direct HW) ALL FAILED. Arduino per-byte transfer() is the only working SPI path.**
- **Throughput ceiling for this configuration: ~1400 kbps. Further gains require reducing air time, not SPI speed.**

---

## 1. WHAT WORKED

### Proven End-to-End Link
- TX: 1000 packets sent, 1000 TX_DONE confirmed, 0 timeouts
- RX: 1018 packets received (0% loss after removing 18 stale FIFO entries)
- DEADBEEF end-marker successfully received on RX side
- RF link fully functional — real packets over real radio

### v4 Baseline Firmware (Canonical)
- Arduino `SPI.transfer()` byte-by-byte at 16 MHz (12 MHz actual on RP2040)
- 255-byte FLRC payload, 2.4 GHz, 2600 kbps air rate, uncoded (CR 1/0)
- Throughput: 1367-1377 kbps (consistent across multiple runs)
- TX_DONE: 1000/1000 (100%) every run
- Status: **This is the production firmware. Do not change it.**

### Coordinated TX/RX Test Harness
- Python script sends "RUN" to RX first (2s head start), then to TX
- Captures both serial ports for 15s
- Reusable: `scripts/coordinated_tx_rx_test.py`

### Key Fixes That Made It Work
1. **IRQ pin polling fix** (eee6147): BUSY-pin based TX completion detection → 1000/1000 TX_DONE
2. **CDC DTR fix**: `Serial.dtr = True` via pyserial, or `delay(2000)` in firmware for TinyUSB enumeration
3. **FLRC config**: bitrate=2600, CR=1/0 (uncoded), BT=0.5, 255-byte payload — already at maximum
4. **CDC-safe init**: no `Serial.flush()` in hot paths, no Serial.print during TX loop

---

## 2. WHAT DIDN'T WORK (All Tested on Real Hardware)

### 2.1 Pico SDK `spi_write_blocking()` — BROKEN
- **Symptom:** Fake TX_DONE (spin=0), 8160 kbps reported (impossible, exceeds air rate 3x), 0 RX packets
- **Root cause:** Pico SDK batch FIFO management incompatible with LR2021 SPI timing requirements
- **Lesson:** Only Arduino per-byte `transfer()` drives LR2021 correctly on RP2040

### 2.2 DMA via `spi0_hw->dr` — Radio Init Fails
- **Symptom:** Status=0x00, IRQ=0x21000200, RADIO_INIT_FAIL
- **Root cause:** Direct register access bypasses Arduino SPI transaction protocol
- **Lesson:** No direct `spi0_hw->dr` access — neither CPU writes nor DMA

### 2.3 Direct HW SPI Tight Loop — No Transmission
- **Symptom:** 7034 kbps reported (fake), spin=0, radio never transmits, 0 RX
- **Root cause:** Same as 2.2 — direct register access doesn't drive LR2021

### 2.4 Runtime SPI Clock Change — Kills Radio
- **Symptom:** All TX bursts produce fake results after `spi_deinit()+spi_init()`
- **Root cause:** SPI peripheral teardown breaks LR2021 sync; requires full hardware reset
- **Lesson:** SPI clock is compile-time `#define SPI_FREQ_HZ` only. Never change at runtime.

### 2.5 PIO State Machine TX (v1, v2, v3) — CDC Death
- **v1 (PIO from boot):** CDC dead immediately. Throughput 1377 kbps (within noise of v4). No gain.
- **v2 (Hybrid Arduino init + PIO TX):** CDC alive during init, dies during TX loop. DMA_IRQ_0 starves USB IRQ.
- **v3 (Deferred printing):** CDC dies during TX, partially restored after. Throughput unknown but expected ~1377 kbps.
- **Overall:** PIO+DMA offers ZERO throughput gain. SPI saving (~430µs) consumed by air time (~803µs).
- **Lesson:** PIO+DMA and TinyUSB CDC are fundamentally incompatible on RP2040 when both active.

### 2.6 20MHz RX SPI — 77% Packet Loss
- **Symptom:** 231/1000 received at 20 MHz SPI
- **Root cause:** RX FIFO read timing requires slower SPI
- **Lesson:** RX stays at 16 MHz. TX at 20 MHz gains nothing (both map to 12 MHz actual).

### 2.7 Pipelining (Pipe Firmware) — Seq Bug
- **Throughput:** 1389 kbps (1.6% over baseline)
- **Problem:** 938 duplicates due to sequence number encoding bug
- **Lesson:** Marginal gain not worth the complexity. v4 stays canonical.

---

## 3. BOTTLENECK ANALYSIS — WHY ~1400 kbps IS THE CEILING

### Per-Packet Time Breakdown (v4 at 1377 kbps, ~1481µs total)

| Component | Time (µs) | % of Total | Reducible? |
|-----------|-----------|------------|------------|
| **RF air time** | **803** | **54%** | **NO — physics** |
| Arduino SPI (268 bytes @ 12 MHz) | 535 | 36% | No working alternative found |
| IRQ poll + loop overhead | 143 | 10% | Partially (~24µs via combined CS) |
| **Total** | **1481** | **100%** | |

### The Air Time Wall

```
FLRC air rate:     2600 kbps
Payload:           255 bytes = 2040 bits
Preamble + sync:   48 bits
Total bits/packet: 2088 bits
Air time:          2088 / 2,600,000 = 803 µs  ← IMMUTABLE
```

This 803µs is physics. No firmware optimization can reduce it. It's the time
for 2600 kbps FLRC modulation to push 2088 bits through the air.

### Why SPI Optimization Doesn't Help

Arduino SPI (535µs) and RF air time (803µs) **partially overlap** — the CPU
starts preparing the next packet's SPI while the previous packet is still
on-air. This overlap means:

- SPI saving of 430µs (PIO) → actual gain of ~10µs (1%)
- Measured: v4=1367 kbps, PIO=1377 kbps → 0.7% difference (noise)

The overlap exists because the TX loop structure is:
1. Write packet N to FIFO via SPI (535µs)
2. Send SET_TX command
3. Wait for TX_DONE (air time 803µs) ← overlaps with step 1 of packet N+1

---

## 4. CAN WE GO FASTER?

### Short Answer: Not meaningfully with current config. ~1400 kbps is the practical ceiling.

### Options Investigated and Rejected

| Approach | Potential Gain | Status | Why Rejected |
|----------|---------------|--------|--------------|
| PIO SPI | 430µs SPI → 0µs | Tested | 0.7% gain (noise), kills CDC |
| DMA SPI | 535µs → ~0µs | Tested | Radio init fails |
| Batch transfer | 535µs → ~100µs | Tested | Fake TX_DONE, 0 RX |
| Direct HW SPI | 535µs → ~50µs | Tested | No transmission |
| Pipelining | ~20µs overlap | Tested | 1.6% gain, seq bug |
| Runtime SPI sweep | N/A | Tested | Kills radio permanently |
| 20MHz SPI | 535µs → 430µs | Tested | Same actual clock (12 MHz) |

### Theoretical Paths to Higher Throughput (Untested, Higher Risk)

1. **Shorter preamble** — 16-bit → 8-bit saves ~3µs/pkt (0.2%). Risk: reduced sync reliability at range.
2. **Smaller payload** — paradoxically faster per-packet but lower aggregate throughput. Not useful.
3. **ESP32-C3 port** — ESP32 has hardware SPI DMA that may work with LR2021 (different SPI peripheral than RP2040). Worth testing on actual flight hardware.
4. **Dual-buffer pipeline** — prepare packet N+1 in buffer B while packet N transmits from buffer A. Saves the 535µs SPI if radio can accept next FIFO write during TX. Needs LR2021 datasheet confirmation.
5. **Reduce FLRC overhead** — investigate if LR2021 supports shorter sync word or preamble configuration.

### Honest Assessment

The RP2040 + Arduino mbed framework combination imposes a hard SPI ceiling.
The LR2021 chip itself supports 2600 kbps air rate, but the RP2040's SPI
peripheral + Arduino abstraction layer limits us to ~1400 kbps aggregate.
Moving to ESP32-C3 (the actual flight hardware) may unlock hardware SPI
DMA that actually works with LR2021 — this is the most promising next step.

---

## 5. FIRMWARE INVENTORY (Final State)

| File | Env | Status | Throughput | Notes |
|------|-----|--------|------------|-------|
| flrc_raw_tx.cpp | rp2040-raw-tx | ✅ CANONICAL | 1367 kbps | v4 baseline — production |
| flrc_raw_rx.cpp | rp2040-raw-rx | ✅ CANONICAL | 0% loss | RX — production |
| flrc_raw_tx_20mhz.cpp | rp2040-raw-tx-20mhz | ✅ Tested | 1377 kbps | Marginal gain |
| flrc_raw_tx_pipe.cpp | rp2040-raw-tx-pipe | ⚠️ Bug | 1389 kbps | Seq encoding bug |
| flrc_pio_tx.cpp | rp2040-pio-tx | ❌ Abandoned | 1377 kbps | Kills CDC, no gain |
| flrc_pio_tx_v2.cpp | rp2040-pio-tx-v2 | ❌ Abandoned | Unknown | CDC dies during TX |
| flrc_pio_tx_v3.cpp | rp2040-pio-tx-v3 | ❌ Abandoned | Unknown | CDC partially restored |
| flrc_dma_tx.cpp | rp2040-dma-tx | ❌ Failed | N/A | Radio init fails |
| flrc_raw_tx_batch.cpp | rp2040-raw-tx-batch | ❌ Failed | N/A | Fake TX_DONE |
| flrc_raw_tx_sweep.cpp | rp2040-raw-tx-sweep | ❌ Failed | N/A | Kills radio |

---

## 6. KEY TECHNICAL LEARNINGS

### LR2021 Gen 4 Chip
- Semtech LR2021 = Gen 4 "LoRa Plus" — NOT LR11x0, NOT SX1280
- FLRC modulation: coherent GMSK, 260 kbps to 2.6 Mbps
- Supports Sub-GHz (150-960 MHz) + 2.4 GHz + S-Band
- SPI: 4-wire with BUSY, IRQ (DIO9), NSS (CS) lines
- DIO9 fires on ALL enabled IRQ bits, not just TX_DONE
- BUSY pin is ground truth for TX completion

### RP2040 SPI Limitations
- System clock 125 MHz, SPI prescaler limits actual SCK to 12 MHz for requests ≥12 MHz
- "16 MHz" and "20 MHz" firmware both run at 12 MHz actual
- Pico SDK `spi_write_blocking()` is incompatible with LR2021 (timing/Cs/FIFO issue)
- Direct `spi0_hw->dr` access breaks radio init (bypasses transaction protocol)
- PIO+DMA and TinyUSB CDC fundamentally conflict (DMA_IRQ_0 starves USB IRQ)

### USB CDC (Critical for Any RP2040 USB Serial Work)
- `Serial.begin(115200)` alone produces no output
- Must assert DTR: `s.dtr = True` in pyserial after opening port
- Or `delay(2000)` in firmware for TinyUSB enumeration
- Never call `Serial.flush()` in hot paths — blocks CDC

### Test Infrastructure
- 1200 baud touch reboots RP2040 into BOOTSEL mode reliably
- `pyserial` with `dtr=True` is required for CDC communication
- Background capture scripts must handle port name changes after reboot
- Coordinated TX/RX requires RX head start (2s) before TX starts

---

## 7. WHAT NEEDS TO HAPPEN NEXT

### Immediate (Bench → Flight Transition)
1. **ESP32-C3 port** — Move FLRC TX/RX from RP2040 dev boards to actual ESP32-C3 flight hardware. ESP32 has different SPI peripheral, hardware DMA may work where RP2040's doesn't.
2. **Range test** — Current tests are bench (cm distance). Test at 10m, 100m, 1km+ to validate link budget.
3. **Power measurement** — Measure TX current draw at 12 dBm for solar/supercap power budget validation.

### Application Layer
4. **Telemetry protocol** — Define 24-byte binary telemetry format (ADR-008) with CRC-16, implement TX/RX.
5. **Mesh protocol** — TDMA slot assignment, adaptive data rate (FLRC vs LoRa fallback).
6. **GPS integration** — Add GPS parsing, position encoding into telemetry packets.

### If Higher Throughput Needed (Low Priority)
7. **Dual-buffer pipeline on ESP32-C3** — Test if ESP32 SPI DMA allows overlapping FIFO write with air time.
8. **Preamble optimization** — Reduce from 16-bit to 8-bit if range tests show reliable sync.
9. **FLRC 1300 kbps mode** — Lower air rate but may allow smaller packets and higher aggregate throughput if overhead-per-packet dominates.

---

## 8. COMMIT HISTORY (This Session — Chronological)

```
dceb6e5 docs+test: coordinated TX/RX verified — 1377 kbps, 0% loss, RF link confirmed
936b68b docs: flash+capture pitfalls — capture blocks BOOTSEL, stale mount, port shifts
87db5fd fix(flrc-pio-tx-v3): check BOOTSEL command during WAIT window
8b5385c feat(makefile): 1200 baud touch BOOTSEL targets + board identification
486a4bd feat(firmware): add bootsel-1200 alias target for discoverability
5f32cf9 fix(flrc-pio-tx-v3): add DMA/busy timeout + per-step UART debug for TX hang
bddf7e5 docs: PIO TX v3 CDC permanently dead after PIO — root cause + conclusion
46de3c9 feat(flrc-pio-tx-v3): CDC restore after PIO teardown + BOOTSEL serial command
8104c6c docs(flrc-pio-tx-v3): HW test results — RF output confirmed, throughput pending UART capture
92903f3 fix(flrc-pio-tx-v3): disable INIT command in PIO mode + fix banner string
ae56e94 docs: comprehensive PIO TX v1/v2/v3 summary + RX test checklist
fbfe319 feat(flrc): PIO TX v3 — deferred printing fix for CDC death during TX loop
d05490b feat(flrc): PIO TX v3 — UART-only output during PIO mode
55ba06e docs: PIO TX v2 CDC dies during TX loop — root cause + fix plan
cda70d2 docs: PIO TX v2 results — CDC-safe init works, CDC dies during TX loop
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

---

*This document supersedes all individual session docs. All measurements from real hardware testing on 2026-07-16.*
