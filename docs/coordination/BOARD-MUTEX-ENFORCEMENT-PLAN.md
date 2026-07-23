# Board Mutex Enforcement Plan v2

Created: 2026-07-24
Status: ACTIVE — implementing now
Owner: balloon-hermes orchestrator

## Problem Statement

Both speed-tests and range-tests tracks access the same RP2040 boards (/dev/ttyACM0, /dev/ttyACM2) simultaneously despite having a board mutex lock. Two bugs identified:

### Bug 1: TTL-based lock expiry (FIXED in commit 327dd42)
Old lock used 15-minute TTL. Locks expired mid-test, allowing concurrent access.
Fix: Rewrote to flock(2) + sentinel daemon. OS-enforced mutual exclusion.

### Bug 2: Advisory lock bypass (CURRENT — NOT YET FIXED)
flock is advisory on Linux. A process can open /dev/ttyACM0 directly via
pyserial without acquiring the lock. Speed-tests (PID 3883573) did exactly
this — opened serial port directly, never called balloon-board-lock.py.

Root cause: AGENTS.md documentation is not enforcement. Sub-managers can
ignore or not read instructions. Need HARD enforcement layers.

## Evidence (2026-07-24)

```
flock status: range-tests holds TX+RX (sentinels alive, correct)
fuser /dev/ttyACM0: PID 3883573 (speed-tests serial reader, NO lock acquired)
```

Range-tests followed the rules. Speed-tests bypassed them.

## Implementation Plan (5 Layers)

### Layer 1: Mandatory Serial Wrapper
- File: `~/repos/balloon-fresh/tools/board-serial.py`
- Wraps pyserial.Serial() for /dev/ttyACM* ports
- Checks flock held by calling track BEFORE opening port
- Refuses to open if lock not held, prints clear error
- All test scripts MUST use this instead of raw `serial.Serial()`
- Sub-managers update their test scripts to import this

### Layer 2: Pre-Flight Assertion Script
- File: `~/repos/balloon-fresh/tools/board-lock-assert.py`
- Called at top of every test script: `board-lock-assert.py tx rx`
- Exits with error if flock not held by this track
- Lightweight: just checks flock state, no acquire
- Bake into PlatformIO upload scripts and test runners

### Layer 3: Board Access Monitor Cron
- File: `~/.hermes/profiles/manager/scripts/board-access-monitor.sh`
- Runs every 60 seconds via cron
- Checks `fuser /dev/ttyACM*` against flock holders
- Reports violations to balloon-hermes immediately
- Also cleans up orphaned sentinel processes

### Layer 4: AGENTS.md Hard Requirement Update
- Update BOTH worktree AGENTS.md files with:
  - "You MUST use board-serial.py, NOT serial.Serial()"
  - "You MUST call board-lock-assert.py at script start"
  - "Scripts found using raw serial.Serial() are BUGS"
- Add copy of lock script to each worktree's tools/ dir (currently missing)

### Layer 5: Gateway Restart + Sub-Manager Notification
- Restart Hermes gateway to regenerate channel_directory.json
- Send status requests to both speed-tests and range-tests Signal groups
- Collect reports on what happened
- Verify both sub-managers understand the lock system

## Execution Order

1. Write this plan doc ← DONE
2. Implement Layer 1: board-serial.py wrapper ← DONE
3. Implement Layer 2: board-lock-assert.py ← DONE
4. Implement Layer 3: board-access-monitor.sh + cron ← DONE (cron b6df723690d7)
5. Implement Layer 4: Update AGENTS.md files ← DONE
6. Restart gateway, notify sub-managers ← GATEWAY RESTARTING (02:55), then send messages
7. Commit + push all changes ← DONE (4e4956b, d7bfc78, 171387d)
8. Verify with live test ← PENDING (after gateway restart)

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| tools/board-serial.py | CREATE | Serial wrapper with lock check |
| tools/board-lock-assert.py | CREATE | Pre-flight lock assertion |
| scripts/board-access-monitor.sh | CREATE | Cron violation detector |
| balloon-speed-tests/AGENTS.md | PATCH | Add mandatory wrapper usage |
| balloon-range-tests/AGENTS.md | PATCH | Add mandatory wrapper usage |
| balloon-speed-tests/tools/ | CREATE | Copy lock+wrapper tools locally |
| balloon-range-tests/tools/ | CREATE | Copy lock+wrapper tools locally |

## Success Criteria

- [ ] board-serial.py refuses to open port without lock
- [ ] board-lock-assert.py exits non-zero without lock
- [ ] Monitor cron detects violations within 60s
- [ ] Both AGENTS.md updated with wrapper requirement
- [ ] Both sub-managers notified and acknowledge
- [ ] All changes committed + pushed to ngit
- [ ] Live test: one track acquires lock, other track's wrapper refuses
