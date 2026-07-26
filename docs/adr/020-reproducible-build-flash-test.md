# ADR-020: Reproducible Build, Flash, and Test via Make Targets + pytest

## Status

Accepted

## Date

2026-07-26

## Related

- ADR-018: TX Autonomy Requirement
- ADR-019: TX-RX Sync Invariant
- PlatformIO build config: `firmware/rp2040/platformio.ini`

## Context

The balloon range test firmware has suffered repeated regressions due to
manual, ad-hoc procedures:

1. **Manual flashing**: Boards flashed with different commands at different
   times. Wrong .uf2 flashed to wrong board. Firmware version mismatch.

2. **No test coverage**: No automated tests verify that TX transmits, RX
   decodes, GPS locks, interleave syncs, or phase tables match. Every
   change is tested manually by running a capture and eyeballing output.

3. **Flaky capture scripts**: `cat /dev/ttyACM*` and `dd if=/dev/ttyACM*`
   commands compete for serial ports. One script reading a port steals
   data from another. Port assignments shift on unplug/replug.

4. **No regression detection**: A firmware change that breaks FLRC decoding
   is discovered hours later during a walk test, not immediately after
   the build.

## Decision

**All build, flash, capture, and test operations are defined as Make
targets and pytest fixtures. No manual commands.**

### Make Targets

```makefile
# Build
build-tx:     Build TX firmware (.uf2)
build-rx:     Build RX firmware (.uf2)
build-both:   Build both (default)

# Flash
flash-tx:     Flash TX board via BOOTSEL (auto-detect by serial)
flash-rx:     Flash RX board via BOOTSEL (auto-detect by serial)
flash-both:   Flash both boards in sequence

# Test
test:         Run pytest suite
test-unit:    Unit tests only (no hardware)
test-hw:      Hardware tests (requires boards connected)
test-walk:    Full walk simulation test

# Capture
capture:      Start robust RX capture daemon (timestamped files)
capture-stop: Stop capture daemon

# All-in-one
walk-ready:   build-both + flash-both + test-hw + verify GPS lock
```

### pytest Framework

**Fixtures** (setup/teardown):

```python
@pytest.fixture
def tx_board():
    """Flash TX, wait for boot, verify GPS module alive."""
    # Flash TX via BOOTSEL
    # Wait for serial enumeration
    # Verify NMEA output
    yield serial_port
    # Cleanup: close port

@pytest.fixture
def rx_board():
    """Flash RX, wait for boot, verify sweep output."""
    # Flash RX via BOOTSEL
    # Wait for PHASE_START output
    yield serial_port
    # Cleanup

@pytest.fixture
def both_boards(tx_board, rx_board):
    """Both boards flashed + synced with same epoch."""
    epoch = int(time.time())
    send_command(tx_board, f"SET_TIME {epoch}")
    send_command(rx_board, f"SET_TIME {epoch}")
    wait_for_phase_alignment(tx_board, rx_board)
    yield (tx_board, rx_board)
```

**Test Cases** (minimum required coverage):

| Test | What it verifies |
|------|-----------------|
| test_tx_boots | TX powers on, outputs NMEA within 5s |
| test_rx_boots | RX powers on, outputs PHASE_START within 5s |
| test_tx_gps_time | TX acquires GPS time within 60s |
| test_phase_table_match | TX and RX compute same phase for same UTC |
| test_interleave_auto | Both boards start interleave on boot (no command) |
| test_tx_no_usb | TX keeps sweeping after USB disconnect (simulated) |
| test_rx_decodes_tx | RX decodes at least 1 packet from TX |
| test_gps_fix_position | TX embeds lat/lon in packets after GPS fix |
| test_cdc_watchdog_battery | TX does NOT reboot 30s after USB disconnect |
| test_capture_daemon | Capture daemon writes timestamped files correctly |
| test_no_port_conflict | No two processes read same serial port |
| test_full_sweep_cycle | Complete 77-phase cycle with >50% decode rate |

### Robust RX Capture Daemon

Replace `cat /dev/ttyACM*` with a Python daemon:

```python
# rx_capture.py — always-on RX listener
# - Opens RX serial port by serial ID (not /dev path)
# - Writes to timestamped files: rx_capture_YYYYMMDD_HHMMSS.log
# - Rotates files every 30 minutes
# - Handles port disconnect/reconnect gracefully
# - No competing processes — exclusive lock on port
# - Signal handler for clean shutdown
```

## Invariants

1. `make flash-both` always flashes matching firmware to both boards
2. pytest fixtures flash boards before each hardware test (clean state)
3. Capture daemon runs continuously, never competes for port
4. Port detection by serial ID, not /dev path (ports shift on replug)
5. Every firmware change must pass `make test` before walk test

## Consequences

### Positive

- Reproducible: same procedure every time, no manual steps
- Regression detection: tests catch breakage immediately
- Port reliability: no more cat/dd stealing data
- Audit trail: test results logged with timestamps
- Onboarding: anyone can run `make walk-ready` and get working boards

### Costs

- Initial setup time (writing Makefile + pytest framework)
- Hardware tests require boards connected (can't run in CI)
- pytest adds dependency (pyserial, pytest)

## Rollout

### PR 1 — Make targets + capture daemon
- Makefile with build/flash/capture targets
- rx_capture.py daemon (replaces all cat/dd scripts)
- Port detection utility (find by serial ID)

### PR 2 — pytest framework
- conftest.py with board fixtures
- Unit tests (phase computation, NMEA parsing)
- Hardware test markers

### PR 3 — Full test coverage
- All 12+ test cases from the table above
- Walk simulation test
- Regression test for each previously-found bug
