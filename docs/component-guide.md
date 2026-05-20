# Komponenten-Guide: Teile, Erklaerungen und Alternativen

Uebersicht aller Komponenten mit Begruendung, Alternativen und Empfehlung fuer
den Pico-Balloon-Tracker.

---

## 1. Mikrocontroller (MCU)

**Warum noetig**: Steuert alles - liest Sensoren, steuert den LR2021 ueber SPI,
verwaltet den Duty Cycle, kodiert Telemetrie.

| Option | Gewicht | Kosten | Vorhanden? | Bewertung |
|--------|---------|--------|------------|-----------|
| XIAO ESP32C3 | ~4g (Board) | 0 EUR | 20x da | Perfekt fuer Dev/DIY, USB onboard, zu schwer fuer Flight |
| ESP-C3-12F bare | ~1.0g | ~2 EUR | Nein | Flight-Board Standard. Flash integriert |
| ESP32-C3FH4 | ~0.8g | ~2 EUR | Nein | Noch kleiner, 4MB Flash intern |
| XIAO ESP32-C5 | ~4g | 0 EUR | 2x da | WiFi 6, als Bodenstation nutzbar |
| RP2040 Nano | ~2g | ~3 EUR | Nein | Alternative, aber kein ESP-IDF |

**Empfehlung**: XIAO C3 fuer Entwicklung, ESP-C3-12F fuer Flight-Board.

---

## 2. LoRa-Transceiver Modul

**Warum noetig**: Das Herzstueck. Sendet und empfaengt Funksignale ueber
LoRa/FLRC/Sub-GHz. Ohne dieses Modul kein Funk.

| Option | Gewicht | Kosten | Vorhanden? | Bewertung |
|--------|---------|--------|------------|-----------|
| NiceRF LoRa2021 | ~1.8g | 0 EUR | 4x da | Gen 4, Sub-GHz + 2.4 GHz, FLRC, RTToF, LR-FHSS |
| EBYTE E28-2G4M27S | ~2g | 0 EUR | 3x da | SX1281, 2.4 GHz only, +27 dBm PA, direct SPI |
| Seeed Wio-LR2021 | ~2g | ~10 EUR | Nein | Alternative LR2021 Modul |
| Ebyte E28-LR1121 | ~2g | ~8 EUR | Nein | Gen 3, nur LoRa/GFSK, kein FLRC |
| SX1262 Modul | ~1.5g | ~5 EUR | Nein | Nur Sub-GHz, kein 2.4 GHz, kein FLRC |
| SX1280 Modul | ~1.5g | ~6 EUR | Nein | Nur 2.4 GHz, hat Ranging, aber kein Sub-GHz |

**Empfehlung**: NiceRF LoRa2021 - bestes Feature-Set, bereits vorhanden.

### E28-2G4M27S als Entwicklungs-Plattform

Die EBYTE E28-2G4M27S Module bieten einen wichtigen Vorteil gegenueber den NiceRF LoRa2021 fuer die Entwicklung:

**Vorteile:**
- **+27 dBm (500 mW)** eingebauter PA — 5 dB mehr als SKY66112 FEM (+22 dBm), kein externer FEM noetig
- **Direkter SPI-Zugriff** auf SX1281 Register — kein USB-Seriell-Chip als Flaschenhals
- Kann als Throughput-Testplattform dienen (SX1280 USB Dongles haben CH341 als Durchsatz-Begrenzung)

**Nachteile:**
- Nur 2.4 GHz (kein Sub-GHz)
- SX1281 statt LR2021 (kein RTToF Ranging)
- ~2g Modulgewicht

**Nutzung im Projekt:**
1. Prototyping: +27 dBm TX testen ohne SKY66112 FEM
2. Throughput-Messung: Direkte SPI-Register-Auslesung ohne CH341-Bottleneck
3. Bodenstation: Als 2.4 GHz Empfaenger mit +27 dBm Sendeleistung

---

## 3. Antenne(n)

**Warum noetig**: Ohne Antenne sendet/empfaengt das Modul nichts. Die Antenne
bestimmt Gewinn und Richtcharakteristik.

