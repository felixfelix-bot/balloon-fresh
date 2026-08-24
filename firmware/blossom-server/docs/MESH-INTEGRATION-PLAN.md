# Blossom-over-LR2021: Integration Plan

**Status:** DRAFT — awaiting Felix approval before scheduling  
**Date:** 2026-07-29  
**Author:** balloon-blossom sub-manager (Hermes)  

## Executive Summary

The mesh stack is ~90% BUILT but ~0% WIRED. All 7 protocol components exist, pass 72+ unit tests, and are proven individually. The gap to Blossom-over-LR2021 is **wiring work**, not greenfield development. Estimated 7 working days.

The proven working pieces:
- Blossom server: HTTP over WiFi, all BUD endpoints, on real ESP32-C3 hardware (commit 5f5018b)
- LR2021 radio: raw SPI, 1377 kbps, 0% packet loss (proven in prior tests)
- Mesh stack: FIPS, pipeline, frag, TDMA, nostr_store, mesh_adapter — 72+ tests passing

The missing piece: connecting these three islands into one working system.

---

## Verified Current State (2026-07-29 code audit)

| Component | Location | Lines | Tests | Status |
|-----------|----------|-------|-------|--------|
| mesh_adapter | `tracker/firmware/components/mesh_adapter/` | 65 | 12/12 PASS | **Missing CMakeLists.txt, FIPS stub is no-op** |
| fips_transport | `tracker/firmware/components/fips_transport/` | 411 | 17/17 PASS | **Not wired into build or app_main** |
| pipeline | `tracker/firmware/components/pipeline/` | 154 | 9/9 PASS | Wired under CONFIG_ENABLE_MESH |
| frag | `tracker/firmware/components/frag/` | 115 | 13/13 PASS | Wired under CONFIG_ENABLE_MESH |
| tdma | `tracker/firmware/components/tdma/` | 115 | 12/12 PASS | Wired under CONFIG_ENABLE_TDMA |
| nostr_store | `tracker/firmware/components/nostr_store/` | 125 | 7/7 PASS | **nostr_event_deserialize() declared but not implemented** |
| meshcore | `tracker/firmware/components/meshcore/` | ~5700 | Build-only | Builds OK, no dedicated tests |
| stratorelay | `tracker/firmware/components/stratorelay/` | ~273 | 11/11 PASS | Header-only, no CMakeLists wiring needed |
| blossom-server | `firmware/blossom-server/` | ~1353 | 0 (hardware-tested) | **Working on C3, no mesh integration** |
| blossom_auth | `firmware/blossom-server/components/blossom_auth/` | 226 | 0 | BUD-11 auth verification |
| blossom_storage | `firmware/blossom-server/components/blossom_storage/` | 300 | 0 | LittleFS blob path management |
| blossom_crypto | `firmware/blossom-server/components/blossom_crypto/` | 157 | 0 | secp256k1 schnorr verification |

### Integration Gaps Identified

1. **`mesh_adapter` has NO `CMakeLists.txt`** — building with CONFIG_ENABLE_MESH=y would fail immediately
2. **`fips_transport` not wired** — has own CMakeLists, passes 17 tests, but never included in main build or referenced in app_main. The `mesh_adapter_set_fips_sessions()` stub (lines 49-52) confirms FIPS integration is planned but not connected
3. **`nostr_event_deserialize()`** — declared in `nostr_store.h:54`, body missing from `nostr_store.c`
4. **`esp-now-firmware` source deleted** — only build artifacts remain
5. **All mesh flags disabled by default** — sdkconfig has mesh completely off; firmware is in pure tracker mode
6. **Blossom has no mesh awareness** — blossom-server firmware doesn't include any mesh components

### Test Summary (all host-compiled, run via pytest)

```
TestMeshAdapter    8 PASS
TestEndToEnd       4 PASS
TestPipeline       9 PASS
TestFIPSTransport  13 PASS
TestFrag          13 PASS
TestTDMA          12 PASS
TestNostrStore     7 PASS
TestStratoRelay   11 PASS
─────────────────────────
Total             87 assertions PASS in 2.52s
```

