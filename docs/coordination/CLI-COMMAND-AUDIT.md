# CLI Command Audit — balloon-fresh/tracker/firmware

**Date:** 2026-08-05
**Auditor:** worker-balloon (kanban task t_3a5a143c)
**Branch:** autonomous/mesh-baseline
**Scope:** `~/repos/balloon-fresh/tracker/firmware/`

---

## Summary

| # | Command | Status | File:Line |
|---|---------|--------|-----------|
| 1 | `radio_test` | EXISTS | main/app_main.cpp:315 (handler), :404 (registration) |
| 2 | `radio_recv` | EXISTS | main/app_main.cpp:335 (handler), :405 (registration) |
| 3 | `relay_send_nostr` | IMPLEMENTED | main/app_main.cpp:403 (handler), :587 (registration) |
| 4 | `nostr_dump` | IMPLEMENTED | main/app_main.cpp:402 (handler), :490 (registration) |
| 5 | `tollgate_send_pay` | IMPLEMENTED | main/app_main.cpp (handler), setup_cli() (registration) |

**5 of 5 commands implemented.**

---

## Existing Commands

### 1. radio_test — EXISTS

- **Handler:** `cli_cmd_radio_test()` at `main/app_main.cpp:315`
- **Registration:** `main/app_main.cpp:404`
- **Help text:** "Transmit test packet"
- **Behavior:** Builds a `telemetry_packet_t` from current sensor data + callsign hash, serializes it, calls `s_radio->send_packet()`, waits for TX done with 10s timeout.
- **Dependencies:** `s_radio` (EspHalLr2021Radio), telemetry component, power_manager.
- **Notes:** Sends a raw telemetry packet (not a relay_packet_t). Uses direct radio API, not the relay queue infrastructure.

### 2. radio_recv — EXISTS

- **Handler:** `cli_cmd_radio_recv()` at `main/app_main.cpp:335`
- **Registration:** `main/app_main.cpp:405`
- **Help text:** "Listen for FLRC packets (30s)"
- **Behavior:** Puts radio into RX mode, polls IRQ for 30 seconds, reads packets on IRQ, prints hex + RSSI/SNR, validates telemetry packets if they match TELEMETRY_SIZE.
- **Dependencies:** `s_radio` (EspHalLr2021Radio), telemetry component.
- **Notes:** Uses direct radio API (not transport layer). Hardcoded 30s timeout. Does not route received packets through the relay pipeline (g_rx_queue).

---

## Missing Commands

### 3. relay_send_nostr — IMPLEMENTED

**Status:** Implemented (kanban task t_9b570899, 2026-08-05)
**Handler:** `cli_cmd_relay_send_nostr()` at `main/app_main.cpp:403`
**Registration:** `main/app_main.cpp:587`
**Guard:** `#if defined(CONFIG_ENABLE_RELAY_MODE) && defined(CONFIG_ENABLE_NOSTR_STORE)`

**Behavior:**
- Builds a `nostr_event_t` with deterministic test ID + pubkey (V1: no Schnorr sig)
- Parses optional args: `"<kind> <content>"` or just `"<content>"` (default: kind=1, "balloon relay test event")
- Calls `nostr_event_serialize()` into `pkt.data + 1` (skip type tag byte)
- Sets `pkt.data[0] = RELAY_TYPE_NOSTR_EVENT`, `pkt.len = serialized_len + 1`
- Queues to `g_tx_queue` via `xQueueSend()` with 100ms timeout
- `radio_task` drains the queue and TXes via FLRC transport

**Host-side test:** `main/test/test_relay_send_nostr.c` — 9/9 tests pass
- Default event, custom kind+content, tags, large content, oversized rejection, empty content, multi-queue, queue-full, and full round-trip through nostr_store

**Pitfalls handled:**
- `nostr_event_serialize()` returns 0 on error (content too big) → checked and error printed
- Content limited by relay packet cap (511 bytes), not NOSTR_MAX_CONTENT (480) — serialize fails gracefully
- `g_tx_queue` only exists in relay mode → guarded with `#if defined(CONFIG_ENABLE_RELAY_MODE)`
- `nostr_event_t` has sig field but V1 doesn't populate it — documented in comment block

---

### 4. nostr_dump — IMPLEMENTED

**Purpose:** Dump all stored Nostr events from the nostr_store to serial output.

**Status:** Implemented (kanban task t_c27101f0).

**Handler:** `cli_cmd_nostr_dump()` at `main/app_main.cpp:402`
**Registration:** `main/app_main.cpp:490`
**Help text:** "Dump stored Nostr events (optional count arg)"

**Implementation details:**
- **Store scoping refactor:** `nostr_store_t` moved from local var in `app_task()` to file-static `s_nostr_store` in `app_task.cpp`. Accessor function `app_task_get_store()` (extern "C") returns pointer to the store, or NULL if not yet initialized.
- **Handler logic:** Calls `nostr_store_count()` to get N, loops i=0..N-1 calling `nostr_store_get(store, i, &event)`.
- **Output format:** `[idx] kind=<kind> ts=<created_at> len=<content_len> pub=<16 hex chars> <content>`
- **Content truncation:** Content shown up to 80 chars, with "..." suffix if longer. Non-printable bytes (outside 0x20-0x7E) replaced with '.' for safe terminal output.
- **Pagination:** Optional count arg (e.g., `nostr_dump 10` limits to first 10 events).
- **Guard:** `#ifdef CONFIG_ENABLE_NOSTR_STORE` around handler, registration, and accessor.

