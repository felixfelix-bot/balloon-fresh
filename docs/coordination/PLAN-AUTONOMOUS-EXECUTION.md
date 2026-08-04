# Balloon Project — Autonomous Execution Plan
## Work That Requires NO Felix Action

**Created:** 2026-08-05
**Constraint:** Everything in this plan can be executed by the orchestrator + sub-managers WITHOUT Felix touching hardware, procuring parts, or making decisions. All host-side build/test/integration work.
**Repo:** ~/repos/balloon-fresh/ (master branch)

---

## Guiding Principles

1. **Every task produces a commit + push.** No exceptions.
2. **Every task has a clear definition of done** (build passes, tests pass, artifact exists).
3. **Tasks are ordered by critical path** — upstream tasks unblock downstream work.
4. **No board access required.** If a task needs /dev/ttyACMx, it doesn't belong here.
5. **No new decisions.** All tasks follow existing ADRs (ADR-016, 020, 024, 025).

---

## PHASE 1: BUILD INFRASTRUCTURE UNBLOCK (1-2 hours)
### Goal: Get all mesh components compiling together in one build

### Task 1.1: Create mesh_adapter/CMakeLists.txt
- **Problem:** `mesh_adapter` component has no CMakeLists.txt. Any track enabling `CONFIG_ENABLE_MESH=y` gets a build failure.
- **Action:** Write CMakeLists.txt that declares mesh_adapter as an ESP-IDF component, links fips_transport + lr2021_transport as dependencies.
- **Files:** `firmware/components/mesh_adapter/CMakeLists.txt` (new)
- **Done when:** `idf.py build` succeeds with CONFIG_ENABLE_MESH=y
- **Owner:** delegate to worker (leaf role)
- **Estimate:** 30 min

### Task 1.2: Wire fips_transport into main build
- **Problem:** fips_transport has its own CMakeLists, passes 17 tests standalone, but is never included in app_main or the main build.
- **Action:** Add fips_transport to the main component list in tracker/firmware/CMakeLists.txt. Verify it links.
- **Files:** `tracker/firmware/CMakeLists.txt`, possibly `tracker/firmware/main/main.cpp`
- **Done when:** `idf.py build` includes fips_transport symbols in final binary
- **Owner:** delegate to worker (leaf role)
- **Estimate:** 30 min
- **Depends on:** Task 1.1

### Task 1.3: Expand Blossom flash partition table
- **Problem:** Blossom firmware uses 95% of 1MB factory partition. Adding mesh components will overflow.
- **Action:** Update partitions.csv: factory 1MB→2MB, data 1MB→1.5MB. Verify total ≤ 4MB.
- **Files:** `firmware/blossom-server/partitions.csv`
- **Done when:** Build succeeds with expanded partition, binary < 2MB
- **Owner:** delegate to worker (leaf role)
- **Estimate:** 15 min

---

## PHASE 2: SHARED BLOCKER RESOLUTION (2-3 hours)
### Goal: Fix the 3 cross-cutting blockers that prevent multiple tracks from progressing

