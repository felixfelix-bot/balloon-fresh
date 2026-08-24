# ADR 022: Mandatory Full Test Coverage for Walk Test Firmware

## Status
Accepted (2026-07-26)

## Context

During the 2026-07-26 walk test preparation, multiple regressions were
discovered through manual testing:

1. **60s boot gate** — TX blocked on GPS, fell back to millis() (ADR-021)
2. **Interleave mode mismatch** — TX defaulted to 14-phase, RX to 56-phase
3. **RMC time parsing bug** — time only extracted when position fix available
4. **Phase desync** — all three bugs above caused TX/RX to be on different
   RF modes at the same time → zero packets decoded

Each of these regressions could have been caught by automated tests before
flashing. The manual debug cycle took hours and required physical walk tests
to discover failures.

## Decision

All firmware changes that affect walk test reliability MUST have
corresponding pytest tests before they are merged. Tests are organized
into two tiers:

### Tier 1: Unit Tests (`@pytest.mark.unit`)

No hardware required. Run on any machine. These test:

- **RMC parser logic** — feed sample NMEA sentences (with and without fix),
  verify time extraction works in all cases
- **Phase computation** — verify `computePhaseFromUTC()` produces correct
  phase for given UTC times
- **Interleave table** — verify TX and RX produce identical phase tables
- **Packet format** — verify beacon packet structure, CRC, field sizes
- **walk_capture.py parsing** — verify log parsing, stats extraction

### Tier 2: Hardware Integration Tests (`@pytest.mark.hardware`)

Requires both RP2040 boards connected via USB. These test:

- **Flash + boot** — flash both boards, verify boot messages within timeout
- **Phase alignment** — both boards compute same phase from same UTC time
- **TX transmission** — TX outputs PKT lines with correct phase numbers
- **RX reception** — RX decodes packets when boards are phase-aligned
- **GPS time sync** — TX gets valid UTC from GPS within 30s
- **Walk capture** — walk_capture.py runs for 60s, captures data to file

### Test Fixtures

- `conftest.py` defines board serial numbers, port auto-detection
- `flash_tx` fixture: builds + flashes TX, waits for boot, returns port
- `flash_rx` fixture: builds + flashes RX, waits for boot, returns port
- `flash_both` fixture: flashes both, returns (tx_port, rx_port)
- Each fixture handles setup (flash + wait) and teardown (kill processes)

## Consequences

- `make test-unit` runs fast (seconds), no hardware needed — run before every commit
- `make test-hardware` runs slow (minutes), requires boards — run before walk tests
- `make flash-all` uses same Make targets as tests → reproducible
- Regressions in RMC parsing, phase computation, interleave mode will be
  caught by unit tests instantly
- Phase desync between TX and RX will be caught by hardware tests

## Related
- ADR-021: Absolute UTC phase synchronization
- ADR-023: TX autonomy and TX/RX mode synchronization
- Makefile: `make test`, `make test-unit`, `make test-hardware`
- tests/conftest.py: pytest fixtures