**Dependencies:**
- `nostr_store` component (EXISTS) — `nostr_store_count()`, `nostr_store_get()`, `nostr_event_t`
- `CONFIG_ENABLE_NOSTR_STORE=y` in sdkconfig (set)
- LittleFS mounted before app_task starts (handled by app_main boot sequence)

**Test:** `main/test/test_nostr_dump.c` — 6 host-side tests covering empty store, single event format, FIFO order, content truncation, pagination, and non-printable content sanitization. All pass.

---

### 5. tollgate_send_pay — IMPLEMENTED

**Purpose:** Encode a TollGate PAY message and send it via relay mode (queue to g_tx_queue with RELAY_TYPE_TOLLGATE_PAY tag).

**Status:** Implemented (kanban task t_999528b6).

**Implementation:**
- Created `main/tollgate_payment_proto.h` — standalone header with `tollgate_msg_hdr_t`, `tollgate_ack_payload_t`, `TG_MSG_PAY`/`TG_MSG_ACK`/etc., `tollgate_proto_encode()`/`tollgate_proto_decode()`. Wire-compatible with `mesh-stack/tollgate/components/tollgate_balloon/include/tollgate_payment_proto.h` (ADR-002). No ESP-IDF deps — host-testable with gcc.
- Created `main/tollgate_payment_proto.c` — encode/decode implementation.
- Added `cli_cmd_tollgate_send_pay()` handler in `app_main.cpp` — builds PAY message with `tollgate_proto_encode(TG_MSG_PAY, seq, payload, len)`, sets `pkt.data[0] = RELAY_TYPE_TOLLGATE_PAY`, queues to `g_tx_queue`.
- Registered in `setup_cli()` with `cli_register_command("tollgate_send_pay", ...)`.
- Guarded with `#ifdef CONFIG_ENABLE_TOLLGATE`.
- Enabled `CONFIG_ENABLE_TOLLGATE=y` in `sdkconfig.defaults.esp32s3`.
- Updated `main/CMakeLists.txt` — conditionally compiles `tollgate_payment_proto.c` when `CONFIG_ENABLE_TOLLGATE` is set.
- Updated `main/test/test_relay_pipeline.c` — replaced mock tollgate protocol with the real `tollgate_payment_proto.h` + real encode/decode functions.
- Created `main/test/test_tollgate_payment_proto.c` — 83 host unit tests (struct packing, encode basic/empty/overflow, decode valid/short/bad-version/truncated, round-trip all message types, ACK payload struct).
- Updated this audit doc.

**Tests:** 83/83 proto tests pass, 12/12 relay pipeline tests pass, 9/9 relay_send_nostr tests pass (no regressions).

**Dependencies (all met):**
- `tollgate_payment_proto.h` — CREATED at `main/tollgate_payment_proto.h`
- `relay_types.h` (EXISTS) — provides `RELAY_TYPE_TOLLGATE_PAY = 0x02`
- `g_tx_queue` (EXISTS) — FreeRTOS queue for outbound packets
- `CONFIG_ENABLE_TOLLGATE` — now SET in `sdkconfig.defaults.esp32s3`

---

## Infrastructure Summary

### CLI Framework
- **Component:** `components/cli/` — custom lightweight CLI (not esp_console)
- **Registration:** `cli_register_command(name, help, handler)` in `components/cli/cli.c:45`
- **Built-in:** `help` command (auto-registered in `cli.c:42`)
- **All app commands registered in:** `main/app_main.cpp:setup_cli()` (lines 395-407)

### Relay Mode Infrastructure
- **Queue-based:** `g_rx_queue` (8 slots) + `g_tx_queue` (4 slots), both `relay_packet_t`
- **radio_task.cpp:** Drains g_tx_queue → radio TX; polls radio RX → g_rx_queue
- **app_task.cpp:** Drains g_rx_queue → dispatches by type tag (NOSTR_EVENT, TOLLGATE_PAY, TELEMETRY, RAW)
- **Type tags:** `relay_types.h` — `RELAY_TYPE_NOSTR_EVENT=0x01`, `RELAY_TYPE_TOLLGATE_PAY=0x02`, `RELAY_TYPE_TOLLGATE_ACK=0x03`, `RELAY_TYPE_TELEMETRY=0x04`, `RELAY_TYPE_RAW=0xFF`

### Current Kconfig State (sdkconfig)
- `CONFIG_ENABLE_RELAY_MODE=y` — relay mode active
- `CONFIG_ENABLE_NOSTR_STORE=y` — nostr store active
- `CONFIG_ENABLE_TOLLGATE=y` — tollgate code is now compiled in (sdkconfig.defaults.esp32s3)

### Component Availability
| Component | Status | Relevant API |
|-----------|--------|-------------|
| `nostr_store` | EXISTS, built | `nostr_store_init/add/get/count/find`, `nostr_event_serialize/deserialize` |
| `secp256k1` | EXISTS, built | Schnorr verification (used in app_task for sig verify) |
| `stratorelay` | EXISTS, built | Cluster-head election, NodeTable — NOT the relay pipeline |
| `fips_radio_bridge` | EXISTS, built | FIPS framing over radio |
| `tollgate_payment_proto` | CREATED | `main/tollgate_payment_proto.h` + `.c` — standalone, wire-compatible with tollgate component |

---

## Follow-up Tasks — All Completed

1. ~~**P5: Implement `relay_send_nostr` CLI command**~~ — DONE (task t_9b570899)

2. ~~**P5: Implement `nostr_dump` CLI command**~~ — DONE (task t_c27101f0)

3. ~~**P6: Create `tollgate_payment_proto.h` + implement `tollgate_send_pay` CLI command**~~ — DONE (task t_999528b6)