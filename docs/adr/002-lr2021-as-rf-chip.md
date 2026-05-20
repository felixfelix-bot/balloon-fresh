# ADR 002: Semtech LR2021 als LoRa-Transceiver (Gen 4)

## Status
Akzeptiert

## Kontext
Der Ballon braucht einen LoRa-Funktransceiver fuer Telemetrie-Uebertragung zur Bodenstation. Der Chip muss 2.4 GHz ISM-Band unterstuetzen (weltweit lizenzfrei) und moeglichst stromsparend sein.

## Entscheidung
Wir verwenden den **Semtech LR2021** (LoRa Plus, Gen 4) als Primaer-Chip. Der **LR1121** (Gen 3) wird als pin-kompatible Alternative auf dem selben Footprint mitgeplant.

## Alternativen

| Feature | LR2021 (Gen 4) | LR1121 (Gen 3) | SX1280 (Gen 2) |
|---------|---------------|---------------|---------------|
| Sub-GHz LoRa | Ja (150-960 MHz) | Ja (150-960 MHz) | Nein |
| 2.4 GHz LoRa | Ja (1600-2500 MHz) | Ja (2400-2500 MHz) | Ja (2400-2500 MHz) |
| S-Band Sat | Ja | Ja (1900 MHz) | Nein |
| FLRC | **Ja (2.6 Mbps)** | Nein | Ja |
| O-QPSK | **Ja** | Nein | Nein |
| Sensitivity | **-141.5 dBm** | -141 dBm | -132 dBm |
| TX Sub-GHz | +22 dBm | +22 dBm | - |
| TX 2.4 GHz | +12 dBm | +11.5 dBm | +12.5 dBm |
| RX Current | 5.7 mA | 5.7 mA | 5.5 mA |
| Min. BW | **31 kHz** | 62.5 kHz | 200 kHz |
| ToF Ranging | Nein | Nein | **Ja** |
| Passive GNSS | Nein | Nein (nur Edge) | Nein |
| Crypto Engine | Ja (AES-128) | Ja (AES-128) | Nein |
| Status | **New (2025)** | Active | Active |
| EVK verfuegbar | Ja | Ja | Ja |

## Begruendung

1. **Neueste Generation**: Gen 4 (Maerz 2025), zukunftssicher
2. **FLRC**: Bis 2.6 Mbps - extrem kurze Airtime fuer Telemetrie bei naehen Distanzen
3. **O-QPSK**: Zusaetzliche Modulation fuer Kompatibilitaet
4. **-141.5 dBm**: Beste Sensitivity in dieser Klasse = maximale Reichweite
5. **31 kHz Min BW**: Feinere LoRa-Konfiguration = bessere Sensitivity bei gleicher Airtime
6. **Dual-Band**: Sub-GHz fuer maximale Reichweite + 2.4 GHz fuer weltweit lizenzfreien Betrieb
7. **Pin-kompatibel mit LR1121**: Beide Module auf dem selben PCB Footprint

## Kritischer Nachteil
- **Kein ToF Ranging**: Weder LR2021 noch LR1121 haben die Ranging-Engine des SX1280
- **Kein GNSS**: Position muss ueber LoRaWAN-TDoA oder separate GPS-Loesung bestimmt werden
- **Neuer Chip**: Weniger Community-Support, neuere Treiber

## Konsequenzen
- Positionierung erfolgt ueber LoRaWAN-Geolocation (TDoA) oder separaten GPS-Chip (optional)
- Treiber-Entwicklung basiert auf Semtech SWDR001 (LR11xx Driver) und muss fuer LR2021 angepasst werden
- Dual-Footprint auf dem PCB ermoeglicht spaeteren Wechsel zwischen LR2021 und LR1121
