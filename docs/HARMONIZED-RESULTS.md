# Cross-Board Harmonized Bench — Results Summary

**Status:** Living summary (HARM-T9). One row per *config* per *board pair* per *band*.
**Companion docs:** [`HARMONIZED-BENCH-PACKAGE.md`](HARMONIZED-BENCH-PACKAGE.md) (how to run a session),
[`HARMONIZED-RUN-REPORT-TEMPLATE.md`](HARMONIZED-RUN-REPORT-TEMPLATE.md) (per-run report),
[`BENCH-CONSOLE-SPEC.md`](BENCH-CONSOLE-SPEC.md) (normative protocol),
[`harmonization-plan-20260821.md`](harmonization-plan-20260821.md) (task chain HARM-T1..T9).

> **How to read this file.** Feature data lives in the raw CSVs, not here. This
> file is an index: it says which board pair × band × LEN × BR combinations have
> been measured, gives the headline numbers, and links the raw file. A cell that
> has not been measured says `not run` — it is never `0` and never blank.

---

## 1. Data status (read this first)

| Board pair | 868 MHz (sub-GHz baseline) | 2.4 GHz | Notes |
|---|---|---|---|
| `E80BENCH` ↔ `E80BENCH` | **measured** — full LEN × BR matrix, session `2608212001` | **measured** — session `2608222108` | Same-family baseline. Not a cross-board pair: E80↔E80 uses the legacy symmetric FLRC config (Match1, sync `2D D4 D4 B2`), which spec §8 forbids cross-board. |
| `E80BENCH` ↔ `ESP32BENCH` | **not run** — HARM-T7 has zero runs and no artifacts | not applicable (E80 has no 2.4 GHz entry in the spec §9 matrix) | T9's results package is therefore a *scaffold* for this pair. |
| `E80BENCH` ↔ `RP2040BENCH` | **not run** — no raw CSVs on any branch | not applicable | — |
| `ESP32BENCH` ↔ `RP2040BENCH` | **not run** — no raw CSVs on any branch | **not run** — the only spec-legal 2.4 GHz pair; validates the RadioLib RX-path patch | — |

**Honest statement of provenance.** The two `measured` rows above come from the
pre-harmonization E80 sweep tool (`firmware/e80-stm32-bench/tools/e80_sweep_full.py`),
not from `tools/balloon_sweep.py`. They are the **regression baseline** the
harmonization plan §Verification#5 requires ("E80↔E80 511B row unchanged
post-merge"); they are not cross-board evidence. All three cross-board pairs —
the actual deliverable of HARM-T7/T8 — have no data at the time of writing, and
none is inferred or interpolated here.

---

## 2. 868 MHz — sub-GHz baseline

### 2.1 `E80BENCH` ↔ `E80BENCH` — FLRC LEN × BR matrix (measured)

Session `2608212001`, 2026-08-21, bench, boards ~30 cm apart, whip antennas,
N = 50 per config, `GAP = 40 000 µs`, PA 5 dBm, firmware `88a00cf` on both boards.
Raw: [`full-sweep-summary-20260821-200111.csv`](../full-sweep-summary-20260821-200111.csv) ·
[`full-sweep-pkts-20260821-200111.csv`](../full-sweep-pkts-20260821-200111.csv) ·
[report](../full-sweep-report-20260821-200111.md)

