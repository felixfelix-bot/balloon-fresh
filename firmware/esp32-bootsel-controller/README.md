# ESP32-C3 RP2040 BOOTSEL/RUN Controller — test firmware

Interactive test firmware that drives an RP2040's **RUN** and **BOOTSEL (GP0)**
pads from an ESP32-C3 over GPIO, so a soldered auto-BOOTSEL circuit can be
exercised without touching the board: reset it, force USB bootloader mode, and
watch it for liveness.

This is the firmware for validating the soldered circuit. Whether a *particular*
soldered harness works end-to-end is verified by `balloon:t_33db8c37` with both
boards on a desk — the tests here are host-side only and need no hardware.

## Hardware

| ESP32-C3 | Direction | RP2040 | Notes |
|---|---|---|---|
| GPIO1 (D1) | → | RUN button pad (3V3 signal side) | reset, active LOW |
| GPIO8 (D8) | → | BOOTSEL / GP0 button pad (3V3 signal side) | bootloader select, active LOW |
| GND | ↔ | GND | common ground, required |

```
ESP32-C3                        RP2040
+--------+                     +----------------------+
| GPIO1  +---- direct wire ----+ RUN  button pad (3V3)|
| GPIO8  +---- direct wire ----+ GP0  button pad (3V3)|
| GND    +-------------------- + GND                  |
+--------+                     +----------------------+
```

**No series resistors, no external pull-ups.** A 1 kΩ series resistor with the
board's pull-up forms a divider and parks the pad at ~1.65 V — above the RP2040's
0.8 V guaranteed-LOW threshold and below its HIGH threshold, i.e. no-man's-land.
The ESP32 driver sinks far more than the pull-up sources, so a direct wire
overpowers it. Each button has two pads: solder to the **3V3 signal side**, not
the GND side (verify ~3.3 V with a multimeter; it must drop to 0 V when pressed).

`GPIO8` is an **ESP32-C3 strapping pin**, sampled at power-on. The RP2040's GP0
idles HIGH via its internal pull-up, which is the safe level; if the target ever
holds GPIO8 LOW while the ESP32 boots, the ESP32 enters download mode instead of
running this firmware (no heartbeat LED, no command acks).

## Build & flash

```bash
cd firmware/esp32-bootsel-controller
pio run -e esp32c3

# pio upload can fail on these boards ("Invalid head of packet"); esptool direct:
python3 -m esptool --port /dev/ttyACMX --chip esp32c3 --baud 460800 \
  --before default_reset --after hard_reset write_flash 0x0 \
  .pio/build/esp32c3/firmware.bin
```

Do **not** set `ARDUINO_USB_MODE=1` / `ARDUINO_USB_CDC_ON_BOOT=1` — they break the
console on this board.

Other environments:

| env | purpose |
|---|---|
| `esp32c3` | interactive controller (default) |
| `esp32c3-diag` | toggles the pins at visible rates for multimeter checks of the soldered pads |
| `esp32c3-loop` | blind loop trigger: full BOOTSEL sequence every 5 s, for recovering an RP2040 whose USB CDC is dead |

## Serial commands

Single letter, optionally with a trailing CR/LF. Commands are matched **exactly**
— a line that merely starts with a command letter is an error, because these
commands move hardware.

| command | long alias | action |
|---|---|---|
| `r` | `reset` | pulse RUN LOW for 100 ms → RP2040 restarts with its existing flash image |
| `b` | `bootsel` | full entry sequence → RP2040 enumerates as RPI-RP2 mass storage |
| `s` | `status` | one `STAT …` line: pin levels, event counters, watchdog state |
| `w on` / `w off` | — | enable/disable the heartbeat watchdog (default OFF) |
| `h` | `hb` | record an RP2040 heartbeat (for a host that forwards HB lines) |

A `STAT …` line is also emitted every second, so a host sees the controller is
alive without polling. `RESET` / `BOOTSEL` / `STATUS` are the words the older
`enhanced_board_watcher.sh` already sends, and still work.

