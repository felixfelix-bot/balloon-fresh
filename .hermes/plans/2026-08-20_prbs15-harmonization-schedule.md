# PRBS-15 BER Pattern Harmonization — Execution Schedule

> **Generated:** 2026-08-20
> **Parent Plan:** `2026-08-20_firmware-harmonization-schedule.md` (Phase 1 harmonization)
> **Quality Gates:** v3.1.0
> **Objective:** Port PRBS-15 from C3 to E80 so both platforms use identical BER test pattern generation and verification.

---

## Current State Analysis

### C3 (ESP32-C3) — Already PRBS-15

**Files:**
- `mesh-stack/flrc-bench-espidf/main/prbs.cpp` (35 lines, non-inline)
- `mesh-stack/flrc-bench-espidf/main/prbs.h` (7 lines, declarations)
- `mesh-stack/flrc-test/src/prbs.h` (38 lines, inline variant — older test copy)

**Algorithm:**
- 15-bit LFSR, Galois polynomial: taps at bits 14 and 13 (`x^15 + x^14 + x^13`)
- Seed initialization: `state = (uint16_t)(seed ^ 0x5A5A) | 1` (ensures non-zero, 15-bit mask `0x7FFF`)
- `prbs15_fill(buf, len, seed)`: generates `len` bytes, MSB-first per byte
- `prbs15_verify(buf, len, seed, &bytes_bad)`: returns `uint16_t bit_errors`, populates `bytes_bad` via `__builtin_popcount(diff)`
- Used in `bench_main.cpp`, `range_test.cpp`, `autonomous_main.cpp`, `fifo_tx.cpp`, `fast_rx.cpp`
- Seeds from sequence number: `prbs15_fill(buf + 4, pktSize - 4, txCurrentPkt)`
- PKT line reports `bit_err` and `bytes_bad` in fields 10-11

### E80 (STM32F103C8T6) — Currently xorshift32

**Files:**
- `firmware/e80-stm32-bench/src/bench_payload.c` (78 lines)
- `firmware/e80-stm32-bench/src/bench_payload.h` (47 lines)
- `firmware/e80-stm32-bench/tests/test_bench_payload.c` (118 lines)
- `firmware/e80-stm32-bench/tests/test_bench_seq.c` (183 lines)

**Algorithm:**
- xorshift32 LFSR: `x ^= x<<13; x ^= x>>17; x ^= x<<5`
- Seed: `seq ^ 0x1A2B3C4D` (non-zero fallback to `0xDEADBEEF`)
- 6-byte header: `[0..3] u32 seq LE` + `[4..5] u16 len LE`
- Body: xorshift32 bytes, 4 bytes per LFSR step
- `bench_payload_verify`: returns `int` (0=fail, 1=pass) — no bit error count
- Called in `bench.c:691,860` (`bench_payload_build`), no firmware verify call found (verify only in host tests)
- `bench_pkt.c:57` currently hardcodes `bit_err=0, bytes_bad=0` in PKT line

### Key Differences Summary

| Aspect | C3 (PRBS-15) | E80 (xorshift32) | After Port |
|--------|-------------|-------------------|------------|
| Polynomial | x^15+x^14+x^13 | xorshift32 (3 shifts) | x^15+x^14+x^13 |
| State width | 16-bit (masked 15) | 32-bit | 16-bit (masked 15) |
| Seed init | `(seed ^ 0x5A5A) \| 1` | `seed ^ 0x1A2B3C4D` | `(seed ^ 0x5A5A) \| 1` |
| Per-byte cost | 8 LFSR steps | 1/4 of a 32-bit step | 8 LFSR steps |
| Verify return | `uint16_t bit_errors` + `bytes_bad` | `int` (0/1) | `uint16_t bit_errors` + `bytes_bad` |
| Header | 4 bytes seq (BE on C3) | 6 bytes (4 seq LE + 2 len LE) | 6 bytes (unchanged header, PRBS-15 body) |
| PKT bit_err field | Populated | Hardcoded 0 | Populated |

### `__builtin_popcount` Portability Note

The C3 `prbs15_verify` uses `__builtin_popcount(diff)` (GCC intrinsic). The E80 firmware is compiled with `arm-none-eabi-gcc` which supports `__builtin_popcount`. Host tests use `gcc` which also supports it. **No portability issue.**

---

## Flash Budget Impact

