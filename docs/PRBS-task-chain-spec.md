# PRBS Enablement Task Chain Specification

**Status**: Draft  
**Created**: 2026-08-20  
**Author**: Firmware harmonization team  
**Repos**: `balloon-e80bench`, `balloon-fresh` (mesh-stack + rp2040)

---

## 1. Overview

This spec defines a kanban task chain for enabling Pseudo-Random Bit Sequence (PRBS) testing across all 3 RF characterization rigs. Two PRBS modes are targeted:

| Mode | Type | CPU Cost | Default | Use Case |
|------|------|----------|---------|----------|
| **PRBS-15** | Software LFSR (15-bit Galois) | ~5 ms/pkt | ON for range test, OFF for throughput | True BER measurement via payload XOR |
| **PRBS-9** | Hardware chip TX test mode | Zero (on-chip) | OFF (optional CONFIG command) | Raw link quality / sensitivity testing |

### 1.1 Rig Summary

| Rig | MCU | Radio | Band | Repo Path | Current PRBS-15 | Current PRBS-9 |
|-----|-----|-------|------|-----------|-----------------|----------------|
| E80 | STM32F103C8T6 | LR2021 | 868 MHz | `~/repos/balloon-e80bench/firmware/e80-stm32-bench/` | Stub (TDD red phase ready) | Driver enum exists, never called |
| C3 | ESP32-C3 | LR2021 | 2.4 GHz | `~/repos/balloon-fresh/mesh-stack/flrc-bench-espidf/` | Fully implemented | Not exposed (RadioLib) |
| RP2040 | RP2040 | LR2021 | 2.4 GHz | `~/repos/balloon-fresh/firmware/rp2040/` | None (counter pattern) | Not exposed (raw SPI) |

### 1.2 Current State of `bit_err` / `bytes_bad` in PKT Output

| Rig | CRC-failed packets | CRC-ok packets | Notes |
|-----|--------------------|----------------|-------|
| E80 | `bit_err=0, bytes_bad=0` (hardcoded) | `bit_err=0, bytes_bad=0` (hardcoded) | `prbs.c` is a stub; `bench_payload_verify()` exists but is never called on RX path |
| C3 | `bit_err=0, bytes_bad=0` (correct) | `bit_err=<real>, bytes_bad=<real>` | Fully working via `prbs15_verify()` |
| RP2040 | `bit_err=0, bytes_bad=0` (hardcoded) | `bit_err=<counter XOR>, bytes_bad=0` | Uses counter pattern `i & 0xFF`, not PRBS; `bytes_bad` never computed |

### 1.3 PRBS-15 Algorithm Reference (from C3 implementation)

The C3 `prbs.cpp` is the reference implementation. All ports must produce **byte-identical output** for the same seed.

```
Seed obfuscation:  state = (seed ^ 0x5A5A) | 1   (ensures non-zero 15-bit state)
Polynomial:        x^15 + x^14 + x^13 + 1  (taps at bits 14 and 13)
Bit packing:       MSB-first within each byte
State mask:        0x7FFF (15-bit)

prbs15_fill(buf, len, seed):   generates len bytes of PRBS-15
prbs15_verify(buf, len, seed, &bytes_bad):  returns bit_errors (uint16_t), writes bytes_bad
  - XORs received vs expected per byte
  - bit_errors = sum of __builtin_popcount(xor_diff) per byte
  - bytes_bad = count of bytes where xor_diff != 0
```

**TX payload layout (all rigs)**: Bytes 0-3 = sequence number (big-endian on C3; little-endian on E80/RP2040 — see per-task notes). Bytes 4+ (or 29+ on RP2040) = PRBS-15 fill seeded with the sequence number.

---

## 2. Task Dependency Graph

```
                    PRBS-1 (C3: enable PRBS-15 default-on for range, default-off for throughput)
                   /
PRBS-0 (spec) ────┼── PRBS-2 (E80: implement PRBS-15 LFSR — replace stub)
                  │     │
                  │     ├── PRBS-3 (E80: wire PRBS-15 into RX path + PKT formatter)
                  │     │
                  │     └── PRBS-4 (E80: add PRBS9 hardware CONFIG command)
                  │
                  ├── PRBS-5 (RP2040: port PRBS-15 fill + verify)
                  │     │
                  │     ├── PRBS-6 (RP2040: wire PRBS-15 into TX fill + RX verify)
                  │     │
                  │     └── PRBS-7 (RP2040: add PRBS-9 hardware CONFIG command)
                  │
                  └── PRBS-8 (Cross-rig: integration test — all 3 rigs PRBS-15 cross-check)
```

**Parallelism rules**:
- PRBS-1, PRBS-2, PRBS-5 can run in **parallel** (independent repos/codebases)
- PRBS-3 depends on PRBS-2 (needs real LFSR implementation)
- PRBS-4 depends on PRBS-2 (needs to share flash budget accounting)
- PRBS-6 depends on PRBS-5 (needs PRBS functions)
- PRBS-7 depends on PRBS-5 (same repo)
- PRBS-8 depends on PRBS-1, PRBS-3, PRBS-6 (all rigs must be PRBS-15 capable)

---

## 3. Task Details

---

### PRBS-1: C3 — Enable PRBS-15 Default-On for Range Test, Default-Off for Throughput

**Objective**: Ensure PRBS-15 is automatically enabled in range test mode and disabled in throughput/bench mode on the C3 rig. The implementation already exists — this task is about mode-gating and verification, not new code.

**Dependencies**: None (PRBS-15 already fully implemented in C3)

**Repo**: `~/repos/balloon-fresh/mesh-stack/flrc-bench-espidf/`

**Current state**:
- `prbs15_fill()` and `prbs15_verify()` are fully implemented in `main/prbs.cpp` / `main/prbs.h`
- `range_test.cpp` (line 144) already calls `prbs15_fill(buf + 4, w->pkt_size - 4, seqCounter)` for TX
- `range_test.cpp` (line 492) already calls `prbs15_verify(buf + 4, len - 4, seq, &bytesBad)` for RX
- `bench_main.cpp` (line 150) also uses PRBS fill/verify
- PRBS is currently **always on** in both range_test and bench_main — no mode gating exists

**Files to modify**:
- `main/range_test.cpp` — verify PRBS is called unconditionally in range test mode (already is)
- `main/bench_main.cpp` — add a runtime flag `prbs_enabled` (default false for throughput mode), gate the `prbs15_fill` and `prbs15_verify` calls behind it
- `main/bench_main.h` (or equivalent config struct) — add `bool prbs_enabled` field