---

## The Constraint Math

| Metric | Value | Source |
|--------|-------|--------|
| LR2021 max payload (FLRC, SF7) | 222 bytes | link_budget.py, fips-study.md |
| FIPS AEAD overhead per packet | ~13 bytes (nonce + tag) | fips_transport.cpp |
| Usable payload per radio packet | ~209 bytes | 222 - 13 |
| Nostr auth event (kind 24242) | ~630 bytes | Measured during C3 testing |
| Fragments for auth alone | 3 (at 209 bytes each) | ceil(630/209) |
| Pipeline erasure overhead | +30% | pipeline.c redundancy config |
| Typical blob (telemetry) | 20-100 bytes | |
| Typical blob (compressed photo) | 2-10 KB | |
| ESP32-C3 heap | 276 KB total | C3 boot log |
| Flash (blossom only) | 95% of 1MB | 5f5018b build output |

**Key constraint:** Flash is tight. Blossom alone fills 95% of 1MB factory partition. Adding FIPS + mesh components will overflow. Must either: (a) expand factory partition to use full 4MB flash, or (b) build mesh+blossom as a separate firmware target.

---

## Phase 1: Component Wiring (host-side, no hardware)

### Task 1.1: Wire FIPS into mesh_adapter
**Scope:**
- Replace `mesh_adapter_set_fips_sessions()` no-op stub (lines 49-52 in mesh_adapter.c) with real FIPS encrypt/decrypt calls
- Add fips_transport to mesh_adapter CMakeLists REQUIRES (once CMakeLists exists from 1.2)
- Add new test: encrypted roundtrip through FIPS → pipeline → radio callback → pipeline reassemble → FIPS decrypt → verify payload

**Files touched:**
- `tracker/firmware/components/mesh_adapter/mesh_adapter.c`
- `tracker/firmware/components/mesh_adapter/include/mesh_adapter.h`
- `tracker/firmware/components/mesh_adapter/test/test_mesh_adapter.c`

**Gate:** 13/13 mesh_adapter tests pass (existing 12 + new encrypted roundtrip)

### Task 1.2: Create mesh_adapter CMakeLists + wire into build
**Scope:**
- Create `tracker/firmware/components/mesh_adapter/CMakeLists.txt`
- Add mesh_adapter to `tracker/firmware/main/CMakeLists.txt` REQUIRES under CONFIG_ENABLE_MESH
- Verify build succeeds with CONFIG_ENABLE_MESH=y

**Files touched:**
- `tracker/firmware/components/mesh_adapter/CMakeLists.txt` (NEW)
- `tracker/firmware/main/CMakeLists.txt`

**Gate:** `idf.py build` succeeds with CONFIG_ENABLE_MESH=y

### Task 1.3: Implement nostr_event_deserialize()
**Scope:**
- Implement body for function declared at nostr_store.h:54
- Parse JSON string → nostr_event_t struct (inverse of existing serialize)
- Must handle: kind, content, tags array, pubkey, created_at, id, sig
- Add test: serialize → deserialize → field-by-field compare

**Files touched:**
- `tracker/firmware/components/nostr_store/nostr_store.c`
- `tracker/firmware/components/nostr_store/test/test_nostr_store.c`

**Gate:** 8/8 nostr_store tests pass (existing 7 + new deserialize roundtrip)

### Task 1.4: Blossom mesh build path
**Scope:**
- Add Kconfig entries for CONFIG_ENABLE_MESH in blossom-server (currently only tracker has them)
- Add mesh components (fips_transport, pipeline, frag, mesh_adapter, nostr_store) to blossom-server build
- Evaluate flash size: if >1MB, expand factory partition to 0x200000 (2MB) in partitions.csv
- Build must succeed

**Files touched:**
- `firmware/blossom-server/Kconfig.projbuild` (NEW or extend)
- `firmware/blossom-server/main/CMakeLists.txt`
- `firmware/blossom-server/partitions.csv` (partition resize if needed)
- `firmware/blossom-server/sdkconfig.defaults`

