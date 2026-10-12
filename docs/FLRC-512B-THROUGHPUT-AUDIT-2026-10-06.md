# FLRC 512 B / 2.6 Mbps — settled

**Card:** `balloon/t_6b68897c` (FLRC-512B) · **Date:** 2026-10-06 (rev 2)
**Scope:** settle the "~2.6 Mbps at 512 B payload" report. Deliverables 1–3 of the
card; deliverable 4 (a *fresh* 512 B sweep) is **not** met — see §7.

**Tool:** `tools/flrc_512b_throughput_audit.py` (`--selftest` 16/16) and
`tests/test_flrc_512b_throughput_audit.py` (21 host tests, no radio).
Every number below is either an arithmetic result from that tool or a file:line on
disk. Nothing was measured on a radio for this document.

> **rev 2 note (2026-10-06, second pass over this same card).** rev 1 (commit
> `c3bb6e6` on main) got the verdict right but its second ceiling model was
> mislabelled — it called an *uncoded* model "the driver model" and quoted
> 2550/2569 kbps for it. The LR20xx driver's numerator does scale by the coding
> rate, and the firmware runs **CR 3/4**, so the real ceiling is a third lower.
> §2, §3 and §8 are corrected; the verdict is unchanged and now stronger.

---

## 1. Verdict

**The 2.6 Mbps figure is (i) — the configured FLRC *air rate*, not delivered
goodput.** It is the raw physical-layer rate of `BR_2_600_BW_2_666`
(`lr20xx_radio_flrc.c:341-342`: `get_flrc_br_in_kbps` → `2600`). No payload size
can make goodput reach it, and a ~2.6 Mbps *goodput* figure is not merely
unmeasured, it is **impossible under every model below**.

**The 512 B run does not exist.** Payloads `{16, 64, 128, 192, 255, 256, 300, 384,
448, 511}` were measured; **512 was never measured anywhere on disk, and cannot
be — 511 B is the driver's documented maximum** (`lr20xx_radio_flrc_types.h:210`:
`pld_len_in_bytes` *"FLRC payload length in byte - in [6:511]"*; the bench
firmware enforces it at runtime through its own named clamp,
`#define BENCH_START_LEN_MAX_FLRC 511u` (`bench_cmd.h:157`), applied by
`bench_start_len_ok()` (`bench_cmd.c:593-604`) at both the TX and RX start
branches (`bench.c:768`, `:795`); the START parser also re-checks the same
literal range (`bench_cmd.c:365`, `v < 6 || v > 511` — duplicated constant,
a harmless belt-and-braces check).

