# Consultant Review V2 — Integration Plan: First Unified Image

## Brutally Honest Audit of INTEGRATION-PLAN-FIRST-UNIFIED-IMAGE.md

**Reviewed by:** Senior Systems Architecture Consultant
**Date:** 2026-08-05
**Plan under review:** `docs/coordination/INTEGRATION-PLAN-FIRST-UNIFIED-IMAGE.md`
**Context doc:** `docs/coordination/CONSULTANT-PROJECT-REVIEW.md`
**Method:** Every claim verified against actual source code in `tracker/firmware/`, `mesh-stack/`, `firmware/blossom-server/`, and component CMakeLists/Kconfig files.

---

## EXECUTIVE SUMMARY

**The plan is well-organized but architecturally naive.** It treats integration as "add 200 lines of glue code to connect proven components." In reality, the integration faces three problems the plan doesn't mention:

1. **4 of 9 components don't exist in the tracker firmware's build tree.** secp256k1 lives in `firmware/blossom-server/`. TollGate lives in `mesh-stack/tollgate/`. E-hash lives in `mesh-stack/ehash-relay/`. They are not ESP-IDF components in `tracker/firmware/components/`. The plan's "Phase 4: Unified Build" is not "flip config flags" — it's "port three separate codebases into one build system."

2. **The tracker firmware architecture is fundamentally incompatible with continuous mesh relay.** The current `app_main.cpp` is a TX-sleep device: wake → read sensors → TX → deep sleep. When MeshCore is enabled, it enters a blocking `while(true) { mesh.loop(); }` that replaces the sleep path entirely. There is no RX-driven event processing, no concurrent TX/RX, no task separation. A store-and-forward relay balloon needs to be always-on RX. The plan adds nostr_store, secp verify, tollgate, and e-hash without addressing that the firmware has no event loop to receive anything.

3. **GPIO10 is a hardware collision.** The LR2021 SPI chip-select (NSS) and the status LED share GPIO10. `blink_led()` toggles GPIO10 directly, which will corrupt any in-flight SPI transaction. This is a latent bug that will cause mysterious radio failures the moment integration testing starts.

**Verdict: HOLD — redesign before execution.** The plan will produce a firmware that compiles but cannot function as a relay. The architecture needs a FreeRTOS task design and an event-driven RX path before any protocol integration makes sense. However, the individual steps are mostly right — they just need to be re-sequenced and the architecture gap must be addressed first.

---

## 1. IS THE INTEGRATION SEQUENCE CORRECT? (Question 1)

**No. The sequence is backwards and misses the real dependency.**

### The plan's sequence:
```
Phase 0: Unblock → Phase 1: nostr_store polish → Phase 2: radio integration → Phase 3: tollgate → Phase 4: unified build
```

### Why this is wrong:

**Problem A: Highest-risk step is last.** The single highest-risk integration question is: "Can all 9 components coexist in one build?" This is a linking/compilation problem with potential symbol conflicts, header conflicts, and build-system incompatibilities. It should be Step 1, not Step 4. The plan defers it behind 3 phases of component-level work that may be wasted if the unified build fails.

**Problem B: Component-level polish before integration is wasted work.** Phase 1 (index persistence, secp verify wiring) and Phase 2.1 (ehash radio stub replacement) are improvements to individual components. But you don't know which components will actually integrate cleanly. Do the smoke build first, find out what conflicts exist, then prioritize the work that unblocks the real conflicts.

**Problem C: The real Phase 0 is missing.** The plan's Phase 0 (FIPS build fix + flash baseline) is correct but insufficient. The real Phase 0 should be:
- Add ALL 9 components to one CMakeLists.txt
- Compile. Don't wire anything. Just see if it links.
- Flash. See if it boots. Measure free heap.
This takes 2-3 hours and answers the most important question instantly.

**Problem D: The architecture conflict is invisible to the plan.** The plan's Phase 2.2 says "RX: LR2021 IRQ → deserialize → secp256k1 verify → nostr_store_add." But the current firmware has no IRQ handler, no RX task, and no event loop. The main loop either blocks on `mesh.loop()` or enters deep sleep. Before you can wire any RX path, you need a FreeRTOS task architecture. This is unmentioned.

