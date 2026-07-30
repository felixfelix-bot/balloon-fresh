# PLAN: Fix Two TollGate Blockers

**Date:** 2026-07-29
**Author:** balloon-tollgate sub-manager
**Related:** ADR-001, ADR-002, ADR-024

## Blockers

1. **FIPS mesh UDP transport API** — tollgate_balloon needs UDP socket send/recv over the FIPS mesh, plus node ID lookup
2. **nucula wallet spend_proofs()** — platform adapter's spend_proofs() stub must call nucula wallet for real Cashu token processing

---

## BLOCKER 1 STATUS UPDATE (2026-07-29): PARTIALLY RESOLVED

balloon-hermes created `mesh_adapter` component (commit 5d17114) with:
- `mesh_adapter_send(data, len, frag_size, redundancy)` — send over mesh
- `mesh_adapter_receive_frame(frame, len, out, out_len, size)` — receive + reassemble
- encrypt/decrypt callbacks for FIPS Noise sessions
- Fragmentation handling built-in

Also created `blossom_datagram` (commit 7971810) — follows the EXACT same
dependency-injected pattern TollGate should use: serialize message → inject
send callback wired to mesh_adapter → handle_message() for incoming.

**Integration is now straightforward:**
1. Wire mesh_adapter_send() as tollgate_balloon's send callback
2. Route reassembled mesh frames to tollgate_balloon_on_packet()
3. FIPS session provides sender identity (node ID) for payment tracking

**Remaining work:** Add a 1-byte service demux (so TollGate + Nostr + Blossom
can share mesh_adapter), and wire the FIPS session context. This is integration
work, not new API design.

### Problem

tollgate_balloon calls `tollgate_balloon_on_packet()` when a UDP packet arrives on port 2121. But we have no FIPS mesh UDP socket layer to receive packets or send responses.

### Key Discovery: Port Conflict

FIPS VPS binds **0.0.0.0:2121**. Our TollGate also wants **port 2121**. These must coexist — either different ports or FIPS multiplexes.

### microfips Architecture (from AGENTS.md)

microfips is **Rust** with a **transport trait**:
- `microfips-service`: transport-neutral request/response layer
- `microfips-esp-common`: UDP transport for ESP32
- `fips-noise`: Noise IK/XK/XX encrypted sessions
- `fips-fmp`: FMP link-layer wire format

The balloon runs **FIPS as a mesh node**, not as a VPS. Ground stations are also FIPS nodes. TollGate messages ride inside FIPS sessions.

### What This Means

TollGate does NOT open a raw UDP socket. Instead:
1. FIPS mesh provides an **encrypted session** between balloon and ground station
2. TollGate messages are **application-layer payloads** inside FIPS FSP sessions
3. The "transport" is: `TollGate → FIPS service layer → FIPS protocol → Noise encrypted → FMP framed → mesh route → LR2021 radio`

### Plan

#### Phase 1: Study FIPS Service Layer (delegate to research)
- Clone microfips repo
- Study `microfips-service` crate: how does it expose request/response?
- Study `microfips-protocol`: what's the `transport` trait? Can we register a custom service handler?
- Document: function signatures for sending/receiving application messages
- **Deliverable:** API spec doc (what functions to call, what headers to include)

#### Phase 2: Design TollGate FIPS Service
- TollGate registers as a FIPS service (like an HTTP handler but over FIPS)
- Message types map to FIPS service requests:
  - PAY → service request type 0x01
  - STATUS → service request type 0x04
- Responses are FIPS service responses (ACK/NACK/INFO)
- **Deliverable:** tollgate_fips_service.h API design

#### Phase 3: Implement C Wrapper Around FIPS Rust API
- FIPS is Rust. TollGate is C. Need FFI bridge.
- Option A: `#[no_mangle] extern "C"` wrappers in microfips exposing send/recv
- Option B: TollGate sends raw bytes to FIPS via ESP-IDF FreeRTOS message buffers, FIPS Rust side reads from buffer
- Option C: Use ESP-IDF lwIP UDP sockets directly if FIPS mesh exposes a virtual network interface (like a TUN)
- **Recommendation:** Option C if mesh-stack INTEGRATION-ARCHITECTURE.md says L4 is "UDP/IP tunnel" — that means standard sockets work!
- **Deliverable:** Working FFI bridge or socket interface

#### Phase 4: Integration Test
- Two ESP32-C3 boards: one as balloon (TollGate + FIPS), one as ground station (FIPS client)
- Ground station sends PAY message → balloon processes → sends ACK
- Verify end-to-end over actual LR2021 radio (if hardware available) or over WiFi (integration test)
- **Deliverable:** Passing integration test

### Dependency
- **Requires balloon-fips track** to provide FIPS mesh running on ESP32-C3
- **Requires balloon-firmware track** for LR2021 driver (L1)
- Current balloon-fips status: Phase 2 research, not yet on hardware

### Escalation Needed
ORCHESTRATOR: Forward to balloon-fips: TollGate needs the FIPS service layer API. Specifically:
1. How does an application register as a FIPS service?
2. Does the mesh expose UDP/IP sockets at L4? (INTEGRATION-ARCHITECTURE.md says "UDP/IP tunnel" — confirm this means standard lwIP sockets)
3. Can we use port 2121 or does FIPS already claim it?

---

## BLOCKER 2: nucula wallet spend_proofs()

### Problem

The platform adapter's `pf_spend_proofs()` stub returns false. It must call nucula wallet to actually receive/swap incoming Cashu tokens.