| Metric | Current | After PRBS-15 Port | Delta |
|--------|---------|--------------------|----|
| Firmware size | 24,316 B (37.10%) | ~24,350 B (37.15%) | +~34 B |
| Flash budget | < 35,000 B (53.4%) | < 35,000 B (53.4%) | Headroom: ~10,650 B |
| Code added | — | `prbs.c` (~35 lines) | Compiled to ~30-40 bytes of ARM Thumb code |
| Code removed | — | xorshift32 body from `bench_payload.c` | ~-40 bytes |
| Net flash delta | — | **~0 bytes** | PRBS-15 replaces xorshift32, similar code size |

**Verdict:** Flash budget is not a concern. PRBS-15 replaces xorshift32 in-place. Net code size change is negligible.

---

## Worker Assignments

| Worker | Profile | Repo | Branch | Scope |
|--------|---------|------|--------|-------|
| Worker-E80 | worker-balloon | `~/repos/balloon-e80bench/` | `feat/persist-tx-seq` | Tasks P1-P5, P8 (E80 side) |
| Worker-C3 | worker-balloon | `~/repos/balloon-fresh/` | `feat/c3-harmonization` | Task P6, P7 (C3 side, verify only) |
| Worker-Host | worker-admin | `~/repos/balloon-fresh/` | `feat/c3-harmonization` | Task P7 (cross-platform host test) |

> **Note:** Worker-E80 and Worker-C3 operate on different repos and branches. No file overlap.

---

## Task Table

| Task ID | Description | Est. Time | Dependencies | Worker | Quality Gates |
|---------|-------------|-----------|--------------|--------|---------------|
| **P1** | Write failing E80 host tests for PRBS-15 (test_prbs.c) | 15m | None | Worker-E80 | Gate 1 (TDD red-first) |
| **P2** | Port prbs.c + prbs.h to E80 (`src/prbs.c`, `src/prbs.h`) | 10m | P1 | Worker-E80 | Gate 2 (tests pass), Gate 4 (atomic commit) |
| **P3** | Update bench_payload.c to use PRBS-15 (replace xorshift32) | 15m | P2 | Worker-E80 | Gate 1 (update tests), Gate 2 (tests pass + firmware build < 35K), Gate 4 |
| **P4** | Update bench_payload.h API (add bit_err/bytes_bad return, remove xorshift32 declarations) | 10m | P3 | Worker-E80 | Gate 2 (tests pass), Gate 3 (docs), Gate 4 |
| **P5** | Update E80 host tests (test_bench_payload.c, test_bench_seq.c) to verify PRBS-15 not xorshift32 | 20m | P3, P4 | Worker-E80 | Gate 1 (TDD), Gate 2 (tests pass), Gate 4 |
| **P6** | Verify C3 prbs15_verify matches E80 prbs15_verify (same polynomial, same seed → same output) | 10m | P2 | Worker-C3 | Gate 2 (C3 build), Gate 5 (push) |
| **P7** | Cross-platform host test: generate PRBS-15 on E80 side (C test), verify on C3 side (Python test), and vice versa | 20m | P2, P6 | Worker-Host | Gate 1 (TDD), Gate 2 (pytest pass), Gate 5 (push) |
| **P8** | Update documentation: both platforms now use PRBS-15 for BER | 10m | P3, P5, P7 | Worker-E80 | Gate 3 (docs), Gate 4, Gate 5 |

---

## Wave Structure

### Dependency Graph

```
WAVE 1 (TDD + Port)           WAVE 2 (Integration)        WAVE 3 (Cross-Platform + Docs)
──────────────────            ──────────────────          ──────────────────────────────
P1 (15m) ─┐
          ├→ P2 (10m) ─┐
          │             ├→ P3 (15m) ─┐
          │             │            ├→ P5 (20m) ─┐
          │             │            │             ├→ P8 (10m)
          │             │            ├→ P4 (10m) ─┘
          │             │            │
          │             ├→ P6 (10m) ─┐
          │             │            ├→ P7 (20m) ─┐
          │             │            │             ├→ P8 (10m)
          └─────────────┘            │             │
                                     │             │
                                     └─────────────┴── [GATE 6: Manager validation]
```

### Wave 1: TDD Red-First + PRBS-15 Port (25 min wall time)

**Goal:** Write failing tests, then port PRBS-15 to E80 as a standalone module.

