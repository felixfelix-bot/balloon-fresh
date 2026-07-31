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
- **Recent commits:** continuous TX firmware, goodput measurement, ESP32 capture targets, batched SPI TX
- **Next:** Execute SPEED-P0P2P3 verification plan against MERGE-FIX branch for throughput measurement
