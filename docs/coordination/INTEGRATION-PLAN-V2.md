# Integration Plan V2: First Unified Balloon Firmware Image

**Date:** 2026-08-05 (revised after consultant review V2)
**Branch:** `integration/first-unified-image`
**Predecessor:** INTEGRATION-PLAN-FIRST-UNIFIED-IMAGE.md (V1, superseded)
**Consultant review:** CONSULTANT-PLAN-REVIEW-V2.md

---

## WHAT CHANGED FROM V1

Consultant found 3 critical issues in V1:
1. GPIO10 collision (LED + LR2021 NSS on same pin) — causes radio corruption
2. No RX event loop — firmware is TX-sleep, can't relay without FreeRTOS tasks
3. Smoke build should be FIRST, not last — highest information value

V2 reverses the sequence: link everything first, prove radio second, protocols last.

---

## GOAL

Two ESP32-C3 boards running one unified firmware. Board A sends a Nostr event
over LoRa. Board B verifies the Schnorr signature, stores it, and ACKs a
TollGate payment. First time all 9 components run together.

---

## REVISED PHASES

### Phase 0: SMOKE (Day 1, 3h)

**0.1 — Fix GPIO10 collision** [5 min]
- Move LED from GPIO10 to GPIO18 (or remove blink_led for flight)
- Fix in app_main.cpp:70
- Also fix GPS/FEM GPIO1 collision (Kconfig defaults)

**0.2 — Smoke build: link all components** [2-3h]
- Add secp256k1, tollgate_core, ehash_relay to tracker CMakeLists.txt
- Enable CONFIG_ENABLE_MESH=y, CONFIG_ENABLE_NOSTR_STORE=y
- Goal: does it COMPILE? Does it LINK? Any duplicate symbols?
- Flash to board → does it boot? Free heap?
- This answers the #1 integration risk question

**0.3 — CI for 210 host-side tests** [2h]
- GitHub Actions workflow
- Run gcc-compiled unit tests: nostr_store, tollgate, e-hash, stratorelay, FIPS
- Highest-ROI work in the project — protects against regressions during integration

### Phase 1: ARCHITECTURE (Day 1-2, 4h)

**1.1 — FreeRTOS task design** [2h design + 2h impl]
- radio_task (HIGH priority, 4KB stack): IRQ-driven RX, TX dispatch queue
- app_task (MEDIUM priority, 8KB stack): event processing, secp verify, store
- main_task (MEDIUM priority, 8KB stack): telemetry, sensors, CLI
- Replace TX-sleep main loop with continuous-run
- Log free heap every 10s
- Flash → verify continuous operation, no panics, stable heap

**1.2 — Schnorr verify stack measurement**
- Call uxTaskGetStackHighWaterMark() before/after secp verify
- If close to 16KB limit, move verify to dedicated task with larger stack

### Phase 2: RAW PING (Day 2, 2h)

**2.1 — Two-board raw byte ping** [ZERO new code]
- Board A: `radio_test` CLI command (TX)
- Board B: `radio_recv` CLI command (RX, 30s listen)
- Verify: board B sees board A's packet
- This is the first board-to-board integration test EVER
- Uses existing CLI commands in the 227KB mesh-enabled binary

### Phase 3: NOSTR ROUND-TRIP (Day 3, 4h)

**3.1 — Nostr event over LoRa**
- Board A: serialize Nostr event → send_packet
- Board B: receive → secp256k1_schnorrsig_verify → nostr_store_add
- Verify: event appears in board B's store
- Proves the core store-and-forward use case

### Phase 4: TOLLGATE ROUND-TRIP (Day 3-4, 3h)

**4.1 — Payment over radio**
- Board A: tollgate PAY encode → send_packet
- Board B: receive → tollgate decode → ACK encode → send
- Verify: board A receives ACK
- Proves payment relay use case

### Phase 5: POLISH (Day 5+, deferred items)

- nostr_store index persistence (brownout survival)
- FIPS Noise handshake wrapping transport
- E-hash relay (skip for V1 — balloon never hashes)
- StratoRelay multi-hop (3+ boards)
- Outdoor range testing
- Power budget measurement
- One binary, runtime config flag (CONFIG_NODE_ROLE_BALLOON/GROUND)

### Phase 6: HARDWARE COMPARISON (coming days)

- **Logic analyzer: C3 vs RP2040 SPI timing for LR2021**
  - RP2040 baseline exists: 10.4MHz SCK, 18.3% bus duty, 1754 kbps
  - C3: NO data yet. Need identical capture methodology.
  - Capture script exists: scripts/capture_spi_timing.sh
  - Wiring docs exist: docs/la-wiring-guide.md, docs/logic-analyzer-wiring-diagram.png
  - Key question: does C3 SPI bus duty cycle match RP2040's 18.3%?
  - Bottleneck likely radio physics (air time), not MCU — but confirm with data
  - This determines: C3 as relay MCU vs RP2040+C3 dual-MCU architecture
- **Cross-platform firmware**: binary runs on both C3 and S3 (in progress)

---

## PARALLEL WORK (can start immediately)

- **Order V1 PCB** — Felix action. Gerbers ready, fix GPIO10 in schematic first. 2-week lead time = hardware critical path.
- **FIPS per-member build fix** — `cargo test -p microfips-esp32c3`. Independent.

---

## SUCCESS CRITERIA

1. [ ] All 9 components linked in one binary, boots on C3
2. [ ] FreeRTOS tasks running: radio_task, app_task, main_task
3. [ ] Free heap > 150KB with all tasks running
4. [ ] Two boards exchange raw bytes over LoRa
5. [ ] Nostr event: board A → board B (verified sig, stored)
6. [ ] TollGate PAY: board A → board B → ACK back to A
7. [ ] CI running on GitHub Actions (210 tests)

---

## KEY DECISIONS LOCKED (from consultant review)

| Decision | Answer | Rationale |
|----------|--------|-----------|
| FIPS in first image? | DEFER | Plaintext first, wrap transport later |
| One firmware or two? | ONE binary, runtime config | 63% flash free, simpler CI |
| E-hash in V1? | SKIP | Balloon never hashes. Raw LoRa suffices. |
| Dual-band TDMA? | DEFER | Use one band (sub-GHz for range) for V1 |
| CI now? | YES | Protect 210 tests during integration |
| PCB order? | NOW | 2-week lead time is critical path |
| secp verify as hard gate? | NO | Parameter, not gate. Verify at transport layer. |
