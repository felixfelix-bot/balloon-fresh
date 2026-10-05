# PCB Phase 5 — Firmware GPIO update (V1 flight board)

Plan: `docs/coordination/PCB-AUTOROUTE-EXECUTION-PLAN.md`, Phase 5 (`worker-balloon`).
Task: kanban `t_807f52d4`.

## 1. Why the pins moved

The V1 flight PCB freed GPIO9 (formerly the BMP280 I2C SDA line) and dropped the
SKY66112 FEM. Three firmware defaults still pointed at the *breadboard* pin map
and had to be brought in line:

| Signal | Old | New | Reason |
|---|---|---|---|
| Status LED | GPIO18 | **GPIO9** | GPIO18 exists on the C3 Mini but the V1 board routes the LED to GPIO9; GPIO9 was I2C SDA (BMP280 dropped for V1) |
| FEM `TX_EN` | GPIO19 | **-1 (disabled)** | GPIO19 does not exist on the ESP32-C3 Mini V1 (it is USB D+) |
| FEM `RX_EN` | GPIO0 | **-1 (disabled)** | GPIO0 is GPS UART TX — must never be driven by the FEM |
| BMP280 | enabled (`default y`) | **disabled (`default n`)** | SDA/SCL were GPIO8/GPIO9; GPIO9 is now the LED |
| Supercap ADC | always compiled | **`#ifdef SUPERCAP_MONITORING`** | `ADC1_CH0` = GPIO0 = GPS TX on the ESP32-C3 |

### 1.1 GPIO9 is a strapping pin — why the LED is wired the way it is

