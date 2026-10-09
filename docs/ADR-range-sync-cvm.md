# ADR: Range-Sync via CVM Message Layer (ARMED / GO / Verdict)

**Status:** Proposed (Phase 1 — message layer)
**Date:** 2026-08-30
**Branch:** `wt/cvm-p1`
**Design session:** balloon-hermes 2026-08-30 (consultants A+B, code-grounded)
**Supersedes:** manual T0+SESSION relay over Signal; plaintext kind-30315 tallies

---

## 1. Context

Outdoor E80 range tests split TX and RX across two machines behind different
NATs. Today the two operators coordinate the launch by hand:

1. Both machines NTP-sync and pick a shared `T0` (next 5-minute boundary).
2. The TX operator Signals the `T0` + `SESSION_ID` to the RX operator the
   moment the TX banner prints.
3. RX pre-arms and both sides anchor their cycle machinery to `T0`.

This has three failure classes:

- **Human relay latency / error** — a 20 s desync incident (2026-08-28) where
  the two sides anchored to different `T0`s and silently ran disjoint
  schedules.
- **Blind TX starts** — TX can start before RX is armed/logging, losing the
  rehearsal pass (logger-off).
- **RF recon leak** — plaintext kind-30315 tallies reveal PER curves and
  movement to anyone watching the relay.

The existing CVM transport (`cvm_board_server.py` / `cvm_campaign.py`) already
speaks gift-wrapped NIP-59 kind-1059 JSON-RPC over a relay failover set. This
ADR replaces the manual T0 relay with a **message-derived T0** carried by an
`ARMED` message, and adds a **verdict publisher** that wraps `range_check.py`
output into the same channel.

## 2. Decision

### 2.1 Message-derived T0 (not literal epoch-0)

RX is the **sole session authority**. At arm time RX generates:

```
session_id = %y%m%d%H%M + 3-hex-nonce     # e.g. 2608301430a3f
```

and publishes an `ARMED` message carrying:

| Field          | Meaning                                              |
|----------------|------------------------------------------------------|
| `session_id`   | RX-generated at arm time (RX is sole authority)      |
| `stop`         | distance stop id, e.g. `50m`                         |
| `t_ready_utc`  | epoch seconds when RX is ready to receive            |
| `preset_hash`  | sha256 of the config preset (both sides must match)  |
| `seq`          | monotonic re-broadcast counter (idempotency)          |

Both sides compute `T0 = t_ready_utc + 30s` margin, then the **existing**
T0-anchored cycle machinery runs unchanged (drift-safe re-anchor per cycle).
Absolute-T0 semantics are kept for log correlation + GPS stitching.

### 2.2 ARMED re-broadcast + freshness

- RX re-broadcasts `ARMED` every **10–15 s** until it observes `GO`.
- Re-broadcasts are **idempotent** (same `session_id`; `seq` increments).
- TX-side freshness watchdog:
  - reject any `ARMED` whose `created_at` skew is **> 60 s**;
  - **abort** if the last good `ARMED` is **stale > 30 s** (no fresh
    re-broadcast seen).

### 2.3 Transport: gift-wrapped NIP-59 kind-1059 STORED wrappers

- Messages are **gift-wrapped NIP-59 kind-1059 stored wrappers** (durable +
  private), **not** plaintext kind-30315 (RF recon leak).
- Reuse ~75% of `cvm_board_server.py` transport: `nostr_sdk ClientBuilder`,
  `NostrSigner.keys`, `gift_wrap`, `HandleNotification` class, relay failover
  set (`nostr.mom`, `relay.primal.net`, `nos.lol`, `relay2.contextvm.org`,
  `relay.nostr.band`; `relay.contextvm.org` is DEAD).
- Keys via **env var, never CLI arg**. Client/server keys **must differ**.

#### 2.3.1 Emission chokepoint and the kind guard

The wrap is built and emitted by exactly one module,
`firmware/e80-stm32-bench/tools/nostr_giftwrap.py`:

- `build_gift_wrap(payload, tx_npub, signer)` builds the inner kind-25910 rumor
  and calls the upstream `nostr_sdk.gift_wrap` — the same primitive
  `cvm_board_server.py` uses. It re-implements neither signing nor the relay
  client, and it does not mint or validate the session (that is the ARMED
  payload interface it transports).
- `publish_gift_wrap()` is the **single emission choke-point**. The kind guard
  `assert_gift_wrap_kind()` runs **before** `client.send_event()`, so a
  non-kind-1059 event can never be queued on a relay pool.
- `assert_gift_wrap_kind()` **raises** `PlaintextKindError` (an `AssertionError`
  subclass) on any kind other than 1059 — it never downgrades and never
  re-tags. **kind 30315 (plaintext ARMED/tally) is FORBIDDEN** and is named in
  the assertion message (§1, RF recon leak).
- `assert_recipient_tag()` asserts the outer `p` tag equals the TX npub, and
  `assert_no_plaintext_leak()` asserts no payload fragment is visible in any
  tag value or the content field.
- `publish_armed(...)` is the failover-layer entry point (build + publish).

`tools/test_nostr_giftwrap.py` pins all of the above (23 tests, runnable
without `nostr_sdk`); `tools/test_giftwrap_single_path.py` pins this module's
single `gift_wrap` call site alongside the existing construction paths.

### 2.4 TX-side subscribe

- Subscribe **broad** to kind 1059 + **client-side npub allowlist** (server-side
  `#p` filtering is unreliable — established in `cvm_board_server.py`).

### 2.5 Verdict publisher

- Wrap `range_check.py` output (per-config `OK`/`THIN`/`MISS` + counts +
  `resend-<stop>.json` inline) into the same channel.
- **Config-end granularity** (NOT per-packet) — one verdict per stop, matching
  `range_check`'s `verdict_line` output.

## 3. Consequences

- Kills the 5-minute boundary wait, the human Signal T0 relay, the desync
  class, and blind TX starts.
- Legacy boundary+Signal path stays as fallback (boat / no-internet).
- `range_check` join key switches to `session_id` with `t0` fallback (Phase 2).
- `rx_lead` bumps to ≥ 5 s in GO mode (Phase 2).
- Monotonic-clock anchor captured at event instant (NTP step mid-pass must not
  shift a side) (Phase 2).

## 4. Phase 1 scope (this task)

- `docs/ADR-range-sync-cvm.md` (this file).
- Message layer: `ARMED` publish (RX) + subscribe/freshness (TX) + verdict
  publisher, reusing the CVM transport.
- TDD RED-then-GREEN per new behavior.
- Docs changed in the same commit as the code.

Phase 2 (`t_72586d0e`) wires derived-T0 GO mode into `e80_bench_ctl`; Phase 3
(`t_f73fc5df`) adds TX waiter UX + `make range-cvm-test` preflight.
