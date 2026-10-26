# ESP32-C3 GDMA Speed Test Results — 2026-07-27

**Task:** ESP32-SPEED-3 (kanban `t_f55c4dd2`) · **Branch:** `speed-sustained-sweep`
**Test window:** 2026-07-27T22:06:20Z → 2026-07-27T22:14Z (local 2026-07-28 03:36 IST)
**Run by:** task ESP32-SPEED-2 (`t_b1b38d3d`) on real hardware; transcribed here by ESP32-SPEED-3.

> **RESULT SUMMARY — READ THIS FIRST.**
> The **TX half of this test succeeded and is a new repo record** (1616.5 kbps,
> vs the RP2040 baseline of 1377.4 kbps). The **RX half failed: the receiver
> received 0 packets in 3 consecutive 12 s windows**, so **end-to-end throughput
> is 0 kbps**. ESP32 **cannot yet be claimed to match the RP2040 baseline**.
> No RX number in this document is estimated or projected — where a value was
> not measured it is written `n/a`.

---

## 1. Test configuration

### 1.1 Devices under test

| Role | Board | USB serial | Port (at test time) | Firmware mode |
|------|-------|-----------|---------------------|---------------|
| TX | ESP32-C3 SuperMini V1 + NiceRF LoRa2021F33 (LR2021) | `B0:A6:04:00:96:DC` | `/dev/ttyACM0` | `CONFIG_BENCH_MODE_FIFO_TX=y` (`fifo_tx.cpp`) |
| RX | ESP32-C3 SuperMini V1 + NiceRF LoRa2021F33 (LR2021) | `88:56:A6:7B:C6:98` | `/dev/ttyACM1` | `CONFIG_BENCH_MODE_FAST_RX=y` (`fast_rx.cpp`) |

Both boards: bench distance (inches apart), wire-dipole antennas, no attenuator.

### 1.2 Firmware / build configuration actually flashed

| Parameter | Value | Source |
|-----------|-------|--------|
| Firmware dir | `mesh-stack/flrc-bench-espidf/` | `PLAN-esp32-speed-test-2026-07-27.md` |
| ESP-IDF target | `esp32c3` | `sdkconfig.defaults` |
| CPU clock | **160 MHz** | `CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_160=y` |
| SPI HAL | **GDMA batch** (`EspHalC3`) — `spi_bus_initialize(..., SPI_DMA_CH_AUTO)`, persistent DMA-capable staging buffers, one `spi_device_polling_transmit()` per logical transfer | `EspHalC3.h:156-233`, commit `7429b2e` (2026-07-28) |
| SPI clock | **40 MHz** (`ESPHAL_C3_SPI_HZ = 40e6`) | `EspHalC3.h:32` at test time |
| SPI pins | SCK=6, MISO=2, MOSI=7, NSS=10, BUSY=4, RST=3, DIO9(IRQ)=5 | `fifo_tx.cpp:21-27`, `fast_rx.cpp:20-26` |
| Radio params | FLRC **2600 kbps**, CR 1/0, preamble 16 B, shaping 0.5, **+22 dBm**, fixed 255 B payload | `fifo_tx.cpp:92-98`, `fast_rx.cpp:118-127` |
| Frequency | **2440 MHz** (single-entry band table) | `fifo_tx.cpp:49-51`, `fast_rx.cpp:67-69` |
| Burst shape | TX: 500 packets/loop, 5 s startup delay, 840 µs fixed inter-packet delay, 5 s between loops. RX: 12 000 ms listen window, 500-packet target | `fifo_tx.cpp:144-159`, `fast_rx.cpp:57-59` |
| IRQ path | `radio->irqDioNum = 9`; ISR sets flag + `vTaskNotifyGiveFromISR`; RX task runs at `configMAX_PRIORITIES-1` | `fast_rx.cpp:34-38, 218` |

> **Config drift note (important).** The task brief described the HAL as "40 MHz SPI".
> That is correct **for this test** but is **no longer the branch state**: commit
> `d5f2f6e` (2026-07-29, the day after this run) clamped the define to
> **`ESPHAL_C3_SPI_HZ = 16 MHz`** with the rationale *"16 MHz is the LR2021
> datasheet maximum ... 40 MHz ran at bench distance but violated the datasheet
> and risked SPI timing failures in flight."* Any re-run on current HEAD tests
> 16 MHz, not 40 MHz.

