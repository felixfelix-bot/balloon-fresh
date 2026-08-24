# ADR-025: Shared Hardware Access — Mandatory flock Mutex for ESP32-C3 + LR2021

**Date:** 2026-07-29
**Status:** ACCEPTED
**Decision Maker:** Felix (operator)

## Context

The balloon project runs multiple AI agent sessions concurrently (balloon-range-tests, balloon-speed-tests, balloon-fips, etc.). All sessions share the same physical machine and connected hardware. Without coordination, two sessions can attempt to flash/read the same board simultaneously, corrupting firmware or blocking serial ports.

An existing flock-based board lock system exists (`tools/balloon-board-lock.py`) with resources defined for:
- `tx`, `rx` — RP2040 boards (speed-tests, range-tests)
- `board-a`, `board-b`, `board-c` — ESP32-S3 boards

The ESP32-C3 + LR2021 boards currently connected to the machine (detected at `/dev/ttyACM0` MAC 96:DC, `/dev/ttyACM1` MAC C6:98) are NOT registered as lockable resources.

## Decision

**All hardware access by ANY agent session MUST acquire a flock lock first. No exceptions.**

### New Lock Resources

Add ESP32-C3 + LR2021 board resources to `balloon-board-lock.py`:

| Resource | Device | MAC | Purpose |
|----------|--------|-----|---------|
| `c3-a` | /dev/ttyACM0 | 96:DC | ESP32-C3 + LR2021 (Node A) |
| `c3-b` | /dev/ttyACM1 | C6:98 | ESP32-C3 + LR2021 (Node B) |
| `both-c3` | — | — | Both ESP32-C3 boards (coordinated TX/RX) |

### Lock Acquisition Protocol

1. **Before ANY hardware operation** (flash, serial read, SPI bus access, pio/idf.py):
   ```bash
   BALLOON_TRACK=balloon-fips python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py acquire c3-a \
       --purpose "FIPS handshake test" --timeout 120
   ```

2. **After operation completes** (or on error):
   ```bash
   BALLOON_TRACK=balloon-fips python3 ~/repos/balloon-fresh/tools/balloon-board-lock.py release c3-a
   ```

3. **Never bypass the lock.** Direct `idf.py -p /dev/ttyACM0 flash` without acquiring the lock is a violation.

4. **Never hold a lock longer than needed.** Release immediately after the operation.

### Enforcement

- The `balloon-board-lock.py` v3 hard device lock (chmod 000) physically prevents access by other processes
- The board-access-monitor cron job detects violations and alerts the orchestrator
- Track name MUST match (`BALLOON_TRACK=balloon-fips`) — cross-track access without `--steal` is blocked

## Consequences

- No two sessions can access the same board simultaneously
- Sessions must wait (up to timeout) if a board is locked
- `--steal` flag exists for emergency override but logs to THEFT-LOG and alerts the orchestrator

## Affected Components

- `tools/balloon-board-lock.py` — add c3-a, c3-b, both-c3 resources
- All agent AGENTS.md files — document the lock protocol
- Board access monitor cron — update port map for ESP32-C3 resources
