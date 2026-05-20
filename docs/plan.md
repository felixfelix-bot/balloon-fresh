# Projektplan: ESP32 Pico-Balloon Tracker

## Projektuebersicht

Ultraleichter Pico-Balloon-Tracker basierend auf ESP32-C3 und Semtech LR2021 (LoRa Gen 4). Ziel: Ein <15g schweres Payload, das via 2.4 GHz LoRa Telemetrie an eine Bodenstation sendet, mit 3D-Yagi-Antennen-Array und Solar/Supercap-Stromversorgung.

## Design-Entscheidungen

Siehe [docs/adr/](adr/) fuer detaillierte Architecture Decision Records:

| ADR | Thema | Entscheidung |
|-----|-------|-------------|
| [001](adr/001-esp32-c3-as-mcu.md) | Mikrocontroller | ESP32-C3 (XIAO fuer Dev, ESP-C3-12F fuer Flug) |
| [002](adr/002-lr2021-as-rf-chip.md) | LoRa-Transceiver | LR2021 Gen 4 (mit LR1121 Alternative) |
| [003](adr/003-dual-track-hardware.md) | Hardware-Strategie | Dual-Track: Dev-Board + Flight-Board |
| [004](adr/004-3d-yagi-antenna-structure.md) | Antenne | 4x PCB-Yagi in 3D + SP4T Switch |
| [005](adr/005-sky66112-fem.md) | PA/LNA | SKY66112-11 FEM (+22 dBm TX, +14 dB LNA) |
| [006](adr/006-supercapacitor-power.md) | Stromversorgung | Solar → Schottky → Supercaps → LDO |
| [007](adr/007-adaptive-protocol.md) | Funkprotokoll | Adaptiv: FLRC/LoRa/Sub-GHz je nach Distanz |
| [008](adr/008-telemetry-protocol.md) | Telemetrie | 24-Byte biniaeres Paket mit CRC-16 |

## Hardware-Konfiguration

### Flug-Board (3D-Struktur, <15g)

Siehe [docs/hardware-design.md](hardware-design.md) fuer vollstaendiges 3D-Design.

```
              Ballon
                │
          ╔═══════════╗
          ║  HUB-BOARD ║ 22x22mm, 0.6mm FR4
          ║  ESP32-C3  ║
          ║  LR2021    ║
          ║  Supercaps ║
          ║  FEM+Switch║
          ╚══╦══╦══╦══╝
             ╱  │  ╲
     4x WING BOARDS (je 65x28mm)
     Jeweils: PCB-Yagi + 3 Solarzellen
```

### Gewichtsbudget

| Komponente | Gewicht |
|-----------|---------|
| Hub PCB (22x22mm, 0.6mm) | 0.3g |
| ESP-C3-12F | 1.0g |
| LR2021 Modul | 2.0g |
| SKY66112 FEM + SP4T Switch | 0.2g |
| BMP280 | 0.5g |
| 2x Supercap 3.3F 2.7V | 3.0g |
| LDO + Diode + Passiv | 0.25g |
| 4x Wing PCB (65x28mm, 0.6mm) | 3.2g |
| 12x Solarzellen 52x19mm | 6.0g |
| Loetverbindungen | 0.2g |
| **TOTAL** | **~16.65g** |

> Hinweis: Das 15g-Ziel wird mit Optimierungen erreicht (weniger Solarzellen, duennere PCBs). Aktuell als "Komfort-Modus" mit ~16.5g geplant.

## Firmware-Architektur

### Duty Cycle

```
Deep Sleep (~10 uA, 30s-5min Timer)
    │
    ▼ Wake
Check Supercap Voltage (ADC, GPIO0)
    │ < 3.0V? ──► Deep Sleep
    ▼ OK
Read BMP280 (I2C: SDA=GPIO8, SCL=GPIO9)
    ▼
GNSS Snapshot (LR2021, optional)
    ▼
Encode Telemetry (24 Bytes)
    ▼
Select TX Mode (adaptiv: FLRC/LoRa/Sub-GHz)
    ▼
Leuchtturm TX (SP4T: Wing1→Wing2→Wing3→Wing4)
    ▼
RX Window (optional, Bodenstations-Kommandos)
    ▼
Deep Sleep
```

