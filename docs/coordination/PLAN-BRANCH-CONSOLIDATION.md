# Plan: Branch Consolidation — Merge Active Branches to Master

**Status:** DRAFT — awaiting sub-manager input, then Felix approval
**Created:** 2026-07-30
**Author:** Orchestrator (balloon-hermes)

## Purpose

All 9 balloon sub-managers now work on branches in the same repo (felixfelix-bot/balloon-fresh). This is major coordination progress — branches can build on each other's work. But branches are diverging. This plan sequences merges to master so sub-managers can rebase and pick up each other's completed work.

## Current Branch State

| Branch | Ahead | Behind | Conflicts | Domain | Worktree |
|--------|-------|--------|-----------|--------|----------|
| balloon-nostr-extract | 2 | 0 | 0 | nostr_store component | balloon-nostr-fresh |
| balloon-fips-extract | 17 | 42 | 0 | lr2021_transport + fips_radio_bridge | balloon-fips-fresh |
| balloon-tollgate-extract | 26 | 18 | 0 | mesh-stack/tollgate/ | balloon-tollgate-fresh |
| balloon-circuit-design | 16 | 18 | 0 | tracker/hardware/ (PCB) | balloon-circuit-design |
| balloon-pow-e-hash | 9 | 18 | 0 | mesh-stack/ehash-*/ | (no worktree) |
| pre-stretching | 8 | 7 | 0 | tools/balloon_pressure_test/ | balloon-pre-stretching |
| range-tests | 6 | 18 | 0 | data/walk-tests/ + LED firmware | balloon-fresh (range-tests branch) |
| rf-tests | 31 | 18 | 0 | captures/ + LA + ESP32 cont-TX | balloon-fresh (rf-tests branch) |
| blossom-server | 0 | 13 | 0 | ALREADY MERGED — delete | balloon-blossom-fresh |
| balloon-blossom-extract | 0 | 0 | 0 | STALE SNAPSHOT — delete | (no worktree) |

**Key finding:** Zero merge conflicts across all branches. Each branch works on different parts of the codebase. The "blossom-server files" appearing in multiple branch diffs is a phantom — those branches diverged before blossom was merged to master.

## Pre-Merge Safety Protocol

Before ANY merge begins, the worker MUST verify:

1. **Sub-manager idle check** — Query each sub-manager via Signal or session_search to confirm they are not actively committing/working. Look for:
   - No uncommitted changes in their worktree (`git status --short` in each worktree)
   - No in-progress kanban tasks that touch shared files
   - Sub-manager has pushed all work to their branch on github
2. **Working tree clean** — `git status` shows clean in the worktree for the branch being merged
3. **Branch is pushed** — Local branch matches remote (`git log origin/<branch>..<branch>` is empty)
4. **No active builds/flashes** — No `idf.py build` or `pio run` running in any worktree

If any sub-manager is actively working, PAUSE that merge step until they confirm they've committed and pushed.

## Merge Sequence (Dependency-Driven)

### Phase 0: Cleanup (no dependency)

**Worker:** glm-5.2 leaf
**Quality gates:** Verify branches deleted on both github and local

Delete stale branches:
- `blossom-server` (already merged to master, 0 ahead)
- `balloon-blossom-extract` (stale snapshot, 0 unique commits)

```bash
cd ~/repos/balloon-fresh
git branch -d blossom-server
git branch -d balloon-blossom-extract
git push github --delete blossom-server
git push github --delete balloon-blossom-extract
```

Remove old worktree:
```bash
git worktree remove ~/worktrees/balloon-blossom 2>/dev/null || true
```

### Phase 1: Merge balloon-nostr-extract (no dependency, trivial)

**Worker:** glm-5.2 leaf
**Pre-check:** Confirm balloon-nostr sub-manager is idle (no active commits)
**Quality gates:**
- `git merge --no-ff` preserves branch history
- `idf.py build` PASS after merge (if nostr_store compiles)
- `git push github master` succeeds
- Post-merge: verify `git log --oneline master -3` shows nostr commits

```bash
cd ~/repos/balloon-fresh
git checkout master
git pull github master
git merge --no-ff balloon-nostr-extract -m "merge: consolidate balloon-nostr-extract into master — flash-backed nostr_store"
git push github master
```

