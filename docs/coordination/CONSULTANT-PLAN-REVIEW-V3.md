# Consultant Plan Review V3 — No-Hardware Work Items

**Date:** 2026-08-05
**Reviewer:** Consultant subagent (deep code-level review)
**Status:** ACCEPTED — all findings actionable without hardware

---

## Critical Issues Discovered

### 1. Two incompatible `nostr_event_t` structs
- `nostr_store.h` (tracker firmware): binary format, `uint8_t id[32]`, `uint8_t pubkey[32]`, `uint16_t kind` — NO signature field
- `nostr_event.h` (tollgate/mesh-stack): string format, `char pubkey[65]`, `char id[65]`, `char sig[129]` — HAS signature field
- `app_task.cpp` uses the nostr_store version (no sig). This is why Schnorr verification is deferred.

### 2. TollGate API mismatch in `app_task.cpp`
- Code uses: `tollgate_msg_encode()`, `tollgate_msg_decode()`, `tollgate_msg_header_t`, `tollgate_msg_t`, `TOLLGATE_MSG_ACK`
- Actual API: `tollgate_proto_encode()`, `tollgate_proto_decode()`, `tollgate_msg_hdr_t`, `tollgate_msg_type_t`, `TG_MSG_ACK`
- `CONFIG_ENABLE_TOLLGATE` is NOT defined anywhere in Kconfig — entire tollgate block in app_task.cpp is dead code

### 3. `radio_task.cpp` blocking recv() design
- Uses `s_transport->recv()` with 5000ms timeout — radio_task can't check `tx_queue` for up to 5 seconds
- Architecture doc called for IRQ-driven `handle_irq()` — implementation uses polling
- Correct approach: GPIO interrupt on DIO9 (pin 5) with `xTaskNotifyWait()` or short-poll `handle_irq()`

### 4. `MockLr2021Radio` already exists
- Host-compilable mock in `lr2021_spi.h`, used by existing transport tests
- Enables full host-side integration testing without hardware

### 5. CI gap
- CI covers 4 test suites (nostr_store, tollgate, ehash, stratorelay) but NOT `lr2021_transport` tests

---

## Top 3 No-Hardware Actions (Priority Order)

1. **Fix TollGate API mismatch + wire `CONFIG_ENABLE_TOLLGATE` into Kconfig**
2. **Add signature field to `nostr_event_t` in nostr_store** — `uint8_t sig[64]` for Schnorr
3. **Build host-side integration test harness using `MockLr2021Radio`** — full relay pipeline test

## Additional No-Hardware Items

4. **Refactor radio_task from blocking recv() to IRQ-polling** with short timeout
5. **Add lr2021_transport tests to CI**
6. **Unify nostr_event_t format** — pick one (binary for flash efficiency) and convert

## Phase 3-4 Prep (Without Boards)

- Write host-side round-trip tests: `serialize → mock_tx → mock_rx → deserialize → store_verify`
- Fix tollgate API names and types in app_task.cpp
- Add `CONFIG_ENABLE_TOLLGATE` to Kconfig.projbuild
- Implement signature field in nostr_store's `nostr_event_t` and update serialize/deserialize
- Write mock-based test exercising full app_task switch-case logic

## Radio Task Design Recommendation

Current: `recv()` blocks 5000ms → can't service tx_queue
Recommended: `handle_irq()` or `poll_irq()` with short timeout, check `tx_queue` between polls
Best: GPIO interrupt on DIO9 (pin 5) with `xTaskNotifyWait()` as architecture doc specified

## Binary Size (Q6)

29KB difference (301KB C3 vs 330KB S3) is expected — S3 has larger HAL drivers, WiFi/BLE library code, PSRAM init. Both >69% flash free. Not a concern.

## S3 vs C3 Strategy (Q4)

Develop and test on S3 (16MB flash, 8MB PSRAM, boards available). Compile for C3 regularly in CI to catch target-specific issues. Same code, separate sdkconfigs. Port to C3 as flight target.