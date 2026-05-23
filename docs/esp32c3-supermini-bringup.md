# ESP32-C3 SuperMini Bring-up Fixes

**Board**: ESP32-C3 SuperMini V1 (4MB XMC flash, detected at `/dev/ttyACM1`)
**Date**: 2026-05-24
**Status**: Fixing pre-existing sdkconfig issues, then verifying LoRa2021 wiring

## Problems Found

### P1: Flash size mismatch (bootloop)
- **Symptom**: `partition 3 invalid - offset 0x150000 size 0x140000 exceeds flash chip size 0x200000`
- **Cause**: `sdkconfig` has `CONFIG_ESPTOOLPY_FLASHSIZE_2MB=y` but chip has 4MB XMC flash
- **Fix**: Set `CONFIG_ESPTOOLPY_FLASHSIZE_4MB=y` in `sdkconfig.defaults`
- **Status**: Fixed in previous clean build (partition table reverted to single-app), but flash size still wrong

### P2: esp_pm_configure crash (abort loop)
- **Symptom**: `ESP_ERROR_CHECK failed: esp_err_t 0x106 (ESP_ERR_NOT_SUPPORTED)` at `app_main.cpp:389`
- **Cause**: `CONFIG_PM_ENABLE=y` but PM config not fully supported on this board variant
- **Fix**: Make `esp_pm_configure()` non-fatal (log warning instead of abort)

### P3: Deprecated CPU freq config (warnings)
- **Symptom**: `warning: unknown kconfig symbol 'ESP_SYSTEM_DEFAULT_CPU_FREQ_80'`
- **Cause**: ESP-IDF v5.4.1 renamed these symbols
- **Fix**: Remove deprecated options from `sdkconfig.defaults`, use correct v5.4 names

### P4: Actual flash is 4MB but reported as 2MB
- **Symptom**: `Detected size(4096k) larger than the size in the binary image header(2048k)`
- **Fix**: Set flash size to 4MB to match actual hardware

## Board Detection

| Port | Chip | Flash | MAC | Purpose |
|------|------|-------|-----|---------|
| `/dev/ttyACM0` | ESP32-S3 | — | — | TollGate router |
| `/dev/ttyACM1` | ESP32-C3 (v0.4) | 4MB XMC | `b0:a6:04:00:96:dc` | LoRa2021 test board |

## Checklist

- [x] Detect ESP32-C3 on `/dev/ttyACM1`
- [x] Flash firmware (partition table fix from single-app)
- [ ] Fix `sdkconfig.defaults`: flash size 4MB, remove deprecated symbols
- [ ] Fix `app_main.cpp`: make `esp_pm_configure()` non-fatal
- [ ] Clean build + flash to `/dev/ttyACM1`
- [ ] Verify boot without crashes
- [ ] Verify LoRa2021 radio init (SPI communication)
- [ ] If radio init OK → wiring confirmed correct
- [ ] If radio init FAIL → check soldering, pin mapping
- [ ] Commit and push fixes

## Key Files
- `tracker/firmware/sdkconfig.defaults` — Flash size, CPU freq, PM config
- `tracker/firmware/sdkconfig` — Auto-generated, needs `rm` + rebuild after defaults change
- `tracker/firmware/main/app_main.cpp:389` — `esp_pm_configure()` crash location