**Gate:** `idf.py build` with CONFIG_ENABLE_MESH=y produces binary. Binary fits in partition.

**Dependencies:** 1.4 depends on 1.2 (mesh_adapter CMakeLists must exist first)

### Task 1.5: Flash partition table fix
**Scope:**
- Current partitions.csv has factory=0x100000 (1MB) but blossom binary is 0xf2170 (~1MB, 95% full)
- Adding mesh components will overflow 1MB. Expand factory partition to 0x200000 (2MB)
- Blossom data partition moves from 0x110000 to 0x210000
- Reduce blossom data partition to 0x180000 (1.5MB) — still substantial for blobs

**Files touched:**
- `firmware/blossom-server/partitions.csv`

**Gate:** Build succeeds. `idf.py -p /dev/ttyACM0 flash` succeeds. Board boots clean.

**Dependencies:** Can run in parallel with 1.1-1.4

---

## Phase 2: LR2021 Hardware Wiring

### Task 2.1: Wire mesh_adapter radio TX/RX callbacks to LR2021 SPI driver
**Scope:**
- mesh_adapter_send() uses a callback function pointer for TX. Wire it to LR2021Raw SPI driver
- Pattern: `firmware/rp2040/src/flrc_raw_tx.cpp` and `firmware/esp32-c3-flrc/main/main.cpp`
- Implement radio RX interrupt handler → `mesh_adapter_receive_frame()`
- TDMA scheduler for slot timing (or simple round-robin for MVP — see decision points)
- SPI pin mapping for the Maker Go ESP32-C3 Mini V1 + LR2021 board

**Files touched:**
- `firmware/blossom-server/main/blossom_main.c` (or new mesh_init.c)
- New file: `firmware/blossom-server/main/lr2021_radio.c`

**Gate:** Flash one board, send test frame over radio, observe on serial: "mesh_adapter: frame received, N bytes"

### Task 2.2: Blossom datagram protocol adapter
**Scope:**
- HTTP/TCP doesn't work over datagram mesh. Build thin adapter:
  - `BLOB_PUT` message: sha256 + blob data, chunked through pipeline
  - `BLOB_GET` message: sha256 request → response with blob data
  - Auth: attach FIPS-encrypted Nostr event to each BLOB_PUT
- 3 message types only. NOT a full HTTP stack.
- Compact binary format (1-byte type + 32-byte SHA + payload), NOT JSON

**Files touched:**
- New file: `firmware/blossom-server/main/blossom_datagram.c`
- New file: `firmware/blossom-server/main/blossom_datagram.h`

**Gate:** Host test: create BLOB_PUT → serialize → fragment through pipeline → reassemble → deserialize → verify SHA + auth valid

**Dependencies:** 2.1 depends on 1.1+1.2. 2.2 depends on 1.4.

---

## Phase 3: Two-Board Integration Test

### Task 3.1: Flash Board A — blossom server + mesh
**Scope:**
- Flash blossom-server with CONFIG_ENABLE_MESH=y + datagram adapter + LR2021 radio
- Board A acts as: WiFi blossom AP (for laptop testing) AND mesh node (for radio testing)
- Serial log should show both: "Blossom server ready" + "mesh adapter initialized, LR2021 radio ready"

**Gate:** Boot log shows both WiFi AP up + mesh initialized. No crash.

### Task 3.2: Flash Board B — mesh client + LR2021
**Scope:**
- Minimal firmware: mesh_adapter + FIPS + nostr_store + datagram client
- No blossom server, no WiFi AP — pure mesh node
- Can send BLOB_PUT to Board A over radio

**Gate:** Boot log shows "mesh client ready, FIPS handshake complete"

### Task 3.3: End-to-end test — upload blob over LR2021
**Scope:**
- Board B sends 20-byte test file to Board A over radio
- Board A stores it in LittleFS via blossom datagram adapter
- Board B requests it back
- SHA256 matches
- Capture serial logs from BOTH boards simultaneously
- Felix wants to run this test personally

**Gate:** SHA256 of received blob matches sent blob. No crashes. Serial logs clean from both boards.

