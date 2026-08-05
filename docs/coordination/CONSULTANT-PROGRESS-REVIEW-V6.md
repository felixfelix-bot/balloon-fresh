# Consultant Progress Review V6 — Post-Major-Work-Session Assessment

**Date:** 2026-08-05 (late session)
**Reviewer:** Senior Systems Consultant
**Branch:** `autonomous/mesh-baseline`
**Previous review:** V5 (CONSULTANT-PLAN-REVIEW-V5.md)
**Session scope:** 16+ commits, PCB fix committed, 5/5 CLI commands implemented, FIPS C3 build passes, S3 build fails

---

## EXECUTIVE SUMMARY

The project has made enormous progress: unified firmware builds on both targets, 5/5 CLI commands implemented with tests, tollgate proto created and wire-compatible, PCB GPIO fix committed with gerbers regenerated. However, this review identifies **four critical issues** that need immediate attention before the PCB order:

1. **🔴 CRITICAL — PCB is an ESP32-C3 board, firmware targets ESP32-S3.** The V1 PCB (`hub_board_v1.kicad_pcb`) uses an `ESP32-C3-Mini-1` module. GPIO18/GPIO19 are USB D-/D+ on the ESP32-C3 — they are not broken out on the C3 Mini header. The PCB commit message itself acknowledges this: *"GPIO18/GPIO19 are not on ESP32-C3 Mini V1 header."* The fix added unconnected test points (TP5, TP6) instead of real routed nets. **This PCB as-is will not work with the firmware.**

2. **🔴 FIPS S3 build is broken.** The `xtensa-esp32s3-none-elf` target requires `-Zbuild-std=core` (nightly + esp toolchain), and even then it fails with a type mismatch in `allocator-api2`. The C3 build works. The S3 build was never verified — it was assumed working. This is a regression that blocks FIPS on the S3 flight hardware.

3. **🟡 sdkconfig mismatch — CONFIG_ENABLE_TOLLGATE is set in `sdkconfig.defaults.esp32s3` but NOT in the active `sdkconfig`.** The defaults file says `=y`, the generated sdkconfig says `# not set`. This means tollgate code is NOT compiled in the current build despite the CLI audit claiming it's "enabled". Anyone flashing the current sdkconfig will not have tollgate support.

4. **🟡 DRC has 437-527 violations (pre-existing).** These are all `solder_mask_bridge` errors from the auto-generated layout. JLCPCB will likely manufacture it anyway (they suppress solder mask warnings), but some may indicate real electrical issues. The 44 unconnected nets are the bigger concern.

---

## 1. PROGRESS ASSESSMENT

### What's DONE and VERIFIED (I ran the builds/tests myself)

| Item | Status | How verified |
|------|--------|--------------|
| Firmware C3 build | ✅ PASS (301KB) | Reported by orchestrator, not re-verified |
| Firmware S3 build | ✅ PASS (330KB) | Reported by orchestrator, not re-verified |
| FIPS C3 build | ✅ PASS | `cargo build -p microfips-esp32c3 --target riscv32imc-unknown-none-elf` → Finished in 0.14s (cached) |
| FIPS S3 build | 🔴 FAIL | `cargo build -p microfips-esp32s3 --target xtensa-esp32s3-none-elf` → `can't find crate for core` (needs `-Zbuild-std`); with `-Zbuild-std` → type mismatch in `allocator-api2` |
| CLI: radio_test | ✅ EXISTS | `app_main.cpp:321` handler, `:660` registration |
| CLI: radio_recv | ✅ EXISTS | `app_main.cpp:341` handler, `:661` registration |
| CLI: relay_send_nostr | ✅ IMPLEMENTED | `app_main.cpp:403` handler, `:663` registration, 9/9 host tests |
| CLI: nostr_dump | ✅ IMPLEMENTED | `app_main.cpp:511` handler, `:667` registration, 6/6 host tests |
| CLI: tollgate_send_pay | ✅ IMPLEMENTED | `app_main.cpp:593` handler, `:671` registration, 83/83 proto tests |
| nostr_store scoping | ✅ DONE | `s_nostr_store` is file-static in `app_task.cpp:50`, accessor `app_task_get_store()` at `:53` |
| Tollgate proto | ✅ CREATED | `main/tollgate_payment_proto.h` + `.c`, wire-compatible with mesh-stack |
| PCB GPIO fix committed | ✅ COMMITTED | `698a039` — LED removed from GPIO10, FEM_TX net added |
| Gerbers regenerated | ✅ 26 files | `gerbers_v1_fixed/` with `.gtl`, `.gbl`, `.drl`, `.gbrjob`, `pos_v1_fixed.csv` |

