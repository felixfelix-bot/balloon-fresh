# Range-split acceptance suite — reconciliation record (2026-10-09)

**Card:** e80-bench `t_45438008` (E80-TR: reconcile 92cf11f acceptance-test suite onto current main)
**Verified base:** `origin/main` @ `ce491f93eda8bf39f97a075afb8a84b765abe1fe`
**Verdict:** the suite is **already on main and green (34/34 PASS, 0 skipped)**. The
"23-test RED acceptance suite @ 92cf11f" that this card asks to re-apply is
**unrecoverable**, and the RED premise it rests on is **falsified** by measurement.
No host-code fix, no skip conversion, and no tests-only port are therefore possible
or needed.

This document is the *explicit per-test disposition list* the card asks for as its
alternative deliverable, and it is the durable, pushed home for the reconciliation
conclusions that previously lived only on unpublished local branches
(see `wt/range-split-triage`, `wt/cvm-p1-tx-listener` — both now gone; flagged as the
MAJOR finding by the Gate 2.5 reviewer, t_ce8c6b36).

---

## 1. What was asked

> Re-apply the 23-test RED acceptance suite quarantined at `~/worktrees/range-check2-own`
> (branch `worker-balloon/range-check2-wip` @ `92cf11f`, tests live in
> `firmware/e80-stm32-bench/tools/test_e80_range_split.py`) onto current main as
> tests-only commits. Run them. Triage every failure.
> Deliverable: suite green or explicit per-test disposition list.

Three independent premises in that sentence were checked and all three fail:

| Premise | Measured reality |
|---|---|
| `~/worktrees/range-check2-own` exists | **no** — path absent (`git -C` → *cannot change to … No such file or directory*) |
| branch `worker-balloon/range-check2-wip` exists | **no** — remote has only `worker-balloon/range-check`, `worker-balloon/range-check2`, `worker-balloon/range-preflight` |
| commit `92cf11f` exists | **no** — `git cat-file -t 92cf11f` → *Not a valid object name* in all three clones (`~/repos/balloon-e80bench`, `~/repos/e80-bench`, `~/repos/balloon`) |
| the suite is RED against main | **no** — 34 collected / 34 PASSED / 0 skipped (section 3) |

## 2. Finding A — the port source is unrecoverable

Evidence (all commands re-run 2026-10-09 by this card):

1. `92cf11f` is absent from **every** local clone's object store
   (`git cat-file -t 92cf11f` → *Not a valid object name*).
2. No ref anywhere carries the port: `git ls-remote origin` lists 216 heads; no
   `*range-check2-wip*`; `git for-each-ref | grep range-check2-wip` → empty across
   every repo under `~/repos/`.
3. Exhaustive object scan — not just reachable refs. Every blob in
   `~/repos/balloon-e80bench` (reachable **and** unreachable, via
   `git cat-file --batch-all-objects`) whose header matches *"Host tests for
   e80_bench_ctl"* was counted for `def test_` lines. The **minimum ever seen is 33**
   tests; a 23-test revision **has never existed in this object store**.
4. `~/worktrees/range-check2-own` is gone; the only `*range*` worktree left is
   `t_f29ece94-rangetests`, which is a different repository (no
   `firmware/e80-stm32-bench` tree).
5. On `origin/main` the file is **byte-identical to the tip of the merged
   `worker-balloon/range-check2` branch** (`613e8c0f`, blob
   `7b9a16f0b75bbcdf55ab36908f43c04997c86be1`; `git diff 613e8c0f origin/main -- <file>`
   is empty). `613e8c0f` *is* an ancestor of `origin/main` — the lineage was
   consolidated ("superset of both range-check lineages", merge `391e3de1`), so the
   suite the quarantine worktree was built from is already landed in its current form.

The same conclusion was reached independently by the Gate 2.5 reviewer on 2026-10-01
(`t_ce8c6b36` → REQUEST_CHANGES, "blocker: Port source unrecoverable";
full review: `~/reports/reviews/e80-bench-t_aabd1170-kimi.md`).

**Consequence:** `t_aabd1170` ("Port 92cf11f range-split acceptance suite onto main and
capture RED baseline") is unexecutable as written. It must be cancelled or re-scoped to
authoring a *new* suite; re-publishing a byte-identical copy of a file that is already on
main has no value.

## 3. Finding B — the RED premise is falsified by measurement

The 23-test RED baseline cannot be reproduced because the suite on current main is
fully green:

```bash
cd firmware/e80-stm32-bench
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest tools/test_e80_range_split.py -v -p no:cacheprovider
# → collected 34 items — 34 passed in 0.08s   (0 failed, 0 errored, 0 skipped)
```

Full gate set at `ce491f93` (see section 8 for the exact commands):

| Gate | Result |
|---|---|
| `pytest tools/test_e80_range_split.py -v` | **34 passed** |
| `pytest tools/test_range_check.py -q` | **104 passed** |
| `make range-test-host` (Makefile:657 — both suites) | **138 passed**, exit 0 |
| `make -n range-dry-run DIST=50m` (repo root) | exit 0 |

This matches the reviewer's independent run at `dfda57a1` (34 passed / 0 failed /
0 skipped). The card's assumption that the four landings named below broke the suite
does not hold.