### Read this before blaming the wiring: serial on 303a:1001

The ESP32-C3 SuperMini "USB JTAG/serial debug unit" (VID 303a:1001) has a broken
console: `Serial.print()` emits zero bytes and `Serial.available()` never returns
true, measured across 10+ reflashes and both cores. This firmware therefore
accepts the same commands on the **hardware UART** as well:

```
UART0  TX = GPIO21, RX = GPIO20, 115200 8N1
```

Drive it from a USB-serial adapter, or from the RP2040's own UART bridge. When
the USB CDC console does work (other board revisions), it works too.

## BOOTSEL entry sequence (order-critical)

```
1. GP0 LOW                           bootloader mode selected
2. hold   50 ms                      settle
3. RUN LOW                          reset the RP2040 while GP0 is held LOW
4. hold  100 ms                      RUN LOW: >= 1 us required, 100 ms verified
5. RUN HIGH                          release reset -> boots into the bootloader
6. hold  500 ms                      RP2040 samples GP0 during early boot
7. GP0 HIGH                          internal pull-up keeps it HIGH
-> USB 2e8a:0003, RPI-RP2 mass storage appears
```

Two ways to get this wrong, both previously shipped as bugs: driving GP0 **HIGH**
to select the bootloader (it is the opposite), and releasing GP0 before the
RP2040 has sampled it (it boots the flash image instead). The host suite pins both
down, along with every delay above.

## Heartbeat watchdog

Off by default. When enabled (`w on`), silence from the RP2040 for
`BOOTSEL_WD_DEFAULT_MS` (8000 ms) triggers **one** recovery per episode: a RUN
pulse, i.e. a hardware reset.

Two deliberate constraints:

* It resets, it never enters the bootloader. An RP2040 parked in the bootloader
  at altitude has no USB host to hand it a UF2, so it is unrecoverable — whereas
  a reset restores a running board with its existing firmware. On the flight
  board this is the only flight-critical function of this circuit.
* It is inert until it has seen at least one heartbeat. Absence of evidence is
  not evidence of a hang, and a controller that cannot observe the RP2040 must
  not reset it on a guess. The shipped configuration keeps this firmware off the
  RP2040's serial path (the UART bridge has it) — that is why the default is OFF.

After a reset, liveness must be re-proven before the watchdog may act again; a
`h` (or a forwarded heartbeat) re-arms it.

## Verifying the firmware

```bash
python3 -m pytest tests/test_bootsel_controller.py -q
```

The suite compiles `src/bootsel_controller.cpp` — the same translation unit the
board runs — into `tests/src/ser_io_host.cpp` with recording stubs and asserts on
the observed pin trace, timings, ack strings and watchdog behaviour, then checks
the flashable sources and this README still carry the same contract. No hardware,
no serial port. It caught a real defect on first run: the parser accepted any
line starting with a command letter, so `BL` force-entered the bootloader.

What it does not prove: that a soldered harness conducts. That is
`balloon:t_33db8c37`.

## Recovery paths that do not need this ESP32

* **1200 baud on the RP2040 directly** (needs the earlephilhower core, PID 000a):
  `python3 -c "import serial; s=serial.Serial('/dev/ttyACM0', 1200, timeout=1); s.close()"`
  If the firmware starves USB CDC, use `dtr=False, rts=False` before `open()`.
* **Physical BOOTSEL + USB replug** — always works, no prerequisites.

## Related

* `firmware/esp32-c3-bootsel-controller/` — the older project (one-shot and
  watcher-script variants); superseded by this one.
* skill `esp32-rp2040-bootsel-control` — pin logic, pad identification, the full
  troubleshooting history.
* `HARDWARE_CONNECTIONS.md`, `docs/FLIGHT-BOARD-AUTO-BOOTSEL.md` — soldering and
  circuit theory.
