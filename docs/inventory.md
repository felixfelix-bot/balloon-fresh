# Inventarliste - Vorhandene Komponenten

Stand: 2026-05-21

## Mikrocontroller

| # | Komponente | Spezifikation | Menge | Quelle | Einzelpreis | Gesamtpreis |
|---|-----------|---------------|-------|--------|------------|------------|
| 1 | ESP32-C3_Mini_V1 | WiFi/BLE, USB-C, U.FL, 4MB Flash, RISC-V 160MHz | **20** | AliExpress | 3.89 EUR | 77.80 EUR |
| 2 | XIAO ESP32-C5 | WiFi 6 (2.4+5GHz), BT5, Zigbee, Thread, 8MB | **2** | AliExpress | 5.89 EUR | 11.78 EUR |

## RF Module

| # | Komponente | Spezifikation | Menge | Quelle | Einzelpreis | Gesamtpreis |
|---|-----------|---------------|-------|--------|------------|------------|
| 3 | NiceRF LoRa2021 | LR2021 Gen4, Sub-GHz + 2.4GHz, FLRC, RTToF, 19.72x15x2.2mm | **4** | NiceRF | ~10 EUR | ~40 EUR |
| 4 | EBYTE E28-2G4M27S | SX1281, 2.4 GHz, +27 dBm PA built-in, SPI interface | **3** | Amazon | ~8 EUR | ~24 EUR |

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

Details EBYTE E28-2G4M27S:
- Chip: Semtech SX1281 (2.4 GHz only)
- TX power: +27 dBm (500 mW) built-in PA — no external FEM needed
- Interface: Direct SPI (no serial chip bottleneck)
- Modulations: LoRa, FLRC, GFSK, LR-FHSS
- Key advantage: Direct register access for prototyping and throughput testing
- Can replace SKY66112 FEM in development setups
- Product: https://www.amazon.de/dp/B07QQSS2XD

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
| 8 | MS300 Waage | 0.01g Aufloesung | **1** | Fuer Gewichtsmessung (nicht fuer Magnete geeignet) |
| 9 | Messschieber | Digital, 0.01mm | **1** | Fuer Magnet-Dimensionierung |

## Ballons

| # | Komponente | Spezifikation | Menge | Quelle | Einzelpreis | Gesamtpreis |
|---|-----------|---------------|-------|--------|------------|------------|
| 10 | DecoGlee 18" Foil Balloons | Rund, Mylar, selbstversiegelnd | **30** | Amazon (DecoGlee) | 0.37 EUR | 11.09 EUR |
| 11 | Magenesis Neodym Magnete | 10x2mm, N35, ~1.21g/Stueck | **52** | Amazon (Magenesis) | 0.21 EUR | 10.99 EUR |

Details DecoGlee Ballons:
- Produkt: https://www.amazon.de/dp/B0F5H6VLPZ
- 30 Stück, 18 Zoll (~45.7cm) Durchmesser, rund
- Mylar-Folie, selbstversiegelndes Ventil
- Gemessener Netto-Auftrieb: ~4.8g pro Ballon mit Helium
- Geschätztes Huellengewicht: ~10.5g pro Ballon
- Leckrate (Indoor, Amazon-He): ~0.15 g/Tag pro Ballon
- Siehe docs/balloon-test-results.md fuer vollstaendige Testdaten

Details Magenesis Magnete:
- Produkt: https://www.amazon.de/dp/B06X977K8L
- 52 Stück, 9.97mm Durchmesser x 2.12mm Dicke (kalibriert gemessen)
- Gewicht: ~1.21g pro Magnet (berechnet aus Volumen + N35 Dichte 7.3 g/cm³)
- MS300 Waage kann Neodym-Magnete nicht zuverlaessig wiegen (magnetische Interferenz mit Dehnungsmessstreifen)
- Verwendet als Testgewichte fuer Ballon-Leckrate-Test
- Einige Magnete gebrochen (verbleibend: ~43 intakt + Fragmente)

