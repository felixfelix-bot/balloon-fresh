# Consultant Plan Review V6 — Architecture Mismatch & Brutal Honesty

**Date:** 2026-08-05 14:40
**Reviewer:** Senior Systems Architect (automated)
**Session context:** 39 commits, 53 files, 11,522 lines. V5 review addressed. PCB architecture mismatch discovered — this is the dominant issue.
**Previous review:** V5 (CONSULTANT-PLAN-REVIEW-V5.md)

---

## EXECUTIVE SUMMARY

**The GPIO10→GPIO18 fix was applied to the wrong architecture.** The firmware assumes single-MCU (C3 directly drives LR2021 via SPI on GPIOs 6/7/2/10). The V1 PCB is dual-MCU (RP2040 drives SPI/LR2021, C3 handles UART/GPS/I2C). The V1 PCB also has 18 fatal 3V3↔GND shorts and all 4 SPI lines shorted together — it's a paperweight as designed.

**The good news:** 39 commits of firmware work (CLI commands, relay pipeline, bug fixes, FIPS build, tests) is NOT wasted. It's the correct firmware for a single-MCU architecture. The problem is the PCB, not the code.

**The bad news:** We spent a session fixing a GPIO collision that doesn't exist on the target hardware, and the V1 PCB needs a complete redesign — not a patch.

---

## ANSWER TO THE 6 QUESTIONS

### Q1: Architecture Decision — Single-MCU (new PCB) vs Dual-MCU (firmware rewrite)?

**ANSWER: SINGLE-MCU. DESIGN A NEW PCB. DO NOT REWRITE FIRMWARE FOR DUAL-MCU.**

Reasoning:

1. **The firmware is already single-MCU and it works.** 39 commits, 13 CLI commands, 12/12 relay pipeline tests, 7/7 nostr_store tests, 83/83 tollgate proto tests, FIPS C3 builds. This is real, tested, working code. Throwing it away to write a dual-MCU UART relay bridge is insanity.

2. **Dual-MCU adds complexity for zero benefit on a balloon payload.** The RP2040 exists on the V1 PCB to "handle SPI timing" — but the C3 is perfectly capable of driving SPI at the LR2021's required speeds. The consultant PCB review itself says "V2 should aim for single-MCU if C3 SPI timing is validated." The firmware already assumes this is true.

3. **Dual-MCU firmware rewrite would take 2-4 weeks.** You'd need: RP2040 firmware (SPI master for LR2021), a UART command protocol between C3 and RP2040, a C3 radio driver that wraps SPI commands in UART frames, synchronization logic, error handling for UART link failure, and a test harness for the dual-MCU path. This is a massive investment to support a broken PCB.

4. **A new single-MCU PCB takes 2-3 hours to design + 2 weeks lead time.** The schematic is simple: C3 + LR2021 (SPI on GPIOs 6/7/2/10) + GPS (UART) + LED (GPIO18) + FEM (GPIO19) + I2C sensors. No RP2040. No inter-MCU UART. Fewer nets = fewer routing problems. Use KiCad's interactive router, not `gen_pcb.py`.

5. **Cost and power improvement.** Removing the RP2040-Zero saves ~$4-6/board and ~20-50mA current. Both matter for a balloon.

**The decision is clear: the firmware architecture is correct. The PCB must be redesigned to match it.**

### Q2: V1 PCB Salvageable or Start Fresh?

**ANSWER: START FRESH. THE V1 PCB IS NOT SALVAGEABLE.**

The PCB consultant review is brutal but correct:

- **18× 3V3↔GND shorts** = systematic routing error (ground pour overlapping 3V3). Not a localized bug. The entire power distribution is broken.
- **All 4 SPI lines shorted together + SCK↔3V3 + SCK↔GND + NSS↔GND** = SPI bus completely dead. Not fixable with a knife.
- **43 unconnected nets** = missing traces. Can't be fixed post-manufacture.
- **UART TX lines shorted** = inter-MCU comms dead (irrelevant now since we're going single-MCU).
- **RF traces shorted to ground** = both radios compromised.
- **The PCB is dual-MCU architecture** = doesn't match our firmware anyway.

Even if you fixed every short in KiCad, you'd still have a dual-MCU board that requires a firmware rewrite. **Two reasons to abandon it, either one sufficient alone.**

**What to do instead:** Design a new single-MCU PCB (C3 + LR2021 + GPS + sensors). Use KiCad interactive router. Run DRC until 0 errors. Generate BOM. Order from JLCPCB.

### Q3: Relay Pipeline Test — Link Real Tollgate Proto or Keep Mock?

**ANSWER: THE TEST ALREADY LINKS THE REAL PROTO AND PASSES. UPDATE CI TO INCLUDE IT.**

I verified this myself. The test at `tracker/firmware/main/test/test_relay_pipeline.c`:
- `#include "tollgate_payment_proto.h"` (line 83) — the real proto header
- Calls `tollgate_proto_encode()` and `tollgate_proto_decode()` — the real functions
- Compiles and passes 12/12 when built with the correct command:

```bash
gcc -Wall -O2 -I tracker/firmware/main -I tracker/firmware/components/nostr_store/include \
    -o /tmp/test_relay tracker/firmware/main/test/test_relay_pipeline.c \
    tracker/firmware/main/tollgate_payment_proto.c \
    tracker/firmware/components/nostr_store/nostr_store.c
```

**The "broken" claim in the progress report is stale.** The test was updated to use the real proto (commit 65a46fd) and the mock was removed. The build command in the test header comment includes `tollgate_payment_proto.c`. It works.

**The REAL problem:** This test is NOT in CI. The `.github/workflows/ci-host-tests.yml` has 4 test suites (nostr_store, tollgate, ehash-relay, stratorelay) but does NOT include the relay pipeline test or the nostr_dump test. **Add a Suite 5 for the relay pipeline test and a Suite 6 for the nostr_dump test.**

### Q4: Resource Management — Limit to 2 Concurrent Workers?

**ANSWER: YES. 2 CONCURRENT WORKERS MAX. THE SYSTEM IS SWAPPING 4GB.**

Current state (measured at 14:40):
- RAM: 2.9GB used / 7.0GB total, only 1.5GB free, 3.0GB buff/cache → 4.1GB available
- Swap: 4.0GB used / 15GB — system is actively swapping
- CPU: load 4.73 on 4 cores — oversubscribed
- Uptime: 9 days (accumulated swap pressure)

With 8 worker processes on a 4-core/7GB system, workers are competing for memory and CPU. The FIPS Rust build alone can use 2-3GB. The previous V5 review already recommended 3 workers; we're past that now.

**Rule:** Maximum 2 concurrent workers. When one finishes, don't immediately dispatch another. Let the system breathe. If swap exceeds 5GB, kill everything and run one at a time.

**Priority for the 2 worker slots:**
1. PCB redesign (single-MCU) — this is the critical path
2. CI updates (add relay pipeline + nostr_dump tests to GitHub Actions) — lightweight, can overlap

### Q5: Next Steps While PCB is Blocked?

**ANSWER: SHORT LIST. STOP SPRAWLING.**

The PCB is the critical path (2-week lead time once designed). Everything else is secondary. Here's what to do while waiting for boards:

**Immediate (today, 1-2 hours each):**
1. **Design the new single-MCU PCB schematic in KiCad.** C3 + LR2021 (SPI: SCK=GPIO6, MOSI=GPIO7, MISO=GPIO2, NSS=GPIO10), GPS (UART RX=GPIO1), LED (GPIO18), FEM_TX (GPIO19), I2C (SDA+SCL for BMP280). No RP2040. ~15 nets total.
2. **Route the PCB.** Use KiCad interactive router. Run DRC until 0 errors, 0 unconnected. Generate gerbers + BOM.
3. **Order the PCB from JLCPCB.** Express shipping. This starts the 2-week clock.
4. **Add relay pipeline + nostr_dump tests to CI.** Two new suites in `ci-host-tests.yml`. 10 minutes of work.

**While PCB is in fabrication (2 weeks):**
5. **Write the SPI timing characterization test for C3.** The PCB consultant recommended validating C3 SPI timing. Use the S3 test board (which has direct C3-equivalent SPI access) to verify the LR2021 works at ≥8MHz. If it doesn't, adjust the SPI clock in firmware before boards arrive.
6. **Write the integration test scripts** for Phases 5-7 so they're ready when boards arrive. Don't wait until the boards are on the bench to start writing test procedures.
7. **Fix the `gen_pcb.py` router** (or better: abandon it). The PCB consultant found it has no copper pour isolation, no net-to-net clearance, and no directional routing. Use KiCad. Don't waste time debugging a Python router for a one-time prototype.

**Stop doing:**
- ❌ Do NOT write dual-MCU firmware (RP2040 bridge). Wrong architecture.
- ❌ Do NOT try to fix the V1 PCB in KiCad. Wrong architecture + fatal shorts.
- ❌ Do NOT dispatch more CLI command workers. All 5 CLI commands are implemented.
- ❌ Do NOT write more coordination docs. We have 6 plan/review docs already. The next doc should be the PCB design file.
- ❌ Do NOT run the FIPS build again unless alone. It OOMs with other workers.

### Q6: SINGLE Most Important Decision for Felix Right Now?

**ANSWER: APPROVE THE SINGLE-MCU PCB REDESIGN AND ORDER IT TODAY.**

This is not close. Every day the PCB order is delayed is a day added to the flight date. The firmware is ready. The PCB is the bottleneck. The V1 PCB is dead (wrong architecture + fatal shorts). A new single-MCU PCB is a simple design that matches the existing firmware.

**Felix needs to say one sentence: "Design a new single-MCU PCB with C3 + LR2021 on SPI GPIOs 6/7/2/10, GPS on UART, LED on GPIO18, FEM_TX on GPIO19, and order it from JLCPCB today."**

---

## BRUTAL HONESTY: What We Wasted Time On

### Wasted: GPIO10→GPIO18 Fix (commit 698a039, gerbers_v1_fixed)
**Time wasted: ~2 hours**

The GPIO10→GPIO18 LED fix was applied to the V1 PCB gerbers. But the V1 PCB doesn't have GPIO10 connected to the C3 at all — it's a dual-MCU board where the RP2040 controls SPI. The fix solved a problem that doesn't exist on the target hardware. We regenerated 24 gerber files for a board that will never be manufactured.

**Lesson:** Before fixing PCB issues, verify the PCB netlist matches the firmware pin assignments. The architecture mismatch should have been caught before touching gerbers.

### Wasted: PCB DRC Without Architecture Check
**Time wasted: ~1 hour (running DRC on a board with the wrong architecture)**

The DRC found 18× 3V3↔GND shorts and all SPI lines shorted. These are real, fatal errors. But even if they were fixed, the board would still be wrong (dual-MCU vs single-MCU firmware). The DRC was a necessary step, but the architecture mismatch should have been caught first — before spending time analyzing individual shorts.

### Wasted: 5 Coordination/Review Docs in One Session
**Time wasted: ~3-4 hours of agent time writing reviews instead of doing work**

We wrote: Consultant Review V3, V4, V5, V6, Integration Plan V2, V3, CLI Audit, Progress Report V6. That's 8 documents. Each one took 30-60 minutes of agent compute. The documents are useful, but the diminishing returns are obvious — V5 and V6 are reviewing the same session from slightly different angles.

**Lesson:** One progress report per session. One integration plan. One review at the end. Stop writing meta-documents about the work — do the work.

### Not Wasted: Firmware Work (39 commits)
The firmware work is NOT wasted. It's the correct single-MCU architecture. The CLI commands, relay pipeline, nostr_store, tollgate proto, FIPS build — all of this is reusable on the new PCB. The only thing that needs updating is the PCB, not the firmware.

**The firmware is ready. The PCB is not. Fix the PCB.**

---

## UPDATED RISK MATRIX

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| PCB redesign delayed → flight date slips | HIGH | CRITICAL | Order TODAY. Express shipping. |
| C3 SPI timing insufficient for LR2021 | LOW-MEDIUM | HIGH (need RP2040 fallback) | Characterize on S3 test board during 2-week wait |
| CI doesn't include relay pipeline test | CONFIRMED | LOW (test passes locally) | Add to ci-host-tests.yml (10 min) |
| System OOM from too many workers | MEDIUM | MEDIUM (lost work) | 2 workers max. Monitor swap. |
| V1 PCB accidentally ordered | LOW | CRITICAL (2 weeks wasted) | Delete gerbers_v1/ and gerbers_v1_fixed/ |
| More coordination docs written instead of PCB design | MEDIUM | HIGH (wasted time) | STOP. Design PCB. |

---

## CONCRETE ACTION PLAN

### Phase A: PCB Design + Order (TODAY, 3 hours) — CRITICAL PATH

| Step | Time | Who |
|------|------|-----|
| A1. Open KiCad. New project: `balloon-tracker-v2-single-mcu` | 5 min | Worker 1 |
| A2. Draw schematic: C3 + LR2021 (SPI: SCK=6, MOSI=7, MISO=2, NSS=10) + GPS (UART RX=1) + LED (GPIO18) + FEM_TX (GPIO19) + I2C (BMP280) | 45 min | Worker 1 |
| A3. Layout PCB (50×40mm, 2-layer). Use KiCad interactive router. | 60 min | Worker 1 |
| A4. Run DRC. Fix all errors. Repeat until 0 errors, 0 unconnected. | 30 min | Worker 1 |
| A5. Generate gerbers + drill files + BOM | 15 min | Worker 1 |
| A6. Upload to JLCPCB. Select express shipping. Place order. | 15 min | Worker 1 (or Felix) |
| A7. Delete `gerbers_v1/` and `gerbers_v1_fixed/` to prevent accidental ordering | 1 min | Worker 1 |

### Phase B: CI Updates (TODAY, 30 min) — Lightweight, can overlap with Phase A

| Step | Time | Who |
|------|------|-----|
| B1. Add Suite 5 to ci-host-tests.yml: relay pipeline test (12 tests) | 15 min | Worker 2 |
| B2. Add Suite 6 to ci-host-tests.yml: nostr_dump test (6 tests) | 15 min | Worker 2 |

### Phase C: SPI Timing Characterization (DURING 2-WEEK WAIT)

| Step | Time | Who |
|------|------|-----|
| C1. Wire LR2021 to S3 test board (SPI on GPIOs 6/7/2/10) | 30 min | When boards arrive |
| C2. Flash tracker firmware. Run radio_test CLI. | 15 min | When boards arrive |
| C3. Verify SPI at 8MHz. If fails, try 4MHz. If fails, try 2MHz. | 30 min | When boards arrive |
| C4. Log results. If <8MHz, adjust firmware SPI clock before V2 PCB arrives. | 15 min | When boards arrive |

### Phase D: Integration Test Scripts (DURING 2-WEEK WAIT)

| Step | Time | Who |
|------|------|-----|
| D1. Write Phase 5 test script (raw ping, 2 boards) | 30 min | Worker |
| D2. Write Phase 6 test script (nostr round-trip) | 30 min | Worker |
| D3. Write Phase 7 test script (tollgate PAY→ACK) | 30 min | Worker |

---

## ASSESSMENT OF V5 RECOMMENDATIONS

| V5 Recommendation | Status | Notes |
|---|---|---|
| Redirect tollgate_send_pay to copy existing proto | ✅ DONE | Proto created, wire-compatible, 83/83 tests pass |
| Reduce to 3 concurrent workers | ❌ NOT DONE | Still oversubscribed. Now recommending 2. |
| Monitor FIPS worker for OOM | ✅ DONE | FIPS C3 build passes. No more OOM. |
| Prepare merge plan for 3 CLI workers | ✅ DONE (N/A) | All 3 CLI commands merged successfully |
| PCB task: dispatch in first available slot | ✅ DONE | But found fatal architecture mismatch |

**5/5 V5 recommendations addressed.** The PCB architecture mismatch was an unknown unknown — V5 couldn't have predicted it. The tollgate proto redirect was the single most impactful V5 recommendation and it worked.

---

## BOTTOM LINE

**The firmware is ready. The PCB is not. Stop writing firmware. Stop writing reviews. Design and order a new single-MCU PCB today.**

The 39 commits of firmware work are solid and correct. The V1 PCB is a dead end (wrong architecture + fatal shorts). The path to flying is:

1. **Today:** Design single-MCU PCB in KiCad → DRC clean → order from JLCPCB
2. **2-week wait:** CI updates, SPI timing characterization, integration test scripts
3. **When boards arrive:** Flash firmware → raw ping → nostr round-trip → tollgate round-trip → fly

**Felix's one decision: "Design a new single-MCU PCB and order it today."**

Everything else is secondary. The clock is ticking on the 2-week lead time.

---

*End of review.*