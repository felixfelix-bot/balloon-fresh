# Balloon Dev Board Waterproof Enclosure

## Overview
3D-printable parametric enclosure for outdoor deployment of balloon tracker
development boards. Designed in OpenSCAD for CLI-driven parametric design.

## Fits
- ESP32-C3 SuperMini V1 (22.52 x 18mm) + LR2021 (19.72 x 15mm) soldered on top
- RP2040 SuperMini (21.5 x 17.8mm) — adjustable in .scad file
- Wire dipole antennas via cable glands
- Solar panel wiring via cable glands

## Dimensions
| Measurement | Value |
|------------|-------|
| Exterior | 57.2 x 48.0 x 25.9mm (with lid) |
| Interior | 52.2 x 43.0 x 20.4mm |
| Wall thickness | 2.5mm |
| Print volume needed | 60 x 100 x 30mm (both parts) |

## Features
1. **O-ring groove** in lid (2mm cord, AS568 compatible) — IP65+ sealing
2. **4x M3 screw bosses** with heat-set inserts (M3 x 5mm)
3. **3x cable gland holes** (6mm) — antenna1, antenna2, solar
4. **Pole mount tabs** — 2x M5 holes for U-bolts or zip ties
5. **Board standoffs** — M2 self-tapping, 3mm height
6. **Gore-Tex vent** — 4mm hole with recess for pressure equalization
7. **Solar panel recess** in lid top — 1.5mm deep for panel mounting
8. **Rounded corners** — 4mm radius for print quality

## Print Settings

### Material (critical for outdoor use)
- **ASA** (best): UV resistant, heat resistant (-20C to +90C), weatherproof
- **PETG** (good): UV stable enough, moisture resistant, easier to print
- **ABS** (acceptable): Heat resistant but degrades in UV over time
- **PLA** (NOT recommended): Melts in sun, deforms above 60C, absorbs moisture

### Print Parameters
| Setting | Value |
|---------|-------|
| Layer height | 0.2mm |
| Perimeters | 3 minimum |
| Top/bottom layers | 4 minimum |
| Infill | 30% (gyroid) |
| Support material | Not needed (designed support-free) |
| Wall count | 4 (for waterproofing) |

### Print Orientation
- **Bottom shell**: Print as-is (opening facing up)
- **Lid**: Print flat side down (solar recess facing up)

## Assembly

### Hardware Needed
| Part | Qty | Notes |
|------|-----|-------|
| M3 x 12mm screws | 4 | Stainless steel (PHILLIPS or HEX) |
| M3 heat-set inserts | 4 | OD 4.2mm, length 5mm |
| O-ring cord (2mm) | ~200mm | Nitrile or silicone |
| M2 x 6mm self-tapping screws | 4 | Board mounting |
| Cable glands (PG7/M6) | 3 | For antenna + solar cables |
| Gore-Tex patch | 1 | 8mm diameter, for vent |
| U-bolt (M5) or zip ties | 2 | Pole mounting |

### Steps
1. **Heat-set inserts**: Press 4x M3 inserts into screw bosses in bottom shell (use soldering iron tip)
2. **Board mounting**: Screw ESP32-C3+LR2021 stack onto center standoffs with M2 screws
3. **RP2040 mounting**: Screw RP2040 onto standoffs (if side-by-side layout)
4. **Cable routing**: Route antenna pigtails + solar wires through cable glands
5. **O-ring**: Install 2mm O-ring cord into lid groove (cut to length, join ends with CA glue)
6. **Vent**: Apply Gore-Tex patch over vent hole on interior side
7. **Solar panel**: Mount solar cell(s) in lid recess with silicone adhesive
8. **Close**: Install lid, tighten 4x M3 screws evenly
9. **Mount**: Attach to pole with U-bolts through back tabs

## Waterproofing Notes
- **FDM prints are NOT inherently waterproof** — layer lines leak
- Apply 2-3 coats of epoxy resin or spray-on waterproofing to interior walls
- OR: Print at higher temperature + 100% flow for better layer adhesion
- OR: Use acetone smoothing (ABS/ASA only)
- Test: Submerge in water for 30 min, check for leaks before deploying
- Cable glands: tighten firmly but don't overtighten (compresses cable seal)
- Gore-Tex vent: REQUIRED for pressure equalization (sealed case will deform)

## Customization
All dimensions are parametric in `balloon_dev_case.scad`. Key parameters:
```openscad
esp_w = 22.52;    // ESP32-C3 width
esp_l = 18.0;     // ESP32-C3 length
rp_w = 21.5;      // RP2040 width — CHANGE FOR YOUR BOARD
rp_l = 17.8;      // RP2040 length
layout = "stacked"; // or "sidebyside"
gland_count = 3;   // number of cable glands
wall = 2.5;        // wall thickness
```

## Regenerate STL
```bash
openscad -o bottom.stl -D 'part="bottom"' balloon_dev_case.scad
openscad -o lid.stl -D 'part="lid"' balloon_dev_case.scad
```

## Limitations
1. **Not flight-rated**: This is for ground/bench testing only. Flight boards
   use soldered wing boards with no enclosure (weight critical).
2. **USB access**: The lid does not have a USB cutout by default. For
   programming, open the case or add a side cutout. For permanent outdoor
   deployment, seal fully.
3. **Thermal management**: ESP32-C3 + LR2021 TX can draw 100+ mA at +22dBm.
   In direct sun + sealed case, may need ventilation or heat sinking.
4. **Print verification needed**: Always test-fit with actual boards before
   final outdoor deployment. FDM tolerances vary by printer.
