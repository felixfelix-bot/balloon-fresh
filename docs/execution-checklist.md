# Ausfuehrungs-Checkliste: DIY Prototyp + Ballontest

Physische Aufgaben die DU erledigen musst bevor wir testen koennen.
Hacken ab wenn erledigt.

---

## Phase 0: Inventar pruefen (HEUTE)

### Verfuegbarkeit bestaetigen
- [ ] **20x XIAO ESP32C3** - Auspacken, 2 Stk bereitlegen
- [ ] **2x XIAO ESP32-C5** - Falls als Bodenstation genutzt
- [ ] **4x NiceRF LoRa2021 Module** - Auspacken, Pinbelegung pruefen (18-Pin)
- [ ] **100x Solarzellen 52x19mm** - Verfuegbarkeit bestaetigen
- [ ] **50x Solarzellen 78x39mm** - Verfuegbarkeit bestaetigen
- [ ] **Drucksensor** - Finden und identifizieren (welcher Typ? I2C? Analog?)
- [ ] **Pumpe** - Finden und testen (funktioniert sie noch?)

### Zu pruefende Haushalts-/Werkstattgegenstaende
- [ ] **Protoboard / Lochrasterplatte** - Irgendwo eine kleine (5x7cm) gefunden?
- [ ] **Lochrasterplatte / Perfboard** - Alternative: Streifenraster
- [ ] **Kupferdraht** - Irgendwelcher duenner Draht (0.1-0.3mm) vorhanden?
  - Antennendraht: ~17cm fuer 868 MHz Dipol
  - Antennendraht: ~3cm fuer 2.4 GHz Dipol
- [ ] **Kondensatoren** - Irgendwelche 100nF Keramik-Caps im Haus?
  - Oft auf alten PCBs, Arduino-Shields, etc.
  - Brauchen: 2-3x 100nF (Spannungsstabilisierung)
- [ ] **Widerstaende** - Irgendwelche 4.7kOhm (I2C Pullups) vorhanden?
- [ ] **Lötzinn + Lötkolben** - Funktioniert? Spitze sauber?
- [ ] **USB-C Kabel** - Fuer XIAO ESP32C3 (mindestens 2 Stk)
- [ ] **Dupont-Kabel (Female-Female)** - Fuer Breadboard-Verbindung
- [ ] **Breadboard** - Falls kein Loeten moeglich
- [ ] **Multimeter** - Fuer Spannungs- und Widerstandsmessung

### Pruefen ob folgende Teile vorhanden sind (Ersatz/Bastelkram)
- [ ] **Elektrolyt-Caps** - 10uF, 47uF, 100uF? (Entkopplung)
- [ ] **5V Netzteil / Powerbank** - Als alternative Stromversorgung fuer Tests
- [ ] **Zweites Laptop** - Fuer Bodenstation (oder Terminal nebenbei)
- [ ] **Mylar/Folienballon** - Irgend ein alter Geburtstagsballon zum Testen?
- [ ] **Tesa / Heisskleber** - Zum Abdichten von Ballon-Haelzen

---

## Phase 1: DIY Prototyp aufbauen (Tag 1-2)

### Schritt 1: Arbeitsplatz einrichten
- [ ] Loetstation aufbauen, auf ~320 C einstellen
- [ ] Belueftung sicherstellen (Loetdampfe!)
- [ ] Werkzeug bereitlegen: Pinzette, Seitenschneider, Abisolierzange
- [ ] XIAO ESP32C3 auspacken und per USB anschliessen
- [ ] Pruefen: Wird der XIAO als USB-Geraet erkannt? (`lsusb` oder Gerätemanager)

### Schritt 2: XIAO ESP32C3 testen
- [ ] USB-C Kabel an XIAO anschliessen
- [ ] Pruefen ob Serial Port erscheint (`ls /dev/ttyACM*` oder `/dev/ttyUSB*`)
- [ ] Einfaches Blink-Testprogramm flashen (wir stellen das bereit)
- [ ] LED blinkt? → MCU funktioniert