| Option | Gewicht | Gewinn | Kosten | Bewertung |
|--------|---------|--------|--------|-----------|
| Draht-Dipol Sub-GHz | ~0.3g | ~2 dBi | 0 EUR | lambda/2 @ 868MHz = 16.4cm. Omnidirektional, simpel |
| Draht-Dipol 2.4 GHz | ~0.1g | ~2 dBi | 0 EUR | lambda/2 = 3.1cm. Sehr kurz |
| Draht-Monopol | ~0.2g | ~0-2 dBi | 0 EUR | lambda/4, noch einfacher als Dipol |
| PCB-Yagi (pro Wing) | ~0.5g | ~6-9 dBi | PCB-Kosten | Gerichtet, hoher Gewinn, braucht SP4T fuer 3D |
| Patch-Antenne | ~0g (auf PCB) | ~6-9 dBi | PCB-Kosten | Zirkular polarisiert, immun gegen Ballon-Drehung |
| Koaxial-Dipol (Sleeve) | ~0.5g | ~2 dBi | ~1 EUR | Robuster als blanker Draht |

**Empfehlung**: Start mit Draht-Dipol (kostenlos). PCB-Yagi fuer Flight-Board als
Optimierung.

---

## 4. Supercapacitors (Energiespeicher)

**Warum noetig**: Puffert die Solarenergie fuer Nacht/Schatten-Phasen. Batterien
sterben bei -60 C in der Stratosphaere. Supercaps funktionieren bis -40 C und
ueberstehen 500.000+ Ladezyklen.

| Option | Gewicht | Kapazitaet | Kosten | Bewertung |
|--------|---------|-----------|--------|-----------|
| 2x 3.3F 2.7V Serie | ~3.0g | 1.65F @ 5.4V | ~6 EUR | Komfort/Mittel. 73h Deep Sleep Reserve |
| 2x 1.5F 2.7V Serie | ~1.5g | 0.75F @ 5.4V | ~4 EUR | Minimal. ~36h Deep Sleep |
| 1x 1F 5.5V | ~2g | 1.0F @ 5.5V | ~3 EUR | Einfacher (kein Balancing), weniger Reserve |
| 1x 0.47F 5.5V | ~0.5g | 0.47F @ 5.5V | ~1 EUR | Ultra-leicht, nur ~15h Reserve |
| MLCC-Stack (10x 100uF) | ~0.3g | 0.001F | ~2 EUR | Nur fuer TX-Burst, keine Nacht-Reserve |
| Kein Cap (direkt Solar) | 0g | 0 | 0 EUR | Nur bei Sonne, kein TX in der Nacht |

**Empfehlung**: 2x 3.3F fuer Mittel-Plan, 1x 1F 5.5V fuer Minimal-Plan.

---

## 5. Solarzellen

**Warum noetig**: Einzige Energiequelle im Flug. Supercaps werden tagsueber
geladen und liefern Energie nachts.

| Option | Gewicht/Stk | Leistung | Vorhanden? | Bewertung |
|--------|------------|---------|------------|-----------|
| 52x19mm (0.5V 400mA) | ~0.5g | 0.2W peak | 100x da | Standard fuer Flight-Wings |
| 78x39mm (0.54W) | ~2g | 0.54W peak | 50x da | Groesser, fuer Dev/Prototyp |
| 10x 52x19mm (Mittel) | 5.0g | ~2.0W | Vorhanden | 2-3 pro Wing |
| 8x 52x19mm (Minimal) | 4.0g | ~1.6W | Vorhanden | 2 pro Wing |
| 28x12mm | ~0.2g | 0.05W | Nein | Ultra-leicht, aber sehr wenig Leistung |

**Verschaltung**: 3 Zellen in Serie = 1.5V. 4 Wings in Serie = 6V. Direkt in
Supercaps ohne Boost-Konverter.

**Empfehlung**: 12 Zellen fuer Mittel, 8 fuer Minimal. 78x39mm fuer DIY-Prototyp.

---

## 6. Spannungsregler (LDO)

**Warum noetig**: Supercaps liefern 0-5.4V (variabel). ESP32 und LR2021 brauchen
stabile 3.3V. Der LDO regelt das herunter.