**TDD test specs (RED phase first)**:
1. **test_prbs_mode_gating**: Write a host-side test that verifies:
   - Range test mode: PRBS fill is called (bit_err/bytes_bad populated for CRC-ok packets)
   - Throughput mode with `prbs_enabled=false`: TX fills with zeros or counter, RX does not call verify, bit_err=0 bytes_bad=0
   - Throughput mode with `prbs_enabled=true`: PRBS fill/verify active (opt-in)

**Implementation approach**:
1. Add `bool prbs_enabled` to the bench config struct (default `false`)
2. In `bench_main.cpp:runTx()`, wrap `prbs15_fill()` call in `if (cfg.prbs_enabled)`
3. In `bench_main.cpp:runRx()`, wrap `prbs15_verify()` call in `if (cfg.prbs_enabled)`
4. When `prbs_enabled=false`, fill bytes 4+ with zeros (or counter pattern) and skip verify
5. Range test mode (`range_test.cpp`) keeps PRBS always on — no gating needed

**Quality gates**:
- [ ] TDD: test written and fails (RED) before implementation
- [ ] `idf.py build` passes for C3 firmware
- [ ] Flash C3, run range test, verify PKT lines show non-zero `bit_err` for corrupted packets
- [ ] Flash C3, run throughput test, verify PKT lines show `bit_err=0, bytes_bad=0`
- [ ] Atomic commit with message `PRBS-1: C3 mode-gate PRBS-15 (range=on, throughput=off)`
- [ ] Push to remote

**Flash budget impact**: Negligible — adds 1 bool field + 2 branches. No new code, just gating.

**Worker assignment**: C3 firmware developer

**Estimated time**: 2 hours

**Parallel**: Yes — independent of E80 and RP2040 tasks

---

### PRBS-2: E80 — Implement PRBS-15 LFSR (Replace Stub)

**Objective**: Replace the stub `prbs.c` with a real PRBS-15 LFSR implementation matching the C3 reference. The TDD red phase is already set up — tests exist and will fail until the stub is replaced.

**Dependencies**: None (stub + tests already exist)

**Repo**: `~/repos/balloon-e80bench/firmware/e80-stm32-bench/`

**Current state**:
- `src/prbs.c` — **STUB** (fills with zeros, verify always returns 0). Comment: "STUB for TDD red phase"
- `src/prbs.h` — header with correct signatures
- `src/bench_payload.c` — `bench_payload_build()` (line 22) and `bench_payload_verify()` (line 43) already call `prbs15_fill`/`prbs15_verify`
- `tests/test_prbs.c` — PRBS-15 unit tests
- `tests/test_bench_payload.c` — payload build/verify integration tests (roundtrip, corruption detection, bit error counting, distinct sequences, min length)
- All tests currently FAIL (by design — TDD red phase)

**Files to modify**:
- `src/prbs.c` — replace stub with real PRBS-15 implementation

**Files NOT to modify** (already correct):
- `src/prbs.h` — signatures already match C3
- `src/bench_payload.c` — already calls PRBS functions
- `tests/test_prbs.c` — tests already written
- `tests/test_bench_payload.c` — tests already written

**TDD test specs (RED phase — already done)**:
1. `test_prbs.c`: PRBS-15 LFSR correctness — roundtrip, distinct sequences, deterministic
2. `test_bench_payload.c`:
   - `test_header()`: verifies seq + len fields in payload
   - `test_roundtrip()`: 50 sequences, build→verify, expects 0 bit errors
   - `test_lengths()`: every length 6-511, build→verify
   - `test_corruption_detected()`: flip 1 bit → bit_err>0, bytes_bad=1
   - `test_bit_errors_count()`: flip 3 bits in one byte → bit_err=3, bytes_bad=1
   - `test_distinct_sequences()`: different seeds → different bytes; same seed → identical
   - `test_min_length()`: header-only (6 bytes) → 0 bit errors

**Implementation approach**:

Port the C3 `prbs15_fill` and `prbs15_verify` to `prbs.c`. The C3 code uses `__builtin_popcount` which is available on GCC for ARM Cortex-M3.

```c
// prbs.c — E80 implementation
#include "prbs.h"

void prbs15_fill(uint8_t *buf, size_t len, uint32_t seed) {
    uint16_t state = (uint16_t)(seed ^ 0x5A5A) | 1;
    for (size_t i = 0; i < len; i++) {
        uint8_t byte_val = 0;
        for (int b = 0; b < 8; b++) {
            uint16_t newbit = ((state >> 14) ^ (state >> 13)) & 1;
            state = ((state << 1) | newbit) & 0x7FFF;
            byte_val = (byte_val << 1) | (newbit & 1);
        }
        buf[i] = byte_val;
    }
}

uint16_t prbs15_verify(const uint8_t *buf, size_t len, uint32_t seed, uint16_t *out_bytes_bad) {
    uint16_t state = (uint16_t)(seed ^ 0x5A5A) | 1;
    uint16_t bit_errors = 0;
    uint16_t bytes_bad = 0;
    for (size_t i = 0; i < len; i++) {
        uint8_t expected = 0;
        for (int b = 0; b < 8; b++) {
            uint16_t newbit = ((state >> 14) ^ (state >> 13)) & 1;
            state = ((state << 1) | newbit) & 0x7FFF;
            expected = (expected << 1) | (newbit & 1);
        }
        uint8_t diff = buf[i] ^ expected;
        if (diff) {
            bytes_bad++;
            bit_errors += __builtin_popcount(diff);
        }
    }
    if (out_bytes_bad) *out_bytes_bad = bytes_bad;
    return bit_errors;
}
```

**IMPORTANT — Endianness note**: The E80 `bench_payload_build()` writes the seq number in **little-endian** (bytes 0-3), while C3 uses **big-endian**. The PRBS seed must be the same value the RX uses to decode seq. Since `bench_payload_verify()` reads seq from the payload header and passes it as seed, the endianness is internally consistent within E80 — no issue.

**Quality gates**:
- [ ] TDD: `ctest --output-on-failure` — all tests pass (GREEN). Tests were RED with stub.
- [ ] `test_prbs.c` all assertions pass
- [ ] `test_bench_payload.c` all assertions pass (roundtrip, corruption, bit counting, distinct sequences)
- [ ] `make build-fw` — firmware compiles for STM32F103
- [ ] `arm-none-eabi-size build-fw/e80_bench` — flash < 35K (currently 19.6K, expect ~200 bytes for PRBS code)
- [ ] Atomic commit: `PRBS-2: E80 implement PRBS-15 LFSR (replace TDD stub)`
- [ ] Push to remote

**Flash budget impact**: ~200-400 bytes (LFSR loop code, no new data). Current: 19,604 B. Expected: ~19,900 B. Well under 35K limit.