GPIO9 is the ESP32-C3 `BOOT` strapping input (sampled at reset; the chip must see
it HIGH for a normal SPI-boot). Putting the status LED here is only safe because
the V1 circuit is **`GPIO9 → R_LED (330 Ω) → LED anode → cathode → GND`** — the
LED is on the *low* side of the pin, so an idle/unconfigured GPIO9 sees R_LED in
series with the LED to ground: no pull-down strong enough to change the strap
level, and the pin is not driven at reset (the firmware only configures it as an
output inside `blink_led()`, and drives it **low** at the end of
`app_main()`'s radio path). A second consideration: the same net is shared with
the J1 programming header's `IO9(BOOT)` pin (`build_sch.py:625`), which is what
lets BOOT be asserted by an external programmer — that is a deliberate reuse of
the strap pin, not an accident.

The inverse wiring (anode to 3V3, cathode to the pin, i.e. "active-LOW LED"
as the older breadboard comment implies) WOULD be a real risk if the pin were
held low, so the V1 net order above is the contract. If the LED circuit is ever
re-spun, keep R_LED on the pin side and do not add a pull-down on the segment
between the pin and R_LED. (Verified against
`tracker/hardware/schematics/v_c3_rp2040/build_sch.py:210-223`.)

## 2. The ADC conflict (why supercap monitoring is off for V1)

`components/power_manager/power_manager.c` used `ADC_CHANNEL_0` on `ADC_UNIT_1`.
On the ESP32-C3, `ADC1_CH0` is **GPIO0**, which is also GPS UART TX. ADC is only
available on GPIO0–GPIO4, and every one of those pins is already allocated (GPS
RX/TX, LR2021 SPI, radio control). There is **no free ADC-capable pin on V1** —
so the divider is not populated and the ADC path is compiled out.

`SUPERCAP_MONITORING` is intentionally **not** defined anywhere in the tree, so
the ADC objects are absent from the image rather than merely "unused". V2
(ESP32-S3) re-arms it by defining the macro once a free ADC pin exists.

**The "no measurement" value is `POWER_MANAGER_MV_INVALID` (0xFFFF), not 0.**
An earlier cut returned literal `0` from the disabled stub and called the
low-voltage check "a no-op" — that is inverted: `0 < CONFIG_LOW_VOLTAGE_MV + 200`
is TRUE, so any consumer not itself compiled out would report LOW_POWER against
an unpopulated divider, and `telemetry_fill()` would still broadcast a
believable-but-wrong `voltage_mv = 0` (a ground station reading
`tracker/ground-station/ground_station.py` prints `Vcap:0mV`). 0xFFFF is outside
the divider's physical range (R1 = R2 = 1 MΩ ⇒ max 6600 mV) and above any
threshold, so it means "not measured" in both directions.

## 3. Exact changes

- `tracker/firmware/main/app_main.cpp`
  - `LED_GPIO` 18 → 9.
  - `cli_cmd_i2c_scan()` compiled out when `CONFIG_ENABLE_BMP280=n` (stub prints
    "I2C scan disabled (BMP280 dropped for V1 flight)").
  - Supercap logging + `TELEMETRY_FLAG_LOW_POWER` checks wrapped in
    `#ifdef SUPERCAP_MONITORING`; when disabled the log states monitoring is off
    for V1 instead of printing a meaningless `0 mV`.
  - `bmp280_init(&bmp, I2C_NUM_0, 8, 9, 400000)` kept inside the existing
    `CONFIG_ENABLE_BMP280` guard, with a comment that SCL must move off GPIO9 if
    BMP280 is ever re-enabled.
- `tracker/firmware/main/Kconfig.projbuild`
  - `ENABLE_BMP280` `default y` → `default n`.
  - `FEM_TX_PIN` `default 19` → `default -1`.
  - `FEM_RX_PIN` `default 0` → `default -1`.
  - Help text on both FEM pins explaining the C3 pinout constraint.
- `tracker/firmware/radio_test/main/main.cpp`
  - `LED_PIN` 8 → 9 (matches the tracker LED).
- `tracker/firmware/components/power_manager/power_manager.c`
  - Whole ADC path under `#ifdef SUPERCAP_MONITORING`; the `#else` branch keeps
    `power_manager_init()` / `power_manager_read_supercap_mv()` ABI-compatible.
  - The disabled branch returns `POWER_MANAGER_MV_INVALID` (0xFFFF), **not** 0 —
    see §2. The guarded branch now checks the return of every `adc_*` call:
    `adc_ready` is set only after a successful unit + channel init, a failed
    `adc_oneshot_read()` returns the sentinel, and a failed
    `adc_cali_create_scheme_curve_fitting()` falls back to raw scaling without
    latching readiness (so the next read retries rather than reading through a
    NULL handle).
- `tracker/firmware/components/power_manager/power_manager.h`
  - New `POWER_MANAGER_MV_INVALID` (0xFFFF) sentinel with the rationale above.
- `tracker/firmware/components/power_manager/test/test_power_manager_guard.c`
  - New host test asserting BOTH sides of the guard. Runs in
    `.github/workflows/ci-host-tests.yml` and
    `.ngit/act/workflows/host-tests.yml` (Suite 8) and as
    `TestPowerManager::test_power_manager_guard_v{1,2}` in `tests/test_c_host.py`.
  - It carries its own `test/stubs/esp_adc/*` (same type names as
    `tests/host_stubs/esp_adc/*`) because the shared ones are read-only
    `static inline` bodies and this suite has to script the failure paths.
- `tracker/firmware/sdkconfig` (TRACKED — `sdkconfig.defaults*` are only applied
  when `sdkconfig` is absent): `CONFIG_ENABLE_BMP280=y` →
  `# CONFIG_ENABLE_BMP280 is not set` (the canonical Kconfig spelling, so a
  build does not rewrite the tracked file).
- `tracker/firmware/sdkconfig.defaults.esp32s3`: **left at
  `CONFIG_ENABLE_BMP280=y`.** This file is the S3 bench variant, not the V1
  flight board; S3 boards still wire the sensor and the Kconfig help itself says
  "re-enable in V2 with a larger MCU (ESP32-S3)". The V1 decision lives in the
  tracked C3 `sdkconfig` + `main/Kconfig.projbuild` (`default n`).

## 4. Build verification (must be run for the C3 target)

The tracked `sdkconfig` in this repo is pinned to `CONFIG_IDF_TARGET="esp32s3"`
from the cross-platform build commit; `build/` is configured for `esp32c3`. To
build the C3 image **without disturbing the repo** (no rewrite of the tracked
`sdkconfig`, `build/`, or `dependencies.lock`):

```bash
sed 's/CONFIG_IDF_TARGET="esp32s3"/CONFIG_IDF_TARGET="esp32c3"/' \
    tracker/firmware/sdkconfig > /tmp/sdkconfig-c3
python3 $IDF_PATH/tools/idf.py -B ~/altbuild-t807 -DSDKCONFIG=/tmp/sdkconfig-c3 build
```

Note: `riscv32-esp-elf` must be on `PATH` for a C3 build — `source
~/esp/esp-idf/export.sh` aborts on this host (see
`esp-idf-build-verify-tracker` skill), and the manual env needs the **riscv**
toolchain dir, not the xtensa one.

Result (V1 image, `esp32c3`):

```
balloon-tracker.bin binary size 0x44410 bytes.
Smallest app partition is 0x100000 bytes. 0xbbbf0 bytes (73%) free.
Project build complete.
```

## 5. Gate evidence

- LED on GPIO9: `main/app_main.cpp:85` (`#define LED_GPIO 9`) and
  `radio_test/main/main.cpp:52` (`#define LED_PIN 9`).
- FEM disabled: `CONFIG_ENABLE_FEM` unset in `sdkconfig`; `FEM_TX_PIN`/`FEM_RX_PIN`
  default `-1`; `sky66112_init()` stays behind `#ifdef CONFIG_ENABLE_FEM`.
- ADC guarded: `SUPERCAP_MONITORING` is not defined anywhere in the tree;
  `riscv32-esp-elf-nm balloon-tracker.elf | grep -i 'adc_oneshot\|adc_cali'`
  returns **no symbols** (the ADC driver objects are not linked in).
- GPS TX unaffected: the only reference to GPIO0 in the firmware is the
  *comment* in `power_manager.c` explaining the conflict — no code drives GPIO0.
  GPS itself is off by default (`ENABLE_GPS` unset, `GPS_UART_TX_PIN=-1`).
- Host unit tests: `83 passed, 0 failed` (tollgate proto) and `12/12 passed`
  (relay pipeline).
