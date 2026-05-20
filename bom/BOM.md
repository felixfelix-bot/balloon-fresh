# Bill of Materials (BOM)

## Vorhandene Komponente

| # | Komponente | Spezifikation | Menge | Quelle | Gesamtpreis |
|---|-----------|---------------|-------|--------|------------|
| 1 | XIAO ESP32C3 | WiFi/BLE, USB-C, 4MB Flash | **20** | AliExpress | 77.80 EUR |
| 2 | XIAO ESP32-C5 | WiFi 6 (2.4+5GHz), BT5, Zigbee, 8MB | **2** | AliExpress | 11.78 EUR |
| 3 | NiceRF LoRa2021 | LR2021 Gen4, Sub-GHz+2.4GHz, FLRC, RTToF, 19.72x15x2.2mm | **4** | NiceRF | ~40 EUR |
| 4 | Solarzellen 52x19mm | 0.5V 400mA, polykristallin | **100** | Amazon (AOSHIKE) | 16.92 EUR |
| 5 | Solarzellen 78x39mm | 0.54W 0.5V, polykristallin | **50** | AliExpress | 2.59 EUR |
| 6 | Drucksensor + Pumpe | Fuer Ballon-Drucktest | **je 1** | - | - |

## Noch zu beschaffen - Nach Prioritaet

### Prioritaet 1: DIY-Prototyp (sofort noetig)

| # | Komponente | Spezifikation | Menge | Preis ca. | Lieferant |
|---|-----------|---------------|-------|-----------|-----------|
| 7 | BMP280 Breakout | I2C Druck/Temperatur | 1 | ~1 EUR | AliExpress |
| 8 | 30 AWG Kupferdraht | Verbindungen, Antennen | 2m | ~2 EUR | Amazon |
| 9 | Protoboard | Fuer DIY-Aufbau | 1-2 | ~2 EUR | AliExpress |
| 10 | 100nF Keramik-Caps | Entkopplung LR2021/ESP32 | 5-10 | ~0.30 EUR | LCSC |

**Subtotal DIY**: ~5 EUR

### Prioritaet 2: Solarbetriebener Test

| # | Komponente | Spezifikation | Menge | Preis ca. | Lieferant |
|---|-----------|---------------|-------|-----------|-----------|
| 11 | Supercapacitor 3.3F 2.7V | AVX SCC Serie | 2 | ~6 EUR | DigiKey |
| 12 | TPS7A02 LDO | 3.3V, 25nA IQ, SOT-23 | 1 | ~0.50 EUR | LCSC |

**Subtotal Solar**: ~7 EUR

### Prioritaet 3: Flight-Board (Minimal)

| # | Komponente | Spezifikation | Menge | Gewicht | Preis ca. | Lieferant |
|---|-----------|---------------|-------|---------|-----------|-----------|
| 13 | ESP-C3-12F bare | RISC-V, 4MB Flash | 1 | 1.0g | ~2 EUR | AliExpress |
| 14 | Supercap 1F 5.5V oder 2x 3.3F 2.7V | je nach Plan | 1-2 | 2-3g | 3-6 EUR | DigiKey |
| 15 | PCB Bestellung | 0.4mm FR4, Hub+/-Wings | 1 Set | 2-3g | ~15 EUR | JLCPCB |

**Subtotal Flight Minimal**: ~20-23 EUR

### Prioritaet 4: Flight-Board (Komfort-Optionen)

| # | Komponente | Spezifikation | Menge | Gewicht | Preis ca. | Lieferant |
|---|-----------|---------------|-------|---------|-----------|-----------|
| 16 | SKY66112-11 FEM | 2.4GHz PA+LNA | 1 | 0.1g | ~3 EUR | DigiKey |
| 17 | SP4T RF Switch | SKY13351-378LF | 1 | 0.1g | ~2 EUR | DigiKey |
| 18 | Passive (R,C,Ferrites) | Balancing, Pullups, Bypass | Set | 0.2g | ~1.50 EUR | LCSC |

**Subtotal Komfort-Optionen**: ~6.50 EUR

### Prioritaet 5: Flug

| # | Komponente | Spezifikation | Menge | Preis | Lieferant |
|---|-----------|---------------|-------|-------|-----------|
| 19 | Yokohama 32" Crystal Clear | Nylon/PE, ventillos, 10er Pack | 1 Set | 105.95 EUR | yokohamaballoon.com |
| 20 | He 99.6% (Bauhaus Party Factory) | 0.14 m³, Einweg | 1 | 27.50 EUR | Bauhaus |
| 21 | Impuls-Heissiegelgeraet | Fuer Yokohama Nahtversiegelung | 1 | ~15 EUR | Amazon |
| 22 | Kapton Tape | Fuer Nahtverstaerkung | 1 Rolle | ~5 EUR | Amazon |
| 23 | u-blox MAX-M10S GPS | UART, ~0.6g, 25 mW | 1 | ~15-20 EUR | DigiKey/Mouser |

**Subtotal Flug**: ~170 EUR (inkl. 10 Yokohama Ballons)

## Kostenuebersicht

| Kategorie | Kosten |
|-----------|--------|
| Bereits gekauft (Inventar) | ~149 EUR |
| DIY Start (Prioritaet 1) | ~5 EUR |
| Solar-Erweiterung (Prioritaet 2) | ~7 EUR |
| Flight Minimal (Prioritaet 3) | ~20 EUR |
| Komfort-Optionen (Prioritaet 4) | ~7 EUR |
| Flug-Vorbereitung (Prioritaet 5) | ~170 EUR |
| **Nachbeschaffung Gesamt** | **~209 EUR** |

## Lieferanten

| Lieferant | Website | Bemerkung |
|-----------|---------|-----------|
| LCSC | lcsc.com | Passive, ESP-Module, guenstig |
| AliExpress | aliexpress.com | Module, Solarzellen, Sensoren |
| DigiKey | digikey.com | SKY66112, SP4T Switch, TPS7A02, Supercaps |
| Mouser | mouser.com | Alternative fuer DigiKey |
| JLCPCB | jlcpcb.com | PCB Fertigung (guenstig) |
| PCBWay | pcbway.com | Alternative PCB Fertigung |
| NiceRF | nicerf.com | LoRa2021 Module |
| Yokohama | yokohamaballoon.com | 32" Crystal Clear Ballons |
| Bauhaus | bauhaus.info | Party Factory He 99.6% |
