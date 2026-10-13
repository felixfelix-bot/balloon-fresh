# Distributed Range Test — Timing Tolerance & Launch-Offset Robustness Analysis

**Branch:** `feat/2g4-sweep`
**Scope:** `firmware/e80-stm32-bench/tools/e80_bench_ctl.py` (`run_tx_mode` / `run_rx_mode`)
**Author:** design review prompted by operator question
**Status:** analysis + minimal recommended fix implemented

> Operator question: *"What happens if we trigger the make targets on
> TX and RX multiple minutes apart? How tolerant to offsets in initiation
> time is the system? Does it use some sort of modulo and/or wrap around
> to recover from such situations?"*

Short answer: **the system has a wide but finite tolerance window
(default ≈ 90 s after T0), and it does NOT use modulo or wraparound.
A late launcher silently catches past timestamps and cascades into
permanent desync.** This document explains the failure modes, why modulo
is the wrong tool here, and the minimal fix we recommend (and ship below).

---

## 1. Current Timing Model

### 1.1 Schedule construction

`build_preset_schedule(cfgs, t0_epoch, t0_margin, guard, settle, rx_lead,
swd_reset_s)` computes absolute epoch start times, one per config in the
JSON preset:

```
starts[0] = T0 + t0_margin
starts[i] = starts[i-1]
          + cfgs[i-1].expected_s      # burst duration (airtime*N + gap)
          + settle                     # post-burst quiet
          + guard                       # inter-config breathing room
          + rx_lead                     # re-arming slack
          + (swd_reset_s if mod/sf/br/bw changed)   # SX1280 can't hot-switch
```

`expected_s` per config = `n_pkts * (airtime_s + gap)`, e.g.:

- FLRC-650, LEN=51, N=10000, gap=5000 µs → airtime ≈ 0.7 ms × 10000 + 50 s ≈ 57 s
- FLRC-2600, LEN=51, N=10000 → ≈ 5 s
- LoRa-SF12, LEN=51, N=1000 → ≈ 130 s
- LoRa-SF7, LEN=51, N=10000 → ≈ 33 s

A typical 5-config preset (FLRC-650/2600 + SF7 + SF12 + FLRC-650-anchor)
takes ~5–6 minutes end-to-end including all gaps.

### 1.2 Absolute-time sync primitive

Both `run_tx_mode` and `run_rx_mode` define a **local** `wait_until(ts)`
identical in body:

```python
def wait_until(ts):
    while True:
        d = ts - time.time()
        if d <= 0:
            return                # PAST → returns immediately
        time.sleep(min(d, 30.0))  # caps any single sleep
```

Critical property: **if `ts <= now`, `wait_until` is a no-op**.

### 1.3 RX vs TX per-config flow

```
        ←────── starts[i-1]──────→←─gap─→←rx_lead→←─ starts[i] ─→
                                                       │
RX:   wait_until(start-rx_lead) → CFG cmds → wait_until(start) → drain_pkts(expected+settle+guard)
TX:                                       → CFG cmds → wait_until(start) → START → poll STAT
```

RX arms its listener `rx_lead` seconds before TX bursts. After the burst,
RX drains serial for `expected_s + settle + guard` (= the full capture
window) before issuing the next config's commands.

### 1.4 How T0 is shared

The Makefile defaults to:

```makefile
T0 ?= $(shell date -d '+5 minutes' '+%Y-%m-%d %H:%M' ...)
```

…but this is **per-invocation** (`?=`), so each operator's `make range-tx`
gets a different timestamp unless one of them explicitly passes
`T0='2026-08-30 14:05:00'` on the command line. In practice the operator
shares T0 by phone/chat ("both start at 14:05"), then both run:

```
make range-tx T0='2026-08-30 14:05:00'
make range-rx T0='2026-08-30 14:05:00'
```

Config 0 then fires at `T0 + t0_margin = 14:07:00`.

### 1.5 Default parameters

