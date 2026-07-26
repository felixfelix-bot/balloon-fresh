# Balloon-Fresh Master Consolidation Plan

**Status:** AWAITING FELIX APPROVAL  
**Date:** 2026-07-26  
**Author:** Orchestrator (balloon-hermes)

---

## 1. CURRENT STATE

### Branches with firmware/code (4 active):

| Branch | Commit | What's Unique | Already in master? |
|--------|--------|---------------|-------------------|
| **master** | 9550c2d | BASE — V4 firmware, make targets, pytest, rx_capture, ADRs 17-20 | — |
| **speed-sustained-sweep** | 5ae1d8a | Board lock (udev+pio guard), 20s guard band, FLRC RSSI analysis | NO — needs cherry-pick |
| **github/main** | 4566437 | ms-precision phase fix, CRC overread guard, channel sweep (7HF+5LF), CR=3/4 | NO — needs rebase+merge |
| **phase1-interop-test** | a6ce19c | ESP32 raw SPI firmware, 2.4GHz fix | NO — separate platform, keep as-is |

### Branches with docs only (3):

| Branch | Status | Action |
|--------|--------|--------|
| track/range-testing | docs only | Archive — plans absorbed into master |
| track/speed-testing | docs only | Archive — plans absorbed into master |
| balloon-pre-stretching | docs only | Archive — no code |

### Branches with hardware (1):

| Branch | Status | Action |
|--------|--------|--------|
| balloon-circuit-design | SKiDL schematics | Keep as feature branch — merge when ready |

---

## 2. BUG FIX INVENTORY — WHAT GOES WHERE

### Fixes from speed-sustained-sweep NOT YET in master:

| Fix | Commit | Critical? | Already in V4? | Action |
|-----|--------|-----------|-----------------|--------|
| Board lock chmod enforcement | 99b94ca | YES | NO | Cherry-pick to master |
| pio upload guard shim | ef60a51 | YES | NO | Cherry-pick to master |
| udev rules for port perms | 068f7b8 | YES | NO | Cherry-pick to master |
| 20s LoRa guard band | 3d5ffd4 | MEDIUM | PARTIAL (V4 has 20000ms for LF-LoRa only) | Verify + merge if needed |
| STANDBY re-arm sequence | 9d7f2ce | LOW | YES (V4 has SET_STANDBY abort) | Already in V4 |
| FLRC RSSI 9-bit | c4aa1ff | LOW | YES (V4 has correct 9-bit formula) | Already in V4 |

### Fixes from github/main NOT YET in master:

| Fix | Commit | Critical? | Action |
|-----|--------|-----------|--------|
| ms-precision phase computation | e303327 | YES | Merge via rebase |
| CRC buffer overread guard | 1fc9a72 | CRITICAL | Merge via rebase |
| Phase-sync from TX packets | 1fc9a72 | MEDIUM | Merge via rebase |
| Channel sweep (7HF + 5LF) | 0562e73 | FEATURE | Merge via rebase |
| Dynamic transition guard + CR=3/4 | 0a9fa51 | MEDIUM | Merge via rebase |

---

## 3. CONSOLIDATION ORDER (CRITICAL — sequential, not parallel)

```
Phase 1: speed-sustained-sweep fixes → master
         (cherry-pick board lock + udev + pio guard)
         ↓
Phase 2: github/main features → master
         (rebase main onto master, resolve conflicts, merge)
         ↓
Phase 3: Verify consolidated master
         (build both targets, run pytest, sub-manager consensus)
         ↓
Phase 4: Clean up branches
         (archive doc-only, keep circuit-design + phase1-interop)
         ↓
Phase 5: Push + Felix laptop verification
```

### Why this order:
- Phase 1 first: board lock + udev rules are infrastructure, no conflicts with firmware
- Phase 2 second: github/main has firmware changes that may conflict — needs careful rebase
- Phase 3: full verification before declaring done
- Phase 4: cleanup after verification
- Phase 5: Felix pulls and tests on laptop

