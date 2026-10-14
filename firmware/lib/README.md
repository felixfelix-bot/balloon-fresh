# flight software — independently tested libraries

Six (then nine) modules, each **self-contained and host-testable without
hardware**, so they can be composed into one deployment when needed.

## Test harness decision (2026-10-14)

**PlatformIO is NOT installed on the build host** — `which pio platformio`
returns nothing; only `g++`/`gcc` are present. `pio test -e native` is therefore
impossible. The harness is a **plain g++ + assert-based** one:

```sh
make -C firmware/lib test          # builds and runs every module test
make -C firmware/lib test-telemetry  # not implemented; use `test` and read the log
```

Each module is `firmware/lib/<mod>/{<mod>.h,<mod>.cpp,test_<mod>.cpp}`.
`test_<mod>.cpp` defines `void run_tests()` and ends with `TEST_MAIN()`.

If the ESP32-S3 toolchain is ever installed, add a root `platformio.ini` with an
`[env:hub_v9]` (esp32-s3, `framework = arduino`, matching the per-directory
conventions in `firmware/esp32-uart-bridge/platformio.ini`) — but the host tests
must keep working with g++ only, because that is what CI here can run.

## Discipline (non-negotiable)

1. **TDD:** write the test, run it, **observe it fail**, then implement. Paste the
   real RED output in the commit message — never describe a failure you did not see.
2. **Counter-test per module:** every module carries at least one test that
   *proves the test can fail* (corrupt the CRC and assert rejection; inject a torn
   write and assert the counter still increments). A green suite with no
   counter-test is not evidence.
3. **No hardware claim without hardware.** A compile is not a flash; a host mock
   is not a radio.

## Modules

| # | module | what it does |
|---|---|---|
| — | `telemetry` (S1) | versioned record + LSB-first wire format + CRC32 |
| — | `resetlog` (S3) | persisted reset cause + monotonic boot counter |
| — | `ringstore` (S2) | littlefs store-and-forward ring, power-cut safe |
| — | `scheduler` (H1) | energy-budgeted duty scheduling (pure logic) |
| — | `gpsconfig` (S4) | UBX airborne<1g config + read-back assert |
| — | `expframework` (H2) | enable/disable experiments; disabled = zero cost |

Planned: LR2021 driver (L0), LoRaWAN (L2), MeshCore (L3), Meshtastic (L4) — all
three protocols share one radio, so a single driver with per-protocol schedulers
is mandatory, or they contend for SPI/TCXO.
