# Inventarliste - Vorhandene Komponenten

Stand: 2026-05-20

## Mikrocontroller

| # | Komponente | Spezifikation | Menge | Quelle | Einzelpreis | Gesamtpreis |
|---|-----------|---------------|-------|--------|------------|------------|
| 1 | XIAO ESP32C3 | WiFi/BLE, USB-C, 4MB Flash, RISC-V 160MHz | **20** | AliExpress | 3.89 EUR | 77.80 EUR |
| 2 | XIAO ESP32-C5 | WiFi 6 (2.4+5GHz), BT5, Zigbee, Thread, 8MB | **2** | AliExpress | 5.89 EUR | 11.78 EUR |

## RF Module

| # | Komponente | Spezifikation | Menge | Quelle | Einzelpreis | Gesamtpreis |
|---|-----------|---------------|-------|--------|------------|------------|
| 3 | NiceRF LoRa2021 | LR2021 Gen4, Sub-GHz + 2.4GHz, FLRC, RTToF, 19.72x15x2.2mm | **4** | NiceRF | ~10 EUR | ~40 EUR |

Details NiceRF LoRa2021:
- Pin 1: VCC (1.8-3.6V)
- Pin 2,8,11,12,18: GND
- Pin 3: MISO, Pin 4: MOSI, Pin 5: SCK, Pin 6: NSS
- Pin 7: BUSY
- Pin 9: ANT (Sub-GHz, 50 Ohm)
- Pin 10: 2.4G/S_ANT (2.4 GHz + S Band, 50 Ohm)
- Pin 13: VTCXO
- Pin 14: RST
- Pin 15: DIO9, Pin 16: DIO8, Pin 17: DIO7
- TX @433MHz 22dBm: <120mA, TX @2.4GHz 12dBm: <35mA
- RX Sub-GHz: <6mA, RX 2.4GHz: <7mA
- Sleep: <2uA, Sensitivity: -143dBm (SF12/62.5kHz Sub-GHz), -137dBm (SF12/203kHz 2.4GHz)

## Solarzellen

| # | Komponente | Spezifikation | Menge | Quelle | Einzelpreis | Gesamtpreis |
|---|-----------|---------------|-------|--------|------------|------------|
| 4 | Solarzellen 52x19mm | 0.5V 400mA, polykristallin | **100** | Amazon (AOSHIKE) | 0.17 EUR | 16.92 EUR |
| 5 | Solarzellen 78x39mm | 0.54W 0.5V, polykristallin | **50** | AliExpress | 0.05 EUR | 2.59 EUR |

## Test-Ausruestung

| # | Komponente | Spezifikation | Menge | Bemerkung |
|---|-----------|---------------|-------|-----------|
| 6 | Drucksensor | - | **1** | Fuer Ballon-Drucktest |
| 7 | Pumpe | - | **1** | Fuer Ballon-Drucktest |

## Zusammenfassung

| Kategorie | Wert |
|-----------|------|
| Gesamtinvestition | ~149 EUR |
| Verfuegbare MCU Boards | 22 (20x C3, 2x C5) |
| Verfuegbare RF Module | 4x LR2021 |
| Verfuegbare Solarzellen | 150 (100x 52x19mm, 50x 78x39mm) |

## Noch zu beschaffen

| # | Komponente | Fuer | Prioritaet | Gesch. Kosten |
|---|-----------|------|-----------|--------------|
| 1 | ESP-C3-12F bare | Flight-Board | Mittel | ~2 EUR |
| 2 | BMP280 Breakout | DIY + Flight | Hoch | ~1 EUR |
| 3 | Supercaps 3.3F 2.7V (2x) | DIY + Flight | Hoch | ~6 EUR |
| 4 | TPS7A02 LDO | Flight | Hoch | ~0.50 EUR |
| 5 | SKY66112-11 FEM | Flight (opt.) | Niedrig | ~3 EUR |
| 6 | SP4T RF Switch | Flight (opt.) | Niedrig | ~2 EUR |
| 7 | Passive (R, C) | Alle | Hoch | ~2 EUR |
| 8 | 30 AWG Kupferdraht | Alle | Hoch | ~2 EUR |
| 9 | Mylar Ballon 36" | Flug | Hoch | ~3 EUR |
| 10 | Helium | Flug | Hoch | ~15 EUR |
| 11 | PCB Bestellung (Flight) | Flight | Mittel | ~15 EUR |
| 12 | Protoboard | DIY | Hoch | ~2 EUR |

**Minimale Nachbestellung fuer DIY-Start**: ~12 EUR (BMP280 + Supercaps + Passive + Draht + Protoboard)
**Volle Flight-Ausruestung**: ~35 EUR
