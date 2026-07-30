# Balloon-FIPS Master Execution Plan

**Created:** 2026-07-29
**Author:** balloon-fips sub-manager
**Status:** AWAITING FELIX APPROVAL
**Worktree:** `~/worktrees/balloon-fips-fresh/` (branch `balloon-fips-extract`)

---

## Current State

### Completed (host-side, all pushed)

| Deliverable | Commit | Tests | Status |
|-------------|--------|-------|--------|
| LR2021 transport Rust→C++ port | `88b9f8b` | 36 host tests PASS | DONE |
| Phase 1: FIPS↔LR2021 bridge | `7992b8e` | 4/4 tests PASS | DONE |
| Phase 3: Multi-frame encrypted transport | `f524d1e` | 5/5 tests PASS | DONE |
| ADR-025: Hardware flock mutex | `717b581` | c3-a/c3-b deployed | DONE |
| ADR-026: Dual-MCU radio architecture | `f0236f0` | Documented | DONE |
| Board lock resources (c3-a, c3-b) | `54ff84e` | Status verified | DONE |
| Integration plan (6 phases) | `866a08e` | Documented | DONE |
| Phase 2 plan | `c69e7a3` | Documented | DONE |

### ADRs Established

| ADR | Title | Status |
|-----|-------|--------|
| 016 | Keep C++ microfips (not Rust FIPS) | ACCEPTED |
| 020 | Raw 2-byte SPI, no RadioLib | ACCEPTED |
| 024 | Source repos READ-ONLY, extract only | ACCEPTED |
| 025 | Shared hardware flock mutex | ACCEPTED |
| 026 | Dual-MCU: RP2040 radio processor + ESP32-C3 app | ACCEPTED |

### Key Architecture Decisions

- **Language:** C++ ESP-IDF (ADR-016)
- **Radio driver:** Raw 2-byte SPI opcodes, NO RadioLib (ADR-020)
- **Radio MCU:** RP2040 as radio processor for flight; ESP32-C3 direct for dev (ADR-026)
- **Transport priority:** FIPS primary, MeshCore fallback (Felix directive)
- **RadioLib:** Full removal from balloon-fresh (Felix directive)

---

## Task Breakdown — 9 Tasks

### GROUP A: Host-Side (START NOW — no DQ05, no hardware)

---

#### Task A1: Remove dead SX1280 opcodes from lr2021_spi.h

**Goal:** Eliminate confusion from wrong opcode namespaces. Keep only `Lr2021Opcodes` (correct 2-byte).

**Worker profile:** `glm-4.5-flash` — mechanical deletion + grep verification

**Scope:**
1. Read `tracker/firmware/components/lr2021_transport/include/lr2021_spi.h`
2. Search ALL source files for references to `Lr2021Commands::` and `Lr2021Registers::`
3. Remove `Lr2021Commands` namespace (1-byte SX1280 opcodes — WRONG)
4. Remove `Lr2021Registers` namespace (16-bit addresses — WRONG)
5. Keep `Lr2021Opcodes` namespace (2-byte opcodes — CORRECT)
6. Rebuild: `cd tracker/firmware/components/lr2021_transport/test && make clean && make build && make test`
7. All 36 tests must still pass
8. Also rebuild fips_radio_bridge tests: `cd ../../fips_radio_bridge/test && make clean && make build && make test`
9. All 9 tests must still pass

**Quality Gates:**
- [ ] Gate 1 (TDD): Existing 45 tests (36+9) serve as regression suite
- [ ] Gate 2 (Tests pass): `make test` in both test dirs — 45/45 pass
- [ ] Gate 3 (Docs): Add comment in header noting removed namespaces were SX1280-incompatible
- [ ] Gate 4 (Atomic commit): `refactor: remove dead SX1280 opcode namespaces from lr2021_spi.h`
- [ ] Gate 5 (PUSHED): `git push github balloon-fips-extract`

**Estimated time:** 30 min
**Needs DQ05:** NO
**Needs hardware:** NO
**Blocks:** Nothing
**Blocked by:** Nothing

---

#### Task A2: Fix pio-flash.sh to enforce c3-a/c3-b locks

**Goal:** Flash shim must enforce ADR-025 locks for ESP32-C3 boards, not just RP2040 tx/rx.

**Worker profile:** `glm-4.5-flash` — mechanical file edit, clear pattern

