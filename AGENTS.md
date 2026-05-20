# AGENTS.md - AI Agent Instructions

## Project Overview
ESP32-C3 + NiceRF LoRa2021 (Semtech LR2021 Gen 4) pico balloon tracker. Solar/supercap power. Target weight: <15g (Mittel-Plan) or <9g (Minimal-Plan).

## RF Driver: RadioLib

**IMPORTANT**: We use RadioLib v7.6.0 (NOT a custom driver) for LR2021 communication.
- RadioLib is included as an ESP-IDF component dependency via `idf_component.yml`
- Supports: LoRa, FLRC, GFSK, OOK, LR-FHSS, O-QPSK, RTToF ranging
- Has native ESP-IDF support with HAL abstraction layer
- The custom LR2021 driver in `firmware/components/lr2021/` is DEPRECATED
- See `firmware/main/EspHalC3.h` for the ESP32-C3 hardware abstraction

## Inventory (Owned Parts)
- 20x XIAO ESP32C3
- 2x XIAO ESP32-C5
- 4x NiceRF LoRa2021 modules (19.72x15x2.2mm, 18-pin)
- 100x Solar cells 52x19mm (0.5V 400mA)
- 50x Solar cells 78x39mm (0.54W 0.5V)
- 1x Pressure sensor + pump (for balloon testing)

## Build & Flash Commands

### Firmware (ESP-IDF v5.4.1)
```bash
source ~/esp/esp-idf/export.sh
cd firmware && idf.py build
idf.py -p /dev/ttyACM0 flash monitor    # XIAO ESP32C3
idf.py -p /dev/ttyUSB0 flash             # bare ESP-C3-12F
```

### Hardware (SKiDL + KiCad)
```bash
pip install skidl graphviz
cd hardware && python hub_board/hub_schematic.py
```

### Lint & Typecheck
```bash
cd firmware && idf.py reconfigure
ruff check hardware/
```

## Project Structure
```
firmware/main/         - Main application (C++, uses RadioLib)
firmware/components/   - Drivers (BMP280, power_manager, antenna_switch, sky66112)
                       NOTE: lr2021/ is deprecated, use RadioLib instead
hardware/hub_board/    - Central electronics board (SKiDL + KiCad)
hardware/wing_board/   - 4x identical antenna+solar boards
docs/adr/              - Architecture Decision Records (8 decisions)
docs/component-guide.md - All parts with explanations and alternatives
docs/inventory.md      - Full inventory tracking
docs/plan-variants.md  - DIY / Minimal / Mittel / Komfort plans
docs/antenna-strategy.md - Yagi vs Patch + CP strategy
docs/balloon-pressure-test.md - Mylar balloon test plan
bom/BOM.md             - Bill of Materials (prioritized)
```

## Plan Variants
| Variant | Weight | Antenna | FEM/SP4T | Target |
|---------|--------|---------|----------|--------|
| DIY v0.1 | ~15g | Wire dipole | No | Development |
| Minimal | ~8-9g | Wire dipole | No | Ultra-light flight |
| Mittel | ~12-13g | 1-2x PCB-Yagi | Optional | Recommended flight |
| Komfort | ~16.6g | 4x PCB-Yagi | Yes | Full features |

## Key Design Decisions (see docs/adr/)
1. ESP32-C3 as MCU (ADR-001)
2. LR2021 Gen 4 as LoRa chip (ADR-002)
3. Dual-track hardware: Dev board (XIAO) + Flight board (bare chip) (ADR-003)
4. 3D Yagi antenna structure: 4 wings + SP4T switch (ADR-004)
5. SKY66112-11 FEM for PA+LNA (ADR-005)
6. Supercapacitor power (Solar → Caps → LDO) (ADR-006)
7. Adaptive protocol (FLRC/LoRa/Sub-GHz) (ADR-007)
8. 24-byte binary telemetry with CRC-16 (ADR-008)

## NiceRF LoRa2021 Pin Mapping (XIAO ESP32C3)
```
NiceRF Pin   Function    XIAO GPIO   XIAO Pin
Pin 1        VCC         3.3V        3V3
Pin 2,8,11,12,18  GND   GND         GND
Pin 3        MISO        GPIO7       D7
Pin 4        MOSI        GPIO6       D6
Pin 5        SCK         GPIO5       D5
Pin 6        NSS         GPIO10      D10
Pin 7        BUSY        GPIO4       D4
Pin 9        ANT (Sub-GHz, 50 Ohm)
Pin 10       2.4G (2.4 GHz + S Band, 50 Ohm)
Pin 14       RST         GPIO3       D3
Pin 15       DIO9 (IRQ)  GPIO2       D2
Pin 16       DIO8        GPIO1       D1
Pin 17       DIO7        GPIO0       D0
```
RadioLib: Set `radio.irqDioNum = 9` and call `setDioFunction()` for DIO9 as IRQ.

## Pin Assignment (ESP32-C3 bare, Flight Board)
```
GPIO7  = SPI_MOSI (LR2021)
GPIO2  = SPI_MISO (LR2021)
GPIO6  = SPI_SCLK (LR2021)
GPIO10 = SPI_CS   (LR2021 NSS)
GPIO3  = LR2021 RESET
GPIO4  = LR2021 BUSY
GPIO5  = LR2021 DIO9 (IRQ) -- note: NiceRF exposes DIO7/8/9, not DIO1/5
GPIO0  = ADC Supercap Voltage (or use LR2021 getVoltage())
GPIO8  = I2C_SDA (BMP280)
GPIO9  = I2C_SCL (BMP280)
GPIO1  = FEM TX_EN (SKY66112) -- optional
GPIO21 = SP4T CTRL_1 (Antenna Select) -- optional
GPIO20 = SP4T CTRL_2 (Antenna Select) -- optional
```

## Antenna Strategy
- Sub-GHz (868 MHz): Wire dipole, omnidirectional, +22 dBm, ~480 km range
- 2.4 GHz: PCB Yagis on wing boards (Komfort) or wire dipole (Minimal)
- Ground station: Circular polarized (RHCP) antenna for 2.4 GHz to eliminate rotation loss
- See docs/antenna-strategy.md for details

## Important Notes
- WiFi and Bluetooth MUST be disabled in sdkconfig.defaults (power saving)
- CPU clock should be set to 80 MHz (not 160 MHz) for power saving
- RadioLib is C++; app_main must be in a .cpp file with `extern "C" void app_main()`
- All wing boards are IDENTICAL (same PCB, same components)
- Solder joints connect wing boards to hub board (no connectors on flight board)
- Always run `idf.py build` after firmware changes to verify compilation
- FEM and SP4T are optional; start without them for DIY/Minimal
