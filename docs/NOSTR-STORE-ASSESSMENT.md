# `nostr_store` Assessment — Flash-Backed Persistence, RAM & Query Capabilities

**Date:** 2026-08-05
**Scope:** `tracker/firmware/components/nostr_store/{nostr_store.c, include/nostr_store.h, test/test_nostr_store.c}`
**Comparison source:** `~/wisp-esp32/main/storage_engine.{c,h}` (per ADR-024, read-only reference)
**Method:** Source read + host build & run of the existing unit tests.

---

## TL;DR

The consultant's claim is **correct**: `nostr_store` is flash-backed via POSIX file
I/O, uses **~10.1 KB RAM** (verified by `sizeof(nostr_store_t)` on host), and uses a
bloom filter for dedup. The earlier `docs/STATUS-balloon-nostr.md` description
(RAM-only, 606 KB, missing `deserialize`) is **stale** — the component has been
rewritten and **all of those specific complaints are resolved**.

What remains true vs `wisp-esp32/storage_engine.c`:

| Capability | `nostr_store` (current) | `wisp` storage_engine |
|---|---|---|
| Event bodies on flash | ✅ POSIX `.evt` files | ✅ LittleFS, sharded by `id[0]` |
| **Index persisted across reboot** | ❌ **RAM-only index** | ✅ NVS chunked blobs |
| RAM footprint | ✅ **10.1 KB** | 260 KB at S3 defaults |
| Filtered query (kind/author/time) | ❌ id/index only | ✅ `query_events(filter)` |
| TTL / NIP-40 expiry | ❌ FIFO count only | ✅ `expires_at` + sweeper task |
| Thread safety | ❌ no locks | ✅ FreeRTOS mutex |
| `deserialize` exists | ✅ defined + tested | ✅ (JSON via libnostr-c) |
| Wire format | ⚠️ custom binary | ✅ JSON (NIP-01) |

The single most important remaining gap is **#1 — the index is not persisted**.
Flash files survive reboot but the in-RAM index that maps `event_id → file_idx` is
zeroed on every boot, so the store cannot find its own persisted events after a
power cycle. Everything else (filtering, TTL, thread safety) is an additive feature.

---

## 1. How does it store events?

**Event bodies: flash files. Event index: RAM.**

- `nostr_store_init(store, storage_dir)` records a directory path and `mkdir()`s it.
  On target the caller mounts LittleFS at that path and passes it in; on host a plain
  directory works because the code uses **only POSIX calls** (`fopen`/`fwrite`/`fread`/
  `unlink`/`mkdir`). Confirmed in source (lines 187, 202, 219) and verified by the
  host test run writing to `/tmp/nostr_test/`.
- Each event is serialized via `nostr_event_serialize()` into a flat file named
  `<storage_dir>/<file_idx>.evt`, where `file_idx` is a monotonic 32-bit counter.
  No sharding (wisp shards by `event_id[0]` into 256 subdirs; nostr_store does not).
- The **RAM index** (`store->index[256]`) holds only `{id[32], file_idx, created_at}`
  per entry (40 bytes packed) — enough to locate a file by event id or by FIFO slot,
  **not** enough to filter by pubkey/kind without re-reading the file.
- FIFO eviction at capacity 256 calls `delete_event_file()` (real `unlink`) before
  overwriting the slot, so flash does not leak orphaned files on eviction.

**Serialization format** (binary, custom — NOT NIP-01 JSON):

```
[32 id][32 pubkey][4 created_at BE][2 kind LE][2 clen LE]
[clen bytes content][1 num_tags]
per tag: [1 key_len][1 val_len][key bytes][val bytes]
```

`created_at` is big-endian; `kind`/`content_len` are little-endian (mixed
endianness is a minor wart, not a bug). Max serialized size is
`NOSTR_SER_BUF_SIZE = 1024` bytes; content capped at `NOSTR_MAX_CONTENT = 480`.

---

## 2. Actual RAM footprint

Measured on host with `cc` (x86-64, normal alignment):

```
sizeof(nostr_event_t)     = 1212 bytes   ← per-event, lives in CALLER's RAM/stack
sizeof(nostr_index_entry) = 40 bytes     ← packed, asserted by test
sizeof(nostr_store_t)     = 10380 bytes  (10.1 KB)
  index: 256 × 40 = 10240 bytes
  bloom: 66 bytes
```

**Breakdown of `nostr_store_t` (10 380 B):**

| Field | Size |
|---|---|
| `index[256]` (40 B packed entry) | 10 240 B |
| `bloom` (64 B bitfield + 2 B count) | 66 B |
| `head`, `count` (uint16 ×2) | 4 B |
| `next_file_idx` (uint32) | 4 B |
| `storage_dir[64]` | 64 B |
| tail padding | ~2 B |

**Per-operation stack/heap cost (not counted in `sizeof(store)`):**