| Option | Gewicht | IQ (Eigenverbrauch) | Kosten | Bewertung |
|--------|---------|-------------------|--------|-----------|
| TPS7A02 (3.3V) | ~0.05g | 25 nA | ~0.50 EUR | Perfekt. Fast kein Eigenverbrauch im Sleep |
| HT7333 | ~0.05g | ~4 uA | ~0.10 EUR | Guenstiger, aber 160x mehr IQ |
| AMS1117-3.3 | ~0.1g | ~5 mA | ~0.05 EUR | Billiger Standard-LDO. 5mA IQ = schlecht |
| ME6211 | ~0.05g | ~1 uA | ~0.20 EUR | Guter Kompromiss |
| Kein LDO (direkt an Cap) | 0g | 0 | 0 EUR | Riskant bei 5.4V! Nur bei <3.6V sicher |

**Empfehlung**: TPS7A02 - die 25 nA IQ sind unschlagbar. HT7333 als guenstige
Alternative.

---

## 7. BAT54 Schottky-Diode

**Warum noetig**: Verhindert dass sich Supercaps nachts ueber die Solarzellen
entladen (Rueckstrom).

| Option | Gewicht | Forward Drop | Kosten | Bewertung |
|--------|---------|-------------|--------|-----------|
| BAT54 | ~0.01g | 0.3V | ~0.10 EUR | Klassische Loesung |
| Keine Diode | 0g | 0V | 0 EUR | Solarzellen-Dunkelstrom meist vernachlaessigbar |
| P-MOSFET als Schalter | ~0.02g | ~0V | ~0.20 EUR | Besser als Diode, kein Spannungsabfall |
| Schottky SOD-323 (andere) | ~0.01g | 0.2-0.4V | ~0.10 EUR | Alternativen zur BAT54 |

**Empfehlung**: Weglassen fuer DIY/Prototyp. Fuer Flight-Board: P-MOSFET statt
BAT54 (kein Spannungsverlust).

---

## 8. BMP280 Sensor

**Warum noetig**: Misst Luftdruck und Temperatur. Daraus berechnet man die Hoehe
(wichtig fuer Telemetrie). Ohne Hoehendaten weiss man nicht in welcher Hoehe der
Ballon fliegt.

| Option | Gewicht | Kosten | Bewertung |
|--------|---------|--------|-----------|
| BMP280 Breakout | ~0.5g | ~1 EUR | Standard. I2C, genau genug |
| BMP280 bare chip | ~0.05g | ~0.50 EUR | Auf Flight-Board geloetet |
| BME280 (auch Feuchte) | ~0.5g | ~2 EUR | Feuchte bei -60 C irrelevant |
| BMP388 | ~0.3g | ~2 EUR | Neuer, etwas genauer |
| LR2021 getTemperature() | 0g | 0 EUR | Nur Chip-Temperatur, kein Druck/Hoehe |
| DPS310 | ~0.3g | ~2 EUR | Gute Alternative, weniger Temperatur-Drift |
| Kein Sensor | 0g | 0 EUR | Hoehe nur ueber GPS/TDoA abschaetzbar |

**Empfehlung**: BMP280 fuer Flight-Board (0.5g, guenstig, bewaehrt). Fuer Minimal:
weglassen und LR2021-internen Temp-Sensor nutzen.

---

## 9. SKY66112-11 FEM (PA + LNA)

**Warum noetig**: Power Amplifier boostet Sendeleistung von +12 auf +22 dBm
(Faktor 10x). LNA verbessert Empfangsempfindlichkeit um +14 dB. Zusammen: ~10 dB
mehr Reichweite.

| Option | Gewicht | Gewinn | Kosten | Bewertung |
|--------|---------|--------|--------|-----------|
| SKY66112-11 | ~0.1g | +10 dB TX, +14 dB RX | ~3 EUR | Optimale Loesung fuer 2.4 GHz |
| Kein FEM | 0g | 0 dB | 0 EUR | LR2021 direkt: +12 dBm (2.4GHz), +22 dBm (Sub-GHz) |
| SKY66112 +26 dBm Version | ~0.1g | +14 dB TX | ~4 EUR | Noch mehr Leistung |
| SE2435L | ~0.1g | +10 dB TX | ~2 EUR | Alternative von Skyworks |
| RFX2401C | ~0.1g | +8 dB TX | ~1 EUR | Billigere Alternative |