## 4. Per-test disposition — all 34 tests

All 34 tests were executed at `ce491f93eda8bf39f97a075afb8a84b765abe1fe` with the command in section 3. Disposition is
`PASS` for every test; there is no failure, no error, no skip, and therefore nothing to
triage, fix, or skip-convert.

| # | Test class | Test | Disposition |
|---|---|---|---|
| 1 | `TestLoadConfigPreset` | `test_config_has_airtime` | **PASSED** |
| 2 | `TestLoadConfigPreset` | `test_config_has_expected_s` | **PASSED** |
| 3 | `TestLoadConfigPreset` | `test_config_has_label_and_idx` | **PASSED** |
| 4 | `TestLoadConfigPreset` | `test_empty_configs` | **PASSED** |
| 5 | `TestLoadConfigPreset` | `test_flrc_missing_br` | **PASSED** |
| 6 | `TestLoadConfigPreset` | `test_invalid_mod` | **PASSED** |
| 7 | `TestLoadConfigPreset` | `test_load_from_dict` | **PASSED** |
| 8 | `TestLoadConfigPreset` | `test_load_from_file` | **PASSED** |
| 9 | `TestLoadConfigPreset` | `test_lora_missing_sf` | **PASSED** |
| 10 | `TestLoadConfigPreset` | `test_missing_configs_key` | **PASSED** |
| 11 | `TestBuildPresetSchedule` | `test_first_start_after_t0_margin` | **PASSED** |
| 12 | `TestBuildPresetSchedule` | `test_gap_between_configs` | **PASSED** |
| 13 | `TestBuildPresetSchedule` | `test_schedule_independent_of_call_order` | **PASSED** |
| 14 | `TestBuildPresetSchedule` | `test_schedule_returns_list_of_floats` | **PASSED** |
| 15 | `TestBuildPresetSchedule` | `test_starts_are_monotonically_increasing` | **PASSED** |
| 16 | `TestParsePktLine` | `test_flrc_pkt` | **PASSED** |
| 17 | `TestParsePktLine` | `test_non_pkt_line` | **PASSED** |
| 18 | `TestParsePktLine` | `test_short_pkt` | **PASSED** |
| 19 | `TestParsePktLine` | `test_valid_pkt` | **PASSED** |
| 20 | `TestTxLogWriter` | `test_config_row` | **PASSED** |
| 21 | `TestTxLogWriter` | `test_header_written` | **PASSED** |
| 22 | `TestTxLogWriter` | `test_incremental_write` | **PASSED** |
| 23 | `TestRxLogWriter` | `test_header_written` | **PASSED** |
| 24 | `TestRxLogWriter` | `test_multiple_pkts` | **PASSED** |
| 25 | `TestRxLogWriter` | `test_pkt_row` | **PASSED** |
| 26 | `TestMergeCsvs` | `test_all_lost_per_100` | **PASSED** |
| 27 | `TestMergeCsvs` | `test_all_received_per_zero` | **PASSED** |
| 28 | `TestMergeCsvs` | `test_csv_output` | **PASSED** |
| 29 | `TestMergeCsvs` | `test_foreign_packets_flagged` | **PASSED** |
| 30 | `TestMergeCsvs` | `test_half_lost` | **PASSED** |
| 31 | `TestMergeCsvs` | `test_multiple_configs` | **PASSED** |
| 32 | `TestMergeCsvs` | `test_per_stats_in_report` | **PASSED** |
| 33 | `TestDryRunPreset` | `test_dry_run_no_file` | **PASSED** |
| 34 | `TestDryRunPreset` | `test_dry_run_preset` | **PASSED** |

**Summary: 34 collected / 34 PASS / 0 FAIL / 0 ERROR / 0 SKIP.**

## 5. Skip audit

The only skip construct in the whole suite is the pre-existing

```python
@unittest.skipUnless(HAVE_MERGE, "merge_csvs.py not yet implemented")
class TestMergeCsvs(unittest.TestCase):     # tools/test_e80_range_split.py:372
```

which landed with the suite itself (`184d18e2`, 2026-08-23). `HAVE_MERGE` is `True`
(`merge_csvs.py` is present at `origin/main`), so the guard is **inert and no skip is
reported in the run above** — the 7 `TestMergeCsvs` tests all execute. No skip added by
this card, and no skip anywhere is masking a regression.

No `xfail`/`skip` markers were introduced at any point (there is no reconciliation diff
to carry them; see Finding A).

## 6. Coverage map — the four landings named by the card are real and covered

All four semantics that "landed after the suite was written" are implemented in
`origin/main` and covered by `tools/test_range_check.py` (104 tests):

