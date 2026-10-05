# Harmonized Run Report — Template

**Status:** Template (HARM-T9)
**Applies to:** any cross-board bench run driven by `tools/balloon_sweep.py`
**Normative references:** [`BENCH-CONSOLE-SPEC.md`](BENCH-CONSOLE-SPEC.md) v1.0,
[`harmonization-plan-20260821.md`](harmonization-plan-20260821.md),
[`BALLOON-SWEEP-TOOL.md`](BALLOON-SWEEP-TOOL.md),
[`HARMONIZED-BENCH-PACKAGE.md`](HARMONIZED-BENCH-PACKAGE.md)

Copy this file to `docs/runs/<session>-<txpair>-<rxpair>-<band>.md`, fill every
`<...>` slot, and commit it **in the same commit** as the raw CSVs it describes.

Rules for this document:

1. Every number in §6 must be reproducible from the raw CSVs linked in §7. If a
   number cannot be traced to a raw file, it does not go in the table.
2. A config that was not run is written as `not run` — never as `0`, `n/a`, or
   left blank. Blank cells are indistinguishable from missing data.
3. Band sections do not mix. 868 MHz rows and 2.4 GHz rows live in separate
   tables under separate headings (see the band-pair semantics note,
   [`HARMONIZED-RESULTS.md`](HARMONIZED-RESULTS.md)).
4. Anomalies are reported in §8 even when the run passes acceptance. A run with
   a hidden anomaly is worse than a run with a documented one.

---

## 1. Run identity

| Field | Value |
|---|---|
| Report ID | `<yymmddHHMM>-<txtag>-<rxtag>-<band>` |
| Session tag (`SESSION <id>`) | `<yymmddHHMM>` |
| UTC start / end | `<2026-..-..THH:MM:SSZ>` → `<...>` |
| Operator | `<name>` |
| Board lock holder (`BALLOON_TRACK`) | `<track>` |
| FLASH-QUEUE row | `<link or row id>` |
| Run by (agent/human) | `<worker-balloon \| human>` |

## 2. Build provenance (per board)

The `fw=<sha7>` token in each board's `ID?` reply is authoritative. Paste the
full `ID?` line, not a paraphrase.

| Role | Board tag | Port | Probe / UUID | Firmware branch | `fw=` (from `ID?`) | Full `ID?` line |
|---|---|---|---|---|---|---|
| TX | `<E80BENCH \| ESP32BENCH \| RP2040BENCH>` | `<dev>` | `<serial>` | `<branch@sha>` | `<sha7>` | `<paste>` |
| RX | `<...>` | `<dev>` | `<serial>` | `<branch@sha>` | `<sha7>` | `<paste>` |

Tooling versions:

| Item | Version |
|---|---|
| `tools/balloon_sweep.py` `__version__` | `<x.y.z>` |
| BENCH-CONSOLE-SPEC | `v1.0` |
| Cross-board FLRC config | Match123 + sync `0x12AD101B` + chip CRC ON + CR 3/4 + preamble 32 (spec §8) |

## 3. Physical setup

| Field | Value |
|---|---|
| Band / frequency (Hz) | `<868000000 \| 2440000000>` |
| Distance TX↔RX | `<m>` |
| Environment | `<indoor desk \| outdoor line-of-sight>` |
| Antennas | `<per board: sub-GHz / 2.4 GHz, model, connector>` |
| PA mode | `<indoor cap 0-10 dBm \| outdoor unlock +22>` |
| Notes | `<anything that changes comparability>` |

## 4. Config matrix

List the planned configs exactly as passed to the tool.

| # | Label | Mod | SF | BW (kHz) | BR (kbps) | PA (dBm) | LEN (B) | GAP (µs) | N |
|---|---|---|---|---|---|---|---|---|---|
| 0 | `<label>` | `<flrc \| lora>` | `<sf>` | `<bw>` | `<br>` | `<pa>` | `<len>` | `<gap>` | `<n>` |

Spec-derived constraints that must hold for every row (host enforces
pre-hardware; if the tool refused the plan, stop and record the refusal):

| Rule | Check |
|---|---|
| LEN ≤ 255 (LoRa) / ≤ 511 (FLRC) — spec §6 | `<ok \| violation>` |
| GAP ≥ 40 000 µs whenever LEN > 256 — spec §7 | `<ok \| violation>` |
| FREQ inside the TX∩RX board plan — spec §9 | `<ok \| violation>` |
| 2.4 GHz rows only on the ESP32↔RP2040 pair — spec §9 | `<ok \| violation \| no 2.4G rows>` |

## 5. Acceptance criteria

From the harmonization plan §Verification. Copy the tool's raw output for each.