**Empfehlung**: Ohne FEM starten. Sub-GHz @ +22 dBm reicht fuer ~480 km. FEM erst
fuer 2.4 GHz Optimierung.

---

## 10. SP4T RF-Switch

**Warum noetig**: Schaltet das Funksignal zwischen 4 Antennen
(Leuchtturm-Modus). Ohne ihn kann man nur 1 Antenne nutzen.

| Option | Gewicht | Verlust | Kosten | Bewertung |
|--------|---------|---------|--------|-----------|
| SKY13351-378LF | ~0.1g | 0.8 dB | ~2 EUR | SP4T, 2.4 GHz |
| Kein Switch (1 Antenne) | 0g | 0 dB | 0 EUR | Einfachste Loesung |
| SP2T Switch | ~0.05g | 0.5 dB | ~1 EUR | 2 Antennen statt 4 |
| 2x SPDT statt SP4T | ~0.1g | 0.6 dB | ~2 EUR | Aehnliche Loesung |

**Empfehlung**: Ohne Switch starten (1 Antenne). SP4T erst fuer 4-Yagi
Flight-Board.

---

## 11. Passive Bauteile (Widerstaende, Kondensatoren)

### 11a. Entkopplungs-Caps (100nF, 10V)

**Warum noetig**: Stabilisieren die Spannungsversorgung von LR2021 und ESP32.
Ohne diese kann es zu brownouts beim Senden kommen (Stromspitzen bis 120 mA).

| Option | Bewertung |
|--------|-----------|
| 2-3x 100nF 0402 | Empfohlen. Eine am LR2021, eine am ESP32 |
| NiceRF Modul hat evtl. schon welche onboard | Pruefen! Viele Module haben integrierte Bypass-Caps |
| 10uF Tantal | Alternativ fuer groessere Stromspitzen |

**Empfehlung**: 2-3x 100nF. Pruefen ob NiceRF Modul schon welche hat.

### 11b. Supercap Balancing-Widerstaende (10kOhm)

**Warum noetig**: Zwei Supercaps in Serie muessen symmetrisch geladen werden.
Ohne Balancing kann ein Cap ueberspannt werden (>2.7V) und zerstoert werden.

| Option | Bewertung |
|--------|-----------|
| 2x 10kOhm parallel zu Caps | Standard-Loesung |
| 1x Supercap 5.5V statt 2x in Serie | Kein Balancing noetig |
| Aktiver Balancer (OPAMP) | Overkill |
| Kein Balancing | Riskant: Caps koennen ueberspannt werden |

**Empfehlung**: Einzelne 5.5V Cap nutzen oder 10kOhm Balancing-Widerstaende.

### 11c. Spannungsteiler (1MOhm fuer ADC)

**Warum noetig**: Supercap-Spannung (0-5.4V) muss auf 0-3.3V heruntergeteilt
werden damit der ADC sie messen kann.

| Option | Bewertung |
|--------|-----------|
| 2x 1MOhm Spannungsteiler | Klassisch. 2.7V am ADC bei 5.4V Cap |
| LR2021 getVoltage() nutzen | Interne Messung, kein externer ADC noetig |
| Hochohmiger OP | Overkill |
| Keine Spannungsmessung | Firmware weiss nicht ob genug Energie da ist |

**Empfehlung**: LR2021-internen getVoltage() nutzen statt externem ADC.

### 11d. I2C Pull-ups (4.7kOhm fuer BMP280)

**Warum noetig**: I2C Bus braucht Pull-up-Widerstaende auf SDA und SCL.

| Option | Bewertung |
|--------|-----------|
| 2x 4.7kOhm | Standard |
| BMP280 Breakout hat meist schon welche | Pruefen! |
| ESP32 interne Pull-ups | Zu schwach (~40kOhm), unzuverlaessig |
| Keine Pull-ups | I2C funktioniert nicht |

**Empfehlung**: Nur noetig wenn BMP280 Breakout keine eingebauten Pull-ups hat.

