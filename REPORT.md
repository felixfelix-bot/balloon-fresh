# REPORT — balloon-fresh full test-suite triage

Branch: `fix/test-suite-triage` (worktree `/home/c03rad0r/worktrees/bf-tests`)
Base: `github/main` @ `1351ed2`
Date: 2026-10-07

`PROGRESS.md` and `REPORT.md` are gitignored (`.gitignore:67/68`); both are
force-added (`git add -f`) on this branch only and are noted in the commit
message. Nothing was pushed to main/master.

---

## 1. Suite before / after

| | command | result |
|---|---|---|
| Before (task brief) | `python3 -m pytest tests/ -q --continue-on-collection-errors` | `4 failed, 481 passed, 23 skipped, 25 warnings, 16 errors in 191.71s` |
| Before (re-measured on `1351ed2`) | same | `4 failed, 481 passed, 23 skipped, 25 warnings, 16 errors in 190.43s` |
| **After** | same | **`550 passed, 37 skipped in 158.51s`** (re-run: `550 passed, 37 skipped in 169.85s`) — **0 failed, 0 errors, exit 0** |
| After (with reasons) | `python3 -m pytest tests/ -q --continue-on-collection-errors -rs` | identical counts; all 37 skips print a reason |

Collection: `518 items / 6 errors` → **`587 items / no errors`**.

Deltas: `+69 passed` (62 recovered modules + 7 new/regression tests), `16 errors → 0`,
`4 failed → 0`, `23 → 37 skipped` (+14 newly-clean skips: 6 rp2040-speed + 5 board-lock
+ 3 coincurve; the pre-existing 23 skips are unchanged and all carry reasons).

---

## 2. The three real hardware-independent failures

Assertion output taken from the first complete run, then re-verified locally.

### BUG 1 — `tests/src/test_phase1_runner.py::TestParsing::test_result_garbage`
**Real production defect**, fixed in `tests/phase1_test_runner.py::parse_result_line`.

* Observed: `parse_result_line("RESULT,garbage")` → `{'received': None}` (expected `None`).
* Actual cause: the positional branch zipped the key list against whatever tokens
  were present and stored the result of `_to_int`/`_to_float` unconditionally, so
  **any** unparseable token became `None` and the line was accepted as a footer.
  `_collect()` then treats that as a parsed RESULT, so a nonsense line that merely
  *contains* "RESULT" was reported as a result record.
* Fix side: **production code**. Positional footers are now rejected unless every
  field is numeric (validated with `_to_float`, independent of the int/float
  coercion), and the `key=value` branch keeps only numeric fields (`None` if none).
* Proof (old vs new, same inputs):

```
OLD RESULT,garbage      -> {'received': None}          NEW -> None
OLD RESULT,status=ok    -> {'status': None}            NEW -> None
OLD RESULT,500,garbage  -> {'received': 500, 'unique': None}  NEW -> None
OLD valid 9-field footer-> {'received': 500, 'unique': 498, ...} NEW -> identical dict
```
  The valid-footer dict is byte-identical before/after — no behaviour change for
  well-formed input.

### BUG 2 — `tests/src/test_phase1_runner.py::TestOrchestration::test_dual_rx_mode_1F_merges_packets`
**The test fixture was wrong; the production merge code is correct.** Fixed in the
test (`_runner_with_mocks`).

* Observed: `assert res.stats.packets_received == 1000` → got `500`; `duplicates == 0`.
  The dumped `raw_log` contained **only** `[RP2040-A]` lines — zero from `ESP32-C`.
* Actual cause: the fixture installed the RX emitter only on `RP2040-A` and gave
  `ESP32-B`/`ESP32-C` `on_write=lambda _t: []`. Mode 1F's RX nodes are
  `['RP2040-A', 'ESP32-C']`, so the second receiver emitted **nothing**. The
  fixture contradicted its own docstring ("Both RX nodes emit the same script").
* Is the code right? Yes — `Phase1Runner.run_mode` iterates `mode.rx_nodes`,
  concatenates each node's parsed packets into `all_packets` and computes the stats
  over the union, i.e. two receivers *do* sum (physically correct: one transmission
  heard by two receivers → 1000 received, 500 unique seqs, 500 cross-receiver
  duplicates). Verified empirically after the fixture fix: 1000/500/500/0.0 %.
* Fix side: **test fixture** (all three mock nodes now get the shared emitter,
  mirroring `phase1_test_runner.make_mock_nodes`). **No production change** — I did
  not touch the aggregation logic, because it was already correct.
* Consequence of the fixture bug: the dual-RX merge had never been exercised, and
  modes whose RX node is an ESP32 (1D/1E) silently collected zero packets.