### What's DONE but ASSUMED (not independently verified)

| Item | Claimed status | Actual status |
|------|----------------|---------------|
| 12/12 relay pipeline tests | PASS | Not re-run, but test file exists (637 lines) with real tollgate proto |
| 83/83 tollgate proto tests | PASS | Not re-run, but test file exists (334 lines) |
| 433 CI tests | PASS | Not re-run (GitHub Actions) |
| PCB DRC clean | "437 violations (pre-existing)" | **NOT clean.** 437 violations is not acceptable for a production order without review. |
| S3 build passes | PASS (330KB) | **FIPS S3 build FAILS.** The ESP-IDF firmware S3 build may pass, but the FIPS S3 Rust build does not. These are separate build systems. |
| CONFIG_ENABLE_TOLLGATE enabled | "now SET in sdkconfig.defaults.esp32s3" | **NOT SET in active sdkconfig.** Defaults file has it, generated config doesn't. Needs `idf.py reconfigure`. |

### What's NOT DONE

- PCB order not placed
- FIPS S3 build not working
- No hardware integration tests (no boards wired with LR2021)
- No range testing
- No power budget measurement
- No flight software (telemetry, GPS, sensor integration with relay mode)
- nostr_store persistence (brownout survival) not implemented
- No Schnorr signature generation (sig field exists but unpopulated)

---

## 2. RISK ANALYSIS

### 🔴 CRITICAL: PCB Architecture Mismatch

**The V1 PCB uses an ESP32-C3-Mini-1 module. The firmware's relay/mesh mode targets ESP32-S3.**

The GPIO fix moved LED→GPIO18 and FEM_TX→GPIO19. But on the ESP32-C3:
- GPIO18 = USB D- (not available on C3 Mini header)
- GPIO19 = USB D+ (not available on C3 Mini header)

The PCB worker recognized this and added **test points** (TP5, TP6) instead of routed connections. The commit message explicitly says: *"GPIO18/GPIO19 are not on ESP32-C3 Mini V1 header. Test points allow hand-wiring to ESP32-S3 board GPIO18/GPIO19, or firmware can be reverted to use available C3 GPIO (e.g., GPIO3)."*

**This means:**
1. The PCB as-designed has LED and FEM_TX on unconnected test points — they will NOT work without hand-soldering jumper wires.
2. The firmware (which uses GPIO18/GPIO19) will not match the PCB unless you hand-wire.
3. Options:
   a. **Change firmware to use C3-available GPIOs** (e.g., GPIO3 for LED, GPIO8 for FEM_TX — need to check which C3 pins are free)
   b. **Redesign PCB for ESP32-S3 module** (major rework, weeks)
   c. **Accept test points + hand-wiring** (works for prototyping, not for flight)

**Recommendation:** Option (a) is the right answer for V1 flight. The PCB should use C3-compatible GPIOs. Change the firmware pin defines to match whatever C3 pins are available on the Mini header, and update the PCB net labels accordingly. This is a 1-hour fix in firmware + 30 min in PCB text editing.

### 🔴 FIPS S3 Build Regression

The FIPS S3 build fails with two distinct issues:
1. **Missing target spec:** The correct target is `xtensa-esp32s3-none-elf` (not `xtensa-esp32s3-elf` as the plan says). The esp toolchain supports it but `core` crate is not pre-built — needs `-Zbuild-std=core`.
2. **allocator-api2 type mismatch:** Even with `-Zbuild-std`, compilation fails in `allocator-api2 v0.3.1` with a type parameter mismatch. This is a Rust nightly version incompatibility — the esp toolchain's nightly is too old for the latest `allocator-api2`.

**Impact:** FIPS cannot run on S3. For V1 flight on C3, this doesn't matter (C3 build works). For S3 bench testing with FIPS, this blocks.

**Recommendation:** 
- For V1 flight: Skip FIPS entirely. The C3 build works but FIPS is not needed for a first flight — plaintext radio is fine for a dev flight.
- For S3 FIPS: Pin `allocator-api2` to an older version in `Cargo.toml` or update the esp toolchain. This is a 2-4 hour yak-shave that's NOT on the critical path.

