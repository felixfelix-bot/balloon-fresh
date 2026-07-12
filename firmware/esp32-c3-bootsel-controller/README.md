# ESP32 RP2040 BOOTSEL Controller

> **VERIFIED WORKING (2026-07-13)** — Full flash pipeline tested.
> Commit e9102be. Direct wire connection, zero resistors.

## Overview

This ESP32-C3 firmware provides programmatic control over RP2040 BOOTSEL mode,
enabling automated testing, recovery, and firmware flashing without physical
button presses.

## Hardware Configuration (VERIFIED WORKING)

### Pin Mapping

| ESP32-C3 Pin | Via | RP2040 Button Pad | Resistors |
|-------------|-----|-------------------|-----------|
| GPIO1 (D1) | DIRECT WIRE | RESET button (3V3 side) | NONE |
| GPIO8 (D8) | DIRECT WIRE | BOOTSEL button (3V3 side) | NONE |
| GND | DIRECT WIRE | GND | NONE |

### Wiring Diagram

```
ESP32-C3                      RP2040
+-------+                    +-------------------+
|       |                    |                   |
| GPIO1 +--------------------+ RESET button pad  | (3V3 signal side)
|  (D1) |   direct wire      |                   |
+-------+                    +-------------------+
|       |                    |                   |
| GPIO8 +--------------------+ BOOTSEL button pad| (3V3 signal side)
|  (D8) |   direct wire      |                   |
+-------+                    +-------------------+
|       |                    |                   |
| GND   +--------------------+ GND               |
+-------+                    +-------------------+
```

**NO series resistors. NO external pull-up resistors.**
The RP2040 button pads have internal pull-ups to 3V3. Direct wire connection
lets the ESP32 output driver pull the pad to true 0V, overpowering the
internal pull-up. Previous designs used 1kOhm series resistors which created
a voltage divider preventing the signal from reaching logic LOW threshold.

### CRITICAL: Button Pad Selection

Each button has TWO pads — signal (3V3) and GND (0V).
Solder to the 3V3 signal side ONLY. Use multimeter to verify (~3.3V idle).

## Build & Flash

```bash
cd ~/repos/balloon-fresh/firmware/esp32-c3-bootsel-controller
pio run -e esp32-c3-bootsel-controller -t upload --upload-port /dev/ttyACM0
```

### Board Config
- Board ID: `esp32-c3-devkitm-1` (works with raw GPIO numbers)
- Do NOT use `esp32c3_supermini` — not in PlatformIO board registry
- Do NOT set `ARDUINO_USB_MODE=1` or `ARDUINO_USB_CDC_ON_BOOT=1` — breaks serial

## How It Works

### BOOTSEL Trigger Sequence (Verified)

```
1. Hold D8 (BOOTSEL) LOW           <- GP0 LOW = bootloader mode selected
2. Wait 50ms for stabilization
3. Pulse D1 (RESET) LOW for 100ms  <- reset RP2040
4. Release D1 (drive HIGH)         <- RP2040 starts booting
5. Hold D8 LOW for 500ms           <- RP2040 samples BOOTSEL during early boot
6. Release D8 (drive HIGH)         <- internal pull-up keeps it HIGH

Result: RP2040 appears as RPI-RP2 mass storage (USB VID 2e8a, PID 0003)
```

### Current Firmware: Auto-BOOTSEL on Boot

The current firmware (main.cpp) automatically triggers the BOOTSEL sequence
3 seconds after ESP32 boot. This is a one-shot test firmware. Production
firmware should use serial commands or watchdog-based triggering.

## Flashing RP2040 Once in BOOTSEL

```bash
# After ESP32 triggers BOOTSEL, RP2040 appears as mass storage
udisksctl mount --block-device /dev/sdb1
cp ~/repos/rp2040-usb-alive/.pio/build/rp2040/firmware.uf2 /run/media/$USER/RPI-RP2/
sync
# RP2040 auto-reboots after UF2 copy
```

## Fallback Methods

### 1200 Baud BOOTSEL (works when USB CDC is alive)
```bash
stty -F /dev/ttyACM1 1200
sleep 2
# RP2040 enters bootloader mode
```

### Physical BOOTSEL + USB replug (last resort, works on dead USB CDC)
1. Unplug RP2040 USB
2. Press and hold BOOTSEL button
3. Plug USB back in
4. RPI-RP2 drive appears

## Troubleshooting

### RP2040 Not Responding to GPIO Pulses

1. **Are there series resistors in the wires?** REMOVE THEM. (Root cause #1)
2. **Are you on the correct button pad?** Check with multimeter (3V3 signal side)
3. **Is GND connected between both boards?** Check continuity
4. **Is ESP32 firmware running?** Check with host USB monitor (lsusb)

### ESP32-C3 Serial Not Working

The ESP32-C3 SuperMini (VID 303a:1001) has broken Arduino Serial output.
Do NOT rely on serial for debugging. Use host-side USB monitoring instead:
```bash
lsusb | grep 2e8a  # Watch for RP2040 PID changes
```

## References

- `docs/FLIGHT-BOARD-AUTO-BOOTSEL.md` — Circuit design and theory
- `HARDWARE_CONNECTIONS.md` — Detailed soldering instructions
- Skill: `esp32-rp2040-bootsel-control` — Full troubleshooting guide
