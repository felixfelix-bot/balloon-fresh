# STATUS — balloon-nostr (Nostr Store-and-Forward Track)

**Last updated:** 2026-07-29
**Phase:** Extraction plan complete; implementation not started
**Author:** balloon-nostr sub-manager

## Track Goal

Deliver a **Nostr store-and-forward** layer for the ESP32-C3 flight platform.

Per `mesh-stack/AGENTS.md`: there is **no WiFi/BLE on the balloon** — all
communication is over LoRa, and "Nostr goes over FIPS over LoRa," **not** over a
WebSocket relay. Phase 3 goal: "Nostr store-and-forward + TollGate ground
station" (L7 layer: TollGate + Nostr async messaging).

This is a **store-and-forward** node, NOT a NIP-01 WebSocket relay. That
distinction drives the whole extraction plan below.

---

## 1. What already exists in balloon-fresh

### 1a. `nostr_store` component (firmware/components/nostr_store/)

A **RAM-only** event ring-buffer with bloom-filter dedup. Files:
- `include/nostr_store.h` — types + API
- `nostr_store.c` — implementation
- `test/test_nostr_store.c` — 7/7 tests pass (bloom, add/retrieve, dedup,
  find-by-id, FIFO overflow, serialize roundtrip, multi-event)

**What works:**
- ✅ Bloom-filter dedup (`nostr_bloom_*`: FNV-style double hash, 64-byte bitfield)
- ✅ FIFO ring buffer with capacity eviction
- ✅ `nostr_store_find()` by 32-byte event id
- ✅ Custom **binary** serialization (`nostr_event_serialize`)
- ✅ FNV event-id hash helper
- ✅ Tests are real and green

**Critical gaps / defects:**
- ❌ **`nostr_event_deserialize` is declared in the header (line 54) but NEVER
  DEFINED in `nostr_store.c`.** Serialize has no inverse — cannot round-trip
  from the wire. Blocker for any receive path.
- ❌ **RAM-only.** No persistence. Every event is lost on brownout / reboot,
  which is the normal flight condition. A store-and-forward relay MUST survive
  power cycles.
- ❌ **No filtering.** Only `get(index)` and `find(id)`. No way to answer
  "give me kind 30023 from pubkey X since time T" — which is exactly the query a
  ground station issues over LoRa.
- ❌ **No signature validation.** Events are accepted with no Schnorr check, no
  event-id hash verification. A forwarding relay that doesn't validate will
  propagate garbage/forgeries.
- ❌ **No expiry / TTL / cleanup.** No NIP-40 expiration, no oldest-eviction by
  time.
- 🐛 **Bloom hash spread is weak.** `1 << (h1 % 8)` only ever selects bit
  positions 0–7 within a byte, ignoring the higher hash bits. Still *functions*
  for dedup but with a higher false-positive rate than the bitfield size implies.
  Not a correctness blocker; worth fixing on copy.
- ⚠️ **Bloom is never shrunk/reset as the ring rolls over.** The bitfield grows
  monotonically while entries age out of the ring → false-positive rate inflates
  over a long flight.

**🚨 HEADLINE PROBLEM — cannot fit on the C3:**
`nostr_event_t` is **1212 bytes** (id[32] + pubkey[32] + created_at[4] + kind[2]
+ content_len[2] + content[480] + num_tags[1] + 8×(82-byte tag structs), padded
to 4-byte alignment). With `NOSTR_STORE_CAPACITY = 512`:

```
nostr_store_t  =  512 × 1212  +  64 (bloom)  ≈  606 KB
C3 free heap   =  258 KB
store alone    =  235 % of heap   ←  CANNOT be instantiated as a static/stack
                                     struct on the flight platform
```

This component, as written, does not fit in the C3 memory budget. It is a
prototype-quality dedup cache, not a flight relay.

### 1b. `stratorelay` component (firmware/components/stratorelay/)

Header-only C++ templates implementing the **mesh clustering** layer from
ADR-013 (cluster-aware stratorelay). **This is the LoRa mesh layer, separate
from and below Nostr.** Files: `StaticBloomFilter.h`, `UnionFind.h`,
`NodeTable.h`, `ClusterHeadElector.h`, `CMakeLists.txt`, plus
`test/test_stratorelay.cpp`.