**Scope:**
1. Read `~/repos/balloon-fresh/tools/pio-flash.sh`
2. Read `~/repos/balloon-fresh/tools/balloon-board-lock.py` (resource resolution pattern)
3. Add MAC-based device resolution for ESP32-C3 boards:
   - MAC contains `96:DC` → resource = `c3-a`
   - MAC contains `C6:98` → resource = `c3-b`
4. Update fallback port mapping: `ttyACM0` is now `c3-a` (was `rx`)
5. Also support `idf.py flash` mode (not just `pio run -t upload`):
   - Detect if called as `idf-flash.sh` or with `--idf` flag
   - Run `idf.py -p <port> flash` instead of `pio run -t upload`
6. Test: simulate lock-held and lock-not-held scenarios (dry run, no actual flash)
7. Commit to `~/repos/balloon-fresh/` master branch

**Quality Gates:**
- [ ] Gate 1 (TDD): Write a test script that:
  - (a) Runs shim with lock NOT held → must refuse with clear error message
  - (b) Runs shim with lock held → must proceed to flash command
- [ ] Gate 2 (Tests pass): Both scenarios behave correctly
- [ ] Gate 3 (Docs): ADR-025 enforcement section updated to note pio-flash.sh coverage
- [ ] Gate 4 (Atomic commit): `fix: pio-flash.sh enforces c3-a/c3-b locks per ADR-025`
- [ ] Gate 5 (PUSHED): `git push github master`

**Estimated time:** 1-2 hours
**Needs DQ05:** NO
**Needs hardware:** NO (dry-run with mock lock state)
**Blocks:** Phase 5 hardware test (must use shim)
**Blocked by:** Nothing

**RISK:** pio-flash.sh is on master in main repo (shared by all tracks). Must not break existing tx/rx behavior. Test backward compatibility.

---

#### Task A3: SPI speed constraints documentation

**Goal:** Document 20MHz SPI layout rules for Phase 5 breadboard testing and future PCB design.

**Worker profile:** `glm-4.5-flash` — documentation from existing data

**Scope:**
1. Create `tracker/firmware/components/lr2021_transport/SPI-LAYOUT-CONSTRAINTS.md`
2. Document:
   - 20 MHz confirmed working on ESP32-C3 (1733 kbps, 1000/1000)
   - PCB layout rules: <30mm traces, length-matched ±5mm, 45° corners, ground plane, 100nF+10µF decoupling
   - RP2040 caps at 12 MHz actual → 77% RX loss at "20 MHz" setting
   - 40 MHz corrupts FIFO → hard ceiling
   - ESP32-C3 achieves true 20 MHz
3. Add "Phase 5 Breadboard Setup" section:
   - Pin connections (ESP32-C3 ↔ LR2021)
   - Wire length recommendations (<10cm jumpers)
   - Ground return path
   - Common pitfalls
4. Cross-reference existing docs

**Quality Gates:**
- [ ] Gate 1 (Review): Covers all 5 constraint areas (speed, layout, RP2040 cap, ceiling, ESP32 advantage)
- [ ] Gate 2 (Accuracy): Values match proven firmware (20 MHz, 1733 kbps, 12 MHz RP2040 cap)
- [ ] Gate 3 (Commit): `docs: SPI layout constraints for LR2021 at 20MHz`
- [ ] Gate 4 (PUSHED)

**Estimated time:** 1 hour
**Needs DQ05:** NO
**Needs hardware:** NO
**Blocks:** Nothing
**Blocked by:** Nothing

---

### GROUP B: DQ05-Dependent (START WHEN DQ05 BACK ONLINE)

---

#### Task B1: Write EspHalLr2021Radio — ESP-IDF hardware adapter

**Goal:** Implement `Lr2021Radio` interface using ESP-IDF SPI/GPIO. Direct ESP32-C3→LR2021 for dev testing per ADR-026.

**Worker profile:** `glm-5.2` — complex embedded, SPI timing critical

**DEPENDS ON:** DQ05 online. Task A1 complete (clean opcodes).

**Scope:**
1. Create `tracker/firmware/components/lr2021_transport/include/esp_idf_lr2021_radio.h`
2. Create `tracker/firmware/components/lr2021_transport/src/esp_idf_lr2021_radio.cpp`
3. Implement all 9 `Lr2021Radio` virtual methods
4. Reference: `firmware/esp32-c3-flrc/main/main.cpp` (PROVEN — port the SPI patterns)
5. SPI config: SPI2_HOST, 20 MHz, mode 0, half-duplex, manual CS, max_transfer 526B
6. GPIO: SCK=6, MOSI=7, MISO=2, CS=10, BUSY=4, IRQ=5, RST=3
7. Full 17-step LR2021 init sequence (from proven firmware)
8. Helper methods: `spi_write()`, `spi_read()`, `wait_busy()`, `hardware_reset()`, `compute_frf()`
9. Compile on DQ05: `cd tracker/firmware && idf.py build` with lr2021_transport in REQUIRES

