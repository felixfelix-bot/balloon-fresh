# PLAN: Four Tasks — Proto Tests, ESP-IDF Build, GS Client, Mesh Integration

**Date:** 2026-07-29 (updated)
**Author:** balloon-tollgate sub-manager
**Branch:** balloon-tollgate-extract @ 7b1e342
**Related:** ADR-002, PLAN-fix-blockers.md

## Overview

Four tasks to advance TollGate. Blocker 1 (mesh transport) partially resolved
by balloon-hermes mesh_adapter component — Task D integrates it.

| Task | Name | Duration | Dependencies | Parallelizable |
|------|------|----------|--------------|----------------|
| A | Payment proto unit tests | ~1h | None | Yes (with B) |
| B | ESP-IDF build + flash size check | ~2h | None | Yes (with A) |
| C | Ground station client design + impl | ~3h | Task A done | After A |
| D | mesh_adapter integration | ~2h | Task A done | After A (parallel with C) |

**Total wall time with parallelism:** ~5h (A+B parallel → C+D parallel)
**Total sequential time:** ~8h

---

## TASK A: Payment Protocol Unit Tests

### Goal
Write comprehensive host unit tests for `tollgate_payment_proto.c` encode/decode functions and `tollgate_balloon.c` packet handler logic.

### Scope
- Test file: `mesh-stack/tollgate/tests/unit/test_payment_proto.c`
- Extend existing `Makefile` with new test binary
- Pure host gcc build, no ESP-IDF needed
- Uses existing stubs/ directory

### Test Cases (TDD — write tests FIRST)

```
test_proto_encode_basic
  - Encode PAY message with known payload
  - Verify header: version=1, type=0x01, seq=N, payload_len matches
  - Verify payload bytes match input

test_proto_encode_empty_payload
  - Encode STATUS message with 0-length payload
  - Verify total size = 8 bytes (header only)

test_proto_encode_overflow
  - Encode with buf_len too small
  - Verify returns -1

test_proto_decode_valid
  - Decode a known-good byte sequence
  - Verify all header fields parsed correctly
  - Verify payload pointer points to correct offset

test_proto_decode_short
  - Decode with len < sizeof(hdr) (7 bytes)
  - Verify returns -1

test_proto_decode_bad_version
  - Decode with version=2
  - Verify returns -1

test_proto_decode_truncated_payload
  - hdr says payload_len=100 but only 50 bytes follow
  - Verify returns -1

test_proto_roundtrip
  - Encode PAY → decode → compare all fields
  - Encode ACK → decode → compare
  - Encode NACK → decode → compare
  - Encode INFO → decode → compare

test_proto_build_info_json
  - Build info JSON with known values
  - Verify price_sats, step_ms, mint_url, active_sessions, version
  - Verify valid JSON structure

test_proto_build_info_json_null_mint
  - Build info JSON with NULL mint_url
  - Verify mint_url field is empty string, not crash

test_msg_hdr_packed_size
  - Verify sizeof(tollgate_msg_hdr_t) == 8
  - Verify struct is packed (no padding)
```

### Worker Profile

| Field | Value |
|-------|-------|
| Delegate to | leaf worker (delegate_task) |
| Model | glm-5.2 |
| Toolsets | terminal, file |
| Estimated time | 45-60 min |
| Background | Yes |

### Quality Gates

1. **TDD:** Tests written before any fix to proto code. Run tests, observe failures if any bugs found in proto.
2. **Tests pass:** `make` must compile + run test_payment_proto binary with all sub-tests passing.
3. **Docs:** No docs needed (test code is self-documenting).
4. **Atomic commit:** `test(tollgate): add payment proto encode/decode unit tests`
5. **Push:** `git push github balloon-tollgate-extract`

### Deliverable
- `test_payment_proto.c` with 12+ sub-tests
- All pass on `make`
- Commit hash on balloon-tollgate-extract

---

## TASK B: ESP-IDF Build + Flash Size Check