### Corrected sequence:
```
Phase 0: Smoke build (link everything, boot, measure heap)     ← HIGHEST PRIORITY
Phase 1: FreeRTOS task architecture (RX task, app task)        ← BLOCKS ALL RADIO WORK
Phase 2: Two-board raw byte ping (no protocol layers)          ← VALIDATES RADIO PATH
Phase 3: Nostr event round-trip (serialize → radio → verify → store)
Phase 4: TollGate PAY round-trip
Phase 5: Polish (index persistence, FIPS, e-hash, mesh routing)
```

---

## 2. LOWEST-HANGING FRUIT MISSED (Question 2)

### FRUIT-1: The GPIO10 collision [SEVERITY: CRITICAL, EFFORT: 5 min]

**The LED and LR2021 NSS are both on GPIO10.** From `app_main.cpp:70` and `app_main.cpp:76`:
```c
#define LED_GPIO 10       // blink_led() toggles this
#define LR2021_NSS 10     // SPI chip select for the radio
```

`blink_led()` is called on every first boot (line 427). If the radio is mid-transaction, the LED toggle will deassert NSS and corrupt the SPI frame. This will cause intermittent, unreproducible radio failures.

**Fix:** Move the LED to an unused GPIO (GPIO 18 or 19 are typically free on C3-32PIN). Or better: remove blink_led entirely for flight firmware. The LED consumes power and adds weight.

### FRUIT-2: The GPS/FEM pin conflict [SEVERITY: HIGH, EFFORT: 5 min]

From Kconfig.projbuild:
```
config GPS_UART_RX_PIN  default 1    # GPS receive
config FEM_TX_PIN       default 1    # SKY66112 TX enable
```

Both default to GPIO1. You cannot use GPS and the SKY66112 FEM amplifier simultaneously. Since GPS and FEM are both default-off in the current config, this hasn't bitten yet — but the moment someone enables both, the radio amplifier enable pin will fight the GPS UART.

**Fix:** Change FEM_TX_PIN default to GPIO18 or another free pin.

### FRUIT-3: Kconfig dead values [SEVERITY: LOW, EFFORT: 10 min]

The Kconfig defines `RADIO_FREQ_MHZ_X10=8680` (868 MHz LoRa) and `RADIO_SF=9` (spreading factor), but the actual radio init in `app_main.cpp:170` hardcodes FLRC 2440 MHz / 2600 kbps. These Kconfig values are dead — they mislead anyone reading the configuration. If a developer changes `RADIO_FREQ_MHZ_X10` expecting the radio frequency to change, nothing will happen.

**Fix:** Either wire the Kconfig values into `init_radio()`, or remove the dead Kconfig entries. Don't ship misleading configuration.

### FRUIT-4: CI for 210 existing tests [SEVERITY: MEDIUM, EFFORT: 2h]

The plan's own Question #4 asks about this but doesn't include it as a step. Before integration work begins, you need regression protection. Adding GitHub Actions to run the host-side tests (gcc-compiled C unit tests for nostr_store, tollgate, e-hash, stratorelay, FIPS) takes 2 hours and prevents breaking working components during integration.

**This is the single highest-value 2-hour investment in the entire project right now.**

### FRUIT-5: Two-board raw byte ping before any protocol [SEVERITY: HIGH, EFFORT: 2h]

The plan jumps straight from "wire ehash radio stub" to "Nostr event over LoRa." Skip the intermediate protocol layers. The simplest possible integration test is:
- Board A: `s_radio->send_packet("HELLO", 5)` in bench test mode
- Board B: poll for RX, print anything received

If this doesn't work, no protocol layer will work. The `radio_test` and `radio_recv` CLI commands ALREADY DO THIS. You just need two boards running simultaneously — one in TX, one in RX. This can be done TODAY with the existing 227KB binary, no new code needed.

### FRUIT-6: micro_ecc vs secp256k1 redundancy [SEVERITY: MEDIUM, EFFORT: Decision]

The tracker already has `components/micro_ecc/` (micro-ECC library) providing `uECC_secp256k1()`. The plan adds full `libsecp256k1` (69KB) for BIP-340 Schnorr verification. micro_ecc does NOT support Schnorr (only ECDH and ECDSA key generation), so libsecp256k1 is genuinely needed for Schnorr. But you now have TWO elliptic curve libraries on the same curve. Audit for:
- Duplicate static lookup tables (both may embed generator point precomputation)
- Linker symbol conflicts (unlikely but possible)
- Flash waste (if micro_ecc's secp256k1 tables aren't needed, disable that curve in micro_ecc)