- **T0-anchor (all cycles anchored to a shared T0, drift-free)**
  - `TestCycleAnchoring::test_all_cycles_anchor_to_shared_t0 (L537)`
- **late-join (late launch detected, no silent re-anchoring)**
  - `TestCycleAnchoring::test_late_launch_detected_against_true_schedule (L522)`
  - `TestMakefileLogNaming::test_range_rx_late_join_flag (L825)`
- **conditional warmup (first 2 replicates excluded only when >2 distinct replicates)**
  - `TestVerdicts::test_warmup_only_is_gaps_not_logging_gap (L195)`
  - `TestLoop1WarmupRegression::test_multi_cycle_warmups_still_excluded_best_pass (L339)`
  - `TestAnalyzeCapture::test_warmup_replicates_excluded_when_requested (L581)`
- **best-pass merge (best single surviving replicate, never pooled)**
  - `TestVerdicts::test_multi_replicate_counts_best_pass (L248)`
  - `TestLoop1WarmupRegression::test_multi_cycle_warmups_still_excluded_best_pass (L339)`
  - `TestAnalyzeCapture::test_best_pass_across_replicates (L572)`
  - `TestMergeBestPass::test_best_pass_not_union (L691)`

Because this coverage already exists on main, duplicating it inside
`test_e80_range_split.py` would add no protection — a further reason not to re-author the
"quarantined" suite just to have re-applied something.

## 7. Disposition and decisions

1. **No tests-only port commit.** Source irrecoverable (Finding A); the file at the
   card's target path is already the consolidated version of that lineage.
2. **No host-code fix.** Zero failures to fix (Finding B).
3. **No skip conversions.** One pre-existing inert skip; nothing needs re-scoping
   (section 5).
4. **Deliverable satisfied** as the card's own alternative: the suite is green, and this
   document is the explicit per-test disposition list (section 4) plus the per-premise
   disposition (section 1).
5. **Board hygiene:** cancel/close `t_aabd1170` (unexecutable as written) instead of
   letting it dispatch a worker against a missing object; treat the "23-test RED suite"
   as a **falsified premise**, not as pending debt. If lost coverage is ever suspected,
   author a *new* suite against current semantics rather than trying to resurrect
   `92cf11f`.

### Remaining known debt (recorded here, deliberately not fixed by this card)

This is a documentation-only change; no host or test code was touched. Two items of
real, pre-existing host-test debt are recorded so they are not lost:

1. **Duplicated band-override window constants.** The acceptance window
   `410 MHz … 2483.5 MHz` lives in three places: firmware `src/main.h:78-79`
   (`E80_BENCH_OVERRIDE_MIN_HZ/MAX_HZ`), host `tools/e80_bench_ctl.py:112-113`
   (`OVERRIDE_MIN_HZ/OVERRIDE_MAX_HZ`), and as **hardcoded literals** in the `FakeBoard`
   stand-in (`tools/test_e80_bench_ctl.py:118`, and the comment at `:477-480` that says
   "matching `E80_BENCH_OVERRIDE_*_HZ`" while not importing them). A drift guard that
   monkeypatches `ctl.OVERRIDE_MIN_HZ` and asserts `FakeBoard` tracks it would be genuinely
   RED today. Deferred: this card's deliverable is the reconciliation record, and a
   code-tier card is currently blocked fleet-wide by `no_live_drift`
   (`~/.hermes/bot/repo_drift_state.json` is non-empty: 13 drifted
   `hermes-orchestration` systemd paths as of 2026-10-08T22:42:53Z).
2. **No drift guard on this disposition table.** If tests are added to or renamed in
   `tools/test_e80_range_split.py`, section 4 above goes stale silently. A tiny pytest
   module under `tools/` (wired into `Makefile:659`, which enumerates its pytest files
   explicitly) would keep it honest — same deferral reason as (1).


## 8. Reproduction

```bash
cd firmware/e80-stm32-bench
python3 -m pytest tools/test_range_check.py -v          # 104 passed
make range-test-host                                    # 138 passed (both suites)
cd "$(git rev-parse --show-toplevel)" && make -n range-dry-run DIST=50m   # exit 0

# unrecoverability proof
git cat-file -t 92cf11f                                 # fatal: Not a valid object name
git ls-remote origin | grep -i 'range-check2-wip'        # (empty)
git log --all --oneline -- firmware/e80-stm32-bench/tools/test_e80_range_split.py
#   → 2d73fbf3 (2026-08-25) and earlier; the file has NEVER carried 23 tests
```

## 9. References

- Gate 2.5 cross-family review (kimi-k3 / moonshot) of the original chain:
  `~/reports/reviews/e80-bench-t_aabd1170-kimi.md`, board card `t_ce8c6b36`.
- Operator guide: `firmware/e80-stm32-bench/docs/RANGE-TEST-GUIDE.md`.
- Design: `docs/DESIGN-distributed-range-test.md`, `docs/ADR-range-sync-cvm.md`.
