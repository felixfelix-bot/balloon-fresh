# PROGRESS — balloon-fresh test-suite triage (branch `fix/test-suite-triage`)

Base: `github/main` @ `1351ed2`. Worktree: `/home/c03rad0r/worktrees/bf-tests`.
Scratch files `PROGRESS.md` / `REPORT.md` are gitignored, so they are added with
`git add -f` on this branch only (never to main).

## Cluster 1 — three phase1 runner failures (DONE)

Ran `pytest tests/src/test_phase1_runner.py -v` and captured the real assertion
output (the summary in the task brief was missing #3's detail).

| Test | Real failure | Root cause | Side fixed |
|---|---|---|---|
| `TestParsing::test_result_garbage` | `{'received': None}` returned for `"RESULT,garbage"` | `parse_result_line` positional branch zipped keys against whatever tokens existed and stored `None` for unparseable ones | **production code** (`tests/phase1_test_runner.py`) |
| `TestOrchestration::test_dual_rx_mode_1F_merges_packets` | `packets_received == 500`, not 1000; `raw_log` contained **only** `[RP2040-A]` lines | **test fixture**: `_runner_with_mocks` installed the RX emitter on `RP2040-A` only, giving `ESP32-C` a no-op `on_write`. The merge code (which iterates all `rx_nodes`) is correct | **test fixture** (justified in REPORT.md) |
| `TestOrchestration::test_csv_footer_has_stats` | `assert 'pkt,seq,rssi' in 'index,seq,rssi,snr,...'` | stale assertion: `pkt,seq,...` is the *firmware* dialect header; the runner's CSV header is `runner.CSV_FIELDS` → `index,seq,rssi,...` | **test assertion** (strengthened, not weakened) |

Also found and fixed while in the file: the orchestration helpers were on
`TestOrchestration`, so the new regression class could not reuse them → hoisted
into `_MockOrchestrationMixin` (not collected by pytest).

Evidence: `pytest tests/src/test_phase1_runner.py -q` → **28 passed** (was 21 passed / 3 failed).

## Cluster 2 — three "unclassified" import errors (DONE — real fix, not a skip)

All three were the same harness regression, not a missing dependency:

    E   ImportError: cannot import name 'load_link_budget' from 'conftest' (...)
    E   ImportError: cannot import name 'load_ground_station' from 'conftest' (...)
    E   ImportError: cannot import name 'load_telemetry_to_nostr' from 'conftest' (...)

`conftest.py` gained `_load_module` + the three `load_*` loaders in `e19e773`
and lost them when `c6265ba` rewrote the file for the flash fixtures. The three
test modules test the shipped tools by path (`tools/link_budget.py`,
`tracker/ground-station/ground_station.py`,
`tracker/ground-station/nostr_bridge/telemetry_to_nostr.py`) — no hardware, no
network. Restored the loaders verbatim.

Result: **62 passed, 3 skipped** (65 collected). The 3 skips need `coincurve`
(libsecp256k1) for Schnorr signing / pubkey derivation — not installed here and
not installed in CI (`.github/workflows/test.yml` installs only pytest +
pyserial), so they carry an explicit `skipif` with a stated reason.

## Cluster 3 — hardware-gated errors → clean skips (DONE)

* `tests/src/test_rp2040_speed.py::TestHardwareSpeed` (6 ERRORs): the `hardware`
  fixture called `request.config.getoption("--tx-port")`, but `--tx-port` was
  never registered with pytest (it only existed in that file's `__main__`
  argparse block) → `ValueError: no option named '--tx-port'` inside the
  fixture. Registered `--tx-port` / `--rx-port` via `pytest_addoption` in
  `tests/conftest.py`. The fixture's own `pytest.skip` paths then fire
  normally: **11 passed, 6 skipped**.
* `tests/test_board_lock.py` (4 ERRORs + 1 FAIL):
  - `locked_tx` / `locked_rx` / `locked_both` / `locked_esp32_tx` are defined in
    `tests/board_lock_fixtures.py`, which pytest never loads as a plugin →
    "fixture not found". Imported them (plus their `board_lock` dependency) into
    the test module.
  - `TestBoardLockIntegration::test_manual_lock_pattern` acquired a *device*
    lock before checking whether a device exists; with no board it blocked on
    another track's advisory lock and then hard-`fail`ed. Added the board
    presence check first → `pytest.skip`. Same reorder applied to the fixtures
    (a lock on an absent board is meaningless), plus `find_port_by_serial` now
    returns immediately when no `/dev/ttyACM*` node exists instead of burning
    its timeout.
  - Result: **2 passed, 6 skipped** (was 4 errors / 1 failed / 1 skipped / 2 passed).

## Cluster 4 — hyphenated-directory collection errors (DONE — diagnosis corrected)

`tests/throughput-matrix/uart_id_test.py` and `uart_rx_test.py` error at
**import**, with `FileNotFoundError: .../openocd-esp32/bin/openocd` — i.e. the
scripts run `subprocess.Popen([openocd, ...])` at module scope, before any test
runs. The hyphen is a red herring: with pytest's default import mode those
modules are imported by basename, not as a package (the traceback proves the
import itself succeeded — line 6 executed).

Chosen fix: **narrow `python_files` to `test_*.py`** in `pytest.ini`. These
files are `*_test.py` lab scripts with zero test functions that belong to the
`balloon-e80bench` bench (`docs/coordination/E80-NEXT-STEPS-SCHEDULE.md`), so
they should never be collected. One line covers the whole directory *and*
`tests/lora_rpi_test.py` (same defect: `SerialException` at import because it
opens `/dev/ttyACM2` at module scope), **without touching the just-landed
`collect_ignore` line in `tests/conftest.py`**. No legitimately-collected test
module in the repo matches `*_test.py` (verified: only those 4 files, one of
which — `p1b_ab_test.py` — was already ignored).

## Cluster 5 — regression locks (DONE)

New `TestRegressions` class in `tests/src/test_phase1_runner.py`:
`test_result_line_never_invents_a_record_from_garbage`,
`test_dual_rx_merge_sums_both_receivers` (+ `test_single_rx_mode_is_not_double_counted`
guard), `test_csv_header_and_footer_are_the_runner_schema`.

## Cluster 6 — full suite + report (DONE)

* `python3 -m pytest tests/ -q --continue-on-collection-errors` →
  **550 passed, 37 skipped, 0 failed, 0 errors, exit 0** in 158.51 s
  (re-run with `-rs`: 550 passed / 37 skipped in 169.85 s — stable, all 37 skips
  carry a reason). Collection: 518 items / 6 errors → **587 items / 0 errors**.
* Two tracked build artifacts (`tracker/firmware/components/fips_transport/test/test_fips*`)
  are rewritten by the C host tests during a run; they were restored with
  `git checkout --` and are **not** part of the commit.
* REPORT.md written with the disposition table, before/after evidence and the
  file/verify inventory.