### Phase 2: Rebase + Merge balloon-fips-extract (foundation layer)

**Worker:** glm-5.2 leaf
**Pre-check:** Confirm balloon-fips sub-manager is idle. This is the most diverged branch (42 behind) but 0 conflicts.
**Quality gates:**
- Rebase completes with 0 conflicts
- `idf.py build` PASS after rebase (lr2021_transport + fips_radio_bridge compile)
- All fips tests pass: `cd tracker/firmware && idf.py build` (or host tests)
- `git push github balloon-fips-extract --force-with-lease` succeeds (rebase rewrites history)
- Merge to master: `git merge --no-ff` 
- `git push github master` succeeds
- Post-merge: verify lr2021_transport/ and fips_radio_bridge/ directories exist on master

**CRITICAL:** This is the foundation. Once lr2021_transport is on master, tollgate, nostr, and blossom can import it. This unblocks the most downstream work.

```bash
cd ~/worktrees/balloon-fips-fresh
git fetch origin
git rebase origin/master
# Resolve any conflicts (expected: 0 per analysis)
# Run build verification
source ~/esp/esp-idf/export.sh
cd tracker/firmware && idf.py build
git push github balloon-fips-extract --force-with-lease

# Merge to master
cd ~/repos/balloon-fresh
git checkout master
git pull github master
git merge --no-ff balloon-fips-extract -m "merge: consolidate balloon-fips-extract into master — lr2021_transport + fips_radio_bridge + ADR-026"
git push github master
```

### Phase 3: Merge balloon-tollgate-extract (depends on Phase 2)

**Worker:** glm-5.2 leaf
**Pre-check:** Confirm balloon-tollgate sub-manager is idle
**Quality gates:**
- Rebase onto updated master (with fips transport now available)
- `idf.py build` PASS for tollgate C3 project
- Tollgate unit tests pass: `cd mesh-stack/tollgate/tests/unit && make`
- `git push github balloon-tollgate-extract --force-with-lease` succeeds
- Merge to master succeeds
- Post-merge: verify mesh_service_mux/ exists on master

```bash
cd ~/worktrees/balloon-tollgate-fresh
git fetch origin
git rebase origin/master
# Build verification
source ~/esp/esp-idf/export.sh
cd mesh-stack/tollgate && idf.py build
# Unit tests
cd tests/unit && make
git push github balloon-tollgate-extract --force-with-lease

cd ~/repos/balloon-fresh
git checkout master
git pull github master
git merge --no-ff balloon-tollgate-extract -m "merge: consolidate balloon-tollgate-extract into master — mesh_service_mux + tollgate_client + unit tests"
git push github master
```

### Phase 4: Merge rf-tests + range-tests (firmware fixes, shared data/)

**Worker:** glm-5.2 leaf
**Pre-check:** Confirm range-tests AND rf-tests sub-managers are idle. These two share data/ files.
**Quality gates:**
- Merge rf-tests first (has firmware fixes: single-CS SPI, SET_TX_PATH — needed by all)
- Rebase range-tests onto updated master (after rf-tests merge)
- Build verification for any firmware touched
- Both pushes succeed
- Post-merge: verify captures/ and data/walk-tests/ exist on master

```bash
# 4a: Merge rf-tests
cd ~/repos/balloon-fresh
git checkout master
git pull github master
git merge --no-ff rf-tests -m "merge: consolidate rf-tests into master — LA captures, payload sweeps, ESP32 cont-TX, SPI fixes"
git push github master

# 4b: Rebase + merge range-tests
cd ~/repos/balloon-fresh  # or the range-tests worktree
git checkout range-tests
git fetch origin
git rebase origin/master
git push github range-tests --force-with-lease

cd ~/repos/balloon-fresh
git checkout master
git merge --no-ff range-tests -m "merge: consolidate range-tests into master — walk test data, LED fixes, GPS restore"
git push github master
```

### Phase 5: Merge balloon-circuit-design (after F33 fix complete)