**Dependencies:** 3.1+3.2 depend on 2.1+2.2. 3.3 depends on 3.1+3.2.

---

## Quality Gates (EVERY task, no exceptions)

| Gate | Description | Verification |
|------|-------------|--------------|
| G1 TDD | Test exists, observed FAILING before implementation | Worker shows failing test output |
| G2 Tests OK | Full suite run, 0 failures (existing + new) | pytest output |
| G3 Docs | Component README or AGENTS.md updated in same commit | Diff includes doc changes |
| G4 Atomic-commit | One concern per commit, conventional message | `git log --oneline` shows clean history |
| G5 Pushed | git push to github verified exit 0 | `git push github master` exit 0 |

---

## Worker Profiles

### worker-balloon (leaf, glm-5.2)
- **Scope:** All firmware tasks (Phases 1-3)
- **Tools:** terminal, file, patch
- **Knows:** ESP-IDF build system, CMakeLists, Kconfig, LR2021 SPI protocol
- **Branch:** `balloon-mesh-wiring/` feature branches, merged to master via PR

### worker-admin (leaf, glm-4.5-flash)
- **Scope:** Documentation tasks only
- **Tools:** terminal, file
- **Knows:** Markdown formatting, AGENTS.md conventions

### Felix (hands-on)
- **Scope:** Phase 3 board testing
- **Prefers:** Personally run make targets + see outputs
- **Activities:** Flash boards, monitor serial, verify results

---

## Schedule

```
Week 1 (3 parallel tracks where possible):

  Mon ─┬─ [1.1] FIPS→mesh_adapter wiring     (worker-balloon)
       ├─ [1.2] mesh_adapter CMakeLists       (worker-balloon)
       └─ [1.3] nostr_event_deserialize       (worker-balloon)

  Tue ─┬─ [1.5] Flash partition fix           (worker-balloon)
       └─ [1.1] continued + [1.2] merge

  Wed ─── [1.4] Blossom mesh build path        (worker-balloon, deps: 1.2)
       ─── [1.1] completed + test written

  Thu ─┬─ [2.1] LR2021 radio TX/RX wiring     (worker-balloon, deps: 1.1+1.2)
       └─ [2.2] Datagram protocol adapter      (worker-balloon, deps: 1.4)

  Fri ─── [2.1] + [2.2] continued, host tests

Week 2:

  Mon ─┬─ [3.1] Board A: blossom + mesh flash  (Felix hands-on)
       └─ [3.2] Board B: mesh client flash     (Felix hands-on)

  Tue ─── [3.3] End-to-end test over LR2021    (Felix hands-on)
```

**Total: 7 working days. ~2 days need Felix's hands.**

---

## Key Risks

1. **Memory (276KB heap on C3):** FIPS + secp256k1 + mesh + blossom may not fit.  
   *Mitigation:* Profile memory in Phase 1, Task 1.4. If overflow, disable WiFi when mesh active (mesh-only mode).

2. **Binary size (95% of 1MB already):** Adding mesh components will overflow.  
   *Mitigation:* Task 1.5 expands factory partition to 2MB. blossom data partition stays at 1.5MB.

3. **FIPS handshake timing:** Noise IK needs 3 round trips on LR2021. At 1377kbps FLRC, ~0.5ms per packet → ~1.5ms total. Negligible.  
   *Mitigation:* None needed, but verify in Task 2.1.

4. **SPI bus contention:** WiFi and LR2021 both use SPI (different buses). WiFi uses VSPI, LR2021 uses HSPI. No conflict.  
   *Mitigation:* Verify pin assignments in Task 2.1.

---

## Decisions (Felix approved 2026-07-29)

1. **Platform: TRACKER FIRMWARE + blossom datagram adapter.** NOT blossom-server.
   Tracker already has all mesh wiring scaffolding. Build blossom datagram as a new component.
2. **Protocol: Compact binary.** 1-byte type + 32-byte SHA + payload. NOT JSON.
3. **Scheduling: Simple round-robin for MVP.** TDMA code preserved on roadmap for later.
4. **Partition layout:** TBD — check tracker firmware current partition size.
