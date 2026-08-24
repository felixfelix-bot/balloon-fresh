# Branch Consolidation — Execution Plan with Handover Prompts
# Date: 2026-07-26
# Status: AWAITING FELIX APPROVAL — do NOT execute until approved

## GOAL
One clean master branch with ALL bug fixes from ALL branches.
Buildable on Felix's laptop with `make` targets. All sub-managers sign off.

---

## EXECUTION ORDER (critical — rebasing depends on this)

```
Step 1: Orchestrator finalizes merge (range-tests → master)
         ↓
Step 2: Orchestrator builds + tests on DQ05 (verifies clean compile)
         ↓
Step 3: Orchestrator pushes consolidated master to github
         ↓
Step 4: Sub-managers pull new master, review their domain's fixes
         (PARALLEL — range-tests + speed-tests review simultaneously)
         ↓
Step 5: Sub-managers report: APPROVED or MISSING_FIX_X
         ↓
Step 6: If missing fixes → port them, re-push, re-review
         If all approved → Step 7
         ↓
Step 7: Orchestrator tags v5.0-consolidated
         ↓
Step 8: Sub-managers rebase their feature branches onto new master
         (AFTER master is frozen — not before)
```

WHY THIS ORDER:
- Master must be frozen BEFORE sub-managers rebase
- Build verification happens BEFORE sub-manager review (so they review working code)
- Parallel review (range-tests + speed-tests at same time) saves time
- If fixes are missing, we loop back to Step 1 before tagging

---

## ROLES AND RESPONSIBILITIES