**Fix:** After adding libsecp256k1, configure micro_ecc to only include the curves you actually use via micro_ecc (if any). If micro_ecc is only used by FIPS Noise (Curve25519), keep it. If it's vestigial, remove it and save flash.

---

## 3. IMMEDIATELY ACTIONABLE STEPS (Question 3)

Ranked by impact/effort ratio:

### Step 1: Fix GPIO10 collision (5 min)
Move LED to GPIO 18 (or remove entirely). Change in `app_main.cpp:70`.

### Step 2: Smoke build — all components linked (2-3h)
```bash
cd tracker/firmware
# Add to main/CMakeLists.txt COMPONENT_REQUIRES:
#   secp256k1 (from blossom-server/components — symlink or copy)
#   tollgate_core (from mesh-stack/tollgate)
#   ehash_relay (from mesh-stack/ehash-relay)
# Enable: CONFIG_ENABLE_MESH=y CONFIG_ENABLE_NOSTR_STORE=y
idf.py build 2>&1 | tee smoke-build.log
```
Capture: does it compile? Does it link? Any duplicate symbols? Binary size?

This single action tells you more about integration feasibility than the entire Phase 1-3 of the plan.

### Step 3: CI for host-side tests (2h)
GitHub Actions workflow that runs `make test` (or equivalent) for each component's host-side test suite. Catches regressions during integration.

### Step 4: Flash baseline + two-board raw ping (1h)
With orchestrator approval:
1. Flash the existing 227KB mesh-enabled binary to board A
2. Flash to board B
3. Board A: `radio_test` CLI command
4. Board B: `radio_recv` CLI command
5. Verify: board B sees board A's packet

This proves the radio path end-to-end with ZERO new code.

### Step 5: Define FreeRTOS task architecture (2-4h, design only)
Before writing ANY integration code, decide:
- Radio RX task: IRQ-driven, priority HIGH, reads packets, queues to app task
- App task: processes events (Nostr verify, tollgate, store), priority MEDIUM
- Mesh task: runs mesh.loop() if MeshCore is enabled, priority LOW
- Main task: sensor reading + telemetry TX, priority MEDIUM

Write this as a one-page design doc. This is the missing architecture that the entire integration plan depends on.

### Step 6: Flash the V1 PCB order (5 min)
Gerbers are ready. The 2-week JLCPCB lead time is the critical path for flight hardware. Order now. You can always update firmware — you can't update a 2-week delay.

---

## 4. ARCHITECTURAL CONCERNS (Question 4)

### CONCERN-1: TX-Sleep vs Continuous Relay — THE fundamental conflict [CRITICAL]

The current `app_main.cpp` has two mutually exclusive execution paths:

**Path A (default):** Wake → init → read sensors → TX telemetry → deep sleep for 60s. This is battery-optimized for a tracker. The radio is OFF 99% of the time.

**Path B (CONFIG_ENABLE_MESHCORE):** Init → `while(true) { mesh.loop(); vTaskDelay(1ms); }`. This is always-on for mesh. Deep sleep never happens.

**Neither path supports store-and-forward relay.** A relay balloon must:
- Continuously listen for incoming messages (always-on RX)
- Process and verify received messages (Schnorr verify, ~100ms)
- Store messages for later forwarding (nostr_store)
- Forward when a neighbor is available (TX on demand)
- Still do its own telemetry and GPS tracking

This requires a fundamentally different main loop than either current path. The plan never addresses this. Adding nostr_store + secp + tollgate + e-hash to a TX-sleep firmware produces a firmware that compiles but cannot relay anything, because nothing is listening.

**Resolution:** Design a FreeRTOS task architecture where:
- A radio RX task runs continuously (or is woken by DIO9 IRQ)
- An application task processes received events
- The main loop handles telemetry + power management
- Deep sleep is replaced with light sleep + radio wake-on-RX (or eliminated for relay nodes)

This is the single most important architecture decision in the project, and it's not in any document.

### CONCERN-2: Single-threaded main task [HIGH]

Everything currently runs on the main FreeRTOS task with a 16KB stack. There are zero `xTaskCreate` calls in the entire firmware. This means:
- A Schnorr verify call (~100ms on single-core C3 at 80MHz) blocks the entire system
- No packets can be received while processing an event
- CLI processing blocks during radio operations
- No watchdog recovery if any component deadlocks

