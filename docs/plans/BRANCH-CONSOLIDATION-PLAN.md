# Branch Consolidation Plan — balloon-fresh

## Date: 2026-07-26
## Status: ACTIVE — approved by Felix

## Goal
Consolidate all bug fixes from all branches into a single clean master branch.
Result: one buildable, testable, well-documented firmware that works with
`make` targets on Felix's laptop.

## Branch Analysis Summary

### Branch Priority (by completeness)

| Branch | TX LoC | RX LoC | Role | Unique Value |
|--------|--------|--------|------|--------------|
| range-tests | 1395 | 1193 | **BASE** — most complete | Everything (see below) |
| main | 1346 | 1198 | Ancestor of range-tests | Nothing unique (subset) |
| master | 1146 | 1069 | Newer fixes post-divergence | ADR-021 UTC sync, RMC parsing, boot gate removal |
| speed-sustained-sweep | N/A | N/A | OLD format (pre-V4) | Fixes already ported to range-tests |
| speed-optimization | N/A | N/A | Single-batch SPI 1733kbps | Performance only, separate concern |

### Key Finding: range-tests ⊇ main ⊇ speed-sustained-sweep fixes

range-tests ALREADY CONTAINS:
- ✅ GPS baud 115200 (from speed-sustained-sweep)
- ✅ GPS pins GP0/GP1 (from speed-sustained-sweep)
- ✅ RSSI 9-bit assembly (from speed-sustained-sweep)
- ✅ NMEA u-blox M10 prefix (from speed-sustained-sweep)
- ✅ FLRC CRC24 + sync word fixes
- ✅ FLRC byte alignment fix
- ✅ All main branch fixes (main is pure ancestor)
- ✅ totalCycleSec reset (own implementation, recompute variant)
- ✅ Interleave mode default ON
- ✅ Board lock system + udev rules
- ✅ pytest framework (14 tests)
- ✅ Make targets + flash scripts
- ✅ Walk capture data (93% decode)
- ✅ GPS fix-gate (ADR-018)
- ✅ TX autonomy (GPS time hold, WAIT_GPS state)

### What master has that range-tests DOESN'T (the gap)

These are commits made to master AFTER range-tests diverged:

**BUG FIXES (must cherry-pick):**
1. `dce248f` — totalCycleSec accumulates on EVERY SET_TIME (not just interleave toggle)
2. `0880443` — RMC time parsing independent of GPS fix (parses time even without position lock)
3. `2752fa1` — TX starts sweeping in 5s, no 60s GPS gate + periodic beacon
4. `1174659` — RX interleave mode default ON (may already exist, verify)

**ARCHITECTURE (ADR conflict — needs resolution):**
5. `9737c5c` — ADR-021: absolute UTC phase sync, no boot-time GPS gate
   CONFLICTS with ADR-018 (range-tests): unconditional GPS fix-gate
   - ADR-018: TX never transmits without GPS fix
   - ADR-021: TX starts immediately, GPS optional
   - RESOLUTION: Make GPS gate configurable. Default ON for range tests (ADR-018),
     configurable OFF for bench testing (ADR-021). Both ADRs coexist.

**TOOLS (useful, cherry-pick):**
6. `2f9e5a9` — overnight stability monitor script
7. `003f666` — overnight monitor v3 (auto-detect RX port)
8. `e44d533` — walk capture script (RX-only, laptop clock sync)
9. `1ba7b9c` — Make targets, pytest fixtures, ADR-022/023

