# FLRC 512 B / 2.6 Mbps — settled

**Card:** `balloon/t_6b68897c` (FLRC-512B) · **Date:** 2026-10-06
**Scope:** settle the "~2.6 Mbps at 512 B payload" report. Deliverables 1–3 of the
card; deliverable 4 (a *fresh* 512 B sweep) is **not** met — see §6.

**Tool:** `tools/flrc_512b_throughput_audit.py` (`--selftest` 10/10).
Every number below is either an arithmetic result from that tool or a file:line on
disk. Nothing was measured on a radio for this document.

---

## 1. Verdict

**The 2.6 Mbps figure is (i) — the configured FLRC *air rate*, not delivered
goodput.** It is the physical-layer symbol rate; no payload size can make goodput
reach it, and a ~2.6 Mbps *goodput* figure is not merely unmeasured, it is
**impossible under any header model**.

**The 512 B run does not exist.** Payloads `{16, 64, 128, 192, 255, 256, 300, 384,
448, 511}` were measured; **512 was never measured anywhere on disk, and cannot be
— 511 B is the hardware maximum** (`SET_FLRC_PACKET_PARAMS` payload length is a
9-bit field, `lr20xx_radio_flrc.c` rejects `pld_len > 511 - crc_bytes`).

So the physical claim behind the report — *"doubling the payload raises
throughput"* — is **correct in direction and already demonstrated**: 511 B FLRC is
measured working at 50/50 reception and zero PRBS-15 payload bit errors at all
three bitrates, including BR2600 (§3). What does not exist is a sustained
(no-gap) goodput number for it, because every 511 B burst on disk was run at a
40 ms inter-packet gap, which floors the rate at ~90 kbps.

---

## 2. Ceilings — goodput cannot reach 2600, at any payload

Uncoded, BR2600, zero host/SPI overhead (i.e. the *optimistic* limit). Two header
models, because the repo's own audit and the shipped firmware disagree by ~2 %:

| LEN | airtime (audit model) | ceiling (audit model) | airtime (driver model) | ceiling (driver model) |
|----:|----------------------:|----------------------:|-----------------------:|-----------------------:|
| 255 | 803.1 µs | 2540.2 kbps | 815.4 µs | 2501.9 kbps |
| 511 | 1590.8 µs | **2569.8 kbps** | 1603.1 µs | **2550.1 kbps** |

* audit model = `16 b preamble + 32 b sync + payload·8`, no CRC —
  `lr2021-flrc-24ghz-datasheet-audit-2026-07-26.md:80` (reproduces its 2540 figure
  and the card's 2570 figure).
* driver model = `32 b preamble + 4 B sync + (payload+2)·8` — what
  `src/radio_bench.c` configures (`preamble_len = 32 bits`,
  `sync_word_len = 4 bytes`, `crc_type = 2 bytes`) and what the LR20xx driver's
  own on-air numerator computes.

**Both ceilings are below 2600.** The card's conflict therefore resolves cleanly:
the 2540/2570 model is *not* what is wrong; what is wrong is expecting a
*configured air rate* to appear as delivered payload. `2 × 255 B` does not equal
`2 × 2.6 Mbps`; it equals 511 B, and 511 B is bounded by the table above.

Corollary the card did not ask for: **the ceiling gain from 255 B → 511 B is
1.2 % (2540 → 2570), not ~2×.** Doubling the payload doubles the *air time* too —
it fills the fixed header/preamble overhead better, it does not double the rate.
The lever is **modulation + payload size + pipelining**, in that order.

## 3. What was actually measured at ≥ 255 B

`tools/flrc_512b_throughput_audit.py` enumerates every FLRC row with `plen ≥ 255`
in the on-disk sweeps. Three sessions, identical rows (fw `88a00cf`, 868 MHz,
PA 5 dBm, SMA ~30 cm apart, GAP 40 ms):

| LEN | BR | rx | crc_err | PRBS bit_err | tx_done |
|----:|---:|----:|--------:|-------------:|:-------:|
| 255 | 650 | 50/50 | 0/50 | 0 | ✓ |
| 256 | 650 | 50/50 | 50 | 0 | ✓ |
| 300 | 650 | 50/50 | 50 | 0 | ✓ |
| 384 | 650 | 50/50 | 50 | 0 | ✓ |
| 448 | 650 | 50/50 | 50 | 0 | ✓ |
| **511** | **650** | **50/50** | 50 | **0** | ✓ |
| 384 | 1300 | 50/50 | 50 | 0 | ✓ |
| **511** | **1300** | **50/50** | 50 | **0** | ✓ |
| **511** | **2600** | **50/50** | 50 | **0** | ✓ |

Sources: `full-sweep-summary-20260821-175612.csv`,
`full-sweep-summary-20260821-200111.csv`,
`full-sweep-results-2g4-summary-20260822-210817.csv`.

Reading it correctly matters:

* **`bit_err = 0` is the integrity signal.** The `crc_err` column is the *chip* CRC
  verdict, which is unreliable in FLRC on this firmware (root cause: RX sync-match
  mode; fix in review). Every length except 255 reports `crc_err = 50`, including
  lengths that are demonstrably fine. Do not read the `50` as loss.
* **`rx 50/50` at 511 B × BR2600 is a delivery result, not a throughput result.**
  At GAP 40 ms the delivered rate is gap-limited (~90 kbps); the on-air rate is
  1.92 Mbps (`full-sweep-report-20260821-175612.md:99`, PHY = payload·8/ToA at
  CR 3/4). Neither number is the sustained goodput the card asks for.

The best *measured* sustained figure anywhere in the repo remains
**1484.9 kbps** (`sustained-throughput-results-2026-07-23.md`, BR2600, **LEN 127**,
0.00 % PER, TX-side-limited at ~1487 kbps). At 511 B the per-packet SPI write is
4× longer, so the TX-side ceiling does **not** improve with payload — it is a
host-side wall, and a bigger packet does not move it.

## 4. Firmware note from the card — answered

`firmware/rp2040/src/flrc_throughput_tx.cpp:8` says *"127-byte packets (max SX1280
FLRC)"*. Confirmed:

* **It is an SX1280 limit only.** That file is explicitly marked
  *"DEPRECATED — DO NOT USE. This file uses SX1280 raw SPI commands (wrong chip).
  Our chip is LR2021 (Gen 4), NOT SX1280. See ADR-017."* (`:2-3`). The 127 B ceiling
  is an artefact of dead code written for the wrong radio.
* **The LR2021 path takes 511 B in one FIFO write.** `SET_FLRC_PACKET_PARAMS` takes
  a 16-bit big-endian payload length; RadioLib defines
  `RADIOLIB_LR2021_MAX_PACKET_LENGTH_FLRC = 511`; the E80 firmware enforces
  `6–511` at runtime (`bench.c` → `MAX 255 LORA / 511 FLRC`) and writes the whole
  frame with a single `lr20xx_radio_fifo_write_tx(context, buf, len)` — no chunking
  (`radio_bench.c:427`) — and it demonstrably delivers 511 B (§3).
* The "512" in the report is **one byte past the field limit**. The real headline
  number is 511 B.

## 5. Docs corrected in this commit

| File | Change |
|---|---|
| `docs/PLAN-speed-optimization.md` | retitled off "Breaking the 1391 kbps Ceiling"; added a dated §1.1 status block stating the 2540/2570 ceiling, the measured 1484.9 kbps, that 1391 kbps is superseded, and that 2600 is air rate |
| `docs/frequency-plan-868.md` | FLRC 2600 row annotated: these are *airtime* rows and 2600 kbps is the air rate, not goodput; ceiling at 255 B is 2540 kbps |
| `tools/plot_full_characterization.py` | `phase_defs` label `"2600k"` → `"2600k(air)"` for the four HF/LF-FLRC-2600 phases, with an inline comment |
| `docs/SX1280-ARRAY-FEASIBILITY.md` (branch `pr/029-dual-band-flight-board`) | replaced the caveat with the settled figure; the throughput lever re-stated as **modulation + payload size**, not radio count |

`PLAN-speed-optimization.md` was **not** rewritten to claim 2.6 Mbps — the card's
explicit instruction. The stale 1391 kbps figure is kept as history and annotated.

## 6. What is NOT done — and why

The card's deliverable 1 is *"run the sweep at 512 B (and 255 B as control) at
2600 kbps FLRC, 2440 MHz"*. **Not done: no radio is attached to any reachable
machine.** Verified five independent ways on 2026-10-06:

* `lsusb` — no `1a86` (CH340) / `303a` (ESP32) / `2e8a` (RP2040) / `0483` (STM32)
  device on this host. The only `/dev/ttyUSB*` are this laptop's own Sierra EM7455
  LTE modem (udev-verified).
* `/dev/ttyACM*` — does not exist.
* `balloon-board-lock.py status` → `Connected boards:` empty, all locks FREE.
* `dmesg`/`journalctl -k` restricted; no USB-serial plug events visible.
* Over SSH: `dq05` (100.90.22.201), `t440`, `x280` — **no** `/dev/ttyUSB*` or
  `/dev/ttyACM*` boards. x280's only `ttyACM0` is its own Fibocom L830 LTE modem.

The E80 pair used for every previous sweep was last seen on this bench on
2026-08-22. The card's own gate says: *"If the hardware cannot produce a clean
reading, report the blocker rather than filling in an estimate."* No goodput
number was invented.

**One command once the boards are in** (E80 pair, CH340 + Pico debugprobe):

```bash
cd ~/repos/balloon-e80bench/firmware/e80-stm32-bench
# 0. both boards attached, roles assigned, no rx-logger.service running
# 1. sweep both payloads at BR2600 with a MINIMAL gap so the number is PHY-bound,
#    not gap-bound:  LEN 255 (control) and LEN 511, N large, GAP ~= 2x airtime
python3 tools/e80_bench_ctl.py --length 511 --n 10000 --gap-us 4000 \
    --freq 2440000000 --dbm 5 --tx-log /tmp/flrc511-tx.csv --rx-log /tmp/flrc511-rx.csv
python3 tools/e80_bench_ctl.py --length 255 --n 10000 --gap-us 2500 \
    --freq 2440000000 --dbm 5 --tx-log /tmp/flrc255-tx.csv --rx-log /tmp/flrc255-rx.csv
# 2. STAT? on both boards prints  kbps=  from the FIRMWARE's own calculation:
#    kbps = rx_bytes*8000/elapsed_us   (src/bench_stats.c:106)  <-- the goodput number
# 3. report: actual kbps, LEN, packets, PER, method.
```

Anticipated: with a 4 ms gap at 511 B the host cannot beat its own TX-side wall
(~1487 kbps on RP2040; the E80 console adds its own serial ceiling), so expect the
result to land between the 1484.9 kbps already measured and the 2569.8 kbps
ceiling, and **materially below 2600**. That prediction is the thing to test.

---

## 7. Reproduce

```bash
cd ~/repos/balloon-e80bench
python3 tools/flrc_512b_throughput_audit.py --selftest   # 10/10
python3 tools/flrc_512b_throughput_audit.py              # full audit
python3 tools/flrc_512b_throughput_audit.py --json       # machine-readable
```