### BUG 3 — `tests/src/test_phase1_runner.py::TestOrchestration::test_csv_footer_has_stats`
**Stale test assertion.** Fixed in the test.

* Observed: `assert 'pkt,seq,rssi' in 'index,seq,rssi,snr,irq_us,read_us,clear_us,rx_us,total_us'`.
* Actual cause: the assertion expected the **firmware per-packet dialect header**
  (`pkt,seq,...`, the string `parse_packet_line` consumes and explicitly rejects) in
  the **runner's own output CSV**, whose header is the exported
  `runner.CSV_FIELDS` → `index,seq,rssi,...`. The runner's first column is
  `index` (receiver-side arrival index) and is deliberately distinct from `seq`
  (transmitter sequence number). No consumer in the repo reads this CSV by a
  `pkt` column name (`tests/run_interop_v2.py` parses raw text, not the runner CSV).
* Fix side: **test assertion**, and it was *strengthened*, not weakened: exact
  equality with `",".join(CSV_FIELDS)`, plus the footer is now parsed and checked
  numerically (`packets_received`, `unique_seqs`, `packet_loss_pct ≈ 0.0`,
  `rssi_avg ≈ -73.0`) instead of the old `any("0.00" in ln)` substring check — which
  only passed by accident, because `100.00` also contains `"0.00"`.

### 4th failure — `tests/test_board_lock.py::TestBoardLockIntegration::test_manual_lock_pattern`
Hardware-gated (classified here, details in §4). It acquired a *device* lock
before checking whether a device exists; with no board attached the lock script
blocked behind another track's live advisory lock
(`BLOCKED: tx held by track=tollgate sentinel=…`, from a running
`~/worktrees/bf-f33land` process) and the test then hard-`fail`ed. Now skips with a
stated reason before touching the lock.

---

## 3. Disposition table — every previously failing / erroring item

| # | Item | Before | Root cause | Disposition |
|---|---|---|---|---|
| 1 | `tests/src/test_phase1_runner.py::TestParsing::test_result_garbage` | FAILED | parser accepted garbage, invented `{'received': None}` | **FIXED (production code)** + regression test |
| 2 | `…::TestOrchestration::test_dual_rx_mode_1F_merges_packets` | FAILED (500 ≠ 1000) | test fixture wired only one RX emitter; merge code correct | **FIXED (test fixture)** + regression test |
| 3 | `…::TestOrchestration::test_csv_footer_has_stats` | FAILED | stale assertion used the firmware header for the runner CSV | **FIXED (test assertion, strengthened)** + regression test |
| 4 | `tests/test_board_lock.py::TestBoardLockIntegration::test_manual_lock_pattern` | FAILED | hardware-gated; locked before presence check | **SKIPPED-FOR-HARDWARE** |
| 5 | `tests/lora_rpi_test.py` | ERROR (collection) | standalone lab script; opens `/dev/ttyACM2` at import (no test functions) | **EXCLUDED FROM COLLECTION** (not a test) |
| 6-11 | `tests/src/test_rp2040_speed.py::TestHardwareSpeed` (6 tests) | ERROR ×6 | `--tx-port`/`--rx-port` never registered with pytest → `ValueError` in the `hardware` fixture | **FIXED harness** (options registered) → **SKIPPED-FOR-HARDWARE** (`RP2040 did not send READY`) |
| 12-15 | `tests/test_board_lock.py` fixture users (`locked_tx`, `locked_rx`, `locked_both`, `locked_esp32_tx`) | ERROR ×4 | fixtures live in `board_lock_fixtures.py`, which pytest never loads | **FIXED harness** (fixtures imported; presence checked before locking) → **SKIPPED-FOR-HARDWARE** |
| 16 | `tests/throughput-matrix/uart_id_test.py` | ERROR (collection) | lab script runs `openocd` at import (missing binary) | **EXCLUDED FROM COLLECTION** (not a test) |
| 17 | `tests/throughput-matrix/uart_rx_test.py` | ERROR (collection) | same | **EXCLUDED FROM COLLECTION** (not a test) |
| 18 | `tests/test_ground_station.py` | ERROR (collection) | `from conftest import load_ground_station` — loader dropped in `c6265ba` | **FIXED** (loader restored) → 20 tests pass |
| 19 | `tests/test_link_budget.py` | ERROR (collection) | `load_link_budget` missing from conftest | **FIXED** (loader restored) → 29 tests pass |
| 20 | `tests/test_telemetry_to_nostr.py` | ERROR (collection) | `load_telemetry_to_nostr` missing from conftest | **FIXED** (loader restored) → 11 tests pass; **3 SKIPPED-FOR-DEPENDENCY** (`coincurve` absent) |