### Goal
Verify the extracted tollgate components + nucula build together under ESP-IDF for ESP32-C3 target. Measure flash/RAM usage to confirm nucula fits.

### Scope

This is NOT a full firmware build. It's a minimal ESP-IDF project that:
1. Creates a project-level `CMakeLists.txt`
2. Creates `main/main.c` with a minimal `app_main()` that calls `tollgate_balloon_init()`
3. Creates `sdkconfig.defaults` for ESP32-C3
4. Runs `idf.py set-target esp32c3 && idf.py build`
5. Reports: binary size, flash usage, RAM usage, any link errors

### Sub-tasks

**B.1: Create ESP-IDF project skeleton**
- `mesh-stack/tollgate/CMakeLists.txt` (project root)
  ```cmake
  cmake_minimum_required(VERSION 3.16)
  set(EXTRA_COMPONENT_DIRS "components")
  include($ENV{IDF_PATH}/tools/cmake/project.cmake)
  project(tollgate-balloon-test)
  ```
- `mesh-stack/tollgate/main/CMakeLists.txt`
  ```cmake
  idf_component_register(SRCS "main.c" INCLUDE_DIRS "." REQUIRES tollgate_balloon)
  ```
- `mesh-stack/tollgate/main/main.c` — minimal app_main that calls init with stub values
- `mesh-stack/tollgate/sdkconfig.defaults` — ESP32-C3 settings, 4MB flash

**B.2: Fix component CMakeLists for ESP-IDF build**
- Verify `tollgate_balloon/CMakeLists.txt` REQUIRES line includes all deps
- Verify `nucula_lib/CMakeLists.txt` compiles under ESP-IDF
- Verify `tollgate_core/CMakeLists.txt` has correct SRCS
- Fix any missing include paths or link deps

**B.3: Build + size report**
```bash
cd mesh-stack/tollgate/
source ~/esp/esp-idf/export.sh
idf.py set-target esp32c3
idf.py build
# Report:
idf.py size   # flash + RAM breakdown
```

**B.4: Memory budget analysis**
- Compare binary size against ESP32-C3 4MB flash budget
- DRAM usage vs 400KB total (312KB usable)
- Flag if nucula pushes us over budget

### Risk: nucula C++ compilation

nucula is C++ (`nucula_wallet.cpp`). ESP-IDF handles C++ but may need:
- `CONFIG_CXX_EXCEPTIONS=y` in sdkconfig
- Proper `SRC_FILES` with `.cpp` extension in CMakeLists
- `std::string`, `std::vector` need heap (check if PSRAM needed — C3 has NO PSRAM!)

**This is the #1 risk.** If nucula's dynamic allocation exceeds C3's 312KB DRAM, we need to either:
- Strip nucula to minimal paths (receive only, no display/keypad/mint management)
- Use a different wallet implementation
- Switch target to ESP32-S3 with PSRAM (but Felix chose C3 for balloon)

### Worker Profile

| Field | Value |
|-------|-------|
| Delegate to | leaf worker (delegate_task) |
| Model | glm-5.2 |
| Toolsets | terminal, file |
| Estimated time | 90-120 min |
| Background | Yes |
| Special | Needs ESP-IDF at ~/esp/esp-idf/export.sh |

### Quality Gates

1. **Build succeeds:** `idf.py build` exit 0
2. **Size reported:** `idf.py size` output captured
3. **Docs:** Create `docs/BUILD-SIZE-REPORT.md` with flash/RAM numbers + verdict
4. **Atomic commit:** `build(tollgate): ESP-IDF project skeleton + C3 build verification`
5. **Push:** `git push github balloon-tollgate-extract`

### Deliverable
- Working ESP-IDF project skeleton
- Binary that compiles for ESP32-C3
- `BUILD-SIZE-REPORT.md` with:
  - Total flash size
  - .text / .rodata / .data / .bss breakdown
  - DRAM usage
  - Verdict: FITS / TOO BIG / NEEDS STRIPPING
- If TOO BIG: specific modules consuming most flash, recommendations

