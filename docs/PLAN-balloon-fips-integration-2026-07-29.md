# Balloon-FIPS Integration Plan

**Created:** 2026-07-29
**Author:** balloon-fips sub-manager
**Status:** AWAITING FELIX APPROVAL
**Branch:** `balloon-fips-extract` in `~/worktrees/balloon-fips-fresh/`

## Current State Assessment

### What EXISTS (code + tests)

| Component | Lines | Tests | Status |
|-----------|-------|-------|--------|
| lr2021_transport | 2,223 | 36 host tests PASS | Just extracted (commit 88b9f8b). Raw 2-byte SPI, TxFramer/RxFramer, Lr2021Transport. NOT in firmware build. |
| fips_transport | 1,086 | test_fips.cpp exists | Noise IK handshake + ChaChaPoly AEAD. Uses function pointers (`fips_send_fn`/`fips_recv_fn`) for I/O. NOT wired to LR2021. |
| meshcore | 7,939 | 11/11 stratorelay tests | ESP-IDF component, builds OK (330KB). Uses RadioLib LR2021 driver. |
| stratorelay | 442 | 11/11 tests PASS | UnionFind, NodeTable, BloomFilter, ClusterHeadElector. |
| wirehair | 10,249 | test + bench exist | Fountain codes. Standalone. NOT in transport path. |
| erasure | 551 | test exists | Erasure coding wrapper. NOT integrated. |
| frag | 359 | test exists | Fragmentation. NOT integrated. |
| pipeline | 410 | test exists | Pipeline orchestration. NOT integrated. |
| tdma | 413 | test exists | TDMA scheduler. NOT integrated with LR2021. |
| mesh_adapter | 513 | — | Bridge between FIPS and MeshCore. |
| app_main.cpp | 607 | — | Uses RadioLib LR2021 + MeshCore. Does NOT use fips_transport or lr2021_transport. |

### Critical Findings