Nothing was left as a silenced pass, `xfail`ed, or deleted. Every skip prints a
reason.

### Skip inventory after the change (37, all with reasons)

| Reason | Count |
|---|---|
| `KiCad python module unusable on this host (import crashed, exit -11 (SIGSEGV))` — `tests/test_pcb_track_import.py` (pre-existing subprocess probe) | 13 |
| `TX board not found` / `Board with serial … not found` — `tests/test_hardware.py` (pre-existing conftest fixture skips) | 9 |
| `… board not attached — hardware lock test skipped` — `tests/test_board_lock.py` | 6 |
| `RP2040 did not send READY — check firmware` — `tests/src/test_rp2040_speed.py` | 6 |
| `coincurve (libsecp256k1) not installed — Schnorr signing / pubkey derivation unavailable` — `tests/test_telemetry_to_nostr.py` | 3 |

---

## 4. Harness fixes (no assertion weakened)

1. **`tests/conftest.py` — `pytest_addoption` for `--tx-port` / `--rx-port`.**
   `tests/src/test_rp2040_speed.py` documents these flags and its `hardware`
   fixture calls `request.config.getoption("--tx-port")`, but the options only
   existed in that file's `__main__` argparse block. Unregistered →
   `ValueError: no option named '--tx-port'` inside the fixture → 6 setup ERRORS.
   Options must be registered from a conftest; the fixture's own `pytest.skip`
   paths then work (`Need 2 serial ports…` / `Hardware connection failed` /
   `RP2040 did not send READY`).

2. **`tests/conftest.py` — restored the three module loaders.**
   `_load_module`, `load_link_budget`, `load_telemetry_to_nostr`,
   `load_ground_station` were added with the test modules in `e19e773` and dropped
   when `c6265ba` rewrote the file for the flash fixtures. Those modules test
   shipped tools that live outside `tests/` and are not importable packages, so
   the loaders are the only way to reach them. **The pre-existing
   `collect_ignore = ["p1b_ab_test.py"]` line was not touched** (verified:
   `git diff tests/conftest.py` shows only additions after it).

3. **`tests/test_board_lock.py` — import the lock fixtures.**
   `board_lock_fixtures.py` is neither a conftest nor declared via
   `pytest_plugins`, so pytest never loaded it and every test requesting a
   `locked_*` fixture errored with `fixture 'locked_tx' not found`. Imported
   `board_lock` + the four `locked_*` fixtures into the module.

4. **`tests/board_lock_fixtures.py` — physical precondition before locking.**
   A lock on an absent board is meaningless, and `tools/board-lock.py acquire`
   otherwise waits out its full timeout behind another track's live advisory
   lock (observed: a running `bf-f33land` sentinel holding `tx`). `locked_tx`,
   `locked_rx`, `locked_both`, `locked_esp32_tx` now resolve the port first and
   `pytest.skip` when it is not attached; `find_port_by_serial` returns
   immediately when no `/dev/ttyACM*` node exists at all instead of spinning for
   its full timeout. The lock is still acquired and released on the happy path,
   so the tests still exercise the mechanism when a board is present.

5. **`pytest.ini` — `python_files = test_*.py`.**
   Excludes the standalone `*_test.py` lab scripts (see below). Also registered
   the `simulate` marker used by `tests/src/test_phase1_runner.py` (removes 28
   `PytestUnknownMarkWarning`s and makes the module's documented `-m simulate`
   work).

### Hyphenated directory — the diagnosis in the brief was wrong; here is what was

The brief attributed the two `tests/throughput-matrix/*` errors to the hyphen
("cannot be imported as a package"). It is not the hyphen. The traceback shows
the module imported fine and then failed *executing its body*:

```
tests/throughput-matrix/uart_id_test.py:6: in <module>
    proc = subprocess.Popen([openocd, '-f', 'interface/cmsis-dap.cfg', ...])
E   FileNotFoundError: … /openocd-esp32/bin/openocd
```

With pytest's default import mode (`prepend`, no `__init__.py`) those modules are
imported by basename, so a hyphen in the parent directory is irrelevant. The
defect is import-time side effects — the same class as `p1b_ab_test.py`
(`sys.exit(1)` at import), which was fixed with `collect_ignore`.

**Chosen fix: narrow `python_files` to `test_*.py` in `pytest.ini`** rather than
renaming the directory or extending the protected `collect_ignore` line. Why:

* Renaming to `throughput_matrix` would **not** fix the errors — the openocd
  `FileNotFoundError` would remain (and would still be a landmine). Rejected.