---

## 4. SUB-MANAGER ROLES AND HANDOVER PROMPTS

### Sub-Manager 1: balloon-range-tests
**Role:** Infrastructure extraction from speed-sustained-sweep

**Handover prompt:**
> You are extracting infrastructure from the speed-sustained-sweep branch and merging into master. Your worktree is ~/worktrees/balloon-range-tests.
>
> TASKS (in order):
> 1. Identify the exact files from these commits on speed-sustained-sweep:
>    - 99b94ca (board lock chmod enforcement)
>    - ef60a51 (pio upload guard shim)
>    - 068f7b8 (udev rules)
> 2. Cherry-pick or manually copy these files to a new branch `consolidation-infra` based on master
> 3. Verify the files are complete and functional
> 4. Build both V4 firmware targets to confirm nothing broke
> 5. Run pytest to confirm 14 tests still pass
> 6. Commit + push to consolidation-infra branch
>
> QUALITY GATES:
> - Gate 1: `pio run -e rp2040-sweep-tx-v4` succeeds
> - Gate 2: `pio run -e rp2040-sweep-rx-v4` succeeds
> - Gate 3: `make test-unit` passes (14 tests)
> - Gate 4: udev rules file exists and references correct board serials
> - Gate 5: pio_upload_guard.py imports cleanly
> - Gate 6: Committed + pushed to GitHub
>
> DELEGATE the mechanical work (file copying, build runs) to worker-balloon via kanban. You are a MANAGER, not a worker. Do NOT read firmware line-by-line yourself.
>
> REPORT BACK: list of files cherry-picked, build output, test output, branch name + commit hash.

### Sub-Manager 2: balloon-speed-tests  
**Role:** Firmware audit — verify speed-sweep bug fixes are in V4

**Handover prompt:**
> You are auditing the V4 firmware on master to confirm that critical speed-sweep bug fixes have been carried forward. Your worktree is ~/worktrees/balloon-speed-tests.
>
> TASKS:
> 1. Compare these specific fixes between speed-sustained-sweep and master's V4 firmware:
>    a. FLRC RSSI 9-bit assembly (speed commit c4aa1ff) — is it in multi_radio_sweep_rx_v4.cpp?
>    b. STANDBY re-arm sequence (speed commit 9d7f2ce) — is it in V4?
>    c. FIFO-before-RSSI order (speed commit 9d7f2ce) — is it in V4?
>    d. 20s guard band for LoRa (speed commit 3d5ffd4) — is it in V4?
>    e. 4-byte sync header (speed commit dae34c4) — is it in V4?
> 2. For EACH fix: report VERIFIED or MISSING with specific line numbers from V4 source
> 3. If any are MISSING: create a task to cherry-pick the missing fix
>
> QUALITY GATES:
> - Gate 1: Every fix audited with evidence (file + line numbers)
> - Gate 2: Any missing fix identified with exact commit to cherry-pick
> - Gate 3: Report reviewed by orchestrator
>
> DELEGATE the file reading and diffing to worker-balloon via kanban. You are a MANAGER. Do NOT read firmware yourself.
>
> REPORT BACK: table of fix name | in V4? | evidence | action needed

### Sub-Manager 3: NEW (consolidation-main)
**Role:** Rebase github/main features onto consolidated master

