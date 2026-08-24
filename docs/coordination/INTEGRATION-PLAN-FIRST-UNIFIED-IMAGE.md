# Integration Plan: First Unified Balloon Firmware Image

**Date:** 2026-08-05
**Author:** Hermes Manager (orchestrator)
**Status:** DRAFT — awaiting consultant review
**Branch:** `integration/first-unified-image`

---

## CONTEXT

We have 9 individually-proven components (210 tests, all passing) that have
never been combined into a single firmware image. Every component fits the
ESP32-C3 budget independently (verified: 63% flash free, 68% RAM free with
all components accounted for). The critical path is now INTEGRATION, not new
development.

This plan describes the sequence to get from "9 separate pieces" to "one
bootable firmware that exercises the full stack on real hardware."

---

## GOAL

A single ESP32-C3 firmware binary that:
1. Boots and runs the tracker (GPS, BMP280, telemetry)
2. Has the LR2021 radio initialized and TX/RX capable
3. Can receive a Nostr event over LoRa, verify its Schnorr signature, store it
4. Can relay a Nostr event to a second board
5. Can process a TollGate PAY message and respond with ACK

All on ONE ESP32-C3, flashed to TWO boards, tested bench-distance.

---

## PHASES (sequential, each gates the next)

### Phase 0: Unblock (Day 1, ~2h total)

**0.1 — FIPS per-member build fix**
- Change: `cargo test --no-run` → `cargo test --no-run -p microfips-esp32c3`
- Verify: FIPS leaf node compiles for C3 target
- Owner: balloon-fips track
- Effort: 1 line

**0.2 — Flash mesh baseline to C3 hardware**
- Flash existing `balloon-tracker.bin` (227KB, mesh-enabled) to a C3 board
- Verify: boots, serial output shows mesh init
- This is the FIRST TIME mesh-enabled firmware runs on actual hardware
- Owner: orchestrator (needs board lock)
- Gate: confirms the build we verified tonight works on real silicon

### Phase 1: nostr_store Flight-Proofing (Day 1-2, ~4h)

**1.1 — Index persistence**
- Write `nostr_store_save_index()` — flushes 256-entry RAM index to `index.bin`
- Write `nostr_store_load_index()` — called during `nostr_store_init()`
- Trigger: save on every 10th insert + on graceful shutdown
- ~100 lines C, reuses existing POSIX file I/O pattern
- Test: store events, reboot simulation (re-init), verify events findable
- Owner: balloon-nostr track

**1.2 — Add secp256k1 verify call to store**
- Before `nostr_store_add()`, call `secp256k1_schnorrsig_verify()`
- Reject unsigned/invalid events (return error code)
- secp256k1 context: create once at init, destroy at shutdown (~2KB heap)
- ~30 lines C
- Test: valid sig accepted, invalid sig rejected
- Owner: balloon-nostr track

### Phase 2: Radio Integration (Day 2-3, ~6h)

**2.1 — E-hash radio wiring**
- Replace `ehash_radio_stub.c` with callbacks to real LR2021 driver
- TX callback: calls `lr2021_send_packet()` (from speed-tests proven code)
- RX callback: triggered by GPIO IRQ, calls `lr2021_read_packet()`
- ~200 lines C glue
- Test: send TEMPLATE message board-to-board, verify reception
- Owner: balloon-pow track

**2.2 — Nostr-over-LoRa transport**
- Define minimal wire format: [1B type][NOSTR_EVENT binary serialized]
- TX: serialize event → ehash TX callback → LR2021
- RX: LR2021 IRQ → deserialize → secp256k1 verify → nostr_store_add
- Reuses: nostr_store serialization (proven 7/7 tests)
- ~150 lines C
- Test: send event from board A, verify stored on board B
- Owner: balloon-nostr + balloon-pow coordination

### Phase 3: TollGate Integration (Day 3-4, ~4h)

**3.1 — TollGate payment over radio**
- Wire `tollgate_payment_proto` encode/decode to the radio path
- PAY message: ground station → balloon (via LoRa)
- ACK message: balloon → ground station (via LoRa)
- 119 encode/decode tests already pass — just connect transport
- ~100 lines C glue
- Test: send PAY from board A, receive ACK from board B
- Owner: balloon-tollgate track

### Phase 4: Integrated Build (Day 4-5, ~6h)

**4.1 — Unified CMakeLists.txt**
- Enable ALL components in one build:
  `CONFIG_ENABLE_MESH=y CONFIG_ENABLE_NOSTR_STORE=y CONFIG_ENABLE_TOLLGATE=y`