| cfg | Mod | BR (kbps) | LEN (B) | rx/n | PER % | RSSI avg | RSSI min | RSSI max | SNR avg | bit_err | crc_err | Raw CSV |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 48 | flrc | 650 | 16 | 50/50 | 0.0 | −70.7 | −72.0 | −63.0 | 0.0 | 0 | 50 | [summary](../full-sweep-summary-20260821-200111.csv) |
| 49 | flrc | 650 | 64 | 50/50 | 0.0 | −70.0 | −85.0 | −63.0 | 0.0 | 0 | 50 | [summary](../full-sweep-summary-20260821-200111.csv) |
| 50 | flrc | 650 | 128 | 50/50 | 0.0 | −70.9 | −84.0 | −62.0 | 0.0 | 0 | 50 | [summary](../full-sweep-summary-20260821-200111.csv) |
| 51 | flrc | 650 | 192 | 50/50 | 0.0 | −70.6 | −72.0 | −63.0 | 0.0 | 0 | 50 | [summary](../full-sweep-summary-20260821-200111.csv) |
| 52 | flrc | 650 | **255** | 50/50 | 0.0 | **−38.0** | −39.0 | −38.0 | 0.0 | 0 | **0** | [summary](../full-sweep-summary-20260821-200111.csv) |
| 53 | flrc | 650 | 256 | 50/50 | 0.0 | −38.9 | −39.0 | −38.0 | 0.0 | 0 | 50 | [summary](../full-sweep-summary-20260821-200111.csv) |
| 54 | flrc | 650 | 300 | 50/50 | 0.0 | −39.9 | −41.0 | −39.0 | 0.0 | 0 | 50 | [summary](../full-sweep-summary-20260821-200111.csv) |
| 55 | flrc | 650 | 384 | 50/50 | 0.0 | −38.9 | −39.0 | −38.0 | 0.0 | 0 | 50 | [summary](../full-sweep-summary-20260821-200111.csv) |
| 56 | flrc | 650 | 448 | 50/50 | 0.0 | −38.5 | −39.0 | −38.0 | 0.0 | 0 | 50 | [summary](../full-sweep-summary-20260821-200111.csv) |
| 57 | flrc | **650** | **511** | **50/50** | **0.0** | −39.4 | −41.0 | −38.0 | 0.0 | 0 | 50 | [summary](../full-sweep-summary-20260821-200111.csv) |
| 58 | flrc | 1300 | 384 | 50/50 | 0.0 | −39.9 | −41.0 | −39.0 | 0.0 | 0 | 50 | [summary](../full-sweep-summary-20260821-200111.csv) |
| 59 | flrc | **1300** | **511** | **50/50** | **0.0** | −39.9 | −41.0 | −39.0 | 0.0 | 0 | 50 | [summary](../full-sweep-summary-20260821-200111.csv) |
| 60 | flrc | **2600** | **511** | **50/50** | **0.0** | −35.7 | −37.0 | −34.0 | 0.0 | 0 | 50 | [summary](../full-sweep-summary-20260821-200111.csv) |

Acceptance for this matrix: 511 B row 50/50 ✔, `bit_err = 0` on all received
packets ✔ (PRBS ON), `pcrc16` present (fw `88a00cf` = BUF-T5a) ✔, `STAT?`
`drops = 0` per the report's zero-drop note ✔.

**Anomalies visible in this baseline** — carry them into every cross-board report:

- **LEN = 255 RSSI step.** RSSI jumps ≈ +32 dB between LEN 192 and LEN 255
  (−70.6 → −38.0 dBm) and stays high above it. This is the known boundary
  defect documented as BUG 3 in [`rca-fix-plan-20260821.md`](rca-fix-plan-20260821.md)
  ("RSSI jumps +35 dB at LEN ≥ 255"). Treat any LEN 254/255/256 comparison as
  suspect until the boundary is bisected on hardware.
- **FLRC `crc_err` counter.** `crc_err = 50` on FLRC rows that also report
  `rx_pkts = 50`. The run's own metadata says why:
  `"integrity_note": "pre-Match123-fix fw: trust bit_err (PRBS-15), not crc_ok, for FLRC"`
  ([`full-sweep-results-2g4-meta-20260822-210817.json`](../full-sweep-results-2g4-meta-20260822-210817.json)).
  For FLRC rows in these pre-Match123 sweeps, **`bit_err` is the integrity
  signal and `crc_err` is not.**
- **LoRa LEN = 511 is refused, not failed.** Config 30 (`SF8 BW125 PA10 L511`)
  reports `rx_pkts = 0`, `tx_done = False` — the LEN cap (spec §6: 255 LoRa /
  511 FLRC) rejected the burst. Cross-board reports must record such a row as
  `refused by LEN cap`, not as a 0 % link result.

### 2.2 `E80BENCH` ↔ `ESP32BENCH` (HARM-T7) — not run

| cfg | Mod | BR (kbps) | LEN (B) | Forward (E80 TX → ESP32 RX) | Reverse (ESP32 TX → E80 RX) | Raw CSV |
|---|---|---|---|---|---|---|
| — | flrc | 650 | 16, 64, 128, 192, 255, 256, 300, 384, 448, 511 | not run | not run | — |
| — | flrc | 1300 | 384, 511 | not run | not run | — |
| — | flrc | 2600 | 511 | not run | not run | — |

Planned matrix per the HARM-T7 card (FLRC 650 kbps, PA 5, @868.0 MHz, N = 50,
both directions, plus BR-interaction rows 1300×384 / 1300×511 / 2600×511).
**Blocking reason:** no sweep CSVs exist on any branch of this repo or on the
ESP32 repo, and `STAT`/flash-queue evidence for a session is absent. The card is
un-run, so this table stays `not run` until the session happens.