### Schritt 3: NiceRF LoRa2021 Modul begutachten
- [ ] Modul aus Antistatik-Beutel nehmen
- [ ] Pin 1 (VCC) identifizieren - meist markiert mit Punkt/Loch
- [ ] Alle 18 Pins zaehlen und mit Pinout-Tabelle abgleichen
- [ ] Mit Multimeter: Durchgang zwischen GND-Pins pruefen (Pin 2,8,11,12,18)
- [ ] Keine sichtbaren Beschaedigungen? → OK

### Schritt 4: Protoboard-Verkabelung (Breadboard oder gelötet)

Verbindungen XIAO → LoRa2021:

```
XIAO          →  LoRa2021
──────────────────────────────
3V3 (Pin)     →  Pin 1 (VCC)
GND (Pin)     →  Pin 2,8,11,12,18 (GND) - mindestens einen verbinden
D7 (GPIO7)    →  Pin 3 (MISO)
D6 (GPIO6)    →  Pin 4 (MOSI)
D5 (GPIO5)    →  Pin 5 (SCK)
D10 (GPIO10)  →  Pin 6 (NSS/CS)
D4 (GPIO4)    →  Pin 7 (BUSY)
D3 (GPIO3)    →  Pin 14 (RST)
D2 (GPIO2)    →  Pin 15 (DIO9/IRQ)
```

- [ ] Alle 9 Verbindungen hergestellt (Breadboard-Draht oder gelötet)
- [ ] **Keine 3.3V/GND Kurzschlüesse!** Vor dem Anschliessen mit Multimeter pruefen
- [ ] XIAO per USB anschliessen
- [ ] Stromaufnahme pruefen (sollte ~10-30mA sein, nicht >200mA)

### Schritt 5: Drahtantennen anloeten
- [ ] **Sub-GHz Antenne** (Pin 9, ANT):
  - ~16.4 cm blanker Draht als lambda/2 Dipol bei 868 MHz
  - Alternativ: ~8.2 cm als lambda/4 Monopol
  - An Pin 9 anloeten
- [ ] **2.4 GHz Antenne** (Pin 10, 2.4G):
  - ~3.1 cm Draht als lambda/2 Dipol bei 2.4 GHz
  - Alternativ: ~1.5 cm als lambda/4 Monopol
  - An Pin 10 anloeten
- [ ] Beide Antennen gerade nach oben/abwaerts biegen

### Schritt 6: Erster SPI-Test
- [ ] Firmware flashen (wir stellen bereit)
- [ ] Serial Monitor oeffnen (`idf.py monitor` oder `minicom`)
- [ ] Chip ID sollte erscheinen (0x????)
- [ ] Wenn Chip ID lesbar → SPI funktioniert!

### Schritt 7: Zweiter XIAO + LoRa2021 (Bodenstation)
- [ ] Schritt 3-6 mit zweitem XIAO + zweitem LoRa2021 wiederholen
- [ ] Auf gleiche Weise verkabeln
- [ ] Beide Boards nebeneinander platzieren

### Schritt 8: Erster LoRa TX/RX Test
- [ ] Board 1: TX-Modus flashen
- [ ] Board 2: RX-Modus flashen
- [ ] Pruefen: Empfängt Board 2 die Nachricht?
- [ ] RSSI-Wert notieren (sollte bei <1m Abstand: -20 bis -40 dBm)
- [ ] Abstand schrittweise erhoehen und RSSI notieren

---

## Phase 2: Ballon-Drucktest (parallel, Tag 1-3)

### Schritt 1: Drucksensor identifizieren
- [ ] Sensor finden
- [ ] Typ bestimmen: I2C (BMP280/BME280)? Analog? SPI?
- [ ] Datenblatt googeln falls noetig
- [ ] Pinbelegung herausfinden
- [ ] Falls BMP280/BME280: perfekt, wir koennen unsere Firmware nutzen
- [ ] Falls anderer I2C-Sensor: Adresse mit I2C-Scanner finden
- [ ] Falls analoger Sensor: ADC-Firmware anpassen

### Schritt 2: Testaufbau
- [ ] XIAO ESP32C3 (3. Board) + Drucksensor verkabeln
- [ ] Sensor an Pumpe/Ballon anschliessen (Schlauch + Kabelbinder oder Tesa)
- [ ] Falls BMP280: SDA→D8, SCL→D9, VCC→3V3, GND→GND
- [ ] Pruefen: Wird der Sensor am I2C erkannt?