### Escalation Triggers
- If nucula won't compile for C3 → escalate to orchestrator immediately
- If DRAM > 280KB → escalate (leaves no room for mesh stack)
- If link errors can't be resolved → escalate with error log

---

## TASK C: Ground Station Client

### Goal
Design + implement a TollGate client that runs on a ground station. Sends PAY messages to the balloon, receives ACK/NACK, manages payment sessions.

### Architecture

```
Ground Station                          Balloon
┌─────────────────┐                    ┌──────────────────┐
│ tollgate_client │                    │ tollgate_balloon │
│                 │                    │                  │
│ 1. Get price    │─── STATUS ────────>│                  │
│    from balloon │<─── INFO ──────────│                  │
│                 │                    │                  │
│ 2. Create Cashu │                    │                  │
│    token (send  │                    │                  │
│    from wallet) │                    │                  │
│                 │                    │                  │
│ 3. Pay for      │─── PAY ───────────>│                  │
│    relay access │                    │ swap token       │
│                 │<── ACK ────────────│ grant session    │
│                 │                    │                  │
│ 4. Use relay    │<──── mesh relay ───>│                  │
│    (FIPS traffic│                    │                  │
│    through balloon)                  │                  │
└─────────────────┘                    └──────────────────┘
```

### Scope — Two Deliverables

**C.1: `tollgate_client` ESP-IDF component (C)**
- `tollgate_client.h` — public API
- `tollgate_client.c` — implementation
- Client-side state machine
- Uses `tollgate_payment_proto` for encode/decode (shared with balloon side)
- Uses `nucula_wallet` to create/send Cashu tokens

**C.2: Host test harness (`tollgate_client_test.c`)**
- Mocks the mesh transport with loopback (client sends to local buffer, test reads it)
- Tests: state machine transitions, token creation, timeout handling
- Pure host gcc, no ESP-IDF

### Client API Design

```c
typedef enum {
    TG_CLIENT_IDLE,        // No active session
    TG_CLIENT_QUERYING,    // Sent STATUS, awaiting INFO
    TG_CLIENT_PAYING,      // Sent PAY, awaiting ACK/NACK
    TG_CLIENT_ACTIVE,      // Session granted, relay active
    TG_CLIENT_EXPIRED,     // Session expired, need to re-pay
    TG_CLIENT_ERROR,       // Payment failed or comms error
} tollgate_client_state_t;

typedef struct {
    tollgate_client_state_t state;
    uint32_t balloon_node_id;    // Target balloon mesh ID
    uint16_t price_sats;         // Learned from INFO
    int32_t  step_ms;            // Time per payment unit
    uint32_t session_id;         // From ACK
    uint32_t session_expires;    // Unix timestamp
    int      retries;            // Payment retry count
    int64_t  last_payment_ms;    // Timestamp of last successful payment
} tollgate_client_session_t;

// Initialize client with wallet + transport callbacks
esp_err_t tollgate_client_init(
    const char *mint_url,                         // Cashu mint
    void (*send_fn)(const char *dst, const uint8_t *data, uint16_t len),  // Mesh send callback
    void (*on_state_change)(tollgate_client_state_t old, tollgate_client_state_t new)
);

// Called when packet arrives from balloon
esp_err_t tollgate_client_on_packet(const uint8_t *data, uint16_t len);

// User actions
esp_err_t tollgate_client_query_price(void);      // Send STATUS
esp_err_t tollgate_client_pay(uint16_t sats);     // Send PAY with Cashu token
bool      tollgate_client_is_active(void);        // Check if relay access granted
void      tollgate_client_tick(void);             // Call 1Hz, handles expiry

// Status
const tollgate_client_session_t *tollgate_client_get_session(void);
```

### Implementation Plan

**Step 1: Design review (15 min, manager)**
- Review API above
- Verify it covers: query, pay, retry, expiry
- Approve before implementation starts