**Worker:** glm-5.2 leaf
**Pre-check:** F33 shorts fix (PLAN-F33-SHORTS-FIX.md) is COMPLETE. Both boards DRC clean. Gerbers regenerated.
**Quality gates:**
- DRC reports show 0 shorting_items, 0 clearance violations for BOTH boards
- Router test suite passes: `cd tracker/hardware && python -m pytest test_router.py`
- `ruff check tracker/hardware/` passes
- Merge succeeds
- Post-merge: verify router.py, gen_pcb.py, .kicad_pcb files exist on master

**DO NOT MERGE if F33 still has electrical shorts.** Wait for circuit-design sub-manager to confirm fix complete.

```bash
cd ~/repos/balloon-fresh
git checkout master
git pull github master
git merge --no-ff balloon-circuit-design -m "merge: consolidate balloon-circuit-design into master — Router class, PCB files, Gerbers, DRC reports"
git push github master
```

### Phase 6: Merge pre-stretching + balloon-pow-e-hash (independent, low priority)

**Worker:** glm-4.5-flash leaf
**Pre-check:** Confirm both sub-managers idle
**Quality gates:**
- Pre-stretching: pressure test rig firmware builds
- E-hash: ehash codec tests pass
- Both merges succeed

```bash
# 6a: pre-stretching
cd ~/repos/balloon-fresh
git checkout master
git pull github master
git merge --no-ff pre-stretching -m "merge: consolidate pre-stretching into master — pressure test rig + protocol docs"
git push github master

# 6b: balloon-pow-e-hash
git checkout master
git pull github master
git merge --no-ff balloon-pow-e-hash -m "merge: consolidate balloon-pow-e-hash into master — e-hash relay + stratum bridge"
git push github master
```

### Phase 7: Post-Merge Rebase Notification

After each phase completes, notify ALL sub-managers via Signal:

```
ORCHESTRATOR: Master updated. Branch <name> merged. All sub-managers: rebase your branch onto master to pick up new code.
  cd ~/worktrees/<your-worktree>
  git fetch origin
  git rebase origin/master
  git push github <your-branch> --force-with-lease
```

Sub-managers who are mid-task should finish their current commit, push, then rebase.

## Worker Assignment

| Phase | Worker Model | Est. Time | Can Parallel? |
|-------|-------------|-----------|---------------|
| 0 (cleanup) | glm-4.5-flash | 2 min | Yes (with Phase 1 pre-check) |
| 1 (nostr) | glm-5.2 | 5 min | After Phase 0 |
| 2 (fips) | glm-5.2 | 15 min | After Phase 1 (rebase + build) |
| 3 (tollgate) | glm-5.2 | 10 min | After Phase 2 |
| 4 (rf+range) | glm-5.2 | 15 min | After Phase 3 |
| 5 (circuit) | glm-5.2 | 5 min | After F33 fix complete (can defer) |
| 6 (pre-stretch+ehash) | glm-4.5-flash | 5 min | After Phase 4 (or independent) |
| 7 (notification) | orchestrator | 2 min | After each phase |

**Total est. time:** ~60 min sequential, ~40 min if phases 5+6 deferred.

## Risk Mitigation

1. **Force-push safety:** All rebases use `--force-with-lease` (rejects if remote moved)
2. **Build verification:** Every phase that touches firmware requires `idf.py build` PASS before merge
3. **Rollback plan:** If a merge breaks master: `git revert -m 1 <merge-commit>` then `git push github master`
4. **Sub-manager coordination:** Each phase waits for sub-manager confirmation that they're idle
5. **No parallel merges:** Phases are sequential to avoid master race conditions

## Open Questions for Sub-Managers

1. **balloon-fips:** Are you actively working on Phase 2 (RadioLib replacement)? If so, should we wait for that to complete before rebasing+merging, or merge current state first?
2. **balloon-tollgate:** Any uncommitted work in your worktree?
3. **balloon-circuit-design:** Is F33 fix in progress? Should we merge current state (with F33 broken) or wait for fix?
4. **range-tests / rf-tests:** Any active captures or builds running?
5. **pre-stretching:** Any active work?
6. **balloon-pow-e-hash:** Any active work?

## Approval Gate

This plan requires Felix's explicit approval before execution begins. No merges will be scheduled until approved.