| # | Criterion | Required | Observed | Verdict |
|---|---|---|---|---|
| A1 | FLRC LEN=511 row (both directions) | 50/50 = 100 % | `<50/50>` | `<PASS \| FAIL>` |
| A2 | PRBS-15 bit errors on every received packet (`PRBS ON`) | `bit_err = 0` | `<0>` | `<PASS \| FAIL>` |
| A3 | `pcrc16` present on received rows (spec §5 / BUF-T5a) | non-zero on all CRC-OK rows | `<n/n>` | `<PASS \| FAIL>` |
| A4 | `STAT?` radio event-mailbox drops | `drops = 0` | `<0>` | `<PASS \| FAIL>` |
| A5 | Same `SESSION` id on both ends, joinable CSVs | yes | `<yes/no>` | `<PASS \| FAIL>` |

If A4 fails, rerun with `GAP` doubled and report **both** runs (§6 gets a
second block, or a `gap_us` column with two values). Do not silently discard the
first run.

## 6. Results — 868 MHz (sub-GHz baseline)

One row per config. `rx/n` = received packets / transmitted packets.

| # | Label | Mod | BR (kbps) | LEN | rx/n | PER % | RSSI avg | RSSI min | RSSI max | SNR avg | crc_err | bit_err | drops | kbps | Raw file |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | `<label>` | `<mod>` | `<br>` | `<len>` | `<50/50>` | `<0.0>` | `<dBm>` | `<dBm>` | `<dBm>` | `<dB>` | `<n>` | `<n>` | `<n>` | `<n>` | `[<file>](../..//<path>)` |

## 6b. Results — 2.4 GHz (separate band; never mixed with §6)

Only populated for the `ESP32BENCH ↔ RP2040BENCH` pair (spec §9). If the run has
no 2.4 GHz rows, write `not run (band not exercised)` and delete the table.

| # | Label | Mod | BR (kbps) | LEN | rx/n | PER % | RSSI avg | SNR avg | crc_err | bit_err | drops | Raw file |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | `<label>` | `<mod>` | `<br>` | `<len>` | `<50/50>` | `<0.0>` | `<dBm>` | `<dB>` | `<n>` | `<n>` | `<n>` | `[<file>](<path>)` |

## 7. Data products

| Artifact | Path | sha256 |
|---|---|---|
| Summary CSV | `<prefix>-summary.csv` | `<sha256>` |
| Per-packet CSV | `<prefix>-pkts.csv` | `<sha256>` |
| Tool report | `<prefix>-report.md` | `<sha256>` |
| Meta JSON | `<prefix>-meta.json` | `<sha256>` |

Join keys across boards/runs: `session`, `config`, `pkt_idx` (`replicate`
disambiguates re-runs of one config). `CONFIG_START,<config>,<replicate>,<ts_ms>`
marker lines bracket each config segment in the capture log.

```bash
# how to reproduce the numbers above from the raw CSVs
python3 tools/balloon_sweep.py --tx <family> --rx <family> --session <id> \
    --only <idx> --dry-run          # pre-hardware plan check
```

## 8. Anomalies, deviations, open items

- `<anomaly: what was seen, which config, whether it reproduces>`
- `<spec deviation: what and why>`
- `<data gap: configs planned but not run, and why>`

Known cross-run anomalies to check for explicitly (cite
[`rca-fix-plan-20260821.md`](rca-fix-plan-20260821.md) BUG 3 and re-state here
whether they were seen):

| Anomaly | Expected signature | Seen this run? |
|---|---|---|
| LEN = 255 boundary | RSSI step of ≈ +30…+35 dB between LEN 254→255 | `<yes/no>` |
| FLRC `crc_err` counter | non-zero `crc_err` on FLRC rows with 100 % `rx_pkts` in the 2026-08-21/22 E80 sweeps | `<yes/no>` |
| 2.4 GHz silent fallback | RSSI ≈ −70 dBm on 2.4 GHz FLRC rows (sub-GHz-like path) | `<yes/no/not applicable>` |

## 9. Comparability statement

State plainly whether this run's rows may be compared with the rows already in
[`HARMONIZED-RESULTS.md`](HARMONIZED-RESULTS.md):

- Same band? `<yes/no — mixed bands are never comparable>`
- Same frame config (FLRC golden config / LoRa SF+BW+CR)? `<yes/no>`
- Same antenna + distance + PA mode? `<yes/no>`
- Same `GAP` policy for LEN > 256? `<yes/no>`
- Same firmware on both ends as the reference run? `<yes/no — name the delta>`

## 10. Sign-off

| Role | Who | Verdict |
|---|---|---|
| Run author | `<name>` | `<complete / incomplete>` |
| Cross-family reviewer | `<reviewer_model:>` | `<APPROVED \| REQUEST-CHANGES>` |
| Manager | `<name>` | `<accepted / returned>` |