Those two in-repo layers are what the audit tool reads (report key
`radio_lib_flrc_max` → `flrc_max_payload()`), and they are what makes the number
reproducible on a CI runner. A RadioLib checkout **outside** the repo is now only
an advisory cross-check: the snapshot archived at
`docs/lr2021-research/radiolib-master/` does not carry
`RADIOLIB_LR2021_MAX_PACKET_LENGTH_FLRC` (upstream issue #1882, "Fix some LR2021
constants", was still open at the 2026-09-30 retrieval), so requiring that
host-local checkout is what turned the repo-root `Tests` workflow red on main for
four consecutive pushes (2026-10-09/10, runs 37992095474, 37988348046,
37946525396, 37946322065).

So the physical claim behind the report — *"doubling the payload raises
throughput"* — is **correct in direction and already demonstrated**: 511 B FLRC is
measured working at 50/50 reception and zero PRBS-15 payload bit errors at BR650,
BR1300 and **BR2600** (§3). What does not exist is a sustained (no-gap) goodput
number for it, because every 511 B burst on disk was run at a 40 ms inter-packet
gap, which floors the delivered rate at ~90 kbps.

### The card's either/or, answered

* **(i) holds.** 2600 kbps is the configured air rate.
* **(ii) is also true, but it does not help.** The repo's 2540/2570 kbps ceiling
  model *is* wrong — it is an **uncoded** (CR NONE) bound, and the firmware ships
  **CR 3/4** (`radio_bench.c:55`, `:171-180`, `:314`). Correcting it makes the
  ceiling *fall* to ~1910 kbps at 511 B, i.e. about **27 % below** 2600, not
  closer to it. The model was optimistic, never pessimistic.

---

## 2. Ceilings — goodput cannot reach 2600, at any payload, under any model

Zero host/SPI overhead (the optimistic limit). Three explicitly-labelled models,
because they differ by a third and the repo has published two of them:

| LEN | uncoded (repo model) | uncoded + CRC | **fw CR 3/4 (shipped config)** |
|----:|---------------------:|--------------:|-------------------------------:|
| 127 | 409.2 µs / 2482.7 kbps | 415.4 µs / 2445.9 kbps | **565.0 µs / 1798.2 kbps** |
| 255 | 803.1 µs / 2540.2 kbps | 809.2 µs / 2520.9 kbps | **1090.4 µs / 1870.9 kbps** |
| 511 | 1590.8 µs / **2569.8 kbps** | 1596.9 µs / 2559.9 kbps | **2140.4 µs / 1909.9 kbps** |

* **uncoded (repo model)** = `16 b preamble + 32 b sync + payload·8`, no CRC —
  `lr2021-flrc-24ghz-datasheet-audit-2026-07-26.md:80`. Reproduces its 2540 figure
  and the card's 2570 figure. This is the model the card quotes, and it is a
  **CR NONE** bound.
* **uncoded + CRC** = the same numerator with the firmware's 2-byte CRC.
* **fw CR 3/4** = the LR20xx driver's own time-on-air numerator
  (`lr20xx_radio_flrc.c:285-309`) with the parameters `radio_bench.c:52-69` actually
  configures (`cr = CR_3_4`, `header = FIX_LEN`, `crc = 2 B`, `preamble = 32 b`,
  `sync = 4 B`):
  ```
  n_coded              = header(0) + tail(6) + crc(16) + payload·8
  n_coded_after_decode = ceil(12 · n_coded / 9)      ; ceil_den = 9 for CR 3/4
  numerator            = n_coded_after_decode + preamble(32) + agc(21) + sync(32)
  airtime              = numerator / 2 600 000 bps
  ```
  CR 3/4 costs 4/3 in air time, so the payload rate tops out at 2600 × 3/4 = 1950
  kbps minus overhead. At 511 B that is **1909.9 kbps**, which agrees to **0.6 %**
  with the *independently* computed on-air figure already in the repo —
  **1921.8 kbps** (LEN·8/ToA @ CR 3/4, `full-sweep-report-20260821-175612.md:99`).
  Two derivations from different directions landing inside 1 % is the cross-check
  that rev 1 was missing.

**Every model is below 2600.** The card's conflict therefore resolves cleanly:
the 2540/2570 model is not what makes 2.6 Mbps wrong — expecting a *configured air
rate* to appear as delivered payload is. And the model that matters for our
measurements is the CR-3/4 one, ~1910 kbps, not ~2550.

**The best measured sustained figure on disk is 1484.9 kbps**
(`sustained-throughput-results-2026-07-23.md:7`, BR2600, **LEN 127**, 0.00 % PER,
TX-side-limited at ~1487 kbps). Against the corrected ceiling that is **82.6 % of
1798.2 kbps** for that length — consistent with a host-side SPI wall, and 57.1 % of
the raw 2600 air rate (the figure the old doc quoted).

Corollary the card did not ask for: **the ceiling gain from 255 B → 511 B is
+2.1 % (1870.9 → 1909.9 kbps), not ~2×.** Doubling the payload doubles the air
time too; it only amortises the fixed preamble/sync/AGC overhead better. The lever
is **modulation + payload size + pipelining**, in that order.

## 3. What was actually measured at ≥ 255 B

`tools/flrc_512b_throughput_audit.py` enumerates every FLRC row with `plen ≥ 255`
in the on-disk sweeps. Three sessions, same configuration (fw `88a00cf`, **868 MHz**,
PA 5 dBm, SMA ~30 cm apart, GAP 40 ms, CR 3/4):

| LEN | BR | rx | crc_err | PRBS bit_err | tx_done |
|----:|---:|----:|--------:|-------------:|:-------:|
| 255 | 650 | 50/50 | 0/50 | 0 | ✓ |
| 256 | 650 | 50/50 | 50 | 0 | ✓ |
| 300 | 650 | 50/50 | 50 | 0 | ✓ |
| 384 | 650 | 50/50 | 50 | 0 | ✓ |
| 448 | 650 | 50/50 | 50 | 0 | ✓ |
| **511** | **650** | **50/50** † | 50 | **0** | ✓ |
| 384 | 1300 | 50/50 | 50 | 0 | ✓ |
| **511** | **1300** | **50/50** | 50 | **0** | ✓ |
| **511** | **2600** | **50/50** | 50 | **0** | ✓ |

† the `175612` session recorded `51/51` for this row (one stray 51st packet, 5.3 s
span — `full-sweep-report-20260821-175612.md:97-99`); the `200111` and 2g4
sessions recorded `50/50`. The rows are otherwise identical.

Sources: `full-sweep-summary-20260821-175612.csv`,
`full-sweep-summary-20260821-200111.csv`,
`full-sweep-results-2g4-summary-20260822-210817.csv`.

Reading it correctly matters:

* **`bit_err = 0` is the integrity signal.** The `crc_err` column is the *chip* CRC
  verdict, which is unreliable in FLRC on this firmware (root cause: RX sync-match
  mode; fix in review). Every length except 255 reports `crc_err = 50`, including
  lengths that are demonstrably fine. Do not read the `50` as loss.
* **`rx 50/50` at 511 B × BR2600 is a delivery result, not a throughput result.**
  At GAP 40 ms the delivered rate is gap-limited (~90 kbps); the on-air payload
  rate is 1.92 Mbps (`full-sweep-report-20260821-175612.md:99`). Neither number is
  the sustained goodput the card asks for.
* **All ≥255 B evidence is 868 MHz.** The card asked for 2440 MHz. Frequency does
  not change the packet-length/bitrate ceiling (it is a PHY-length property) — it
  changes link margin, and this bench is a 30 cm SMA pair where margin is not the
  binding constraint. The *sustained* run still has to be done at the frequency
  the claim is about; see §7.

## 4. Firmware note from the card — answered

`firmware/rp2040/src/flrc_throughput_tx.cpp:8` says *"127-byte packets (max SX1280
FLRC)"*. Confirmed:

