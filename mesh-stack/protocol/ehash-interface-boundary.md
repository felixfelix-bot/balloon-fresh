# E-Hash Ground Station Interface Boundary

**Status:** Proposed
**Date:** 2026-07-29
**Tracks:** balloon-pow ↔ tollgate
**Related:**
- [ADR-025](../../docs/adr/025-e-hash-relay-transport-layer.md) — full e-hash relay architecture
- [ADR-025 Decisions D1–D10](../../docs/adr/adr-e-hash-relay-DECISIONS.md) — locked design decisions
- [Binary Encoding Spec](ehash-spec.md) — EHASH_TEMPLATE/NONCE/RESULT/CREDIT wire format
- [C Header](ehash_messages.h) — packed structs and encode/decode prototypes

---

## 1. Purpose

The e-hash ground station stratum-bridge is a single process (or process
group) running on the ground station Pi that serves two constituencies:

1. **Upstream radio path** (balloon mesh → stratum protocol translation)
2. **Downstream customer path** (customer hardware → wallet/billing/access control)

This document defines the **interface boundary** between the balloon-pow and
tollgate development tracks so both can build and test independently without
blocking each other. The boundary is a set of **localhost APIs** — no shared
code, no shared state files, no compilation dependencies.

---

## 2. Architecture: Where the Boundary Sits

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                        GROUND STATION (Pi)                       │
  │                                                                  │
  │  ╔═══════════════════════════════════════════╗                   │
  │  ║        BALLOON-POW TRACK (upstream)        ║                   │
  │  ║                                            ║                   │
  │  ║  LR2021 RX → FIPS decrypt → L7 dispatch    ║                   │
  │  ║    → ehash_template_decode()               ║                   │
  │  ║    → reconstruct Stratum V1 JSON           ║                   │
  │  ║    → TCP stratum server (localhost:3333) ◄────────────────┐   │
  │  ║                                            ║               │   │
  │  ║  Bitaxe mining.submit (TCP :3333) ──────────────────────┐ │   │
  │  ║    → ehash_nonce_encode()                ║             │ │   │
  │  ║    → local difficulty filter (D7)        ║             │ │   │
  │  ║    → LR2021 TX → balloon relay           ║             │ │   │
  │  ║                                            ║             │ │   │
  │  ║  EHASH_RESULT RX → stratum response ───────┼─────────────┼─┘   │
  │  ║                                            ║             │     │
  │  ╚════════════════╤═══════════════════════════╝             │     │
  │                   │                            │             │     │
  │          ═════════╪═══════════════╗             │             │     │
  │          ║  INTERFACE BOUNDARY 1  ║             │             │     │
  │          ║  TCP localhost:3333    ║ ◄───────────┘             │     │
  │          ═════════╪═══════════════╝                            │     │
  │                   │                                            │     │
  │  ╔════════════════╧══════════════════════════╗                │     │
  │  ║       TOLLGATE TRACK (downstream)          ║                │     │
  │  ║                                            ║                │     │
  │  ║  Bitaxe physical connection (USB/network)  ║ ◄──────────────┘     │
  │  ║  Customer session mgmt (captive portal)    ║                      │
  │  ║  E-hash wallet (Cashu) — ground station    ║                      │
  │  ║  Template decryption keys (D8)             ║                      │
  │  ║  TTL expiry / pause logic (D9)             ║                      │
  │  ║  Customer-facing UI / status               ║                      │
  │  ║                                            ║                      │
  │  ║  ══════════════════════════════════════════ ║                     │
  │  ║  INTERFACE BOUNDARY 2: Balance Query API    ║ ──────► (polled by  │
  │  ║  GET /api/v1/balance  (HTTP localhost)      ║       balloon-pow)  │
  │  ║  POST /api/v1/share-report (HTTP localhost) ║ ◄────── (balloon-pow│
  │  ║  GET /api/v1/session-status                 ║        reports)     │
  │  ║  ══════════════════════════════════════════ ║                     │
  │  ╚════════════════════════════════════════════╝                      │
  │                                                                  │
  └──────────────────────────────────────────────────────────────────┘
         ↑ templates DOWN / nonces UP              ↑ physical hash rate
    LR2021 radio (balloon mesh)               Bitaxe ASIC (customer HW)
