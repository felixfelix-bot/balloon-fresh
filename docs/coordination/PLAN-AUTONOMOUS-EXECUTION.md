# Balloon Project — Autonomous Execution Plan v2 (Corrected)
## Post-Consultant-Review — Verified Against Actual Codebase

**Created:** 2026-08-05
**Revised:** 2026-08-05 (consultant corrections applied)
**Constraint:** Everything executable WITHOUT Felix action. All host-side build/test/integration.
**Repo:** ~/repos/balloon-fresh/ (master branch)

### Changes from v1 (per consultant review):
- **DELETED** Task 1.1 (mesh_adapter CMakeLists — already exists)
- **DELETED** Task 2.1 (nostr_event_deserialize — already implemented + tested)
- **DELETED** Task 2.3 (bloom filter fix — code is correct, "fix" would introduce bug)
- **DELETED** Task 3.2 (blossom datagram — 11KB component already exists)
- **RESCOPED** Task 4.3 (FIPS crate — wrong repo, wrong diagnosis, fix is rustup update)
- **ADDED** Task 1.0 (baseline build verification with CONFIG_ENABLE_MESH=y)
- **REFRAMED** Task 1.2 (real blocker is Kconfig flag, not CMakeLists)
- **VERIFIED** Task 3.3 (nostr_store may already be flash-backed — verify first)
- **CORRECTED** Task 1.3 partition numbers

---

## PHASE 1: BASELINE (30 min)
### Task 1.0: Baseline build verification with mesh enabled
- **Action:** Set CONFIG_ENABLE_MESH=y in tracker/firmware/sdkconfig. Run idf.py build. Capture binary size, link errors, DRAM usage.
- **Files:** tracker/firmware/sdkconfig
- **Done when:** Build succeeds OR fails with documented errors. Record baseline: binary size, DRAM, component list.
- **Estimate:** 30 min (first build may be >300s)

### Task 1.1: Blossom partition expansion
- **Current state:** factory=1MB (0x100000), blossom data=1.5MB (0x180000)
- **Action:** Expand factory to 2MB. Verify total ≤ 4MB.
- **Files:** firmware/blossom-server/partitions.csv
- **Done when:** Build succeeds with expanded partition
- **Estimate:** 15 min

---

## PHASE 2: KEY MEASUREMENT (45 min — HIGHEST PRIORITY)
### Task 2.1: Measure secp256k1 flash footprint on ESP32-C3
- **Why:** Gates ADR-026 (Schnorr validation strategy). Single most important autonomous task.
- **Action:** Create minimal ESP-IDF project linking libsecp256k1. Call secp256k1_ecdsa_verify(). Build. Read idf.py size. Report flash .text + .rodata + DRAM.
- **Files:** firmware/tests/secp_test/ (new)
- **Done when:** idf.py size prints secp256k1 sizes. ADR-026 drafted.
- **Estimate:** 45 min (build >300s — background)
- **Parallel with:** Everything (independent)

---

## PHASE 3: MESH TRANSPORT WIRING (2 hours)
### Task 3.1: Wire ehash_radio_stub → LR2021 transport
- **Problem:** PoW relay radio is stubbed (ehash_radio_stub.c, 119 lines).
- **Action:** Create ehash_radio_lr2021.c implementing same interface but calling lr2021_transport_send/recv. Keep stub for unit tests.
- **Files:** mesh-stack/ehash-relay/ehash_radio_lr2021.c (new)
- **Done when:** Compiles against lr2021_transport; 8 existing unit tests still pass with stub
- **Estimate:** 1 hour
- **Depends on:** Task 1.0 (need build baseline)

### Task 3.2: Verify nostr_store persistence on C3
- **Problem:** Plan v1 claimed nostr_store is RAM-only (606KB). Consultant found it's actually flash-backed (~10KB RAM, POSIX file I/O).
- **Action:** Read nostr_store.c thoroughly. Run existing tests. Document what it does and doesn't do. Identify gaps vs wisp-esp32 storage_engine. If gaps exist, add features in-place — do NOT create new component.
- **Files:** tracker/firmware/components/nostr_store/ (read + possibly patch)
- **Done when:** Written assessment of nostr_store capabilities + gaps. If flash-backed persistence works, mark Task 3.3 from v1 as DONE.
- **Estimate:** 45 min