### Schritt 3: Ballon testen
- [ ] Einen Folienballon besorgen (falls keiner vorhanden)
  - Drogerie (dm, Rossmann): ~1-3 EUR
  - Amazon: Qualatex 36" (~3 EUR)
- [ ] Ballon mit Pumpe aufpumpen (nicht zu voll! max. ~1.1 bar)
- [ ] Druck am Sensor ablesen: Stimmt die Anzeige?
- [ ] Ballon verschliessen (heisskleben oder Klemme)
- [ ] Loggen starten (wir stellen Firmware bereit)
- [ ] Mindestens 4 Stunden laufen lassen
- [ ] Daten auswerten (wir stellen Python-Script bereit)

---

## Phase 3: Solar-Test (Tag 3-5)

### Schritt 1: Solarzellen-Test
- [ ] 3x 78x39mm Zellen nehmen
- [ ] In Serie schalten (Plus von Zelle 1 → Minus von Zelle 2, etc.)
- [ ] Mit Multimeter: Spannung im Sonnenlicht messen
  - Erwartet: ~1.5V (3 x 0.5V)
  - Kurzschlussstrom: ~400mA
- [ ] In Schatten stellen: Spannung sollte auf ~0V fallen

### Schritt 2: Solar + Supercap Test (falls Supercaps vorhanden)
- [ ] Falls Supercaps noch nicht gekauft: bestellen (Prioritaet 2)
- [ ] 2x 3.3F in Serie schalten (+ 2x 10kOhm Balancing parallel)
- [ ] Solar-Array (6x 78x39mm in Serie = 3V) an Supercaps anschliessen
- [ ] Spannung am Supercap ueber Stunden beobachten
- [ ] Ladekurve notieren

---

## Phase 4: FLRC + Sub-GHz Test (Tag 5-7)

### Schritt 1: Frequenz wechseln
- [ ] Firmware auf 868 MHz LoRa aendern
- [ ] TX/RX Test wiederholen
- [ ] Reichweite im Freien testen (mit Draht-Dipol)

### Schritt 2: FLRC High-Speed
- [ ] Firmware auf FLRC 650 kbps aendern
- [ ] TX/RX Test mit grossem Payload (255 Bytes)
- [ ] Datenrate messen (Zeit pro Paket)

### Schritt 3: RTToF Ranging
- [ ] Firmware auf Ranging-Modus aendern
- [ ] Abstand zwischen 2 Boards messen
- [ ] Mit Massband vergleichen: Wie genau?

---

## Phase 5: Integration Test (Tag 7-10)

### Schritt 1: Duty Cycle Test
- [ ] Deep Sleep + Wake + TX + Sleep Zyklus programmieren
- [ ] Stromverbrauch messen (Multimeter in Reihe)
  - Deep Sleep: soll < 20 µA sein
  - TX Burst: soll < 120 mA sein
- [ ] Laeuft der Zyklus stabil ueber 100+ Iterationen?

### Schritt 2: Bodenstation Software
- [ ] Python Script auf Laptop starten
- [ ] 2. XIAO + LoRa2021 als RX testen
- [ ] Telemetrie-Pakete empfangen und dekodieren
- [ ] CRC-Check bestanden?

---

## Benoetigte Einkaeufe (falls nicht im Haus)

| # | Teil | Gesch. Preis | Dringlichkeit | Kaufen bei |
|---|------|-------------|---------------|-----------|
| 1 | BMP280 Breakout | ~1 EUR | Hoch (Ballontest) | AliExpress |
| 2 | Protoboard 5x7cm | ~1 EUR | Hoch (Aufbau) | AliExpress/Amazon |
| 3 | Dupont-Kabel F-F (20er Set) | ~2 EUR | Hoch (Verkabelung) | Amazon |
| 4 | 30 AWG Kupferdraht | ~2 EUR | Mittel (Antennen) | Amazon |
| 5 | Folienballon 36" | ~1-3 EUR | Mittel (Drucktest) | Drogerie |
| 6 | Supercaps 3.3F 2.7V (2x) | ~6 EUR | Mittel (Solar-Test) | DigiKey |
| 7 | TPS7A02 LDO | ~0.50 EUR | Niedrig | LCSC |

**Minimum fuer sofortigen Start**: BMP280 + Protoboard + Dupont-Kabel = ~4 EUR