* **It is an SX1280 limit only.** That file is explicitly marked
  *"DEPRECATED — DO NOT USE. This file uses SX1280 raw SPI commands (wrong chip).
  Our chip is LR2021 (Gen 4), NOT SX1280. See ADR-101."* (`:2-3`). The 127 B
  ceiling is an artefact of dead code written for the wrong radio. (The LR20xx
  driver retains an SX1280-compat range note of `[6:127]` alongside the real
  `[6:511]` — *that* is the "127" that leaked into the comment.)
* **The LR2021 path takes 511 B in one FIFO write.** `SET_FLRC_PACKET_PARAMS` carries
  a 16-bit big-endian payload length (`lr20xx_radio_flrc.c:198-201`: `pld_len_in_bytes
  >> 8`, `>> 0`); the E80 firmware enforces `6–511` at runtime (`bench.c:786-789`)
  and writes the whole frame with a single `lr20xx_radio_fifo_write_tx(context, buf,
  len)` — no chunking (`radio_bench.c:427`) — and it demonstrably delivers 511 B (§3).
* The "512" in the report is **one byte past the documented range**. The real
  headline number is 511 B.

## 5. Docs corrected in this commit

| File | Change |
|---|---|
| `docs/FLRC-512B-THROUGHPUT-AUDIT-2026-10-06.md` | this file, rev 2 (§2 corrected to three models incl. CR 3/4; §8 correction log) |
| `docs/PLAN-speed-optimization.md` | §1.1 table: the "2550 / 2569 kbps driver model" row replaced with the CR-3/4 ceilings (1871 / 1910 kbps) |
| `docs/frequency-plan-868.md` | FLRC 2600 row annotated: these are *airtime* rows, 2600 kbps is the air rate; ceiling with the shipped CR 3/4 is ~1910 kbps |
| `tools/plot_full_characterization.py` | `phase_defs` label `"2600k"` → `"2600k(air)"` for the four HF/LF-FLRC-2600 phases |
| `tools/flrc_512b_throughput_audit.py`, `tests/test_flrc_512b_throughput_audit.py` | CR-3/4 model added, mislabelled model renamed, 4 capability probes (incl. the CR itself) |
| `docs/SX1280-ARRAY-FEASIBILITY.md` (branch `pr/029-dual-band-flight-board`, commit `52aa3b4`) | replaced the caveat with the settled figure; lever re-stated as **modulation + payload size**, not radio count |

`PLAN-speed-optimization.md` was **not** rewritten to claim 2.6 Mbps — the card's
explicit instruction. The stale 1391 kbps figure is kept as history and annotated.

## 6. What is NOT done — and why

The card's deliverable 1 is *"run the sweep at 512 B (and 255 B as control) at
2600 kbps FLRC, 2440 MHz"*. **Not done: no radio is attached to any reachable
machine.** Re-verified 2026-10-06 by this run (rev 2) from scratch:

* `lsusb` on this host — no `1a86` (CH340) / `303a` (ESP32) / `2e8a` (RP2040) /
  `0483` (STM32) device. The only `/dev/ttyUSB*` (`ttyUSB0-2`) are this laptop's own
  Sierra EM7455 LTE modem (`lsusb` shows `1199:9079 Sierra Wireless EM7455`).
* `/dev/ttyACM*` — does not exist.
* `balloon-board-lock.py status` → `Connected boards:` **empty**; all locks FREE.
* Over SSH: `dq05` (reachable, `c03rad0r-DQ05proplus`) has **no** `/dev/ttyACM*` /
  `/dev/ttyUSB*`; `t440` and `x280` are currently unreachable
  (`Too many authentication failures` — ssh key state, not a board statement).