---

## PHASE 4: TEST COVERAGE (2.5 hours)
### Task 4.1: Tollgate payment protocol unit tests
- **Action:** Write tests for PAY/ACK/NACK/STATUS/REVOKE encode/decode. Edge cases: malformed tokens, expired proofs, double-spend.
- **Files:** mesh-stack/tollgate/test/test_payment_protocol.c (new)
- **Done when:** ≥15 test cases pass
- **Estimate:** 1 hour

### Task 4.2: 3-hop relay simulation (PoW)
- **Action:** Chain existing test harnesses: ground stratum server → balloon1 relay → balloon2 relay → upstream. Use mock radio links. Verify template downlink, nonce uplink, credit accrual, TTL expiry.
- **Simplification (per consultant):** Use existing test harnesses, don't build new simulation framework.
- **Files:** mesh-stack/ehash-bridge/test/test_3hop_relay.py (new)
- **Done when:** 100 templates, 1000 nonces, 0 loss, credit balances correct
- **Estimate:** 1 hour
- **Depends on:** Task 3.1

### Task 4.3: Fix FIPS Rust toolchain (RESCOPED)
- **Problem:** v1 said "20 SPI API errors in ~/worktrees/balloon-fips/". WRONG.
- **Actual:** FIPS code at ~/repos/microfips-upstream/. Error = Rust toolchain version mismatch (rustc 1.93.1 vs required 1.94.0 for embassy-stm32f469i-disco).
- **Action:** `rustup update stable` or pin embassy version. Run `cargo test --no-run`. Verify compilation.
- **Files:** ~/repos/microfips-upstream/rust-toolchain.toml (if exists)
- **Done when:** cargo test compiles (0 errors). Run tests if they pass.
- **Estimate:** 15 min (was 1 hour — wrong diagnosis)

---

## PHASE 5: CLEANUP (45 min)
### Task 5.1: Update 4 missing assessment status files
- **Action:** Generate assessments for nostr, pow, range-tests, speed-tests from git logs + status files. Update COORDINATOR-TRACKING.md.
- **Done when:** 10/10 tracks have assessments
- **Estimate:** 30 min

### Task 5.2: ADR-026 from secp256k1 measurement
- **Action:** Write ADR-026: "Schnorr Validation Strategy on ESP32-C3" with data from Task 2.1.
- **Done when:** ADR committed
- **Depends on:** Task 2.1

### Task 5.3: Clean uncommitted state in balloon-fresh
- **Action:** Review 6 modified + 7 untracked files. Commit relevant, discard cruft.
- **Done when:** git status clean
- **Estimate:** 15 min

---

## EXECUTION ORDER

```
Task 1.0 (baseline build) ──┬── Task 3.1 (ehash radio) ──── Task 4.2 (3-hop sim)
                             │
Task 2.1 (secp measure) ────┼── Task 5.2 (ADR-026)
                             │
Task 1.1 (blossom part)      │
                             │
Task 3.2 (nostr verify)      │
                             │
Task 4.1 (tollgate tests)    │
                             │
Task 4.3 (fips toolchain)    │
                             │
Task 5.1 (assessments) ── Task 5.3 (git clean)
```

**Parallelism:** Tasks 1.0, 2.1, 4.1, 4.3, 5.1 are all independent — can run concurrently.

**Total:** ~6-7 hours worker time → ~2.5 hours wall time with 3 concurrent workers.

## DEFINITION OF DONE
- [ ] Baseline build with CONFIG_ENABLE_MESH=y verified (pass or documented failure)
- [ ] secp256k1 flash size measured, ADR-026 written
- [ ] ehash relay uses lr2021_transport
- [ ] nostr_store persistence capability documented
- [ ] Tollgate payment tests (≥15 cases) pass
- [ ] 3-hop relay simulation passes
- [ ] FIPS Rust toolchain fixed, cargo test compiles
- [ ] 10/10 track assessments submitted
- [ ] git status clean, all work committed + pushed
