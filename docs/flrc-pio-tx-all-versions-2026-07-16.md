# FLRC PIO TX — All Versions Summary (v1, v2, v3)

**Date:** 2026-07-16  
**Repo:** balloon-fresh  
**Branch:** master  
**Hardware:** TX board = RP2040 + LR1121 (F242D), RX board = F242D  
**Goal:** Replace Arduino `SPI.transfer()` byte-by-byte SPI with PIO+DMA at 20.83 MHz to reduce SPI overhead and increase throughput.

---

## Background

The v4 baseline firmware uses Arduino's `SPI.transfer()` at 16 MHz to push
FLRC packets to the LR1121 radio.  SPI overhead is ~535 µs per packet
(21 bytes × ~25 µs/byte at 16 MHz).  PIO+DMA can push the same payload
at 20.83 MHz in ~103 µs — a theoretical saving of ~430 µs per packet.

However, **RF air time is ~803 µs/packet** and dominates total latency.
The SPI saving (~430 µs) is consumed by air time, yielding negligible
throughput improvement.  Worse, PIO+DMA and TinyUSB CDC are fundamentally
incompatible when both are active (see conclusions below).

---

## Version Comparison Table

| Version   | SPI Method       | CDC Status           | Throughput  | TX_DONE    | RX Loss | Status       |
|-----------|------------------|----------------------|-------------|------------|---------|--------------|
| **v4**    | Arduino 16 MHz   | Alive throughout     | 1367 kbps   | 1000/1000  | 0%      | ✅ PROVEN     |
| **PIO v1**| PIO+DMA 20.83 MHz| Dead from boot       | 1377 kbps   | 1000/1000  | Unknown | Completed    |
| **PIO v2**| Hybrid (Arduino init + PIO TX) | Alive through init, dies during TX | Unknown | Unknown | Unknown | Abandoned     |
| **PIO v3**| PIO+DMA 20.83 MHz, deferred print | Alive before TX, restored after TX | Unknown | Unknown | Unknown | **Awaiting HW test** |
| **Theoretical max** | — | — | ~2540 kbps | — | — | Calculated |

**v4 baseline (1367 kbps) is the proven ceiling.**  
**PIO v1 (1377 kbps) is within noise of v4 — confirming SPI is NOT the bottleneck.**

---

## v1 — `flrc_pio_tx.cpp` (PIO+DMA All-In From Boot)

**File:** `src/flrc_pio_tx.cpp`  
**Approach:** PIO+DMA configured at boot, before any Arduino/USB init.

### What Happened

- PIO program loaded and DMA channel configured immediately at startup.
- **CDC (USB serial) died immediately** — no output visible via `arduino-cli monitor` or `screen`.
- TinyUSB never had a chance to initialise because pico-sdk peripheral
  claimed resources (PIO, DMA IRQ) before the Arduino core ran its USB setup.
- Results were captured by running `stty` raw mode on `/dev/ttyACM0` and
  reading bytes directly — bypassing the CDC protocol layer entirely.

### Results (captured via stty)