* These files are `*_test.py` lab scripts with **zero test functions**, owned by
  the `balloon-e80bench` bench
  (`docs/coordination/E80-NEXT-STEPS-SCHEDULE.md:197,235`), so they should never
  be pytest-collected.
* One line covers the whole directory *and* `tests/lora_rpi_test.py` (same
  defect: `SerialException` opening `/dev/ttyACM2` at import), **without editing
  the just-landed `collect_ignore` line** that I was told not to touch.
* Verified safe: exactly 4 files in the repo match `*_test.py`
  (`p1b_ab_test.py` — already ignored, `lora_rpi_test.py`, and the two
  `throughput-matrix` scripts); **no legitimately-collected test module uses that
  pattern**, so nothing real is hidden. `tests/` collection went from
  `518 + 6 errors` to **587 items, 0 errors**.

Caveat: passing one of those paths *explicitly* (`pytest tests/lora_rpi_test.py`)
still collects it — pytest ignores `python_files` for explicitly named files.
That is the intended use of a standalone script; documented here.

---

## 5. Regression tests added (deliverable 5)

New class `TestRegressions` in `tests/src/test_phase1_runner.py` (extends the
existing spec, reusing its mock helpers via a new `_MockOrchestrationMixin`):

| Test | Locks in | Fails against pre-triage code? |
|---|---|---|
| `test_result_line_never_invents_a_record_from_garbage` | BUG 1: 5 garbage forms rejected; valid positional + key=value footers still parse with unchanged types | **Yes** — pre-fix returned `{'received': None}` / `{'status': None}` |
| `test_dual_rx_merge_sums_both_receivers` | BUG 2: mode 1F = 1000 received / 500 unique / 500 duplicates / 0 % loss, and **per-receiver counts are individually visible in `raw_log`** so a silent RX node can never hide behind the aggregate | **Yes** — with only one RX emitter wired it yields 500 and an empty second receiver |
| `test_single_rx_mode_is_not_double_counted` | guard for BUG 2's fix: single-RX mode stays at 500/500/0 and only one receiver appears in `raw_log` | (new guard, prevents over-correction) |
| `test_csv_header_and_footer_are_the_runner_schema` | BUG 3: exact header `",".join(CSV_FIELDS)`, footer values equal the computed stats, one data row per packet | **Yes** — pre-triage asserted the firmware header |

The pre-existing `test_result_garbage`, `test_dual_rx_mode_1F_merges_packets` and
`test_csv_footer_has_stats` were kept and are now green (their assertions were
correct; BUG 3's header check is the one that was repaired).

---

## 6. Deferred / known-not-green

* **Nothing was deferred as unfixable.** Every previously failing or erroring item
  is fixed, excluded (with the standalone-script justification above), or skipping
  for a stated hardware/dependency reason.
* `coincurve` (libsecp256k1) is **not installed on this host and not installed in
  CI** (`.github/workflows/test.yml` installs only `pytest` and `pyserial`), so
  `sign_event` / `derive_pubkey` cannot be exercised. The three tests carry an
  explicit `pytest.mark.skipif` with the reason and would run unmodified if
  `coincurve` were installed — a real environment gap, not a code defect.
* The 13 KiCad skips are the pre-existing subprocess probe from the just-landed
  `1351ed2` fix (`_pcbnew.so` is ABI-incompatible → SIGSEGV); untouched by design.

---

## 7. How to verify

```bash
cd /home/c03rad0r/worktrees/bf-tests
python3 -m pytest tests/ -q --continue-on-collection-errors          # 550 passed, 37 skipped
python3 -m pytest tests/ -q --continue-on-collection-errors -rs       # same, with reasons
python3 -m pytest tests/src/test_phase1_runner.py -q                  # 28 passed (was 21p/3f)
python3 -m pytest tests/test_ground_station.py tests/test_link_budget.py \
                   tests/test_telemetry_to_nostr.py -q                # 62 passed, 3 skipped
git ls-remote --heads github fix/test-suite-triage                    # GitHub tip
git ls-remote --heads ngit   fix/test-suite-triage                    # ngit tip
```

Files changed (7, all under `tests/` + `pytest.ini`):
`pytest.ini`, `tests/conftest.py`, `tests/phase1_test_runner.py`,
`tests/src/test_phase1_runner.py`, `tests/board_lock_fixtures.py`,
`tests/test_board_lock.py`, `tests/test_telemetry_to_nostr.py`
(plus force-added `PROGRESS.md`, `REPORT.md`).
`tests/test_pcb_track_import.py` and the `collect_ignore` line are untouched.
