# ESP32-C3 SuperMini Bring-up Fixes

**Board**: ESP32-C3 SuperMini V1 (4MB XMC flash, detected at `/dev/ttyACM1`)
**Date**: 2026-05-24
**Status**: SPI HAL fixed, radio init hang debugging in progress

## Problems Found

### P0: USB-Serial/JTAG forces download mode on software reset (HIGH PRIORITY)

- **Symptom**: After `idf.py flash` or `esptool run`, chip enters `boot:0x6 (DOWNLOAD)` instead of booting firmware. Only power cycle (unplug/replug USB) boots into `boot:0xe (SPI_FAST_FLASH_BOOT)`.
- **Root cause**: ESP32-C3 USB-Serial/JTAG controller forces download mode on any reset initiated via USB (DTR/RTS toggle). This is by design for programming. Additionally, GPIO8 (shared with onboard LED, active-LOW) may have a pull-up through the LED resistor that contributes to strapping pin state.
- **Impact**: Every flash cycle requires manual USB unplug/replug. Cannot use `idf.py monitor` or any automated reset-to-run workflow.
- **Long-term fix (HARDWARE)**: Solder a **10k pull-down resistor between GPIO8 and GND** on the dev board. This overrides the LED pull-up at reset, ensuring GPIO8=LOW → SPI boot mode even after USB-initiated resets. Place the resistor close to the GPIO8 pin.
- **Alternative fix (SOFTWARE)**: Move I2C SDA from GPIO8 to a non-strapping pin (e.g., GPIO1, GPIO19, GPIO20). This would require PCB respin for flight boards but is viable for the dev board with jumper wires.
- **Workaround**: Manual USB unplug/replug after every flash. The firmware's 2-second boot delay (`vTaskDelay` in `app_main`) ensures USB console is ready before printing.
- **Status**: Documented, awaiting hardware fix

### P1: Flash size mismatch (bootloop)
- **Symptom**: `partition 3 invalid - offset 0x150000 size 0x140000 exceeds flash chip size 0x200000`
- **Cause**: `sdkconfig` has `CONFIG_ESPTOOLPY_FLASHSIZE_2MB=y` but chip has 4MB XMC flash
- **Fix**: Set `CONFIG_ESPTOOLPY_FLASHSIZE_4MB=y` in `sdkconfig.defaults`
- **Status**: Fixed

### P2: esp_pm_configure crash (abort loop)
- **Symptom**: `ESP_ERROR_CHECK failed: esp_err_t 0x106 (ESP_ERR_NOT_SUPPORTED)` at `app_main.cpp:389`
- **Cause**: `CONFIG_PM_ENABLE=y` but PM config not fully supported on this board variant
- **Fix**: Made `esp_pm_configure()` non-fatal (log warning instead of abort)
- **Status**: Fixed

### P3: Console on UART instead of USB-Serial/JTAG
- **Symptom**: No serial output on `/dev/ttyACM1` despite firmware running
- **Cause**: `sdkconfig` had `CONFIG_ESP_CONSOLE_UART_DEFAULT=y` (primary console on UART0 GPIO21/GPIO20, which aren't connected on SuperMini). USB-Serial/JTAG was only secondary console.
- **Fix**: Changed to `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y` in `sdkconfig`. Required editing the stale `sdkconfig` file directly (sdkconfig.defaults only applies when no sdkconfig exists).
- **Status**: Fixed

### P4: CPU frequency at 160 MHz instead of 80 MHz
- **Symptom**: `cpu freq: 160000000 Hz` instead of target 80 MHz
- **Cause**: `sdkconfig` had `CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ_160=y` overriding `sdkconfig.defaults`
- **Fix**: Changed to 80 MHz in `sdkconfig`
- **Status**: Fixed

### P5: Low voltage threshold blocking radio init
- **Symptom**: `Low voltage (1530 mV < 3300), skipping TX` — radio init never attempted
- **Cause**: ADC on GPIO0 reads ~1530 mV on USB power (not a real supercap). The 3300 mV threshold is designed for supercap-powered flight boards.
- **Fix**: Temporarily set `CONFIG_LOW_VOLTAGE_MV=1000` for bench testing
- **Status**: Temporary workaround for dev board

### P6: SPI transfer hangs (LR2021 radio init)
- **Symptom**: `while(this->spi->cmd.usr)` never completes in `EspHalC3::spiTransferByte()`. Task watchdog triggers after 5 seconds.
- **Investigation**: BUSY pin (GPIO4) goes LOW after reset — LR2021 module IS alive and responding. The SPI peripheral itself appears stuck (USR bit never clears).
- **Partial fix**: Added `periph_module_reset()` and proper `slave.val=0`, `misc.val=0` register resets to `EspHalC3::spiBegin()`. Removed invalid `pin` register access (doesn't exist on ESP32-C3, `ck_idle_edge` is in `misc` register).
- **Status**: Under investigation — may need to switch to ESP-IDF SPI master driver instead of raw register access

## Board Detection

| Port | Chip | Flash | MAC | Purpose |
|------|------|-------|-----|---------|
| `/dev/ttyACM0` | ESP32-S3 | — | — | TollGate router |
| `/dev/ttyACM1` | ESP32-C3 (v0.4) | 4MB XMC | `b0:a6:04:00:96:dc` | LoRa2021 test board |

## Checklist

- [x] Detect ESP32-C3 on `/dev/ttyACM1`
- [x] Flash firmware (partition table fix from single-app)
- [x] Fix `sdkconfig`: flash size 4MB, console on USB-Serial/JTAG, CPU 80 MHz
- [x] Fix `app_main.cpp`: make `esp_pm_configure()` non-fatal
- [x] Fix `EspHalC3.h`: correct register resets for ESP32-C3 SPI
- [x] Verify boot without crashes — boots OK via power-on reset
- [x] Verify USB console output on `/dev/ttyACM1`
- [x] Verify LR2021 BUSY pin responds to reset (GPIO4 = HIGH → LOW after RST toggle)
- [ ] **HARDWARE FIX: Add 10k pull-down on GPIO8 to fix USB boot mode issue**
- [ ] Fix SPI transfer hang (raw SPI or switch to ESP-IDF driver)
- [ ] Verify LoRa2021 radio init succeeds
- [ ] Test LoRa TX/RX
- [ ] Commit and push fixes

## Key Files
- `tracker/firmware/sdkconfig.defaults` — Flash size, CPU freq, PM config
- `tracker/firmware/sdkconfig` — Auto-generated, needs edit when defaults change
- `tracker/firmware/main/app_main.cpp` — PM fix, 2s boot delay, SPI debug code
- `tracker/firmware/main/EspHalC3.h` — SPI HAL (register-level, needs ESP-IDF driver migration)