**Resolution:** Minimum 2-3 FreeRTOS tasks:
- `radio_task` (HIGH priority, 4KB stack): IRQ-driven RX, TX dispatch
- `app_task` (MEDIUM priority, 8KB stack): event processing, secp verify, store
- `main_task` (MEDIUM priority, 8KB stack): telemetry, sensors, CLI

### CONCERN-3: Schnorr verify stack depth [MEDIUM, UNMEASURED]

The plan says secp256k1 context is ~2KB heap, transient. But the VERIFY CALL uses stack, not heap. On ESP-IDF with a 16KB main task stack, a deep Schnorr verify call chain could overflow. libsecp256k1's `secp256k1_schnorrsig_verify` calls into ecmult_precomp and field operations that may use significant stack.

**Resolution:** Before integrating, measure the peak stack depth during verify:
```c
// In test:
uxTaskGetStackHighWaterMark(NULL)  // before and after verify
```
If close to limit, run verify in a dedicated task with a large stack.

### CONCERN-4: Half-duplex radio scheduling [MEDIUM]

The LR2021 is half-duplex — it cannot TX and RX simultaneously. In the current code, TX is synchronous (`send_packet` → poll for `TX_DONE` → return). During a TX, nothing can receive. For a relay, this means:
- While forwarding a message, you miss incoming messages
- While verifying a Schnorr signature (100ms), you miss incoming messages
- During mesh.loop(), timing-sensitive radio state may be disrupted

**Resolution:** Accept packet loss during processing. The mesh layer (erasure coding, fragmentation) is designed for lossy links. But measure the effective duty cycle: what fraction of time is the radio in RX mode? If it's <50%, relay performance will be poor.

### CONCERN-5: Flash write endurance [LOW-MEDIUM]

nostr_store writes events to flash. The plan adds index persistence (writing `index.bin` on every 10th insert). ESP32 flash has ~100K erase cycles per sector. At altitude with continuous message relay:
- If you store 512 events and evict FIFO, you're writing ~1KB per event to flash
- SPI flash writes are slow (~100µs/byte) and block the CPU
- No wear leveling on raw POSIX file I/O (depends on LittleFS/SPIFFS implementation)

**Resolution:** This is not a V1 blocker. For the first integrated image, just get it working. But plan for: (a) batching flash writes, (b) using NVS for the index (has built-in wear leveling), (c) measuring actual flash write frequency.

### CONCERN-6: Brownout recovery for full stack [MEDIUM]

At altitude with solar power, brownouts will happen. The current code has `RTC_DATA_ATTR` variables that survive deep sleep, but a brownout is NOT a controlled deep sleep — it's a power glitch. After brownout recovery:
- Radio must reinitialize (SPI, LR2021 register config) — does this work reliably?
- nostr_store RAM index is lost (the index persistence gap from the review)
- secp256k1 context must be recreated
- Mesh state (neighbors, routes) is lost

**Resolution:** For V1, accept that brownout = full reboot. The system is designed to reinit from scratch. But TEST THIS: deliberately brown out the board mid-operation and verify clean recovery. This is a 10-minute test that will reveal real-world reliability issues.

### CONCERN-7: Boot time with all components [LOW, UNMEASURED]

How long from power-on to "all 9 components initialized and ready"? Current firmware delays 2 seconds at start (`vTaskDelay(pdMS_TO_TICKS(2000))` in app_main). Adding secp context creation, nostr_store init, tollgate init, mesh init could push boot to 5-10 seconds. With marginal solar power at altitude, a long boot increases the probability of brownout during boot.

**Resolution:** Measure. The 2-second startup delay can probably be removed. Log timestamps at each init step.

---

## 5. SHOULD WE PRIORITIZE DIFFERENTLY? (Question 5)

**Yes. Fundamentally differently.**

### Current priority: Component polish → Integration
### Recommended priority: Integration → Prove the critical path → Polish

### Priority matrix:

| What | Current Plan | Should Be | Why |
|------|-------------|-----------|-----|
| Unified smoke build | Phase 4 (last) | **Phase 0 (first)** | Highest risk, highest information value |
| FreeRTOS task design | Not mentioned | **Phase 1** | Blocks all radio integration work |
| Two-board raw ping | Not mentioned | **Phase 2** | Proves radio path with zero new code |
| Nostr round-trip | Phase 2.2 | **Phase 3** | First protocol layer on proven radio |
| TollGate round-trip | Phase 3.1 | **Phase 4** | Payment relay on proven protocol |
| Index persistence | Phase 1.1 | **Phase 5** | Not needed for first integration |
| E-hash relay wiring | Phase 2.1 | **Phase 5** | Overcomplicates the critical path |
| FIPS encryption | Not in plan | **Phase 5** | Wraps transport; add after transport works |
| Mesh routing (StratoRelay) | Not in plan | **Phase 6** | Multi-hop after single-hop works |
| CI | Question #4 only | **Now** | Protect 210 tests from regressions |
| PCB order | Question #5 only | **Now** | 2-week lead time is the hardware critical path |

### The one-sentence priority:
**Get two boards talking over LoRa with raw bytes using existing firmware, then build up.**

---

## 6. WHAT YOU'RE OVERCOMPLICATING

### OVERCOMP-1: E-hash relay before raw radio

The plan puts e-hash radio wiring as Phase 2.1, BEFORE the Nostr-over-LoRa transport (Phase 2.2). This is backwards. E-hash adds a complex PoW transport protocol on top of raw radio. You should prove raw radio works board-to-board FIRST (which requires zero new code — the CLI commands already exist), then add Nostr serialization, then add e-hash on top only if you need it.

**The balloon never hashes (per ADR-025).** E-hash is a pure L7 transport wrapper. For the first integration, skip it entirely. Send raw Nostr event bytes over raw LoRa. Add e-hash later if the use case demands it.

### OVERCOMP-2: Index persistence as an integration gate

Phase 1.1 (nostr_store index persistence) is listed as a prerequisite for integration. It's not. The store works in RAM. For the first integration test, events don't need to survive reboot. You need persistence for FLIGHT, not for BENCH INTEGRATION TESTING. Defer this to post-integration.

### OVERCOMP-3: Separate balloon/ground-station firmware

Question #3 asks about this. The answer is obvious: one binary, one config flag. `CONFIG_NODE_ROLE_BALLOON=y` or `CONFIG_NODE_ROLE_GROUND=y`. Set via NVS or a GPIO strap. The flash budget has 63% free. There's no reason to maintain two builds. Keep it simple.

### OVERCOMP-4: Dual-band TDMA

The review's Question #3 about TDMA scheduling is premature. For V1, pick ONE band (sub-GHz 915 MHz for maximum range — range matters more than throughput for a relay). Use it for everything. Don't time-multiplex two bands. The complexity of dual-band scheduling on a single-radio, single-core MCU is not worth it for V1.

### OVERCOMP-5: Wiring secp verify into nostr_store_add() as a hard gate

Phase 1.2 says "Before `nostr_store_add()`, call `secp256k1_schnorrsig_verify()`. Reject unsigned/invalid events." This makes signature verification mandatory for ALL storage. But the balloon itself generates telemetry events — does it sign them? If not, the balloon's own events would be rejected by its own store.

**Better approach:** Make verification a parameter, not a gate:
```c
nostr_store_add(event, verify_sig);  // verify_sig=true for relayed events
```
Or: verify at the TRANSPORT layer (before accepting from radio), not at the STORE layer.

### OVERCOMP-6: The 4-phase plan itself

The plan has 4 sequential phases with a dependency graph. The reality is simpler:
1. Link everything, see if it boots
2. Send bytes between two boards
3. Send a Nostr event between two boards
4. Send a payment between two boards

That's it. Four steps. Each one is a clear binary success/fail. No dependency graph needed.

---

## 7. ANSWERS TO THE PLAN'S QUESTIONS

### Q1: Is Phase 2 (radio integration) the right priority? Or TollGate-over-WiFi first?

**Radio integration is correct. WiFi is wrong.** This is a balloon. Balloons don't have WiFi. The transport IS LoRa. Testing TollGate over WiFi first would prove the wrong thing. Test the actual transport path.

However, skip the e-hash layer for the first radio test. Raw LoRa → raw bytes → print on serial. Then build up.

### Q2: Include FIPS encryption in first image, or defer?

**Defer.** FIPS Noise handshake is proven (13/13 tests) but wraps the transport layer. Get plaintext LoRa working first — prove you can send and receive Nostr events. Then wrap the transport with FIPS. FIPS is a transport-layer concern, not an application-layer concern. Adding it before the transport works means you can't distinguish transport bugs from encryption bugs.

### Q3: One firmware or two?

