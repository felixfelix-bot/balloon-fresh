# Consultant Review — Autonomous Execution Plan
## Critical Audit of PLAN-AUTONOMOUS-EXECUTION.md

**Reviewed by:** Senior Systems Architecture Consultant
**Date:** 2026-08-05
**Plan under review:** `docs/coordination/PLAN-AUTONOMOUS-EXECUTION.md`
**Context doc:** `docs/coordination/CONSULTANT-PROJECT-REVIEW.md`
**Method:** Every factual claim in the plan was verified against the actual repository state (`~/repos/balloon-fresh/`, worktrees, and source repos). File paths, function existence, and build configs were checked directly.

---

## EXECUTIVE SUMMARY

**The plan is well-structured but factually unreliable.** Of 15 tasks, at least **5 are already done** or based on false premises, **1 points to the wrong codebase entirely**, and **1 proposes a fix for a non-existent bug**. The plan reads as if it was written from stale status documents rather than from a fresh inspection of the codebase. Before any execution begins, the task list must be reconciled with reality — otherwise workers will waste hours re-implementing existing code and "fixing" bugs that don't exist.

**Verdict: CONDITIONAL GO** — execute only after the corrections in Section 3 below are applied. With corrections, the plan shrinks from ~13 hours to ~6-7 hours of genuine work and becomes significantly higher-value.

---

## 1. STRENGTHS — What the Plan Gets Right

1. **Clear phase structure and dependency ordering.** The 5-phase progression (build infra → blockers → mesh integration → tests → docs) is logically sound. Dependencies are mostly correct where they matter.

2. **Strong definition-of-done discipline.** Every task specifies a measurable completion criterion (build passes, test passes, artifact exists). The overall DoD checklist at the end is thorough. This is exactly the right approach.

3. **Correct identification of the critical path.** The plan correctly identifies that the mesh transport layer is the blocking dependency for most software tracks, and prioritizes build infrastructure unblocking first.

4. **Task 2.2 (secp256k1 measurement) is genuinely valuable and correctly scoped.** This is the single most important autonomous task — it gates the Schnorr validation architecture decision (ADR-026) and is truly unmeasured. The approach (minimal ESP-IDF project, `idf.py size`) is exactly right.

5. **Task 3.1 (ehash radio stub → LR2021) is valid and well-scoped.** The stub (`mesh-stack/ehash-relay/ehash_radio_stub.c`, 119 lines) genuinely exists and explicitly documents itself as a Phase D integration point. Replacing it with real transport calls is legitimate work.

6. **Task 5.3 (git clean) is practical and necessary.** The repo genuinely has 6 modified + 7 untracked files (verified). Cleaning this up prevents confusion.

7. **Constraints are well-articulated.** "No board access," "no new decisions," "every task produces a commit" — these are the right guardrails for autonomous work.

---

## 2. GAPS — What's Missing or Overlooked

### GAP-1: No "verify current state" pre-flight task [CRITICAL]
The plan assumes its task descriptions are accurate. They are not (see Section 3). **Before any execution**, the first task should be: "For each task in this plan, verify the claimed problem still exists against the actual codebase. Mark tasks DONE/SKIP if already resolved." This would have caught 5 of the issues below before any worker time was spent.

### GAP-2: No full build verification task
The plan has tasks to wire individual components, but no task that says: "Run `idf.py build` with `CONFIG_ENABLE_MESH=y` on the tracker firmware and verify it produces a binary." The actual integration test — does everything compile together — is missing. This is the single most valuable thing to verify.

### GAP-3: No DQ05 build server availability check
The project review states FIPS Phases 2, 4, 5, 6 are "blocked on DQ05." The plan's Task 4.3 (FIPS test crate) touches this area but never checks whether DQ05 is reachable. If the FIPS Rust code lives on DQ05 and DQ05 is down, Task 4.3 cannot execute. This should be a prerequisite check.

### GAP-4: `nostr_store` already does flash-backed persistence
The plan's Task 3.3 ("Port wisp-esp32 storage_engine for C3") assumes `nostr_store` is "RAM-only (606KB, doesn't fit)." But the actual `nostr_store.c` header comment says: *"Flash-backed Nostr event store for ESP32-C3. RAM: ~10 KB (index + bloom). Event content in flash via POSIX file I/O."* It already uses `fopen/fwrite/fread/unlink` on the filesystem. The 606KB RAM claim is from an older version or a different component. Task 3.3 may be partially or wholly unnecessary — this needs verification before writing a new storage component.