Test suite (11 cases, all in `main()`): bloom insert/contains/non-member-FP/clear,
union-find basic/separate/path-compression, node-table insert/update/aging/eviction,
cluster-head election. ~6.5 KB static DRAM per ADR-013 budget (already allocated).

**Relevance to Nostr:** Nostr rides *on top of* this layer. Stratorelay decides
which ground nodes the balloon talks to; Nostr is the async messaging payload
carried over FIPS over LoRa. The two are decoupled. The nostr extract does **not**
touch stratorelay.

### 1c. Ground-station bridge + tests

- `tracker/ground-station/nostr_bridge/telemetry_to_nostr.py` — Python tool that
  reads JSON telemetry lines, builds **kind 30023** (parameterized-replaceable)
  events with `d`/`alt`/`voltage`/`sats`/`seq`/`geo` tags, computes the Nostr
  event id (canonical JSON → sha256), derives pubkey + Schnorr-signs via
  `coincurve`, and optionally publishes over `websockets` to a real relay. This
  is the **ground-station** side (runs where there IS internet), not the balloon.
- `tests/test_telemetry_to_nostr.py` — pytest: deterministic serialization/id,
  telemetry parsing, kind-30023 creation, geo-tag conditional, JSON content,
  signing adds 128-hex sig, pubkey derivation. All real, no mocks of crypto.

**Takeaway:** the ground-station bridge already defines the **wire format and
tag schema** the balloon store-and-forward must be able to ingest and serve
(kind 30023, the tag set above, Schnorr sigs). The balloon side is the missing
half.

### 1d. Relevant ADRs

- **ADR-013** (cluster-aware stratorelay): the ~6.5 KB clustering layer is
  already built and budgeted. Nostr must coexist within the remaining heap.
- **ADR-024** (extract-only source policy, ACCEPTED 2026-07-29): source repos
  (`wisp`, tollgate, microfips, blossom) are **READ-ONLY**. Balloon work must
  **COPY** balloon-relevant code into the balloon repo and adapt it — never
  reference source repos as dependencies, never modify them. The wisp row:
  extract a *lightweight event relay*; leave full relay features in source.

---

## 2. wisp-esp32 source — balloon-relevant modules

Source: `~/wisp-esp32/` (origin github.com/privkeyio/wisp-esp32), ESP32-S3
target. Per ADR-024 it is **read-only**; we copy, we do not reference.

### 2a. `storage_engine.c` / `.h` — LittleFS + NVS persistent store
- Flash-backed event bodies (LittleFS, sharded by `event_id[0]`), with a
  **52-byte packed index entry** persisted to NVS in 50-entry chunks:
  `event_id[32] + created_at[4] + expires_at[4] + file_index[4] + kind[2] +
  pubkey_prefix[4] + flags[1] + reserved[1]`.
- API: `storage_save_event`, `storage_query_events` (filter + limit + results),
  `storage_get_event`, `storage_delete_event`, `storage_event_exists`,
  `storage_purge_expired`, `storage_compact_index`, `storage_get_stats`,
  `storage_start_cleanup_task` (FreeRTOS TTL sweeper).
- `storage_stats_t` tracks totals, bytes, oldest/newest ts.
- Mutex-protected, default TTL configurable.
- Defaults are S3-sized (`STORAGE_MAX_EVENTS 5000`, `STORAGE_MAX_EVENT_SIZE 8192`,
  `STORAGE_INDEX_ENTRIES 5000` → 260 KB index alone) — **must be shrunk for C3.**

### 2b. `validator.c` / `.h` — full event validation pipeline
- Delegates schema + event-id-hash + **Schnorr signature** verification to
  `nostr_event_validate_full()` (libnostr-c / secp256k1), then layered checks:
  age (`max_event_age_sec`), future-skew (`max_future_sec`), NIP-13 PoW
  (`min_pow_difficulty`), duplicate (against storage, skipping ephemeral kinds).
