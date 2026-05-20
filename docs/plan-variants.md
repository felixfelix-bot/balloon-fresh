# Plan-Varianten: Komfort / Mittel / Minimal / DIY

Uebersicht der vier Hardware-Varianten mit Gewichtsbudget und Prioritaet.

---

## Varianten-Uebersicht

| Aspekt | DIY v0.1 | Minimal | Mittel | Komfort |
|--------|----------|---------|--------|---------|
| Zweck | Entwicklung | Flug (ultra-leicht) | Flug (empfohlen) | Flug (alle Features) |
| MCU | XIAO ESP32C3 | ESP-C3-12F | ESP-C3-12F | ESP-C3-12F |
| RF | NiceRF LR2021 | NiceRF LR2021 | NiceRF LR2021 | NiceRF LR2021 |
| Gewicht | ~15g (mit Board) | ~8-9g | ~12-13g | ~16.6g |
| PCB | Protoboard | 0.4mm (nur Hub) | 0.4mm (Hub + Wings) | 0.6mm (Hub + Wings) |
| Antennen | Draht | 1x Draht | 1-2x Draht + PCB-Yagis | 4x PCB-Yagis + SP4T |
| FEM | Nein | Nein | Nein | Ja (SKY66112) |
| Sensor | Optional | Nein | Ja (BMP280) | Ja (BMP280) |
| Strom | USB/Solar | Solar+Caps | Solar+Caps | Solar+Caps |
| Kosten extra | ~12 EUR | ~30 EUR | ~35 EUR | ~40 EUR |

---

## DIY v0.1 (Entwicklungs-Prototyp)

### Ziel
Erste Tests ohne custom PCB. Sofort startbar mit vorhandenen Teilen.

### Komponenten

| Teil | Option | Gewicht |
|------|--------|---------|
| MCU | XIAO ESP32C3 (von 20) | ~4g |
| RF | NiceRF LoRa2021 (von 4) | ~1.8g |
| Antenne Sub-GHz | Draht-Dipol 16.4cm | ~0.3g |
| Antenne 2.4 GHz | Draht-Dipol 3.1cm | ~0.1g |
| Strom | USB (Entwicklung) oder 78x39mm Solar + Supercaps | ~5g |
| Sensor | BMP280 Breakout (optional) | ~0.5g |
| Verbindung | Protoboard + Draht | ~3g |
| **Total** | | **~12-15g** |

### Was getestet werden kann
- SPI-Kommunikation mit LR2021 (Chip ID, Register)
- LoRa TX/RX @ 868 MHz und 2.4 GHz
- FLRC High-Speed Modus
- RSSI-Messungen
- RTToF Ranging zwischen 2 Modulen (4 Module vorhanden!)
- Duty Cycle + Deep Sleep Stromverbrauch
- Bodenstation Software
- Ballon-Drucktest (Sensor + Pumpe vorhanden)

### NiceRF LoRa2021 Pin-Mapping (XIAO ESP32C3)

```
NiceRF Pin   Funktion    XIAO GPIO   XIAO Pin
────────────────────────────────────────────────
Pin 1        VCC         3.3V        3V3
Pin 2,8,11,12,18  GND   GND         GND
Pin 3        MISO        GPIO7       D7
Pin 4        MOSI        GPIO6       D6
Pin 5        SCK         GPIO5       D5
Pin 6        NSS         GPIO10      D10
Pin 7        BUSY        GPIO4       D4
Pin 9        ANT (Sub-GHz)
Pin 10       2.4G (2.4 GHz)
Pin 14       RST         GPIO3       D3
Pin 15       DIO9 (IRQ)  GPIO2       D2
Pin 16       DIO8        GPIO1       D1
Pin 17       DIO7        GPIO0       D0
```

Hinweis: RadioLib irqDioNum = 9 setzen und setDioFunction() fuer DIO9 als IRQ aufrufen.

### Naechste Schritte
1. RadioLib als ESP-IDF Component integrieren
2. XIAO + LoRa2021 auf Protoboard verkabeln
3. Erster SPI-Test (Chip ID lesen)
4. LoRa TX/RX zwischen 2 Boards testen
5. FLRC-Modus testen
6. Bodenstation mit 2. XIAO + 2. LoRa2021 aufbauen

---

## Minimal-Plan (~8-9g, Ultra-Leicht)

### Ziel
Minimales Gewicht fuer maximalen Auftrieb. Nur die unbedingten Komponenten.

### Komponenten