### GAP-5: No task to set `CONFIG_ENABLE_MESH=y` in sdkconfig
The tracker's `sdkconfig` currently has `# CONFIG_ENABLE_MESH is not set`. ESP-IDF uses `EXTRA_COMPONENT_DIRS "components"` which auto-discovers all components — so `mesh_adapter`, `fips_transport`, `nostr_store`, etc. are already registered. The real blocker is the Kconfig flag, not a missing CMakeLists.txt. No task addresses this.

### GAP-6: Task owners reference undefined roles
Every task says "Owner: delegate to worker (leaf role)." The AGENTS.md hierarchy defines sub-project managers and an orchestrator, but no "leaf role" or "worker" role. Either these tasks should be assigned to existing sub-managers (tollgate, fips, nostr, blossom, pow), or the hierarchy needs a new role definition. Without clear ownership, tasks will sit unclaimed.

### GAP-7: No regression baseline
The plan says "all existing tests still pass" in the DoD, but there's no task to capture the CURRENT test baseline (how many tests, which pass/fail) before starting work. Without a "before" snapshot, you can't detect regressions.

---

## 3. RISKS — Ranked by Severity

### RISK-1: Workers re-implement existing code [SEVERITY: CRITICAL]
**5 of 15 tasks describe work that is already done or based on false premises.** If executed as written, workers will:
- Create a `mesh_adapter/CMakeLists.txt` that already exists (Task 1.1)
- Implement `nostr_event_deserialize()` that is already implemented and tested (Task 2.1)
- "Fix" a bloom filter bug that doesn't exist (Task 2.3)
- Create a `blossom_datagram` component that already exists with 11KB of code (Task 3.2)
- Attempt to fix a FIPS test crate in the wrong repository (Task 4.3)

This wastes 4-5 hours of worker time and risks creating duplicate/conflicting code.

### RISK-2: FIPS test crate task targets wrong repository [SEVERITY: HIGH]
Task 4.3 says "Worktree: ~/worktrees/balloon-fips/" and claims "20 compile errors from old SPI API." Verification shows:
- The worktree has NO FIPS Rust test crate (only antenna tracker Rust code)
- The actual FIPS Rust code lives at `~/repos/microfips-upstream/` (17 crates)
- The actual build error is a **Rust toolchain version mismatch** (rustc 1.93.1 vs required 1.94.0 for `embassy-stm32f469i-disco`), NOT "old SPI API" errors
- Fixing this requires `rustup update` or pinning embassy versions, not rewriting SPI calls

### RISK-3: Duplicate blossom_datagram at wrong path [SEVERITY: HIGH]
Task 3.2 wants to create `firmware/blossom-server/blossom_datagram.h` + `.c` as new files. But a complete `blossom_datagram` component already exists at `tracker/firmware/components/blossom_datagram/` (11,525 bytes of `.c` code, header, CMakeLists, test directory). Creating a second implementation at a different path creates confusion about which is canonical and risks divergent protocol implementations.

### RISK-4: Plan's bloom filter "fix" would introduce a bug [SEVERITY: MEDIUM]
Task 2.3 claims the bloom filter "only selects bit positions 0-7." The actual code at `nostr_store.c:42-44`:
```c
uint16_t bits = sizeof(bloom->bits) * 8;       /* 512 */
bloom->bits[(h1 % bits) / 8] |= (uint8_t)(1u << (h1 % 8));
```
This is **correct two-level bit addressing**: `(h1 % 512) / 8` selects one of 64 bytes, `1 << (h1 % 8)` selects one of 8 bits within that byte. Together they address all 512 bits. The plan's proposed "fix" (`1 << (h1 % 64)`) would be WRONG — it would only set bits 0-6 within each byte, reducing coverage. **Do not execute Task 2.3 as written.**

### RISK-5: Blossom partition numbers are wrong [SEVERITY: LOW]
Task 1.3 says "factory 1MB→2MB, data 1MB→1.5MB." The actual `partitions.csv` shows factory is already `0x100000` (1MB) but blossom data is already `0x180000` (1.5MB), not 1MB. The expansion should be factory 1MB→2MB (correct concept) but the "data 1MB→1.5MB" is based on a wrong current-state assumption.

