# Balloon Dev Board Enclosure — Variant B (Big LR2021 Dev Board)

## Overview
Same waterproof outdoor enclosure as Variant A, but fits the LARGER AliExpress
LR2021 development board with SMA connectors and external PA (~2W output)
instead of the small bare NiceRF LoRa2021 module.

## Enclosure Variants

| Variant | Radio Board | Antennas | Exterior Size |
|---------|-------------|----------|---------------|
| **A** (`balloon_dev_case.scad`) | NiceRF LoRa2021 bare module (19.72x15mm) | Wire dipoles through cable glands | 76.5 x 45 x 35.8mm |
| **B** (`balloon_dev_case_big.scad`) | Big LR2021 dev board with PA (~52x35mm est) | External antennas via SMA bulkhead holes | 76.5 x 48 x 46.1mm |

## Variant B Fits (4 boards, 3-layer stacked)
- **Layer 1 (bottom):** ESP32-C3 SuperMini V1 (22.52 x 18mm)
- **Layer 2 (middle):** Big LR2021 dev board with PA + dual SMA connectors (~52 x 35mm est)
- **Layer 3 (top):** RP2040 + GPS MAX-M10S (side by side)

## SMA Antenna Pass-Through
Two SMA bulkhead holes (6.5mm) on the side wall where the radio board's SMA
connectors face. Screw SMA connectors through from outside — antennas live
OUTSIDE the box, connected via SMA cables. Fully waterproof with SMA O-rings.

- Sub-GHz SMA: for 868/915 MHz antenna
- 2.4 GHz SMA: for 2.4 GHz antenna

## Dimensions
| Measurement | Value |
|------------|-------|
| Exterior | 76.5 x 48.0 x 46.1mm (with lid) |
| Interior | 71.5 x 43.0 x 40.6mm |
| Wall thickness | 2.5mm |

## CRITICAL: Big Radio Board Dimensions are ESTIMATES
The `big_radio_w`, `big_radio_l`, `big_radio_h` values are ESTIMATES (52x35x8mm).
When you have calipers, measure the actual AliExpress board and update in the
.scad file, then regenerate STL. The parametric design adjusts everything.

## Print Settings
Same as Variant A: ASA or PETG, 0.2mm layers, 4+ perimeters, 30% infill.