- Add secp256k1 component to tracker build
- Add tollgate_balloon component to tracker build
- Resolve any linker conflicts (watch for duplicate symbols)
- Owner: orchestrator

**4.2 — First flash + boot**
- Flash unified binary to board A
- Verify: serial log shows all components initialized
- Expected flash: ~755KB (from budget analysis), well within 2MB partition
- Capture: serial output, free heap, any panics
- Gate: if it boots and inits all components → milestone achieved

**4.3 — Two-board integration test**
- Flash board A (balloon mode) and board B (ground station mode)
- Test sequence:
  1. A sends telemetry event → B receives, verifies sig, stores
  2. B sends PAY message → A receives, responds ACK
  3. A relays stored event to B (store-and-forward)
- Capture: serial logs from both boards
- Evidence: Playwright or terminal capture of full round-trip
- Gate: ONE successful round-trip of each message type

---

## DEPENDENCY GRAPH

```
Phase 0.1 (FIPS fix) ──────────────────────────────┐
Phase 0.2 (flash baseline) ────────────────────────┤
                                                    ▼
Phase 1.1 (index persist) ──┐
Phase 1.2 (secp verify)  ───┤
                             ├──► Phase 2.1 (ehash radio)
                             │         │
                             │         ▼
                             ├──► Phase 2.2 (nostr-over-lora)
                             │         │
                             │         ▼
                             ├──► Phase 3.1 (tollgate radio) ──┐
                             │                                  ▼
                             └─────────────────────────► Phase 4.1 (unified build)
                                                                        │
                                                                        ▼
                                                                 Phase 4.2 (boot test)
                                                                        │
                                                                        ▼
                                                                 Phase 4.3 (2-board test)
```

Phases 0.1, 0.2, 1.1, 1.2 are all independent and can run in parallel.
Phase 2 depends on Phase 1. Phase 3 depends on Phase 2. Phase 4 depends on all.

---

## RISK ANALYSIS

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Flash overflow at link time | LOW (63% free) | HIGH | Budget verified. If overflow, strip MeshCore first (saves 84KB) |
| RAM exhaustion at runtime | LOW (68% free) | HIGH | secp context is transient. Monitor free heap in serial |
| LR2021 SPI conflict (tracker + ehash both use SPI) | MEDIUM | HIGH | Tracker uses dedicated SPI bus. E-hash uses same radio. Investigate bus sharing |
| Build system conflicts (ESP-IDF vs PlatformIO) | MEDIUM | MEDIUM | All C3 components are ESP-IDF. RP2040 is PlatformIO only. Keep separate |
| Two-board test needs correct firmware on each | LOW | LOW | Build two configs: `balloon` and `ground-station` |

---

## SUCCESS CRITERIA

The plan is complete when:

1. [ ] One firmware binary boots on C3 with all components initialized
2. [ ] Serial log shows: GPS lock, BMP280 read, mesh init, nostr_store init, secp context create, LR2021 init
3. [ ] Board A sends a Nostr event over LoRa to board B
4. [ ] Board B verifies the Schnorr signature and stores the event
5. [ ] Board B sends a TollGate PAY message, board A responds with ACK
6. [ ] Free heap after all components running > 150KB
7. [ ] Evidence captured: serial logs + photo/video of setup

---

## WHAT THIS ENABLES

Once the first unified image works:
- **First outdoor walk test** with real mesh firmware (not just raw TX)
- **First FIPS encrypted session** over LoRa between two C3 boards
- **Flight readiness review** — we know the full stack works together
- **Power measurement** — actual current draw of full-stack firmware
- **V1 PCB order** — we know exactly what firmware will run on it

---

## QUESTIONS FOR CONSULTANT

1. **Is Phase 2 (radio integration) the right priority?** We could alternatively
   do TollGate-over-WiFi first (proven S3 code, no LoRa needed), then add LoRa
   later. Pro: faster to "something working." Con: doesn't test the actual
   balloon transport path.

2. **Should we include FIPS encryption in the first integrated image, or defer?**
   FIPS Noise handshake is proven (13/13 tests) but adds complexity. We could
   ship plaintext LoRa first, add encryption as Phase 5.

3. **One firmware or two?** Should the balloon and ground station run the same
   binary with a config flag, or separate builds? Same binary = simpler CI.
   Separate = smaller flash per device.

4. **Should we invest in CI now?** 210 tests exist but none run in CI. Adding
   GitHub Actions for host-side tests would catch regressions during integration.
   Effort: ~2h. Worth it before Phase 4?

5. **When do we order the V1 PCB?** Gerbers are ready. Ordering now means we
   have hardware for flight testing in ~2 weeks. But we haven't validated the
   schematic against the integrated firmware yet.
