# Consultant Plan Review V5 — Post-Major-Work-Session Assessment

**Date:** 2026-08-05 13:05
**Reviewer:** Consultant (automated)
**Session context:** 61 commits today on `autonomous/mesh-baseline`, 5 consultant bugs fixed, 3 plans + 4 reviews written, 5 active worker tasks
**Previous review:** V4 (CONSULTANT-PLAN-REVIEW-V4.md)

---

## EXECUTIVE SUMMARY

The project has made extraordinary progress in this session — from "no unified firmware, 5 known bugs, 3 missing plans" to "unified builds passing on C3 and S3, 433+12+7 tests green, 5 bugs fixed, CLI audit done, 3 CLI commands being implemented, PCB task dispatched, FIPS worker running." The orchestrator's dispatch decisions have been sound: critical-path-first (PCB), no-hardware-second (FIPS), audit-then-implement (CLI). The main risks now are resource exhaustion (3.4GB/7GB RAM, 4 cores, load 3.07), merge conflicts from 3 workers touching the same files, and the tollgate_payment_proto.h discovery that changes the scope of the tollgate_send_pay task.

---

## 1. WORKER DISPATCH ASSESSMENT

### What's running (5 tasks)

| Task | Worker | Status | Assessment |
|------|--------|--------|------------|
| P2 PCB fix | worker-balloon | dispatched (retry) | ✅ Correct priority. First attempt crashed, re-dispatched. KiCad files + CLI found. |
| P3 FIPS build | worker-fips | running (run 164) | ⚠️ Previous run OOM'd. See §3. |
| P5 relay_send_nostr | worker-balloon | running | ✅ Dependencies met, straightforward. |
| P5 nostr_dump | worker-balloon | running | ⚠️ Needs refactoring nostr_store_t scope — see §4. |
| P6 tollgate_send_pay | worker-balloon | running | 🔴 DEPENDENCY NOT MET — tollgate_payment_proto.h was assumed missing but EXISTS in mesh-stack/tollgate. Worker may be writing from scratch unnecessarily. See §5. |

### Verdict: Dispatch was correct, but tollgate_send_pay needs immediate correction

The parallel dispatch of 3 CLI commands was aggressive but reasonable given they're independent commands. However:

1. **tollgate_send_pay is the problem child.** The CLI audit said `tollgate_payment_proto.h` doesn't exist in `tracker/firmware/` — correct. But it DOES exist at `mesh-stack/tollgate/components/tollgate_balloon/include/tollgate_payment_proto.h` with a full implementation (PAY/ACK/NACK payloads, encode/decode). The worker should be **copying this file**, not writing from scratch. This is a 1-hour task, not a 4-8 hour task, if the existing proto is ported.

2. **All 3 CLI workers are touching `main/app_main.cpp`.** This is a guaranteed merge conflict vector. The file has a `setup_cli()` function at line ~395-407 where all commands register. Three workers will all modify this function simultaneously. **Action needed: see §4.**

3. **worker-fips has been running for a while (run 164).** The previous run OOM'd. Current system memory is 3.4GB used / 7GB total with 3.7GB swap used — the system is under memory pressure. The FIPS Rust build (`cargo build` for `riscv32imc`) is memory-intensive. See §3.

---

## 2. RESOURCE MANAGEMENT

### Current system state (measured at 13:03)

| Metric | Value | Assessment |
|--------|-------|------------|
| RAM used | 3.4GB / 7.0GB | ⚠️ 49% used, but only 360MB truly free (buff/cache 3.6GB) |
| Swap used | 3.7GB / 15GB | ⚠️ System is actively swapping — this will cause OOM kills |
| CPU load | 3.07 / 3.78 / 2.56 | ⚠️ Sustained load above core count (4 cores) — system is oversubscribed |
| Worker processes | ~8 (per context) | 🔴 Too many for 4-core, 7GB RAM system |
| DQ05 remote | Unreachable | Not relevant to this assessment |

### Diagnosis: System is over-subscribed but not yet critical

The 1-minute load average (3.07) is below the 5-minute (3.78), suggesting load is decreasing — workers are finishing tasks. However:

- **Swap usage (3.7GB) is the real danger.** The FIPS worker's previous OOM crash was likely caused by `cargo build` allocating large amounts of memory while other workers were also active. With 3.7GB already in swap, another large allocation could trigger the OOM killer.
- **The PCB task doesn't need much CPU/RAM** (KiCad CLI is lightweight). It's blocked not by compute resources but by whether the worker process can get a slot. This is a scheduling problem, not a resource problem.

