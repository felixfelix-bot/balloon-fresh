# Post-Merge Integration Plan

**Created:** 2026-07-30
**Status:** APPROVED — dispatching to sub-managers

## Overview

All 8 branches merged to master. Now each track does cross-integration work using code from other tracks now available on master.

## Flash Policy

**All tracks may flash any board if physically present. Must respect the hard mutex lock (balloon-board-lock.py). No orchestrator approval needed for individual flashes — but tracks must log to FLASH-QUEUE.md.**

---

## Workstream 1: FIPS × Tollgate Cross-Integration

**Owner:** balloon-fips sub-manager (lead) + balloon-tollgate sub-manager (support)
**Model:** glm-5.2
**Branch:** feature/lr2021-tollgate-integration

### Objective
Wire lr2021_transport (now on master from fips) into tollgate mesh layer (now on master from tollgate). Enable tollgate to send/receive mesh packets over LR2021 radio instead of WiFi-only.

### Tasks

1. **Tollgate: Import lr2021_transport**
   - Add lr2021_transport to tollgate CMakeLists REQUIRES
   - Create radio_adapter.cpp bridging mesh_service_mux → lr2021_transport
   - Quality gate: `idf.py build` PASS (no compile errors)

2. **FIPS: Verify lr2021_transport API surface**
   - Audit lr2021_transport.h public API
   - Confirm send/recv/init functions match what tollgate needs
   - Quality gate: API doc written, header review clean

3. **Integration: End-to-end build**
   - Build tollgate firmware with lr2021_transport linked
   - Run existing tollgate unit tests (24 tests must still pass)
   - Quality gate: `make test-unit` 24/24 PASS + `idf.py build` PASS

4. **Integration test stub**
   - Write test_radio_adapter.cpp — mock LR2021 SPI, verify mesh packet → radio frame conversion
   - Quality gate: test compiles + runs, mock returns expected frames

### Deliverable
Working build of tollgate firmware with lr2021_transport linked. Push to feature/lr2021-tollgate-integration branch.

---

## Workstream 2: Circuit-Design Short Reduction + JLCPCB Prep

**Owner:** balloon-circuit-design sub-manager
**Model:** glm-5.2
**Branch:** balloon-circuit-design (continue on existing)

### Objective
Reduce F33 shorts from 17 toward 0 algorithmically. Prepare complete JLCPCB order package for V1 board.

### Tasks

1. **F33 algorithmic short reduction**
   - Run Router with lane assignment improvements (dedicate x-columns per net on B.Cu with 2mm spacing)
   - Target: reduce 17 → <10 shorts
   - Quality gate: DRC report shows reduction, router tests pass

2. **V1 JLCPCB order package verification**
   - Verify gerbers_v1/ contains: .GTL, .GBL, .GTS, .GBS, .GTO, .GBO, .TXT (drill), .DRL
   - Generate BOM (CSV: designator, value, footprint, LCSC part number)
   - Generate CPL (CSV: designator, mid X, mid Y, layer, rotation)
   - Quality gate: all files present, opens in gerber viewer, BOM matches schematic

3. **F33 remaining short analysis**
   - For each of the 17 shorts, document: which nets, which layer, which pads
   - Classify: GUI-fixable vs footprint-conflict vs design-error
   - Quality gate: analysis doc committed

### Deliverable
Updated F33 with reduced shorts. V1 order package ready. Short analysis doc for Felix's GUI session.

---

## Workstream 3: Range-Tests Firmware + Test Scripts

**Owner:** balloon-range-tests sub-manager
**Model:** glm-5.2
**Branch:** range-tests (continue on existing)

### Objective
Develop TX/RX firmware improvements using merged lr2021_transport. Write automated test scripts for walk tests. No flashing without mutex.

### Tasks

1. **Port range-test firmware to lr2021_transport**
   - Replace raw SPI calls with lr2021_transport API (now on master)
   - Keep NeoPixel LED status indicator (MANDATORY)
   - Quality gate: `idf.py build` PASS

2. **Walk test automation script**
   - Python script: log GPS + RSSI + packet stats during walk
   - Use BoardSerial wrapper for serial access
   - Auto-generate plots (matplotlib) after capture
   - Quality gate: script runs, produces CSV + PNG output

3. **Payload sweep test configuration**
   - Config files for 32B, 64B, 128B, 255B payload sweeps
   - Quality gate: configs valid, build with each config PASS

### Deliverable
Updated firmware using lr2021_transport. Test scripts ready for when Felix approves walk tests.

---

## Workstream 4: E-Hash Integration Tests

**Owner:** balloon-pow sub-manager
**Model:** glm-5.2
**Branch:** balloon-pow-e-hash (continue on existing)

### Objective
Write and run integration tests for e-hash relay (Phase A/B/C now on master).

### Tasks

1. **Unit tests for L7 handler (Phase C)**
   - Test packet parsing, relay forwarding, hop-count tracking
   - Quality gate: `make test` PASS, coverage > 80%

2. **Stratum bridge protocol test**
   - Test stratum message format, share submission, difficulty validation
   - Quality gate: test compiles, runs, validates protocol conformance

3. **End-to-end relay simulation**
   - Simulate 3-hop relay chain (ground → balloon1 → balloon2 → ground)
   - Verify packet integrity through chain
   - Quality gate: simulation runs, 0 packet loss in ideal conditions

### Deliverable
Test suite proving e-hash relay works. Push to balloon-pow-e-hash branch.

---

## Workstream 5: Blossom Cleanup + Rebase

**Owner:** balloon-blossom sub-manager
**Model:** glm-4.5-flash
**Branch:** rebase onto master

### Objective
Clean up 2 dirty files, rebase onto master, verify blossom-server still works with all merged code.

### Tasks

1. **Rebase blossom-server onto master**
   - git fetch github && git rebase github/master
   - Quality gate: 0 conflicts, push --force-with-lease succeeds

2. **Verify blossom-server compatibility**
   - Check nostr_store (from nostr branch) doesn't conflict with blossom storage
   - Quality gate: build PASS, no duplicate symbols

3. **Clean up dirty files**
   - Commit or discard the 2 uncommitted files
   - Quality gate: git status --short shows clean

### Deliverable
Clean blossom-server on master. Ready for future work.

---

## Cross-Cutting Quality Gates (ALL workstreams)

1. **Build PASS** — `idf.py build` or `make` succeeds
2. **Tests PASS** — existing tests still pass (no regressions)
3. **Commit + Push** — all work committed and pushed to github
4. **Mutex respected** — board access via balloon-board-lock.py only
5. **No RadioLib** — lr2021_transport only (ADR-020)