| Parameter      | Default | Meaning                                          |
|----------------|---------|--------------------------------------------------|
| `t0_margin`    | 120 s   | startup buffer before config 0 start             |
| `rx_lead`      | 10 s    | RX arms before TX bursts                         |
| `guard`        | 20 s    | inter-config gap                                 |
| `settle`       | 2 s     | post-burst quiet before RX STAT?                 |
| `swd_reset_s`  | 10 s    | extra gap when mod params change (SX1280 limit)  |

### 1.6 Timeline diagram (default params, 5 configs)

```
T0                                                                                       wall
 │                                                                                               
 │   ←─ t0_margin=120s ─→←── cfg 0 ──→G+S+RL←─ cfg 1 ─→G+S+RL ←─ cfg 2 ─→G+S+RL←─ cfg 3 ─→G+S+RL←─ cfg 4 ─→
 │                       │              │              │              │              │
 │                       │              │              │              │              └── final settle+guard
 │                  starts[0]       starts[1]      starts[2]      starts[3]      starts[4]
 │                       │
 │            ┌──────────┴──────────┐
 │            │ RX arm start        │    (rx_lead = 10s before each cfg)
 │            │ Board open + drain  │
 │            │ FW hash gate        │    ← ~5-15s of init time
 │            └─────────────────────┘
 │
 └──────────────► operator launch time L  (must be ≤ starts[0] - rx_lead - init_time)
```

---

## 2. Tolerance Window

The system tolerates **launch offset** as long as the later machine still has
enough time to finish **board open + drain + (optional FW hash gate) + config
commands** before the first `wait_until` target is reached.

### 2.1 Default parameters

```
starts[0] - rx_lead  =  T0 + 120 - 10  =  T0 + 110
init_time (RX)       ~  board open + drain + 6 cmds ≈ 5-15 s

Tolerance RX (relative to T0):  ≤ 110 - ~15  =  ~95 s
Tolerance TX (relative to T0):  ≤ 120 - ~5   =  ~115 s   (no rx_lead)
```

In other words: **if both operators launch within ~90 s of each other
(after T0 is set), the system stays in sync.** Beyond ~120 s the late
machine starts missing config 0.

### 2.2 Custom parameters

The user can widen the window by passing `--t0-margin 300` (5 min startup
buffer) for the cost of overall wall-clock duration. With `t0_margin=300`,
the tolerance window widens to ~280 s. There is **no parameter that makes
the system recover from missing configs** — only one that pushes the first
start later, buying more launch slack.

### 2.3 Why NTP clock drift is not the issue

Test results cited by the operator (TX=DQ05 UTC-4, RX=T470 UTC+2,
50/50, 0% PER, ~1 s drift) confirm: with `t0_margin=120, guard=20,
settle=2`, a 1 s clock skew is absorbed trivially. The failure mode we
worry about is not clock drift — it is **launch-time offset**, which is
~3 orders of magnitude larger (minutes vs seconds).

---

## 3. Failure Modes When Launch Offset > Tolerance

We have three distinct failure cases. All three currently manifest as
**silent cascading desync**: nothing aborts, the log just contains garbage.

### 3.1 RX launches late, TX on time (the common case)

Suppose TX launches at T0 correctly. Config 0 starts at `T0+120`.
RX launches at `T0+200` (80 s after TX already bursted).

What happens on RX:

1. opens board, sends 6 config commands for cfg 0 (~5 s);
2. `wait_until(starts[0] - rx_lead)` — timestamp is `T0+110`, already
   past by 90 s → **returns immediately**;
3. `wait_until(starts[0])` — `T0+120`, already past by 80 s →
   **returns immediately**;
4. `drain_pkt_lines(dur = expected_s + settle + guard)` — RX listens
   for ~30–130 s on cfg 0's frequency, but TX finished cfg 0 long ago
   and is now in cfg 1 (different freq/mod). RX captures silence or,
   worse, the tail of cfg 1, which it logs under cfg 0's header;
5. RX advances to cfg 1: `wait_until(starts[1] - rx_lead)` returns
   immediately, arms listener on cfg 1 freq. TX is now in cfg 2. RX
   captures the wrong burst again;
