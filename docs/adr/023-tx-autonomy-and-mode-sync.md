# ADR 023: TX Full Autonomy and TX/RX Mode Synchronization

## Status
Accepted (2026-07-26)

## Context

During walk test preparation on 2026-07-26, three critical architectural
violations were discovered:

### Violation 1: TX Depended on Laptop Connection

The TX firmware had a `SET_TIME` command that allowed the laptop to inject
UTC time via USB serial. During walk tests, TX is on a power bank — no USB
connection to laptop. If TX didn't get GPS time within 60s at boot, it fell
back to millis() and never recovered.

**The TX must be fully autonomous.** It gets ALL information it needs from
GPS. No laptop, no manual commands, no SET_TIME.

### Violation 2: TX and RX Ran Different Sweep Modes

TX defaulted to 14-phase base mode. RX defaulted to 56-phase interleave mode.
Both computed phase from UTC time, but different cycle lengths meant they
were on different RF modes at the same time. Result: zero packets decoded.

**TX and RX must always run the same sweep mode.** Default is 56-phase
interleave for both boards.

### Violation 3: Phase Sync Was Brittle

Phase computation depended on GPS time being available at boot (60s gate).
If GPS cold start exceeded 60s, TX fell back to millis() permanently.

**Phase sync must be continuous, not boot-time-only.** TX computes phase
from GPS UTC every loop iteration. If GPS time isn't available yet, TX
starts on millis() and seamlessly switches to GPS UTC the moment satellites
provide time.

## Decision

### 1. TX Is Fully Autonomous (GPS-Only)

TX MUST NOT require any connection to a computer. It:
- Gets UTC time from GPS RMC sentence (available without position fix)
- Computes sweep phase from GPS Unix epoch
- Starts sweeping within 5 seconds of power-on
- Switches from millis() to GPS UTC automatically when time arrives
- Embeds GPS status (fix, sats, position) in every transmitted packet

No SET_TIME command is needed or used for TX during walk tests.

### 2. TX and RX Must Always Be in the Same Sweep Mode

Both TX and RX default to **56-phase interleave mode** on boot.
- Phase tables are identical between TX and RX
- `totalCycleSec` is computed from the same interleave phase set
- Both compute `phase = utcSeconds % totalCycleSec`
- `make flash-all` ensures both boards have matching firmware

Changing the sweep mode (e.g., to 14-phase base mode) requires a deliberate
serial command on BOTH boards simultaneously. The default is interleave.

### 3. Continuous Phase Synchronization

Phase is recomputed every loop iteration from the current UTC time source:
1. **GPS Unix epoch** (`gps.unixTime` from date+time in RMC) — primary
2. **Laptop SET_TIME** (USB serial, RX only) — backup for lab testing
3. **millis() fallback** — only until GPS or laptop time arrives

TX uses priority 1→3. RX uses 2→1→3 (laptop clock is more accurate when
USB-connected, GPS is backup). Both converge to the same UTC → same phase.

### 4. Make Targets for Reproducibility

`make flash-all` builds and flashes both boards with identical configuration.
This eliminates the manual flashing errors that caused several regressions:
- Wrong firmware on wrong board
- Forgetting to flash RX after TX firmware change
- Mismatched interleave modes

### 5. RMC Time Parsing Independent of Position Fix

GPS RMC sentences contain valid UTC time even when position fix is not
available (status='V'). The firmware MUST extract time from RMC regardless
of fix status. This was the root cause of all walk test failures:
time was only parsed when position fields were populated (status='A').

## Consequences

- Walk test procedure: power TX on power bank, wait 30-60s for GPS time,
  start walk. No laptop interaction with TX.
- `make flash-all` is the ONLY supported way to flash boards for walk tests
- Any firmware change that affects phase computation, interleave mode, or
  GPS parsing MUST have unit tests (ADR-022) before merge
- TX beacon (every 5s) embeds phase/fix/sats/source in packet data so RX
  can report TX status even when boards are phase-desynced

## Related
- ADR-021: Absolute UTC phase synchronization (mechanism)
- ADR-022: Mandatory test coverage (enforcement)
- Makefile: `make flash-all`, `make detect`, `make walk-test`