### RISK-6: Worktrees are stale [SEVERITY: LOW]
All four sub-manager worktrees (`balloon-fips`, `balloon-blossom`, `balloon-nostr`, `balloon-pow`) are at the same HEAD commit (775d19b) as master. None has diverged with track-specific work. If workers operate in worktrees, they'll need to create feature branches first. The plan doesn't address worktree/branch strategy.

---

## 4. PRIORITY ADJUSTMENTS — What Should Be Re-ordered

### MOVE UP: Full build verification
**Should be Task 1.0, before everything else.** Set `CONFIG_ENABLE_MESH=y` in tracker sdkconfig, run `idf.py build`, and capture the result. This single action tells you whether the "build infrastructure unblock" phase is even needed, or if the components already compile together (they may — ESP-IDF auto-discovers them).

### MOVE UP: secp256k1 measurement (Task 2.2)
This is the highest-value autonomous task. It gates ADR-026 (Schnorr validation strategy), which in turn gates the Nostr and Blossom architecture decisions. It should start immediately in parallel with build verification, as it's completely independent.

### DEFER: Task 3.2 (blossom datagram) and Task 3.3 (nostr persistent storage)
Both need re-scoping against existing code before execution. Don't schedule workers until the scope is corrected.

### DEFER: Task 4.3 (FIPS test crate)
Wrong repository, wrong diagnosis. Must be re-scoped to point at `~/repos/microfips-upstream/` and address the actual toolchain issue.

### KEEP AS-IS: Tasks 3.1, 4.1, 4.2, 5.1, 5.3
These are correctly scoped and ready to execute.

---

## 5. SPECIFIC RECOMMENDATIONS — Actionable Corrections

### REC-1: Corrected Task List

| Original Task | Status | Corrected Action |
|---|---|---|
| 1.1 mesh_adapter CMakeLists | ✅ **ALREADY DONE** | Verify existing file is correct. It links `pipeline`, `erasure`, `frag` — not `fips_transport` + `lr2021_transport` as the plan claims. |
| 1.2 Wire fips into main build | **REFRAME** | The real task: set `CONFIG_ENABLE_MESH=y` in `tracker/firmware/sdkconfig` and run `idf.py build`. Components are auto-discovered via `EXTRA_COMPONENT_DIRS`. |
| 1.3 Blossom partition expansion | **CORRECT NUMBERS** | Current: factory=1MB, blossom=1.5MB. Expand factory to 2MB. Verify total ≤ 4MB after expansion. |
| 2.1 nostr_event_deserialize | ✅ **ALREADY DONE** | Function exists at `nostr_store.c:104`, round-trip test at `test_nostr_store.c:159`. Skip. |
| 2.2 secp256k1 measurement | ✅ **VALID — EXECUTE** | Highest priority. Start immediately. |
| 2.3 Bloom hash fix | ❌ **CANCEL — FALSE PREMISE** | The code is correct. Do not "fix" it. See RISK-4. |
| 3.1 ehash radio → LR2021 | ✅ **VALID — EXECUTE** | Stub genuinely exists. Good task. |
| 3.2 Blossom datagram | ✅ **ALREADY EXISTS** | Component at `tracker/firmware/components/blossom_datagram/` (11KB). Verify it meets needs instead of recreating. |
| 3.3 Nostr persistent storage | **VERIFY FIRST** | `nostr_store.c` already does flash-backed I/O. Determine what's actually missing before writing a new component. |
| 4.1 Tollgate payment tests | ✅ **VALID — EXECUTE** | Good coverage task. |
| 4.2 3-hop relay simulation | ✅ **VALID — EXECUTE** | Valuable integration test. |
| 4.3 FIPS test crate repair | **RESCOPE** | Target: `~/repos/microfips-upstream/`. Actual issue: Rust toolchain version (1.93.1 vs 1.94.0). Fix: `rustup update` or pin embassy. NOT an SPI API rewrite. |
| 5.1 Update assessments | ✅ **VALID — EXECUTE** | |
| 5.2 ADR-026 from Task 2.2 | ✅ **VALID** | Depends on 2.2 completing. |
| 5.3 Git clean | ✅ **VALID — EXECUTE** | |

### REC-2: Add a "baseline build" task as the new Task 1.0
```bash
cd ~/repos/balloon-fresh/tracker/firmware
# Set mesh config
idf.py menuconfig  # or sed/sdkconfig edit: CONFIG_ENABLE_MESH=y
idf.py build 2>&1 | tee build-mesh-baseline.log
# Capture: does it build? Binary size? Any link errors?
```
This should be the very first action. The result determines whether Phase 1 is needed at all.