**Worker assignment**: E80 firmware developer

**Estimated time**: 1.5 hours (port is trivial — tests already written)

**Parallel**: Yes — independent of C3 and RP2040 tasks

---

### PRBS-3: E80 — Wire PRBS-15 into RX Path + PKT Formatter

**Objective**: Call `bench_payload_verify()` on CRC-ok RX packets and populate `bit_err` / `bytes_bad` fields in the 23-field PKT output. Currently the PKT formatter hardcodes `0,0`.

**Dependencies**: PRBS-2 (needs real PRBS-15 implementation in `prbs.c`)

**Repo**: `~/repos/balloon-e80bench/firmware/e80-stm32-bench/`

**Current state**:
- `src/bench_pkt.c` (line 56): format string has literal `0,0` for bit_err/bytes_bad
- `src/bench_pkt.h`: `bench_pkt_evt_t` struct has no bit_err/bytes_bad fields
- `src/radio_bench.c` (line 433+): RX_OK path reads payload into `radio_bench_rx_buf`, extracts seq from bytes 0-3, but does NOT call `bench_payload_verify()`
- `src/bench.c` (line 882+): `RB_EVT_RX_OK` handler in the superloop — this is where PKT lines are emitted
- `bench_payload_verify()` exists in `bench_payload.c` and calls `prbs15_verify()` — just never called on RX path

**Files to modify**:
1. `src/bench_pkt.h` — add `uint16_t bit_err` and `uint16_t bytes_bad` to `bench_pkt_evt_t`
2. `src/bench_pkt.c` — change format string from `0,0` to `%u,%u` and pass the new fields
3. `src/bench.c` — in `RB_EVT_RX_OK` handler: call `bench_payload_verify()`, populate the event struct

**TDD test specs (RED phase first)**:
1. **test_bench_pkt_bit_err**: Modify `test_bench_pkt.c` to verify:
   - PKT line with `bit_err=5, bytes_bad=2` contains those values in the correct field positions
   - PKT line with `bit_err=0, bytes_bad=0` (CRC fail) still works
2. **test_bench_payload_rx_verify**: New test in `test_bench_payload.c`:
   - Build payload with `bench_payload_build()`, corrupt 2 bits, verify `bench_payload_verify()` returns correct bit_err and bytes_bad
   - Build payload, no corruption, verify returns 0, 0

**Implementation approach**:

Step 1 — Add fields to `bench_pkt_evt_t` in `bench_pkt.h`:
```c
typedef struct {
    // ... existing fields ...
    uint16_t bit_err;
    uint16_t bytes_bad;
} bench_pkt_evt_t;
```

Step 2 — Update format string in `bench_pkt.c`:
```c
// Change from:
"PKT,...,%d,0,0,..."
// To:
"PKT,...,%d,%u,%u,..."
// And pass: crc_ok, (unsigned)evt->bit_err, (unsigned)evt->bytes_bad
```

Step 3 — Wire up in `bench.c` `RB_EVT_RX_OK` handler:
```c
case RB_EVT_RX_OK:
    // ... existing RSSI/SNR extraction ...
    if (e.len >= 6) {  // minimum payload for header + PRBS
        uint16_t bytes_bad = 0;
        uint16_t bit_err = bench_payload_verify(radio_bench_rx_buf, e.len, e.seq, &bytes_bad);
        pkt_evt.bit_err = bit_err;
        pkt_evt.bytes_bad = bytes_bad;
    } else {
        pkt_evt.bit_err = 0;
        pkt_evt.bytes_bad = 0;
    }
    // ... format and emit PKT line ...
    break;
```

Step 4 — CRC-failed packets (`RB_EVT_RX_CRC`): leave `bit_err=0, bytes_bad=0` (payload is unreliable).

**Quality gates**:
- [ ] TDD: tests written and fail (RED) before implementation
- [ ] `ctest --output-on-failure` — all tests pass (GREEN)
- [ ] `make build-fw` — firmware compiles
- [ ] `arm-none-eabi-size build-fw/e80_bench` — flash < 35K (expect ~300 bytes for verify call + format change)
- [ ] Flash E80, run range test with C3 as TX, verify PKT lines show non-zero `bit_err` for corrupted packets
- [ ] Flash E80, verify CRC-failed packets still show `bit_err=0, bytes_bad=0`
- [ ] Atomic commit: `PRBS-3: E80 wire PRBS-15 into RX path + PKT formatter`
- [ ] Push to remote

**Flash budget impact**: ~300-500 bytes (format string change + verify call + struct fields). Expected total: ~20,200 B. Well under 35K.

**Worker assignment**: E80 firmware developer

**Estimated time**: 3 hours

**Parallel**: No — depends on PRBS-2

---

### PRBS-4: E80 — Add PRBS-9 Hardware TX Test Mode via CONFIG Command

**Objective**: Add a `CONFIG PRBS9 ON` / `CONFIG PRBS9 OFF` command that activates the LR2021 chip's built-in PRBS9 TX test mode. This is a hardware-level continuous TX test — no structured packets, no seq/config/session_id. Used for raw link sensitivity testing.

**Dependencies**: PRBS-2 (to ensure flash budget accounting includes both PRBS-15 and PRBS-9 additions)

**Repo**: `~/repos/balloon-e80bench/firmware/e80-stm32-bench/`

**Current state**:
- LR2021 driver has `lr20xx_radio_common_set_tx_test_mode()` in `lr20xx_radio_common.c` (line 491)
- Enum `LR20XX_RADIO_COMMON_TX_TEST_MODE_PRBS9 = 0x03` in `lr20xx_radio_common_types.h` (line 233)
- **Constraint**: PRBS9 mode is "not available with LoRa nor LR-FHSS" — only FLRC and FSK
- Bench firmware never calls `set_tx_test_mode()` — not wired up
- CONFIG command parser in `bench_cmd.c` uses a `bench_strcaseeq()` chain pattern
- Adding a command requires: (1) new enum in `bench_cmd.h`, (2) new parse block in `bench_cmd.c`, (3) new handler case in `bench.c`

**Files to modify**:
1. `src/bench_cmd.h` — add `BENCH_CMD_PRBS9` enum value + `uint8_t prbs9_on` field to `bench_cmd_t`
2. `src/bench_cmd.c` — add parse block for `CONFIG PRBS9 ON` / `CONFIG PRBS9 OFF` (3-token: "CONFIG" + "PRBS9" + "ON"|"OFF")
3. `src/bench.c` — add handler case for `BENCH_CMD_PRBS9`:
   - ON: call `lr20xx_radio_common_set_tx_test_mode(E80_CONTEXT, LR20XX_RADIO_COMMON_TX_TEST_MODE_PRBS9)` then `lr20xx_radio_common_set_tx(E80_CONTEXT, 0)` (continuous)
   - OFF: call `lr20xx_radio_common_set_tx_test_mode(E80_CONTEXT, LR20XX_RADIO_COMMON_TX_TEST_MODE_NORMAL)` then standby