6. **cascades through all N configs**, the RX log is mostly zeros with
   a few packets captured in the wrong slot.

Result: TX log shows correct `sent_ok` totals, RX log shows 0/N for
most rows. *No error is raised.* The merge script later reports ~100 %
PER for the run, which looks like a hardware failure rather than what
it really is (operator error).

### 3.2 TX launches late, RX on time (the dangerous case)

RX arms for cfg 0 at `T0+110` on the correct frequency. TX launches
at `T0+200`. TX races through its pre-config commands and `wait_until`
returns immediately for the past timestamp.

Result: TX bursts immediately on cfg 0 freq. RX, however, has already
been armed and listening since `T0+110` and has drained for
`expected_s + settle + guard` (~30–130 s). RX will have *long since
stopped listening* by the time TX actually transmits — RX timed out
waiting and moved on to cfg 1. TX bursted into a closed listener.

Same cascade: TX log has correct `sent_ok` numbers, RX log is mostly
empty, ~100 % PER reported.

### 3.3 Both launch late equally

If both launch at `T0+200` (synchronised relative to each other but
later than T0): both immediately catch up to the latest future start
and run from there. The early configs are skipped entirely.

Whether this is OK depends on operator intent: if they want configs 0–4
but only ran 2–4, all results are valid PER but the dataset is incomplete.
**This is the only naturally-recoverable case** — the late-but-synced
case — and it could be made explicit with a `--skip-late-configs` flag
(see §5).

### 3.4 One machine crashes mid-test and restarts

If TX crashes after cfg 2 and restarts at `cfg 2 finish + 10 s`:
TX re-runs the full preset from cfg 0 (timestamps for cfg 0/1/2 are
past → immediate skips), then catches up to cfg 3 as RX is waiting.
Result: TX redoes cfg 0–2 as ghost bursts (RX is in cfg 3 capture
window and captures nothing of those ghost bursts), then resyncs at
cfg 3.

RX-side crash after cfg 2: similar — RX skips cfg 0/1/2 timestamps
immediately, then catches up to cfg 3 (~30–130 s late). Whether the
RX side resyncs depends on whether TX has moved on past cfg 3 in the
meantime. If TX is mid-cfg-3 burst, RX joins too late to capture all
of it; if TX is past cfg 3, RX captures nothing.

### 3.5 Summary of failure signature

All four cases share the same signature: **no `--dry-run` validation,
no startup assert, wait_until silently skips, RX log contains zero
captured packets while TX log shows full sent_ok, merge reports
~100 % PER**. Nothing in the toolchain distinguishes "the radio is
broken" from "the operator started 90 s late".

---

## 4. Does Modulo / Wraparound Make Sense Here?

**Short answer: no, modulo/wraparound is the wrong primitive for a
single-shot sweep. It only fits continuous/periodic monitoring.**

### 4.1 What modulo/wraparound would mean

Define `P = starts[-1] + cfgs[-1].expected_s + settle + guard - starts[0]`
as the cycle length. A late launcher would compute:

```
idx   = first i in [0,N) such that starts[i] + k*P > now + init_time
       for some integer k ≥ 0
phase = (now - T0 - t0_margin) mod (P / N)   ... need both evaluations
then run from idx forwards, looping through the schedule
```

Two ways to interpret this:

1. **Repeating infinite schedule** (`--cyclic`): the tool loops through
   the preset forever; late launches just pick up the next phase. This
   is fine for a *long-running PER monitor* (e.g., 24 h drift test).
   Not applicable to the campaign sweep — a single stop is one pass.

2. **Cyclic catch-up within one pass** (`--modulo`): a late launcher
   skips ahead to the next upcoming start, runs the remaining configs,
   then either re-loops to grab the missed configs (only works if the
   TX also follows the same discipline!) or fills the holes in a later
   pass.

### 4.2 Why modulo fails for this design

**Reason 1: TX sends each burst exactly once.** There is no "next cycle"
to wrap into. RX wrapping means RX listens to silence while TX has long
since moved on. The fundamental constraint — *RX must have its listener
armed exactly when TX's burst is on-air* — is not solvable by modulo
because TX does its own thing in real time.

