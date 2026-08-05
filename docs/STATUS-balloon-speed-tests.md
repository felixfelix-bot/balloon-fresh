# Balloon Speed Tests — Status

## Discovery Sync Acknowledgment (2026-08-01)

### Discovery: P1B.1-FIX — SPI TX debugging for raw FLRC (balloon-hermes, commit 822cdf0)
- **Tags:** SPI, RADIO, PROTOCOL
- **Assessed:** DIRECTLY RELEVANT to speed-tests scope (throughput, TX firmware)

#### Findings:
1. **SET_FLRC_PACKET_PARAMS already present** in my `esp32_raw_tx.cpp` (line ~248). 6-byte layout matches RadioLib reference. Balloon-hermes was testing a version missing this call — different code path.
2. **SPEED-P0P2P3-HW-VERIFICATION-PLAN.md** maps 4 speed-record commits:
   - SPEED-P0 (`44ad093`, `fix/raw-tx-packet-params`): packet params fix
   - SPEED-P2 (`67c0552`, `feat/radiolib-bypass-tx`): RadioLib bypass
   - SPEED-P3 (`45b57ab`, `feat/flrc-max-params`): FLRC_MAX + sweep
   - MERGE-FIX (`dc9d2e2`, `feat/speed-merge-fix`): P3 + shaping fix (PRIMARY TARGET)
   - All 4 branches exist in this worktree.
3. **Debugging techniques adopted**: GPIO toggle CS monitoring, FIFO write-readback verification, BUSY transition monitoring. Will add to benchmark scripts if TX issues arise.

#### Action: Independently usable. No coordination needed. These branches are my throughput optimization targets.

## Current State
- **Branch:** `speed-sustained-sweep`
- **Recent commits:** continuous TX firmware, goodput measurement, ESP32 capture targets, batched SPI TX, FLRC fixes synced from RP2040
- **Next:** Execute SPEED-P0P2P3 verification plan against MERGE-FIX branch for throughput measurement

## Discovery Sync (2026-08-05) — 4 findings from balloon-hermes

### 1. GPIO10 collision (LED vs LR2021 NSS) — commit f926dc9 | RADIO
- **Assessed:** NOT applicable to speed-test boards. Our ESP32-C3 Mini V1 uses GPIO10=NSS, GPIO8=LED (no collision). FEM_TX_PIN also N/A (no FEM on speed-test boards).
- **Action:** No changes needed.

### 2. FLRC RP2040 fixes (STDBY_RC, CLEAR_ERRORS, DIO_IRQ_CONFIG) — commit 0292aec | RADIO
- **Assessed:** CRITICAL — ESP32-C3 throughput firmware was missing all 3 fixes that RP2040 got.
- **Action taken:** Synced all 3 fixes to `firmware/esp32-c3-flrc/main/main.cpp` (commit afe0edb):
  - STDBY_XOSC → STDBY_RC in init_radio()
  - CLEAR_ERRORS between TX cycles
  - DIO_IRQ_CONFIG re-set before each TX
  - Fixed incorrect IRQ bit comment (bit 11 → bit 19)
- **Impact:** Sustained TX (1000 pkts) without CLEAR_ERRORS can accumulate PA_OCP_OVP errors → intermittent failures. Should improve throughput measurement reliability.

### 3. secp256k1 component added to tracker firmware — commit 0829953 | FIRMWARE, TEST
- **Assessed:** Informational. Speed-tests track doesn't use secp256k1. No action.

### 4. Mesh baseline build verified + secp measurement + tollgate payment tests — commit 8aaa0bb | FIRMWARE, PROTOCOL, TEST
- **Assessed:** Informational. Speed-tests scope is throughput optimization only. No action.

## Discovery Sync Batch 2 (2026-08-05) — 6 findings from balloon-hermes

### 5. Integration test plan + PCB GPIO fix plan — commit 2cbf7cd | HARDWARE, TEST
- **Assessed:** Phase 6 (logic analyzer C3 vs RP2040 SPI timing) is DIRECTLY in speed-tests scope.
- **Action:** Cherry-picked CONTINUOUS_TX firmware feature (aaa6aef) into speed-tests worktree. Applied FLRC fixes to continuous TX function. Ready for LA capture when orchestrator approves board access.

### 6. radio_task non-blocking loop — commit 4e7722c | RADIO, FIRMWARE
- **Assessed:** Informational. Tracker relay-mode radio_task uses lr2021_transport layer, not my raw SPI benchmark firmware. Different code path. The non-blocking pattern (100ms recv timeout + tx_queue poll) is good architecture but not applicable to throughput benchmarks which run single-purpose TX.

### 7. signature field in nostr_event_t — commit bc3bd5b | FIRMWARE, TEST
- **Assessed:** Not applicable. Speed-tests firmware has no Nostr event handling.

### 8. host-side relay pipeline integration test — commit 4e86174 | PROTOCOL, TEST
- **Assessed:** Not applicable. Relay pipeline tests are for tracker firmware, not throughput benchmarks.

### 9. SPI timing comparison status + Phase 6 plan — commits 4c5fa95, 4d53713, b6c2146 | SPI
- **Assessed:** CRITICAL — Phase 6 IS speed-tests work. RP2040 baseline complete (10.4 MHz SCK, 18.3% bus duty, 1754 kbps). C3 has zero LA captures.
- **Action taken:**
  - Cherry-picked CONTINUOUS_TX mode (commit 7861c3c)
  - Applied FLRC fixes to continuous TX function
  - Firmware ready for LA capture: `idf.py -DCONTINUOUS_TX=1 build` + flash
- **BLOCKER:** Need orchestrator approval for board access to flash C3 + capture with logic analyzer
- **Next:** When boards available, run `make debug-esp32` (builds + flashes + captures in one command)

## Discovery Sync Batch 3 (2026-08-05) — 5 findings

### 10. V1 PCB GPIO fix (gerbers) — commit 698a039 | HARDWARE, TEST
- **Assessed:** N/A. Same GPIO10 collision already assessed in batch 1. Speed-test boards use different pinout (GPIO10=NSS, GPIO8=LED, no FEM). PCB gerbers are for tracker V1 board.

### 11. tollgate_payment_proto.h + CLI — commit 65a46fd | FIRMWARE, PROTOCOL, TEST
- **Assessed:** N/A. TollGate payment logic, not throughput firmware.

### 12. relay_send_nostr CLI — commit 108c2b9 | PROTOCOL, TEST
- **Assessed:** N/A. Nostr relay command in tracker firmware.

### 13. nostr_dump CLI — commit b093ac8 | TEST
- **Assessed:** N/A. Nostr debug dump command.

### 14. pre-stretching discovery sync — commit (line 95) | HARDWARE, TEST
- **Assessed:** Informational. Pre-stretching track assessed same findings independently.

## Discovery Sync Batch 4 (2026-08-05) — 3 findings

### 15. V1-FAST board smoke test — commit (balloon-hermes) | HARDWARE, TEST
- **Assessed:** N/A. PCB pipeline DRC smoke test for V1-FAST board. No speed-tests impact.

### 16. Range-tests V1 GPIO fix — commit (balloon-range-tests) | HARDWARE, TEST
- **Assessed:** N/A. Same GPIO10 collision fix range-tests adopted (batch 1 sync). Already assessed N/A for speed-test boards.

### 17. Range-tests integration test plan — commit (balloon-range-tests) | HARDWARE, TEST
- **Assessed:** Informational. Range-tests assessed same Phase 2-4 integration plan.