The E80 pair used for every previous sweep was last seen on this bench on
2026-08-22. The card's own gate says: *"If the hardware cannot produce a clean
reading, report the blocker rather than filling in an estimate."* No goodput
number was invented; this is the honest blocker, recorded on the card.

**One command once the boards are in** (E80 pair, CH340 + Pico debugprobe):

```bash
cd ~/repos/balloon-e80bench/firmware/e80-stm32-bench
# 0. both boards attached, roles assigned, no rx-logger.service running
# 1. sweep both payloads at BR2600 with a MINIMAL gap so the number is PHY-bound,
#    not gap-bound:  LEN 255 (control) and LEN 511, N large, GAP ~= 2x airtime
#    (511 B @ CR3/4 = 2.14 ms on air, so GAP 4000 us is ~1.9x airtime)
python3 tools/e80_bench_ctl.py --length 511 --n 10000 --gap-us 4000 \
    --freq 2440000000 --dbm 5 --tx-log /tmp/flrc511-tx.csv --rx-log /tmp/flrc511-rx.csv
python3 tools/e80_bench_ctl.py --length 255 --n 10000 --gap-us 2500 \
    --freq 2440000000 --dbm 5 --tx-log /tmp/flrc255-tx.csv --rx-log /tmp/flrc255-rx.csv
# 2. STAT? on both boards prints  kbps=  from the FIRMWARE's own calculation:
#    kbps = rx_bytes*8000/elapsed_us   (src/bench_stats.c:106-111)  <-- the goodput number
# 3. report: actual kbps, LEN, packets, PER, method.
```

Anticipated: at 511 B / CR 3/4 the PHY ceiling is 1910 kbps and the host SPI write
is 4× longer per packet than at LEN 127, so expect the result to land at or below
the 1484.9 kbps already measured and **materially below 2600**. That prediction is
the thing to test.

## 7. Correction log — rev 2 (2026-10-06)

rev 1 of this document (commit `c3bb6e6`, pushed to main on GitHub and ngit) said,
in §2, that the "driver model = 32 b preamble + 4 B sync + (payload+2)·8" was
*"what the LR20xx driver's own on-air numerator computes"*, and quoted 2550.1 /
2569.8 kbps from it. Two things were wrong with that:

1. **The driver's numerator is coding-rate scaled.** `lr20xx_get_flrc_time_on_air_numerator`
   (`lr20xx_radio_flrc.c:285-309`) computes `ceil(12 · n_coded / ceil_den) + n_uncoded`
   with `ceil_den = 9` for CR 3/4 (`lr20xx_get_flrc_cr_scalled_numerator`, `:311-332`),
   adds the 6-bit tail and the 21-bit AGC preamble, and only then divides by the bit
   rate. rev 1's model omitted all three.
2. **The firmware ships CR 3/4**, not CR NONE (`radio_bench.c:55`), so the omission
   was worth a third of the ceiling, in the direction that flattered the number.

rev 1 also asserted that "`lr20xx_radio_flrc.c` rejects `pld_len > 511 - crc_bytes`".
**No such check exists in that file** — the 511 bound is documented in
`lr20xx_radio_flrc_types.h:210` and enforced in `bench.c:786-789`; the driver's
only CRC arithmetic is in the time-on-air numerator. That sentence is removed.

Both errors are the same class of mistake: quoting a plausible-looking model
instead of reading the code that produces the number. The tool now probes for the
CR constant itself (`fw_flrc_cr_3_4`) and a host test fails if the firmware stops
shipping CR 3/4, so the next reader cannot silently re-derive the old figures.

**What rev 2 changes:** §2 (three models, corrected numbers), §3 (the 51/51 row,
the 868 MHz scope), §4 (the SX1280-compat `[6:127]` note), §5 (§1.1 of
PLAN-speed-optimization.md re-corrected), §7 (this log).
**What rev 2 does not change:** the verdict (i), the impossibility of 2.6 Mbps
goodput, the 1484.9 kbps best-measured sustained figure, and the fact that the
sustained 511 B run still has not happened.

---

## 8. Reproduce

```bash
cd ~/repos/balloon-e80bench
python3 tools/flrc_512b_throughput_audit.py --selftest   # 16/16
python3 tools/flrc_512b_throughput_audit.py              # full audit
python3 tools/flrc_512b_throughput_audit.py --json       # machine-readable
/usr/bin/python3 -m pytest tests/test_flrc_512b_throughput_audit.py -q   # 19 passed
```