```

---

## 3. Ownership Matrix

### 3.1 Balloon-Pow Owns (Upstream Side)

The balloon-pow track builds a **standalone stratum-bridge daemon** that
runs on the ground station Pi. It handles the radio path and stratum
protocol translation. It has no knowledge of customers, wallets, or
billing.

| Component | Responsibility |
|-----------|---------------|
| LR2021 RX → FIPS decrypt | Receive radio frames, decrypt, reassemble fragments |
| L7 message dispatch | Read type tag, route to EHASH_TEMPLATE/NONCE/RESULT/CREDIT decoder |
| `ehash_template_decode()` | Parse binary EHASH_TEMPLATE (0x10) into structured fields |
| Stratum V1 JSON reconstruction | Convert binary template → `mining.notify` JSON for Bitaxe |
| TCP stratum server | Listen on `localhost:3333`, accept Bitaxe connections, serve `mining.subscribe` / `mining.notify` / `mining.set_difficulty` |
| `mining.submit` ingestion | Receive share submissions from Bitaxe via TCP |
| `ehash_nonce_encode()` | Convert `mining.submit` JSON fields → binary EHASH_NONCE (0x11, 21 bytes) |
| Local difficulty filter (D7) | Run higher-difficulty check on shares before encoding for uplink — only shares meeting the threshold get sent over radio |
| EHASH_NONCE → LR2021 TX | Queue encoded nonce for next TDMA uplink slot |
| EHASH_RESULT handling | Receive EHASH_RESULT (0x12) from radio, translate to stratum JSON response, send to Bitaxe |

### 3.2 Tollgate Owns (Downstream Side)

The tollgate track builds the **customer and wallet layer**. It manages
who can connect, how they pay, and what happens when connectivity is lost.
It has no knowledge of radio, binary encoding, or stratum internals.

| Component | Responsibility |
|-----------|---------------|
| Bitaxe physical connection | USB or network discovery and provisioning of customer ASIC hardware |
| Customer session management | Captive portal, device pairing, session lifecycle |
| E-hash wallet (Cashu) | Ground-station Cashu wallet: receive e-hash tokens from balloon (for valid nonces), spend e-hash on internet access |
| Template decryption keys (D8) | Per-session key management — hold/issue the key that decrypts templates after payment verification. No payment = no key = no decryption |
| TTL expiry / pause (D9) | Detect upstream loss (no new templates within TTL window), pause mining, grant free local relay access during outage |
| Customer-facing UI | Status display: balance, hash rate, connectivity state, mining progress |
| Share accounting | Track accepted/rejected shares for billing and reward attribution |

### 3.3 Shared Concerns (Neither Owns — Interface Contracts Define These)

| Concern | Resolution |
|---------|-----------|
| Template decryption | Balloon-pow decrypts using key obtained from tollgate (via Interface Boundary 2). Tollgate manages the key lifecycle. |
| Balance check before serving templates | Stratum server (balloon-pow) calls tollgate's balance API before sending `mining.notify` to a newly connected Bitaxe |
| Share acceptance reporting | Stratum server (balloon-pow) calls tollgate's share-report API after receiving EHASH_RESULT |

---

## 4. Interface Contracts

Two interfaces define the handoff. Both are **localhost HTTP** to ensure
process isolation and language independence (balloon-pow may be Python,
tollgate may be Go/Rust/Python).

### 4.1 Interface Boundary 1: Stratum TCP Server

**Owner (server):** balloon-pow
**Consumer (client):** tollgate (on behalf of the Bitaxe it manages)

| Attribute | Value |
|-----------|-------|
| Protocol | Stratum V1 (JSON-RPC over TCP, newline-delimited) |
| Address | `127.0.0.1:3333` |
| Auth | None (localhost only — no password needed; access control is tollgate's job) |

**Balloon-pow guarantees:**
- Server is listening on `127.0.0.1:3333` when templates are available.
- Responds to standard stratum V1 methods: `mining.subscribe`, `mining.authorize`, `mining.notify`, `mining.set_difficulty`.
- `mining.notify` messages are reconstructed from the latest received EHASH_TEMPLATE.
- `mining.submit` responses reflect upstream EHASH_RESULT status.

**Tollgate obligations:**
- Connects the Bitaxe to `127.0.0.1:3333` (proxies or bridges as needed for USB-attached devices).
- Does not send non-stratum traffic on this socket.
- Responsible for any per-customer difficulty overrides via the balance API (see 4.2).

**Note on authorization:** Standard stratum `mining.authorize` with username/password
will be accepted with a fixed dummy credential. Real authorization is enforced by
tollgate's captive portal / session layer before the Bitaxe is allowed to connect.
The stratum server does not implement customer authentication.

### 4.2 Interface Boundary 2: Tollgate Balance & Session API

**Owner (server):** tollgate
**Consumer (client):** balloon-pow stratum daemon

All endpoints return JSON. Base URL: `http://127.0.0.1:PORT/v1/` (port TBD,
recommend `127.0.0.1:3334`).

