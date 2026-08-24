# Consultant Plan Review V3 — No-Hardware Phase

**Date:** 2026-08-05
**Status:** Complete
**Focus:** What can we do without physical boards?

---

## Executive Summary

Phase 0 and Phase 1 complete. Unified firmware builds for both C3 (301KB) and S3 (330KB). FreeRTOS 3-task architecture compiles and links. 433 host-side tests in CI. Relay pipeline integration test (12/12 pass) found critical bugs.

## Critical Issues Found & Fixed

### 1. Inverted nostr_event_deserialize() check [FIXED]
- **Bug:** `app_task.cpp` checked `== 0` for success, function returns >0 on success
- **Impact:** Events NEVER stored on real firmware
- **Fix:** Changed to `> 0` check
- **Commit:** dispatched

### 2. TollGate API mismatch [FIXED]
- **Bug:** app_task.cpp used invented function names (`tollgate_msg_encode`, `tollgate_msg_header_t`, `TOLLGATE_MSG_ACK`)
- **Actual API:** `tollgate_proto_encode`, `tollgate_msg_hdr_t`, `TG_MSG_ACK`
- **Also:** `CONFIG_ENABLE_TOLLGATE` missing from Kconfig — dead code
- **Fix:** Corrected all names, added Kconfig flag
- **Commit:** `cb49869`

### 3. Two incompatible nostr_event_t structs [IDENTIFIED]
- `nostr_store.h`: binary format, no signature field
- `nostr_event.h` (tollgate): string format, has signature field
- Need unification for Schnorr verification
- Status: identified, fix pending

### 4. radio_task blocking recv() [IDENTIFIED]
- Uses 5000ms blocking `recv()` — can't check tx_queue during this time
- Architecture doc called for IRQ-driven via DIO9
- Status: identified, refactor pending

### 5. MockLr2021Radio exists [OPPORTUNITY]
- Host-compilable mock already in lr2021_spi.h
- Enables full pipeline testing without hardware
- Status: relay pipeline test created (12/12 pass)

## Top 3 Actions Without Boards

1. **Fix nostr_event_t to add signature field** — enables Schnorr verification, unifies the two structs
2. **Refactor radio_task to IRQ-polling** — replace 5000ms blocking recv() with short-timeout poll + tx_queue check
3. **Add lr2021_transport tests to CI** — 4 suites covered, transport not yet

## Phase 3-4 Prep (No Boards)

- Host-side round-trip tests: serialize → mock_tx → mock_rx → deserialize → store_verify
- TollGate API names fixed, Kconfig flag added
- Mock-based test exercises full app_task switch-case logic
- All prep done — when boards arrive, flash + run

## S3 vs C3 Strategy

Develop on S3 (16MB flash, 8MB PSRAM, boards available). Compile for C3 in CI. Separate sdkconfigs, same code. Port to C3 as flight target.

## Binary Size

301KB (C3) → 330KB (S3): expected. S3 has larger HAL drivers, WiFi/BLE libs, PSRAM init. Both >69% free. Not a concern.