| Teil | Option | Gewicht |
|------|--------|---------|
| Hub PCB | 22x22mm, 0.4mm FR4 | 0.2g |
| MCU | ESP-C3-12F bare | 1.0g |
| RF | NiceRF LoRa2021 | 1.8g |
| Antenne Sub-GHz | Draht-Dipol 16.4cm | 0.3g |
| Antenne 2.4 GHz | Draht-Dipol 3.1cm | 0.1g |
| Supercaps | 1x 1F 5.5V | 2.0g |
| Solar | 6x 52x19mm (2x3 Serie) | 3.0g |
| LDO | TPS7A02 | 0.05g |
| Passiv | 2-3x 100nF | 0.05g |
| Loeten + Draht | | 0.2g |
| **Total** | | **~8.7g** |

### Features
- Sub-GHz @ +22 dBm: ~480 km Reichweite
- 2.4 GHz @ +12 dBm: ~150 km Reichweite
- Kein FEM, kein SP4T, kein BMP280
- LR2021-interner Temperatursensor fuer Telemetrie
- LR2021-intern getVoltage() fuer Spannungsueberwachung
- ~24h Deep Sleep Reserve (1F Cap)

### Einsparungen vs. Komfort
- Keine Wing-Boards / Yagis: -2.3g
- Weniger Solarzellen (6 statt 12): -3.0g
- Kein FEM: -0.1g
- Kein SP4T: -0.1g
- Kein BMP280: -0.5g
- Kleinere Supercaps: -1.0g
- Duennere PCB: -0.1g
- **Gesamt-Ersparnis: ~7g**

---

## Mittel-Plan (~12-13g, Empfohlen fuer Flug)

### Ziel
Gutes Gleichgewicht aus Gewicht, Features und Reichweite. Behaelt Solar-Kapazitaet und Sensorik.

### Komponenten

| Teil | Option | Gewicht |
|------|--------|---------|
| Hub PCB | 22x22mm, 0.4mm FR4 | 0.2g |
| 2x Wing PCB | 65x28mm, 0.4mm FR4 | 1.1g |
| MCU | ESP-C3-12F bare | 1.0g |
| RF | NiceRF LoRa2021 | 1.8g |
| Antenne Sub-GHz | Draht-Dipol 16.4cm | 0.3g |
| Antenne 2.4 GHz | 2x PCB-Yagi auf Wings | 0g (geaetzt) |
| SP4T Switch | SKY13351-378LF | 0.1g |
| Supercaps | 2x 3.3F 2.7V Serie (1.65F) | 3.0g |
| Solar | 12x 52x19mm (6 pro Wing x 2 Wings) | 6.0g |
| LDO | TPS7A02 | 0.05g |
| Sensor | BMP280 | 0.5g |
| Passiv | 100nF + Pullups + Balancing | 0.15g |
| Loeten + Draht | | 0.2g |
| **Total** | | **~14.4g** |

Hmm, knapp ueber. Alternative mit 10 Solarzellen:

| Teil | Aenderung | Gewicht |
|------|----------|---------|
| Solar | 10x statt 12x (-2g) | 5.0g |
| Wings | nur 1 Wing mit Yagi (-0.55g) | 0.55g |
| SP4T | entfaellt (-0.1g) | 0g |
| **Total** | | **~12.6g** |

### Features
- Sub-GHz @ +22 dBm: ~480 km (Draht-Dipol, omnidirektional)
- 2.4 GHz @ +12 dBm: ~200 km (PCB-Yagi, gerichtet)
- BMP280: Druck, Temperatur, Hoehe
- 73h Deep Sleep Reserve (1.65F Caps)
- Volle Solarkraft (12 oder 10 Zellen)
- Wetter-Temperatur-Kompensation
- Leuchtturm-Modus (wenn 2 Wings mit Yagis)

### Optimierung auf <12g (falls noetig)
- 8 Solarzellen statt 10: -1g → 11.6g
- BMP280 weglassen: -0.5g → 11.1g
- Einzelnen 5.5V Cap statt 2x Serie: -1g + weniger Passiv → 10.5g

---

## Komfort-Plan (~16.6g, Alle Features)

### Ziel
Maximale Feature-Dichte. Urspruenglicher Plan. Leicht ueber 15g.

### Komponenten

| Teil | Option | Gewicht |
|------|--------|---------|
| Hub PCB | 22x22mm, 0.6mm FR4 | 0.3g |
| 4x Wing PCB | 65x28mm, 0.6mm FR4 | 3.2g |
| MCU | ESP-C3-12F bare | 1.0g |
| RF | NiceRF LoRa2021 | 1.8g |
| FEM | SKY66112-11 | 0.1g |
| SP4T Switch | SKY13351-378LF | 0.1g |
| Antennen | 4x PCB-Yagi auf Wings | 0g (geaetzt) |
| Sub-GHz Antenne | Draht-Dipol | 0.3g |
| Supercaps | 2x 3.3F 2.7V Serie | 3.0g |
| Solar | 12x 52x19mm | 6.0g |
| LDO | TPS7A02 | 0.05g |
| Sensor | BMP280 | 0.5g |
| Passiv | R, C, Ferrites | 0.25g |
| Loeten + Draht | | 0.2g |
| **Total** | | **~16.8g** |

