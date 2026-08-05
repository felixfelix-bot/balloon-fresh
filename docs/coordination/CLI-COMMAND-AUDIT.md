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
| 3 | `relay_send_nostr` | MISSING | — |
| 4 | `nostr_dump` | IMPLEMENTED | main/app_main.cpp:402 (handler), :490 (registration) |
| 5 | `tollgate_send_pay` | MISSING | — |

**3 of 5 commands exist/implemented. 2 commands need to be implemented.**

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

### 3. relay_send_nostr — MISSING

**Purpose:** Serialize a Nostr event and send it via relay mode (queue to g_tx_queue with RELAY_TYPE_NOSTR_EVENT tag).

**Estimated implementation time:** 2-4 hours

**Complexity:** Medium

**Dependencies:**
- `nostr_store` component (EXISTS) — provides `nostr_event_t`, `nostr_event_serialize()`
- `relay_types.h` (EXISTS) — provides `relay_packet_t`, `RELAY_TYPE_NOSTR_EVENT`
- `g_tx_queue` (EXISTS in radio_task.cpp) — FreeRTOS queue for outbound packets
- `CONFIG_ENABLE_RELAY_MODE` must be set (currently `y` in sdkconfig)
- `CONFIG_ENABLE_NOSTR_STORE` must be set (currently `y` in sdkconfig)

**Implementation sketch:**
1. Add `cli_cmd_relay_send_nostr()` handler in `app_main.cpp`
2. Build a `nostr_event_t` (either from hardcoded test data or parse args for content/kind)
3. Call `nostr_event_serialize()` into `pkt.data + 1` (skip type tag byte)
4. Set `pkt.data[0] = RELAY_TYPE_NOSTR_EVENT`, `pkt.len = serialized_len + 1`
5. `xQueueSend(g_tx_queue, &pkt, ...)` to queue for radio_task TX
6. Register with `cli_register_command("relay_send_nostr", ...)`
7. Guard with `#ifdef CONFIG_ENABLE_RELAY_MODE`

**Pitfalls:**
- The `nostr_event_t` structure has no signature field populated — `app_task.cpp` stores events without sig verification (V1 integration). The CLI command should note this.
- `nostr_event_serialize()` returns 0 on error — must check.
- The serialized event must fit in `RELAY_PACKET_MAX_SIZE - 1` (511 bytes). `NOSTR_SER_BUF_SIZE` is 1024 but the relay packet max is 512, so content is effectively limited to ~480 bytes (matches `NOSTR_MAX_CONTENT`).
- `g_tx_queue` is only created in relay mode. The command registration must be guarded by `#ifdef CONFIG_ENABLE_RELAY_MODE` or it will crash if relay mode is disabled.

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

### 5. tollgate_send_pay — MISSING

**Purpose:** Encode a TollGate PAY message and send it via relay mode (queue to g_tx_queue with RELAY_TYPE_TOLLGATE_PAY tag).

**Estimated implementation time:** 4-8 hours

**Complexity:** High

**Dependencies:**
- `tollgate_payment_proto.h` — **DOES NOT EXIST**. Referenced in `app_task.cpp:33` via `#include "tollgate_payment_proto.h"` under `#ifdef CONFIG_ENABLE_TOLLGATE`, but the file is not found anywhere in the firmware tree.
- `relay_types.h` (EXISTS) — provides `RELAY_TYPE_TOLLGATE_PAY = 0x02`
- `g_tx_queue` (EXISTS) — FreeRTOS queue for outbound packets
- `CONFIG_ENABLE_TOLLGATE` — currently **NOT SET** in sdkconfig (line 576: `# CONFIG_ENABLE_TOLLGATE is not set`)
- The test file `main/test/test_relay_pipeline.c` has a **mock** tollgate protocol (line 75: "Mock tollgate protocol (tollgate_payment_proto.h doesn't exist yet)") with `build_tollgate_pay_packet()` that manually constructs a PAY packet.

**Implementation sketch:**
1. **First: create `tollgate_payment_proto.h`** — define `tollgate_msg_hdr_t`, `tollgate_ack_payload_t`, `TG_MSG_PAY`, `TG_MSG_ACK`, `tollgate_proto_encode()`, `tollgate_proto_decode()`. The test file's mock gives the expected API shape.
2. Add `cli_cmd_tollgate_send_pay()` handler in `app_main.cpp`
3. Build a PAY message using `tollgate_proto_encode()` with `TG_MSG_PAY`
4. Set `pkt.data[0] = RELAY_TYPE_TOLLGATE_PAY`, `pkt.len = encoded_len + 1`
5. `xQueueSend(g_tx_queue, &pkt, ...)` to queue for radio_task TX
6. Register with `cli_register_command("tollgate_send_pay", ...)`
7. Guard with `#ifdef CONFIG_ENABLE_TOLLGATE`
8. **Enable `CONFIG_ENABLE_TOLLGATE` in sdkconfig.defaults.esp32s3** (currently not set)

**Pitfalls:**
- The `tollgate_payment_proto.h` header doesn't exist — `app_task.cpp` will not compile with `CONFIG_ENABLE_TOLLGATE` set until it's created.
- The test file uses a mock protocol — the real protocol needs to match the mock's API or the tests need updating.
- TollGate is a separate track (balloon-tollgate). The payment proto may already be specified or partially implemented there. Check `~/repos/balloon-fresh/` tollgate components before writing from scratch.
- `CONFIG_ENABLE_TOLLGATE` is disabled in sdkconfig — enabling it without the header will break the build.

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
- `CONFIG_ENABLE_TOLLGATE` — **not set** — tollgate code is #ifdef'd out

### Component Availability
| Component | Status | Relevant API |
|-----------|--------|-------------|
| `nostr_store` | EXISTS, built | `nostr_store_init/add/get/count/find`, `nostr_event_serialize/deserialize` |
| `secp256k1` | EXISTS, built | Schnorr verification (used in app_task for sig verify) |
| `stratorelay` | EXISTS, built | Cluster-head election, NodeTable — NOT the relay pipeline |
| `fips_radio_bridge` | EXISTS, built | FIPS framing over radio |
| `tollgate_payment_proto` | **DOES NOT EXIST** | Header missing, referenced but not created |

---

## Recommended Follow-up Tasks

If the orchestrator approves, create these kanban tasks (do NOT implement in this audit task):

1. **P5: Implement `relay_send_nostr` CLI command** — serialize Nostr event → g_tx_queue. Medium, 2-4h. Dependencies: nostr_store (met), relay_mode (met).

2. **P5: Implement `nostr_dump` CLI command** — dump stored Nostr events to serial. Low, 1-2h. Requires: refactor nostr_store_t from app_task local to shared scope.

3. **P6: Create `tollgate_payment_proto.h` + implement `tollgate_send_pay` CLI command** — create missing header, implement PAY encode/decode, wire CLI command. High, 4-8h. Dependencies: tollgate proto spec (check balloon-tollgate track), sdkconfig change.