4. `src/radio_bench.h` / `radio_bench.c` — optionally add a wrapper function `radio_bench_set_prbs9(bool on)` that validates current modulation (reject if LoRa active)

**TDD test specs (RED phase first)**:
1. **test_bench_cmd_prbs9**: In `test_bench_cmd.c`:
   - `CONFIG PRBS9 ON` → parses to `BENCH_CMD_PRBS9`, `prbs9_on=1`
   - `CONFIG PRBS9 OFF` → parses to `BENCH_CMD_PRBS9`, `prbs9_on=0`
   - `config prbs9 on` (lowercase) → same (case-insensitive)
   - `CONFIG PRBS9` (missing arg) → `BENCH_CMD_E_ARG`
   - `CONFIG PRBS9 MAYBE` (invalid arg) → `BENCH_CMD_E_ARG`
2. **test_radio_bench_prbs9_mod_guard**: Verify that calling `radio_bench_set_prbs9(true)` when `cur_cfg.mod == BENCH_MOD_LORA` returns an error (PRBS9 not available with LoRa)

**Implementation approach**:

Step 1 — Parse block in `bench_cmd.c` (insert before the unknown-command fallthrough):
```c
if (bench_strcaseeq(tokens[0], "CONFIG") && ntok == 3 &&
    bench_strcaseeq(tokens[1], "PRBS9")) {
    out->id = BENCH_CMD_PRBS9;
    if (bench_strcaseeq(tokens[2], "ON"))
        out->prbs9_on = 1;
    else if (bench_strcaseeq(tokens[2], "OFF"))
        out->prbs9_on = 0;
    else
        return BENCH_CMD_E_ARG;
    return BENCH_CMD_OK;
}
```

Step 2 — Handler in `bench.c`:
```c
case BENCH_CMD_PRBS9:
    if (c->prbs9_on) {
        if (cur_cfg.mod == BENCH_MOD_LORA) {
            console_putln("ERR PRBS9 not available with LoRa");
            break;
        }
        lr20xx_radio_common_set_tx_test_mode(E80_CONTEXT,
            LR20XX_RADIO_COMMON_TX_TEST_MODE_PRBS9);
        lr20xx_radio_common_set_tx(E80_CONTEXT, 0);  // continuous TX
        console_putln("OK PRBS9 ON");
    } else {
        lr20xx_radio_common_set_tx_test_mode(E80_CONTEXT,
            LR20XX_RADIO_COMMON_TX_TEST_MODE_NORMAL);
        lr20xx_system_set_standby(E80_CONTEXT, LR20XX_SYSTEM_STANDBY_RC);
        console_putln("OK PRBS9 OFF");
    }
    break;
```

Step 3 — Add `PRBS9 ON/OFF` to the HELP command output.

**Quality gates**:
- [ ] TDD: command parser tests written and fail (RED) before implementation
- [ ] `ctest --output-on-failure` — all tests pass (GREEN)
- [ ] `make build-fw` — firmware compiles
- [ ] `arm-none-eabi-size build-fw/e80_bench` — flash < 35K (expect ~400-600 bytes for command + driver calls)
- [ ] Flash E80, send `CONFIG PRBS9 ON` via serial, verify chip enters continuous PRBS9 TX (monitor on spectrum analyzer or SDR)
- [ ] Flash E80, send `CONFIG PRBS9 OFF`, verify chip returns to standby
- [ ] Flash E80, set LoRa mode, send `CONFIG PRBS9 ON`, verify `ERR PRBS9 not available with LoRa` response
- [ ] Atomic commit: `PRBS-4: E80 add PRBS-9 hardware TX test mode CONFIG command`
- [ ] Push to remote

**Flash budget impact**: ~400-600 bytes (parse block + handler + driver function calls). Expected total: ~20,800 B. Well under 35K.

**Worker assignment**: E80 firmware developer

**Estimated time**: 3 hours

**Parallel**: No — depends on PRBS-2 (shared flash budget tracking)

---

### PRBS-5: RP2040 — Port PRBS-15 Fill + Verify Functions

**Objective**: Create `prbs15.cpp` / `prbs15.h` for the RP2040 firmware, porting the C3 reference implementation. This is the foundational module for both TX fill and RX verify.

**Dependencies**: None (pure C/C++ code, no hardware deps)

**Repo**: `~/repos/balloon-fresh/firmware/rp2040/`

**Current state**:
- No PRBS code exists anywhere in the RP2040 firmware
- Current BER uses a simple counter pattern: TX fills bytes 29..pktSize-3 with `i & 0xFF`, RX compares against same
- `bytes_bad` is never computed (always 0)
- No test framework exists (no unit tests, no test directory)
- Build system: PlatformIO (primary), CMake (secondary)

**Files to create**:
1. `src/prbs15.h` — header with `prbs15_fill` and `prbs15_verify` declarations
2. `src/prbs15.cpp` — implementation (copy of C3 `prbs.cpp`, adapted for RP2040)

**Files to modify**:
- `platformio.ini` — add `prbs15.cpp` to the `build_src_filter` for `rp2040-harm-rx` and `rp2040-sweep-tx-v4` environments

**TDD test specs (RED phase first)**:

Since no test framework exists, create a minimal host-testable harness:

1. Create `test/test_prbs15.cpp` — standalone host GCC test (no PlatformIO dependency):
   - `test_roundtrip`: fill buffer, verify → expect 0 bit errors, 0 bytes_bad
   - `test_corruption`: fill buffer, flip 1 bit, verify → expect bit_err>0, bytes_bad=1
   - `test_bit_count`: flip 3 bits in one byte → expect bit_err=3, bytes_bad=1
   - `test_distinct_seeds`: different seeds produce different byte sequences
   - `test_same_seed`: same seed reproduces identical sequence
   - `test_cross_compat`: verify that C3 and RP2040 produce identical bytes for the same seed (golden vector test)
2. Create `test/Makefile` — simple `gcc -o test_prbs15 test_prbs15.cpp ../src/prbs15.cpp && ./test_prbs15`

**Implementation approach**:

Direct port of C3 `prbs.cpp`. The RP2040 (Cortex-M0+) supports `__builtin_popcount` via GCC.

```cpp
// prbs15.h
#pragma once
#include <stdint.h>
#include <stddef.h>

void prbs15_fill(uint8_t *buf, size_t len, uint32_t seed);
uint16_t prbs15_verify(const uint8_t *buf, size_t len, uint32_t seed, uint16_t *out_bytes_bad);
```

