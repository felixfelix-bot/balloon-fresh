# Test Plan

## Overview

Full pytest test coverage for all business logic in the pico balloon tracker project.
C host tests compiled with gcc/g++ and wrapped in pytest via subprocess.
Python modules tested directly with pytest.

**Current status: 72/72 tests passing. All tiers complete.**

Run all tests:
```bash
python -m pytest tests/ -v
```

---

## Tier 1: High ROI, Zero/Low Effort

### T1.1: Frag standalone tests
- [x] Write `tracker/firmware/components/frag/test/test_frag.c` (13 tests)
  - [x] `frag_crc16` known vectors, empty, deterministic, different data
  - [x] `frag_reassembler_init` zero state, correct field values
  - [x] `frag_reassembler_feed` valid frame, short frame (< header), wrong block_id, wrong count, duplicate detection, completion
  - [x] `frag_make_frame` output format, CRC in header, oversized output
  - [x] Roundtrip: make_frame → feed → verify assembly
- [x] Add `TestFrag` entry in `tests/test_c_host.py`
- [x] Verify passing

### T1.2: BMP280 compensation math tests
- [x] Write `tracker/firmware/components/bmp280/test/test_bmp280.c` (include bmp280.c directly for static functions)
  - [x] `compensate_temp` with known ADC_T + calibration → expected output
  - [x] `compensate_press` with known ADC_P + calibration + t_fine → expected output
  - [x] Edge cases: zero ADC, max ADC, negative temperature
- [x] Add `TestBMP280` entry in `tests/test_c_host.py`
- [x] Verify passing

### T1.3: CI config (GitHub Actions)
- [x] Write `.github/workflows/test.yml`
  - [x] Trigger on push/PR to main
  - [x] Install gcc, g++, python 3.13, pytest, pyserial, libmbedtls-dev
  - [x] Run `python -m pytest tests/ -v`
- [x] Verify workflow syntax

---

## Tier 2: Medium Effort

### T2.1: Antenna switch + SKY66112 GPIO tests
- [x] Write `tests/host_stubs/driver/gpio.h` (gpio_config, gpio_set_level stubs recording to arrays)
- [x] Write `tracker/firmware/components/antenna_switch/test/test_antenna_switch.c` (7 tests)
  - [x] Init sets GPIO outputs
  - [x] Select antenna 0-3 sets correct pin states
  - [x] Select >3 clamps to 3
  - [x] get_current returns last selected
- [x] Write `tracker/firmware/components/sky66112/test/test_sky66112.c` (9 tests)
  - [x] Init sets GPIO outputs
  - [x] set_mode TX/RX/BYPASS/SHUTDOWN pin states
  - [x] Wrapper functions delegate correctly
- [x] Add `TestAntennaSwitch` and `TestSKY66112` entries in `tests/test_c_host.py`
- [x] Verify passing

### T2.2: CLI tests
- [x] Refactor `cli.c`: add `cli_set_io(getchar_fn, printf_fn)` for test injection
- [x] Write `tracker/firmware/components/cli/test/test_cli.c` (8 tests)
  - [x] Init registers "help" command
  - [x] Register custom command, dispatch matches
  - [x] Unknown command prints error
  - [x] Args splitting (command + space + args)
  - [x] Backspace handling
  - [x] Buffer overflow protection
  - [x] Multiple commands in sequence
- [x] Add `TestCLI` entry in `tests/test_c_host.py`
- [x] Verify passing

### T2.3: Power manager voltage math tests
- [x] Extract `power_manager_raw_to_mv(raw, calibrated_mv)` pure function
- [x] Write `tracker/firmware/components/power_manager/test/test_power_manager.c` (5 tests)
  - [x] Raw ADC → voltage conversion (12-bit, 3.3V ref)
  - [x] Voltage divider multiplier (×2)
  - [x] Calibration override
- [x] Add `TestPowerManager` entry in `tests/test_c_host.py`
- [x] Verify passing

### T2.2: CLI tests
- [ ] Refactor `cli.c`: add `cli_set_io(int (*getchar_fn)(void), void (*printf_fn)(const char *, ...))` for test injection
- [ ] Write `tracker/firmware/components/cli/test/test_cli.c`
  - [ ] Init registers "help" command
  - [ ] Register custom command, dispatch matches
  - [ ] Unknown command prints error
  - [ ] Args splitting (command + space + args)
  - [ ] Backspace handling
  - [ ] Buffer overflow protection
  - [ ] Multiple commands in sequence
- [ ] Add `TestCLI` entry in `tests/test_c_host.py`
- [ ] Verify passing

### T2.3: Power manager voltage math tests
- [ ] Extract `pm_raw_to_mv(int raw, int calibrated_mv)` pure function
- [ ] Write `tracker/firmware/components/power_manager/test/test_power_manager.c`
  - [ ] Raw ADC → voltage conversion (12-bit, 3.3V ref)
  - [ ] Voltage divider multiplier (×2)
  - [ ] Calibration fallback when no calibration scheme
- [ ] Add `TestPowerManager` entry in `tests/test_c_host.py`
- [ ] Verify passing

---

## Tier 3: Deferred

### T3.1: Crypto component (on-target)
- [ ] Needs ESP-IDF Unity test framework + actual hardware
- [ ] `test/` directory exists but empty
- [ ] Deep dependencies: mbedtls, NVS flash, esp_timer, ESP32 HW AES
- [ ] Deferred until bench testing

### T3.2: Hardware-mocked integration tests
- [ ] Full I2C/SPI/ADC flows with mocked drivers
- [ ] Deferred until bench testing

### T3.3: Playwright
- [ ] No web UI in ground station — not applicable

---

## Test Count Tracking

| Category | Component | Tests | Status |
|----------|-----------|-------|--------|
| **Python** | link_budget | 29 | Done |
| **Python** | telemetry_to_nostr | 11 | Done |
| **Python** | ground_station | 14 | Done |
| **C Host** | erasure | 5 | Done |
| **C Host** | tdma | 7 | Done |
| **C Host** | nostr_store | 7 | Done |
| **C Host** | micro_ecc | 5 | Done |
| **C Host** | fips_transport | 10 | Done |
| **C Host** | pipeline | 5 | Done |
| **C Host** | telemetry | 11 | Done |
| **C Host** | gps | 8 | Done |
| **C Host** | frag | 13 | Done |
| **C Host** | bmp280 | 6 | Done |
| **C Host** | antenna_switch | 7 | Done |
| **C Host** | sky66112 | 9 | Done |
| **C Host** | cli | 8 | Done |
| **C Host** | power_manager | 5 | Done |

**Total: 72 done + ~0 planned = 72 complete**