| Buffer | Size | Where |
|---|---|---|
| `NOSTR_SER_BUF_SIZE` in `write_event_file` / `read_event_file` | 1024 B | stack |
| `path[NOSTR_STORE_DIR_LEN + 16]` | 80 B | stack |
| `nostr_event_t` passed in/out by caller | 1212 B | caller's stack/heap |

**Peak RAM during add/get: ≈ 10.1 KB (store) + ~1.1 KB (ser buf + path) + 1.2 KB
(event struct) ≈ 12.4 KB.** Comfortably inside the ESP32-C3's 258 KB heap, even
with the ~6.5 KB stratorelay clustering layer already allocated.

The consultant's "~10 KB RAM" claim is accurate. The earlier 606 KB figure in
`STATUS-balloon-nostr.md` was for an older version that stored full
1212-byte `nostr_event_t` structs in the ring (`512 × 1212`); the rewrite stores
only 40-byte index entries in RAM and pushes the event body to flash.

---

## 3. Flash footprint

- **Code:** minimal — pure C, no external deps beyond libc/POSIX. Rough estimate
  3–5 KB `.text`. The `CMakeLists.txt` registers the component with empty `REQUIRES`.
- **Per-event data:** serialized blob = 72 B header + `content_len` + Σ tag bytes.
  For a typical kind-30023 telemetry event (~50 B content, 1 tag ~20 B): ~140 B.