### 1.3 Baseline under test (RP2040 — 1377 kbps)

| Parameter | Value | Source |
|-----------|-------|--------|
| Firmware | `firmware/rp2040/src/flrc_raw_tx.cpp` / `flrc_raw_rx.cpp` (v4 "Arduino SPI" baseline) | `docs/flrc-tx-rx-verified-coordinated-2026-07-16.md` |
| SPI | Arduino `SPI.transfer()` byte-at-a-time; **20 MHz requested → 12 MHz actual** (Pico SDK cap), raw register access, RadioLib bypassed | `flrc_raw_tx.cpp:32`, `docs/spi-frequency-sweep-results-2026-07-16.md:40` |
| Radio params | FLRC 2600 kbps, fixed **255 B** payload, 2440 MHz | `flrc_raw_tx.cpp:29-31` |
| Burst | 1000 packets | `flrc_raw_tx.cpp:35` |
| Measured throughput | **TX 1377.4 kbps** (1000/1000 TX_DONE, 1481 ms) · **RX 594.9 kbps** (1018 packets, 3491 ms incl. listen timeout) · 0.00 % loss | same doc, §Results |

The ESP32 (255 B, 2440 MHz, FLRC 2600) and RP2040 (255 B, 2440 MHz, FLRC 2600)
configurations are **directly comparable on the TX side** — same payload, same
band, same modulation, same bitrate.

---

## 2. Results — ESP32-C3, GDMA HAL, 40 MHz SPI, 2440 MHz (2026-07-27/28)

### 2.1 TX side — `fifo_tx.cpp`, 500-packet bursts (MEASURED, WORKS)

Raw serial lines, verbatim (format: `loop,band,pkt_count,sent,elapsed_ms,tx_throughput_kbps`):

```
5,2440,500,500,631,1616.5
19,2440,500,500,649,1571.6
```

| Metric | Loop 5 | Loop 19 |
|--------|--------|---------|
| Packets sent / attempted | **500 / 500** | **500 / 500** |
| Elapsed | 631 ms | 649 ms |
| **TX throughput (255 B payload)** | **1616.5 kbps** | **1571.6 kbps** |
| Per-packet time | 1.262 ms | 1.298 ms |
| — of which fixed inter-packet delay | 840 µs | 840 µs |
| — residual SPI + set-TX + clear-IRQ overhead | 422 µs | 458 µs |
| Radio init failures | none logged | none logged |

`tx_throughput_kbps` is computed by the firmware as
`sent × 255 × 8 / elapsed_ms` (`fifo_tx.cpp:165-166`) — payload bits per unit
wall-clock time, identical in definition to the RP2040 baseline number.

### 2.2 RX side — `fast_rx.cpp`, 12 s windows (MEASURED, FAILED)

Raw serial lines, verbatim (format:
`loop,band,pkt_size,rx_received,rx_errors,elapsed_ms,throughput_kbps,per_pct,duplicates,unique_pkts`):

```
2,2440,255,0,0,12000,0.0,0,0,0
3,2440,255,0,0,12000,0.0,0,0,0
4,2440,255,0,0,12000,0.0,0,0,0
```

| Metric | Attempt 1 (loop 2) | Attempt 2 (loop 3) | Attempt 3 (loop 4) |
|--------|--------------------|--------------------|--------------------|
| Packets received | **0** | **0** | **0** |
| Unique / duplicates | 0 / 0 | 0 / 0 | 0 / 0 |
| Elapsed (full listen window) | 12 000 ms | 12 000 ms | 12 000 ms |
| **RX throughput** | **0.0 kbps** | **0.0 kbps** | **0.0 kbps** |
| Packet loss (500 sent, 0 received) | **100.0 %** | **100.0 %** | **100.0 %** |
| RSSI avg / min / max | **not measured** (no packet ⇒ no RSSI) | — | — |
| DIO9 RX_DONE IRQ observed | **never** (see §4.3) | **never** | **never** |

The 8th field (`per_pct`) prints a hard-coded literal `0` in
`fast_rx.cpp:196`, **not** a computed PER — it must not be read as 0 % error.
Likewise `rx_errors` is a counter that is **declared and printed but never
incremented** (`fast_rx.cpp:138`, printed at `:195`), so `rx_errors=0` carries
**no information**.

### 2.3 Evidence availability