**Step 2: Create component skeleton (30 min, worker)**
- `tollgate_client.h` — full API
- `tollgate_client.c` — state machine stubs
- `CMakeLists.txt`
- Compile syntax check

**Step 3: Implement state machine (60 min, worker)**
- State transitions: IDLE→QUERYING→PAYING→ACTIVE→EXPIRED→PAYING
- `tollgate_client_on_packet()`: parse ACK/NACK/INFO, update state
- `tollgate_client_pay()`: create Cashu token via `nucula_wallet_send()`, encode PAY msg, call send_fn
- `tollgate_client_tick()`: check session expiry, auto-renew if needed

**Step 4: Write host tests (45 min, worker)**
- `test_client_proto.c` — mock transport, verify state transitions
- Test: query → receive INFO → state=QUERYING→IDLE (with price learned)
- Test: pay → receive ACK → state=PAYING→ACTIVE
- Test: pay → receive NACK → state=PAYING→ERROR
- Test: session expiry → state=ACTIVE→EXPIRED
- Test: retry logic (3 attempts, then ERROR)

**Step 5: Integration (30 min, worker)**
- Wire into test Makefile
- Verify all tests pass
- Commit + push

### Worker Profile

| Field | Value |
|-------|-------|
| Delegate to | leaf worker (delegate_task) |
| Model | glm-5.2 |
| Toolsets | terminal, file |
| Estimated time | 2.5-3h |
| Background | Yes |
| Dependencies | Task A complete (uses payment proto + tests pattern) |

### Quality Gates

1. **TDD:** Tests written before state machine implementation. Observe test failures.
2. **Tests pass:** All client tests pass in host build.
3. **Docs:** `tollgate_client.h` fully documented (API comments). No separate doc file needed.
4. **Atomic commits:**
   - `feat(tollgate_client): component skeleton + API`
   - `feat(tollgate_client): state machine implementation`
   - `test(tollgate_client): host unit tests for state machine`
5. **Push:** `git push github balloon-tollgate-extract`

### Deliverable
- `tollgate_client` component with working state machine
- 8+ host unit tests, all passing
- 3 atomic commits, all pushed

---

## TASK D: mesh_adapter Integration

### Goal
Wire tollgate_balloon to use balloon-hermes' `mesh_adapter` component for
real mesh transport. This replaces the stub send/recv with actual encrypted
mesh datagrams, following the dependency-injection pattern established by
`blossom_datagram`.

### Context

balloon-hermes created (commits 5d17114, 7971810, b60c583):
- `mesh_adapter` — send/recv + fragmentation + FIPS encrypt/decrypt
- `blossom_datagram` — reference integration (serialize → inject send callback → handle incoming)

mesh_adapter API:
```c
void mesh_adapter_init(const mesh_adapter_config_t *config);
mesh_result_t mesh_adapter_send(const uint8_t *data, uint16_t data_len,
                                uint8_t frag_size, uint8_t redundancy);
mesh_result_t mesh_adapter_receive_frame(const uint8_t *frame, uint16_t frame_len,
                                         uint8_t *out_data, uint16_t *out_len,
                                         uint16_t out_size);
```

### Scope

**D.1: Service multiplexer (`mesh_service_mux`)**
Multiple L7 services (TollGate, Nostr, Blossom) share one mesh_adapter.
Need a 1-byte service ID prefix on every datagram:

```c
#define MESH_SVC_TOLLGATE  0x01
#define MESH_SVC_NOSTR     0x02
#define MESH_SVC_BLOSSOM   0x03

// Wrap: [svc_byte(1)] [payload(N)]
int  mesh_service_mux_wrap(uint8_t svc, const uint8_t *in, uint16_t in_len,
                            uint8_t *out, uint16_t out_cap);
// Unwrap: returns svc byte, sets payload ptr + len
int  mesh_service_mux_unwrap(const uint8_t *data, uint16_t len,
                              uint8_t *svc_out,
                              const uint8_t **payload, uint16_t *payload_len);
```

