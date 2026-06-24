# ADR-016: FIPS Implementation — Keep C++ microfips

**Status:** Accepted  
**Date:** 2026-06-24  

## Context

The mesh networking stack requires encrypted sessions (Noise XK protocol) for balloon-to-balloon and balloon-to-ground communication. Two FIPS (Federated Identity and Privacy Session) implementations were evaluated:

1. **Main FIPS** (`github.com/jmcorgan/fips`) — Rust implementation, v0.4.0
2. **microfips** (`github.com/Amperstrand/microfips`) — C++ implementation using mbedtls + micro_ecc

The tracker firmware is written in C++ using ESP-IDF v5.4.1. The existing protocol stack (pipeline, erasure coding, fragmentation, TDMA, nostr store, mesh adapter) is all C++.

## Decision

**Keep C++ microfips.** Do not adopt the Rust-based main FIPS.

## Rationale

- **ESP-IDF integration:** microfips uses mbedtls + micro_ecc, both of which are already available in the ESP-IDF component ecosystem. No additional build toolchain needed.
- **Rust↔ESP-IDF is too heavy:** Integrating Rust (via esp-rs/no_std) into the existing C++ ESP-IDF build would require a separate compilation pipeline, FFI bridges, and a dual-language toolchain. This adds significant complexity for a 400KB RAM device.
- **Consistency:** The entire firmware stack is C++. Adding a Rust dependency creates a language boundary that complicates debugging, memory management, and build system maintenance.
- **Memory constraints:** ESP32-C3 has 400KB RAM. The Rust std/no_std overhead plus FFI marshalling is non-trivial. C++ microfips is designed for constrained devices.
- **Working baseline:** microfips already integrates with our existing C++ pipeline component and uses the same crypto primitives (ChaCha20-Poly1305, secp256k1 ECDH) as the Rust version.

## Consequences

- We maintain the C++ microfips integration ourselves.
- If the Rust FIPS ecosystem matures with native ESP-IDF support (e.g., esp-rs reaches production stability), this decision can be revisited.
- The mesh stack remains single-language (C++), simplifying CI, debugging, and memory profiling.

## Related

- [ADR-012: Mesh Networking Strategy](012-mesh-networking-strategy.md) — strategic architecture decision
- [ADR-013: Cluster-Aware StratoRelay](013-cluster-aware-stratorelay.md) — balloon relay design
