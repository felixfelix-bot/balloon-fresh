# Balloon Field-Test Enclosure v2

Waterproof 3D-printable case for 4 boards:
- ESP32-C3 SuperMini (Maker Go)
- RP2040-Zero
- NiceRF LoRa2021 (LR2021)
- u-blox MAX-M10S GPS (high-altitude, 80km ceiling)

## What This Is

Field-test / ground-station enclosure for the dev boards.
NOT a flight enclosure — flight boards stay naked (<14g) on the balloon.
This box replaces the cardboard box for permanent outdoor pole mounting.

## Design Features

- **Clamshell**: 2 parts (bottom + lid), 4x M3 screws
- **Waterproof**: O-ring groove (2mm cord) between halves
- **Pole mount**: Two strap grooves on bottom for zip-ties / hose clamps
- **Solar**: Recess on top lid for solar panel
- **Cable glands**: Two 6mm holes on sides (antenna + solar)
- **GPS sky window**: Cutout in bottom floor for GPS patch antenna
- **Board mounts**: Standoff posts for all 4 boards
- **Vent**: 2mm pressure equalization hole (cover with Gore patch)

## Dimensions (v2 — 4 boards)

```
Board row: 71.2mm (ESP32 + LR2021 + RP2040 side by side)
GPS module: 22x20mm in corner
Interior: 103 x 103 x 24.5 mm
Exterior: 107 x 107 x 29.5 mm
GPS antenna window: 20x18mm in bottom floor
```

## v2 Changes

- Added u-blox MAX-M10S GPS board (4th board)
- GPS antenna window cut in bottom floor (patch antenna faces down through case)
- Larger interior to accommodate all 4 boards
- Board layout: ESP32 | LR2021 | RP2040 in a row + GPS in corner

## GPS Module Notes

The u-blox MAX-M10S is configured for Airborne <1G mode (UBX-CFG-NAV5
dynamic model 6) to bypass COCOM 18km altitude limit. Supports up to 80km.

- UART1 RX on ESP32 GPIO1, 9600 baud, NMEA
- Provides GPS time for phase sync (critical for interleave mode)
- ~0.6g bare module, ~2g with antenna
- GPS antenna window lets patch antenna see sky through case bottom

**IMPORTANT**: GPS breakout dimensions are assumed 22x20mm. VERIFY with
calipers — some M10S breakouts are 25x25mm or 18x18mm. Adjust
`gps_length` and `gps_width` in the SCAD file.

## STL Files

| File | Part | Print Time |
|------|------|------------|
| `bottom.stl` | Bottom shell with board mounts + GPS window | ~4h |
| `lid.stl` | Top lid with solar recess | ~1h |

## Print Settings

```
Material: PETG or ASA (NOT PLA — UV/heat destroys PLA outdoors)
Layer:    0.2mm
Infill:   40%+ (walls need 4+ perimeters for waterproofing)
Walls:    4 perimeters minimum
Support:  YES for bottom shell (standoffs + strap grooves + GPS window)
Nozzle:   0.4mm
Bed:      80°C (PETG) / 100°C (ASA)
```

## Assembly Hardware

| Part | Qty | Notes |
|------|-----|-------|
| M3x16mm screws | 4 | Countersink head, through lid |
| M3 nuts | 4 | Hex trap in bottom |
| 2mm O-ring cord | ~400mm | Rectangular gasket around perimeter |
| M2x6mm self-tapping | 12-16 | Board mounting |
| Zip-ties (heavy duty) | 2 | Pole mounting |
| Cable glands (PG7) | 2 | Antenna + solar feedthrough |
| Gore vent patch | 1 | Cover vent hole |

## How to Customize

Open `balloon-field-case.scad` in any text editor. Board dimensions at top:

```
gps_length = 22.0;    // ← MEASURE your GPS breakout, change this
gps_width  = 20.0;    // ← MEASURE your GPS breakout, change this
...
```

Re-render:
```bash
openscad -o bottom.stl -D 'part="bottom"' balloon-field-case.scad
openscad -o lid.stl -D 'part="top"' balloon-field-case.scad
```
