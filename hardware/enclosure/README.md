# Balloon Field-Test Enclosure v1

Waterproof 3D-printable case for the 3-board dev setup:
- ESP32-C3 SuperMini
- RP2040-Zero  
- NiceRF LoRa2021 (LR2021)

## What This Is

This is a **field-test / ground-station enclosure** — NOT a flight enclosure.
The flight boards go on the balloon (<14g, custom PCB). This box is for the
dev boards you're currently carrying in cardboard, so you can leave them
outside on a pole with solar.

## Design

- **Clamshell**: 2 parts (bottom + lid), bolted with 4x M3 screws
- **Waterproof**: O-ring groove (2mm cord) compressed between halves
- **Pole mount**: Two strap grooves on bottom for zip-ties / hose clamps
- **Solar**: Recess on top lid for solar panel
- **Cable glands**: Two 6mm holes on sides (antenna + solar wires)
- **Vent**: Small 2mm pressure-equalization hole (cover with Gore patch)
- **Board mounts**: Standoff posts for all 3 boards, self-tapping M2 screws

## Dimensions (before your caliper measurements)

```
Interior: 55.7 x 43.0 x 19.7 mm
Exterior: 59.7 x 47.0 x 24.7 mm
Material: ~21g PETG
```

## STL Files

| File | Part | Print Time |
|------|------|------------|
| `bottom.stl` | Bottom shell with board mounts | ~3h |
| `lid.stl` | Top lid with solar recess | ~1h |

## Print Settings

```
Material: PETG or ASA (NOT PLA — UV/heat destroys PLA outdoors)
Layer:    0.2mm
Infill:   40%+ (walls need 4+ perimeters for waterproofing)
Walls:    4 perimeters minimum
Support:  YES for bottom shell (board standoffs + strap grooves)
Nozzle:   0.4mm
Bed:      80°C (PETG) / 100°C (ASA)
```

## Assembly Hardware

| Part | Qty | Notes |
|------|-----|-------|
| M3x12mm screws | 4 | Countersink head, goes through lid |
| M3 nuts | 4 | Sits in hex trap on bottom |
| 2mm O-ring cord | ~200mm | Or pre-made rectangular gasket |
| M2x6mm self-tapping | 8-12 | Board mounting (or use double-sided tape) |
| Zip-ties (heavy duty) | 2 | Pole mounting (or hose clamps for metal pole) |
| Cable glands (PG7) | 2 | For antenna + solar cable feedthrough |

## How to Customize

Open `balloon-field-case.scad` in OpenSCAD (or any text editor).
Change the board dimensions at the top of the file:

```
esp32_length = 22.52;    // ← measure YOUR board, change this
esp32_width  = 18.0;     // ← measure YOUR board, change this
...
```

Then re-render:
```bash
openscad -o bottom.stl -D 'part="bottom"' balloon-field-case.scad
openscad -o lid.stl -D 'part="top"' balloon-field-case.scad
```

## What Needs Your Input

1. **Measure your boards** — use the digital calipers from inventory
2. **Which ESP32?** — C3 SuperMini or S3? Different footprint
3. **Antenna strategy** — external antenna on pole? Or internal with RF-transparent lid?
4. **Solar panel** — which cells? Integrated on lid or separate panel on pole?

## How This Fits With Current Hardware

| Track | Weight | Enclosure | Status |
|-------|--------|-----------|--------|
| Flight board | <14g | None (naked PCB + wings) | In design |
| Dev board | ~30g | This case | **This design** |
| Ground station | ~50g | Larger weatherproof box | Future |