### Recommendation: Reduce to 3 concurrent workers

1. **Immediately:** When the first CLI command worker finishes (relay_send_nostr is the simplest, 2-4h), do NOT immediately dispatch another task. Let the system breathe.
2. **FIPS worker:** Give it priority on memory. If another OOM crash happens, kill the FIPS worker and run it alone with no other workers. The Rust build is the single most memory-intensive task.
3. **PCB task:** This is I/O-bound (editing text, running kicad-cli). It can run concurrently with anything — it barely uses CPU or RAM. Dispatch it as soon as a worker slot opens, even if FIPS is running.
4. **Merge conflicts:** Do NOT let all 3 CLI command workers finish simultaneously and then try to merge. See §4.

---

## 3. FIPS BUILD VIABILITY (Question 3)

### The approach is correct. The execution environment is the problem.

The plan (portable_atomic everywhere, esp32c3 cfg variants, esp-println logger) is the right approach. The 3 bugs are well-specified and the fixes are standard. This will work.

**The OOM risk is environmental, not architectural.** `cargo build` for `riscv32imc-unknown-none-elf` with the esp32c3 target requires compiling libcore and all dependencies from scratch. This easily uses 2-3GB of RAM with default linker settings. On a 7GB system with 3.7GB already in swap, this is marginal.

### Recommendation

1. **Let the current run (164) continue** if it hasn't crashed. Check its status.
2. **If it crashes again:** Kill all other workers, clear swap (`swapoff -a && swapon -a`), and run FIPS build alone:
   ```bash
   # Kill everything else first
   # Then:
   cargo build -p microfips-esp32c3 --target riscv32imc-unknown-none-elf -j 2
   ```
   The `-j 2` flag limits parallel compilation jobs, reducing peak memory usage at the cost of build time.
3. **Do NOT simplify the plan.** The 3-bug fix is already as simple as it gets. If the environment can't support the build, the fix is to reduce parallelism, not to change the code approach.

---

## 4. MERGE CONFLICT RISK — 3 WORKERS ON app_main.cpp (Question 4)

### The problem

All 3 CLI commands need to:
1. Add a handler function in `main/app_main.cpp` (e.g., `cli_cmd_relay_send_nostr()`)
2. Register the command in `setup_cli()` at lines ~395-407
3. Potentially add includes at the top of the file

Three workers editing the same function in the same file simultaneously will produce merge conflicts on every pair.

### Recommendation: Serialize the merge, not the work

The workers can write their code in parallel (each in its own branch or worktree), but the merge into `autonomous/mesh-baseline` must be serialized:

1. **First worker to finish:** Merge directly. This becomes the base.
2. **Second worker:** Rebase on the updated `autonomous/mesh-baseline`, resolve the `setup_cli()` conflict (just add their line after the first worker's line), then merge.
3. **Third worker:** Same — rebase, resolve, merge.

**Alternative (better):** Have each worker write their command handler as a **separate file** (e.g., `cli_cmd_relay_nostr.c`, `cli_cmd_nostr_dump.c`, `cli_cmd_tollgate_pay.c`) and only add a single `#include` + `cli_register_command()` line in `app_main.cpp`. This minimizes the conflict surface to 1 line per worker.

**If conflicts have already happened:** Don't panic. The conflicts will all be in `setup_cli()` — a simple function with a list of `cli_register_command()` calls. Resolution is mechanical: concatenate the lines.

### nostr_store_t scoping issue (from worker report Q2)

The `nostr_store_t` is a local variable in `app_task()` at `app_task.cpp:57-58`. For `nostr_dump` to access it from `app_main.cpp`, it needs to be refactored.

**Recommendation:** Make it `static` in `app_task.cpp` and add an accessor:
```c
// app_task.cpp
static nostr_store_t s_store;
nostr_store_t* nostr_store_get_shared(void) { return &s_store; }
```
This is simpler than moving it to `app_main.cpp` (which would break the init sequence) and avoids creating a separate store instance. The worker should do this.

---

## 5. TOLLGATE PAYMENT PROTO — CRITICAL FINDING (Question from worker report Q1)

### The file already exists

```
mesh-stack/tollgate/components/tollgate_balloon/include/tollgate_payment_proto.h
mesh-stack/tollgate/components/tollgate_balloon/src/tollgate_payment_proto.c
```

This file has:
- `tollgate_msg_hdr_t` (8-byte packed header)
- `tollgate_pay_payload_t` (Cashu token)
- `tollgate_ack_payload_t` (session_id, expires, quota, price)
- `tollgate_nack_payload_t` (error code + message)
- Error codes (`TG_ERR_INVALID_TOKEN`, etc.)
- INFO message format (JSON)

### What the worker should do

1. **COPY** `tollgate_payment_proto.h` and `.c` from `mesh-stack/tollgate/components/tollgate_balloon/` into `tracker/firmware/components/tollgate_balloon/` (or a new component directory).
2. **ADAPT** the include path (`tollgate_balloon.h` → may need adjustment for the tracker firmware context).
3. **ENABLE** `CONFIG_ENABLE_TOLLGATE` in `sdkconfig.defaults.esp32s3`.
4. **BUILD** — if the proto compiles, the CLI command is trivial (encode PAY → queue).
5. **DO NOT** write a new protocol from the mock in `test_relay_pipeline.c`. The mock was a placeholder. The real protocol in `mesh-stack/tollgate/` is the source of truth.

**Action:** Redirect the tollgate_send_pay worker to use the existing proto. This changes the task from "4-8 hours, High complexity" to "1-2 hours, Low complexity."

---

## 6. INTEGRATION TEST PLAN VALIDITY (Question 1)

### Phases 5-7 are still correct, with minor updates

| Phase | Status | Updates needed? |
|-------|--------|------------------|
| Phase 5: Raw ping | ✅ Valid | radio_test + radio_recv exist and work. Use as-is. Note: radio_test uses direct radio API, not relay queue — this is fine for raw ping. |
| Phase 6: Nostr round-trip | ✅ Valid once relay_send_nostr + nostr_dump are implemented | The test flow (send event → receive → store → dump) is correct. The CLI commands being implemented now will unblock this. |
| Phase 7: TollGate round-trip | ✅ Valid once tollgate_send_pay is implemented + CONFIG_ENABLE_TOLLGATE enabled | The test flow (PAY → ACK) is correct. But: the ACK side needs `tollgate_proto_decode()` in `app_task.cpp` which currently has `#include "tollgate_payment_proto.h"` that resolves to nothing. Once the proto is copied in, the decode path should work if `app_task.cpp` already has the dispatch logic. |

### New concern: radio_test sends telemetry, not relay packets

The CLI audit found that `radio_test` uses `s_radio->send_packet()` (direct radio API) with a `telemetry_packet_t`, NOT `g_tx_queue` with a `relay_packet_t`. This means:

- **Phase 5 (raw ping):** ✅ Works — radio_test/radio_recv operate at the raw radio level, which is what raw ping needs.
- **Phase 6 (nostr round-trip):** The receiving board needs to route received packets through `g_rx_queue` → `app_task` → `nostr_store`. But `radio_recv` just prints hex — it doesn't push to `g_rx_queue`. **This means Phase 6 depends on the relay-mode radio_task being active and RX packets flowing through `g_rx_queue` automatically.** Verify that `radio_task.cpp`'s RX poll pushes to `g_rx_queue` even when not in an explicit `radio_recv` CLI session. It should — radio_task runs continuously and polls RX on its 100ms cycle.

**Recommendation:** Add a note to Phase 6: "Board B does NOT need `radio_recv` CLI running. The `radio_task` polls RX continuously and pushes to `g_rx_queue`. `app_task` drains `g_rx_queue` and dispatches by type tag. Just flash board B with relay mode + nostr_store enabled and watch serial logs for 'stored event' messages. Use `nostr_dump` after to verify."

---

## 7. THE SINGLE MOST IMPORTANT THING TO DO NEXT (Question 5)

### **Redirect the tollgate_send_pay worker to copy the existing proto file.**

Here's why:

1. **It's the highest-impact correction.** The worker is about to spend 4-8 hours writing a protocol from scratch that already exists. Copying it is 1 hour. That's a 3-7 hour savings on the critical path.

2. **It unblocks Phase 7.** TollGate round-trip is the last integration test. With the proto in place, the CLI command becomes trivial, and Phase 7 can proceed as soon as boards arrive.

3. **It prevents API mismatch.** If the worker writes a new proto that doesn't match `mesh-stack/tollgate/`, the integration tests will fail in subtle ways (wrong field sizes, wrong message format). The existing proto is battle-tested.

4. **It's a 30-second decision.** Send the worker a message: "The tollgate_payment_proto.h you need is at `mesh-stack/tollgate/components/tollgate_balloon/include/tollgate_payment_proto.h`. Copy it, don't write it."

### Secondary priorities (in order)

1. **Monitor FIPS worker for OOM.** If it crashes, run it alone with `-j 2`.
2. **Prepare merge plan for 3 CLI command workers.** When they finish, merge sequentially, not in parallel.
3. **PCB task:** Just needs to run. It's lightweight. Give it a worker slot as soon as one opens.
4. **After all CLI commands are merged:** Run CI to verify 433+12+7 tests still pass. Then update INTEGRATION-PLAN-V3.md to mark Phase 4 as DONE and Phases 5-7 as UNBLOCKED.

---

## 8. UPDATED RISK MATRIX

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| FIPS worker OOM crash (again) | Medium | High (blocks FIPS integration) | Run alone with `-j 2` if crash; don't simplify the plan |
| Merge conflicts in app_main.cpp | High | Low (mechanical resolution) | Serialize merges; use separate files for handlers |
| tollgate_send_pay worker writes proto from scratch | Medium-High | Medium (wasted time + API mismatch) | Redirect worker NOW to copy existing proto |
| PCB task starved by worker slots | Medium | High (critical path delay) | PCB is lightweight — dispatch in any free slot |
| radio_recv doesn't feed g_rx_queue | Low | Medium (Phase 6 confusion) | Document that radio_task handles RX automatically |
| System runs out of memory with 8 workers | Medium | High | Reduce to 3 concurrent workers after first CLI merge |
| ngit push broken (from V4) | Ongoing | Low (GitHub-only works) | Use GitHub-only push; fix ngit later |

---

## 9. RECOMMENDED ACTION LIST (IMMEDIATE)

1. **[NOW] Redirect tollgate_send_pay worker:** "Copy `mesh-stack/tollgate/components/tollgate_balloon/include/tollgate_payment_proto.h` and `.c` into `tracker/firmware/components/tollgate_balloon/`. Adapt include paths. Enable `CONFIG_ENABLE_TOLLGATE`. Then implement the CLI command."

2. **[NOW] Check FIPS worker status:** If run 164 is still alive, let it run. If dead, clear swap and restart alone with `-j 2`.

3. **[WHEN FIRST CLI WORKER FINISHES] Don't immediately dispatch new work.** Let system memory recover. Merge the completed CLI command, run CI, then proceed.

4. **[WHEN ALL 3 CLI COMMANDS DONE] Merge sequentially:** relay_send_nostr → nostr_dump → tollgate_send_pay. Resolve `setup_cli()` conflicts mechanically.

5. **[AFTER MERGE] Run full CI:** `433 tests + 12 relay + 7 nostr_store`. All must pass. If any fail, bisect.

6. **[ONGOING] PCB task:** Dispatch in first available worker slot. It's I/O-bound, not CPU-bound.

---

## 10. ASSESSMENT OF V4 RECOMMENDATIONS

| V4 Recommendation | Status | Notes |
|---------------------|--------|-------|
| PCB should be first | ✅ Done | Moved to Phase 2, dispatched. Worker crashed, re-dispatched. |
| FIPS atomics simplified | ✅ Done | portable_atomic everywhere, no cfg. Worker running. |
| CLI commands verified | ✅ Done | Audit complete: 2 exist, 3 missing. 3 workers implementing. |
| 30cm too close | ✅ Done | Changed to 1-2m in test plan. |
| Board lock protocol | ✅ Done | Added to all task bodies. |

All 5 V4 recommendations addressed. No outstanding items from V4.

---

## BOTTOM LINE

The orchestrator has done excellent work this session. The project went from "5 bugs, no plans, no tests" to "tests green, bugs fixed, plans written, workers dispatched" in one session. The main risk now is operational (resource exhaustion, merge conflicts) not architectural. The single most impactful action is redirecting the tollgate worker to copy the existing proto — this saves 3-7 hours and prevents an API mismatch that would cause subtle integration test failures.

**Next priority after tollgate redirect:** Get the PCB task running. It's the critical path. Everything else can wait for boards to arrive.