Files:
- `mesh-stack/tollgate/components/mesh_service_mux/include/mesh_service_mux.h`
- `mesh-stack/tollgate/components/mesh_service_mux/src/mesh_service_mux.c`
- `mesh-stack/tollgate/components/mesh_service_mux/CMakeLists.txt`

**D.2: Wire tollgate_balloon to mesh_adapter**
Update `tollgate_balloon.c`:
- Add `mesh_adapter_config_t` with send callback wired to `mesh_adapter_send()`
- `tollgate_balloon_on_packet()` now called after `mesh_service_mux_unwrap()` filters for `MESH_SVC_TOLLGATE`
- `tollgate_balloon_send_response()` (new function): wraps response with mux byte → calls `mesh_adapter_send()`
- Remove `TOLLGATE_BALLOON_PORT` — no port needed, service mux byte replaces port concept

**D.3: Integration callback registration**
```c
// Called by main firmware init:
esp_err_t tollgate_balloon_register_mesh(mesh_adapter_config_t *mesh_cfg);
// Sets up: mesh_adapter → mux_unwrap → tollgate_balloon_on_packet
// And: tollgate_balloon response → mux_wrap → mesh_adapter_send
```

**D.4: Host unit tests**
- `test_mesh_service_mux.c` — wrap/unwrap roundtrip, all 3 service IDs
- `test_tollgate_mesh_integration.c` — mock mesh_adapter, verify PAY → ACK flow through mux

### Sub-task Breakdown

| Step | What | Who | Time |
|------|------|-----|------|
| D.1 | Create mesh_service_mux component (header + impl + tests) | leaf worker | 30 min |
| D.2 | Wire tollgate_balloon send path through mux + mesh_adapter | leaf worker | 30 min |
| D.3 | Wire tollgate_balloon receive path (mux demux → on_packet) | leaf worker | 20 min |
| D.4 | Write integration test (mock mesh, PAY→ACK through mux) | leaf worker | 30 min |
| D.5 | Commit + push | leaf worker | 10 min |

### Architecture After Integration

```
Ground Station                              Balloon
┌──────────────────┐                       ┌──────────────────────────────────┐
│ tollgate_client   │                       │ mesh_adapter (from balloon-hermes)│
│                   │   LR2021 radio        │  ├── encrypt/decrypt (FIPS Noise) │
│ mesh_adapter_send │─────────────────────>│  ├── fragment/reassemble          │
│ (encrypt+fragment)│                       │  └── mesh_service_mux_unwrap()    │
│                   │                       │        ├── SVC_TOLLGATE → on_packet│
│                   │                       │        ├── SVC_NOSTR → nostr_store │
│                   │                       │        └── SVC_BLOSSOM → dgram    │
│                   │<─────────────────────│                                   │
│  ACK received     │   encrypted frames    │ tollgate_balloon:                 │
│  via mesh_adapter │                       │  ├── process PAY → nucula swap   │
│  reassemble       │                       │  ├── grant session               │
│                   │                       │  └── send ACK via mux→mesh_adapter│
└──────────────────┘                       └──────────────────────────────────┘
```

### Worker Profile

| Field | Value |
|-------|-------|
| Delegate to | leaf worker (delegate_task) |
| Model | glm-5.2 |
| Toolsets | terminal, file |
| Estimated time | 2h |
| Background | Yes |
| Dependencies | Task A complete (proto API verified) |

### Quality Gates

1. **TDD:** mux wrap/unwrap tests written before implementation
2. **Tests pass:** All mux + integration tests pass in host build
3. **Docs:** `mesh_service_mux.h` fully documented. Update `tollgate_balloon.h` to reflect mesh registration API
4. **Atomic commits:**
   - `feat(mesh_service_mux): service multiplexer for shared mesh transport`
   - `feat(tollgate_balloon): wire mesh_adapter integration (send + recv paths)`
   - `test(tollgate): mesh integration tests with mock transport`
5. **Push:** `git push github balloon-tollgate-extract`

