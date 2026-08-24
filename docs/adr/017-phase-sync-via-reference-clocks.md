# ADR-017: Phase Synchronization via Independent Reference Clocks

## Status

Accepted

## Date

2026-07-26

## Related

- TX firmware: `firmware/rp2040/src/multi_radio_sweep_gps_v4.cpp` — `computePhaseFromUTC()`, `gpsPoll()`, `checkSerialTimeSync()`
- RX firmware: `firmware/rp2040/src/multi_radio_sweep_rx_v4.cpp` — `computePhaseFromUTC()`, `checkSerialTimeSync()`
- ADR-007: Adaptive Protocol (defines the interleave sweep)

## Context

The balloon RF characterization system uses an interleave sweep: TX cycles
through 56 phases (14 modulation modes x 4 payload sizes) plus 21 channel
sweep phases. Each phase lasts ~3-5 seconds. RX must listen in the SAME
mode at the SAME time to decode packets.

The synchronization problem: how do TX and RX agree on which phase is
active at any given moment?

### Approaches Considered

**Option A: Bidirectional RF sync (REJECTED)**

TX and RX exchange timing packets over the radio link. RX locks onto TX's
phase. Problems:
- Requires bidirectional communication (not available during walk tests)
- Slow modulations (LoRa SF12, ~1 Hz packet rate) make sync acquisition
  extremely slow
- Fails when link is marginal (exactly when characterization matters most)
- Adds protocol complexity to the radio layer

**Option B: TX beacon in fixed mode (REJECTED)**

TX transmits periodic beacon packets in a known mode (LoRa SF7, 868 MHz)
between sweep phases. RX detects beacons and adjusts its phase clock.
Problems:
- Steals airtime from the actual sweep characterization
- Adds firmware complexity (beacon scheduling, collision avoidance)
- Unnecessary — both boards already have accurate independent clock sources

**Option C: Independent reference clocks (ACCEPTED)**

Both TX and RX compute phase independently from their own reference clocks
using a deterministic formula. No RF-based sync required.

## Decision

**Each board computes the current phase from its own UTC time source using
a shared deterministic function.** No bidirectional communication or beacon
exchange is needed for synchronization.

### Time Sources

| Board | Time Source | Accuracy | Update Rate |
|-------|------------|----------|-------------|
| TX | GPS satellites (u-blox M10) | nanosecond | continuous |
| RX | Laptop NTP (via SET_TIME command) | millisecond | every 10s |

### Phase Computation

```
phase = computePhaseFromUTC(currentUtcSeconds)
```

Where `computePhaseFromUTC()` is a pure deterministic function:

1. Convert UTC seconds to a phase index modulo total cycle length
2. Look up modulation parameters from the shared phases[] table
3. Configure radio for that mode

Both TX and RX use the IDENTICAL function and IDENTICAL phases[] table.
As long as both clocks agree within ~500ms, they stay in the same phase.

### Walk Test Procedure

1. TX plugged into laptop: receive `SET_TIME`, acquire GPS lock
2. Unplug TX: GPS provides UTC autonomously
3. TX continues computing phase from GPS time
4. RX computes phase from laptop NTP (resync loop every 10s)
5. No RF-based sync needed at any point

### CDC Watchdog Interaction

The USB CDC watchdog (recovering from dead TinyUSB stack) must NOT fire
when the board is on battery power. The guard:

```cpp
if (Serial && lastCdcSuccessMs > 0 && ...)
```

`Serial` evaluates false when no USB host is present, preventing reboot
and preserving the UTC offset set before unplugging.

## Invariants

1. Both boards MUST have the same phases[] table (same mode definitions)
2. Both boards MUST use the same computePhaseFromUTC() formula
3. TX clock accuracy: GPS UTC (nanosecond)
4. RX clock accuracy: NTP (millisecond) — sufficient for 3-5s phase slots
5. Clock drift between SET_TIME updates MUST be < 500ms (RP2040 crystal: <10ppm = <36ms/hour)
6. GPS gate on TX: NEVER transmit without a valid time source

## Consequences

### Positive

- Zero protocol overhead — no sync packets waste airtime
- Works at any modulation speed (even LoRa SF12 at 0.5 Hz)
- Works when link is marginal (no dependency on RX hearing TX beacons)
- Works during walk tests (TX fully autonomous after SET_TIME)
- Simple firmware: one function, no beacon scheduling
- Deterministic: given UTC, phase is always computable

### Costs

- TX requires GPS lock before transmitting (cold start: 15-30 min without V_BCKP)
- RX requires periodic laptop resync (every 10s) — not fully autonomous
- If GPS time and laptop time disagree, phase desync occurs (mitigated by
  both using UTC standard)
- GPS module cold start is slow without battery backup (V_BCKP pin unwired)

## Notes

### Why the beacon approach was initially proposed

During the 2026-07-26 walk test, TX failed to transmit on power bank. Root
cause was diagnosed as GPS cold start. A TX beacon was proposed to let RX
know TX was alive. However, the ACTUAL root cause was the CDC watchdog
rebooting TX 30s after USB unplug — not a sync problem. Once the watchdog
was fixed (commit 3efdebe), the independent clock architecture worked
correctly without any beacon.

### Future improvement: V_BCKP backup battery

Adding a CR1220 coin cell or supercapacitor to the GPS module's V_BCKP pin
would retain ephemeris data across power cycles, reducing cold start from
15+ minutes to 1-5 seconds (warm start). This is a hardware-track change.