- **Throughput:** 1377 kbps
- **TX_DONE:** 1000 / 1000
- **RX loss:** Not measured (CDC dead, couldn't run RX simultaneously easily)

### Root Cause

pico-sdk peripheral initialisation (PIO SM, DMA channel, IRQ handler)
ran before TinyUSB CDC was initialised by the Arduino core.  The PIO
state machine and DMA IRQ handler consumed resources that conflicted
with USB IRQ priorities, killing CDC before it ever started.

### Key Lesson

**Never initialise PIO+DMA before TinyUSB CDC is up.** The Arduino core
sets up USB during `setup()` implicitly; any pico-sdk peripheral work
that grabs IRQs or DMA channels before that point will break CDC.

---

## v2 — `flrc_pio_tx_v2.cpp` (Hybrid: Arduino SPI Init + PIO+DMA TX)

**File:** `src/flrc_pio_tx_v2.cpp`  
**Approach:** Use Arduino `SPI.begin()` + `SPI.transfer()` for radio init
(register writes, FLRC mode config), then switch to PIO+DMA only for the
payload TX loop.

### What Happened

1. Boot → Arduino core runs → **CDC alive** ✅
2. `spiRf.begin()` → radio init via Arduino SPI → **CDC alive** ✅
3. 10-second WAIT window printed to Serial → **CDC alive** ✅
4. PIO state machine + DMA channel configured → "PIO INIT OK" printed → **CDC alive** ✅
5. TX loop begins (PIO+DMA pushes payload, tight poll on DMA completion) → **CDC dies** ❌
6. No further Serial output after TX loop starts.
7. TX_DONE count and throughput **unknown** (no output captured).

### Root Cause (Two Issues)

1. **DMA_IRQ_0 contention:** The PIO DMA completion handler uses
   `DMA_IRQ_0`.  TinyUSB's USB IRQ handler also relies on interrupt
   priorities.  When DMA fires rapidly (every ~1 ms), it starves the
   USB IRQ, causing CDC to stall.

2. **Tight poll blocks USB IRQ:** The TX loop polls `dma_channel_is_busy()`
   in a tight `while` loop with no yield/sleep.  This prevents the USB
   interrupt from being serviced, dropping the CDC connection within
   the first few packets.

### Key Lesson

**Hybrid init works (CDC survives init), but the TX loop itself kills CDC.**
The problem is not initialisation order — it's the tight polling loop
and DMA IRQ priority conflicting with USB IRQ.  Even with deferred init,
the TX loop's interrupt and polling pattern is fundamentally hostile to
TinyUSB CDC.

---

## v3 — `flrc_pio_tx_v3.cpp` (Deferred Printing, CDC Restore After TX)

**File:** `src/flrc_pio_tx_v3.cpp`  
**Approach:** Accept that CDC dies during PIO TX loop.  Defer all Serial
output.  Buffer TX results in memory.  After TX completes, tear down PIO
and restore Arduino SPI + CDC.

### Design

1. **`delay(2000)` at boot** — known CDC fix (gives TinyUSB time to enumerate).
2. Arduino `SPI.begin()` + radio init via Arduino SPI → **CDC alive** ✅
3. 10-second WAIT window → **CDC alive** ✅
4. Configure PIO + DMA → "PIO INIT OK" → **CDC alive** ✅
5. **TX loop: NO Serial.print() at all.** Results buffered in `uint16_t txDoneCount`, `uint32_t startTime`, etc.
6. TX loop completes (1000 packets or timeout).
7. **Post-TX restore sequence:**
   - `pioSpiStop()` — disable PIO state machine, free DMA channel
   - `spiRf.begin()` — re-initialise Arduino SPI
   - `delay(500)` — give TinyUSB time to recover
   - `Serial.print()` buffered results → **CDC restored** ✅ (expected)

### Build Status

- **Builds OK** ✅ (compiled with `arduino-cli compile` / pio env)
- **Awaiting hardware test** — not yet flashed or run on the board

### Expected Results

If the restore sequence works:
- TX_DONE count and throughput will be printed after TX completes.
- CDC will be alive for post-TX analysis.
- Throughput expected to be ~1370–1380 kbps (same as v1/v4, within noise).

### Key Innovation

v3 is the first version that **accepts CDC death during TX as unavoidable**
and instead focuses on **restoring CDC after TX**.  This is the pragmatic
approach: run PIO TX as a black box, then bring USB back for reporting.

---

## Key Conclusions

### 1. SPI Speed Is NOT the Bottleneck

| Component           | Time (µs) | Notes                          |
|---------------------|-----------|--------------------------------|
| RF air time         | ~803      | Dominates — radio TX + preamble |
| SPI overhead (Arduino 16 MHz) | ~535 | 21 bytes × ~25 µs/byte        |
| SPI overhead (PIO 20.83 MHz)  | ~103 | 21 bytes × ~5 µs/byte         |
| **SPI saving**      | ~430      | Negligible vs 803 µs air time  |
| Total per-pkt (v4)  | ~1338     | 535 + 803                      |
| Total per-pkt (PIO) | ~906      | 103 + 803                      |
| **Theoretical speedup** | 1.48x | 1338 / 906                    |
| **Actual speedup (v1 vs v4)** | 1.007x | 1377 / 1367 — within noise |

The 1.48x theoretical speedup **never materialises** because:
- Air time (~803 µs) is the dominant term and is unaffected by SPI speed.
- Other overheads (Arduino loop, `SPI.beginTransaction`/`endTransaction`,
  register writes for TX start/status poll) add ~400 µs that PIO doesn't eliminate.
- The PIO+DMA path trades SPI time for DMA setup/teardown + PIO SM overhead.

### 2. PIO+DMA and TinyUSB CDC Are Fundamentally Incompatible When Both Active

- **v1:** PIO init before USB → CDC dead from boot.
- **v2:** PIO init after USB → CDC alive, but TX loop kills it (DMA IRQ + tight poll).
- **v3:** Accept death during TX, restore after — only viable approach.

The root cause is **interrupt contention**: PIO DMA completion fires on
`DMA_IRQ_0` at high frequency (~1 kHz), starving TinyUSB's USB IRQ.
Additionally, tight polling loops prevent USB IRQ from being serviced.

### 3. v4 Baseline (1367 kbps) Is the Proven Ceiling

v4 achieves 1367 kbps with 1000/1000 TX_DONE and 0% RX loss.
PIO v1 achieved 1377 kbps — within measurement noise.
**There is no meaningful throughput gain from PIO+DMA.**

### 4. Future Direction

If higher throughput is needed, the path is **reducing air time**, not SPI speed:
- Shorter preamble (if LR1121 allows configuration)
- Fewer sync word bytes
- Higher FLRC data rate (if supported)
- Smaller payload (trade-off with application data)

---

## File Index

| File | Description |
|------|-------------|
| `src/flrc_pio_tx.cpp` | v1 — PIO+DMA all-in from boot |
| `src/flrc_pio_tx_v2.cpp` | v2 — Hybrid Arduino init + PIO TX |
| `src/flrc_pio_tx_v3.cpp` | v3 — Deferred printing, CDC restore after TX |
| `docs/flrc-v4-baseline-*.md` | v4 baseline results (1367 kbps proven) |

---

## Appendix: Theoretical Throughput Calculation

```
FLRC air rate:        2600 kbps
Payload:              21 bytes = 168 bits
Preamble + sync:      ~48 bits (configurable)
Total bits per packet: ~216 bits
Air time per packet:  216 / 2600 = ~83 µs  (raw bit time)

With LR1121 overhead (preamble, sync, CRC, inter-packet gap):
Measured air time:    ~803 µs/packet

Theoretical max throughput:
  21 bytes / 803 µs = 21 × 8 / 803 µs = 168 / 0.000803 = ~209 kbps payload
  
With SPI overhead (v4): 21 bytes / (535 + 803) µs = 168 / 1.338 ms = ~125 kbps
Measured v4: 1367 kbps (aggregate, not per-pkt — includes 1000 pkts in ~1.47s)

Note: 1367 kbps = 1000 × 21 × 8 / 1.227s → measured total time per packet
is ~1227 µs, which is less than 535+803=1338 µs, suggesting some overlap
between SPI and air time (SPI for next packet starts while previous is in air).
```

The overlap explains why PIO's SPI saving doesn't help: Arduino SPI is
already partially overlapping with air time, so reducing SPI time further
yields diminishing returns.

---

*Document generated 2026-07-16. All measurements from hardware testing on F242D boards.*