#### GET `/v1/balance`

Check whether a customer session has sufficient e-hash balance to receive templates.

**Response (200):**
```json
{
  "station_id": 66,
  "balance_sats": 50000000,
  "has_access": true,
  "session_id": "abc-123-def",
  "difficulty_multiplier": 1.0
}
```

| Field | Type | Description |
|-------|------|-------------|
| `station_id` | uint16 | Ground station ID (matches `worker_id` in EHASH_NONCE) |
| `balance_sats` | uint64 | Current e-hash balance in satoshis |
| `has_access` | bool | `true` if customer may receive templates (balance > threshold). `false` = gate the stratum server, do not send `mining.notify`. |
| `session_id` | string | Active customer session identifier (opaque to balloon-pow) |
| `difficulty_multiplier` | float | Optional difficulty multiplier for this session (D7 tuning). `1.0` = default. Higher = fewer shares uplinked. |

**When called:** Stratum server calls this when a new Bitaxe connects and
periodically (every 30–60s) while connected. If `has_access` is `false`, the
stratum server withholds `mining.notify` and may close or idle the connection.

#### POST `/v1/share-report`

Report the outcome of a share submission (after EHASH_RESULT arrives from radio).

**Request body:**
```json
{
  "job_id": 1,
  "worker_id": 66,
  "accepted": true,
  "error_code": 0,
  "timestamp": 1722249600
}
```

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | uint32 | Job ID from the share |
| `worker_id` | uint16 | Station ID |
| `accepted` | bool | Whether the pool accepted the share |
| `error_code` | uint16 | Stratum error code (0 = none). See ehash-spec.md §4.2. |
| `timestamp` | uint32 | Unix timestamp of the result arrival |

**Response (200):**
```json
{
  "reward_sats": 500,
  "new_balance_sats": 50000500
}
```

**When called:** Stratum server calls this after processing each EHASH_RESULT.
Tollgate uses this for billing, reward attribution, and balance updates.

#### GET `/v1/session-status`

Query the current connectivity/session state (used for D9 TTL/pause logic).

**Response (200):**
```json
{
  "session_active": true,
  "upstream_connected": true,
  "ttl_remaining_sec": 1800,
  "mining_paused": false,
  "free_local_relay": false
}
```

| Field | Type | Description |
|-------|------|-------------|
| `session_active` | bool | Customer session is valid |
| `upstream_connected` | bool | Tollgate's view of upstream connectivity |
| `ttl_remaining_sec` | uint32 | Seconds until template TTL expiry (D9). `0` = expired. |
| `mining_paused` | bool | `true` if mining should be paused (upstream lost, TTL expired) |
| `free_local_relay` | bool | `true` if outage mode — free local relay access granted (D9) |