### 2.3 `E80BENCH` ↔ `RP2040BENCH` (HARM-T8) — not run

| cfg | Mod | BR (kbps) | LEN (B) | Result | Raw CSV |
|---|---|---|---|---|---|
| — | flrc | 650 / 1300 / 2600 | `<T7 matrix>` | not run | — |

Planned per the HARM-T8 card. No `harm/t8-results` branch and no CSVs exist.

### 2.4 `ESP32BENCH` ↔ `RP2040BENCH` @868 — not run

| cfg | Mod | BR (kbps) | LEN (B) | Result | Raw CSV |
|---|---|---|---|---|---|
| — | flrc | `<T8 matrix>` | — | not run | — |

---

## 3. 2.4 GHz — separate band, separate section

> **Semantics note — 868 MHz baseline vs 2.4 GHz.** These two bands are **not
> comparable** and must never share a table, a PER denominator, or a conclusion:
>
> 1. **Different legal pairs.** Spec §9 allows 2.4 GHz cross-board work *only* on
>    `ESP32BENCH ↔ RP2040BENCH`. E80 has no 2.4 GHz entry in the spec matrix, so
>    an E80↔ESP32 or E80↔RP2040 row simply cannot exist at 2440 MHz — the host
>    tool refuses such a pair before touching hardware, with
>    `REFUSED (pre-hardware, spec enforcement): FREQ 2440000000 not allowed for pair E80BENCH<->ESP32BENCH (spec S9)`
>    (`tools/balloon_sweep.py` `validate_config()` → `freq_pair_ok()`).
> 2. **Different RF path, therefore different RSSI scale.** At 868 MHz the
>    measured bench RSSI sits near −39…−71 dBm; the 2.4 GHz path on the same
>    bench reports ≈ −71…−80 dBm for the *same* 30 cm geometry. Comparing an
>    868 MHz RSSI number with a 2.4 GHz RSSI number measures the antenna and
>    feed path, not the link.
> 3. **Different antenna port.** 868 MHz uses the sub-GHz jack, 2.4 GHz the
>    2.4 GHz jack (NiceRF LR2021 Pin 9 vs Pin 10). A run that swapped feeds is
>    not comparable to one that did not.
> 4. **Different purpose.** 868 MHz is the *comparability baseline* across all
>    three families. 2.4 GHz exists to validate the ESP32 RadioLib RX-path
>    patch; it is a patch-verification measurement, not a range claim.
> 5. **Reporting rule.** A cross-board result is quoted as
>    `pair @ band`, e.g. `E80BENCH↔ESP32BENCH @868`. A bare `PER` with no band
>    is not a reportable number.

### 3.1 `E80BENCH` ↔ `E80BENCH` @2440 MHz (measured, off-spec for cross-board)

Session `2608222108`, 2026-08-22, firmware `0561b29` (`BAND OVERRIDE` + HF path,
console 2 Mbaud), N = 50, GAP 10 000 µs, PA 5, ~30 cm, SMA.
Raw: [`full-sweep-results-2g4-summary-20260822-210817.csv`](../full-sweep-results-2g4-summary-20260822-210817.csv) ·
[report](../full-sweep-results-2g4-report-20260822-210817.md).

This run proves the E80 hardware *can* drive a 2.4 GHz path (via
`BAND OVERRIDE`), but it is **E80↔E80 on the legacy symmetric config** and is
recorded here only so nobody re-derives it. It is not usable as a cross-board
2.4 GHz baseline: spec §9 gives E80 no 2.4 GHz cross-board entry.

