# Balloon Dev Board Waterproof Enclosure v2

## Overview
3D-printable parametric enclosure for outdoor deployment of balloon tracker
development boards. Designed in OpenSCAD for CLI-driven parametric design.

## Fits (4 boards, 2-layer stacked)
**Bottom layer:**
- ESP32-C3 SuperMini V1 (22.52 x 18mm) with LR2021 soldered on top

**Top layer (side by side):**
- RP2040 board (~21.5 x 17.8mm — ADJUST in .scad if different)
- GPS module u-blox MAX-M10S on breakout (~24 x 24mm — ADJUST in .scad)

## Dimensions
| Measurement | Value |
|------------|-------|
| Exterior | 66.5 x 45.0 x 35.3mm (with lid) |
| Interior | 61.5 x 40.0 x 29.8mm |
| Wall thickness | 2.5mm |
| Bottom layer height | ESP32 PCB + LR2021 = ~7mm |
| Layer gap | 6mm (air circulation + wire routing) |
| Top layer | RP2040 + GPS side by side |
| Wire clearance above top layer | 14mm |

## Features
1. **O-ring groove** in lid (2mm cord, AS568 compatible) — IP65+ sealing
2. **4x M3 screw bosses** with heat-set inserts (M3 x 5mm)
3. **3x cable gland holes** (6mm) — antenna1, antenna2, solar
4. **Pole mount tabs** — 2x M5 holes for U-bolts or zip ties
5. **Board standoffs** — M2 self-tapping, dual-layer
6. **Gore-Tex vent** — 4mm hole with recess for pressure equalization
7. **Solar panel recess** in lid top — 1.5mm deep
8. **USB-C access port** on side — programming without opening case
9. **GPS antenna window** in lid — thinned material over GPS for better signal
10. **Rounded corners** — 5mm radius

## CRITICAL: GPS Antenna Orientation
The GPS module MUST be mounted patch-antenna-side UP (facing the lid).
The lid has a thinned section over the GPS position to reduce signal
attenuation. GPS needs clear sky view — do not bury under other boards.

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
| Perimeters | 4 minimum (for waterproofing) |
| Top/bottom layers | 4 minimum |
| Infill | 30% (gyroid) |
| Support material | Not needed |
| Wall count | 4+ |

### Print Orientation
- **Bottom shell**: Print as-is (opening facing up)
- **Lid**: Print flat side down (solar recess facing up)

## Assembly

### Hardware Needed
| Part | Qty | Notes |
|------|-----|-------|
| M3 x 12mm screws | 4 | Stainless steel |
| M3 heat-set inserts | 4 | OD 4.2mm, length 5mm |
| O-ring cord (2mm) | ~220mm | Nitrile or silicone |
| M2 x 6mm self-tapping screws | 8 | 4x bottom board, 4x top board |
| Cable glands (PG7) | 3 | Antenna + solar cables |
| Gore-Tex patch | 1 | 8mm diameter |
| U-bolt (M5) or zip ties | 2 | Pole mounting |

### Assembly Steps
1. **Heat-set inserts**: Press 4x M3 inserts into bottom shell bosses
2. **Bottom board**: Mount ESP32-C3 + LR2021 on bottom standoffs
3. **Top board**: Mount RP2040 and GPS on top standoffs
   - GPS patch antenna faces UP toward lid
4. **Wire routing**: Route inter-board wires through the 6mm layer gap
5. **Cable glands**: Route antenna pigtails + solar wires through glands
6. **O-ring**: Install 2mm cord in lid groove (join ends with CA glue)
7. **Vent**: Apply Gore-Tex patch over vent hole on interior
8. **Solar panel**: Mount solar cell in lid recess with silicone
9. **Close**: Install lid, tighten 4x M3 screws evenly (criss-cross pattern)
10. **Mount**: Attach to pole with U-bolts through back tabs

## Waterproofing Notes
- **FDM prints are NOT inherently waterproof** — layer lines leak
- Apply 2-3 coats of epoxy resin or spray waterproofing to interior
- OR: Print at higher temperature + 100% flow for better adhesion
- OR: Acetone smoothing (ABS/ASA only)
- Test: Submerge 30 min, check for leaks before deploying
- Cable glands: tighten firmly, don't overtighten
- Gore-Tex vent: REQUIRED for pressure equalization

## Customization
All dimensions parametric in `balloon_dev_case.scad`. Key parameters:
```openscad
// CHANGE THESE WITH CALIPER MEASUREMENTS
esp_w = 22.52;    // ESP32-C3 width
rp_w = 21.5;      // RP2040 width
gps_w = 24.0;     // GPS breakout width
gps_l = 24.0;     // GPS breakout length
```

## Regenerate STL
```bash
openscad -o bottom.stl -D 'part="bottom"' balloon_dev_case.scad
openscad -o lid.stl -D 'part="lid"' balloon_dev_case.scad
```

## Limitations
1. **Not flight-rated**: Ground/bench testing only. Flight uses bare boards.
2. **GPS signal**: FDM material attenuates GPS signal. The lid has a thinned
   section over GPS, but for best performance, consider external GPS antenna.
3. **Thermal**: ESP32-C3 + LR2021 TX draws 100+ mA. Direct sun + sealed case
   may need ventilation. Monitor temps.
4. **USB port**: Side cutout allows programming without opening. For permanent
   outdoor deployment, seal with silicone after final programming.
5. **Verify fit**: Always test-fit with actual boards before outdoor deployment.