## Zusammenfassung

| Kategorie | Wert |
|-----------|------|
| Gesamtinvestition | ~185 EUR |
| Verfuegbare MCU Boards | 22 (20x C3, 2x C5) |
| Verfuegbare RF Module | 7 (4x LR2021, 3x E28-2G4M27S) |
| Verfuegbare Solarzellen | 150 (100x 52x19mm, 50x 78x39mm) |
| Verfuegbare Ballons | 30x DecoGlee 18" Folie (Testflüge) |
| Verfuegbare Testgewichte | ~43x Magenesis Neodym 10x2mm |
| Noch zu beschaffen | Yokohama Ballons, H2, Heat Sealer, Kapton Tape (siehe unten) |

## Noch zu beschaffen

| # | Komponente | Fuer | Prioritaet | Gesch. Kosten | Quelle/Referenz |
|---|-----------|------|-----------|--------------|-----------------|
| 1 | ESP-C3-12F bare | Flight-Board | Mittel | ~2 EUR | AliExpress |
| 2 | BMP280 Breakout | DIY + Flight | Hoch | ~1 EUR | AliExpress |
| 3 | Supercaps 3.3F 2.7V (2x) | DIY + Flight | Hoch | ~6 EUR | AliExpress |
| 4 | TPS7A02 LDO | Flight | Hoch | ~0.50 EUR | DigiKey/Mouser |
| 5 | SKY66112-11 FEM | Flight (opt.) | Niedrig | ~3 EUR | DigiKey |
| 6 | SP4T RF Switch | Flight (opt.) | Niedrig | ~2 EUR | DigiKey |
| 7 | Passive (R, C) | Alle | Hoch | ~2 EUR | AliExpress |
| 8 | 30 AWG Kupferdraht | Alle | Hoch | ~2 EUR | AliExpress |
| 9 | **Yokohama Ballons (10er Pack)** | **Langzeitflug** | **Hoch** | **~EUR 130** | https://www.yokohamaballoon.com/ — Ruthroff: 528 Tage / 32 Runden (JR29) |
| 10 | **Industries Helium He 4.6 (ALbee Fly)** | **Langzeitflug** | **Hoch** | **~EUR 30-50** | Air Liquide ALbee Fly — https://www.airliquide.com/ — integrierter Druckminderer, 99.996% Reinheit |
| 10b | Wasserstoff H2 (Fallback) | Langzeitflug (opt.) | Niedrig | ~EUR 30 | Industrie-Gaslieferant — verschoben bis He Erfahrung vorliegt (ADR-011) |
| 11 | **Impulslöter (Heat Sealer)** | **Alle Ballonflüge** | **Hoch** | **~EUR 15** | Amazon — https://www.theastroimager.com/picoballoning/pico-ballooning/ (Ruthroff: "heat seal + Kapton tape") |
| 12 | **Kapton Tape** | **Alle Ballonflüge** | **Hoch** | **~EUR 5** | Amazon — Ruthroff: "apply 2-3 heat seals + Kapton tape over seal" |
| 13 | Mylar Ballon 36" | Flug (Test) | Niedrig | ~3 EUR | AliExpress |
| 14 | Helium (Industrie 99.999%) | Flug (reserve) | Niedrig | ~EUR 30 | Linde/Messer — falls ALbee nicht verfuegbar |
| 15 | PCB Bestellung (Flight) | Flight | Mittel | ~15 EUR | JLCPCB |
| 16 | Protoboard | DIY | Hoch | ~2 EUR | AliExpress |

**Minimale Nachbestellung fuer DIY-Start**: ~12 EUR (BMP280 + Supercaps + Passive + Draht + Protoboard)
**Erste Flugfertig (Yokohama + He 4.6 + Heat Sealer + Kapton)**: ~EUR 170-190 (ADR-011)
**Volle Flight-Ausruestung**: ~EUR 250
