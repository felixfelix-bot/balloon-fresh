# Integration Assessment — balloon-nostr (Nostr Store-and-Forward)

**Date:** 2026-08-05
**Assessor:** balloon-hermes orchestrator (delegated)
**Track scope:** Nostr store-and-forward relay layer for ESP32-C3 flight platform

---

## Track Scope and Components

Deliver a **Nostr store-and-forward** node that relays events over LoRa (via
FIPS mesh), NOT a NIP-01 WebSocket relay. Per `mesh-stack/AGENTS.md`: "Nostr
goes over FIPS over LoRa."

**Components in balloon-fresh:**
- `firmware/components/nostr_store/` — RAM-only event ring-buffer with bloom-filter dedup
- `firmware/components/stratorelay/` — Header-only C++ mesh clustering layer (ADR-013)

## What Works (Proven, Tested)

- ✅ Bloom-filter dedup (FNV double-hash, 64-byte bitfield) — 7/7 unit tests pass
- ✅ FIFO ring buffer with capacity eviction
- ✅ `nostr_store_find()` by 32-byte event id
- ✅ Custom binary serialization (`nostr_event_serialize`)
- ✅ StratoRelay utilities: 11/11 tests pass (UnionFind, NodeTable, StaticBloomFilter, ClusterHeadElector)

## What Doesn't Work (Blockers)

- ❌ **`nostr_event_deserialize` declared in header but NEVER DEFINED** — no
     round-trip from wire. Blocker for any receive path.
- ❌ **RAM-only.** No persistence. Events lost on brownout/reboot (normal flight
     condition). A store-and-forward relay MUST survive power cycles.
- ❌ **No filtering.** Only `get(index)` and `find(id)`. Cannot answer
     "kind 30023 from pubkey X since time T" — the exact query a ground station needs.
- ❌ **No signature validation.** Events accepted without Schnorr check. A
     forwarding relay that doesn't validate propagates garbage/forgeries.
- ❌ **No expiry/TTL/cleanup.** No NIP-40 expiration, no time-based eviction.
- ⚠️ **Bloom hash spread is weak** — `1 << (h1 % 8)` only selects bits 0–7
     within a byte. Higher false-positive rate than the 64-byte field implies.

## C3 Portability Assessment

**🚨 CRITICAL — does NOT fit on ESP32-C3 as written:**

`nostr_event_t` is **1212 bytes** (id[32] + pubkey[32] + created_at[4] + kind[2]
+ content_len[2] + content[480] + 8×82-byte tags). With `NOSTR_STORE_CAPACITY = 512`:

```
nostr_store_t  =  512 × 1212 + 64 (bloom)  ≈  606 KB
C3 free heap   =  258 KB
store alone    =  235% of heap  ←  CANNOT be instantiated
```

**Required for C3 fit:** Flash-backed storage (LittleFS/SPIFFS), reduced event
size (cap content at 128–256B, limit tags to 2–4), or a streaming relay model
that forwards without buffering. StratoRelay layer (~6.5 KB) is C3-safe.

## What's Next

1. Implement `nostr_event_deserialize` — unblocks receive path
2. Redesign for flash persistence (LittleFS-backed store, <50 KB RAM working set)
3. Add subscription/filter engine (kind + pubkey + since/until)
4. Add Schnorr signature validation (reuse libsecp256k1 from TollGate wallet)
5. Add NIP-40 expiry + periodic cleanup task
6. Fix bloom hash spread (use full hash bits, not just `h1 % 8`)