### 11e. Ferrite Beads

**Warum noetig**: Auf dem Flight-Board verlaufen Solarleitungen und
Antennenstruktur auf demselben PCB. Ferrite Beads verhindern dass Stoersignale
von den Solarleitungen die Antenne beeinflussen.

| Option | Bewertung |
|--------|-----------|
| 4x Ferrite Bead 0402 | Standard fuer Flight-Board |
| Keine Ferrites | OK fuer Prototyp mit separater Drahtantenne |
| Raumtrennung auf PCB | Gutes PCB-Layout kann Ferrites teilweise ersetzen |

**Empfehlung**: Nur fuer Flight-Board mit PCB-Yagi relevant.

### 11f. Bulk-Cap (10uF)

**Warum noetig**: Zusatzlicher Puffer fuer Stromspitzen beim Senden.

| Option | Bewertung |
|--------|-----------|
| 1-2x 10uF Keramik | Standard |
| NiceRF Modul hat evtl. schon Bulk-Cap | Pruefen |
| Kein Bulk-Cap | OK wenn Entkopplungs-Caps ausreichen |

---

## 12. PCB (Leiterplatte)

**Warum noetig**: Traegt alle Komponenten, verbindet sie elektrisch, bildet die
Antennenstruktur.

| Option | Gewicht | Kosten | Bewertung |
|--------|---------|--------|-----------|
| Hub 22x22mm + 4x Wing 65x28mm (0.6mm) | ~3.5g | ~15 EUR | Komfort-Plan |
| Hub 22x22mm + 4x Wing 65x28mm (0.4mm) | ~2.3g | ~15 EUR | Mittel-Plan (empfohlen) |
| Hub 22x22mm + 2x Wing 65x28mm (0.4mm) | ~1.4g | ~10 EUR | Minimal mit 2 Yagis |
| Nur Hub 22x22mm (0.4mm) + Drahtantennen | ~0.2g | ~5 EUR | Ultra-minimal |
| Breadboard/Protoboard | ~10g+ | ~2 EUR | Nur fuer DIY-Prototyp |
| Kein custom PCB | 0g | 0 EUR | Direktes Verkabeln |

**Empfehlung**: Protoboard fuer DIY, 0.4mm PCB fuer Flight.

---

## 13. Ballons (Traggas-Huellen)

**Warum noetig**: Traggas-Huelle erzeugt Auftrieb durch Verdraengung von Luft.
Ohne Ballon kein Flug. Die Wahl des Ballons bestimmt maximalen Flug, Gewicht
und Kosten massgeblich.

| Option | Gewicht | Netto-Auftrieb | Kosten | Bewertung |
|--------|---------|---------------|--------|-----------|
| DecoGlee 18" Folie (30x da) | ~10.5g | ~4.8g (He) | 0.37 EUR | Party-Ballon, kurzzeitiger Flug (4-8 Tage), guenstig |
| SBS-13 / SPS-13 | ~8g | ~20g+ (He) | ~35-50 EUR | Professioneller Pico-Ballon, mehrwoechiger Flug |
| Qualatex 36" Folie | ~60g | ~100g (He) | ~3 EUR | Schwer, viel Auftrieb, aber Overkill fuer Pico |
| Mylar 36" (geziehlt) | ~30g | ~50g (He) | ~3 EUR | Mittelweg |

**DecoGlee 18" Details (getestet, siehe docs/balloon-test-results.md):**
- Netto-Auftrieb: 4.8g pro Ballon mit Helium
- Leckrate (Indoor): 0.15 g/Tag pro Ballon
- Ventile muessen mit Flaecheneisen heissversiegelt werden
- Ueberfluessige Folienraender abschneiden (~1g pro Ballon sparen)
- Mehrere Ballons in vertikaler Kette fuer mehr Auftrieb
- Fuer Langzeitflug: Cut-Down-Mechanismus zwingend erforderlich

**Empfehlung**: DecoGlee fuer erste Testfluege (guenstig, vorhanden). SBS-13 fuer Langzeit-Mesh-Flug.

---

## 14. Cut-Down Mechanismus (Nichrome)