| cfg | Mod | BR (kbps) | LEN (B) | rx/n | RSSI avg | Raw CSV |
|---|---|---|---|---|---|---|
| 94 | flrc | 260 | 64 | 50/50 | −78.7 | [summary](../full-sweep-results-2g4-summary-20260822-210817.csv) |
| 95 | flrc | 325 | 64 | 50/50 | −79.1 | [summary](../full-sweep-results-2g4-summary-20260822-210817.csv) |
| 96 | flrc | 520 | 64 | 50/50 | −79.8 | [summary](../full-sweep-results-2g4-summary-20260822-210817.csv) |
| 97 | flrc | 650 | 64 | 50/50 | −70.9 | [summary](../full-sweep-results-2g4-summary-20260822-210817.csv) |
| 98 | flrc | 1040 | 64 | 50/50 | −72.5 | [summary](../full-sweep-results-2g4-summary-20260822-210817.csv) |
| 99 | flrc | 1300 | 64 | 51/51 | −73.0 | [summary](../full-sweep-results-2g4-summary-20260822-210817.csv) |
| 100 | flrc | 2080 | 64 | 50/50 | −74.4 | [summary](../full-sweep-results-2g4-summary-20260822-210817.csv) |
| 101 | flrc | 2600 | 64 | 50/50 | −74.4 | [summary](../full-sweep-results-2g4-summary-20260822-210817.csv) |
| 102–107 | flrc | 650 @ PA 0/1/3/5/7/10 | 64 | 50/50 each | −71.3 → −74.1 | [summary](../full-sweep-results-2g4-summary-20260822-210817.csv) |

### 3.2 `ESP32BENCH` ↔ `RP2040BENCH` @2440 MHz — not run

The only spec-legal 2.4 GHz cross-board pair. This is the measurement that
closes the open question "does the forked RadioLib 2.4 GHz RX path actually
receive?" (see [`HARMONIZED-BENCH-PACKAGE.md`](HARMONIZED-BENCH-PACKAGE.md) §5).
No data.

| cfg | Mod | BR (kbps) | LEN (B) | Forward | Reverse | Raw CSV |
|---|---|---|---|---|---|---|
| — | flrc | 650 / 1300 / 2600 | `<T8 matrix>` | not run | not run | — |

---

## 4. Raw data inventory

| File | Session | Pair | Band | Contents |
|---|---|---|---|---|
| [`full-sweep-summary-20260821-200111.csv`](../full-sweep-summary-20260821-200111.csv) | 2608212001 | E80↔E80 | 868 | one row per config (21 columns) |
| [`full-sweep-pkts-20260821-200111.csv`](../full-sweep-pkts-20260821-200111.csv) | 2608212001 | E80↔E80 | 868 | one row per received packet |
| [`full-sweep-report-20260821-200111.md`](../full-sweep-report-20260821-200111.md) | 2608212001 | E80↔E80 | 868 | human summary, 61 configs |
| [`full-sweep-results-2g4-summary-20260822-210817.csv`](../full-sweep-results-2g4-summary-20260822-210817.csv) | 2608222108 | E80↔E80 | 2440 | one row per config |
| [`full-sweep-results-2g4-meta-20260822-210817.json`](../full-sweep-results-2g4-meta-20260822-210817.json) | 2608222108 | E80↔E80 | 2440 | run metadata + integrity note |
| [`data/e80-bench/20260826-twomachine-desk/`](../data/e80-bench/20260826-twomachine-desk/) | 2608261211 | E80↔E80 | 868 (869.525 MHz) | first harmonized 25-column PKT capture, FLRC LEN 511, two-machine desk run |
| [`firmware/e80-stm32-bench/docs/hardware-test-data/rx-cross-machine-2608232130.csv`](../firmware/e80-stm32-bench/docs/hardware-test-data/rx-cross-machine-2608232130.csv) | 2608232130 | E80↔E80 | 868 | first "harmonized format" test, 868.0 MHz, FLRC LEN 64 |

Cross-board session CSVs are expected at
`data/e80-bench/<session>-<pair>-<band>/` with the file set
`<prefix>-summary.csv`, `<prefix>-pkts.csv`, `<prefix>-report.md`,
`<prefix>-meta.json` (`tools/balloon_sweep.py` output shape). None exist yet.

## 5. How to add a row to this file

1. Run the session per [`HARMONIZED-BENCH-PACKAGE.md`](HARMONIZED-BENCH-PACKAGE.md) §4.
2. Write the per-run report from
   [`HARMONIZED-RUN-REPORT-TEMPLATE.md`](HARMONIZED-RUN-REPORT-TEMPLATE.md) to
   `docs/runs/<run-id>.md`.
3. Copy that run's config rows into the matching **pair × band** table above,
   in §2 for 868 MHz and §3 for 2.4 GHz. Never move a row between bands.
4. Link the raw CSV. Replace the `not run` text; do not leave a partially
   filled table without saying which configs are still missing.
5. Update §1 "Data status". If a pair × band gains its first data, say so — that
   is the fact downstream readers scan for.
6. Commit the docs, the per-run report, and the CSVs **in one commit** so the
   numbers and their evidence share a revision.
