# RP2040 BOOTSEL & Flashing Guide

## Overview

Both RP2040 boards can be put into BOOTSEL mode and reflashed entirely from software — no physical button press required. This was verified end-to-end on 2026-07-15.

## Board Inventory

| Board | RP2040 Serial | USB PID | Port (ACM) | ESP32 Serial | ESP32 Port |
|-------|--------------|---------|------------|--------------|------------|
| Set 1 (RX) | E663B035973B8332 | 000a | ACM0 | 70:AF:09:13:21:00 | ACM1 |
| Set 2 (TX) | E663B035977F242D | 000a | ACM2 | 70:AF:09:21:FB:18 | ACM3 |

PID 000a = earlephilhower core (USB CDC works, 1200 baud BOOTSEL works).
PID 00c0 = mbed core (USB CDC broken, 1200 baud does NOT work).

Both boards are currently running earlephilhower core. They will never need PID 00c0 again.

## Primary Method: 1200 Baud BOOTSEL

This is the ONLY reliable method. Works on any RP2040 running earlephilhower core.

### Quick Commands

All commands run from `~/repos/balloon-fresh/firmware/`:

```bash
# List all connected devices
make devices

# Put RP2040 into BOOTSEL mode (no physical button)
make bootsel-1200 PORT=/dev/ttyACM0   # board 1 (8332)
make bootsel-1200 PORT=/dev/ttyACM2   # board 2 (F242D)

# Full flash cycle: BOOTSEL → mount → copy UF2 → reboot
make rp2040-flash ENV=rp2040-uart-test PORT=/dev/ttyACM0
make rp2040-flash ENV=rp2040-uart-test PORT=/dev/ttyACM2

# Reset RP2040 (normal reboot, no BOOTSEL)
make rp2040-reset PORT=/dev/ttyACM0
```

### How It Works

1. Opening serial port at 1200 baud signals RP2040 USB CDC to reboot into BOOTSEL.
2. RP2040 disconnects, re-enumerates as PID 0003 (RP2 Boot mode).
3. RPI-RP2 mass storage drive appears (128MB FAT).
4. Makefile polls for `/dev/disk/by-label/RPI-RP2` for up to 10 seconds.
5. UF2 file is copied to the drive — RP2040 auto-reboots with new firmware.

### Timing

- 1200 baud trigger to RPI-RP2 visible: 4-6 seconds
- Full flash cycle (trigger + copy + reboot): ~15 seconds per board
- Both boards back-to-back: ~30 seconds total

## Firmware Environments

Available PlatformIO environments in `firmware/rp2040/platformio.ini`:

| ENV | Purpose |
|-----|---------|
| rp2040-uart-test | UART echo with heartbeat (serial verification) |
| rp2040-flrc-rx | FLRC receiver firmware |
| rp2040-flrc-tx | FLRC transmitter firmware |

Build only (no flash):
```bash
make rp2040-build ENV=rp2040-flrc-rx
```

## ESP32 GPIO BOOTSEL Circuit — DOES NOT WORK

The ESP32-C3 → RP2040 GPIO BOOTSEL circuit was tested extensively across
2026-07-12 to 2026-07-15. Despite verified wiring (multimeter continuity confirmed,
correct button pad side, no series resistors), the circuit never triggered BOOTSEL
reliably on either board set.

Root causes investigated:
1. ESP32-C3 SuperMini USB JTAG serial cannot receive input → commands never arrive
2. ESP-IDF dual app_main bug (bootsel_ctrl.cpp had no #ifdef guard)
3. GPIO8 NeoPixel/LED circuit possible interference
4. Possible pin mapping mismatch on SuperMini clones

**Status: Abandoned. 1200 baud is the primary and only method.**

The ESP32 GPIO circuit remains soldered on both boards but is not used.
The ESP32s are still connected and available for UART bridge or other tasks.

## One-Time Setup: Flashing earlephilhower Core

If a board arrives with mbed core (PID 00c0, CDC dead), you need ONE physical
BOOTSEL to flash earlephilhower firmware. After that, 1200 baud works forever.

1. Unplug RP2040 USB
2. Press and HOLD BOOTSEL button
3. Plug USB back in while holding
4. Release after 3 seconds
5. RPI-RP2 drive appears
6. Flash earlephilhower UF2:
   ```bash
   make rp2040-flash ENV=rp2040-uart-test PORT=/dev/ttyACMX
   ```
7. Done — never need physical BOOTSEL again

## Troubleshooting

### "ERROR: 1200 baud failed — RPI-RP2 never appeared"

1. Check RP2040 PID: `udevadm info -q property /dev/ttyACMX | grep ID_MODEL_ID`
   - PID 000a → earlephilhower, 1200 baud should work
   - PID 00c0 → mbed core, need one-time physical BOOTSEL (see above)
2. Check device is still connected: `make devices`
3. Try again — sometimes udev is slow on first attempt
4. If port disappeared entirely: `fuser -k /dev/ttyACMX`, then unplug/replug

### Serial output is empty

1. Check PID is 000a (earlephilhower). PID 00c0 has broken CDC.
2. Add heartbeat in loop() — Serial.println in setup() may fire before host connects.
3. Remove `-D RP2040` from build_flags (collides with earlephilhower class name).

### Wrong board gets flashed

When both RP2040s are in BOOTSEL simultaneously, only one RPI-RP2 is visible at a
time (same disk label). Flash them one at a time:
```bash
make bootsel-1200 PORT=/dev/ttyACM0   # board 1 only
make rp2040-flash ENV=xxx PORT=/dev/ttyACM0
# wait for board 1 to reboot...
make bootsel-1200 PORT=/dev/ttyACM2   # board 2
make rp2040-flash ENV=xxx PORT=/dev/ttyACM2
```

## Serial Monitor

```bash
# Monitor RP2040 serial output (115200 baud)
make rp2040-monitor MONITOR_PORT=/dev/ttyACM0

# Monitor ESP32 (limited — USB JTAG output is broken on 303a:1001)
make esp32-monitor PORT=/dev/ttyACM1
```

## UART Bridge (Separate from BOOTSEL)

The UART bridge is independent of the BOOTSEL circuit:

| Function | RP2040 Pins | ESP32 Pins | Purpose |
|----------|-------------|------------|---------|
| UART Bridge | GP12 (TX0), GP13 (RX0) | GPIO0, GPIO1 | Read RP2040 serial data via ESP32 |
| BOOTSEL (unused) | RUN, GP0 | GPIO1, GPIO8 | Failed — abandoned |

GP12/GP13 are top-side pins, accessible when RP2040 is soldered to carrier board.
GP17-GP25 are backside and physically inaccessible.

## File Locations

| File | Purpose |
|------|---------|
| `firmware/Makefile` | All make targets |
| `firmware/rp2040/platformio.ini` | RP2040 build environments |
| `firmware/rp2040/src/uart_echo.cpp` | UART echo test firmware |
| `firmware/esp32-bootsel-controller/` | Standalone ESP32 BOOTSEL firmware (unused) |
| `firmware/esp32-c3-bootsel-controller/` | Older ESP32 BOOTSEL firmware (unused) |

## Verification History

- 2026-07-13: Circuit verified working on board set 1 (with series resistors removed)
- 2026-07-15: Both boards flashed earlephilhower core, 1200 baud proven end-to-end
  - Board 1 (8332/ACM0): bootsel-1200 → 5s → flash → serial OK
  - Board 2 (F242D/ACM2): bootsel-1200 → 4s → flash → serial OK
  - Zero physical access required