**Reason 2: Catch-up contraction.** Even if both machines wrapped identically,
the late machine would need to skip ahead and miss early configs
permanently — exactly the behaviour `wait_until` already produces
implicitly today. Modulo is just an obfuscated name for "skip-and-continue".

**Reason 3: SWD resets take ~10 s each.** The schedule already has to
shoe-horn in extra padding (`swd_reset_s`) for mod changes. A cyclic
schedule that involves wrapping through mod-change boundaries would
introduce nondeterministic gap budget — the modulo arithmetic would
need to know whether each transition triggers a reset, and the TX and
RX would need the identical SWD state at any catch-up point. They
don't, by construction: TX and RX independently perform their own SWD
resets when their local `_mod_changed` predicate fires.

**Reason 4: Simplicity loss.** The current `wait_until(ts)` is 4 lines
and obviously correct. Cyclic scheduling with phase alignment,
inter-machine pairing, and SWD-slot budgeting would be ~100+ lines and
subtly buggy. The test/prod is radio-driven PER measurements at discrete
distances; it does not need continuous overlay.

### 4.3 When modulo *would* be the right tool

A genuinely different use case: **always-on PER monitoring** ("run this
preset all day, log continuously, two boards left alone"). Then
modulo/wraparound with `--cyclic` is the correct mental model: missed
configs become air-to-airs in later cycles; the operator accepts that
catch-up is approximate, or designs the preset so all configs in a cycle
fit inside one reporting interval. That is a *different tool* for a
*different job* — not the campaign sweep.

Fine idea to have as a future `--cyclic` mode, but **not the fix for the
launch-offset problem**.

---

## 5. Alternative Approaches (Simplicity vs Robustness)

Ranked from simplest to most robust. The trade-off is implementation
cost vs. operational guarantees.

### 5.1 (A) Make `--t0-margin` Larger — Lowest cost, still fragile

Bump the default to 300 s. Buys 3 extra minutes of slack. Still cannot
recover from a launch 6+ minutes apart. No new code, no new failure mode.
Doesn't fix the silent-desync class of bugs.

**Cost:** trivial (one Makefile/argparser default).
**Robustness gain:** linear (just more headroom, same failure shape).

### 5.2 (B) Startup Lateness Assertion + `--skip-late-configs`  ★ RECOMMENDED

At the top of `run_tx_mode` and `run_rx_mode`, after computing `starts`,
check whether `now > starts[0]` (TX) or `now > starts[0] - rx_lead` (RX).
If so, default behaviour: **print a clear error and exit**, telling
the operator exactly how late they are and which configs they missed.

Add `--skip-late-configs` flag: when set, advance `cfgs`/`starts` to the
first config whose start (minus rx_lead for RX) is still in the future.
This makes **case 3.3 (both late-but-synced)** explicit and recoverable,
and turns **cases 3.1 / 3.2 (one side late)** into a definitive abort
instead of a silent desync.

The implementation is a **pure function** (`compute_late_skip`) of the
already-pure `build_preset_schedule`, so it can be unit-tested without
touching serial ports or `time.time()`.

**Pros:**
- Catches the silent-desync class of bugs that produces ~100 % PER
  mystery results;
- The default (abort on lateness) is the *correct* safety posture —
  the operator gets a message they can act on in 0.5 second instead
  of debugging hours of garbled logs;
- The opt-in `--skip-late-configs` enables the naturally-recoverable
  case (both sides equally late) without making it the default;
- No protocol, no network, no extra coordination — pure local check;
- Backwards-compatible: with no flag, default behaviour changes from
  "silent desync" to "loud abort", which is strictly better.

**Cons:**
- Doesn't help when *one* side is late and the other is on time
  (that case is unrecoverable by any local mechanism — the on-time
  side already sent bursts into silence). The abort at least tells
  the operator "redo this run" instead of producing garbage;
- Doesn't help mid-test crashes for continuing the *current* run
  (3.4) — that requires barrier/resync via a side channel.

**Cost:** small. One pure helper (~25 lines), two call sites (~5 lines
each), one argparser flag, ~10 unit tests.

### 5.3 (C) Ready/Barrier Sync via Shared File or Network

Coordinator creates a ready-signalling mechanism: each TX/RX host
touches a file or hits an HTTP endpoint when finished init; only once
*both* report ready, both proceed. Implemented as:

```
# Coordinator side:
await_barrier(["tx", "rx"], timeout=300s)
broadcast T0 = now + 60s   # so we know both are past their init
```

or via SSHDMIN-style handshake over a tailnet socket.

**Pros:**
- Solves the launch-offset problem completely (both sides guaranteed
  in sync before T0 is even set);
- Doesn't depend on shared clock accuracy.

**Cons:**
- Operator has to **be** on a tailnet/SSH-capable network between the
  two hosts — not always true in field deployments (e.g., DQ05 on
  battery in a field with only 4G uplink to a relay);
- Adds a new failure mode (barrier times out);
- Significant code: HTTP/file/socket plumbing, retry logic, timeout
  handling, two-sided protocol spec;
- Couples the radio test orchestration to network topology;
- Already have a working manual-sync discipline ("share T0 by phone")
  — the barrier replaces a 10-second human decision with 200 lines
  of code.

**Cost:** large. Two-sided protocol, ~200 lines + tests + operational
docs. Recommend against for the moment.

### 5.4 (D) Adaptive Realtime Schedule (TX emits beacon config, RX follows)

The TX emits a low-rate beacon frame ("next config ID = i, burst
start in T ms"); RX listens on a known beacon freq, decodes the
beacon, switches to the indicated config. No T0 needed; schedule is
self-describing.

**Pros:**
- Eliminates the schedule sync problem entirely. Late RX just decodes
  the next beacon;
- Also fixes the mid-test-crash-zero-recovery problem — RX picks up
  wherever TX is.

**Cons:**
- Requires firmware changes (beacon emission, beacon RX, message
  parsing, freq hopping outside the test channel);
- Adds air-time cost on every config transition;
- Couples the test shell to firmware behaviour, breaks the "tool just
  schedules" layering;
- Major engineering effort, weeks not days.

**Cost:** very large. Not appropriate until/unless we have a real reason
to need continuous monitoring.

### 5.5 Ranking summary

| Approach | Cost | Aborts silent desync? | Recovers late-launch? | Recovers mid-test crash? |
|----------|------|------------------------|-------------------------|---------------------------|
| (A) larger `t0_margin`       | trivial | no  | no  | no  |
| (B) lateness assert + skip   | small   | yes | partially (case 3.3) | no |
| (C) barrier sync             | large   | yes | yes | no |
| (D) TX-beacon scheduling     | very large | yes | yes | yes |

Approach (B) is the highest value-per-line option. It catches the
class of bugs that waste operator hours (~100 % PER mystery), recovers
the *only* locally-recoverable late-launch shape (both sides equally
late), and preserves the existing "T0 + absolute schedule"
architecture that has already been proven in two-computer tests.

---

## 6. Recommendation

**Implement approach (B). Reject modulo/wraparound.** Specifically:

1. Add a pure helper `compute_late_skip(starts, now, rx_lead=None,
   min_ahead_s=5.0)` that returns either `None` (no skip needed —
   still on time) or an integer index `i` such that `starts[i:]` is
   the slice whose start (minus `rx_lead` for RX) is at least
   `min_ahead_s` seconds in the future. Fully unit-testable, no
   side effects.

2. In `run_tx_mode` / `run_rx_mode`, call it after building `starts`.
   If it returns non-`None` and `--skip-late-configs` is unset, exit
   with a clear error including:
   - seconds since T0 was supposed to fire,
   - how many configs are already in the past,
   - the suggested command (`--skip-late-configs`) for the recoverable
     case.

3. If `--skip-late-configs` is set, slice `cfgs[start_idx:]` and
   `starts[start_idx:]` and proceed normally with the recovered
   slice. Print a `[LATE]` notice so the operator's transcript
   includes the truncation.

4. Add `--skip-late-configs` to the argparser.

5. The implementation preserves backward compatibility: with no flag
   passed, the behaviour changes from "silent desync" to "loud
   abort", which is strictly safer; existing on-time runs are
   unaffected (the new check is a no-op when `now <
   starts[0] - rx_lead`).

### Explicitly NOT recommended

- Modulo/wraparound scheduling — wrong primitive for single-shot sweeps.
- Barrier sync — overkill for the current operational pattern; defer
  to a `--cyclic` continuous-monitor mode if/when that lands.
- Beacon scheduling — major effort, belongs in firmware not in the
  `e80_bench_ctl` host tool.

### Implementation notes

See the doc footer (Appendix A below) for the actual diff applied. The
new helper is unit-tested in `tools/test_e80_bench_ctl.py` alongside
the existing `build_preset_schedule` tests. Five new test cases cover:

- on-time (no-op);
- past first start, future later starts (returns valid slice index);
- all starts past (returns `None`, operator should re-T0);
- TX semantics (no rx_lead);
- `min_ahead_s` flabbing (prevents catching a start that's 1 s in the
  future, which would race the serial init).

New argparser flag:

```
--skip-late-configs   allow a late launch to skip past configs already
                       missed and proceed from the next future one
                       (default: abort on lateness)
```

---

## 7. Operator Quick-Reference

```
T0 = "2026-08-30 14:05:00"

# On the TX machine, within ~110s of T0+0:
make range-tx  T0='2026-08-30 14:05:00'

# On the RX machine, within ~95s of T0+0:
make range-rx  T0='2026-08-30 14:05:00'

# If you start late but BOTH machines start equally late and at least
# 5s before some future config start:
make range-rx  T0='2026-08-30 14:05:00' --skip-late-configs

# If only one machine was late: ABORT and restart with a new T0.
# The tool will tell you exactly how late when you start it.
```

The tool now refuses (by default) to start a config whose timestamp is
already past; you get one clear error and one clean restart.

---

## Appendix A: Implementation Diff

Added to `e80_bench_ctl.py`:

```python
def compute_late_skip(starts, now, rx_lead=0, min_ahead_s=5.0):
    """Return index into starts[] where the schedule can still be joined,
    or None if the entire schedule has already passed.

    'start_idx' is the index of the first start whose (start - rx_lead)
    timestamp is at least min_ahead_s seconds in the future relative to
    `now`, allowing for board init/swd-reset time. If no such start
    exists, returns None (the operator must re-T0).

    Used by run_tx_mode/run_rx_mode to catch silent launch-late desync.
    Pure function; side-effect free; trivially testable."""

    earliest = now + min_ahead_s
    for i, s in enumerate(starts):
        if (s - rx_lead) >= earliest:
            return i
    return None
```

Call site in `run_tx_mode`:

```python
lateness = compute_late_skip(starts, time.time(), rx_lead=0)
if lateness is not None and lateness > 0:
    if not args.skip_late_configs:
        sys.exit("ERROR: launched {:d}s after T0 — configs 0..{} have already "
                 "started. Aborting to avoid silent desync. Re-set T0, or pass "
                 "--skip-late-configs to start from config {} ({}).".format(
                     int(time.time() - starts[0]),
                     lateness - 1,
                     lateness + 1,
                     cfgs[lateness]["label"]))
    print("[LATE] Skipping configs 0..{} (already past).".format(lateness - 1))
    cfgs = cfgs[lateness:]
    starts = starts[lateness:]
elif lateness is None:
    sys.exit("ERROR: all {} config start times are in the past (by {:.0f}s). "
             "Re-set T0 to a future time and relaunch.".format(
                 len(starts), time.time() - starts[-1]))
```

(Analogous block in `run_rx_mode`, with `rx_lead=args.rx_lead`.)

Tests added: `LateSkipTests` class in `tools/test_e80_bench_ctl.py`,
5 cases.