- Clean `validation_result_t` enum + human strings + relay-error mapping.
- Config-driven (`validator_config_t`) — no hard-coded policy.
- Depends on `libnostr-c` + `secp256k1` (the real crypto cost — see §5).

### 2c. `sub_manager.c` / `.h` — NIP-01 filter + subscription matching
- Static slot table (`SUB_MAX_TOTAL 64`, 8 subs/conn, 4 filters/sub) behind a
  mutex.
- `nostr_filter_t` supports ids / authors / kinds / e_tags / p_tags / generic
  tag filters; deep-copies filter strings (malloc/strdup).
- **`sub_manager_match(event)` → set of matching sub ids** is the reusable core:
  given a stored or incoming event, find which active queries want it.
- API is connection-oriented (`conn_fd`) because wisp is a WS server — the
  `conn_fd` plumbing must be **stripped** for the LoRa pull model.

---

## 3. Extraction plan (copy FROM wisp-esp32, per ADR-024)

Order = dependency order. Each item: copy into
`tracker/firmware/components/`, adapt, add a CMake target + test, commit.

| # | Module | Copy from | Adapt for balloon | Why needed |
|---|--------|-----------|-------------------|------------|
| 1 | **Storage engine** | `storage_engine.{c,h}` | Replace 5000-event defaults with C3 caps (see §5). Keep LittleFS+NVS if a storage partition exists; else fall back to NVS-only index + in-flash bodies. Keep the 52-byte packed index, `query_events(filter)`, TTL sweeper, stats. | Persistence + filtered query — the two biggest gaps in `nostr_store`. |
| 2 | **Validator** | `validator.{c,h}` + the `libnostr-c`/`secp256k1` components it calls | Keep the config-driven pipeline. Verify secp256k1 fits C3 flash/heap (see §5). Drop PoW check if not needed for telemetry. | Store-and-forward must reject forged/invalid events before storing or re-forwarding. |
| 3 | **Filter/subscription matcher** | `sub_manager.c` `sub_manager_match()` + `nostr_filter_t` | Strip `conn_fd` / per-connection WS semantics. Repurpose as a **pull matcher**: a ground-station REQ over FIPS/LoRa carries a filter; the matcher selects stored events to return. | Answers the "give me kind 30023 from X since T" query the bridge implies. |
| 4 | **Shared protocol types** | `nostr_relay_protocol.h` (nostr_event, nostr_filter_t, relay error codes) | Copy the subset storage/validator/sub_manager depend on. | Compile dependency for 1–3. |
| 5 | **Bloom dedup (keep from balloon-fresh)** | existing `nostr_store` bloom | Lift the bloom into the new storage engine's hot path; fix the weak `h1 % 8` bit spread; add periodic reset on ring rollover. | Cheap duplicate rejection before the expensive sig verify + flash write. |

### 3a. What to LEAVE in wisp-esp32 (NOT balloon-relevant)

These are WebSocket-/internet-relay features. The balloon has no WiFi and no
HTTP server; Nostr runs over FIPS over LoRa. Do **not** copy:

| Module | Why leave |
|--------|-----------|
| `ws_server.{c,h}` | WebSocket server — no WiFi on balloon. |
| `nip11.{c,h}` | NIP-11 relay-info doc served over HTTP GET / — no HTTP server. |
| `rate_limiter.{c,h}` | Protects against abusive WS clients; LoRa airtime is the natural rate limit. |
| `broadcaster.{c,h}` | Pushes events to connected WS clients — no WS clients exist. |
| `router.{c,h}` | WS message routing/dispatch. |
| `flash_monitor.{c,h}` | Admin/monitoring for a standalone relay. |
| `relay_core.h` | WS-centric orchestration (reuse only the `config` struct idea). |
| `main.c`, `handlers_stub.c` | WS server bootstrap. |
| `deletion.{c,h}` (NIP-09) | Borderline; defer — not core to store-and-forward telemetry. |

---

## 4. Gap analysis: balloon-fresh vs a store-and-forward relay

