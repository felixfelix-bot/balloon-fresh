# Breadboard Wiring Guide: ESP32-C3_Mini_V1 + LoRa2021 + GPS

## Overview

Wiring guide for the DIY v0.1 development setup on ESP32-C3_Mini_V1 dev board
with NiceRF LoRa2021 module and optional u-blox MAX-M10S GPS.

## Parts Needed

- 1x ESP32-C3_Mini_V1 (Maker go, USB-C)
- 1x NiceRF LoRa2021 (18-pin module)
- 1x u-blox MAX-M10S breakout (optional, for GPS)
- 1x BMP280 breakout (optional, I2C)
- Breadboard + jumper wires
- 2x 100nF ceramic capacitors (decoupling)
- 8.6 cm wire x2 (Sub-GHz dipole antenna, 868 MHz)

## Power

```
ESP32-C3_Mini_V1 3V3  →  Breadboard + rail
ESP32-C3_Mini_V1 GND  →  Breadboard - rail
```

## LoRa2021 Wiring

| NiceRF Pin | Function | ESP32-C3 GPIO | Silkscreen | Wire Color (suggested) |
|------------|----------|---------------|------------|----------------------|
| Pin 1 | VCC | 3.3V | 3V3 | Red |
| Pin 2 | GND | GND | GND | Black |
| Pin 3 | MISO | GPIO2 | D2 | Yellow |
| Pin 4 | MOSI | GPIO7 | D7 | Orange |
| Pin 5 | SCK | GPIO6 | D6 | Green |
| Pin 6 | NSS (CS) | GPIO10 | D10 | Blue |
| Pin 7 | BUSY | GPIO4 | D4 | Purple |
| Pin 8 | GND | GND | GND | Black |
| Pin 9 | ANT | Wire dipole | - | Antenna wire |
| Pin 10 | 2.4G | (leave floating or 50Ω term) | - | - |
| Pin 11 | GND | GND | GND | Black |
| Pin 12 | GND | GND | GND | Black |
| Pin 14 | RST | GPIO3 | D3 | White |
| Pin 15 | DIO9 (IRQ) | GPIO5 | D5 | Brown |
| Pin 16 | DIO8 | GPIO1 | D1 | (optional, leave NC) |
| Pin 17 | DIO7 | GPIO0 | D0 | (optional, leave NC) |
| Pin 18 | GND | GND | GND | Black |

### Decoupling

Place 100nF cap between Pin 1 (VCC) and Pin 2 (GND), as close to module as possible.
Second cap on ESP32-C3_Mini_V1 between 3V3 and GND.

### Antenna (Sub-GHz, 868 MHz)

Wire dipole soldered to Pin 9 (ANT):
- Each leg: 8.6 cm (λ/4 at 868 MHz ≈ 86.4 mm)
- Use stiff copper wire (30 AWG), bend 180° for dipole
- Keep clear of metal surfaces and other wires

### RadioLib Configuration

In firmware, set `radio.irqDioNum = 9` and call `setDioFunction()` for DIO9 as IRQ.
See `EspHalC3.h` for HAL pin definitions.

## GPS Wiring (Optional)

| u-blox MAX-M10S | ESP32-C3 GPIO | Silkscreen | Notes |
|-----------------|---------------|------------|-------|
| VCC | 3.3V | 3V3 | |
| GND | GND | GND | |
| TX | GPIO0 | D0 | ESP32 UART1 RX |
| RX | GPIO1 | D1 | ESP32 UART1 TX |

### GPS Notes

- GPIO0 is strapping pin — must be LOW at boot for SPI boot (default). GPS TX is high-Z at boot, so this is OK.
- GPIO1 is also used for FEM TX_EN in Komfort variant — GPS and FEM are mutually exclusive on this pin.
- Enable GPS in firmware: `CONFIG_ENABLE_GPS=y` in Kconfig.
- MAX-M10S default baud: 9600 or 38400 (check module config).

## BMP280 Wiring (Optional)

| BMP280 Breakout | ESP32-C3 GPIO | Silkscreen | Notes |
|----------------|---------------|------------|-------|
| VCC | 3.3V | 3V3 | |
| GND | GND | GND | |
| SDA | GPIO8 | D8 | Shared with onboard LED (cosmetic flicker) |
| SCL | GPIO9 | D9 | Shared with BOOT button (pullup OK) |

Enable BMP280 in firmware: `CONFIG_ENABLE_BMP280=y`.

## Pin Conflict Summary

| GPIO | Default | GPS | FEM | Antenna Switch | Notes |
|------|---------|-----|-----|----------------|-------|
| GPIO0 | ADC0 | UART1_TX | - | - | Strapping pin |
| GPIO1 | - | UART1_RX | FEM_TX_EN | - | GPS XOR FEM |
| GPIO20 | - | - | - | SP4T_CTRL_2 | Flight board only |
| GPIO21 | - | - | - | SP4T_CTRL_1 | Flight board only |

## Wiring Diagram (ASCII)

```
                    ┌─────────────────────┐
                    │   ESP32-C3_Mini_V1  │
                    │                     │
     BMP280 SDA ←──┤ D8 (GPIO8)          │
     BMP280 SCL ←──┤ D9 (GPIO9)          │
                    │                     │
    LoRa2021 MISO ←─┤ D2 (GPIO2)         │
    LoRa2021 MOSI ←─┤ D7 (GPIO7)         │
    LoRa2021 SCK  ←─┤ D6 (GPIO6)         │
    LoRa2021 NSS  ←─┤ D10 (GPIO10)       │
    LoRa2021 BUSY ←─┤ D4 (GPIO4)         │
    LoRa2021 RST  ←─┤ D3 (GPIO3)         │
    LoRa2021 DIO9 ←─┤ D5 (GPIO5)         │
                    │                     │
      GPS TX       ←─┤ D0 (GPIO0)  UART1 │
      GPS RX       ←─┤ D1 (GPIO1)  UART1 │
                    │                     │
         USB-C ────┤                     │
                    └─────────────────────┘
```

## Flash & Test

```bash
source ~/esp/esp-idf/export.sh
cd tracker/firmware
idf.py build
idf.py -p /dev/ttyACM0 flash monitor
```

## Common Issues

- **GPIO4-7 labeled "JTAG"**: These are general-purpose GPIO when JTAG is not enabled. Safe to use.
- **GPIO8 LED flicker**: onboard LED is on GPIO8 (inverted). I2C traffic causes cosmetic flicker. Not a bug.
- **No JTAG debug**: Using GPIO4-7 for SPI means no JTAG. Use UART/printf via USB-C.
- **RadioLib not found**: Run `idf.py reconfigure` with internet access to fetch managed component.
- **GPS no fix**: MAX-M10S needs clear sky view. First fix can take 5-10 minutes cold start.