**Handover prompt:**
> You are merging the github/main branch's unique features into the consolidated master. This happens AFTER the infrastructure phase is complete.
>
> WAIT FOR: Orchestrator signal that Phase 1 (infrastructure) is done and master is updated.
>
> TASKS:
> 1. Create branch `consolidation-main-rebase` from master
> 2. Identify unique commits on github/main NOT in master:
>    - e303327 (ms-precision phase computation)
>    - 1fc9a72 (CRC buffer overread guard + phase-sync from TX packets)
>    - 0562e73 (channel sweep 7HF + 5LF)
>    - 0a9fa51 (dynamic transition guard + CR=3/4)
> 3. Cherry-pick each commit onto consolidation-main-rebase
> 4. Resolve conflicts CAREFULLY — V4 firmware is canonical for sweep logic
> 5. If a fix conflicts with V4, prefer the V4 version UNLESS the fix addresses a V4 bug
> 6. Build both V4 targets after each cherry-pick
> 7. Run pytest after all cherry-picks
> 8. Commit + push consolidation-main-rebase
>
> QUALITY GATES:
> - Gate 1: Each cherry-pick builds clean (pio run -e rp2040-sweep-tx-v4)
> - Gate 2: pytest still passes (14+ tests)
> - Gate 3: No regression in existing V4 features (GPS fix-gate, interleave, CRC24)
> - Gate 4: ms-precision phase computation verified by unit test
> - Gate 5: CRC overread guard verified by unit test
> - Gate 6: Committed + pushed
>
> DELEGATE mechanical work to worker-balloon. You are a MANAGER.
>
> REPORT BACK: list of cherry-picks applied, conflicts resolved (with rationale), build output, test output.

### Sub-Manager 4: balloon-range-tests (Phase 3 verification)
**Role:** Final consensus verification

**Handover prompt:**
> You are performing the final verification of the consolidated master branch. This happens AFTER Phase 1 and Phase 2 are complete.
>
> WAIT FOR: Orchestrator signal that all consolidation is done.
>
> TASKS:
> 1. Pull latest master
> 2. Clean build: `pio run -t clean && pio run -e rp2040-sweep-tx-v4 && pio run -e rp2040-sweep-rx-v4`
> 3. Run full pytest suite: `make test-unit`
> 4. Verify make targets: `make ports`, `make find-tx`, `make find-rx`
> 5. Verify platformio.ini [env] section has earlephilhower core
> 6. Verify udev rules present in tools/
> 7. Verify pio_upload_guard.py present and importable
> 8. Verify rx_capture.py present and runs
> 9. Write CONSENSUS REPORT: approve or reject with list of issues
>
> QUALITY GATES:
> - Gate 1: Clean build of both targets from scratch
> - Gate 2: All pytest tests pass
> - Gate 3: All make targets functional
> - Gate 4: All infrastructure files present and importable
> - Gate 5: Sub-manager consensus (all 3 sub-managers approve)
>
> DELEGATE to worker-balloon for build/test runs. You are a MANAGER.
>
> REPORT BACK: CONSENSUS APPROVED or CONSENSUS REJECTED with issue list.

---

## 5. QUALITY GATES (ALL PHASES)

Every sub-manager MUST pass all 6 gates before reporting completion:

1. **BUILD**: `pio run -e rp2040-sweep-tx-v4` AND `pio run -e rp2040-sweep-rx-v4` both succeed
2. **TEST**: `make test-unit` passes (14+ tests)
3. **DOCS**: Any architectural change documented in ADR or commit message
4. **COMMIT**: Atomic commits with conventional messages
5. **PUSH**: `git push` succeeded, remote verified
6. **CONSENSUS**: Other sub-managers can review and approve

---

## 6. COLLABORATION PROTOCOL

- Orchestrator creates tasks and assigns to sub-managers
- Sub-managers delegate mechanical work to worker-balloon via kanban
- Sub-managers report back summaries (not raw output)
- Orchestrator reviews, decides go/no-go for each phase
- Phase transitions ONLY happen after orchestrator approval
- Cross-phase dependencies: Phase 2 waits for Phase 1, Phase 3 waits for Phase 2

---

## 7. TIMELINE

| Phase | Duration | Dependency |
|-------|----------|------------|
| Phase 1: Infrastructure cherry-pick | 15 min | None |
| Phase 2: Main rebase | 30 min | Phase 1 done |
| Phase 3: Verification | 15 min | Phase 2 done |
| Phase 4: Cleanup | 5 min | Phase 3 approved |
| Phase 5: Felix laptop test | 10 min | Phase 4 done |

Total: ~75 minutes if no blockers.
