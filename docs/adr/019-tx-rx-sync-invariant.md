# ADR-019: TX-RX Synchronization Invariant — Same 56-Phase Sweep

## Status

Accepted

## Date

2026-07-26

## Related

- ADR-017: Phase Sync via Reference Clocks
- ADR-018: TX Autonomy Requirement
- TX firmware: `firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp`
- RX firmware: `firmware/rp2040/src/multi_radio_sweep_rx_v4.cpp`

## Context

For RX to decode TX packets, both boards must be in the same modulation
mode at the same time. They achieve this by independently computing the
current phase from UTC time using the same `computePhaseFromUTC()` function
and the same `phases[]` table (ADR-017).

### Problem Observed

During testing, the TX and RX ran different sweep configurations at
different times due to manual flashing and mode switching. This caused:

1. **Mode mismatch**: TX in "base mode" (single mode, 255B) while RX in
   "interleave mode" (56-phase sweep). They never aligned.

2. **Phase table drift**: Fixes applied to TX phases[] table but not RX
   (or vice versa). Different index mappings caused complete decode failure.

3. **Manual configuration errors**: SET_INTERLEAVE sent to one board but
   not the other. Different SET_TIME epochs causing phase offset.

4. **Inconsistent flashing**: Boards flashed at different times with
   different firmware versions. No guarantee they run the same code.

## Decision

**TX and RX MUST always run the identical 56-phase interleave sweep.**
This is the one and only sweep mode. There is no "base mode" in production.

### Requirements

1. **Single sweep definition**: Both TX and RX use the same 56-phase
   interleave table. 14 modulation modes × 4 payload sizes = 56 core
   phases, plus 21 channel sweep phases = 77 total.

2. **Interleave is default on boot**: `interleaveMode = true` hardcoded.
   No SET_INTERLEAVE command needed. Both boards start sweeping on boot.

3. **Same firmware build**: TX and RX firmware are built from the same
   source tree. The phases[] table is defined ONCE in a shared header.

4. **Same flash procedure**: Both boards flashed together via `make flash-both`.
   Never flash one without the other.

5. **Phase alignment verification**: After flashing, a test verifies both
   boards compute the same phase for the same UTC timestamp.

## Invariants

1. TX phases[] table === RX phases[] table (byte-identical)
2. TX computePhaseFromUTC() === RX computePhaseFromUTC()
3. Both boards boot directly into interleave mode
4. Both boards compute phase from UTC (TX: GPS, RX: laptop NTP)
5. Phase offset between TX and RX < 500ms at all times

## Consequences

### Positive

- No mode confusion: both boards always in the same mode
- No SET_INTERLEAVE needed: automatic on boot
- make flash-both guarantees firmware consistency
- Regression tests catch phase table divergence

### Costs

- Cannot run "base mode" (single-mode testing) without firmware change
- Both boards must be reflashed together (can't update one independently)
- Less flexibility for ad-hoc testing

## Notes

The "base mode" (single modulation, 255B packets) was a debugging tool
during development. In production, the 56-phase interleave sweep is the
only mode. If single-mode testing is needed in the future, it should be
implemented as a compile-time flag, not a runtime command.