```cpp
// prbs15.cpp — identical algorithm to C3 prbs.cpp
// (see PRBS-2 for the exact code — byte-for-byte identical)
```

**Golden vector for cross-compatibility**: Define a test vector with `seed=42, len=16` and the expected 16 bytes. This vector must match across C3, E80, and RP2040. Generate it from the C3 reference:

```
seed=42, len=16:
(expected bytes — to be filled in from C3 reference output during implementation)
```

**Quality gates**:
- [ ] TDD: host tests written and fail (RED) before implementation
- [ ] `make -C test/` — all tests pass (GREEN)
- [ ] Cross-compatibility: golden vector test matches C3 output exactly
- [ ] `pio run -e rp2040-harm-rx` — firmware compiles with `prbs15.cpp` included
- [ ] `pio run -e rp2040-sweep-tx-v4` — firmware compiles with `prbs15.cpp` included
- [ ] Atomic commit: `PRBS-5: RP2040 port PRBS-15 fill + verify functions`
- [ ] Push to remote

**Flash budget impact**: ~200-400 bytes (LFSR code). RP2040 has 2 MB flash — no budget concern.

**Worker assignment**: RP2040 firmware developer

**Estimated time**: 2 hours (port + test harness creation)

**Parallel**: Yes — independent of E80 and C3 tasks. Can run alongside PRBS-1, PRBS-2.

---

### PRBS-6: RP2040 — Wire PRBS-15 into TX Fill + RX Verify

**Objective**: Replace the counter pattern (`i & 0xFF`) with PRBS-15 fill on TX and PRBS-15 verify on RX. Populate `bytes_bad` (currently always 0).

**Dependencies**: PRBS-5 (needs `prbs15_fill` / `prbs15_verify` functions)

**Repo**: `~/repos/balloon-fresh/firmware/rp2040/`

**Current state**:
- TX (`multi_radio_sweep_gps_v4.cpp`, line 1232): `for (int i = 29; i < pktSize; i++) txBuf[i] = (uint8_t)(i & 0xFF);`
- RX (`pkt_harmonized_rx.cpp`, lines 1010-1022): compares `rxBuf[rxIdx]` against `(uint8_t)(i & 0xFF)` via XOR + popcount
- `emitPktLine()` (line 703) already accepts `bit_err` and `bytes_bad` params — just needs real values
- `bytes_bad` is hardcoded to 0 at line 1045

**Packet layout (RP2040 — different from C3/E80!)**:
```
Bytes 0-3:   sync header (0xA5 0x5A 0x42 0x24)
Bytes 4-18:  GPS payload (lat, lon, sats, fixQ, utcSec)
Byte  19:    phaseId
Bytes 20-21: seq (uint16 BE)
Bytes 22-28: fw_hash (7 ASCII chars)
Bytes 29 to pktSize-3:  PAYLOAD FILL (currently counter, target: PRBS-15)
Bytes pktSize-2 to pktSize-1: CRC-16 (CCITT 0x1021)
```

**Seed strategy**: Use the seq number (bytes 20-21, uint16 BE) as the PRBS-15 seed. The RX already extracts this seq for the PKT output. Alternative: use `phaseId * 256 + seqInPhase` for more entropy — but seq alone is sufficient and simpler.

**Files to modify**:
1. `src/multi_radio_sweep_gps_v4.cpp` — replace counter fill (line 1232) with `prbs15_fill()`:
   ```cpp
   // Replace:
   for (int i = 29; i < pktSize; i++) txBuf[i] = (uint8_t)(i & 0xFF);
   // With:
   uint16_t prbs_seed = (uint16_t)((txBuf[20] << 8) | txBuf[21]);  // seq from header
   prbs15_fill(&txBuf[29], pktSize - 29 - 2, prbs_seed);  // -2 for CRC-16 at end
   ```
2. `src/pkt_harmonized_rx.cpp` — replace counter comparison (lines 1010-1022) with `prbs15_verify()`:
   ```cpp
   // Replace counter BER loop with:
   uint16_t bytes_bad = 0;
   uint16_t bit_err = 0;
   int prbs_len = pktSize - 29 - 2;  // same as TX fill region
   if (prbs_len > 0) {
       uint16_t prbs_seed = pktSeq & 0xFFFF;  // seq from decoded header
       // Note: RX reads from rxBuf at syncOffset + 29
       bit_err = prbs15_verify(&rxBuf[syncOffset + 29], prbs_len, prbs_seed, &bytes_bad);
   }
   emitPktLine(pktSeq, ts_ms, rssi_dbm, snr_db, 1, bit_err, bytes_bad, ...);
   ```

**TDD test specs (RED phase first)**:
1. Extend `test/test_prbs15.cpp`:
   - `test_tx_rx_roundtrip`: build a TX payload with the RP2040 header layout + PRBS fill, then verify it with the same seed → expect 0 bit errors
   - `test_tx_rx_corruption`: build TX payload, corrupt 2 bytes in the PRBS region, verify → expect correct bit_err and bytes_bad
   - `test_seed_from_seq`: verify that seq=0 and seq=1 produce different PRBS patterns (seed sensitivity)

**Implementation approach**:
1. Modify TX fill to use `prbs15_fill()` with seq-based seed
2. Modify RX verify to use `prbs15_verify()` with decoded seq
3. Replace hardcoded `bytes_bad=0` with real value from verify
4. Ensure CRC-16 is computed AFTER PRBS fill (TX line 1288 — already after fill)
5. Ensure PRBS verify happens BEFORE the CRC-16 check on RX (or only on CRC-ok packets — see note below)