### REC-3: Consolidate mesh_adapter dependencies
The existing `mesh_adapter/CMakeLists.txt` declares `REQUIRES pipeline` and `PRIV_REQUIRES erasure frag`. It does NOT currently depend on `fips_transport` or `lr2021_transport`. If the mesh adapter needs to bridge to FIPS/LR2021, its dependency list may need updating — but this is a code change, not a "create CMakeLists from scratch" task.

### REC-4: Verify `nostr_store` persistence before Task 3.3
Run the existing nostr_store tests. If they pass with flash-backed storage, Task 3.3 is unnecessary. The component comment says "RAM: ~10 KB" and uses POSIX file I/O — this is already persistent storage.

### REC-5: Fix the FIPS Rust toolchain before any FIPS work
```bash
rustup update stable  # or: rustup install 1.94.0
cd ~/repos/microfips-upstream
cargo test --no-run   # verify it compiles
```
This is a 5-minute fix, not a 1-hour SPI API rewrite.

---

## 6. SIMPLIFICATION OPPORTUNITIES

### SIMP-1: Eliminate 5 redundant tasks
With corrections, the plan drops from 15 tasks to ~10 genuine tasks. The time estimate drops from 9-13 hours to 5-7 hours. Less work, higher confidence.

### SIMP-2: Don't create a new blossom_datagram at a second path
If the existing `tracker/firmware/components/blossom_datagram/` component needs changes (new message types, fragmentation integration), modify it in place. Don't create a parallel implementation at `firmware/blossom-server/`. One component, one path.

### SIMP-3: Don't port wisp-esp32 storage_engine if nostr_store already works
The plan proposes creating `tracker/firmware/components/nostr_persistent/storage_engine.c` adapted from wisp-esp32. But `nostr_store.c` already does flash-backed event storage with bloom-filter dedup, serialization, and file I/O. If it works, use it. If it's missing a feature, add the feature — don't write a new component.

### SIMP-4: The 3-hop relay simulation (Task 4.2) can be simplified
The plan describes a full Python simulation with mock radio links. A simpler approach: since `ehash-bridge` already has a Python stratum server and `ehash-relay` has C unit tests, write the multi-hop test as a chain of existing test harnesses rather than building a new simulation framework.

### SIMP-5: Merge Phase 5 documentation tasks into a single sweep
Tasks 5.1 (assessments), 5.2 (ADR-026), and 5.3 (git clean) are all lightweight. Do them in one pass at the end rather than treating them as separate phases.

---

## 7. VERDICT

### Overall Assessment: **CONDITIONAL GO — with mandatory corrections**

The plan demonstrates good structural thinking (phased approach, clear DoD, dependency ordering) but was clearly written from **stale documentation rather than fresh codebase inspection**. This is evident from the 5 tasks that describe already-completed work and the 1 task that diagnoses a non-existent bug.

**The corrected plan is leaner and more valuable.** After removing redundant tasks, fixing the FIPS crate location/diagnosis, and reframing the build integration around `CONFIG_ENABLE_MESH`, the plan becomes a focused 5-7 hour effort that produces real progress: secp256k1 measurement, ehash radio wiring, payment test coverage, and a clean build baseline.

### Conditions for execution:

1. **DELETE or MARK SKIP on Tasks 1.1, 2.1, 2.3, 3.2** — already done or false premise.
2. **RESCOPE Task 4.3** — point at `~/repos/microfips-upstream/`, fix Rust toolchain, not SPI API.
3. **ADD Task 1.0** — baseline build with `CONFIG_ENABLE_MESH=y` as the first action.
4. **VERIFY Task 3.3** — confirm `nostr_store` doesn't already solve the persistence problem.
5. **ASSIGN real owners** — replace "worker (leaf role)" with existing sub-managers or define the role.

### What Felix should know:
The orchestrator's heart is in the right place, but this plan needs a reality check before execution. The good news: the codebase is more complete than the plan implies — several "blockers" are already resolved. The autonomous work that remains is genuinely valuable and correctly identified. After a 30-minute correction pass, this plan is ready to execute.

---

*This review was produced by verifying every factual claim in the plan against the live repository state. All file paths, function existence, build configurations, and error conditions were checked directly.*
