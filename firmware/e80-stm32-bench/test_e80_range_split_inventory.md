# E80 range-split suite — RED-failure inventory

Inventory card: **t_bd09660b**. Status: **no RED failures observed — the suite is GREEN.**

## 1. Resolved suite path

Searched, in the card's order:

| candidate | exists? |
|---|---|
| `tools/test_e80_range_split.py` (relative to `firmware/e80-stm32-bench`) | **YES — this is the suite** |
| `tools/tests/test_e80_range_split.py` | no |
| `tests/test_e80_range_split.py` | no |

`find . -name 'test_e80_range_split*.py' -not -path './.git/*'` (from the repo root
`balloon-e80bench/`) returns exactly one file:

```
./firmware/e80-stm32-bench/tools/test_e80_range_split.py
```

* **Suite path, repo-root relative:** `firmware/e80-stm32-bench/tools/test_e80_range_split.py`
* **Suite path, from `firmware/e80-stm32-bench`:** `tools/test_e80_range_split.py`
* **Suite blob:** `7b9a16f0b75bbcdf55ab36908f43c04997c86be1` (md5 `5a7c057c1641066a0af15fb791afeaaf`) — byte-identical on the local `main` lineage (`94d8e85a`) and on `origin/main` (`ce491f93`).

## 2. Exact reproduce command

```bash
cd firmware/e80-stm32-bench && python3 -m pytest tools/test_e80_range_split.py -v -p no:cacheprovider
```

(`-p no:cacheprovider` is not required here; the rootdir `pytest.ini` is used with no cache error. Plain
`python3 -m pytest tools/test_e80_range_split.py -v` gives the same result. Interpreter: Python 3.13.7, pytest 9.1.1.)

Full stdout/stderr captured to `/tmp/e80_range_split_pytest.log`.

## 3. Observed failure count

```
34 collected / 34 passed / 0 failed / 0 errors / 0 skipped   (exit 0)
```

> **PREMISE MISMATCH — read carefully.** The card premise states **23 RED failures**. The observed
> number of failing tests is **0**. Nothing was forced or padded to 23; the whole suite is green.
> Two independent checkouts were tested and both are green (`origin/main ce491f93` in a fresh worktree,
> and the local `main` working tree `94d8e85a`), running the *same* suite blob `7b9a16f0`.

## 4. Failing tests and buckets

Table columns as specified (node id | assertion file:line | host file:line | bucket A/B).
**There are no failing tests, so the table has zero rows** — no failure existed to carry an
assertion site or a bucket:

| test node id | assertion file:line | host file:line | bucket (A/B) |
|---|---|---|---|
| _(none — 0 failing tests observed)_ | — | — | — |

**Bucket balance:** bucket A = 0 tests, bucket B = 0 tests — **both buckets are empty**; nothing
could be classified because there is no RED failure to classify. (Reported as observed; no artificial
rebalancing.)

## 5. Evidence / cross-checks

| command | result |
|---|---|
| `python3 -m pytest tools/test_e80_range_split.py -v -p no:cacheprovider` (origin/main worktree) | **34 passed / 0 failed / exit 0** |
| same command in `~/repos/balloon-e80bench` (local `main` `94d8e85a`) | 34 passed / exit 0 |
| `python3 -m pytest tools/test_range_check.py tools/test_range_preflight.py tools/test_range_test_guide.py -q` (origin/main) | 187 passed / exit 0 |
| `python3 -m pytest tools/ -q` (local main, whole tools dir) | 582 passed, 1 skipped, 1 collection error (see below) |

The single collection **error** in the whole-`tools/` run is `tools/cvm_relay_test.py::test_one_relay`
(`fixture 'url' not found`) — an unrelated manual-script-as-test, not part of the range-split suite and
not a test failure.

## 6. Why "23" cannot be reproduced

* **No 23-test revision ever existed in this repo.** Every revision of
  `tools/test_e80_range_split.py` reachable from any ref (`git log --all`) contains **34** `def test_`
  definitions — the minimum across all history is 34, never 23.
* The preceding triage card `t_bd618872` already established the same result and traced the missing
  input: its source card `t_aabd1170` was never dispatched, and the claimed port commit `92cf11f` is
  absent from every local clone and from `origin` (archived tip `4e7c3498` carries the same 34-test blob
  `7b9a16f0` as `main`).
