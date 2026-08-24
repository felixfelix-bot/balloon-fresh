# ADR-018: TX Board Must Operate Fully Autonomously

## Status

Superseded (partial) — 2026-07-27. The original text stated TX should
NEVER transmit without a GPS satellite fix. This was a misunderstanding.
Corrected: TX transmits whenever it has valid time (can compute phase),
regardless of GPS position fix. GPS coordinates are broadcast once
position lock is acquired.

## Date

2026-07-26 (original), corrected 2026-07-27

## Related

- ADR-017: Phase Sync via Reference Clocks
- TX firmware: `firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp`
- Commit 3efdebe: CDC watchdog Serial && guard

## Context

During walk testing, the TX board is carried on a power bank with no USB
connection to any computer. The operator walks up to 5km away from the
RX receiver. There is NO way to send commands (SET_TIME, SET_INTERLEAVE)
to the TX board during the walk.

### Failures Observed

1. **CDC watchdog reboot (FIXED)**: TX rebooted 30s after USB unplug
   because Serial.write() returned 0. Fixed by `Serial &&` guard (3efdebe).

2. **SET_TIME dependency**: TX boot gate accepted laptop SET_TIME as a
   shortcut, creating a hidden dependency on USB connection. When TX
   booted on battery without ever receiving SET_TIME, it had no time
   source and could not compute phase.

3. **fixValid requirement**: Boot gate required GPS position fix
   (fixValid) before starting sweep. GPS provides time (hasTime) 10-30s
   before position fix (1-15 min). TX sat idle for 15+ min waiting for
   fix when it could have been sweeping with time-only.

## Decision

**The TX board must operate with ZERO computer interaction.** All time
and position information comes exclusively from the GPS module.

### Requirements

1. **No SET_TIME needed**: TX computes UTC from GPS satellites only.
   The SET_TIME serial command exists for bench testing convenience but
   is NEVER required for production operation.

2. **Boot gate waits for hasTime, not fixValid**: TX starts sweeping as
   soon as GPS time is available. Position fix is optional — packets
   carry lat=0/lon=0 until fix acquired, then real position.

3. **GPS fix loss tolerance**: If GPS loses position fix mid-sweep
   (tunnel, building, tree cover), TX keeps sweeping using last known
   UTC offset. Only stops if GPS TIME is lost entirely.

4. **USB CDC safety**: All serial output (outPrintf) is safe when no USB
   host is connected. Serial.write() returning 0 is expected on battery,
   not an error condition.

5. **Power-on autonomy**: TX behavior on battery power-on:
   - Boot → GPS module initializes → NMEA starts flowing
   - GPS time acquired (10-30s) → TX starts sweeping
   - GPS position fix acquired (1-15 min) → position data embedded in packets
   - Sweep continues indefinitely

## Invariants

1. TX NEVER requires a USB connection to function
2. TX NEVER requires SET_TIME from a computer
3. TX time source is GPS only (in production)
4. TX transmits with or without GPS position fix (as long as time exists)
5. TX survives USB disconnect without reboot

## Consequences

### Positive

- Walk test: plug TX into power bank, walk away. Zero interaction.
- Production: tracker balloon launches with battery, no ground station needed
- Testing: can simulate walk by simply unplugging USB

### Costs

- GPS cold start delay (15+ min without V_BCKP battery backup)
- No position data during first sweep cycles (lat=0/lon=0 until fix)
- Cannot override TX behavior remotely during walk

## Notes

The SET_TIME command remains in firmware for bench testing. When a laptop
IS connected, SET_TIME provides faster time sync than waiting for GPS.
This is a convenience, not a dependency.