| Capability | `nostr_store` (balloon-fresh) | store-and-forward needs | Source of fix |
|------------|-------------------------------|-------------------------|---------------|
| Persistence across reboot | ❌ RAM-only | ✅ flash/NVS | wisp `storage_engine` |
| Filtered query (kind/author/time/tags) | ❌ index/id only | ✅ | wisp `storage_engine.query_events` + `nostr_filter_t` |
| Signature validation | ❌ none | ✅ Schnorr + id hash | wisp `validator` + libnostr/secp256k1 |
| Dedup | ✅ bloom (weak spread) | ✅ | keep + fix bloom |
| TTL / expiry | ❌ | ✅ | wisp `storage_engine` sweeper |
| Pull-match for ground REQs | ❌ | ✅ (LoRa pull, not WS push) | wisp `sub_manager_match` (de-WS'd) |
| Wire format compat (kind 30023, tag schema) | ⚠️ custom binary only | ✅ match the Python bridge | align with `telemetry_to_nostr.py` |
| Deserialize | ❌ declared, undefined | ✅ | implement (binary) **or** add JSON for NIP-01 interop |
| Fits C3 memory (258 KB heap) | ❌ 606 KB | ✅ | storage_engine index, capped |

---

## 5. Memory footprint estimate for the extract (ESP32-C3)

Budget reality check (AGENTS.md): **258 KB free heap** after tracker firmware;
**~6.5 KB already allocated** to the stratorelay clustering layer.

| Item | RAM | Flash | Notes |
|------|-----|-------|-------|
| Storage index (capped) | **~13 KB** | — | 256 events × 52-byte packed entry. Tunable; 128 events → 6.5 KB. |
| Event bodies | — (on flash) | ~1 KB/event typical | LittleFS/NVS, not RAM. Telemetry events are tiny. |
| `sub_manager` matcher | **~4–8 KB** | — | 16 subs × 4 filters; shrink from wisp's 64. Filter strings malloc'd. |
| Validator runtime | **~2–4 KB** stack/heap per verify | — | Schnorr verify working memory. |
| `libnostr-c` + `secp256k1` | small statics | **~40–60 KB** | The dominant **flash** cost. Required for real sig checks. |
| Bloom dedup (reused) | **64 B** + code | <1 KB | From existing `nostr_store`. |
| **Extract RAM total** | **≈ 20–30 KB** | **≈ 50–70 KB** flash | Well within the 258 KB heap after the 6.5 KB clustering layer. |

**Contrast:** the current `nostr_store` alone is **606 KB RAM (235 % of heap)**
and is therefore unusable on the C3 as-shipped. Switching to the wisp
flash-indexed design is not an optimization — it is a **requirement** for flight.

**Open risk:** confirm the `secp256k1`/`libnostr-c` flash footprint actually
fits the C3's 4 MB flash alongside the tracker partition map. This is the one
number to measure first before committing to full Schnorr validation. If flash
is tight, a fallback is to validate event-id hash locally (cheap, no secp256k1)
and defer signature verification to the ground station.

---

## 6. Next steps (when implementation starts)

1. **Measure secp256k1 flash cost on C3** first — gates decision on full sig
   validation vs. ground-station-deferred validation.
2. Copy `nostr_relay_protocol.h` types → new component (compile dep).
3. Port `storage_engine` with C3 caps (256 events); add a storage partition if
   none exists; port the TTL sweeper.
4. Port `validator` (schema + id-hash always; sig if §1 passes).
5. Lift + de-WS `sub_manager_match` as the LoRa pull matcher.
6. Reuse + fix the bloom; **implement the missing `deserialize`**.
7. Wire the store behind the FIPS/LoRa transport (separate track), ingesting the
   kind-30023 + tag schema already proven by `telemetry_to_nostr.py`.
8. Tests per component (mirror wisp's `test/` + balloon's existing test style).

## 7. Current state checklist
- [x] Source read & summarized (nostr_store, stratorelay, bridge, wisp modules)
- [x] Memory feasibility analyzed (nostr_store does NOT fit C3)
- [x] Extraction plan produced (this document)
- [ ] secp256k1 C3 flash measurement
- [ ] storage_engine port (capped)
- [ ] validator port
- [ ] sub_manager_match (de-WS'd) port
- [ ] deserialize implemented
- [ ] bloom fix + reuse
