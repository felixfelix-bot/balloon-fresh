# Full Progress Report for Consultant V6 Review

**Date:** 2026-08-05
**Session:** 39 commits, 53 files changed, 11,522 lines added

## COMPLETED WORK (all pushed to github/autonomous/mesh-baseline)

### Builds (verified passing)
- Tracker firmware: 332KB (S3 target), 69% flash free
- FIPS C3: `cargo build -p microfips-esp32c3 --target riscv32imc-unknown-none-elf` PASSES
- Cross-platform: C3 (301KB) + S3 (330KB) both build

### Tests (verified passing)
- nostr_store: 7/7 host tests pass
- nostr_dump CLI: 6/6 host tests pass
- relay pipeline: 12/12 tests pass (but now broken — tollgate_proto_encode/decode undefined reference after real proto header adopted)
- CI: 433 tests in GitHub Actions
- TollGate payment: 119 tests pass (host C)

### Bug Fixes (5 consultant bugs from V3, all fixed)
1. Inverted deserialize check — f11ddd6
2. TollGate API names — cb49869
3. Missing Kconfig flag — cb49869
4. nostr_event_t sig field — bc3bd5b
5. radio_task 5000ms blocking → 100ms — 94bfe4c

### CLI Commands (implemented today)
- radio_test: EXISTS (app_main.cpp:315)
- radio_recv: EXISTS (app_main.cpp:335)
- relay_send_nostr: IMPLEMENTED (108c2b9)
- nostr_dump: IMPLEMENTED (b093ac8)
- tollgate_send_pay: IMPLEMENTED (65a46fd) — used existing proto from mesh-stack/tollgate/
- Total: 13 CLI commands registered in app_main.cpp

### FIPS Rust Build (fixed today)
- 4 commits: cfg variants, logger, .cargo/config.toml, DRAM overflow fix
- C3 target builds: `cargo build -p microfips-esp32c3` → Finished (dev profile)
- Fixes: portable-atomic, esp32c3 register addresses, esp-println logger, riscv32imc target config

### PCB Work (attempted but CRITICAL ISSUE FOUND)
- GPIO fix committed: LED removed from GPIO10, FEM_TX net added (698a039)
- Gerbers regenerated: 24 files in gerbers_v1_fixed/
- BUT: balloon-circuit-design track ran DRC and found:

## CRITICAL: V1 PCB IS NOT ORDER-READY

balloon-circuit-design consultant review (commit 502d33f) found:

### Architecture Mismatch
- Firmware Kconfig: single-MCU (C3 controls SPI/LR2021 directly)
- V1 PCB: dual-MCU (RP2040 controls SPI/LR2021, C3 handles UART/GPS/I2C/LED)
- GPIO10/GPIO18 fix is for single-MCU firmware, NOT applicable to V1 PCB hardware
- The GPIO fix we applied was to the wrong architecture

### V1 PCB DRC Failures (FATAL)
- 3V3↔GND short: 18 instances — systematic routing error, power rail short
- All 4 SPI lines shorted together — LR2021 radio non-functional
- SPI0_SCK↔3V3, SPI0_SCK↔GND, SPI0_NSS↔GND — SPI bus completely broken
- UART TX lines shorted — inter-MCU communication dead
- I2C SDA/SCL shorted to power/ground — I2C bus dead
- RF traces shorted — both radios compromised
- 43 unconnected nets

### F33 PCB Also Broken
- 10 unique net-pair shorts including GND↔RF, UART TX shorted
- 32 unconnected nets

### Implication
The GPIO10→GPIO18 fix was solving a problem that doesn't exist on the V1 PCB.
The V1 PCB needs a complete re-design or the firmware needs to switch to dual-MCU architecture.
This is a HUMAN DECISION: single-MCU vs dual-MCU architecture.

## CROSS-TRACK DISCOVERIES

1. balloon-circuit-design: PCB architecture mismatch (single-MCU firmware vs dual-MCU PCB)
2. balloon-pre-stretching: PCB not order-ready delays weight verification, but pressure test rig unaffected
3. balloon-tollgate: tollgate_payment_proto.h is wire-compatible, relay_send_nostr CLI already adopted

## QUESTIONS FOR CONSULTANT

1. ARCHITECTURE DECISION: Should we go single-MCU (C3 controls everything, needs new PCB design) or dual-MCU (RP2040+LR2021 on SPI, C3 on UART/GPS, needs firmware rewrite to use RP2040 as radio bridge)? Which is faster to flying?

2. PCB FATAL SHORTS: Is the V1 PCB salvageable (fix the shorts in KiCad) or should we start fresh? The 18x 3V3↔GND shorts suggest systematic routing error.

3. RELAY PIPELINE TEST BROKEN: After adopting real tollgate_payment_proto.h, the test_relay_pipeline.c has undefined references to tollgate_proto_encode/decode. Should we link the real proto source in the test, or keep the mock?

4. RESOURCE MANAGEMENT: Workers keep crashing from OOM (7GB RAM, 4 cores, 8 worker processes). Should we limit to 2 concurrent workers?

5. NEXT STEPS PRIORITY: Given PCB is blocked on architecture decision, what should workers do while waiting? Options:
   a. Fix relay pipeline test (link real tollgate proto)
   b. Write dual-MCU firmware bridge (if we go dual-MCU)
   c. Design new single-MCU PCB (if we go single-MCU)
   d. More no-hardware testing
   e. Something else

6. What is the SINGLE most important thing Felix should decide right now?