* Conclusion: `test_e80_range_split.py` is **green**, not RED. There is nothing to bucket.

## 7. Advisory appendix — where the A/B semantics actually live (all GREEN)

Not a failure inventory; recorded so the two downstream classification tasks have the map they were
meant to consume. Every test below **passes**; the rows show which host site a failure *would* have
exercised.

| `tools/test_e80_range_split.py::TestLoadConfigPreset::test_config_has_airtime` | n/a (test passed) | tools/e80_bench_ctl.py:1664 `load_config_preset` | B |
| `tools/test_e80_range_split.py::TestLoadConfigPreset::test_config_has_expected_s` | n/a (test passed) | tools/e80_bench_ctl.py:1664 `load_config_preset` | B |
| `tools/test_e80_range_split.py::TestLoadConfigPreset::test_config_has_label_and_idx` | n/a (test passed) | tools/e80_bench_ctl.py:1664 `load_config_preset` | B |
| `tools/test_e80_range_split.py::TestLoadConfigPreset::test_empty_configs` | n/a (test passed) | tools/e80_bench_ctl.py:1664 `load_config_preset` | B |
| `tools/test_e80_range_split.py::TestLoadConfigPreset::test_flrc_missing_br` | n/a (test passed) | tools/e80_bench_ctl.py:1664 `load_config_preset` | B |
| `tools/test_e80_range_split.py::TestLoadConfigPreset::test_invalid_mod` | n/a (test passed) | tools/e80_bench_ctl.py:1664 `load_config_preset` | B |
| `tools/test_e80_range_split.py::TestLoadConfigPreset::test_load_from_dict` | n/a (test passed) | tools/e80_bench_ctl.py:1664 `load_config_preset` | B |
| `tools/test_e80_range_split.py::TestLoadConfigPreset::test_load_from_file` | n/a (test passed) | tools/e80_bench_ctl.py:1664 `load_config_preset` | B |
| `tools/test_e80_range_split.py::TestLoadConfigPreset::test_lora_missing_sf` | n/a (test passed) | tools/e80_bench_ctl.py:1664 `load_config_preset` | B |
| `tools/test_e80_range_split.py::TestLoadConfigPreset::test_missing_configs_key` | n/a (test passed) | tools/e80_bench_ctl.py:1664 `load_config_preset` | B |
| `tools/test_e80_range_split.py::TestBuildPresetSchedule::test_first_start_after_t0_margin` | n/a (test passed) | tools/e80_bench_ctl.py:1807 `build_preset_schedule` (T0-anchored airtime schedule) | A |
| `tools/test_e80_range_split.py::TestBuildPresetSchedule::test_gap_between_configs` | n/a (test passed) | tools/e80_bench_ctl.py:1807 `build_preset_schedule` (T0-anchored airtime schedule) | A |
| `tools/test_e80_range_split.py::TestBuildPresetSchedule::test_schedule_independent_of_call_order` | n/a (test passed) | tools/e80_bench_ctl.py:1807 `build_preset_schedule` (T0-anchored airtime schedule) | A |
| `tools/test_e80_range_split.py::TestBuildPresetSchedule::test_schedule_returns_list_of_floats` | n/a (test passed) | tools/e80_bench_ctl.py:1807 `build_preset_schedule` (T0-anchored airtime schedule) | A |
| `tools/test_e80_range_split.py::TestBuildPresetSchedule::test_starts_are_monotonically_increasing` | n/a (test passed) | tools/e80_bench_ctl.py:1807 `build_preset_schedule` (T0-anchored airtime schedule) | A |
| `tools/test_e80_range_split.py::TestParsePktLine::test_flrc_pkt` | n/a (test passed) | tools/e80_bench_ctl.py:2027 `parse_pkt_line_legacy` | B |
| `tools/test_e80_range_split.py::TestParsePktLine::test_non_pkt_line` | n/a (test passed) | tools/e80_bench_ctl.py:2027 `parse_pkt_line_legacy` | B |
| `tools/test_e80_range_split.py::TestParsePktLine::test_short_pkt` | n/a (test passed) | tools/e80_bench_ctl.py:2027 `parse_pkt_line_legacy` | B |
| `tools/test_e80_range_split.py::TestParsePktLine::test_valid_pkt` | n/a (test passed) | tools/e80_bench_ctl.py:2027 `parse_pkt_line_legacy` | B |
| `tools/test_e80_range_split.py::TestTxLogWriter::test_config_row` | n/a (test passed) | tools/e80_bench_ctl.py:2205 `TxLogWriter` | B |
| `tools/test_e80_range_split.py::TestTxLogWriter::test_header_written` | n/a (test passed) | tools/e80_bench_ctl.py:2205 `TxLogWriter` | B |
| `tools/test_e80_range_split.py::TestTxLogWriter::test_incremental_write` | n/a (test passed) | tools/e80_bench_ctl.py:2205 `TxLogWriter` | B |
| `tools/test_e80_range_split.py::TestRxLogWriter::test_header_written` | n/a (test passed) | tools/e80_bench_ctl.py:2235 `RxLogWriter` | B |
| `tools/test_e80_range_split.py::TestRxLogWriter::test_multiple_pkts` | n/a (test passed) | tools/e80_bench_ctl.py:2235 `RxLogWriter` | B |
| `tools/test_e80_range_split.py::TestRxLogWriter::test_pkt_row` | n/a (test passed) | tools/e80_bench_ctl.py:2235 `RxLogWriter` | B |
| `tools/test_e80_range_split.py::TestMergeCsvs::test_all_lost_per_100` | n/a (test passed) | tools/merge_csvs.py:232 `merge_csvs` (+ :199 `pick_best_passes` best-pass merge) | B |
| `tools/test_e80_range_split.py::TestMergeCsvs::test_all_received_per_zero` | n/a (test passed) | tools/merge_csvs.py:232 `merge_csvs` (+ :199 `pick_best_passes` best-pass merge) | B |
| `tools/test_e80_range_split.py::TestMergeCsvs::test_csv_output` | n/a (test passed) | tools/merge_csvs.py:232 `merge_csvs` (+ :199 `pick_best_passes` best-pass merge) | B |
| `tools/test_e80_range_split.py::TestMergeCsvs::test_foreign_packets_flagged` | n/a (test passed) | tools/merge_csvs.py:232 `merge_csvs` (+ :199 `pick_best_passes` best-pass merge) | B |
| `tools/test_e80_range_split.py::TestMergeCsvs::test_half_lost` | n/a (test passed) | tools/merge_csvs.py:232 `merge_csvs` (+ :199 `pick_best_passes` best-pass merge) | B |
| `tools/test_e80_range_split.py::TestMergeCsvs::test_multiple_configs` | n/a (test passed) | tools/merge_csvs.py:232 `merge_csvs` (+ :199 `pick_best_passes` best-pass merge) | B |
| `tools/test_e80_range_split.py::TestMergeCsvs::test_per_stats_in_report` | n/a (test passed) | tools/merge_csvs.py:232 `merge_csvs` (+ :199 `pick_best_passes` best-pass merge) | B |
| `tools/test_e80_range_split.py::TestDryRunPreset::test_dry_run_no_file` | n/a (test passed) | tools/e80_bench_ctl.py:3076 `dry_run_preset` | B |
| `tools/test_e80_range_split.py::TestDryRunPreset::test_dry_run_preset` | n/a (test passed) | tools/e80_bench_ctl.py:3076 `dry_run_preset` | B |

Advisory bucket read: only `TestBuildPresetSchedule` (5 tests, the T0-anchored schedule) is
A-relevant inside this suite; the other 29 tests would fall in B. The remaining A/B semantics are
covered by the *other* range suites, all green:

| semantics | host site | green test evidence |
|---|---|---|
| T0-anchor | `tools/e80_bench_ctl.py:217 check_t0_future`, `:1807 build_preset_schedule` | `test_range_check.py`, `test_e80_range_split.py::TestBuildPresetSchedule` |
| late-join | `tools/e80_bench_ctl.py:1897 compute_late_skip`, `:1927 apply_late_skip` | `test_range_check.py` |
| conditional warmup | `tools/range_check.py:603-613` (coverage analysis, warmup-aware) | `test_range_check.py` |
| best-pass merge | `tools/merge_csvs.py:199 pick_best_passes` | `test_e80_range_split.py::TestMergeCsvs` |

## 8. Repo hygiene

No source, test, fixture, or host file was modified. `git status --porcelain` in the worktree that
produced this inventory shows exactly one line — the new inventory file:

```
?? firmware/e80-stm32-bench/test_e80_range_split_inventory.md
```
