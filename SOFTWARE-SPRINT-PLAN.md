# Software Sprint Plan: Full Stack Integration + Research

## Overview

Prove the full mesh protocol stack works end-to-end in software (no hardware needed),
then extend existing components and produce documentation/research artifacts.

**Current status: 72/72 tests passing. Target: ~87 tests + 3 new files.**

Run all tests:
```bash
python -m pytest tests/ -v
```

---

## Phase 1: Prove the Full Stack End-to-End

### W1: FIPS handshake roundtrip host tests
- [ ] Add `test_state_guards` to `test_fips.cpp` — encrypt/decrypt reject when state != ESTABLISHED
- [ ] Add `test_max_payload_boundary` to `test_fips.cpp` — 222 bytes ok, 223 bytes fail
- [ ] Add `test_corrupt_ciphertext` to `test_fips.cpp` — post-handshake AEAD tamper detected
- [ ] Verify all 13/13 FIPS tests pass via pytest

### W2: FIPS + Pipeline integration test
- [ ] Create `tracker/firmware/components/pipeline/test/test_pipeline_fips.cpp`
- [ ] Test: keygen → handshake → encrypt → pipeline fragment → reassemble → decrypt → verify
- [ ] Test: handshake messages (MSG1/MSG2) through pipeline with small frag_size
- [ ] Test: simulate loss of 1 fragment, recovery via erasure redundancy
- [ ] Create `tracker/firmware/components/pipeline/test/Makefile.fips`
- [ ] Add `TestPipelineFIPS` to `tests/test_c_host.py`
- [ ] Verify passing

### W3: Nostr → FIPS → Pipeline adapter (new component)
- [ ] Create `tracker/firmware/components/mesh_adapter/mesh_adapter.h`
  - [ ] `mesh_adapter_send()` — Nostr event → serialize → FIPS encrypt → pipeline fragment → radio TX cb
  - [ ] `mesh_adapter_recv()` — radio RX → pipeline reassemble → FIPS decrypt → deserialize → nostr_store
- [ ] Create `tracker/firmware/components/mesh_adapter/mesh_adapter.cpp`
- [ ] Create `tracker/firmware/components/mesh_adapter/CMakeLists.txt`
- [ ] Create `tracker/firmware/components/mesh_adapter/test/test_mesh_adapter.cpp`
  - [ ] Full roundtrip: create event → send → simulate LoRa → receive → verify stored event
  - [ ] Test: multiple events through the adapter in sequence
- [ ] Add `TestMeshAdapter` to `tests/test_c_host.py`
- [ ] Verify passing

---

## Phase 2: Extend Existing Components

### W4: Pipeline loss recovery tests
- [ ] Add `test_loss_recovery_1_of_5` — drop 1 original frag, recover via redundancy
- [ ] Add `test_loss_recovery_2_of_7` — drop 2 frags from 7+3, recover
- [ ] Add `test_too_much_loss` — drop more than redundancy allows, verify failure
- [ ] Add `test_block_id_mismatch` — feed frag from wrong block, verify rejection
- [ ] Verify pipeline 9/9 tests pass

### W5: TDMA dual-band scheduler tests
- [ ] Add `test_dual_band_slot_allocation` — mix Sub-GHz and 2.4 GHz slots in one frame
- [ ] Add `test_band_switch_callback` — verify callback receives correct band per slot
- [ ] Add `test_contention_slots` — test TDMA_SLOT_CONTENTION type
- [ ] Add `test_beacon_slots` — test TDMA_SLOT_BEACON type
- [ ] Add `test_gps_pps_discipline` — simulate PPS pulse mid-frame, verify timing
- [ ] Verify TDMA 12/12 tests pass

---

## Phase 3: Documentation & Research

### W6: Protocol specification document
- [ ] Create `mesh-stack/protocol/SPEC.md`
- [ ] Define PHY modes and parameters (LoRa SF7-12, FLRC, GFSK)
- [ ] Define TDMA frame format (frame header, slot types, guard bands)
- [ ] Define fragment format with erasure coding metadata
- [ ] Define FIPS frame format (FMP header, AEAD envelope)
- [ ] Define Nostr message types over FIPS (EVENT, REQ, REPLY, OK)
- [ ] Define clock sync message format (GPS PPS + beacon)

### W7: Wirehair x86 benchmark
- [ ] Create `tools/wirehair_bench.c` — host-only benchmark
- [ ] Measure encode time for N=5..20 blocks of 80..240 bytes
- [ ] Measure decode time with 1-3 losses
- [ ] Output table of time and RAM per block count
- [ ] Extrapolate ESP32-C3 RISC-V performance from x86 results
- [ ] Write findings to benchmark output or markdown

### W8: MeshCore RadioLibWrapper study + LR2021 variant design
- [ ] Create `mesh-stack/research/meshcore-radiolib-wrapper-study.md`
- [ ] Study MeshCore's `RadioLibWrapper` class API and callbacks
- [ ] Design LR2021 variant: pin mapping, SPI config, dual-band switching
- [ ] Document init sequence differences from SX1262/SX1280
- [ ] Document power amp control (SKY66112 integration with MeshCore)
- [ ] Identify what needs to change vs what can be reused as-is

---

## Execution Order

| Order | Task | Depends On | Effort |
|-------|------|------------|--------|
| 1 | W1: FIPS roundtrip tests | — | 30 min |
| 2 | W4: Pipeline loss recovery | — | 1 hr |
| 3 | W2: FIPS+Pipeline integration | W1 | 1-2 hr |
| 4 | W3: Nostr→FIPS→Pipeline adapter | W2 | 2-3 hr |
| 5 | W5: TDMA dual-band | — | 1-2 hr |
| 6 | W6: Protocol spec | W2, W3 | 1-2 hr |
| 7 | W7: Wirehair benchmark | — | 1 hr |
| 8 | W8: MeshCore study | — | 1-2 hr |

## Commit Strategy

- Commit after each completed task (W1, W4, etc.)
- Push after each phase (Phase 1, Phase 2, Phase 3)

## Test Count Tracking

| Task | New Tests | Running Total |
|------|-----------|---------------|
| Baseline | — | 72 |
| W1: FIPS roundtrip | 3 | 75 |
| W2: FIPS+Pipeline | 3 | 78 |
| W3: Mesh adapter | 3 | 81 |
| W4: Pipeline loss | 4 | 85 |
| W5: TDMA dual-band | 5 | 90 |
| **Final** | **18** | **90** |
