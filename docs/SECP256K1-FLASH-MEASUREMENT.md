# secp256k1 Flash/RAM Measurement on ESP32-C3

**Date:** 2026-08-05
**Status:** MEASURED — ADR-026 UNBLOCKED
**Verdict:** Full Schnorr verification FITS on C3 with margin

## Measurement

Isolated ESP32-C3 project (`firmware/tests/secp_test/`) that links ONLY libsecp256k1
and calls both `secp256k1_ecdsa_verify()` and `secp256k1_schnorrsig_verify()` with
dummy data. GC-sections cannot drop the crypto code because it's referenced.

### Per-Archive Breakdown (from `esp_idf_size --archives`)

| Archive | DRAM (.data + .bss) | Flash (.text + .rodata) | Total |
|---------|--------------------:|------------------------:|------:|
| **libsecp256k1.a** | **0 bytes** | **68,725 bytes** | **68,725 bytes** |

### Full Test Binary Size

| Section | Size |
|---------|-----:|
| .text (flash) | 136,862 |
| .rodata (flash) | 60,044 |
| DRAM (.data + .bss) | 55,718 |
| **Total image** | **249,044 bytes** |

The 249KB includes ESP-IDF baseline (~180KB). secp256k1 incremental cost = **~69KB flash**.

## Configuration

Using blossom-server's secp256k1 component (C3-tuned):
- `ENABLE_MODULE_SCHNORRSIG=1`
- `ENABLE_MODULE_EXTRAKEYS=1`
- `ECMULT_GEN_PREC_BITS=4`
- `ECMULT_WINDOW_SIZE=4` (reduced from tollgate's 8 for C3 RAM savings)

## Budget Analysis (ESP32-C3, 4MB flash, 400KB RAM)

| Component | Flash | RAM |
|-----------|------:|----:|
| Tracker firmware | 227 KB | ~30 KB |
| Tollgate (extracted) | 309 KB | 49.5 KB |
| secp256k1 (Schnorr+ECDSA) | **69 KB** | **~2 KB** (heap-alloc context) |
| MeshCore | 84 KB | 6.5 KB |
| Bootloader + partitions | ~50 KB | — |
| **Total** | **~740 KB** | **~88 KB** |
| **Available** | **2,048 KB** (factory) | **~321 KB** |
| **Remaining** | **~1,300 KB (64%)** | **~233 KB (73%)** |

## Recommendation for ADR-026

**FULL SCHNORR VERIFICATION ON THE BALLOON.**

69KB flash + ~2KB heap is negligible against 1.3MB free. Zero static DRAM.
The balloon can verify BIP-340 Schnorr signatures natively without deferring
to ground stations. This simplifies the trust model:

- No "unsigned events accepted" compromise
- No dependency on ground station availability for signature verification
- Balloon acts as a proper Nostr relay (verify before store/forward)

The only cost is ~2KB heap per secp256k1_context (created on demand, destroyed
after batch verification). With 321KB DRAM and ~88KB used, there's 233KB headroom.

## Methodology

1. Built minimal ESP-IDF project targeting esp32c3
2. Linked secp256k1 component via EXTRA_COMPONENT_DIRS (blossom-server's component)
3. Called ecdsa_verify + schnorrsig_verify with known-valid pubkey (generator G)
4. Used volatile sink to prevent dead-code elimination
5. Extracted per-archive sizes via `esp_idf_size --archives secp_test.map`

Reproducible: `cd firmware/tests/secp_test && idf.py build && idf.py size`
