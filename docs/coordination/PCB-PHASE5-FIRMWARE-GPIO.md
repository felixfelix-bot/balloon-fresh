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

## 2. The ADC conflict (why supercap monitoring is off for V1)

`components/power_manager/power_manager.c` used `ADC_CHANNEL_0` on `ADC_UNIT_1`.
On the ESP32-C3, `ADC1_CH0` is **GPIO0**, which is also GPS UART TX. ADC is only
available on GPIO0–GPIO4, and every one of those pins is already allocated (GPS
RX/TX, LR2021 SPI, radio control). There is **no free ADC-capable pin on V1** —
so the divider is not populated and the ADC path is compiled out.

`SUPERCAP_MONITORING` is intentionally **not** defined anywhere in the tree, so
the ADC objects are absent from the image rather than merely "unused". V2
(ESP32-S3) re-arms it by defining the macro once a free ADC pin exists.

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
    `power_manager_init()` / `power_manager_read_supercap_mv()` ABI-compatible
    and returns `0` mV so the low-voltage check is a no-op.
  - `adc_ready` replaces the `adc_handle` null-check that guarded the read path.
- `tracker/firmware/sdkconfig` (TRACKED — `sdkconfig.defaults*` are only applied
  when `sdkconfig` is absent): `CONFIG_ENABLE_BMP280=y` → `=n`.
- `tracker/firmware/sdkconfig.defaults.esp32s3`: same flag, for the S3 variant.

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