- **Steady-state event data:** 256 events × ~140 B ≈ **~35 KB** (capped by FIFO).
- **No persistent index file.** Only `.evt` blobs are written; the id→file_idx map
  lives only in RAM (see gap #1 below). Flash does not grow unbounded because
  eviction `unlink`s the old file before reusing the slot.

---

## 4. Query capabilities

| Operation | API | Cost |
|---|---|---|
| Find by event id | `nostr_store_find(id, out)` | bloom pre-filter + O(n) scan of `index[].id`, then 1 flash read |
| Get by FIFO slot | `nostr_store_get(index, out)` | O(1) index lookup + 1 flash read |
| Duplicate check | `nostr_store_is_duplicate(id)` | bloom + O(n) scan (no flash read) |
| Count | `nostr_store_count()` | O(1) |
| **Filter by pubkey** | ❌ none | would require reading every `.evt` and parsing |
| **Filter by kind** | ❌ none | same — index does not store `kind` |
| **Filter by time (since/until)** | ❌ none | index stores `created_at` but no range-scan API exists |
| **Filter by tag (e/d/p/generic)** | ❌ none | not indexed at all |

The index entry deliberately carries only `{id, file_idx, created_at}`. To answer
"give me kind 30023 from pubkey X since T" — the exact query a ground station
issues over LoRa — you would have to iterate all 256 slots, deserialize each from
flash, and test in memory. That is workable at n=256 but is exactly what wisp's
`storage_query_events(filter)` + `index_matches_filter()` provide for free, using
a 52-byte index entry that also carries `kind` and `pubkey_prefix[4]`.

---

## 5. Deserialize function

**Yes — `nostr_event_deserialize()` is defined, exported, and tested.**

- Declared in header line 121, **defined** in `nostr_store.c` lines 104–154.
- Inverse of `serialize`: parses `id`, `pubkey`, `created_at` (BE), `kind` (LE),
  `content_len` (LE), content, `num_tags`, and each tag.
- Has bounds checks at every step (`buf_len < 73`, `content_len > NOSTR_MAX_CONTENT`,
  `num_tags > NOSTR_MAX_TAGS`, `key_len > 16`, `value_len > NOSTR_TAG_MAX_LEN`,
  `pos + ... > buf_len`). Returns 0 on any malformed input.
- Test 6 (`serialization roundtrip`) poisons the output struct with `0xFF`, then
  round-trips a kind-30023 event with one tag and asserts every field matches —
  green.

This **resolves** the "declared but never defined" blocker flagged in
`STATUS-balloon-nostr.md` (which was written against the pre-rewrite version).

> Caveat: the deserialize handles the **custom binary** format, not NIP-01 JSON.
> The Python ground-station bridge (`telemetry_to_nostr.py`) emits JSON kind-30023
> events; `nostr_store` cannot ingest that wire format directly. Either add a JSON
> parser, or carry a binary-only protocol over the LoRa mesh.

---

## 6. What's missing vs `wisp-esp32/storage_engine.c`

In priority order for a store-and-forward relay:

1. **Index persistence across reboot (BLOCKER for flight).** The `.evt` files
   survive power loss but the RAM index is wiped on every boot — after a brownout
   the store cannot find any of its own persisted events, dedup resets, and FIFO
   starts over. wisp persists its index to NVS in 50-entry chunks
   (`save_index_to_nvs`/`load_index_from_nvs`) and reloads on `storage_init`.
   This is the one feature without which "flash-backed" is misleading: the bytes
   are on flash, but the store is amnesiac about them.
2. **Filtered query API.** No `query_events(filter)`. The 40-byte index entry
   lacks `kind` and `pubkey_prefix`; widening it to wisp's 52-byte layout
   (`+kind[2] +pubkey_prefix[4] +expires_at[4] +flags[1] +reserved[1]`) costs
   12 B × 256 = 3 KB extra RAM and unlocks index-side filtering on kind/time/
   author-prefix without touching flash.
3. **TTL / NIP-40 expiry.** No `expires_at`, no `storage_purge_expired`, no
   background sweeper. Only FIFO-by-count eviction. A long flight with bursty
   telemetry will keep stale events until count-evicted.
4. **Thread safety.** No mutex. Fine for a single-task prototype; will race if
   the LoRa RX path and a ground-station REQ handler ever touch the store
   concurrently.
5. **Per-event delete.** No `storage_delete_event(id)` (only FIFO eviction).
   Needed if NIP-09 deletion or explicit purge is ever required.
6. **Stats / introspection.** No `storage_get_stats` (totals, bytes, oldest/newest
   ts). Useful for flight telemetry and debug.
7. **NIP-01 JSON wire format.** Custom binary only. Acceptable if the balloon
   uses a binary mesh protocol end-to-end; a mismatch if it must interoperate
   with JSON-emitting clients/relays.
8. **Bloom filter reset on rollover (minor).** FIFO eviction does not clear the
   evicted id's bloom bits, so the false-positive rate inflates monotonically
   over a long flight. The earlier "weak hash spread" complaint in
   `STATUS-balloon-nostr.md` is **obsolete**: the current code uses
   `(h1 % 512)/8` for the byte and `h1 % 8` for the bit, which is correct
   because 512 is divisible by 8, so `(h1 % 512) % 8 == h1 % 8`.

Features `nostr_store` has that wisp does **not** (or has worse): a 512-bit bloom
dedup pre-filter (wisp does a linear scan only), and a C3-appropriate default
capacity (256 vs wisp's S3-sized 5000).

---

## 7. Existing tests — and do they run on host?

**Yes.** `test/test_nostr_store.c` — 7 tests, **all pass on host with `cc`**:

```
cc -Wall -Wextra -O2 -I include -o /tmp/test_nostr_store \
   nostr_store.c test/test_nostr_store.c && /tmp/test_nostr_store
```

Result (this run, 2026-08-05):

```
sizeof(nostr_event_t)     = 1212 bytes
sizeof(nostr_index_entry) = 40 bytes
sizeof(nostr_store_t)     = 10380 bytes  (10.1 KB)
  index: 256 × 40 = 10240 bytes
  bloom: 66 bytes

TEST 1: bloom filter add/check... PASS
TEST 2: store add + retrieve (flash)... PASS
TEST 3: duplicate detection... PASS
TEST 4: find by ID... PASS
TEST 5: FIFO overflow (capacity=256)... PASS
TEST 6: serialization roundtrip... PASS (104 bytes roundtripped)
TEST 7: multiple events with dedup... PASS

=== Results: 7/7 passed ===
```

Coverage: bloom add/check/non-member, add+retrieve from real flash files,
duplicate rejection (return code 1), find-by-id with flash read-back, FIFO
overflow at capacity 256 (oldest 10 evicted, files unlinked), full
serialize→deserialize roundtrip with field-by-field verification (incl. tags),
multi-event dedup + read-back.

**Caveats:**
- Tests are **not wired into CMake** — `CMakeLists.txt` registers only
  `nostr_store.c` as an IDF component source; the test file is built manually per
  the comment at the top of `test_nostr_store.c`. No `idf.py create-component-test`
  / host test target exists. Adding a `test/CMakeLists.txt` with a host-mode
  executable would let CI run them.
- No test exercises the missing features (reboot persistence, filtered query,
  TTL) — because those features do not exist yet.
- No concurrency test (the store has no locks to break).

---

## 8. Recommendation (per SIMP-3 in `CONSULTANT-PLAN-REVIEW.md`)

**Do not write a new component. Extend `nostr_store` in place.**

The current code is a clean, tested, correctly-sized foundation. The rewrite has
already closed the three biggest complaints from the earlier status doc
(RAM size, missing deserialize, "RAM-only" event bodies). What remains is
additive:

1. **Persist the index** — either to NVS (wisp's approach) or to a single
   `index.bin` file in `storage_dir` loaded on `init`. This is the only item that
   is truly blocking for a flight store-and-forward relay.
2. **Widen the index entry** to 52 bytes (`+kind`, `+pubkey_prefix[4]`,
   `+expires_at[4]`, `+flags`) and add `nostr_store_query(filter, out, limit)`.
   Cost: 3 KB extra RAM (still ~13 KB total — trivial).
3. **Add TTL sweeper** (`expires_at` + a periodic or on-access purge).
4. **Add a mutex** if/when the store is touched from more than one task.
5. **Decide wire format** (binary vs NIP-01 JSON) explicitly before integrating
   with the LoRa transport and the Python bridge.

Items 1–2 are the minimum to call this a flight-grade store-and-forward layer;
3–5 can follow incrementally.