**When called:** Stratum server calls this to determine whether to keep
serving templates. If `mining_paused` is `true`, the stratum server stops
sending `mining.notify` and may send an idle/pause notification.

#### POST `/v1/template-decrypt-key`

**Direction:** Tollgate → balloon-pow (reverse direction — tollgate calls
this on the balloon-pow stratum daemon to deliver the decryption key).

**Endpoint on balloon-pow side:** `http://127.0.0.1:3335/v1/template-decrypt-key`
(balloon-pow listens on a secondary port for control commands from tollgate).

**Request body:**
```json
{
  "session_id": "abc-123-def",
  "key_hex": "a1b2c3d4e5f6..."
}
```

Tollgate provides the per-session template decryption key (D8) once payment
is verified. Balloon-pow uses this key to decrypt incoming EHASH_TEMPLATE
payloads from the radio before decoding.

**Response (200):**
```json
{
  "accepted": true
}
```

---

## 5. Sequence Diagram — Full Data Flow

```
  Mining Pool         E-Hash Proxy          Balloon (ESP32-C3)        Ground Station Pi
  (Internet)          (upstream)            (relay only)                                                       
    │                     │                       │                                            ┌─────────────────────────────────────┐
    │                     │                       │                                            │  GROUND STATION Pi                  │
    │                     │                       │                                            │                                     │
    │                     │                       │   ┌──────────────────────────────────────┐ │                                     │
    │                     │                       │   │                                      │ │                                     │
    │   Stratum V1        │    EHASH_TEMPLATE     │   │           LR2021 radio               │ │                                     │
    │ ◄─────────────────► │ ◄──────────────────► │ ◄─┼─► [BALLOON-POW] FIPS decrypt          │ │                                     │
    │   (TCP JSON)        │    (binary, radio)    │   │   → ehash_template_decode()          │ │                                     │
    │                     │                       │   │   → reconstruct Stratum V1 JSON      │ │                                     │
    │                     │                       │   │                                      │ │                                     │
    │                     │                       │   │   ┌── IF BOUNDARY 1 ─────────────┐    │ │                                     │
    │                     │                       │   │   │ TCP localhost:3333          │    │ │                                     │
    │                     │                       │   │   │ (stratum server)            │    │ │                                     │
    │                     │                       │   │   │                             │    │ │                                     │
    │                     │                       │   │   │  ① GET /v1/balance           │────┼─┼────► [TOLLGATE] Wallet API          │
    │                     │                       │   │   │     (check access gate)      │    │ │   (localhost:3334)                   │
    │                     │                       │   │   │                             │◄───┼─┼──── {has_access: true}              │
    │                     │                       │   │   │                             │    │ │                                     │
    │                     │                       │   │   │  ② mining.notify (JSON)      │    │ │   ┌──────────────────────┐          │
    │                     │                       │   │   │     ────────────────────────►│────┼─┼──►│ Bitaxe (ASIC)        │          │
    │                     │                       │   │   │                             │    │ │   │ - mines template     │          │
    │                     │                       │   │   │                             │    │ │   │ - finds nonce        │          │
    │                     │                       │   │   │  ③ mining.submit (JSON)      │    │ │   │                      │          │
    │                     │                       │   │   │     ◄────────────────────────│◄───┼─┼───│ - submits share      │          │
    │                     │                       │   │   │                             │    │ │   └──────────────────────┘          │
    │                     │                       │   │   │  ④ ehash_nonce_encode()      │    │ │                                     │
    │                     │                       │   │   │     → 21 bytes               │    │ │                                     │
    │                     │                       │   │   │  ⑤ difficulty filter (D7)     │    │ │                                     │
    │                     │                       │   │   │     (drop low-value shares)  │    │ │                                     │
    │                     │                       │   │   └─────────────────────────────┘    │ │                                     │
    │                     │                       │   │                                      │ │                                     │
    │                     │    EHASH_NONCE        │   │   ⑥ LR2021 TX (uplink)              │ │                                     │
    │                     │ ◄──────────────────► │ ◄─┼─► [BALLOON-POW] nonce → radio        │ │                                     │
    │                     │    (21 bytes)         │   │                                      │ │                                     │
    │                     │                       │   │   ⑦ EHASH_RESULT (downlink)          │ │                                     │
    │                     │                       │   │   [BALLOON-POW] result → JSON        │ │                                     │
    │                     │                       │   │   → stratum response to Bitaxe       │ │                                     │
    │                     │                       │   │                                      │ │                                     │
    │                     │                       │   │   ⑧ POST /v1/share-report            │───┼─┼────► [TOLLGATE] accounting        │
    │                     │                       │   │      (accepted/rejected + reward)     │ │   → update e-hash balance           │
    │                     │                       │   │                                      │ │                                     │
    │                     │                       │   │   ⑨ EHASH_CREDIT (downlink)          │ │                                     │
    │                     │                       │   │   [BALLOON-POW] credit → display     │ │                                     │
    │                     │                       │   │                                      │ │                                     │
    │                     │                       │   └──────────────────────────────────────┘ │                                     │
    │                     │                       │                                            └─────────────────────────────────────┘
```