**CRC handling**: On RP2040, there are two CRC checks:
- Hardware CRC (chip-level) — if it fails, PKT is emitted with `crc_ok=0, bit_err=0, bytes_bad=0` (correct, can't verify payload)
- App-layer CRC-16 (line 912) — if it fails, same treatment
- Only on successful packets (both CRCs pass) should PRBS verify be called

**Quality gates**:
- [ ] TDD: tests written and fail (RED) before implementation
- [ ] `make -C test/` — all tests pass (GREEN)
- [ ] `pio run -e rp2040-harm-rx` — compiles
- [ ] `pio run -e rp2040-sweep-tx-v4` — compiles
- [ ] Flash RP2040 TX + RP2040 RX, run sweep, verify PKT lines show non-zero `bit_err` and `bytes_bad` for corrupted packets
- [ ] Verify CRC-failed packets still show `bit_err=0, bytes_bad=0`
- [ ] Cross-compatibility: RP2040 TX → C3 RX should produce matching PRBS verification (if seeds align — see note below)
- [ ] Atomic commit: `PRBS-6: RP2040 wire PRBS-15 into TX fill + RX verify`
- [ ] Push to remote

**⚠️ Cross-rig compatibility note**: The RP2040 packet layout differs from C3/E80. The PRBS fill starts at byte 29 (not byte 4), and the seed is a 16-bit seq (not 32-bit). Cross-rig PRBS verification (e.g., RP2040 TX → C3 RX) will NOT work without alignment of the fill region and seed. This is acceptable — PRBS-15 is primarily for same-rig TX→RX BER measurement. Cross-rig testing uses PRBS-8 integration test (PRBS-8) or PER only.

**Flash budget impact**: Negligible (RP2040 has 2 MB flash). Code replaces a loop with a function call — net delta ~0.

**Worker assignment**: RP2040 firmware developer

**Estimated time**: 4 hours

**Parallel**: No — depends on PRBS-5

---

### PRBS-7: RP2040 — Add PRBS-9 Hardware TX Test Mode via CONFIG Command

**Objective**: Add a serial command to activate the LR2021 chip's PRBS-9 hardware TX test mode on the RP2040 rig. The RP2040 uses a custom raw SPI driver (not RadioLib), so this requires direct register writes.

**Dependencies**: PRBS-5 (same repo, shared build config)

**Repo**: `~/repos/balloon-fresh/firmware/rp2040/`

**Current state**:
- RP2040 uses custom raw SPI driver — no RadioLib, no `lr20xx_radio_common_set_tx_test_mode()` wrapper
- Serial command interface in `pkt_harmonized_rx.cpp:processCommand()` (line 231) handles: `SET_TIME`, `FW_QUERY`, `SESSION`, `CONFIG`, `SET_INTERLEAVE`
- TX side (`multi_radio_sweep_gps_v4.cpp`, line 777) handles: `SET_TIME`, `FW_QUERY`, `SET_INTERLEAVE`
- The LR2021 PRBS-9 TX test mode is activated via SPI command `SET_TX_TEST_MODE` (opcode from the LR2021 datasheet — the E80 driver uses `LR20XX_RADIO_COMMON_SET_TX_TEST_MODE_OC`)

**SPI command for PRBS-9 TX test mode**:
Based on the E80 driver (`lr20xx_radio_common.c` line 491), the command is:
- Opcode: `LR20XX_RADIO_COMMON_SET_TX_TEST_MODE_OC` (2-byte command)
- Payload: 1 byte mode value (`0x03` for PRBS9)
- Followed by `SET_TX` with timeout=0 for continuous TX

**Files to modify**:
1. `src/pkt_harmonized_rx.cpp` — add `PRBS9 ON` / `PRBS9 OFF` command in `processCommand()`
2. `src/multi_radio_sweep_gps_v4.cpp` — add `PRBS9 ON` / `PRBS9 OFF` command in its command handler
3. Optionally create `src/rf_test_mode.cpp` / `rf_test_mode.h` — wrapper functions for PRBS-9 SPI commands

**TDD test specs (RED phase first)**:
1. Host-side test for command parsing:
   - `PRBS9 ON` → sets a global `prbs9_active = true`, responds `OK PRBS9 ON`
   - `PRBS9 OFF` → sets `prbs9_active = false`, responds `OK PRBS9 OFF`
   - Invalid arg → responds `ERR PRBS9 <ON|OFF>`
   - When `prbs9_active=true`, normal sweep TX is suppressed (chip is in continuous test mode)

**Implementation approach**:

Step 1 — Add SPI command for TX test mode. The RP2040 raw SPI driver has `rfWriteCmd()` for writing commands. The LR2021 SET_TX_TEST_MODE command bytes need to be extracted from the E80 driver headers:

```cpp
// rf_test_mode.cpp
#include "rf_test_mode.h"
#include "rf_spi.h"  // existing raw SPI functions

void rf_set_prbs9_tx(bool on) {
    if (on) {
        uint8_t cmd[] = {0x0D, 0x0B, 0x03};  // SET_TX_TEST_MODE opcode + PRBS9 mode
        rfWriteCmd(cmd, 3);
        // Then set TX continuous
        uint8_t tx_cmd[] = {0x02, 0x0D};  // SET_TX (from existing rfSetTx)
        rfWriteCmd(tx_cmd, 2);
    } else {
        uint8_t cmd[] = {0x0D, 0x0B, 0x00};  // NORMAL mode
        rfWriteCmd(cmd, 3);
        // Return to standby
        uint8_t standby[] = {0x02, 0x04};  // SET_STANDBY
        rfWriteCmd(standby, 2);
    }
}
```

**Note**: The exact opcode bytes must be verified from `lr20xx_radio_common.h` / the LR2021 datasheet. The E80 driver constant `LR20XX_RADIO_COMMON_SET_TX_TEST_MODE_OC` holds the 2-byte opcode. The implementer MUST read this value from `~/repos/balloon-e80bench/firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_common.h` before writing the RP2040 SPI command.

Step 2 — Add command handler in `processCommand()`:
```cpp
if (strcmp(cmd, "PRBS9") == 0) {
    if (argc < 1) { dualPrintf("ERR PRBS9 <ON|OFF>\r\n"); return; }
    if (strcmp(arg1, "ON") == 0) {
        rf_set_prbs9_tx(true);
        prbs9_active = true;
        dualPrintf("OK PRBS9 ON\r\n");
    } else if (strcmp(arg1, "OFF") == 0) {
        rf_set_prbs9_tx(false);
        prbs9_active = false;
        dualPrintf("OK PRBS9 OFF\r\n");
    } else {
        dualPrintf("ERR PRBS9 <ON|OFF>\r\n");
    }
    return;
}
```

Step 3 — Guard the sweep TX loop: when `prbs9_active=true`, skip normal packet TX (chip is in continuous test mode).

Step 4 — Add LoRa modulation guard: PRBS-9 is not available with LoRa (per chip datasheet). Check current phase's `pktType` before enabling.

**Quality gates**:
- [ ] TDD: command parsing test written and fails (RED)
- [ ] `pio run -e rp2040-harm-rx` — compiles
- [ ] `pio run -e rp2040-sweep-tx-v4` — compiles
- [ ] Flash RP2040, send `PRBS9 ON` via serial, verify continuous PRBS-9 TX on spectrum analyzer / SDR
- [ ] Send `PRBS9 OFF`, verify chip returns to standby
- [ ] Verify normal sweep resumes after `PRBS9 OFF`
- [ ] Verify LoRa mode rejection (if applicable — RP2040 uses both LoRa and FLRC phases)
- [ ] Atomic commit: `PRBS-7: RP2040 add PRBS-9 hardware TX test mode`
- [ ] Push to remote

**Flash budget impact**: ~400-600 bytes (SPI command + handler). No concern (2 MB flash).

**Worker assignment**: RP2040 firmware developer

**Estimated time**: 4 hours (includes SPI opcode research)

**Parallel**: No — depends on PRBS-5 (shared repo + build config). Can run after PRBS-5 and in parallel with PRBS-6 if different developer.

---

### PRBS-8: Cross-Rig Integration Test — PRBS-15 Cross-Check

**Objective**: Verify that all 3 rigs produce correct PRBS-15 BER measurements via a cross-rig integration test. Confirm that host tools (`pkt_parser.py`, `fw_harm_measurement.py`) correctly parse `bit_err` and `bytes_bad` fields.

**Dependencies**: PRBS-1 (C3 mode-gating), PRBS-3 (E80 RX wired up), PRBS-6 (RP2040 TX+RX wired up)

**Repo**: `~/repos/balloon-fresh/` (host tools + docs)

**Current state**:
- Host tools (`pkt_parser.py`, `fw_harm_measurement.py`) already parse `bit_err` and `bytes_bad` — no changes needed
- All 3 rigs should now emit real values for CRC-ok packets

**Test matrix**:

| TX Rig | RX Rig | Expected | Notes |
|--------|--------|----------|-------|
| C3 → C3 | Same-rig loopback | bit_err ≈ 0 (noise-free bench), bytes_bad ≈ 0 | Baseline — already working |
| E80 → E80 | Same-rig loopback | bit_err ≈ 0, bytes_bad ≈ 0 | New — validates PRBS-2 + PRBS-3 |
| RP2040 → RP2040 | Same-rig loopback | bit_err ≈ 0, bytes_bad ≈ 0 | New — validates PRBS-5 + PRBS-6 |
| C3 → E80 | Cross-rig | ⚠️ See note | Different packet layouts — PRBS fill region differs |
| E80 → C3 | Cross-rig | ⚠️ See note | Same issue |
| C3 → RP2040 | Cross-rig | ⚠️ See note | Different layouts |
| RP2040 → C3 | Cross-rig | ⚠️ See note | Different layouts |
| E80 → RP2040 | Cross-rig | ⚠️ See note | Different layouts |
| RP2040 → E80 | Cross-rig | ⚠️ See note | Different layouts |

**⚠️ Cross-rig compatibility**: The 3 rigs use different packet layouts:
- C3/E80: 4-byte seq header (at byte 0), PRBS fill from byte 4
- RP2040: 29-byte header (sync + GPS + phase + seq + fw_hash), PRBS fill from byte 29

Cross-rig PRBS-15 verification requires the RX to know the TX's packet layout to locate the PRBS region and extract the seed. Since the rigs use different layouts, cross-rig PRBS verification will NOT produce meaningful BER values without a unified packet format. This is a known limitation.

**Same-rig tests are the primary validation**. Cross-rig PER (packet error rate) remains valid regardless of PRBS.

**Files to create**:
1. `docs/PRBS-integration-test-procedure.md` — step-by-step test procedure for each rig pair
2. `tests/host/test_prbs_cross_rig.py` — Python script that:
   - Connects to each rig via serial
   - Sends `CONFIG` commands to set session/config IDs
   - Runs a short range test (10 packets per modulation)
   - Parses PKT output and validates `bit_err` and `bytes_bad` fields
   - Generates a report with pass/fail per rig

**Quality gates**:
- [ ] Same-rig C3 loopback: `bit_err=0, bytes_bad=0` for all CRC-ok packets (bench environment, no noise)
- [ ] Same-rig E80 loopback: `bit_err=0, bytes_bad=0` for all CRC-ok packets
- [ ] Same-rig RP2040 loopback: `bit_err=0, bytes_bad=0` for all CRC-ok packets
- [ ] Introduce controlled attenuation (20 dB pad): verify `bit_err` increases as SNR decreases
- [ ] `pkt_parser.py` correctly parses all 23 fields including `bit_err` and `bytes_bad`
- [ ] `fw_harm_measurement.py` correctly computes BER from `bit_err` / total bits
- [ ] Atomic commit: `PRBS-8: cross-rig PRBS-15 integration test + procedure`
- [ ] Push to remote

**Worker assignment**: Integration test engineer

**Estimated time**: 4 hours

**Parallel**: No — depends on PRBS-1, PRBS-3, PRBS-6 all being complete

---

## 4. Flash Budget Summary (E80)

| Task | Added Flash (est.) | Cumulative Flash | Limit (35K) | Headroom |
|------|--------------------|------------------|-------------|----------|
| Baseline | — | 19,604 B (29%) | 35,840 B | 16,236 B |
| PRBS-2 (LFSR impl) | ~300 B | ~19,900 B | 35,840 B | 15,940 B |
| PRBS-3 (RX wire-up) | ~400 B | ~20,300 B | 35,840 B | 15,540 B |
| PRBS-4 (PRBS-9 CONFIG) | ~500 B | ~20,800 B (30%) | 35,840 B | 15,040 B |

**Verdict**: All PRBS tasks fit comfortably within the 35K flash budget. Final expected usage: ~20.8K (30% of 64K), leaving ~15K headroom.

---

## 5. Parallelism Schedule

```
Time →  T0          T+2h         T+4h         T+6h         T+8h         T+12h
        │            │            │            │            │            │
PRBS-1  ├────────────┤ (C3 dev)   │            │            │            │
PRBS-2  ├─────────┤  (E80 dev)    │            │            │            │
PRBS-5  ├────────────┤ (RP2040 dev)│           │            │            │
        │            │            │            │            │            │
        │       PRBS-3 ├──────────┤ (E80 dev)  │            │            │
        │       PRBS-4 ├──────────┤ (E80 dev)  │            │            │
        │       PRBS-6 ├──────────────┤ (RP2040 dev)        │            │
        │       PRBS-7 ├──────────────┤ (RP2040 dev)        │            │
        │            │            │            │            │            │
        │            │            │            │       PRBS-8 ├────────┤ (Integration)
```

- **Wave 1 (T0)**: PRBS-1, PRBS-2, PRBS-5 in parallel (3 developers)
- **Wave 2 (T+2h)**: PRBS-3, PRBS-4, PRBS-6, PRBS-7 in parallel (E80 dev does PRBS-3 then PRBS-4; RP2040 dev does PRBS-6 then PRBS-7)
- **Wave 3 (T+8h)**: PRBS-8 after all rig tasks complete

**Total estimated wall-clock time**: ~12 hours with 3 developers in parallel.

---

## 6. Summary Table

| Task | Rig | Mode | Dependencies | Est. Time | Parallel? | Flash Impact |
|------|-----|------|--------------|-----------|-----------|--------------|
| PRBS-1 | C3 | PRBS-15 mode-gate | None | 2h | Wave 1 | Negligible |
| PRBS-2 | E80 | PRBS-15 LFSR impl | None | 1.5h | Wave 1 | ~300 B |
| PRBS-3 | E80 | PRBS-15 RX wire-up | PRBS-2 | 3h | Wave 2 | ~400 B |
| PRBS-4 | E80 | PRBS-9 CONFIG cmd | PRBS-2 | 3h | Wave 2 | ~500 B |
| PRBS-5 | RP2040 | PRBS-15 port | None | 2h | Wave 1 | Negligible |
| PRBS-6 | RP2040 | PRBS-15 TX+RX wire-up | PRBS-5 | 4h | Wave 2 | Negligible |
| PRBS-7 | RP2040 | PRBS-9 CONFIG cmd | PRBS-5 | 4h | Wave 2 | ~500 B |
| PRBS-8 | All | Integration test | PRBS-1,3,6 | 4h | Wave 3 | N/A (host) |

---

## 7. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| E80 flash overflow with all PRBS tasks | Low | High | Budget tracking shows 30% usage — 15K headroom. Monitor after each task. |
| Cross-rig PRBS-15 incompatibility (different packet layouts) | Certain | Medium | Documented as known limitation. Same-rig BER is the primary metric. Cross-rig uses PER only. |
| RP2040 PRBS-9 SPI opcode incorrect | Medium | Medium | Must read `LR20XX_RADIO_COMMON_SET_TX_TEST_MODE_OC` from E80 driver headers before implementing. Verify with spectrum analyzer. |
| `__builtin_popcount` not available on target | Very Low | Low | Available on GCC for ARM Cortex-M0+ (RP2040) and Cortex-M3 (E80). C3 uses ESP-IDF GCC. All confirmed. |
| PRBS-15 verify too slow for throughput mode on E80 | Medium | Low | Mode-gated: PRBS-15 is OFF for throughput mode. ~5ms/pkt cost acceptable for range tests. E80 at 72 MHz is slower than C3 at 160 MHz — verify timing if needed. |
| RP2040 no test framework | Medium | Low | Create minimal host-GCC test harness in `test/` directory. Does not need PlatformIO for unit tests. |
| PRBS-9 not available with LoRa modulation | Certain | Low | Add modulation guard in all rigs. Error message if user tries to enable PRBS-9 in LoRa mode. |

---

## 8. Cross-Reference: Key Source Files

### C3 (reference implementation)
| File | Path | Role |
|------|------|------|
| `prbs.h` | `mesh-stack/flrc-bench-espidf/main/prbs.h` | PRBS-15 API declarations |
| `prbs.cpp` | `mesh-stack/flrc-bench-espidf/main/prbs.cpp` | PRBS-15 LFSR implementation (reference) |
| `range_test.cpp` | `mesh-stack/flrc-bench-espidf/main/range_test.cpp` | TX fill (line 144) + RX verify (line 492) |
| `bench_main.cpp` | `mesh-stack/flrc-bench-espidf/main/bench_main.cpp` | TX fill (line 150) + RX verify (line 279) |

### E80
| File | Path | Role |
|------|------|------|
| `prbs.c` | `e80-stm32-bench/src/prbs.c` | STUB — replace with real impl (PRBS-2) |
| `prbs.h` | `e80-stm32-bench/src/prbs.h` | API declarations (already correct) |
| `bench_payload.c` | `e80-stm32-bench/src/bench_payload.c` | `bench_payload_build()` + `bench_payload_verify()` |
| `bench_pkt.c` | `e80-stm32-bench/src/bench_pkt.c` | PKT formatter — hardcoded `0,0` (PRBS-3) |
| `bench_pkt.h` | `e80-stm32-bench/src/bench_pkt.h` | Event struct — add bit_err/bytes_bad (PRBS-3) |
| `bench.c` | `e80-stm32-bench/src/bench.c` | Superloop + command handler (PRBS-3, PRBS-4) |
| `bench_cmd.c` | `e80-stm32-bench/src/bench_cmd.c` | Command parser (PRBS-4) |
| `bench_cmd.h` | `e80-stm32-bench/src/bench_cmd.h` | Command enum + struct (PRBS-4) |
| `radio_bench.c` | `e80-stm32-bench/src/radio_bench.c` | Radio control, RX path, `radio_bench_rx_buf` |
| `lr20xx_radio_common_types.h` | `e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_common_types.h` | PRBS9 enum (line 233) |
| `lr20xx_radio_common.c` | `e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_common.c` | `set_tx_test_mode()` (line 491) |
| `test_prbs.c` | `e80-stm32-bench/tests/test_prbs.c` | PRBS unit tests |
| `test_bench_payload.c` | `e80-stm32-bench/tests/test_bench_payload.c` | Payload build/verify tests |
| `test_bench_pkt.c` | `e80-stm32-bench/tests/test_bench_pkt.c` | PKT formatter tests |
| `test_bench_cmd.c` | `e80-stm32-bench/tests/test_bench_cmd.c` | Command parser tests |

### RP2040
| File | Path | Role |
|------|------|------|
| `pkt_harmonized_rx.cpp` | `firmware/rp2040/src/pkt_harmonized_rx.cpp` | RX firmware — BER loop (line 1010), `emitPktLine()` (line 703), `processCommand()` (line 231) |
| `multi_radio_sweep_gps_v4.cpp` | `firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp` | TX firmware — fill pattern (line 1232), command handler (line 777) |
| `platformio.ini` | `firmware/rp2040/platformio.ini` | Build config — add `prbs15.cpp` to `build_src_filter` |
| `prbs15.cpp` (new) | `firmware/rp2040/src/prbs15.cpp` | PRBS-15 implementation (PRBS-5) |
| `prbs15.h` (new) | `firmware/rp2040/src/prbs15.h` | PRBS-15 API (PRBS-5) |
| `rf_test_mode.cpp` (new) | `firmware/rp2040/src/rf_test_mode.cpp` | PRBS-9 SPI wrapper (PRBS-7) |

---

## 9. Host Tool Compatibility

Per the design requirements, host tools already parse `bit_err` and `bytes_bad`:

- `pkt_parser.py` — parses all 23 fields of the PKT CSV format
- `fw_harm_measurement.py` — computes aggregate BER from `bit_err` / total bits

**No changes needed** to host tools. The PRBS enablement only changes firmware-side values from `0` to real measurements. The PKT format remains identical (23 fields, same positions).

---

*End of specification.*