The raw serial capture files (`/tmp/esp32_speed_tx.log`, `/tmp/esp32_speed_rx.log`)
were written to tmpfs and **no longer exist**. The numbers above are the log
lines quoted in the ESP32-SPEED-2 completion report and comment thread
(kanban task `t_b1b38d3d`, 2026-07-27T22:13:51Z), which recorded them directly
from the boards. They are measurements, not projections — but they are
**transcribed evidence, not raw-capture evidence**, and a future re-run should
commit the logs verbatim.

---

## 3. Comparison table

| Platform / config | SPI clock | Band | TX kbps | RX kbps | End-to-end | Evidence |
|---|---|---|---|---|---|---|
| **ESP32-C3 + GDMA, this test** (2026-07-27) | **40 MHz** (datasheet-violating) | 2440 MHz | **1616.5** (loop 5), 1571.6 (loop 19) | **0.0** | **0.0 kbps** (link never closed) | §2.1, §2.2 above |
| ESP32-C3, polling SPI, 838.8 kbps record era (2026-06-18) | 18 MHz | 868 MHz | 1385.9 | **838.8** (500/500, 0 % PER, seq-verified) | 838.8 kbps | commit `733764e` |
| **RP2040 baseline** (2026-07-16) | 12 MHz actual (20 req.) | 2440 MHz | **1377.4** | 594.9 | 1377.4 kbps | `docs/flrc-tx-rx-verified-coordinated-2026-07-16.md` |
| Theoretical max (255 B @ FLRC 2600, 840 µs/pkt framing) | — | 2440 MHz | 2429 kbps | 2429 kbps | 2429 kbps | arithmetic: 2040 bits / 840 µs |
| Theoretical max (RP2040-measured 803 µs air time) | — | 2440 MHz | 2540 kbps | 2540 kbps | 2540 kbps | `docs/PLAN-esp32-speed-test-2026-07-27.md:24` |

**TX-side comparison (apples to apples, 2440 MHz / FLRC 2600 / 255 B):**

| | ESP32 GDMA 40 MHz | RP2040 Arduino 12 MHz | Δ |
|---|---|---|---|
| TX throughput | **1616.5 kbps** | 1377.4 kbps | **+17.4 %** |
| Per-packet wall clock | 1.262 ms | 1.481 ms | −0.219 ms |
| Share of 2429 kbps framing ceiling | 66.5 % | 56.7 % | — |

**RX-side comparison — NOT comparable yet.** ESP32 RX = 0 kbps in this run.
The only ESP32 RX figure that exists anywhere in this repo (838.8 kbps) was
measured on **868 MHz with the pre-GDMA 18 MHz polling HAL** (2026-06-18) and
therefore does **not** describe the GDMA configuration under test.

---

## 4. Analysis

### 4.1 Did GDMA work with LR2021?

**On the TX path: yes, demonstrably.** The GDMA HAL (`SPI_DMA_CH_AUTO` channel,
persistent `MALLOC_CAP_DMA` staging buffers, one batched
`spi_device_polling_transmit()` per FIFO write) drove the SPI bus for
2 × 500 packets with zero radio-init failures, zero logged HAL transfer errors,
and produced **1616.5 kbps — the highest TX throughput recorded on either
platform in this repo** (previous best: RP2040 1377.4 kbps; ESP32 18 MHz
polling: 1385.9 kbps). GDMA is therefore **not** affected by the LR2021 BUSY
timing incompatibility that killed RP2040 DMA — at least not on the write path,
where the BUSY wait is long (≈840 µs of air time per packet) and masks
marginal SPI timing.

**On the RX path: not demonstrated.** The receiver never read a single FIFO
word: 0 of 500 packets across 3 windows. So the GDMA claim is **half proven** —
proven sufficient for TX, unproven (and now suspected) for RX.

### 4.2 Did 40 MHz SPI cause timing issues?

**Correlated, not proven.** The evidence, stated as evidence:

1. **Datasheet violation.** The LR2021 SPI interface is specified to 16 MHz.
   This test ran 40 MHz — a 2.5× over-clock. The repo independently reached the
   same conclusion the next day (`d5f2f6e`, 2026-07-29: *"40 MHz ran at bench
   distance but violated the datasheet and risked SPI timing failures in
   flight"*) and clamped to 16 MHz.
2. **40 MHz GDMA was the single new variable.** The only previous successful
   ESP32 RX run (500/500, 838.8 kbps) used the **18 MHz byte-at-a-time polling**
   HAL. Nothing else in the RX path changed between that build and this one
   except the HAL (GDMA + 40 MHz) and the band (868 → 2440 MHz).
3. **Asymmetry is expected.** A marginal SPI clock shows up first on the
   latency-critical path (read RX FIFO immediately after an IRQ, then re-arm)
   and last on the write path, where the 840 µs air-time wait absorbs any
   clock-stretch. That is exactly the observed pattern.
4. **Frequency misconfiguration is ruled out as the cause of "0 packets":**
   both firmware copies print band `2440` and both were built from the same
   single-entry band table on `speed-sustained-sweep`, so TX and RX were on the
   same channel.

**What this test cannot tell you:** whether the failure was SPI clock, an
interaction between the GDMA driver and the LR2021 BUSY line, an RX IRQ/DIO9
routing problem, or an RF/burst-alignment artifact. Closing that gap requires a
re-run with a lower clock and/or `CONFIG_BENCH_MODE_PROFILE` (§6).

### 4.3 Why "0 packets" is the strongest signal in the dataset

`fast_rx.cpp` increments `received` **only** after the ISR has fired
(`irqFlag` set by `onIrq` → `vTaskNotifyGiveFromISR`, lines 34-38 / 153-172).
`received == 0` therefore means **the DIO9 RX_DONE interrupt never fired on any
attempt** — not merely that packets were lost in a software blind window.
That narrows the failure to two families:

* **(a) No frame reached the demodulator** — radio/RF/parameter issue, or the
  radio's RX mode was never actually entered (e.g. `SET_RX` mis-issued or
  corrupted over an over-clocked bus).
* **(b) A frame was demodulated but the RX_DONE interrupt never reached the
  MCU** — DIO9 mapping/IRQ-mask problem in the GDMA build.

Note the code review also found two RX-path issues that are **real but not
sufficient** to explain this failure, and should still be fixed:
`rx_errors` is a dead counter (§2.2), and the FIFO read passes
`tx_buffer = NULL` (`EspHalC3.h:222` via `rawSpiRead`, `fast_rx.cpp:93`) — a
pattern that also existed in the successful 18 MHz build, so it is pre-existing
rather than new, but on the GDMA path it relies on the driver synthesising
dummy transmit bytes and deserves an explicit check.

**RF path is unlikely but not excluded.** The two boards sat inches apart on the
same bench, in the same band, with TX configured at +22 dBm, and a 500-packet
burst occupies only ~0.63 s of each ~6.6 s TX loop, i.e. bursts should have
landed repeatedly inside the 12 s listen windows. However, note the honest
limit: **TX was never independently confirmed to be radiating** — `sent=500/500`
is an MCU-side counter, not an SDR/RSSI observation. There was no third
receiver, no SDR, and no RSSI reading anywhere in this run.

---

## 5. Conclusion

**Can the ESP32 match or exceed the RP2040 baseline?**

* **TX side — YES, it already does.** 1616.5 kbps vs 1377.4 kbps (**+17.4 %**),
  same band, same payload, same bitrate, same throughput definition. This is
  the first measurement that beats the RP2040's long-standing 1377 kbps record,
  and it was achieved by **software only** (GDMA + batched 40 MHz transfers on a
  stock ESP32-C3).
* **RX side — NOT YET.** 0 packets, 0.0 kbps, 100 % loss on all three attempts.
  End-to-end throughput is therefore **0 kbps < 1377 kbps**, and the ESP32
  **cannot** be declared the faster platform on this evidence.
* **What the bottleneck is now:** *not* SPI throughput and *not* the TX path.
  The TX path delivers 1616 kbps while the RF air time itself is only
  ~840 µs/packet — SPI is no longer the limiter. **The bottleneck is the RX
  pipeline, which never delivered a single RX_DONE interrupt.**

**Verdict: PARTIAL PASS.** TX target met and exceeded; RX target (RX > 0
packets, ideally > 1377 kbps) **not met**. The dominant suspect is running the
LR2021 above its 16 MHz SPI datasheet limit (40 MHz) on the latency-critical RX
path, but this remains a hypothesis until the §6 re-run.

### Gate status for this document

