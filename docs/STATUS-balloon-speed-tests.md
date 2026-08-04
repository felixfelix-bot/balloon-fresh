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