**DATA (skip — don't bloat master):**
- Walk captures, overnight logs, stability data — keep in branch, not master

### What speed-sustained-sweep has that needs porting (MANUAL)

Already confirmed in range-tests V4 firmware:
- ✅ GPS baud 115200
- ✅ GPS pins GP0/GP1  
- ✅ RSSI 9-bit assembly
- ✅ NMEA parser fix

Might be missing (need verification):
- ? 20s guard band (3d5ffd4) — range-tests uses 500ms guard bands
- ? STANDBY re-arm sequence (9d7f2ce) — verify RX re-arm logic
- ? Board lock chmod enforcement (ef60a51, 99b94ca) — range-tests has pio-flash.sh

### What speed-optimization has (SEPARATE CONCERN)

- Single-batch SPI 1733 kbps breakthrough
- Configurable FLRC TX firmware
- This is throughput optimization, not range testing
- Keep on separate branch, merge AFTER consolidation

---

## Consolidation Strategy

### Phase 1: Deep Diff Analysis (DELEGATE)
**Owner: range-tests sub-manager → worker**
**Deliverable: BUG-FIX-REGISTRY.md**

Task: Systematically diff range-tests vs master firmware source files.
For each difference, classify:
- BUG FIX in master not in range-tests → MUST PORT
- BUG FIX in range-tests not in master → ALREADY HAVE
- SUPERSEDED approach → document, keep newer
- CONFLICT (different fix for same bug) → flag for resolution

Files to diff:
- firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp
- firmware/rp2040/src/multi_radio_sweep_rx_v4.cpp
- firmware/rp2040/platformio.ini
- Makefile
- tools/ (all scripts)
- tests/ (pytest framework)

### Phase 2: Speed-Sweep Cross-Check (DELEGATE)
**Owner: speed-tests sub-manager → worker**
**Deliverable: addendum to BUG-FIX-REGISTRY.md**

Task: Verify speed-sustained-sweep fixes are ALL in range-tests V4:
- 20s guard band (3d5ffd4) — is it in V4? If not, should it be?
- STANDBY re-arm sequence (9d7f2ce) — verify RX re-arm matches
- udev chmod enforcement (99b94ca) — verify range-tests has equivalent
- Any other speed-sweep-specific fixes

### Phase 3: Bug Fix Porting (DELEGATE)
**Owner: range-tests sub-manager → worker**
**Deliverable: PR to master**

Task: Starting from range-tests, create `consolidation/master-v5` branch.
Port ALL identified missing fixes from master.
Key fixes to port:
1. totalCycleSec accumulation guard (if not already adequate)
2. RMC time parsing (time without position fix)
3. ADR-021 UTC sync (configurable GPS gate)
4. TX boot gate removal (5s probe instead of 60s wait)
5. Overnight monitor script
6. walk_capture.py improvements
7. Make target improvements from master

### Phase 4: Make Target Audit + Laptop Compatibility (DELEGATE)
**Owner: range-tests sub-manager → worker**  
**Deliverable: verified Make targets**

Task: Ensure ALL board interactions have Make targets:
- `make flash-tx` / `make flash-rx` — build + flash
- `make build-tx` / `make build-rx` — build only
- `make monitor-tx` / `make monitor-rx` — serial monitor
- `make find-ports` — detect which board is on which port
- `make test` — run pytest suite
- `make test-unit` — unit tests only (no hardware)
- `make walk-test` — start walk capture on RX
- `make sync-time` — sync TX/RX time from laptop
- `make flash-bootsel-tx` — flash via UF2 copy (laptop BOOTSEL mode)

Test ALL targets on clean platformio install (simulate Felix's laptop).
Fix the platformio.ini issue (earlephilhower core vs mbed core).

### Phase 5: Integration Build + Test (DELEGATE)
**Owner: range-tests sub-manager → worker**
**Deliverable: green build + all tests pass**

Task: On DQ05:
1. Clean build both envs: `make build-tx && make build-rx`
2. Run unit tests: `make test-unit` (all must pass)
3. Flash both boards, verify serial output
4. 2-minute bench capture, verify decode > 0

### Phase 6: Sub-Manager Consensus Review (COLLABORATIVE)
**Owner: orchestrator + all sub-managers**
**Deliverable: sign-off document**

Task: Present consolidated branch to all sub-managers:
- range-tests: firmware review
- speed-tests: RSSI/timing review  
- Each confirms their track's fixes are present
- Any missing fix → port before merge

### Phase 7: Merge to Master (ORCHESTRATOR)
**Owner: orchestrator**
**Deliverable: clean master branch**

Task:
1. Merge consolidation branch → master
2. Delete old branches (main, speed-sustained-sweep)
3. Keep: range-tests, speed-optimization, balloon-circuit-design
4. Push master to github + ngit
5. Tag release: v5.0-consolidated

---

## Conflict Resolution Rules

1. **totalCycleSec fix**: range-tests version (recompute from phase table) is MORE robust than master's (just reset before accumulate). KEEP range-tests version, verify it handles SET_TIME without accumulation.

2. **GPS gate philosophy**: Keep BOTH as configurable options.
   - Default: ADR-018 (GPS fix-gate ON for outdoor range tests)
   - Configurable: ADR-021 (GPS optional for bench testing)
   - SET_INTERLEAVE already controls mode — add SET_GPS_GATE command

3. **Guard bands**: Use range-tests 500ms (proven in 93% decode walk test).
   speed-sweep 20s was for old firmware, not needed in V4.

4. **platformio.ini**: Use range-tests version (has `[env]` base section with
   earlephilhower core). Master version is missing this → build failure.

5. **Makefile**: Use range-tests/master version (both have `a93d59e2` blob).
   This has correct env names. Felix's laptop had stale clone.

---

## Quality Gates

Every phase must pass before next:
1. ✅ Bug fix registry complete (all fixes identified)
2. ✅ No fix lost in merge (diff verification)
3. ✅ Clean build (both TX + RX)
4. ✅ Unit tests pass (14+ tests)
5. ✅ Make targets work on clean install
6. ✅ Sub-manager sign-off (consensus)
7. ✅ Pushed to github + ngit