**Warum noetig**: Bei Mehr-Ballon-Konfiguration wird ein toter Ballon zur toten
Last (~10.5g). Da er mehr wiegt als er Auftrieb liefert (4.8g), muss er
abgeworfen werden. Ohne Cut-Down ist der erste Ballonausfall das Missionsende.

| Option | Gewicht/Kanal | Kosten | Bewertung |
|--------|-------------|--------|-----------|
| MOSFET + Nichrome pro Ballon | ~0.5g | ~1 EUR | Vollstaendiges Per-Ballon-Management |
| Einzelner Nichrome (ganze Kette) | ~0.5g | ~0.50 EUR | Einziger Cut, wirft gesamte Kette unterhalb |
| Kein Cut-Down | 0g | 0 EUR | Nur fuer Einzel-Ballon oder kurze Testfluege |

**Empfehlung**: Einzelner Nichrome fuer ersten Testflug. Per-Ballon fuer Langzeit-Mesh.

---

## 15. Mechanische Teile

**Warum noetig**: Halten alles zusammen, versiegeln den Ballon, befuellen mit
Helium.

| Option | Gewicht | Kosten | Bewertung |
|--------|---------|--------|-----------|
| 30 AWG Kupferdraht | ~0.5g/2m | ~2 EUR | Verbindungen, Antennen |
| DecoGlee 18" Folienballon | ~10.5g | 0.37 EUR | 30x vorhanden. Testflug, kurzzeitig |
| Mylar Folienballon 36" | ~60g | ~3 EUR | Langzeit-Alternative (Qualatex/Aeon) |
| Helium | - | ~15 EUR | Befuellung. Industrie 99% empfohlen |
| Wasserstoff | - | ~5 EUR | +8% Auftrieb, billiger, entzuendbar |
| Angelschnur (Dacron/Nylon) | ~0.5g/5m | ~1 EUR | Ballon-Tether (schmilzt mit Nichrome) |
| Flaecheneisen / Heissversiegler | - | ~10 EUR | Ballon-Ventile permanent verschliessen |
| Kabelbinder / Tape | ~0.5g | ~1 EUR | Befestigung |
| Heisskleber | ~0.5g | ~1 EUR | Abdichtung |

---

## 16. Tools und Testausruestung

| Option | Kosten | Bewertung |
|--------|--------|-----------|
| USB-UART Bridge (im XIAO) | 0 EUR | XIAO hat USB onboard |
| Logic Analyzer (Saleae Clone) | ~5 EUR | Fuer SPI Debugging |
| Multimeter | ~10 EUR | Spannung/Strom messen |
| 2. Radio Modul fuer RX Test | 0 EUR | 2. LoRa2021 aus dem 4er-Pack |
| SDR Dongle (RTL-SDR) | ~15 EUR | Optional: 868 MHz Sniffer |
| Ballon-Drucksensor + Pumpe | 0 EUR | Bereits vorhanden |

---

## Zusammenfassung: Was ist wirklich unverzichtbar?

### Absolut noetig (fliegt nicht ohne):

1. **MCU** (XIAO C3 oder ESP-C3-12F)
2. **LR2021 Modul** (NiceRF)
3. **Antenne** (mindestens ein Draht)
4. **Stromversorgung** (Solar + Supercaps oder Batterie)

### Stark empfohlen:

5. **LDO** (TPS7A02 - sonst brownout bei 5.4V)
6. **2-3x 100nF Caps** (Stabilitaet)
7. **1x Supercap** (fuer Nacht-Betrieb)

### Optional / Optimierungen:

8. BMP280 - Hoehe, oder LR2021-intern
9. BAT54 - oder weglassen
10. FEM - nur fuer 2.4 GHz @ +22 dBm (oder E28-2G4M27S mit +27 dBm ohne FEM)
11. SP4T Switch - nur fuer 4-Antennen-Setup
12. Ferrite Beads - nur auf Flight-PCB
13. Balancing Widerstaende - oder Einzelcap nutzen
14. Custom PCB - oder Protoboard/Loeten
15. Cut-Down (Nichrome) - fuer Mehr-Ballon-Langzeitflug
16. E28-2G4M27S - fuer Entwicklungs-Prototyping mit +27 dBm