### Numbered Flow Steps

| Step | Direction | What Happens | Interface Boundary |
|------|-----------|-------------|-------------------|
| ① | balloon-pow → tollgate | Stratum server checks balance before serving templates | Boundary 2: `GET /v1/balance` |
| ② | balloon-pow → Bitaxe | Template served as standard `mining.notify` JSON | Boundary 1: TCP `:3333` |
| ③ | Bitaxe → balloon-pow | Share submitted as standard `mining.submit` JSON | Boundary 1: TCP `:3333` |
| ④ | balloon-pow internal | JSON share → binary EHASH_NONCE (21 bytes) | — |
| ⑤ | balloon-pow internal | Local difficulty filter drops low-value shares (D7) | — |
| ⑥ | balloon-pow → radio | Nonce queued for TDMA uplink to balloon | — |
| ⑦ | radio → balloon-pow | EHASH_RESULT arrives, translated to stratum JSON response | — |
| ⑧ | balloon-pow → tollgate | Share acceptance/rejection reported for accounting | Boundary 2: `POST /v1/share-report` |
| ⑨ | radio → balloon-pow | EHASH_CREDIT arrives, balance update forwarded to tollgate display | — |

---

## 6. Template Decryption Flow (D8)

D8 mandates per-session template encryption. The decryption key is only
provided after e-hash payment is verified. This creates a dependency between
the two tracks at startup:

```
  TOLLGATE                          BALLOON-POW
  ─────────                         ───────────
  Customer pays e-hash
  → verify payment
  → generate/obtain per-session key
  → POST /v1/template-decrypt-key   ───►  Receive key, store per session_id
       {session_id, key_hex}               Store in key ring
                                           
                                    LR2021 RX → FIPS decrypt
                                    → L7 dispatch (EHASH_TEMPLATE)
                                    → Look up session key by station_id
                                    → Decrypt template payload
                                    → ehash_template_decode()
                                    → Stratum V1 JSON → TCP :3333
```

**Contract:** Balloon-pow's stratum daemon exposes a key-reception endpoint
(`POST /v1/template-decrypt-key` on port 3335). Tollgate pushes keys
proactively after payment verification. If no key exists for a session, the
stratum daemon cannot decode templates and withholds `mining.notify`.

---

## 7. TTL Pause Flow (D9)

When the balloon loses upstream connectivity, templates stop arriving.
Tollgate owns the TTL/pause logic:

