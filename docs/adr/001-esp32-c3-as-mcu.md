# ADR 001: ESP32-C3 als Mikrocontroller

## Status
Akzeptiert

## Kontext
Der Pico-Ballon-Tracker braucht einen stromsparenden Mikrocontroller mit genug Leistung fuer SPI-Kommunikation mit dem LoRa-Transceiver, I2C-Sensorabfrage und Deep-Sleep-Power-Management. Gewicht muss unter 1g (Bare Module) bleiben.

## Entscheidung
Wir verwenden den **ESP32-C3** (konkret: ESP-C3-12F Bare Module fuer Flight-Board, XIAO ESP32C3 fuer Prototyping).

## Alternativen

| Option | Strom Deep Sleep | Gewicht | LoRa-Treiber | Preis |
|--------|-----------------|---------|--------------|-------|
| ESP32-C3 | ~10-15 uA | 1.0g (bare) | ESP-IDF SPI | ~2 EUR |
| ESP32-S2 | ~20 uA | 1.5g | ESP-IDF SPI | ~3 EUR |
| ESP32-S3 | ~10 uA | 2.0g | ESP-IDF SPI | ~4 EUR |
| nRF52840 | ~1.5 uA | ~1g | Zephyr SPI | ~5 EUR |
| STM32L4 | ~0.5 uA | ~0.5g | HAL SPI | ~3 EUR |
| ATmega328P | ~1 uA | ~2g | Arduino SPI | ~1 EUR |

## Begruendung

1. **Deep Sleep**: ~10-15 uA ist ausreichend fuer Solar+Supercap-Betrieb
2. **Gewicht**: ESP-C3-12F Bare Module wiegt nur 1.0g
3. **ESP-IDF v5.4.1**: Bereits auf dem System installiert, reife Toolchain
4. **RISC-V Single-Core**: Einfacher, stromsparender als XTENSA-Dual-Core
5. **WiFi/BLE deaktiviert**: Spart massiv Strom wenn abgeschaltet
6. **Verfuegbarkeit**: XIAO ESP32C3 bereits vorhanden (Prototyping)
7. **Community**: Grosse Community, viele LoRa-Bibliotheken verfuegbar

## Nachteile
- Deep Sleep nicht ganz so niedrig wie STM32L4 oder nRF52 (~10uA vs ~1uA)
- Single-Core限制了 parallele Verarbeitung (aber fuer diesen Anwendungsfall irrelevant)

## Vorhandene Hardware
- 1x XIAO ESP32C3 (Seeed Studio) - fuer Dev-Board Prototyping
- 1x ESP32-C5 Board - fuer Bodenstation (WiFi 6)