### Orchestrator (me — balloon-hermes)
- Owns the merge operation and git choreography
- Owns the Makefile combination
- Owns platformio.ini verification
- Owns build + test verification on DQ05
- Owns tagging and final push
- CANNOT modify firmware logic (that's sub-manager domain)
- CANNOT skip quality gates

### range-tests sub-manager
- Owns: TX firmware correctness, phase sync, GPS integration
- Reviews: all TX firmware changes in consolidated master
- Verifies: their TX bug fixes are present and intact
- Authority: can REQUEST changes to TX firmware, cannot merge themselves
- Must delegate actual code review to workers

### speed-tests sub-manager
- Owns: RX firmware correctness, RSSI, throughput measurement
- Reviews: all RX firmware changes in consolidated master
- Verifies: their RSSI/timing fixes are present and intact
- Authority: can REQUEST changes to RX firmware, cannot merge themselves
- Must delegate actual code review to workers

### Quality Gates (ALL must pass before tag)
1. Clean build: `make build-all` exits 0
2. Unit tests: `make test-unit` — all pass
3. TX firmware review: range-tests signs off
4. RX firmware review: speed-tests signs off
5. No regression: key functions match registry classifications
6. Push verified: `git push github master` exits 0

---

## HANDOVER PROMPTS

### PROMPT 1: range-tests sub-manager

Send to: signal:balloon-range-tests

```
CONSOLIDATION REVIEW — range-tests track

CONTEXT:
We're consolidating all balloon-fresh branches into one clean master.
The merge is DONE — range-tests has been merged into master with zero
conflicts. The BUG-FIX-REGISTRY.md (docs/plans/BUG-FIX-REGISTRY.md)
documents every functional difference between branches.

Key findings from the registry:
- range-tests was the most complete branch (28 fixes not in old master)
- Your TX firmware is the consolidation base
- speed-sustained-sweep fixes (GPS baud, RSSI 9-bit) were already in V4
- 5 conflicts resolved — all firmware uses range-tests version

YOUR TASK:
Review the consolidated master and confirm your TX firmware fixes are
intact. Specifically verify these fixes survived the merge:

1. FLRC CRC24 + Match123 packet params (7f5e2bd)
2. FLRC sync word 32-bit (85793c2)
3. GPS baud 115200 (c6fd9e9 from speed-sweep, already in V4)
4. GPS pins GP0/GP1 (5a3b70e from speed-sweep, already in V4)
5. TX autonomous operation + GPS time hold (25dac1b)
6. CDC watchdog guard (3efdebe)
7. Dynamic phase-transition guard (500ms/1000ms)
8. abortTxIfActive() before phase reconfig
9. TX spin timeout 6s → 16s (for LF SF12)
10. totalCycleMs ms-precision phase computation (e303327)

HOW TO REVIEW:
1. Pull the consolidated master: git pull
2. Read firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp
3. For each fix above, grep for the relevant code pattern
4. Report FOUND or MISSING for each

QUALITY GATES YOU MUST ENFORCE:
- Do NOT modify firmware yourself — review only
- If a fix is missing, REPORT IT to me (orchestrator) with the exact
  function name and expected behavior
- Delegate the actual code reading to a worker (you are a manager)
- Your sign-off means: "I confirm all my track's TX fixes are present"

EXECUTION:
- This is a REVIEW task, not a build task
- Use BALLOON_TRACK=range-tests for any board access
- Do NOT rebase your branch yet — wait until master is tagged
- Report back to balloon-hermes group with: APPROVED or MISSING_FIXES

DEADLINE: Respond within this session. This blocks the consolidation tag.
```

### PROMPT 2: speed-tests sub-manager

Send to: signal:balloon-speed-tests

```
CONSOLIDATION REVIEW — speed-tests track

CONTEXT:
We're consolidating all balloon-fresh branches into one clean master.
The merge is DONE — range-tests (which contains your speed-sweep fixes)
has been merged into master. The BUG-FIX-REGISTRY.md
(docs/plans/BUG-FIX-REGISTRY.md) documents every functional difference.

Key findings:
- Your speed-sustained-sweep branch used OLD firmware format (pre-V4)
- ALL your critical fixes were already ported to V4 on range-tests:
  - GPS baud 9600→115200 ✅
  - GPS pins GP20/GP21→GP0/GP1 ✅
  - RSSI 9-bit assembly ✅
  - NMEA u-blox M10 prefix ✅
  - FLRC RSSI formula (remove <<1) ✅
  - FLRC GPS extraction offset ✅
- These are now in master via the range-tests merge

YOUR TASK:
Review the consolidated master and confirm your RX firmware fixes are
intact. Specifically verify these fixes survived the merge:

1. FLRC RSSI: uses 9-bit value (buf[4]<<1 | buf[6] bit[2]) — NOT the
   old <<1 doubling bug
2. LoRa RSSI: uses buf[2] (not buf[4])
3. FLRC GPS extraction: offset 0 for FLRC (hardware strips sync word)
4. NMEA parser: handles u-blox M10 native prefix ($GNGGA vs $GPGGA)
5. GPS baud: 115200 in #define GPS_BAUD
6. STANDBY re-arm sequence: FIFO cleared before RSSI read
7. 4-byte sync header handling
8. Phase-ID validation: does NOT reject all packets (old bug 12ab544)

HOW TO REVIEW:
1. Pull consolidated master: git pull
2. Read firmware/rp2040/src/multi_radio_sweep_rx_v4.cpp
3. For each fix above, grep for the relevant code pattern
4. Report FOUND or MISSING for each

ALSO CHECK:
- The RX firmware uses ms-precision phase computation (totalCycleMs)
- totalCycleSec reset before accumulate in SET_TIME handler
- Interleave mode default ON
- Buffer size rxBuf[264] (not 256 — room for chip framing)

QUALITY GATES YOU MUST ENFORCE:
- Do NOT modify firmware yourself — review only
- If a fix is missing, REPORT IT to me with exact function + expected behavior
- Delegate the actual code reading to a worker
- Your sign-off means: "I confirm all my track's RX fixes are present"

EXECUTION:
- REVIEW task only — no builds, no board access needed
- Do NOT rebase speed-sustained-sweep yet — wait until master is tagged
- Report back to balloon-hermes group with: APPROVED or MISSING_FIXES

DEADLINE: Respond within this session. This blocks the consolidation tag.
```

### PROMPT 3 (conditional — only if sub-managers find missing fixes)

```
FIX REQUEST — [track-name]

A missing fix was identified during consolidation review:
[fix description]
[expected behavior]
[current behavior]
[file and function location]

YOUR TASK:
Create a worker task to port this fix into the consolidated master.
The fix must:
1. Be applied to firmware/rp2040/src/[file]
2. Not break any existing functionality
3. Pass: cd ~/repos/balloon-fresh && make test-unit
4. Be committed with conventional message: "fix: [description]"
5. Be pushed to master

QUALITY GATES:
- Worker must verify the fix compiles: make build-[tx|rx]
- Worker must verify unit tests pass: make test-unit
- Worker must NOT touch unrelated code
- Report back with commit hash

DO NOT rebase your branch. Work directly on master via worktree.
```

---

## WHAT HAPPENS AFTER APPROVAL

1. I commit the merge (already staged)
2. I build both firmware envs on DQ05
3. I run unit tests
4. If build+test pass → I push to github
5. I send PROMPT 1 + PROMPT 2 to sub-managers (parallel)
6. Wait for both responses
7. If both APPROVED → tag v5.0-consolidated
8. If MISSING_FIXES → dispatch PROMPT 3, loop back
9. After tag → sub-managers rebase their branches
10. Old branches (main, speed-sustained-sweep) get deleted

## WHAT I WILL NOT DO

- Will NOT dispatch anything until Felix approves
- Will NOT modify firmware logic (sub-manager domain)
- Will NOT skip quality gates
- Will NOT delete branches until consolidation is verified
- Will NOT tag until both sub-managers sign off
