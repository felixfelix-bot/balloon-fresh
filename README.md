# ESP32 Pico-Balloon Tracker

Ultraleichter (<15g) Pico-Balloon-Tracker basierend auf ESP32-C3 und Semtech LR2021 (LoRa Gen 4).

## Features

- **Multi-Band LoRa**: 2.4 GHz ISM (weltweit lizenzfrei) + Sub-GHz (868/915 MHz)
- **FLRC High-Speed**: Bis 2.6 Mbps fuer kurze Distanzen
- **3D Antennen-Array**: 4 PCB-Yagi Antennen in verschiedenen Raumrichtungen
- **Adaptive Moduswahl**: Automatischer Wechsel zwischen FLRC/LoRa/Sub-GHz
- **Solar + Supercap Stromversorgung**: Keine Batterie noetig
- **SKY66112 FEM**: +22 dBm TX, +14 dB LNA RX
- **BMP280 Sensor**: Druck, Hoehe, Temperatur
- **Dual-Track Hardware**: Dev-Board (XIAO) + Flight-Board (Bare-Chip)

## Hardware

| Komponente | Spezifikation |
|-----------|---------------|
| MCU | ESP32-C3 (ESP-C3-12F / XIAO ESP32C3) |
| LoRa | Semtech LR2021 (Gen 4) / LR1121 (Gen 3, alternative) |
| PA/LNA | Skyworks SKY66112-11 (+22 dBm TX, +14 dB LNA) |
| Antennen | 4x PCB-Yagi + SP4T Switch (Leuchtturm-Modus) |
| Power | 12x Solarzellen (52x19mm) → BAT54 → 2x 3.3F Supercaps → TPS7A02 LDO |
| Sensor | BMP280 (Druck/Temperatur) |
| Zielgewicht | <15g (Komfort-Modus) |

## Dokumentation

- [Projektplan](docs/plan.md) - Gesamtplan mit Phasen und Zeitplan
- [Hardware-Design](docs/hardware-design.md) - 3D Board-Design (Hub + Wings)
- [Link-Budget](docs/link-budget.md) - Reichweitenberechnung
- [Power-Budget](docs/power-budget.md) - Stromverbrauchsanalyse
- [Einkaufsliste](bom/BOM.md) - Bill of Materials

### Architecture Decision Records

| ADR | Entscheidung |
|-----|-------------|
| [001](docs/adr/001-esp32-c3-as-mcu.md) | ESP32-C3 als MCU |
| [002](docs/adr/002-lr2021-as-rf-chip.md) | LR2021 Gen 4 als LoRa-Transceiver |
| [003](docs/adr/003-dual-track-hardware.md) | Dual-Track: Dev + Flight Board |
| [004](docs/adr/004-3d-yagi-antenna-structure.md) | 3D Yagi-Antennen-Struktur |
| [005](docs/adr/005-sky66112-fem.md) | SKY66112-11 als PA/LNA FEM |
| [006](docs/adr/006-supercapacitor-power.md) | Supercapacitor-Stromversorgung |
| [007](docs/adr/007-adaptive-protocol.md) | Adaptive Protokoll-Strategie |
| [008](docs/adr/008-telemetry-protocol.md) | Telemetrie-Paketformat |

## Projektstruktur

```
esp32-balloon-integration/
├── firmware/                  # ESP-IDF v5.4.1 Firmware
├── hardware/                  # SKiDL + KiCad PCB Design
│   ├── hub_board/             # Zentrales Elektronik-Board
│   ├── wing_board/            # 4x identische Antennen/Solar-Wings
│   ├── assembly/              # 3D Assembly
│   └── simulation/            # Antennen + Power Simulation
├── ground-station/            # Python Bodenstation
├── bom/                       # Bill of Materials
├── docs/                      # Dokumentation + ADRs
├── tools/                     # Setup & Build Scripts
└── tests/                     # Unit Tests
```

## Schnellstart

```bash
# ESP-IDF Umgebung laden
source ~/esp/esp-idf/export.sh

# Firmware bauen
cd firmware && idf.py build

# Auf XIAO ESP32C3 flashen
idf.py -p /dev/ttyACM0 flash monitor
```