1. **ADR-020 CONFLICT:** `app_main.cpp` uses RadioLib's LR2021 driver. ADR-020 (accepted Jul 23) says RadioLib's LR2021 driver DOES NOT WORK — wrong protocol (24-bit addressing vs our chip's 2-byte opcodes). This is a known-broken code path.

2. **FIPS transport is standalone:** `fips_transport` uses callback function pointers for send/recv. No glue code connects it to `lr2021_transport`. The Noise handshake has never run over actual LR2021 radio in this codebase (only via SLIP→FLRC bridge in a separate test setup per `fips-flrc-validation-plan.md`).

3. **No vertical integration:** The 7-layer stack (L1 LR2021 → L7 TollGate/Nostr) has individual components with tests but NO end-to-end integration. Each layer is a standalone island.

4. **DQ05 dependency:** ESP-IDF firmware builds (target: ESP32-C3) require DQ05 build server. Host-side tests (g++ compilation) work without DQ05. This plan separates host-testable work from firmware-build work.

---

## Plan: 6 Phases

### Phase 1: FIPS Transport ↔ LR2021 Transport Wiring (HOST, no DQ05)

**Goal:** Connect Noise IK handshake to raw LR2021 SPI transport. Run Noise handshake packets through the LR2021 transport mock.

**Tasks:**
1. Create `fips_radio_bridge.h` / `.cpp` — adapter that implements `fips_send_fn` / `fips_recv_fn` using `Lr2021Transport::send_packet()` / `recv_packet()`.
2. Write host-side integration test: two `Lr2021Transport` instances with mock radios → two `fips_session_t` → complete Noise IK handshake → exchange encrypted payloads.
3. Verify MSG1 (98 bytes) and MSG2 (49 bytes) fit in LR2021 packets (max 255 bytes). Yes — confirmed by FIPS_MSG1_SIZE/FIPS_MSG2_SIZE constants.

**Deliverable:** Host test proving FIPS Noise IK handshake works over LR2021 transport abstraction.

**Estimated time:** 4-6 hours
**Needs DQ05:** NO
**Needs hardware:** NO

---

### Phase 2: Replace RadioLib in app_main with lr2021_transport (NEEDS DQ05)

**Goal:** Migrate `app_main.cpp` from broken RadioLib LR2021 to our raw-SPI `lr2021_transport` component. Complies with ADR-020.

**Tasks:**
1. Add `lr2021_transport` to `main/CMakeLists.txt` COMPONENT_REQUIRES.
2. Create `EspHalLr2021Radio` adapter — wraps ESP-IDF `spi_device_handle_t` + GPIO into the `Lr2021Radio` interface that `lr2021_transport` expects. Pin definitions: SCK/MOSI/MISO/CS/BUSY/IRQ/RST as per ESP32-C3 wiring.
3. Replace RadioLib `LR2021` instantiation in `app_main.cpp` with `Lr2021Transport` using `EspHalLr2021Radio`.
4. Build firmware on DQ05, verify compilation (no runtime test yet).
5. Remove RadioLib from COMPONENT_REQUIRES if no other component uses it.

**Deliverable:** Firmware compiles with lr2021_transport instead of RadioLib. ADR-020 compliance.
**Estimated time:** 6-8 hours
**Needs DQ05:** YES (ESP-IDF cross-compile)
**Needs hardware:** NO (compile only)

---

### Phase 3: Wire Full Data Path — FIPS over LR2021 with Fragmentation (HOST, no DQ05)

**Goal:** End-to-end: application payload → FIPS encrypt → fragment → LR2021 TX → LR2021 RX → reassemble → FIPS decrypt → application payload.

**Tasks:**
1. Create `fips_transport_link.h` / `.cpp` — combines:
   - FIPS session (encrypt/decrypt)
   - `frag` component (split >255B payloads into LR2021-sized packets)
   - `lr2021_transport` (send/recv packets over radio)
2. Write host-side integration test with mock radio:
   - Node A: encrypt 1KB payload → fragment → send via LR2021
   - Node B: recv via LR2021 → reassemble → decrypt → verify payload matches
3. Verify handshake-sized messages (114B MSG1) fit in single packet (no fragmentation needed for handshake).
4. Test multi-fragment datagram path (1KB = ~4-5 fragments).

**Deliverable:** Host test proving encrypted fragmented transport works over LR2021 abstraction.
**Estimated time:** 6-8 hours
**Needs DQ05:** NO
**Needs hardware:** NO

---

### Phase 4: MeshCore LR2021 Radio Migration (NEEDS DQ05)

**Goal:** MeshCore currently uses RadioLib's LR2021 driver (broken per ADR-020). Replace with a MeshCore Radio interface adapter backed by `lr2021_transport`.

**Tasks:**
1. Create `Lr2021MeshCoreRadio` — implements `mesh::Radio` interface using `lr2021_transport` raw SPI calls.
2. Replace `LR2021* radio` and `new Module(...)` in `app_main.cpp` MeshCore section.
3. Build firmware on DQ05, verify compilation.
4. Verify MeshCore initialization sequence works with raw SPI (set frequency, modulation, sync word via 2-byte opcodes instead of RadioLib API).

**Deliverable:** MeshCore builds + initializes using raw LR2021 SPI. No RadioLib dependency for radio.
**Estimated time:** 8-10 hours
**Needs DQ05:** YES
**Needs hardware:** NO (compile + init logic)

**Risk:** MeshCore's Radio interface may require RadioLib-specific types. May need to stub or shim the interface. Investigate `EspIdfInterfaces.h` for existing adapter patterns.

---

### Phase 5: Two-Node Hardware Integration Test (NEEDS DQ05 + HARDWARE)

**Goal:** Two ESP32-C3 + LR2021 nodes complete Noise IK handshake over FLRC radio, exchange encrypted telemetry.

**Tasks:**
1. Flash initiator firmware on Node A (DQ05 build).
2. Flash responder firmware on Node B (DQ05 build).
3. Configure both for FLRC-2600 (2.4 GHz, proven modulation from walk tests).
4. Run: Node A initiates handshake → Node B responds → both reach ESTABLISHED state.
5. Exchange: GPS telemetry (28 bytes) + test datagram (200 bytes) bidirectionally.
6. Capture logic analyzer trace of SPI bus during handshake (verify opcodes on wire).
7. Measure: handshake latency, PER, RSSI at 1m / 5m / 10m.

**Deliverable:** Two-node FIPS-over-LR2021 demo. Logic analyzer capture. Performance metrics.
**Estimated time:** 1 full day (build + flash + test + capture + analyze)
**Needs DQ05:** YES
**Needs hardware:** YES — 2x ESP32-C3, 2x LR2021 modules, logic analyzer

**Prerequisites:** Phases 1-4 complete. Felix confirms hardware availability.

---

### Phase 6: Memory Profiling + Production Readiness (NEEDS DQ05)

**Goal:** Verify ESP32-C3 memory budget. Prepare for first flight.

**Tasks:**
1. Build firmware with all components enabled (meshcore + fips_transport + lr2021_transport + wirehair + stratorelay + tdma).
2. Measure static DRAM usage — target: <280KB of 400KB total (leave 120KB heap).
3. Measure stack usage during Noise handshake (most stack-intensive operation).
4. Profile worst-case: MeshCore relay + FIPS handshake + fragmentation simultaneously.
5. Verify GPS + telemetry + mesh can coexist within RAM budget.
6. Write memory budget report.

**Deliverable:** Memory budget report. Go/no-go for flight firmware.
**Estimated time:** 4-6 hours
**Needs DQ05:** YES (heap tracing, ESP-IDF size analysis)
**Needs hardware:** NO

**This completes task B.7.13-B.7.15 from the mesh-stack roadmap.**

---

## Dependency Graph

```
Phase 1 (host) ──────────────────┐
                                  ├──→ Phase 3 (host) ──┐
Phase 2 (DQ05) ──────────────────┘                      │
                                                         ├──→ Phase 5 (DQ05+HW)
Phase 4 (DQ05) ─────────────────────────────────────────┘         │
                                                                    ▼
                                                           Phase 6 (DQ05)
```

**Parallelizable:** Phase 1 and Phase 2 can run in parallel (host work vs DQ05 work).
Phase 4 can start after Phase 2 (both modify app_main / radio layer).

**Critical path:** Phase 1 → Phase 3 → Phase 5 → Phase 6

## DQ05 Dependency Summary

| Phase | DQ05? | Hardware? | Can Start Now? |
|-------|-------|-----------|----------------|
| 1 | NO | NO | YES |
| 2 | YES | NO | When DQ05 back |
| 3 | NO | NO | YES (after P1) |
| 4 | YES | NO | When DQ05 back (after P2) |
| 5 | YES | YES | When DQ05 back + hardware allocated |
| 6 | YES | NO | After P2 + P4 |

## Hardware Requirements

- Phase 5 needs: 2x ESP32-C3 boards, 2x LR2021 modules (FLRC-capable), logic analyzer (8ch 24MHz), jumper wires
- Felix is replacing RP2040 on the 2W board today. That board is for range-tests, not my track. I need standard ESP32-C3 + LR2021 setups.

## Open Questions for Felix

1. **Hardware allocation:** When can 2x ESP32-C3 + 2x LR2021 modules be spared for Phase 5 integration test? (Not blocking until phases 1-4 done.)
2. **RadioLib removal scope:** Full removal from the repo, or just de-couple app_main? Some MeshCore code paths may still reference RadioLib types.
3. **Priority within phases:** Is Phase 4 (MeshCore migration) a priority, or focus on FIPS transport path (Phases 1-3 + 5) first for the two-node demo?
4. **Firmware language:** ADR-016 says keep C++/ESP-IDF. Confirm this still holds — all new work in C++.

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| RadioLib deeply embedded in MeshCore types | Phase 4 blocked | Investigate `EspIdfInterfaces.h` adapter pattern. May need shim layer. |
| ESP32-C3 RAM insufficient for all components | Phase 6 fails | StratoRelay budget: ~6.5KB. MeshCore: ~50KB. FIPS: ~4KB. Should fit in 400KB. |
| Raw SPI timing different from RadioLib | Phase 5 fails | Walk tests proved raw SPI works at 2600 kbps. Same opcodes. |
| DQ05 extended downtime | Phases 2,4,5,6 blocked | Phases 1,3 are host-only. Can do significant work without DQ05. |
