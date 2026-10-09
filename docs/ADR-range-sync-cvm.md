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

The 3-hex nonce (4096 space) disambiguates two arms inside the same minute and
comes from the **CSPRNG** (`secrets.randbelow`), so a third party cannot predict
the next session id. `cvm_sync.generate_session_id()` is a twin of the
authoritative `cvm_armed_publisher.generate_session_id()` — a parity test pins
that the two agree on shape and nonce source.

RX then publishes an `ARMED` message carrying:

| Field          | Meaning                                              |
|----------------|------------------------------------------------------|
| `session_id`   | RX-generated at arm time (RX is sole authority)      |
| `stop`         | distance stop id, e.g. `50m`                         |
| `t_ready_utc`  | epoch seconds when RX is ready to receive            |
| `preset_hash`  | sha256 of the config preset (both sides must match)  |
| `seq`          | monotonic re-broadcast counter (idempotency)          |
| `created_at`   | publish epoch seconds; **REQUIRED**, strict `int`    |

Both sides compute `T0 = t_ready_utc + 30s` margin, then the **existing**
T0-anchored cycle machinery runs unchanged (drift-safe re-anchor per cycle).
Absolute-T0 semantics are kept for log correlation + GPS stitching.

### 2.2 ARMED re-broadcast + freshness

- RX re-broadcasts `ARMED` every **10–15 s** until it observes `GO`.
- Re-broadcasts are **idempotent** (same `session_id`; `seq` increments).
- TX-side freshness watchdog:
  - reject any `ARMED` whose `created_at` skew is **> 60 s**;
  - `created_at` is a **required** ARMED field and must be a strict integer —
    `cvm_sync.validate_armed()` never `int()`-casts a value off the wire, so a
    malformed `created_at` is rejected with a reason instead of raising, and an
    absent one can no longer skip the skew window (Gate-2.5 R1);
  - the author allowlist is checked **before** any `created_at` parsing, so a
    hostile payload is rejected on identity and can never reach the arithmetic
    (no crash-before-authz);
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
  - Enforced (RX side) by `firmware/e80-stm32-bench/tools/cvm_armed_publisher.py`:
    `load_env_secrets()` resolves the RX client key by precedence
    `CVM_RX_NSEC`/`CVM_RX_HEX` → `CVM_CLIENT_NSEC`/`CVM_CLIENT_HEX` →
    `E80_RX_NSEC`/`E80_RX_HEX`, the board server key from
    `CVM_SERVER_NSEC`/`CVM_SERVER_HEX`, and the TX npub from `CVM_TX_NPUB` or
    its `E80_TX_NPUB` alias (`tx_npub_from_env()`; the CLI then requires
    `--tx-npub`). The canonical `CVM_*` name always wins when both are set, and
    every alias is read from the environment only. The CLI parser exposes **no**
    key-bearing option, and `assert_keys_differ()` aborts startup when the two
    pubkeys match. The ARMED re-broadcast loop lives here too (10-15 s,
    idempotent seq, stops on TX's GO) and emits **only** kind 1059.
    Tests: `tools/test_cvm_armed_publisher.py` (includes the `E80_*` alias
    cases; no `nostr_sdk` required).

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
- `event_view()` normalizes an event from either a real `nostr_sdk.Event` or a
  plain mapping. Real `Tag`s are **not iterable**: elements are read via
  `Tag.as_vec()`, the same accessor `cvm_board_server._extract_p_tag` uses.
- `publish_armed(...)` is the failover-layer entry point (build + publish).

`tools/test_nostr_giftwrap.py` pins all of the above (28 tests, runnable
without `nostr_sdk`); `tools/test_giftwrap_single_path.py` pins this module's
single `gift_wrap` call site alongside the existing construction paths. Because
a fake SDK once hid a real event-shape bug, `tools/test_nostr_giftwrap_realsdk.py`
runs the actual NIP-59 wrap/unwrap round trip when the bindings are installed
(skipped in the bare CI image), plus `test_nostr_giftwrap.py::TestRealSdkTagShape`
pins the non-iterable `Tag` shape without needing the bindings.

### 2.4 TX-side subscribe

- Subscribe **broad** to kind 1059 + **client-side npub allowlist** (server-side
  `#p` filtering is unreliable — established in `cvm_board_server.py`).

### 2.5 Verdict publisher

- Wrap `range_check.py` output (per-config `OK`/`THIN`/`MISS` + counts +
  `resend-<stop>.json` inline) into the same channel.
- **Config-end granularity** (NOT per-packet) — one verdict per stop, matching
  `range_check`'s `verdict_line` output.
  - Enforced (RX side) by `firmware/e80-stm32-bench/tools/cvm_verdict_publisher.py`:
    `build_verdict()` normalizes the per-config rows to the pinned
    (`idx`, `label`, `n_pkts`, `counted`, `status`) shape with `status` ∈
    {`OK`, `THIN`, `MISS`}, inlines the `resend-<stop>.json` content **verbatim**
    (deep copy, never a path), and carries the `session_id` + `stop` linkage
    fields; `validate_session_link()` refuses a verdict that does not match the
    pinned `armed.json` from phase 1. `RxVerdictPublisher.publish_config_end()`
    publishes **exactly one** message per completed config scan — the wire
    message count is independent of the packet count. The one-liner summary is
    `range_check.verdict_line()` itself (no second formatter to drift), and the
    empty-results LOGGING GAP variant is carried as `log_gap: true`. Transport,
    env-only keys, client≠server assertion and the relay failover set are
    reused from `cvm_armed_publisher.py`; the only send path is the NIP-59
    kind-1059 gift wrap (inner envelope kind 25910) — no plaintext kind-30315.
    Tests: `tools/test_cvm_verdict_publisher.py` (45 cases, no `nostr_sdk`
    required).

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

### 4.1 Phase 3 progress — TX-side production listener

`tools/cvm_tx_listener.py` (kanban `t_412706f8`) implements §2.4 + the §2.2
watchdog against a real bus:

- **broad subscribe** to kind-1059 (the `#p` filter is never pushed to the
  relay) + **client-side npub allowlist** — the check keys off the *unwrapped
  rumor author*, because the outer gift-wrap author is ephemeral; non-allowlisted
  authors are dropped and events authored by SELF are ignored.
- **payload validation**: `session_id` must match `%y%m%d%H%M` + 3 lowercase-hex
  (10 digits + 3 hex), plus the required ADR fields
  (`session_id`, `stop`, `t_ready_utc`, `preset_hash`, `seq`).
- **freshness watchdog**: `MAX_CREATED_AT_SKEW` (60 s) strict-`>` rejection of
  `created_at` skew, and `STALE_ABORT` (30 s) abort — from the last good ARMED,
  or from start-up when no ARMED ever arrives — logging a clear abort reason.
  Both thresholds are re-exported from `cvm_sync` so they cannot drift.
- **relay failover set** identical to §2.3; dead `relay.contextvm.org` filtered
  even if supplied.
- **keys via env only** (`CVM_TX_NSEC`/`CVM_TX_HEX` + `CVM_SERVER_NSEC`/`_HEX`);
  the CLI exposes no key-bearing option and client==server aborts startup.

The RX counterpart (`tools/cvm_armed_publisher.py`, kanban `t_0049ed58`) lands
separately; until both are merged a field GO TX still has the `--armed-file`
fallback.