**One binary, runtime config.** A single NVS flag or GPIO strap selects balloon vs ground-station mode. The flash budget allows it. CI is simpler. Reflashing is simpler. The only reason for separate builds is flash savings, and you have 63% free.

### Q4: Invest in CI now?

**Yes. Unconditionally. This is the highest-ROI 2 hours in the project.** 210 tests exist with no CI. During integration, you WILL break things. Without CI, you won't know what broke until hours later. With CI, you know in 3 minutes. Add GitHub Actions for host-side gcc tests NOW.

### Q5: When to order V1 PCB?

**Now. Today.** The PCB is the hardware critical path (2-week lead time). Firmware can be updated indefinitely. The schematic doesn't need to match the firmware — you'll reflash firmware constantly. The only risk is if the integrated firmware reveals a hardware design flaw (like the GPIO10 collision), but that's fixable with a bodge wire on V1 and corrected in V2. Don't let perfect be the enemy of ordered.

**However:** Fix the GPIO10 (LED/NSS) collision in the PCB before ordering. If V1 gerbers have this collision, fix it. It's a 5-minute schematic change and the boards haven't been ordered yet.

---

## 8. REVISED INTEGRATION PLAN (SIMPLIFIED)

```
Phase 0: SMOKE (Day 1, 3h)
├─ Fix GPIO10 collision (LED → GPIO18)
├─ Fix GPS/FEM GPIO1 collision
├─ Add all 9 components to CMakeLists.txt
├─ CONFIG_ENABLE_MESH=y, CONFIG_ENABLE_NOSTR_STORE=y
├─ idf.py build → does it link?
├─ Flash to board → does it boot? Free heap?
└─ Add CI (GitHub Actions for host-side tests)

Phase 1: ARCHITECTURE (Day 1-2, 4h)
├─ Design FreeRTOS task layout (radio_task, app_task, main_task)
├─ Implement radio_task: IRQ-driven RX, TX dispatch queue
├─ Replace TX-sleep main loop with continuous-run main loop
├─ Add esp_get_free_heap_size() logging every 10s
└─ Flash → verify continuous operation, no panics, stable heap

Phase 2: RAW PING (Day 2, 2h)
├─ Board A: radio_test CLI (TX telemetry packet)
├─ Board B: radio_recv CLI (30s listen)
├─ Verify: board B sees board A's packet
└─ This is the first board-to-board integration test EVER

Phase 3: NOSTR ROUND-TRIP (Day 3, 4h)
├─ Board A: serialize Nostr event → send_packet
├─ Board B: receive → secp verify → nostr_store_add
├─ Verify: event appears in board B's store
└─ This proves the core store-and-forward use case

Phase 4: TOLLGATE ROUND-TRIP (Day 3-4, 3h)
├─ Board A: tollgate PAY encode → send_packet
├─ Board B: receive → tollgate decode → ACK encode → send
├─ Verify: board A receives ACK
└─ This proves the payment relay use case

Phase 5: POLISH (Day 5+)
├─ nostr_store index persistence (for brownout survival)
├─ FIPS Noise handshake wrapping the transport
├─ E-hash relay (if needed — balloon never hashes)
├─ StratoRelay multi-hop (3+ boards)
├─ Outdoor range testing
├─ Power budget measurement
└─ Flight readiness review
```

**Total time to first integrated round-trip: ~3 days (Phases 0-2).**
**Total time to proven payment relay: ~4 days (Phases 0-4).**

---

## 9. THE THREE THINGS THAT MATTER MOST

If you remember nothing else from this review:

1. **Do the smoke build FIRST.** Before index persistence. Before e-hash wiring. Before any protocol integration. Link all 9 components, flash, boot, measure heap. This is 3 hours that answers the most important integration question.

2. **Design the task architecture BEFORE writing integration code.** The current single-threaded TX-sleep firmware cannot function as a relay. You need an RX-driven event loop. This is the missing architecture. Without it, the integration plan produces a firmware that compiles but can't relay.

3. **Fix GPIO10 before you do ANYTHING with the radio.** LED and SPI chip-select on the same pin is a bug. It will cause intermittent radio failures that look like RF problems but are actually GPIO conflicts. 5-minute fix, saves hours of debugging.

---

*This review was produced by verifying every claim against the actual source code in `tracker/firmware/main/app_main.cpp`, component CMakeLists.txt files, Kconfig.projbuild, and the partition table. All pin assignments, code structure, and build configuration claims were checked directly.*
