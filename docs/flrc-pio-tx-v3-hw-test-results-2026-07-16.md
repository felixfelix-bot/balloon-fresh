# FLRC PIO TX v3 — Hardware Test Results & Progress

**Date:** 2026-07-16
**Repo:** balloon-fresh
**Commits:** d05490b, fbfe319, ae56e94, 92903f3
**Hardware:** TX = RP2040 Pico 8332 (PIO TX v3), RX = RP2040 Pico F242D

---

## Summary

PIO TX v3 was flashed to 8332 and tested with coordinated TX/RX.
**RF output confirmed** — F242D received real packets.
Full throughput numbers still pending (need UART bridge capture).

---

## What Was Tested

### Firmware: flrc_pio_tx_v3.cpp (commit 92903f3)

Key design:
1. Arduino SPI for radio init (CDC-safe)
2. 8-second WAIT window with dual CDC+UART heartbeat
3. Arduino SPI released, PIO+DMA SPI takes over
4. TX loop: 1000 packets, UART-only output (no CDC calls)
5. Post-TX: PIO torn down, Arduino SPI + CDC restored
6. Subagent-reviewed fixes applied:
   - INIT command disabled in PIO mode (uses dualPrintf which crashes CDC)
   - Banner string corrected

### Board Configuration

| Board | Role | Port | PID |
|-------|------|------|-----|
| 8332 | TX (PIO v3) | /dev/ttyACM1 | 2e8a:000a |
| F242D | RX | /dev/ttyACM0 | 2e8a:000a |
| ESP32 #1 | UART bridge | /dev/ttyACM2 | 303a:1001 |
| ESP32 #2 | UART bridge | /dev/ttyACM3 | 303a:1001 |

---

## Test Results

### RF Output: CONFIRMED ✅

F242D (RX board) received packets from 8332 (PIO TX v3):

```
100,412551800
200,2919153234
```

- Sequence numbers 100 and 200 observed on RX
- Real RF transmission confirmed — not phantom data
- 8332 survived TX (PID 000a, board alive post-TX)

### Board Survival: ✅

8332 did NOT crash during PIO TX:
- PID remained 0x000a (application firmware, not BOOTSEL 0x0003)
- ACM1 port stayed available
- Heartbeat visible in loop() via Serial1

### Throughput: PENDING

TX results are on Serial1 (UART GP12/GP13), NOT CDC.
Need ESP32 UART bridge or background serial capture to read:
- TX_DONE count (expect 1000/1000)
- Spin count per packet
- Elapsed time + throughput kbps

### CDC Status: As Expected

- CDC alive during init + WAIT window ✅
- CDC silent during TX loop (expected — DMA_IRQ_0 starves USB)
- CDC restoration after TX: not yet verified (output already flushed)

---

## Code Changes This Session

### Commit d05490b — PIO TX v3: UART-only output during PIO mode
- All TX-loop output via Serial1 (UART), never Serial (CDC)
- `uartPrintf()` / `uartPrintln()` helpers added
- INIT command in loop() disabled when PIO active

### Commit fbfe319 — Deferred printing fix for CDC death during TX loop
- 2s delay at boot for TinyUSB enumeration
- PIO+DMA configured AFTER CDC established
- Post-TX restore sequence (pioSpiStop → spiRf.begin → delay → Serial.print)

### Commit ae56e94 — Comprehensive PIO TX v1/v2/v3 summary + RX test checklist
- Full version comparison table (v4, PIO v1, v2, v3)
- Root cause analysis for CDC death in each version
- RX test checklist for coordinated TX/RX testing

### Commit 92903f3 — Fix v3: disable INIT in PIO mode + banner fix (subagent review)
- INIT command in loop() would call rawInitRadio() which uses dualPrintf
  (CDC + UART) — crashes TinyUSB when PIO+DMA is active
- Banner string corrected
- Subagent verified: DMA buffers 4-byte aligned, PIO transfers padded,
  pioWaitBusy before every command, no Serial calls in hot loop

---

## All FLRC TX Versions — Complete Status

| Version | SPI Method | CDC | Throughput | TX_DONE | RX | Status |
|---------|-----------|-----|------------|---------|-----|--------|
| v4 baseline | Arduino 16MHz | ✅ alive | 1367 kbps | 1000/1000 | ✅ verified | ✅ PROVEN |
| PIO v1 | PIO+DMA 20.83MHz | ❌ dead from boot | 1377 kbps | 1000/1000 | unknown | completed |
| PIO v2 | Hybrid init + PIO TX | dies during TX | unknown | unknown | unknown | abandoned |
| PIO v3 | PIO+DMA, UART-only | alive pre-TX | **pending** | **pending** | ✅ RF confirmed | **in progress** |
| Stage 3 (skip busy) | direct HW SPI | ❌ | 8986 kbps FAKE | 1000/1000 | ❌ no RF | reverted (f5170b8) |

---

## Key Learnings

1. **PIO+DMA and TinyUSB CDC are fundamentally incompatible when both active**
   - DMA_IRQ_0 fires at ~1kHz, starves USB IRQ
   - Tight polling prevents USB IRQ service
   - v3 solution: UART-only during TX, restore CDC after

2. **Skipping rfWaitBusy produces fake throughput (Stage 3 lesson)**
   - 8986 kbps was spin=0 on every packet — IRQ already HIGH before TX
   - Chip never processed SET_TX — no RF output
   - Reverted to proven v4 code (commit f5170b8)

3. **SPI speed is NOT the bottleneck**
   - RF air time (~803 µs) dominates per-packet latency
   - PIO saves ~430 µs SPI but air time unaffected
   - v1 (1377 kbps) vs v4 (1367 kbps) = within noise

4. **v3 subagent review caught real bugs**
   - INIT command in loop() would crash CDC via dualPrintf
   - DMA alignment + PIO padding verified correct
   - pioWaitBusy placement verified before every command

5. **UART output is the viable path for PIO TX results**
   - Serial1 (GP12/GP13) works during PIO+DMA
   - ESP32 UART bridge can capture TX statistics
   - CDC only for init + post-TX reporting

---

## Remaining Steps

1. **Capture full TX UART output** — flash ESP32 UART bridge, read 8332 Serial1
   - Get TX_DONE count, spin count, elapsed time, throughput
2. **Capture full RX output** — start F242D read BEFORE TX starts
   - Get RX packet count, sequence verification, RX throughput
3. **Compare PIO v3 vs v4 throughput** — if >1367 kbps, optimization worked
4. **Verify CDC restoration** — check if Serial.print works after PIO teardown
5. **Document final results** — commit + push

---

## File Index

| File | Description |
|------|-------------|
| `src/flrc_pio_tx_v3.cpp` | v3 firmware (current, commit 92903f3) |
| `src/flrc_pio_tx_v2.cpp` | v2 (abandoned — CDC dies during TX) |
| `src/flrc_pio_tx.cpp` | v1 (CDC dead from boot) |
| `src/flrc_raw_tx.cpp` | v4 baseline (1367 kbps proven) |
| `docs/flrc-pio-tx-all-versions-2026-07-16.md` | Full v1/v2/v3 comparison |
| `docs/flrc-rx-test-checklist-2026-07-16.md` | RX test procedure |
| `docs/flrc-rx-verified-results-2026-07-16.md` | v4 RX verified results |

---

*Document generated 2026-07-16. RF output confirmed via F242D RX. Full throughput numbers pending UART bridge capture.*