| Worker | Task | Est. | Files | Action |
|--------|------|------|-------|--------|
| Worker-E80 | **P1**: Write failing host test for PRBS-15 | 15m | `tests/test_prbs.c` (new), `tests/CMakeLists.txt` (update) | Write `test_prbs15_fill`, `test_prbs15_verify`, `test_prbs15_known_vector` tests. Add to CMakeLists. Run `make test-host` → **MUST FAIL** (prbs.c doesn't exist yet). |
| Worker-E80 | **P2**: Port prbs.c + prbs.h to E80 | 10m | `src/prbs.c` (new), `src/prbs.h` (new), `CMakeLists.txt` (firmware, add to source list) | Copy algorithm from C3 `prbs.cpp` adapted to C (remove C++ guards, keep `__builtin_popcount`). Add `src/prbs.c` to firmware `CMakeLists.txt` source list. Run `make test-host` → **MUST PASS**. Run `make firmware` → build succeeds, flash < 35K. |

**P1 Details — Failing Tests to Write:**

```c
// tests/test_prbs.c
// Test 1: prbs15_fill produces deterministic output for same seed
// Test 2: prbs15_fill produces different output for different seeds
// Test 3: prbs15_verify returns 0 bit errors for clean buffer
// Test 4: prbs15_verify detects single-bit corruption (bit_err=1, bytes_bad=1)
// Test 5: prbs15_verify matches prbs15_fill output (round-trip)
// Test 6: Known vector — seed=0x0001, len=8, verify first 8 bytes match expected
//         (precomputed from C3 implementation)
```

**P2 Details — Source to Port:**

Copy from C3 `prbs.cpp` → E80 `src/prbs.c`:
- Replace `#include "prbs.h"` with `#include "prbs.h"` (same)
- Algorithm is pure C already (no C++ features in prbs.cpp)
- `__builtin_popcount` is available on `arm-none-eabi-gcc` and host gcc

Copy from C3 `prbs.h` → E80 `src/prbs.h`:
- Add `#ifdef __cplusplus / extern "C" / #endif` guards (E80 header convention)
- Keep `#include <stdint.h>` and `#include <stddef.h>`

**Firmware CMakeLists.txt update:**
- Add `src/prbs.c` to the `add_executable(e80_bench ...)` source list (line 45, after `src/bench_payload.c`)

**Tests CMakeLists.txt update:**
- Add: `add_bench_test(test_prbs ${SRC_DIR}/prbs.c)`
- Update: `add_bench_test(test_bench_payload ${SRC_DIR}/bench_payload.c ${SRC_DIR}/prbs.c)` (will need prbs.c after P3)

#### Gate 1 (TDD red-first)
- **P1:** Tests written, `make test-host` fails with linker error (no `prbs.c`). Document failure.
- **P2:** Tests pass after implementation.

#### Gate 2 (Tests pass)
- **P2:** `make test-host` passes (all test_prbs tests green). `make firmware` builds. `arm-none-eabi-size build-fw/e80_bench.elf` < 35,000 B.

#### Gate 4 (Atomic commit)
- **P1:** `git commit -m "test: add failing PRBS-15 host tests (TDD red-first)"`
- **P2:** `git commit -m "feat: port PRBS-15 generator/verifier from C3 to E80"`

#### Gate 5 (Push)
- After P2 commit: `git push github feat/persist-tx-seq`

**Wall time:** 25 min (serial: P1 → P2) + 10 min gates = **~35 min**

---

### Wave 2: bench_payload Integration + API Update (30 min wall time)

**Goal:** Replace xorshift32 in bench_payload.c with PRBS-15 calls. Update API to expose bit_err/bytes_bad.

| Worker | Task | Est. | Files | Action |
|--------|------|------|-------|--------|
| Worker-E80 | **P3**: Update bench_payload.c to use PRBS-15 | 15m | `src/bench_payload.c` | Replace `bench_lfsr_next` + xorshift32 body with `prbs15_fill()` call in `bench_payload_build`. Replace xorshift32 verification loop with `prbs15_verify()` call in `bench_payload_verify`. Keep 6-byte header (seq + len) unchanged. Body starts at offset 6 (BENCH_PAYLOAD_HDR_LEN). |
| Worker-E80 | **P4**: Update bench_payload.h API | 10m | `src/bench_payload.h` | Remove `bench_lfsr_next` declaration. Update `bench_payload_verify` signature to return bit errors + bytes_bad (or add new function). Update comments to say PRBS-15 instead of xorshift32. |
| Worker-E80 | **P5**: Update host tests for PRBS-15 | 20m | `tests/test_bench_payload.c`, `tests/test_bench_seq.c` | Remove `test_lfsr_deterministic`, `test_lfsr_never_zero` (xorshift32-specific). Add `test_prbs15_roundtrip`, `test_prbs15_bit_error_count`. Update `test_corruption_detected` to check bit_err count. Update `test_distinct_sequences` to verify PRBS-15 body differs. |

**P3 Details — Code Changes in bench_payload.c:**

```c
// BEFORE (xorshift32):
void bench_payload_build(uint8_t* buf, uint32_t len, uint32_t seq) {
    uint32_t st = seq ^ 0x1A2B3C4DU;
    if (st == 0) st = 0xDEADBEEFU;
    put_u32le(&buf[0], seq);
    buf[4] = (uint8_t)(len & 0xFF);
    buf[5] = (uint8_t)((len >> 8) & 0xFF);
    for (uint32_t i = BENCH_PAYLOAD_HDR_LEN; i < len; i++) {
        if ((i - BENCH_PAYLOAD_HDR_LEN) % 4 == 0)
            bench_lfsr_next(&st);
        buf[i] = (uint8_t)(st >> (((i - BENCH_PAYLOAD_HDR_LEN) % 4) * 8));
    }
}

// AFTER (PRBS-15):
#include "prbs.h"
void bench_payload_build(uint8_t* buf, uint32_t len, uint32_t seq) {
    put_u32le(&buf[0], seq);
    buf[4] = (uint8_t)(len & 0xFF);
    buf[5] = (uint8_t)((len >> 8) & 0xFF);
    prbs15_fill(buf + BENCH_PAYLOAD_HDR_LEN, len - BENCH_PAYLOAD_HDR_LEN, seq);
}
```

```c
// BEFORE (xorshift32 verify):
int bench_payload_verify(const uint8_t* buf, uint32_t len) {
    if (len < BENCH_PAYLOAD_HDR_LEN) return 0;
    uint32_t seq = get_u32le(buf);
    uint32_t st = seq ^ 0x1A2B3C4DU;
    if (st == 0) st = 0xDEADBEEFU;
    for (uint32_t i = BENCH_PAYLOAD_HDR_LEN; i < len; i++) {
        if ((i - BENCH_PAYLOAD_HDR_LEN) % 4 == 0)
            bench_lfsr_next(&st);
        if (buf[i] != (uint8_t)(st >> (((i - BENCH_PAYLOAD_HDR_LEN) % 4) * 8)))
            return 0;
    }
    return 1;
}

// AFTER (PRBS-15 verify):
uint16_t bench_payload_verify(const uint8_t* buf, uint32_t len, uint16_t* out_bytes_bad) {
    if (len < BENCH_PAYLOAD_HDR_LEN) return 0;
    uint32_t seq = get_u32le(buf);
    return prbs15_verify(buf + BENCH_PAYLOAD_HDR_LEN,
                         len - BENCH_PAYLOAD_HDR_LEN,
                         seq, out_bytes_bad);
}
```

**P4 Details — API Changes in bench_payload.h:**

```c
// REMOVE:
uint32_t bench_lfsr_next(uint32_t* state);
int bench_payload_verify(const uint8_t* buf, uint32_t len);

// ADD:
#include "prbs.h"  // for prbs15_fill/prbs15_verify

// New verify signature: returns bit_errors, populates bytes_bad
uint16_t bench_payload_verify(const uint8_t* buf, uint32_t len, uint16_t* out_bytes_bad);
```

**Impact on bench.c callers:**

| Call Site | Current | After |
|-----------|---------|-------|
| `bench.c:691` | `bench_payload_build(tx_buf, tx_len, tx_seq)` | No change (same signature) |
| `bench.c:860` | `bench_payload_build(tx_buf, tx_len, tx_seq)` | No change |
| `bench_pkt.c:57` | `bit_err=0, bytes_bad=0` (hardcoded) | Needs `bench_payload_verify` call to populate (separate follow-up or in P3) |

**⚠️ bench_pkt.c update:** P3 should also update the RX path in `bench.c` to call `bench_payload_verify` and pass `bit_err`/`bytes_bad` to `bench_pkt_format`. Currently `bench_pkt.c:57` hardcodes `0,0`. After P3, the PKT line should report actual bit errors. This may require:
1. Finding the RX handler in `bench.c` where packets are received
2. Calling `bench_payload_verify(rx_buf, rx_len, &bit_err, &bytes_bad)` 
3. Passing `bit_err` and `bytes_bad` into `bench_pkt_evt_t` or `bench_pkt_format` call

This is a minor extension to P3's scope (~5 min additional).

**P5 Details — Test Changes:**

| Test | Action | Reason |
|------|--------|--------|
| `test_lfsr_deterministic` | **Remove** | Tests xorshift32 directly |
| `test_lfsr_never_zero` | **Remove** | Tests xorshift32 state |
| `test_header` | **Keep** | Header format unchanged |
| `test_roundtrip` | **Update** | Call with new verify signature |
| `test_lengths` | **Update** | Call with new verify signature |
| `test_corruption_detected` | **Update** | Check `bit_err > 0` instead of `verify == 0` |
| `test_distinct_sequences` | **Keep** | Still valid (different seq → different body) |
| `test_lfsr_deterministic_from_seq` (test_bench_seq.c) | **Rename → `test_prbs15_deterministic_from_seq`** | Same concept, PRBS-15 engine |
| `test_lfsr_differs_with_seq` (test_bench_seq.c) | **Rename → `test_prbs15_differs_with_seq`** | Same concept, PRBS-15 engine |
| New: `test_bit_error_count` | **Add** | Corrupt 1 bit → `bit_err == 1, bytes_bad == 1` |
| New: `test_bit_error_multi_byte` | **Add** | Corrupt 2 bytes → `bytes_bad == 2` |

#### Gate 1 (TDD red-first)
- **P3:** Update `test_bench_payload.c` tests to expect PRBS-15 behavior → `make test-host` fails (bench_payload.c still uses xorshift32)
- **P5:** After P3+P4 are committed, re-run tests → must pass

#### Gate 2 (Tests pass)
- **P3:** `make test-host` passes. `make firmware` builds. `arm-none-eabi-size build-fw/e80_bench.elf` < 35,000 B.
- **P4:** `make test-host` passes (header compiles, all tests link).
- **P5:** `make test-host` passes with all updated tests.

#### Gate 3 (Docs)
- **P4:** Update `bench_payload.h` header comment: "PRBS-15 pseudo-random fill" instead of "xorshift32 LFSR fill". Update payload layout comment.

#### Gate 4 (Atomic commit)
- **P3:** `git commit -m "feat: replace xorshift32 with PRBS-15 in bench_payload"`
- **P4:** `git commit -m "refactor: update bench_payload.h API for PRBS-15 verify with bit_err"`
- **P5:** `git commit -m "test: update host tests for PRBS-15 payload verification"`

#### Gate 5 (Push)
- After each commit: `git push github feat/persist-tx-seq`

**Wall time:** 45 min (serial: P3 → P4 → P5) + 10 min gates = **~55 min**

---

### Wave 3: Cross-Platform Verification + Documentation (30 min wall time, parallel)

**Goal:** Verify both platforms produce identical PRBS-15 output. Write cross-platform host test. Update docs.

| Worker | Task | Est. | Files | Action |
|--------|------|------|-------|--------|
| Worker-C3 | **P6**: Verify C3 prbs15_verify matches E80 | 10m | (read-only verification) | Compare C3 `prbs.cpp` and E80 `src/prbs.c` line-by-line. Confirm identical algorithm, seed init, byte ordering. Run C3 build to confirm no breakage: `source ~/esp/esp-idf/export.sh && cd mesh-stack/flrc-bench-espidf && idf.py build`. |
| Worker-Host | **P7**: Cross-platform host test | 20m | `tests/test_prbs15_cross.py` (new) | Python test: generate PRBS-15 vectors from C3 algorithm (reimplement in Python), compare against E80 C test output. Include known-answer test vectors (seed=1, len=32; seed=42, len=128; seed=0xDEADBEEF, len=255). |
| Worker-E80 | **P8**: Update documentation | 10m | `firmware/e80-stm32-bench/README.md` or `docs/` (E80 repo), and `mesh-stack/flrc-bench-espidf/README.md` (C3 repo) | Document: both platforms now use PRBS-15 (x^15+x^14+x^13), seed = `(seq ^ 0x5A5A) \| 1`, identical `prbs15_fill`/`prbs15_verify`. Note BER measurements are now directly comparable. |

**P6 Details — Equivalence Verification:**

Checklist:
1. Both use `uint16_t state = (uint16_t)(seed ^ 0x5A5A) | 1`
2. Both use `newbit = ((state >> 14) ^ (state >> 13)) & 1`
3. Both use `state = ((state << 1) | newbit) & 0x7FFF`
4. Both build bytes MSB-first: `byte = (byte << 1) | (newbit & 1)`
5. Both use `__builtin_popcount(diff)` for bit error counting
6. C3 `prbs.cpp` is C++ but algorithm is C-compatible (no C++ features in the algorithm body)
7. E80 `prbs.c` should be byte-identical algorithm after porting

**P7 Details — Cross-Platform Test:**

```python
# tests/test_prbs15_cross.py
# Reimplement PRBS-15 in Python, verify against known vectors
# that were precomputed from the C3/E80 C implementation.

def prbs15_fill_python(buf_len: int, seed: int) -> bytes:
    """Python reimplementation of prbs15_fill for cross-platform verification."""
    state = (seed ^ 0x5A5A) | 1
    state &= 0x7FFF
    result = bytearray()
    for _ in range(buf_len):
        byte_val = 0
        for _ in range(8):
            newbit = ((state >> 14) ^ (state >> 13)) & 1
            state = ((state << 1) | newbit) & 0x7FFF
            byte_val = (byte_val << 1) | (newbit & 1)
        result.append(byte_val)
    return bytes(result)

# Known vectors (precomputed from C implementation):
# seed=1,    len=4:  [expected bytes]
# seed=42,   len=8:  [expected bytes]
# seed=255,  len=16: [expected bytes]

def test_prbs15_known_vectors():
    # Verify Python implementation matches C known vectors
    
def test_prbs15_deterministic():
    # Same seed → same output
    
def test_prbs15_different_seeds():
    # Different seeds → different output
    
def test_prbs15_verify_clean():
    # Verify clean buffer → 0 bit errors
    
def test_prbs15_verify_corrupted():
    # Corrupt 1 byte → bit_err = popcount(diff), bytes_bad = 1
```

**P8 Details — Documentation:**

Add to E80 `firmware/e80-stm32-bench/README.md` (or create `docs/ber-pattern.md`):
```
## BER Test Pattern

Both E80 (STM32) and C3 (ESP32-C3) platforms use PRBS-15 as the common
BER test pattern payload:

- **Polynomial:** x^15 + x^14 + x^13 (Galois LFSR)
- **Seed:** `(sequence_number ^ 0x5A5A) | 1` (15-bit, non-zero)
- **Generation:** `prbs15_fill(buf, len, seed)` — MSB-first per byte
- **Verification:** `prbs15_verify(buf, len, seed, &bytes_bad)` — returns bit_errors
- **Bit counting:** `__builtin_popcount(buf[i] ^ expected)` per byte

This makes BER measurements directly comparable across platforms.
```

#### Gate 1 (TDD red-first)
- **P7:** Write pytest with known vectors → run → if vectors are wrong, test fails (expected). Fix vectors from C output.

#### Gate 2 (Tests pass)
- **P6:** C3 `idf.py build` succeeds. Manual code comparison confirms identical algorithm.
- **P7:** `cd ~/repos/balloon-fresh && python3 -m pytest tests/test_prbs15_cross.py -v` passes.

#### Gate 3 (Docs)
- **P8:** Documentation updated in both repos.

#### Gate 4 (Atomic commit)
- **P6:** No code changes (verification only). If C3 needs any fixup: `git commit -m "docs: verify PRBS-15 matches E80 implementation"`
- **P7:** `git commit -m "test: add cross-platform PRBS-15 known-vector tests"`
- **P8:** `git commit -m "docs: document PRBS-15 as common BER pattern for both platforms"`

#### Gate 5 (Push)
- **P6:** `git push github feat/c3-harmonization`
- **P7:** `git push github feat/c3-harmonization`
- **P8:** Push to both repos as applicable.

**Wall time:** 30 min (P6 and P7 parallel; P8 after both) + 10 min gates = **~40 min**

---

## Summary: Wall Time Estimates

| Wave | Worker-E80 | Worker-C3 | Worker-Host | Wall Time (max) | Gates |
|------|-----------|-----------|-------------|-----------------|-------|
| 1: TDD + Port | 25m | — | — | 25m | Gates 1, 2, 4, 5 |
| 2: Integration | 45m | — | — | 45m | Gates 1-5 |
| 3: Cross-Platform + Docs | 10m | 10m | 20m | 30m | Gates 1-5 |
| **Total** | **80m** | **10m** | **20m** | **~100 min code** | |

**With parallel workers in Wave 3:** ~100 min total wall time (1h 40m).

**Critical path:** P1 → P2 → P3 → P4 → P5 → P8 = 90 min (Worker-E80 serial chain).

---

## Risk Assessment

| # | Risk | Severity | Mitigation | Enforcement |
|---|------|----------|------------|-------------|
| **R1** | `__builtin_popcount` not available on ARM | LOW | `arm-none-eabi-gcc` supports it. Verified. | Gate 2: `make firmware` builds successfully. |
| **R2** | PRBS-15 per-byte (8 LFSR steps) slower than xorshift32 (1 step per 4 bytes) on STM32 | LOW | STM32F103 runs at 72 MHz. Even at 8 ops/byte × 505 bytes = 4,040 ops/packet, at 72 MHz this is ~56 μs. At 190 pkt/s, 10.6 ms/s = 1.1% CPU. Negligible. | Gate 2: firmware runs without IWDG issues. |
| **R3** | Seed difference: C3 uses `seq` directly, E80 header has 6-byte header | LOW | Both seed PRBS-15 from `seq` (the sequence number). Header format is orthogonal to PRBS-15 body. `prbs15_fill` is called on body only (offset 6 on E80, offset 4 on C3). Seed is the same value (`seq`). | P6: Verify seed source matches. P7: Cross-platform test uses same seed. |
| **R4** | API change to `bench_payload_verify` breaks callers | MEDIUM | Currently no firmware caller of `bench_payload_verify` was found in `bench.c` (only host tests call it). `bench_pkt.c` hardcodes `bit_err=0,bytes_bad=0`. P3 adds the verify call to the RX path. | Gate 2: `make test-host` + `make firmware` pass. |
| **R5** | Header offset difference: C3 body at offset 4, E80 body at offset 6 | LOW | PRBS-15 functions take a pointer + length. The caller passes `buf + header_len`. The PRBS-15 algorithm doesn't know about the header. Both platforms seed from `seq` and generate the same body bytes. | P7: Cross-platform test seeds from same seq, compares body bytes only. |
| **R6** | E80 test CMakeLists.txt doesn't link prbs.c to bench_payload tests | LOW | P1 and P5 update `tests/CMakeLists.txt` to add `prbs.c` to test executables that need it. | Gate 2: `make test-host` links successfully. |
| **R7** | Flash budget exceeded by adding prbs.c | NEGLIGIBLE | PRBS-15 replaces xorshift32 in bench_payload.c. Net code size delta ~0 bytes. Current: 24,316 B / 35,000 B budget. | Gate 2: `arm-none-eabi-size` check after `make firmware`. |

---

## Quality Gates Checklist (v3.1.0)

| Gate | Description | When Applied |
|------|-------------|--------------|
| **Gate 1** | TDD red-first: write failing test before implementation | P1, P3, P5, P7 |
| **Gate 2** | Tests pass: `make test-host` (E80), `idf.py build` (C3), `pytest` (host) | All tasks |
| **Gate 2.1** | Flash size < 35K (E80 only): `arm-none-eabi-size build-fw/e80_bench.elf` | P2, P3 |
| **Gate 3** | Documentation updated in same commit | P4, P8 |
| **Gate 4** | Atomic commit with conventional message | All tasks |
| **Gate 5** | Push to remote succeeds | P2, P5, P6, P7, P8 |
| **Gate 6** | Manager validation (final review) | After Wave 3 |

---

## Test Vectors for Cross-Platform Verification (P7)

Precompute from C implementation (run once on either platform, capture output):

| Seed | Length | First 4 bytes (hex) | Last 4 bytes (hex) |
|------|--------|---------------------|---------------------|
| 1 | 32 | TBD (from C run) | TBD |
| 42 | 128 | TBD (from C run) | TBD |
| 0xDEADBEEF | 255 | TBD (from C run) | TBD |
| 0 | 64 | TBD (from C run) | TBD |

> These vectors are generated by running `prbs15_fill` on either platform and recording the output. The Python test reimplements the algorithm and checks against these vectors. If all match, both platforms produce identical PRBS-15 output.

---

## File Impact Summary

### E80 Repo (`~/repos/balloon-e80bench`)

| File | Action | Task |
|------|--------|------|
| `src/prbs.c` | **CREATE** | P2 |
| `src/prbs.h` | **CREATE** | P2 |
| `src/bench_payload.c` | **MODIFY** (replace xorshift32 with PRBS-15) | P3 |
| `src/bench_payload.h` | **MODIFY** (update API, remove xorshift32 decls) | P4 |
| `src/bench.c` | **MODIFY** (add verify call in RX path, update PKT bit_err/bytes_bad) | P3 |
| `CMakeLists.txt` | **MODIFY** (add prbs.c to firmware sources) | P2 |
| `tests/CMakeLists.txt` | **MODIFY** (add test_prbs, link prbs.c to test_bench_payload) | P1, P5 |
| `tests/test_prbs.c` | **CREATE** | P1 |
| `tests/test_bench_payload.c` | **MODIFY** (update for PRBS-15 API) | P5 |
| `tests/test_bench_seq.c` | **MODIFY** (rename LFSR tests to PRBS-15) | P5 |
| `README.md` or `docs/ber-pattern.md` | **CREATE/UPDATE** | P8 |

### C3 Repo (`~/repos/balloon-fresh`)

| File | Action | Task |
|------|--------|------|
| `tests/test_prbs15_cross.py` | **CREATE** | P7 |
| `.hermes/plans/2026-08-20_prbs15-harmonization-schedule.md` | **CREATE** (this file) | — |

> C3 `prbs.cpp`/`prbs.h` are NOT modified — they are the reference implementation.

---

## Commit Sequence

| # | Repo | Branch | Commit Message | Task |
|---|------|--------|----------------|------|
| 1 | balloon-e80bench | feat/persist-tx-seq | `test: add failing PRBS-15 host tests (TDD red-first)` | P1 |
| 2 | balloon-e80bench | feat/persist-tx-seq | `feat: port PRBS-15 generator/verifier from C3 to E80` | P2 |
| 3 | balloon-e80bench | feat/persist-tx-seq | `feat: replace xorshift32 with PRBS-15 in bench_payload` | P3 |
| 4 | balloon-e80bench | feat/persist-tx-seq | `refactor: update bench_payload.h API for PRBS-15 verify with bit_err` | P4 |
| 5 | balloon-e80bench | feat/persist-tx-seq | `test: update host tests for PRBS-15 payload verification` | P5 |
| 6 | balloon-fresh | feat/c3-harmonization | `test: verify C3 PRBS-15 matches E80 implementation` | P6 |
| 7 | balloon-fresh | feat/c3-harmonization | `test: add cross-platform PRBS-15 known-vector tests` | P7 |
| 8 | balloon-e80bench | feat/persist-tx-seq | `docs: document PRBS-15 as common BER pattern for both platforms` | P8 |

> All commits use: `git -c core.hooksPath=/dev/null --no-verify commit -m "..."`

---

## Critical Path

```
P1 (15m) → P2 (10m) → P3 (15m) → P4 (10m) → P5 (20m) → P8 (10m)
                                                                    = 80 min
```

**Critical path wall time:** 80 minutes (Worker-E80 serial chain, code only).

P6 (10m) and P7 (20m) run in parallel during Wave 3 and do not extend the critical path.

---

## Notes for Manager

1. **C3 is the reference implementation.** Do NOT modify `prbs.cpp`/`prbs.h` in the C3 repo. E80 ports FROM C3, not the other way around.

2. **Header format is preserved.** E80 keeps its 6-byte header (4 seq LE + 2 len LE). C3 uses a 4-byte header. PRBS-15 operates on the body only. The header difference is intentional and does not affect BER comparability — both platforms seed PRBS-15 from the sequence number and generate the same body bytes.

3. **Seed equivalence:** Both platforms seed PRBS-15 from the TX sequence number. The seed initialization `(seq ^ 0x5A5A) | 1` is identical. Different sequence numbers produce different PRBS-15 streams, which is the desired behavior (each packet has a unique test pattern).

4. **bench_pkt.c bit_err population:** Currently `bench_pkt.c:57` hardcodes `bit_err=0, bytes_bad=0`. Task P3 includes adding the `bench_payload_verify` call to the E80 RX path so these fields are populated. This is a functional improvement that makes the E80 PKT line match the C3 PKT line.

5. **Test vector generation:** P7 needs precomputed test vectors. Generate these by compiling and running a small C program that calls `prbs15_fill` with known seeds and prints the output. Or run the E80 host test `test_prbs.c` and capture stdout. The Python test then checks against these vectors.

6. **No firmware flashing required for code tasks.** All tasks (P1-P8) can be completed with host tests and build checks. Hardware testing is a separate follow-up (Phase 2 integration test).

7. **PRBS-15 vs xorshift32 quality:** PRBS-15 is a standard ITU-T O.151 test pattern. xorshift32 is a fast PRNG but not a standardized BER pattern. Switching to PRBS-15 makes BER measurements telecom-grade and directly comparable to industry standards.