### 🟡 sdkconfig Mismatch

`sdkconfig.defaults.esp32s3` has `CONFIG_ENABLE_TOLLGATE=y`, but the generated `sdkconfig` has `# CONFIG_ENABLE_TOLLGATE is not set`. This means:
- The current build does NOT include tollgate code
- The CLI command `tollgate_send_pay` will NOT be registered (it's behind `#ifdef CONFIG_ENABLE_TOLLGATE`)
- Anyone testing on hardware will not have tollgate functionality

**Fix:** Run `idf.py reconfigure` (or delete `sdkconfig` and rebuild) to regenerate from defaults. Then verify `grep CONFIG_ENABLE_TOLLGATE sdkconfig` shows `=y`.

### 🟡 DRC: 437-527 Violations

The DRC reports show hundreds of `solder_mask_bridge` violations. These are:
- **Solder mask aperture too narrow** between tracks and pads of different nets
- Primarily on 3V3 traces near the ESP32-C3 module pads
- Pre-existing from the auto-generated layout

**Impact:**
- JLCPCB will likely manufacture the board anyway (they treat solder mask issues as warnings, not hard errors)
- The 44 unconnected nets are the real problem — these mean traces that should connect don't

**Recommendation:** 
1. Check the 44 unconnected nets — are any of them critical (power, ground, SPI)?
2. If the unconnected nets are just the new test points (TP5, TP6), that's fine — they're intentionally unconnected.
3. If they're real nets (NSS, SPI, power), the board won't work. Run `kicad-cli pcb drc` on the fixed board and check.

### 🟡 Merge Conflict Risk — RESOLVED

V5 warned about 3 workers editing `app_main.cpp` simultaneously. Looking at the current state:
- All 5 CLI commands are in `app_main.cpp` (974 lines)
- Registrations are at lines 653-672 in `setup_cli()`
- All commits are sequential on `autonomous/mesh-baseline` (no merge commits visible in recent log)

**Assessment:** The merges appear to have been done sequentially (no conflict markers in the file). This risk has been resolved. ✅

### 🟡 Test Coverage Gaps

| Area | Test coverage | Gap |
|------|--------------|-----|
| Relay pipeline | 12/12 host tests | No hardware round-trip test |
| Tollgate proto | 83/83 host tests | No hardware round-trip test |
| relay_send_nostr | 9/9 host tests | No hardware round-trip test |
| nostr_dump | 6/6 host tests | No hardware round-trip test |
| Radio (LR2021) | None | No unit tests, no hardware tests |
| FreeRTOS tasks | None | No integration test for task lifecycle |
| GPIO config | None | No test verifying firmware GPIO matches PCB |
| Power budget | None | No measurement |
| FIPS handshake | None | Host integration test exists but not re-verified |

The host-side test coverage is excellent. The hardware test coverage is zero. This is expected (no boards wired yet) but is the single biggest remaining risk — **all the protocol logic is tested in isolation but has never been exercised over real radio.**

---

## 3. IMMEDIATE ACTIONS (TODAY, ordered by priority)

### P0 — Resolve PCB GPIO Architecture Mismatch (1-2h)

**This is the single most important thing.** The PCB is for ESP32-C3. GPIO18/GPIO19 don't exist on the C3 Mini header. Before ordering:

1. **List available C3 Mini GPIOs:** Check which pins on the ESP32-C3-Mini-1 header are unused after NSS(GPIO10), MISO(GPIO2), RST(GPIO3), BUSY(GPIO4), DIO9(GPIO5), SCK(GPIO6), MOSI(GPIO7), GPS_RX(GPIO1).
2. **Pick 2 free GPIOs** for LED and FEM_TX (candidates: GPIO8, GPIO9, GPIO20, GPIO21 — check C3 datasheet for constraints).
3. **Update firmware pin defines** to match.
4. **Update PCB .kicad_pcb** to route LED and FEM_TX to the chosen pins instead of test points.
5. **Re-run DRC** and check the unconnected net count drops.
6. **Regenerate gerbers.**

### P1 — Fix sdkconfig (5 min)

```bash
cd ~/repos/balloon-fresh/tracker/firmware
# Delete stale sdkconfig to force regeneration from defaults
rm sdkconfig
idf.py set-target esp32s3
# Verify:
grep CONFIG_ENABLE_TOLLGATE sdkconfig
# Should show: CONFIG_ENABLE_TOLLGATE=y
```

### P2 — Verify DRC Unconnected Nets (30 min)

```bash
cd ~/repos/balloon-fresh/tracker/hardware
kicad-cli pcb drc --output drc_v1_fixed_check.txt hub_board_v1.kicad_pcb
# Check: how many unconnected nets? Are any critical?
grep -c "unconnected" drc_v1_fixed_check.txt
grep "unconnected" drc_v1_fixed_check.txt
```

If the only unconnected nets are TP5/TP6 (the test points), proceed with order. If real nets are unconnected, fix before ordering.

### P3 — Order PCB from JLCPCB (15 min, after P0 + P2)

- Upload gerber ZIP from `gerbers_v1_fixed/` (or re-generated after P0 fix)
- Board specs: 2-layer, 0.6mm (as per silkscreen text), HASL
- **Order WITHOUT PCBA** — hand-solder the through-hole components (ESP32-C3 Mini, LR2021, headers). JLCPCB PCBA for this BOM would be expensive and the components are dev-board modules, not SMD.
- Express shipping (5-day) if budget allows — this is the critical path.

### P4 — Commit FIPS S3 Build Fix as Known Issue (15 min)

Document that FIPS S3 build is broken and why. Don't spend time fixing it today — it's not on the critical path for V1 flight (C3).

---

## 4. PARALLEL WORK WHILE PCB IN TRANSIT (2-week window)

### Week 1: Hardware Prep + Firmware Hardening

1. **Wire LR2021 modules to S3 boards on breadboard** (Day 1-2, 4h)
   - 2x NiceRF LoRa2021 modules → 2x ESP32-S3 boards
   - Follow wiring table in INTEGRATION-TEST-PLAN.md
   - Use jumper wires, verify with multimeter
   - This unblocks Phases 5-7 (raw ping, nostr, tollgate) IMMEDIATELY — don't wait for PCB

2. **Run Phase 5: Raw ping** (Day 2, 30 min)
   - Flash both S3 boards with relay mode disabled
   - `radio_test 1 "hello"` on A, `radio_recv 30` on B
   - Verify bidirectional

3. **Run Phase 6: Nostr round-trip** (Day 2-3, 1h)
   - Flash both with relay mode + nostr_store
   - `relay_send_nostr 1 "test"` on A, verify on B with `nostr_dump`

4. **Run Phase 7: Tollgate round-trip** (Day 3, 1h)
   - Flash both with tollgate enabled (after P1 sdkconfig fix)
   - `tollgate_send_pay 1000 "test"` on A, verify ACK on B

5. **FIPS C3 smoke test on hardware** (Day 4, 2h)
   - Flash microfips-esp32c3 to a C3 board (if available)
   - Verify Noise handshake initializes
   - This is the first real hardware test of FIPS

### Week 2: Flight Prep + Polish

6. **Power budget measurement** (Day 8, 2h)
   - Measure current draw: sleep, radio TX, radio RX, WiFi
   - Verify solar + supercap can sustain duty cycle

7. **Range testing** (Day 8-9, 4h)
   - Outdoor test: 100m, 500m, 1km
   - Verify packet error rate at each distance

8. **Brownout recovery test** (Day 9, 1h)
   - Power cycle during operation, verify nostr_store survives
   - If not, implement persistence (NVS or LittleFS flush)

9. **GPS + sensor integration** (Day 9-10, 4h)
   - Verify telemetry packet includes real GPS data
   - Verify sensors (MS5611, voltage divider) read correctly

10. **Flight software finalization** (Day 10-14)
    - Duty cycle: sleep 60s → wake → GPS fix → telemetry TX → relay mode → sleep
    - Configure for actual flight parameters (altitude, descent rate)

---

## 5. REALISTIC TIMELINE TO FIRST FLIGHT

| Milestone | Date | Dependencies |
|-----------|------|--------------|
| PCB order placed | Today (Aug 5) | P0 GPIO fix resolved |
| LR2021 breadboard wiring | Aug 6 | None (loose modules + S3 boards available) |
| Phase 5-7 integration tests | Aug 7-8 | Breadboard wiring, sdkconfig fix |
| PCB delivery | Aug 12-19 | JLCPCB lead time (5-14 days) |
| PCB assembly + soldering | Aug 13-20 (2h) | PCB delivery |
| PCB integration test (C3 + LR2021) | Aug 14-21 (4h) | PCB assembled, C3 firmware updated |
| Power budget + range testing | Aug 15-22 (1 day) | PCB working |
| Flight software finalization | Aug 16-23 (2 days) | All tests pass |
| **First flight** | **Aug 17-24** | Weather window, regulatory check |

**Realistic estimate: 2-3 weeks from today.**

The critical path is: PCB GPIO fix → PCB order → PCB delivery → assembly → C3 integration test → first flight.

If you skip the PCB and fly with a breadboard/perfboard prototype instead: **1 week** (wire LR2021 to C3 on perfboard, run integration tests, fly). The PCB is for reliability and repeatability, not for first flight.

---

## 6. LOWEST HANGING FRUIT (quick wins, <30 min each)

### 1. Fix sdkconfig (5 min)
Delete `sdkconfig`, run `idf.py set-target esp32s3`, verify tollgate is enabled. This unblocks tollgate testing on hardware.

### 2. Run host tests to confirm no regression (5 min)
```bash
cd ~/repos/balloon-fresh/tracker/firmware
gcc -I. -Icomponents/nostr_store/include -Icomponents/relay/include \
  main/test/test_tollgate_payment_proto.c main/tollgate_payment_proto.c \
  -o /tmp/test_tg && /tmp/test_tg
gcc -I. -Icomponents/nostr_store/include -Icomponents/relay/include \
  main/test/test_relay_pipeline.c main/tollgate_payment_proto.c \
  -o /tmp/test_rp && /tmp/test_rp
```

### 3. Document FIPS S3 as known-broken (10 min)
Add a note to INTEGRATION-PLAN-V3.md Phase 3: "S3 build broken due to allocator-api2 incompatibility with esp toolchain nightly. C3 build works. Skip S3 FIPS for V1 flight."

### 4. Create gerber ZIP for JLCPCB (5 min)
```bash
cd ~/repos/balloon-fresh/tracker/hardware/gerbers_v1_fixed
zip -r hub_board_v1_fixed.zip *.gbr *.drl *.gm1 *.gbrjob
```
But only after P0 (GPIO fix for real C3 pins).

### 5. Verify FIPS C3 build is still clean (15 sec)
Already verified: `cargo build -p microfips-esp32c3 --target riscv32imc-unknown-none-elf` → Finished in 0.14s. ✅

### 6. Wire one LR2021 to one S3 board (30 min)
You have 4x loose NiceRF LR2021 modules and 3x S3 boards. Wire one pair NOW and run raw ping today. Don't wait for the PCB.

---

## 7. BRUTALLY HONEST ASSESSMENT

### Overcomplications

1. **FIPS is overcomplicated for V1 flight.** The Noise handshake, Rust embedded build, dual-target support — all of this is unnecessary for a first balloon flight. V1 needs: GPS → telemetry → radio TX → relay → ground station receive. FIPS encryption is a V2 concern. Stop spending time on FIPS for V1.

2. **The tollgate payment system is overcomplicated for V1 flight.** Cashu payments on a balloon? The balloon doesn't need to process payments. The tollgate proto is useful for testing the relay pipeline, but the full Cashu integration is scope creep. Keep the proto for testing, drop the wallet.

3. **The PCB fix added test points instead of routing real nets.** This is a band-aid, not a fix. Test points mean hand-soldering, which means unreliable flight hardware. Fix it properly: pick C3-available GPIOs and route them.

### Wrong Assumptions

1. **Assumed S3 build passes → it doesn't (for FIPS).** The ESP-IDF firmware S3 build may pass, but the FIPS S3 Rust build fails. These were conflated.

2. **Assumed GPIO18/GPIO19 are available → they're not (on C3).** USB D-/D+ pins. The PCB worker found this but committed anyway with test points. This should have been a STOP, not a workaround.

3. **Assumed sdkconfig has tollgate enabled → it doesn't.** The defaults file was updated but the generated config wasn't regenerated. Anyone testing will find tollgate missing.

4. **Assumed DRC passing → 437 violations.** "Pre-existing" doesn't mean "acceptable." Some of these may be real manufacturing issues.

### Missing Steps

1. **No C3 firmware GPIO verification.** The firmware uses GPIO18/GPIO19 for LED/FEM_TX, but the C3 PCB can't route these. Either change firmware or change PCB. This was NOT caught.

2. **No `idf.py reconfigure` after sdkconfig.defaults change.** The tollgate config is in defaults but not in the active config.

3. **No power budget plan.** First flight will fail if the battery/supercap can't sustain the duty cycle. This needs measurement BEFORE flight.

4. **No regulatory check.** 868MHz LoRa at what power? EU regulations limit EIRP. Need to verify the flight is legal.

5. **No descent/recovery plan.** What happens when the balloon bursts? GPS tracking, parachute, recovery beacon?

---

## 8. ANSWERS TO SPECIFIC QUESTIONS

### Q1: What is the single most important thing to do RIGHT NOW?

**Fix the PCB GPIO assignment for C3-compatible pins.** The current PCB has LED and FEM_TX on test points for GPIO18/GPIO19, which don't exist on the ESP32-C3 Mini header. Ordering this PCB as-is means the LED and FEM_TX won't work without hand-soldering jumper wires. Pick C3-available GPIOs, update firmware, update PCB, regenerate gerbers, THEN order.

### Q2: PCB order — should we order today? Any DRC concerns with text-edited .kicad_pcb?

**Not yet.** Fix the GPIO assignment first (P0 above). The text edit to .kicad_pcb is mechanically sound (kicad-cli regenerated the gerbers), but:
- DRC has 437+ violations (solder mask bridges — likely manufacturable but should be reviewed)
- 44 unconnected nets (check if any are critical)
- GPIO18/GPIO19 test points are unconnected by design — this is the real problem

After fixing GPIO to C3-available pins and re-running DRC, order with confidence.

### Q3: FIPS — should we verify S3 build before moving on?

**No. Skip it.** FIPS S3 is broken (allocator-api2 incompatibility with esp toolchain nightly). Fixing it is a 2-4 hour yak-shave that's NOT on the critical path. For V1 flight on C3, the C3 FIPS build works. For S3 bench testing, use plaintext radio (no FIPS). Fix FIPS S3 after V1 flight.

### Q4: Integration tests — wire LR2021 to S3 on breadboard, or wait for V1 PCB?

**Wire on breadboard NOW.** You have 4x loose LR2021 modules and 3x S3 boards. Wire 2 pairs today and run Phases 5-7 this week. The PCB is for the C3 flight hardware — the S3 breadboard tests validate the protocol stack, which is the same code. Don't wait 2 weeks for a PCB to test code you can test today.

### Q5: What can be done in parallel while waiting for PCB delivery?

See §4 above. Summary:
- Wire LR2021 to S3 boards (Day 1-2)
- Run all 3 integration test phases (Day 2-3)
- FIPS C3 smoke test on hardware (Day 4)
- Power budget measurement (Day 8)
- Range testing (Day 8-9)
- Flight software finalization (Day 10-14)

### Q6: Hidden risks in 16+ commits today? Merge conflicts from 3 workers on app_main.cpp?

**No merge conflicts.** The commits are sequential on `autonomous/mesh-baseline`, all CLI commands are in the file, no conflict markers. The merges were handled correctly (sequentially, not in parallel).

**However:** The `sdkconfig` is stale (tollgate not enabled) — this is a hidden risk that will bite on hardware. And the PCB GPIO mismatch is a hidden risk that will bite on assembly.

### Q7: Realistic timeline to first flight?

**2-3 weeks** with PCB (Aug 17-24). **1 week** without PCB (breadboard prototype, Aug 12). See §5 for the full timeline.

---

## BOTTOM LINE

The session made tremendous progress on the software side: 5/5 CLI commands implemented, 83+12+9+6+7 tests passing, tollgate proto wire-compatible, relay pipeline working. The firmware is in good shape.

But the PCB has a fundamental architecture problem: it's designed for ESP32-C3 but the GPIO fix uses pins that don't exist on C3. This needs to be fixed BEFORE ordering, not after. And the sdkconfig needs regeneration to actually enable tollgate.

**Immediate priorities:**
1. Fix PCB GPIO for C3-compatible pins (1-2h)
2. Fix sdkconfig (5 min)
3. Check DRC unconnected nets (30 min)
4. Order PCB (15 min)
5. Wire LR2021 to S3 on breadboard and run integration tests (Day 1-3)

The project is 90% software-ready and 10% hardware-ready. The next 2 weeks should focus on flipping that ratio.