**Quality Gates:**
- [ ] Gate 1 (TDD): Host test for pin config validation (compile-time #ifdef checks). MockLr2021Radio tests (45 existing) still pass.
- [ ] Gate 2 (Tests pass): Host tests 45/45; DQ05 ESP-IDF build 0 errors
- [ ] Gate 3 (Docs): Component README with pin mapping + SPI config + init sequence reference
- [ ] Gate 4 (Atomic commit): `feat: EspHalLr2021Radio — ESP-IDF raw SPI adapter (20MHz direct GPIO)`
- [ ] Gate 5 (PUSHED)

**Estimated time:** 4-6 hours
**Needs DQ05:** YES
**Needs hardware:** NO (compile only)
**Blocks:** Task B2
**Blocked by:** Task A1, DQ05

---

#### Task B2: Replace RadioLib in app_main.cpp

**Goal:** Remove all RadioLib LR2021 references. Wire app_main to lr2021_transport. ADR-020 compliance.

**Worker profile:** `glm-5.2` — multi-file refactor, build system

**DEPENDS ON:** Task B1 complete.

**Scope:**
1. Add `lr2021_transport` to `main/CMakeLists.txt` COMPONENT_REQUIRES
2. Remove `RadioLib` from COMPONENT_REQUIRES (verify no other component uses it)
3. In `app_main.cpp`:
   - Remove `#include <RadioLib.h>`, `#include "EspHalC3.h"`
   - Remove `LR2021* radio`, all RadioLib API calls
   - Add `EspHalLr2021Radio` + `Lr2021Transport` instantiation
   - Replace `radio->begin()` → `transport.init(config)`
   - Replace `radio->startTransmit()` → `transport.send()`
   - Replace RadioLib IRQ handler → `transport.poll_irq()` + `recv()`
4. Handle MeshCore: if MeshCore depends on RadioLib types, create minimal shim or defer MeshCore to Phase 4
5. Build on DQ05: `idf.py build` — 0 errors

**Quality Gates:**
- [ ] Gate 1 (TDD): `idf.py build` compiles = test
- [ ] Gate 2 (Build passes): 0 errors
- [ ] Gate 3 (Docs): AGENTS.md updated — RadioLib removed, lr2021_transport is radio driver
- [ ] Gate 4 (Atomic commit): `refactor: replace RadioLib with lr2021_transport in app_main (ADR-020)`
- [ ] Gate 5 (PUSHED)

**Estimated time:** 3-4 hours
**Needs DQ05:** YES
**Needs hardware:** NO
**Blocks:** Phase 4 (MeshCore migration)
**Blocked by:** Task B1
**RISK:** MeshCore may reference RadioLib types. If so, defer MeshCore wiring to Phase 4.

---

#### Task B3: MeshCore LR2021 radio adapter

**Goal:** MeshCore uses raw LR2021 SPI instead of RadioLib. `Lr2021MeshCoreRadio` implements `mesh::Radio`.

**Worker profile:** `glm-5.2` — interface adaptation, MeshCore internals

**DEPENDS ON:** Task B2 complete. Felix priority: FIPS transport first, MeshCore second.

**Scope:**
1. Read `tracker/firmware/components/meshcore/esp_idf/EspIdfInterfaces.h`
2. Create `Lr2021MeshCoreRadio` implementing `mesh::Radio` interface
3. Map MeshCore Radio methods to lr2021_transport calls
4. Build on DQ05: `idf.py build` with MeshCore enabled

**Quality Gates:**
- [ ] Gate 1 (TDD): Build compiles = test
- [ ] Gate 2 (Build passes): 0 errors
- [ ] Gate 3 (Docs): Architecture note — FIPS primary, MeshCore fallback
- [ ] Gate 4 (Atomic commit): `feat: Lr2021MeshCoreRadio adapter (raw SPI, no RadioLib)`
- [ ] Gate 5 (PUSHED)

**Estimated time:** 4-6 hours
**Needs DQ05:** YES
**Needs hardware:** NO
**Blocks:** Phase 5
**Blocked by:** Task B2

---

### GROUP C: Hardware Integration (START WHEN DQ05 + BOARDS AVAILABLE)

---

#### Task C1: Two-node FIPS handshake over FLRC radio

**Goal:** Two ESP32-C3+LR2021 nodes complete Noise IK handshake over real radio. THE proof.

**Worker profile:** `glm-5.2` — hardware testing, serial monitoring, logic analyzer

**DEPENDS ON:** Tasks B1, B2 complete. DQ05 online. Board locks available.

**PRE-REQUISITES:**
- Acquire board lock: `BALLOON_TRACK=balloon-fips python3 balloon-board-lock.py acquire both-c3 --purpose "FIPS handshake test" --timeout 120`
- Use pio-flash.sh (Task A2) for ALL flash operations
- Phase 5 test setup per SPI-LAYOUT-CONSTRAINTS.md (Task A3)

**Scope:**
1. Flash initiator firmware on c3-a (Node A)
2. Flash responder firmware on c3-b (Node B)
3. Configure FLRC-2600 (2.4 GHz, proven modulation)
4. Run: Node A initiates → Node B responds → both ESTABLISHED
5. Exchange: GPS telemetry (28B) + test datagram (200B) bidirectionally
6. Capture logic analyzer trace (8ch, SPI bus during handshake)
7. Measure: handshake latency, PER, RSSI at 1m / 5m / 10m
8. Release board lock: `python3 balloon-board-lock.py release both-c3`

**Quality Gates:**
- [ ] Gate 1 (TDD): Test procedure documented BEFORE running. Expected results defined.
- [ ] Gate 2 (Tests pass): Handshake completes, both nodes ESTABLISHED, payloads verified
- [ ] Gate 3 (Docs): Test report — latency, PER, RSSI, logic analyzer screenshots
- [ ] Gate 4 (Atomic commit): `test: two-node FIPS handshake over FLRC radio — PASS`
- [ ] Gate 5 (PUSHED)
- [ ] Gate 6 (Cleanup): Board locks released, serial ports freed

**Estimated time:** 1 full day
**Needs DQ05:** YES
**Needs hardware:** YES — 2x ESP32-C3 (c3-a, c3-b), 2x LR2021, logic analyzer
**Blocks:** Task C2
**Blocked by:** Tasks B1, B2, A2, A3

---

#### Task C2: Memory profiling + flight readiness

**Goal:** Verify ESP32-C3 RAM budget with all components. Go/no-go for flight firmware. Completes B.7.13-B.7.15.

**Worker profile:** `glm-5.2` — ESP-IDF heap tracing, size analysis

**DEPENDS ON:** Tasks B1, B2, B3 complete.

**Scope:**
1. Build with ALL components: meshcore + fips_transport + lr2021_transport + wirehair + stratorelay + tdma
2. Measure static DRAM — target <280KB of 400KB (leave 120KB heap)
3. Measure stack during Noise handshake (most stack-intensive op)
4. Profile worst case: MeshCore relay + FIPS handshake + fragmentation simultaneously
5. Verify GPS + telemetry + mesh coexist in RAM
6. Write memory budget report

**Quality Gates:**
- [ ] Gate 1 (TDD): Profiling procedure documented
- [ ] Gate 2 (Tests pass): Static DRAM <280KB, heap >120KB after init
- [ ] Gate 3 (Docs): Memory budget report with breakdown per component
- [ ] Gate 4 (Atomic commit): `docs: memory budget report — all components fit in ESP32-C3 RAM`
- [ ] Gate 5 (PUSHED)

**Estimated time:** 4-6 hours
**Needs DQ05:** YES
**Needs hardware:** NO
**Blocks:** Flight readiness decision
**Blocked by:** Tasks B1, B2, B3

---

## Execution Schedule

### Phase 1 — START NOW (no DQ05)

```
Week 1, Day 1 (immediately upon approval):
┌─────────────────────────────────────────────────────────┐
│ A1: Dead opcode cleanup     [30 min]  [glm-4.5-flash]  │
│ A2: pio-flash.sh fix         [1-2 hr]  [glm-4.5-flash]  │
│ A3: SPI constraints doc      [1 hr]    [glm-4.5-flash]  │
│                                                         │
│ All 3 run in PARALLEL. Independent. No blockers.        │
└─────────────────────────────────────────────────────────┘
```

### Phase 2 — WHEN DQ05 BACK

```
┌─────────────────────────────────────────────────────────┐
│ B1: EspHalLr2021Radio       [4-6 hr]  [glm-5.2]        │
│     blocked by: A1 done, DQ05 online                    │
│                                                         │
│ B2: app_main migration       [3-4 hr]  [glm-5.2]        │
│     blocked by: B1 done                                 │
│                                                         │
│ B3: MeshCore adapter         [4-6 hr]  [glm-5.2]        │
│     blocked by: B2 done (can start same day as B2)     │
└─────────────────────────────────────────────────────────┘
```

### Phase 3 — HARDWARE TEST (DQ05 + boards)

```
┌─────────────────────────────────────────────────────────┐
│ C1: Two-node handshake test [1 day]   [glm-5.2]        │
│     blocked by: B1, B2, A2, A3 done                     │
│     requires: board lock (both-c3), logic analyzer     │
│                                                         │
│ C2: Memory profiling         [4-6 hr]  [glm-5.2]        │
│     blocked by: B1, B2, B3 done                         │
└─────────────────────────────────────────────────────────┘
```

## Dependency Graph

```
A1 (cleanup) ──────────────────────────────┐
A2 (pio-flash) ──────────────────────┐     │
A3 (SPI doc) ───────────────────┐    │     │
                                │    │     │
                         (DQ05) │    │     │
                                ▼    │     │
                          B1 (adapter) ◄───┘
                                │    │
                                ▼    │
                          B2 (app_main)
                                │
                    ┌───────────┤
                    ▼           ▼
              B3 (meshcore)  C1 (handshake test) ◄── A2, A3
                    │
                    ▼
              C2 (memory profile)
```

## Worker Profile Summary

| Task | Model | Rationale |
|------|-------|-----------|
| A1 | glm-4.5-flash | Delete + grep, simple |
| A2 | glm-4.5-flash | Pattern-following script edit |
| A3 | glm-4.5-flash | Documentation from data |
| B1 | glm-5.2 | Embedded SPI, timing critical |
| B2 | glm-5.2 | Multi-file refactor |
| B3 | glm-5.2 | Interface adaptation |
| C1 | glm-5.2 | Hardware testing |
| C2 | glm-5.2 | ESP-IDF profiling |

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| MeshCore depends on RadioLib types | MEDIUM | Blocks B2 | Create shim, or defer MeshCore to Phase 4 |
| DQ05 extended downtime | MEDIUM | Blocks B1-C2 | Phase 1 (A1-A3) makes progress independently |
| ESP32-C3 RAM insufficient for all components | LOW | Blocks C2 | Budget analysis: ~61KB used, 400KB available |
| pio-flash.sh breaks existing tx/rx behavior | LOW | Blocks all tracks | Test backward compat before push |
| SPI noise on breadboard at 20 MHz | MEDIUM | C1 fails | Use short jumpers, single ground. Fall back to 16 MHz if needed. |

## Board Lock Protocol (ADR-025)

ALL hardware access requires lock acquisition:

```bash
# Acquire both ESP32-C3 boards for handshake test
BALLOON_TRACK=balloon-fips python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py \
    acquire both-c3 --purpose "FIPS handshake test" --timeout 120

# Flash via shim (NOT direct idf.py)
BALLOON_TRACK=balloon-fips python3 ~/repos/balloon-fresh/tools/pio-flash.sh \
    --idf --upload-port /dev/ttyACM0

# Release after test
BALLOON_TRACK=balloon-fips python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py \
    release both-c3
```

## Deliverables Summary

| # | Deliverable | Gate |
|---|-------------|------|
| A1 | Clean lr2021_spi.h (no dead opcodes) | 45 tests pass |
| A2 | pio-flash.sh protects c3-a/c3-b | Lock test passes |
| A3 | SPI layout constraints doc | Reviewed |
| B1 | EspHalLr2021Radio adapter | DQ05 builds, 0 errors |
| B2 | app_main without RadioLib | DQ05 builds, 0 errors |
| B3 | MeshCore raw SPI adapter | DQ05 builds, 0 errors |
| C1 | Two-node FIPS handshake | Handshake completes, payloads verified |
| C2 | Memory budget report | RAM <280KB, heap >120KB |

**Critical path:** A1 → B1 → B2 → C1 (handshake proof)
**Total estimated time:** 3-5 working days (1 day host + 2-4 days DQ05-dependent)