| Gate | Result |
|---|---|
| G1 — results doc with real measured data (not projected) | **PASS** — every number traces to a quoted harness log line or a committed prior test; nothing is estimated |
| G2 — CSV with actual test data rows | **PASS** — `data/esp32_speed_test_results.csv` (see §7) |
| G3 — explicit comparison to the RP2040 1377 kbps baseline | **PASS** — §3, §5 |
| G4/G5 — commit + push to `github/speed-sustained-sweep` | see task handoff |

---

## 6. Next Steps

ESP32 end-to-end throughput (0 kbps) is **below** the 1377 kbps baseline, so the
iteration track (ESP32-SPEED-4) applies. In priority order:

1. **Drop the SPI clock below the datasheet limit and re-run the coordinated
   test.** GDMA is the prime suspect for BUSY-timing/edge-alignment problems at
   speed. Compile-time only (a runtime clock change breaks LR2021 sync):
   `ESPHAL_C3_SPI_HZ` → 20 MHz, then 18 MHz, then the datasheet-legal
   **16 MHz** (which is already the current HEAD value after `d5f2f6e`), then
   12 MHz as a control equal to the RP2040's effective clock. Re-run the same
   500-packet / 12 s protocol and diff TX **and RX** throughput per variant.
2. **Profile the RX path with `CONFIG_BENCH_MODE_PROFILE`** (`profile_rx.cpp`
   exists in this tree). Get per-packet timing for: IRQ→task wake, FIFO read,
   IRQ clear, `SET_RX` re-arm, and confirm whether RX_DONE ever fires at all
   (that alone separates hypothesis (a) from (b) in §4.3).
3. **Compare GDMA vs polling SPI at the same clock.** Build the HAL with
   byte-at-a-time polling `spiTransfer` at 16/18 MHz and repeat. The 2026-06-18
   polling build received 500/500 at 838.8 kbps, so if polling works and GDMA
   does not at the same clock, the GDMA descriptor/BUSY path is the culprit
   rather than the clock.
4. **Fix the two code defects this review found** before the re-run, so the
   re-run's logs are interpretable: increment `rx_errors`, and make the
   FIFO-read path pass an explicit dummy TX buffer instead of `NULL`
   (`EspHalC3.h:214-223`).
5. **Add an independent TX-radiation check** (SDR sniff, or a third receiver /
   RSSI read) so "TX works" is no longer only an MCU-side counter.
6. **Synchronise TX and RX in hardware** (GPIO trigger or serial `RUN` handshake
   as used in the 2026-07-16 RP2040 test) to remove burst-alignment as an
   explanation.

---

## 7. Machine-readable results

`data/esp32_speed_test_results.csv` (columns:
`timestamp,platform,tx_kbps,rx_kbps,tx_packets,rx_packets,packet_loss_pct,rssi_avg`):

* 5 rows from this run (2 TX loops, 3 RX attempts) — `tx_kbps`/`rx_kbps` as
  measured, `rssi_avg=NA` because no packet was ever received.
* 1 row for the 2026-06-18 ESP32 18 MHz polling run and 1 row for the 2026-07-16
  RP2040 baseline, included because the CSV carries a `platform` column and the
  comparison is the point of the document.

No row is interpolated, averaged across platforms, or estimated.

---

## 8. Provenance index

| Number | Where it comes from | Class |
|---|---|---|
| `5,2440,500,500,631,1616.5` | Serial line quoted in kanban `t_b1b38d3d` comment (2026-07-27T22:13:51Z) | harness output, board-measured |
| `19,2440,500,500,649,1571.6` | same comment | harness output, board-measured |
| `2/3/4,2440,255,0,0,12000,0.0,0,0,0` | same comment, 3 attempts | harness output, board-measured |
| 1385.9 / 838.8 kbps | git commit `733764e` (2026-06-18), 18 MHz polling, 868 MHz | committed measurement |
| 1377.4 / 594.9 kbps | `docs/flrc-tx-rx-verified-coordinated-2026-07-16.md`, flrc_raw_*.cpp, 2440 MHz | committed measurement |
| 40 MHz → 16 MHz clamp | commit `d5f2f6e` (2026-07-29) | repo history |
| 2429 / 2540 kbps ceilings | arithmetic from 255 B @ 2600 kbps and 840 µs / 803 µs framing | derived, labelled |

**Not measured in this run:** RSSI, SNR, BER, CRC-error counts, per-packet RX
timing, RX_DONE IRQ count, radiated power, and any 868 MHz figure for the GDMA
build. Do not cite this document for those.
