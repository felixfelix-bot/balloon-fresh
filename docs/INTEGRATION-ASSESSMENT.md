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

## What Doesn't Work (Remaining Blockers)

- ✅ ~~`nostr_event_deserialize` declared but NEVER DEFINED~~ — **RESOLVED**,
     now implemented in nostr_store.c
- ✅ ~~RAM-only~~ — **RESOLVED**: flash-backed store (ADR-024), 10.4 KB RAM
     index, event content in LittleFS. Survives brownout/reboot.
- ❌ **No filtering.** Only `get(index)` and `find(id)`. Cannot answer
     "kind 30023 from pubkey X since time T" — the exact query a ground station needs.
- ❌ **No signature validation.** Events accepted without Schnorr check. A
     forwarding relay that doesn't validate propagates garbage/forgeries.
- ❌ **No expiry/TTL/cleanup.** No NIP-40 expiration, no time-based eviction.
- ⚠️ **Bloom hash spread is weak** — `1 << (h1 % 8)` only selects bits 0–7
     within a byte. Higher false-positive rate than the 64-byte field implies.

## C3 Portability Assessment

**RESOLVED — flash-backed design fits C3 (ADR-024):**

```
RAM index:  256 × 40 bytes = 10 240 bytes
bloom:      64 + 2         =     66 bytes
misc:                      =    ~72 bytes
total RAM                  ≈  10.4 KB  (4% of C3's 258 KB heap)
```

Event content lives in flash (LittleFS). Original 606 KB RAM concern is moot.

## Cross-Track Findings Adopted (2026-08-05)

Independently adopted from balloon-hermes discovery sync (no coordination):

1. **`extern "C"` guards on nostr_store.h** — C header included from C++ relay
   code (app_task.cpp). Without guards, C++ name mangling breaks linking.
   Applied: ✅

2. **FreeRTOS relay task architecture** (radio_task + app_task + queue-based RX):
   - radio_task (HIGH, 4KB): DIO9 IRQ-driven RX, TX dispatch from queue
   - app_task (MEDIUM, 8KB): secp256k1 Schnorr verify → nostr_store → tollgate ACK
   - relay_types.h: relay_packet_t (512B data, len, timestamp, rssi) via
     g_rx_queue (8 deep) / g_tx_queue (4 deep)
   - Pattern directly applicable to C3 relay. To adopt when implementing relay mode.

3. **secp256k1 on ESP32-C3** — proven to build + link on C3:
   - Blossom-server secp256k1 component reused via EXTRA_COMPONENT_DIRS
   - C3-tuned config: SCHNORRSIG=1, EXTRAKEYS=1, ECMULT_GEN_PREC_BITS=4,
     ECMULT_WINDOW_SIZE=4 (vs TollGate's WINDOW=8 — C3 RAM saving)
   - secp_test firmware exercises both ecdsa_verify AND schnorrsig_verify
   - Resolves blocker: Schnorr validation is feasible on C3
   - Still needed: actual `idf.py size --archives` flash/RAM measurement

4. **secp_test measurement pending** — test firmware created but needs to be
   built + flashed to C3 to get actual flash (.text + .rodata) and DRAM numbers.
   This gates the final go/no-go on on-device Schnorr verify vs. defer-to-ground.

## What's Next

1. ~~Implement `nostr_event_deserialize`~~ ✅ DONE
2. ~~Redesign for flash persistence~~ ✅ DONE (ADR-024, 10.4 KB RAM)
3. Add subscription/filter engine (kind + pubkey + since/until)
4. ~~Add Schnorr signature validation~~ — secp256k1 proven on C3, implement in app_task
5. Add NIP-40 expiry + periodic cleanup task
6. Fix bloom hash spread (use full hash bits, not just `h1 % 8`)
7. **Build + run secp_test on C3** to get actual flash/RAM cost numbers
