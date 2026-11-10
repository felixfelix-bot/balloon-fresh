# SPEC — Balloon pre-stretch pressure rig board (v1)

**Status:** SPEC, 2026-11-10. Nothing built yet. No board, netlist or schematic existed before this.
**Operator directive:** *"design around the esp32-s3, not c3"* and *"pressure will leak out so we can
just run the pump to maintain the pressure without needing a release valve."*

## What this board does

Reads balloon pressure and holds a target pressure by switching a pump. No relief valve — the
envelope leaks, so pressure control is one-directional: pump ON when below target, OFF when at or
above it.

```
        +12V ──[Q1 MOSFET]── Pump ── GND
                  │
              flyback D1
                  │
         ESP32-S3 ──gate── (3V3 logic)
              │
         I2C ── BMP280 (pressure + temperature)
              │
         USB-C ── 5V in + native USB-Serial-JTAG (no bridge chip)
```

## Why these choices

| choice | reason |
|---|---|
| **ESP32-S3-WROOM-1U** | operator directive. Same MCU as the hub and v11, so one toolchain, one flashing procedure, and the BMP280 driver lifts straight into flight firmware. |
| **No release valve** | operator: the envelope leaks, so the pump alone can hold pressure. Removes a part, a failure mode and a GPIO. |
| **BMP280 over I2C** | existing firmware targets it. I2C needs 2 pins and no timing discipline. |
| **USB-C with native USB-Serial-JTAG** | the S3 flashes over its own USB with no CH340/CP2102 bridge — measured on the hub, `docs/analysis/FLASHING-V10.md`. Removes a part and a driver. |
| **12 V pump rail** | bench supply; the pump is the only high-current load, kept on its own rail so a pump stall cannot brown out the MCU. |

## Parts list (15 lines)

| # | ref | part | why |
|---|---|---|---|
| 1 | `U1` | ESP32-S3-WROOM-1U (`C2980300`) | MCU, USB-Serial-JTAG, 3.3 V |
| 2 | `U2` | BMP280 LGA-8 (`C8322`) | pressure + temperature |
| 3 | `U3` | TPS7A0233DBVR (`C5142805`) | 3.3 V LDO, 200 mA, same part as the hub |
| 4 | `Q1` | IRLML6344-class logic-level MOSFET | pump low-side switch |
| 5 | `D1` | SS24 (`C50645`) | pump flyback |
| 6 | `D2` | BAT54 (`C699107`) | reverse-polarity protection on 12 V in |
| 7-9 | `C1`-`C3` | 10 µF / 100 nF / 1 µF | MCU + sensor decoupling |
| 10 | `C4` | 100 µF 1206 | pump-rail bulk |
| 11 | `J1` | USB-C receptacle | 5 V in + USB data |
| 12 | `J2` | 2-pin screw terminal | pump output |
| 13 | `J3` | 2-pin screw terminal | 12 V in |
| 14-15 | `R1`, `R2` | 5.1 kΩ ×2 | USB-C CC1/CC2 pulldowns |

Total ~15 parts. **No RF, no stackup discipline, no controlled impedance** — this is the simplest
board in the project, which is why it goes first.

## Pin plan (must be written before layout, not after)

| signal | S3 pin | note |
|---|---|---|
| `I2C_SDA` | GPIO8 | BMP280 data |
| `I2C_SCL` | GPIO9 | BMP280 clock |
| `PUMP_EN` | GPIO4 | gate drive via 100 Ω |
| `PRESS_ADC` | — | not used; BMP280 is digital |
| `USB_D-/D+` | GPIO19/20 | fixed by the S3, native USB |

**Deliberately no GPIO0 / GPIO45 / GPIO46 usage** — strapping pins, and the hub already learned that
lesson (`/IO0` was a single-pad net for weeks).

## Control law (firmware, not board — recorded so the board supports it)

```
target_kpa = commanded over USB serial
loop:
    p = bmp280.read_pressure()
    if p < target - hysteresis:   PUMP_EN = 1
    elif p >= target:             PUMP_EN = 0
    log(t, p, PUMP_EN)
```

Hysteresis is required: without it the pump chatters at the setpoint and the log is unreadable.
The board does not need to know the value.

## Board

- **2 layers**, 0.8 mm, no controlled impedance
- Estimated **60 × 40 mm** — two screw terminals and a USB-C need edge room
- Assembly: **JLC places everything**, Standard PCBA (the S3 module has a **3.90 × 3.90 mm thermal
  pad underneath** — measured on the hub — which cannot be hand-soldered without hot air; this is
  the settled reason the operator is not hand-fitting S3 modules)

## What this board deliberately does NOT have

- **No relief valve** (operator decision — the envelope leaks)
- **No display** — logging is over USB
- **No battery** — bench powered
- **No RF** — this is not a flight board
- **No pressure sensor redundancy** — one BMP280; a second would be a v2 question

## Open questions before layout

1. **Pump voltage and current.** Not recorded anywhere. A 12 V diaphragm pump draws 300-600 mA;
   a 5 V one 200-400 mA. This decides MOSFET choice, bulk capacitance and terminal rating.
2. **Terminal style.** Screw terminal vs JST vs bare pads — depends on what the pump and supply
   cables actually are.
3. **Enclosure / mounting holes.** None specified.

*(1) and (2) are answered by the parts on the bench, not by more research. Until then the schematic
is correct but the MOSFET and terminals are provisional.*