### Deliverable
- `mesh_service_mux` component (new)
- `tollgate_balloon.c` updated with mesh_adapter send/recv
- `tollgate_balloon_register_mesh()` public API
- 8+ host unit tests, all passing
- 3 atomic commits, all pushed

### Escalation Triggers
- If mesh_adapter API differs from what discovery sync showed → re-read the header, adapt
- If mesh_service_mux design conflicts with blossom_datagram approach → follow blossom_datagram pattern exactly

---

## Execution Schedule

### Phase 1: Parallel kick-off (Tasks A + B simultaneously)

```
T=0min   ┌─ Task A dispatched (background, leaf, glm-5.2)
         │  Payment proto unit tests
         │  Est: 45-60 min
         │
T=0min   └─ Task B dispatched (background, leaf, glm-5.2)
            ESP-IDF build + size check
            Est: 90-120 min
```

### Phase 2: Tasks C + D after A completes (parallel)

```
T=60min  ┌─ Task A COMPLETE (commit hash: ________)
         │
T=60min  ├─ Task C dispatched (background, leaf, glm-5.2)
         │  Ground station client
         │  Est: 2.5-3h
         │
T=60min  └─ Task D dispatched (background, leaf, glm-5.2)
            mesh_adapter integration
            Est: 2h
            Blocked until: Task A done
```

### Phase 3: Results + merge decisions

```
T=120min ┌─ Task B COMPLETE → review size report
         │  Decision: FITS / TOO BIG / NEEDS STRIPPING
         │
T=120min ┌─ Task D COMPLETE → review mesh integration tests
         │  Decision: mesh transport wired, PAY→ACK through mux verified
         │
T=240min └─ Task C COMPLETE → review client tests
            All 4 tasks done.
```

### Dependency Graph

```
[Task A: Proto Tests] ─────────────────────────┐
                                               ├──> [Task C: GS Client]
                                               ├──> [Task D: Mesh Integration]
[Task B: ESP-IDF Build] ──> [Size Report]      │
                    (independent, parallel with A)
```

Tasks A and B have NO interdependency → run simultaneously.
Tasks C and D both depend on Task A → run in parallel after A completes.
Tasks C and D are independent of each other (different components).

### Critical Path

```
A (1h) → D (2h) = 3h  ← critical path (mesh integration unblocks end-to-end)
A (1h) → C (3h) = 4h  ← longest path
B (2h)           = 2h  ← independent, finishes early
```

Wall time: ~4-5h from approval to all 4 tasks complete.

---

## Risk Register

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| nucula too big for C3 DRAM | HIGH | CRITICAL | Task B surfaces this early. If confirmed, escalate to orchestrator for architecture decision |
| nucula C++ won't link under ESP-IDF | MEDIUM | HIGH | Use `extern "C"` wrapper (already done in nucula_wallet.h). Enable CXX_EXCEPTIONS |
| Payment proto has bugs found by tests | LOW | LOW | That's what tests are for. Fix in proto, re-run |
| Client state machine too complex | LOW | MEDIUM | Start with minimal state machine (5 states), expand later |
| ESP-IDF not configured for C3 | LOW | HIGH | sdkconfig.defaults handles this. Already have export.sh |
| mesh_adapter API changed since discovery | LOW | MEDIUM | Re-read header from ~/repos/balloon-fresh before starting Task D |
| mesh_service_mux conflicts with blossom_datagram approach | LOW | LOW | Follow blossom_datagram pattern exactly — same dependency injection style |

---

## Approval Checklist

Before dispatching, confirm:

- [ ] Felix approves the plan (4 tasks)
- [ ] Felix approves Task B running as background build (no flashing, just compile)
- [ ] Felix OK with nucula C++ in C3 build
- [ ] Felix OK with Task C client API design (Section C.2)
- [ ] Felix OK with Task D mesh_service_mux design (1-byte service demux)
- [ ] Felix OK with removing TOLLGATE_BALLOON_PORT (replaced by mux byte)

Once approved, I dispatch Tasks A + B immediately (parallel), then Tasks C + D when A completes.