```
  TOLLGATE (TTL watchdog)              BALLOON-POW
  ───────────────────────              ───────────

  No new template within TTL window
  → set mining_paused = true
  → set free_local_relay = true

                                        GET /v1/session-status  ──►
                                                                        {mining_paused: true,
                                                                         free_local_relay: true}
                                        ◄────
                                        
                                        Stratum server:
                                        - stops sending mining.notify
                                        - sends idle/pause to Bitaxe
                                        - accepts no new mining.submit
                                        
                                        (During outage, existing mesh
                                         relay services still work —
                                         Nostr, local messaging, etc.)
```

**Contract:** The stratum server polls `GET /v1/session-status` at a
configurable interval (default: 30s). When `mining_paused` is `true`, it
withholds templates and returns a stratum error `"upstream paused"` to
`mining.submit` attempts. When upstream is restored and `mining_paused`
returns to `false`, normal operation resumes with the next EHASH_TEMPLATE.

---

## 8. Port Allocation

| Port | Protocol | Owner | Purpose |
|------|----------|-------|---------|
| 3333 | TCP (Stratum V1) | balloon-pow | Stratum server — Bitaxe connects here |
| 3334 | HTTP | tollgate | Balance & session API — balloon-pow calls this |
| 3335 | HTTP | balloon-pow | Control API — tollgate pushes decrypt keys here |

All bound to `127.0.0.1` only. No external network exposure.

---

## 9. Dependencies and Build Isolation

### 9.1 Build Independence

- **Balloon-pow** depends on: `ehash_messages.h`, `ehash-spec.md`, FIPS
  library, LR2021 SPI driver, Stratum V1 protocol knowledge.
- **Tollgate** depends on: Cashu wallet library, captive portal stack,
  Bitaxe USB/network driver, its own session DB.
- **Neither** depends on the other's source code. They communicate only via
  the localhost HTTP + TCP contracts defined in §4.

### 9.2 Testing Independently

| Track | Standalone Test Strategy |
|-------|--------------------------|
| Balloon-pow | Run stratum daemon with a mock tollgate API (returns `has_access: true`, `mining_paused: false`). Use a CPU miner or Bitaxe simulator to test the full radio→stratum→nonce loop. |
| Tollgate | Run wallet/session layer with a mock stratum daemon (receives balance queries, share reports). Test captive portal, payment, key issuance, TTL/pause transitions. |

### 9.3 Integration Test (Joint)

Phase D (per ADR-025) brings both together on the Pi with real radio
hardware and a real Bitaxe. The interface contracts in §4 are the
acceptance criteria.

---

## 10. Open Items

| ID | Item | Owner | Notes |
|----|------|-------|-------|
| O1 | Exact tollgate API port (3334 proposed) | tollgate | Confirm no conflict with existing services |
| O2 | Error response schemas for tollgate API | tollgate | Define 4xx/5xx bodies for balance/session endpoints |
| O3 | EHASH_CREDIT forwarding to tollgate | balloon-pow | Currently displayed by balloon-pow; should credit updates also POST to tollgate for wallet sync? |
| O4 | Multiple Bitaxe sessions (multiplexing) | both | Stratum V1 server needs session tracking if >1 customer connects simultaneously |
| O5 | Stratum `mining.authorize` → session_id mapping | both | How to map a Bitaxe stratum username to a tollgate session_id for the balance check |

---

## 11. Invariants

1. **No shared code or state files between tracks.** All communication via
   the two localhost interfaces (Boundary 1: TCP :3333, Boundary 2: HTTP).
2. **Balloon-pow never touches the Cashu wallet.** It queries tollgate for
   balance; it does not mint, spend, or hold e-hash tokens.
3. **Tollgate never touches the radio.** It does not parse EHASH_* binary
   messages, does not call `ehash_*` functions, does not manage the LR2021.
4. **The stratum server is balloon-pow's only exposed surface.** Tollgate
   does not send non-stratum traffic on port 3333.
5. **Template decryption keys flow tollgate → balloon-pow, never the
   reverse.** Tollgate is the key authority (D8).
6. **Both tracks can build and test against the interface contracts in §4
   without the other track's code.**
