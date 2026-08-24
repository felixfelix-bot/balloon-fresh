# ADR 021: Absolute UTC Phase Synchronization — No Boot-Time GPS Gate

## Status
Accepted (2026-07-26)

Supersedes ADR-019 Phase 2 (GPS Time Sync) — implements and extends it with
critical boot-sequence requirements discovered during field testing.

## Context

ADR-019 proposed GPS-synchronized mode switching as "Phase 2: Future." The V4
sweep firmware (multi_radio_sweep_gps_v4.cpp, commit b7dd442) already
implements the core concept: both TX and RX compute their sweep phase from
absolute UTC time using `computePhaseFromUTC(unixTime)`.

However, field testing (2026-07-26 walk tests) revealed a critical boot-sequence
bug:

### The Problem

The TX firmware had a **60-second blocking GPS wait** at boot:

```cpp
=== WAITING FOR GPS TIME (up to 60s) ===
while (!gps.hasTime && (millis() - gpsStart) < GPS_FIX_TIMEOUT_MS) { ... }
```

When GPS cold-start exceeded 60s (common for GEP-M10 without battery backup,
typical cold start: 30-120s), TX fell back to `millis()`-based phase cycling.
This caused **complete phase desynchronization** between TX (on power bank,
millis-based) and RX (on laptop, UTC-based). Result: zero packets decoded
despite both boards being fully functional.

### Why GPS Time Is Available Without Position Fix

The GEP-M10 outputs valid UTC time in the `$GNRMC` sentence even with `V`
status (no fix). The time field is populated from satellite broadcast as soon
as any satellite is acquired — position fix (4+ satellites, `A` status) is
only needed for lat/lon. The V4 firmware correctly parses this: `gps.hasTime`
is set on the first valid time field, independent of fix status.

## Decision

### 1. Phase Computation from Absolute UTC — ALWAYS

Both TX and RX compute sweep phase from absolute UTC seconds:

```
phase = phaseTable[utcSeconds % totalCycleSeconds]
```

Priority chain (checked every loop iteration):
1. **GPS Unix epoch** (`gps.unixTime` from date+time in RMC) — primary
2. **Laptop SET_TIME** (USB serial command from capture script) — backup
3. **millis() fallback** — last resort, will drift

This is already implemented in the V4 firmware main loop. No change needed.

### 2. No Boot-Time GPS Gate — TX Starts Immediately

**TX must begin sweeping within 5-6 seconds of power-on, regardless of GPS
state.** A short 5-second GPS probe replaces the 60-second blocking wait:

```cpp
// Brief GPS probe (5s), then start sweeping immediately
while (!gps.hasTime && (millis() - gpsStart) < 5000) { gpsPoll(); }
// Start sweeping whether or not GPS has time.
// Main loop will pick up GPS time when it arrives.
```

The main loop already checks `gps.hasUnixTime` every iteration. When GPS
provides time (even without fix), TX seamlessly switches from millis()
to GPS UTC. No reboot, no operator intervention.

### 3. GPS Time Without Fix Is Sufficient for Phase Sync

`gps.hasTime` (RMC time field, status V) is sufficient for phase computation
using `gps.timeSec` (seconds since midnight). `gps.hasUnixTime` (full
date+time from RMC) provides true Unix epoch for long-term accuracy. Position
fix (`gps.fixValid`, status A) is only needed for lat/lon telemetry fields.

### 4. Periodic Beacon for Operator Awareness

TX emits a `BEACON` line every 5 seconds with:
- Current phase number
- GPS fix status (0/1)
- Satellite count
- Uptime
- Time source (GPS / LAPTOP / MILLIS)

When TX is on USB (laptop-connected), beacon appears in serial output.
When TX is on power bank (walk test), beacon data is embedded in every
packet's GPS fields for RX-side extraction.

## Consequences

- TX never blocks on GPS at boot — sweep starts in ~5s
- Walk tests work: TX on power bank acquires GPS time mid-walk, switches to
  UTC phase sync automatically
- No operator intervention needed once TX is powered
- millis() fallback still available for lab testing without GPS module
- ADR-019 Phase 1 (button-triggered sync) is DEPRECATED — not needed
- ADR-019 Phase 2 (GPS sync) is IMPLEMENTED with the boot-fix refinement

## Related
- ADR-018: Multi-mode range characterization (defines the sweep phases)
- ADR-019: GPS-synchronized mode switching (original concept)
- Commit b7dd442: V4 sweep firmware with UTC phase computation
- multi_radio_sweep_gps_v4.cpp: TX implementation
- multi_radio_sweep_rx_v4.cpp: RX implementation