### Key Discovery: spend_proofs() Was Already a Stub in Source Repo!

The original tollgate_esp implementation of `esp_spend_proofs()` also just returns `true` without doing anything. The real Cashu processing happens in `tollgate_core_cashu.c` via HTTP calls to the mint's `/v1/checkstate` endpoint.

The actual payment flow in the original tollgate:
1. Client POSTs Cashu token to TollGate HTTP API
2. `tollgate_core_process_payment()` calls `tollgate_core_cashu_decode_token()` → parses proofs
3. `tollgate_core_cashu_check_proof_states()` → HTTP POST to mint `/v1/checkstate`
4. If proofs are valid (not spent), `spend_proofs()` is called (but it's a no-op!)
5. Session is granted

The original tollgate **trusts that the mint says the proofs are valid** — it doesn't actually spend them via nucula wallet! The nucula wallet is used separately for wallet operations (balance, send, receive) via the `/wallet` API endpoint.

### What Felix Actually Wants (from voice message)

Felix said: "Your job is to swap them. Don't accept the tokens blindly."

This means `spend_proofs()` must:
1. Take the incoming token string
2. Call `nucula_wallet_receive(token_str)` — which performs a Cashu swap (NUT-03)
3. Return true only if the swap succeeds

### nucula_wallet.h API (already extracted)

```c
esp_err_t nucula_wallet_init(const char *mint_url);
esp_err_t nucula_wallet_receive(const char *token_str);  // ← THIS
esp_err_t nucula_wallet_send(uint64_t amount_sat, char *token_out, size_t token_out_size);
uint64_t  nucula_wallet_balance(void);
```

`nucula_wallet_receive()` internally calls `cashu::Wallet::receive()` which:
1. Parses the token
2. Performs a swap operation with the mint (NUT-03)
3. Stores the new proofs in NVS
4. Returns ESP_OK on success

This requires HTTP connectivity to the mint (online mode — which Felix confirmed).

### Plan

#### Phase 1: Wire Up spend_proofs() — DONE (commit d3d54ea)
- Replace `pf_spend_proofs()` stub with call to `nucula_wallet_receive()`
- Ensure nucula wallet is initialized in `tollgate_balloon_init()`
- Handle error cases: mint unreachable, invalid token, already spent
- **Deliverable:** spend_proofs() implementation in tollgate_balloon.c

```c
static bool pf_spend_proofs(const char *raw_token_json) {
    /* The raw_token_json from tollgate_core is the cashuA... token string */
    esp_err_t ret = nucula_wallet_receive(raw_token_json);
    if (ret == ESP_OK) {
        ESP_LOGI(TAG, "Cashu token received + swapped: %llu sats", nucula_wallet_balance());
        return true;
    }
    ESP_LOGW(TAG, "Cashu receive failed: %s", esp_err_to_name(ret));
    return false;
}
```

#### Phase 2: Initialize nucula Wallet — DONE (commit d3d54ea)
- In `tollgate_balloon_init()`, call `nucula_wallet_init(mint_url)`
- Add nucula_lib to tollgate_balloon's CMakeLists.txt REQUIRES
- **Deliverable:** nucula wallet boot sequence

#### Phase 3: Add Payment Error Codes — DONE (commit d3d54ea)
- Error codes documented in PAY handler in tollgate_balloon.c
- Mapping ready for NACK response construction
- Map nucula errors to TollGate NACK codes:
  - ESP_FAIL → TG_ERR_INVALID_TOKEN
  - ESP_ERR_HTTP_CONNECT → TG_ERR_MINT_UNREACHABLE
  - Other → TG_ERR_SWAP_FAILED
- **Deliverable:** Error mapping in packet handler

#### Phase 4: Test on Hardware (1-2 hours)
- Flash balloon with TollGate + nucula
- Connect via WiFi (integration test — radio not ready yet)
- Send a test Cashu token via HTTP POST
- Verify: wallet balance increases, session granted
- **Deliverable:** Passing payment test with real Cashu token

### Risk: Memory Budget
- nucula uses secp256k1 + ChaChaPoly + HTTP client — significant flash/RAM
- ESP32-C3 has 4MB flash (2.5MB factory partition, 50% free after tollgate = ~1.25MB)
- nucula_wallet.cpp + vendored sources: need to verify they fit
- **Mitigation:** Build test to check binary size before committing

---

## Execution Order

1. **BLOCKER 2 first** (nucula spend_proofs) — no external dependencies, can do now
2. **BLOCKER 1 second** (FIPS transport) — depends on balloon-fips track

### Timeline
| Task | Owner | Duration | Dependency |
|------|-------|----------|------------|
| Wire spend_proofs() to nucula | tollgate (me) | 1h | None |
| nucula init in balloon_init | tollgate (me) | 30min | nucula_lib extracted |
| Build test (flash size check) | tollgate (me) | 30min | ESP-IDF build |
| Payment test on hardware | tollgate (me) | 1h | Flash approval |
| FIPS service API research | delegate | 2h | microfips repo clone |
| TollGate FIPS service design | tollgate (me) | 1h | Research done |
| FFI bridge or socket adapter | delegate | 4h | Design done |
| Integration test | tollgate + fips | 2h | Both tracks ready |

**Total: ~12 hours of work, blocked on FIPS mesh readiness.**

Blocker 2 (nucula) can start immediately. Blocker 1 (FIPS) is gated on balloon-fips track.