### Features
- Sub-GHz @ +22 dBm: ~480 km
- 2.4 GHz @ +22 dBm (mit FEM): ~300+ km
- 4x PCB-Yagi mit Leuchtturm-Modus
- BMP280: Druck, Temperatur, Hoehe
- 73h Deep Sleep Reserve
- Volle 3D-Abdeckung

---

## Antennen-Strategie (fuer alle Varianten)

### Ballon-Seite

| Variante | Sub-GHz Antenne | 2.4 GHz Antenne | Switch |
|----------|----------------|----------------|--------|
| DIY | Draht-Dipol 16.4cm | Draht-Dipol 3.1cm | Kein |
| Minimal | Draht-Dipol 16.4cm | Draht-Dipol 3.1cm | Kein |
| Mittel | Draht-Dipol 16.4cm | 1-2x PCB-Yagi | SP2T/SP4T |
| Komfort | Draht-Dipol 16.4cm | 4x PCB-Yagi | SP4T |

### Bodenstation

| Antenne | Frequenz | Polarisation | Gewinn | Zweck |
|---------|----------|-------------|--------|-------|
| 868 MHz Yagi | Sub-GHz | Linear | ~12 dBi | Sub-GHz Empfang |
| 2.4 GHz Helical | 2.4 GHz | **Circular (RHCP)** | ~12-15 dBi | 2.4 GHz Empfang (rotation-immun) |
| 2.4 GHz Yagi | 2.4 GHz | Linear | ~16 dBi | Alternative (aber: 3 dB CP-Verlust) |

### Warum Circular Polarization am Boden?

```
Ballon mit linearer Yagi dreht sich:
  0° Rotation:  0 dB Verlust
  45° Rotation: 3 dB Verlust
  90° Rotation: 20-30 dB Verlust (Signal verschwindet!)

Aber mit CP-Antenne am Boden:
  Beliebige Rotation: IMMER genau 3 dB Verlust
  → Vorhersagbar, konstant, kein Ausfall
```

Siehe auch: docs/antenna-strategy.md

---

## Wiederverwendbare Teile zwischen Varianten

| Teil | DIY | Minimal | Mittel | Komfort |
|------|-----|---------|--------|---------|
| NiceRF LR2021 Modul | 1 | 1 | 1 | 1 |
| XIAO ESP32C3 | Ja | - | - | - |
| ESP-C3-12F bare | - | Ja | Ja | Ja |
| TPS7A02 LDO | Nein (USB) | Ja | Ja | Ja |
| BMP280 | Optional | Nein | Ja | Ja |
| SKY66112 FEM | Nein | Nein | Nein | Ja |
| SP4T Switch | Nein | Nein | Optional | Ja |
| Solar 52x19mm | - | 6 | 10-12 | 12 |
| Solar 78x39mm | 5-6 | - | - | - |
| Supercaps | Optional | 1x 1F | 2x 3.3F | 2x 3.3F |
| Firmware (RadioLib) | Ja | Ja | Ja | Ja |
| Bodenstation | Ja | Ja | Ja | Ja |
| Telemetrie-Format | Ja | Ja | Ja | Ja |

Alle 4 Varianten nutzen **dieselbe Firmware-Codebasis** (RadioLib + ESP-IDF).
Unterschiede sind nur Compile-Time-Konfigurationen (#define).

---

## Prioritaet und Reihenfolge

```
Phase 0: DIY v0.1 aufbauen (Woche 1)
  → XIAO + LoRa2021 + Drahtantenne auf Protoboard
  → RadioLib integrieren, SPI-Test
  → LoRa TX/RX zwischen 2 Boards
  → Ballon-Drucktest parallel

Phase 1: DIY v0.2 erweitern (Woche 2)
  → + BMP280 + Supercaps + Solarzellen
  → Duty Cycle + Deep Sleep testen
  → Bodenstation Software
  → FLRC + Sub-GHz testen

Phase 2: Flight Minimal oder Mittel designen (Woche 3-4)
  → PCB Design (KiCad/SKiDL)
  → 0.4mm FR4
  → PCB-Yagi simulieren + designen
  → Gerber exportieren + bestellen

Phase 3: Flight-Board bauen + testen (Woche 5-6)
  → PCBs bestuecken
  → Firmware flashen
  → Freifeld-Test
  → Bodentest mit Ballon

Phase 4: Flug vorbereiten (Woche 7+)
  → Ballon auswaehlen (Drucktest-Ergebnis)
  → Helium besorgen
  → Finaler Weight-Check
  → Start!
```
