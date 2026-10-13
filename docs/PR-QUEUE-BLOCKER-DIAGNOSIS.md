# Why the PR queue cannot drain — master's `test` job is RED

**Measured:** 2026-10-13, on `felixfelix-bot/balloon-fresh`
**Investigator:** manager session (operator asked to drive PRs 147–156 to merge)

## The answer in one line

**No PR can reach GREEN while `master`'s own `test` job fails.** The blockers
are repo test-infrastructure defects, not PR defects. The 10 PRs were never the
problem.

## Evidence

### master is red, and has been for days

```
$ gh run list --repo felixfelix-bot/balloon-fresh --branch master --limit 4
completed  failure  Merge pr/adr-pipeline-decisions…  Tests  master  38398507099  25s  2026-10-13T12:36Z
completed  success  Merge pr/adr-pipeline-decisions…  Host Unit Tests  master  38398507288  40s  2026-10-13T12:36Z
completed  success  merge: feat/mppt-charge-path…    Host Unit Tests  master  37621233403  1m22s  2026-10-07T12:28Z
completed  failure  merge: feat/mppt-charge-path…    Tests  master  37621233444  33s  2026-10-07T12:28Z
```

The `test` job has failed on every master push at least since 2026-10-07.
`Host Unit Tests` passes — so there IS a working green lane; `test` is the broken one.

### The failure is a FATAL COLLECTION ERROR, not a test failure

```
$ gh run view 38446345369 --log-failed
test  Run all tests  collecting ... ERROR: Need 2 ESP32 serial ports. Found: []
test  Run all tests  collected 65 items / 1 error
test  Run all tests  mainloop: caught unexpected SystemExit!
test  Run all tests  INTERNALERROR> Traceback (most recent call last):
```

A collection error fails the **entire suite** — so one mechanical defect reads as
"the whole test job is broken".

## Root causes (four distinct defects, all measured locally)

Reproduced in a clean worktree of `origin/master`
(`~/worktrees/fix-pytest-collect`):

### Defect 1 — manual hardware runners are collected as tests

Files under `tests/` match pytest's collection patterns but execute
hardware-dependent code **at import time**. `tests/p1b_ab_test.py`:

```python
ESP_PORTS = sorted([f"/dev/ttyACM{i}" for i in range(2, 10) if os.path.exists(...)])
if len(ESP_PORTS) < 2:
    print("ERROR: Need 2 ESP32 serial ports. Found:", ESP_PORTS)
    sys.exit(1)                      # <-- during collection
parser = argparse.ArgumentParser(...)   # module level
args = parser.parse_args()              # module level
```

On any machine without 2 ESP32 boards attached — including every GitHub Actions
runner — importing it calls `sys.exit(1)` while pytest is still collecting.

These files are invoked **by hand** (`python3 -u tests/p1b_ab_test.py`); nothing
in the repo references them. They are hardware runners, not unit tests.

**Affected (measured by `pytest --collect-only`):**
`tests/p1b_ab_test.py`, `tests/p1b0_delay_sweep.py`, `tests/lora_rpi_test.py`,
`tests/throughput-matrix/uart_id_test.py`, `tests/throughput-matrix/uart_rx_test.py`

**Fix:** `collect_ignore` in `tests/conftest.py` — see the accompanying commit.

> **Do NOT use a repo-root `conftest.py` for this.** It is imported under the same
> module name (`conftest`) as `tests/conftest.py` and **shadows** it, so modules
> doing `from conftest import …` break with `ImportError`. Measured: a root
> conftest broke 3 tests that way. `collect_ignore` inside `tests/conftest.py`
> has no collision.

### Defect 2 — three test files import helpers that do not exist

```
$ python3 -m pytest tests/test_link_budget.py --collect-only -q
ImportError: cannot import name 'load_link_budget' from 'conftest' (tests/conftest.py)
```

`tests/test_link_budget.py:3`, `tests/test_ground_station.py`,
`tests/test_telemetry_to_nostr.py` each do `from conftest import load_<name>()`.
**No `load_link_budget` / `load_ground_station` / `load_telemetry_to_nostr` is
defined anywhere in the repo** (`grep -rn "def load_"` finds unrelated helpers).
536 lines of test code were committed against a helper that was never committed.

**Confirmed pre-existing on master** (reproduced with the fix stashed).

**Fix needs a decision, not a guess:**
(a) reconstruct the loader (it should import the named module — e.g.
`link_budget` — and expose its functions), or
(b) delete the three files if the modules under test no longer exist.
This is a judgment call and is left for the operator/a tasked worker.

### Defect 3 — hardware tests are not marked, so CI cannot deselect them

`pytest.ini` declares the marker but nothing uses it:

```
[pytest]
markers =
    unit: Unit tests (no hardware required, fast)
    hardware: Hardware integration tests (requires RP2040 boards connected)
```

With defects 1+2 excused, the suite still has **10 errors** in hardware tests
(`tests/src/test_rp2040_speed.py`, `tests/test_board_lock.py`) because CI has no
boards. The declared-but-unapplied `hardware` marker is the intended mechanism.

### Defect 4 — 4 real test failures

```
= 4 failed, 462 passed, 10 skipped, 24 warnings, 10 errors in 184.99s =
```

These are genuine failures and need individual triage; they are not
infrastructure. (Exact names captured in the run above.)

## Measured baseline (clean master worktree + the collect_ignore fix only)

| | count |
|---|---|
| tests collected | **486** (was 65 + 1 fatal error) |
| passed | **462** |
| failed | 4 |
| skipped | 10 |
| errors (hardware, expected) | 10 |

## The ordered fix

1. `collect_ignore` for the 5 hardware runners — **done, in this commit**
2. Resolve the 3 `load_*` imports — **operator decision** (reconstruct vs delete)
3. Apply the `hardware` marker to hardware tests, then CI runs
   `python -m pytest tests/ -m "not hardware"`
4. Triage the 4 real failures
5. **Then** the 10 PRs can be re-evaluated for GREEN+CLEAN

## Consequence for the PR queue (the operator's actual ask)

The PR worker resolved conflicts and pushed merge commits to the PR branches
(`pr/v9-d3-four-ufl` → `1d16c31b`, `worker-heavy/tollgate-proto-inventory` →
`f1dad44f`, `worker-heavy/relay-mock-contract` → `de8e8dcd`), but **correctly
merged none** — under the standing GREEN+CLEAN rule they could not qualify,
because `test` is red for reasons unrelated to the PR contents.

**Fixing master is the unblocking action.** The queue drains afterwards.

Worktrees with resolved conflicts remain at `~/worktrees/pr-<N>/` — the conflict
work already done is **not** lost and can be re-pushed once `test` is green.