### Pin-Belegung (ESP32-C3)

```
GPIO7  (SPI_MOSI)  → LR2021 MOSI
GPIO2  (SPI_MISO)  → LR2021 MISO
GPIO6  (SPI_SCLK)  → LR2021 SCLK
GPIO10 (SPI_CS)    → LR2021 NSS
GPIO3  (OUTPUT)    → LR2021 RESET
GPIO4  (INPUT)     → LR2021 DIO1 (TX/RX Done IRQ)
GPIO5  (INPUT)     → LR2021 BUSY
GPIO0  (ADC1_CH0)  → Supercap Voltage Divider
GPIO8  (I2C_SDA)   → BMP280 SDA
GPIO9  (I2C_SCL)   → BMP280 SCL
GPIO1  (OUTPUT)    → SKY66112 TX_EN (FEM TX/RX)
GPIO21 (OUTPUT)    → SP4T CTRL_1 (Antenna Select)
GPIO20 (OUTPUT)    → SP4T CTRL_2 (Antenna Select)
```

## Vorhandene Hardware

| Teil | Quelle | Spezifikation |
|------|--------|---------------|
| XIAO ESP32C3 | AliExpress | Dev Board, WiFi/BLE, USB-C |
| ESP32-C5 Board | AliExpress | WiFi 6, BT5, Zigbee → Bodenstation |
| 100x Solarzellen 52x19mm | Amazon (AOSHIKE) | 0.5V 400mA, polykristallin |
| 50x Solarzellen 78x39mm | AliExpress | 0.54W 0.5V, polykristallin |

## Noch zu beschaffende Komponente

Siehe [bom/BOM.md](../bom/BOM.md) fuer vollstaendige Einkaufsliste.

## Link-Budget & Power-Budget

- [docs/link-budget.md](link-budget.md) - Reichweitenberechnung
- [docs/power-budget.md](power-budget.md) - Stromverbrauchsanalyse

## Projektstruktur

```
esp32-balloon-integration/
├── firmware/                  # ESP-IDF v5.4.1 Projekt
│   ├── main/                  # Hauptapplikation
│   └── components/            # Treiber (LR2021, BMP280, FEM, etc.)
├── hardware/                  # SKiDL + KiCad PCB Design
│   ├── hub_board/             # Zentrales Elektronik-Board
│   ├── wing_board/            # 4x identische Antennen/Solar-Wings
│   ├── assembly/              # 3D Assembly Scripts
│   └── simulation/            # Antennen + Power Simulation
├── ground-station/            # Python Bodenstation
├── bom/                       # Bill of Materials
├── docs/                      # Dokumentation + ADRs
├── tools/                     # Setup & Build Scripts
└── tests/                     # Firmware Unit Tests
```

## Umsetzungsreihenfolge

### Phase 1: Grundlagen (Woche 1)
1. Toolchain Setup (KiCad + SKiDL + ESP-IDF)
2. ESP-IDF Projektstruktur erstellen
3. LR2021 SPI-Treiber implementieren
4. BMP280 Treiber implementieren
5. Dev-Board (XIAO Carrier) schematic in SKiDL

### Phase 2: Kommunikation (Woche 2)
6. LoRa P2P TX/RX (2.4 GHz + Sub-GHz)
7. FLRC-Modus implementieren
8. SP4T Antennen-Switch Leuchtturm-Modus
9. Telemetrie-Protokoll implementieren

### Phase 3: Power Management (Woche 3)
10. Deep Sleep / Wake Cycle
11. ADC Spannungsueberwachung
12. Adaptiver Moduswechsel (FLRC/LoRa/Sub-GHz)
13. Brownout-Schutz

### Phase 4: Hardware (Parallel)
14. SKiDL Hub-Board Schematic
15. SKiDL Wing-Board Schematic (Yagi + Solar)
16. KiCad PCB Layout
17. Gerber Export + bestellen

### Phase 5: Integration & Test
18. PCB bestuecken
19. Firmware flashen + End-to-End Test
20. Bodenstation einrichten
21. Freiflug-Vorbereitung