### Task 2.1: Implement nostr_event_deserialize()
- **Problem:** `nostr_event_deserialize()` is declared in `nostr_store.h` (line 54) but NEVER DEFINED. Serialize has no inverse. Blocks Nostr relay (can't receive events) and Blossom (shared dependency).
- **Action:** Implement the inverse of `nostr_event_serialize()`. Parse the custom binary format back into nostr_event_t struct. Write round-trip tests (serialize → deserialize → compare).
- **Files:** `tracker/firmware/components/nostr_store/nostr_store.c`, `tracker/firmware/components/nostr_store/test/test_deserialize.c`
- **Done when:** Round-trip test passes: serialize(event) → deserialize(buffer) → event' == event
- **Owner:** delegate to worker (leaf role)
- **Estimate:** 1-2 hours
- **Depends on:** None (can start immediately)

### Task 2.2: Measure secp256k1 flash footprint on ESP32-C3
- **Problem:** secp256k1 flash cost on C3 is UNMEASURED. This gates the decision: full Schnorr validation on balloon (needs ~50KB flash) vs ground-deferred validation (lighter, accepts unsigned events).
- **Action:** Create a minimal ESP-IDF project that links libsecp256k1, calls `secp256k1_ecdsa_verify()` once. Build it. Read `idf.py size` output. Report flash + DRAM.
- **Files:** `firmware/tests/secp_test/main/secp_test.c` (new), `firmware/tests/secp_test/CMakeLists.txt` (new)
- **Done when:** `idf.py size` prints secp256k1 .text + .rodata sizes, recorded in ADR
- **Owner:** delegate to worker (leaf role)
- **Estimate:** 45 min (first build >300s, use background)
- **Depends on:** None

### Task 2.3: Fix bloom hash spread in nostr_store
- **Problem:** Bloom filter uses `1 << (h1 % 8)` which only selects bit positions 0-7 within a byte. Higher false-positive rate than the 64-byte bitfield implies.
- **Action:** Change to `1 << (h1 % 64)` (full bitfield range) or `bitfield[h1 % 64 / 8] |= (1 << (h1 % 8))`.
- **Files:** `tracker/firmware/components/nostr_store/nostr_store.c`
- **Done when:** Updated bloom test passes with verified spread across all 64 bits
- **Owner:** delegate to worker (leaf role)
- **Estimate:** 15 min

---

## PHASE 3: MESH TRANSPORT INTEGRATION (3-4 hours)
### Goal: Connect the FIPS mesh adapter to all 4 software tracks

### Task 3.1: Wire ehash_radio_stub → LR2021 transport
- **Problem:** PoW relay's radio is a stub (`ehash_radio_stub.c`). All TX/RX is mocked.
- **Action:** Replace stub with real lr2021_transport calls. Create `ehash_radio_lr2021.c` that implements the same interface but calls lr2021_transport_send/recv. Keep stub for unit tests.
- **Files:** `mesh-stack/ehash-relay/ehash_radio_lr2021.c` (new), update Makefile/CMakeLists
- **Done when:** ehash-relay compiles against lr2021_transport; existing 8 unit tests still pass with stub; new integration test uses lr2021 transport mock
- **Owner:** delegate to worker (leaf role)
- **Estimate:** 1 hour
- **Depends on:** Task 1.2

### Task 3.2: Design Blossom datagram protocol adapter
- **Problem:** HTTP/TCP doesn't work over LoRa datagram mesh. Need compact binary protocol.
- **Action:** Create `blossom_datagram.h` + `blossom_datagram.c` with 3 message types: BLOB_PUT (1-byte type + 32-byte SHA256 + payload), BLOB_GET (1-byte type + 32-byte SHA256), BLOB_ACK (1-byte type + status). Fragment large blobs using existing fragmentation layer.
- **Files:** `firmware/blossom-server/blossom_datagram.h` (new), `firmware/blossom-server/blossom_datagram.c` (new)
- **Done when:** Compiles standalone, unit test for encode/decode round-trip passes
- **Owner:** delegate to worker (leaf role)
- **Estimate:** 1.5 hours
- **Depends on:** Task 1.1

### Task 3.3: Port wisp-esp32 storage_engine for C3
- **Problem:** Nostr relay needs persistent storage. Current nostr_store is RAM-only (606KB, doesn't fit). wisp-esp32 has `storage_engine.c` with LittleFS + NVS that could work.
- **Action:** Copy storage_engine.c to new component. Modify: cap at 256 events × 52-byte packed index (~13KB). Add LittleFS partition to tracker firmware partition table.
- **Files:** `tracker/firmware/components/nostr_persistent/storage_engine.c` (new, adapted), `tracker/firmware/components/nostr_persistent/CMakeLists.txt` (new)
- **Done when:** Component compiles standalone, query_events(filter) works with test data
- **Owner:** delegate to worker (leaf role)
- **Estimate:** 1.5 hours
- **Depends on:** Task 2.1 (needs deserialize for round-trip)

---

## PHASE 4: TEST COVERAGE + VERIFICATION (2-3 hours)
### Goal: Prove the software stack works, not just compiles

### Task 4.1: Tollgate payment protocol unit tests
- **Problem:** C3 extraction has protocol encode/decode verified but no formal test suite.
- **Action:** Write unit tests for: PAY encode/decode, ACK encode/decode, NACK encode/decode, STATUS query, REVOKE message. Test edge cases: malformed tokens, expired proofs, double-spend attempt.
- **Files:** `mesh-stack/tollgate/test/test_payment_protocol.c` (new)
- **Done when:** ≥ 15 test cases pass, covering all message types + edge cases
- **Owner:** delegate to worker (leaf role)
- **Estimate:** 1 hour
- **Depends on:** None

### Task 4.2: 3-hop relay simulation (PoW)
- **Problem:** E-hash relay designed for multi-hop but only tested single-node.
- **Action:** Write a Python simulation: ground_station → balloon1_relay → balloon2_relay → upstream_pool. Use ehash-bridge stratum server + mock radio links. Verify: templates propagate downlink, nonces propagate uplink, credit accrues at each hop, TTL expiry works.
- **Files:** `mesh-stack/ehash-bridge/test/test_3hop_relay.py` (new)
- **Done when:** Simulation runs 100 templates, 1000 nonces, 0 packet loss in ideal conditions, credit balances correct at each node
- **Owner:** delegate to worker (leaf role)
- **Estimate:** 1.5 hours
- **Depends on:** Task 3.1

### Task 4.3: FIPS test crate repair
- **Problem:** FIPS test crate has 20 compile errors. Uses old SPI API instead of balloon-hermes 2-byte opcode protocol.
- **Action:** Fix test crate to use lr2021_transport API (not raw SPI). Update imports. Fix mock radio to use transport callbacks.
- **Files:** Worktree: ~/worktrees/balloon-fips/ (or balloon-fips-fresh)
- **Done when:** `cargo test` passes (0 compile errors, all tests green)
- **Owner:** delegate to worker (leaf role)
- **Estimate:** 1 hour
- **Depends on:** None

---

## PHASE 5: DOCUMENTATION + TRACKING HYGIENE (1 hour)
### Goal: Clean up stale docs so the next session starts clean

### Task 5.1: Update 4 missing assessment status files
- **Problem:** 4 tracks (nostr, pow, range-tests, speed-tests) never submitted formal assessments. COORDINATOR-TRACKING.md is stale.
- **Action:** Generate INTEGRATION-ASSESSMENT.md for each from git logs + existing status files. Update COORDINATOR-TRACKING.md.
- **Done when:** 10/10 tracks have assessments in COORDINATOR-TRACKING.md
- **Owner:** delegate to worker (flash model)
- **Estimate:** 30 min

### Task 5.2: Record secp256k1 measurement in ADR
- **Action:** Create ADR-026: "Schnorr Validation Strategy on ESP32-C3" with the measurement from Task 2.2.
- **Done when:** ADR committed, decision recorded: full Schnorr vs deferred
- **Owner:** orchestrator (design decision)
- **Depends on:** Task 2.2

### Task 5.3: Clean uncommitted state in balloon-fresh
- **Problem:** `git status` shows 6 modified + 7 untracked files from various work sessions.
- **Action:** Review each file. Commit relevant changes, discard cruft.
- **Done when:** `git status` is clean
- **Owner:** delegate to worker (flash model)
- **Estimate:** 15 min

---

## EXECUTION ORDER

```
Phase 1 (build infra)     ──────►  Phase 2 (blockers)  ──────►  Phase 3 (mesh)
  1.1 mesh CMakeLists              2.1 deserialize()              3.1 ehash radio
  1.2 wire fips                    2.2 secp measure               3.2 blossom datagram
  1.3 blossom partition            2.3 bloom fix                  3.3 nostr persistent
                                                                   │
Phase 5 (docs)  ◄──────────────────────────────  Phase 4 (tests)
  5.1 assessments                             4.1 tollgate tests
  5.2 ADR-026                                 4.2 3-hop sim
  5.3 git clean                               4.3 FIPS crate fix
```

**Parallelism:** Phase 1 and Phase 2 Tasks 2.1/2.2 can run in parallel (different files). Phase 4 can overlap with Phase 3 tail end.

**Total estimated time:** 9-13 hours of worker time (can be parallelized to ~4-5 hours wall time with 3 concurrent workers).

---

## DEFINITION OF DONE (for entire plan)

- [ ] All builds pass (`idf.py build` for tracker + blossom, `cargo test` for FIPS)
- [ ] All existing tests still pass (no regressions)
- [ ] New tests written and passing (≥ 50 new test cases total)
- [ ] mesh_adapter wired into main build with CMakeLists.txt
- [ ] nostr_event_deserialize() implemented and round-trip tested
- [ ] secp256k1 flash size measured and ADR-026 written
- [ ] ehash relay uses lr2021_transport (not stub)
- [ ] Blossom datagram protocol designed and unit-tested
- [ ] nostr persistent storage component compiles on C3
- [ ] FIPS test crate compiles and passes
- [ ] 10/10 track assessments submitted
- [ ] git status clean, all work committed + pushed to GitHub

---

## RISKS AND MITIGATIONS

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ESP-IDF build takes >300s (timeout) | HIGH | Delays | Use background tasks, notify_on_complete |
| secp256k1 too large for C3 partition | MEDIUM | High | Fallback: event-ID hash only, defer Schnorr to ground |
| Mesh components conflict in same build | MEDIUM | Medium | Build incrementally: one component at a time |
| Partition table expansion breaks OTA | LOW | Low | V1 doesn't use OTA; note for future |
| FIPS Rust test crate needs nightly | LOW | Medium | Check rust-toolchain.toml, pin version |

---

## WHAT THIS PLAN DOES NOT INCLUDE (Requires Felix)

- MCU swap on 2W board (hardware)
- Any board flashing or serial testing
- BMP280 wiring
- Antenna soldering
- Helium procurement
- Solar cell sourcing
- JLCPCB order placement
- Physical balloon preparation
- Any design decisions not covered by existing ADRs
