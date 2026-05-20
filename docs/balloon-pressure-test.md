# Mylar-Ballon Drucktest

## Ziel

Testen ob guenstige Mylar-Folienballons ueber laengere Zeit einen bestimmten
Druck aushalten ohne merklich zu lecken. Ein Ballon der in der Stratosphaere
ueber Stunden/Tage halten soll, muss auch am Boden dicht bleiben.

## Problem

Pico-Balloons nutzen Qualatex oder Aeon 36" Folienballons. Diese sind nicht
fuer Dauerdruck ausgelegt. Billig-Alternativen (Amazon, AliExpress) koennten
schneller lecken. Wir muessen das Leak-Rate quantifizieren.

## Setup

### Variante A: Elektronisch (empfohlen)

```
[Pumpe] → [Ballon] → [Drucksensor] → [XIAO ESP32C3] → USB Serial → PC
```

Hardware:
- XIAO ESP32C3 (von 20)
- BMP280 Breakout (~1 EUR, noch zu kaufen)
- Pumpe + Drucksensor (vorhanden)
- 30 AWG Kupferdraht oder Dupont-Kabel
- USB-Kabel

Verbindung:
- BMP280 SDA → XIAO D8 (GPIO8)
- BMP280 SCL → XIAO D9 (GPIO9)
- BMP280 VCC → 3.3V
- BMP280 GND → GND

### Variante B: Einfach (Quick-Test)

- Ballon aufpumpen auf definierten Druck
- Umfang mit Massband messen
- Staende kontrollieren (Umfang = proportional zu Volumen = proportional zu Druck)
- Keine Elektronik, aber ungenauer

## Test-Prozedur

### Test 1: Kurzer Dichtigkeitstest (2-4 Stunden)

Ziel: Schnell aussortieren ob ein Ballon offensichtlich undicht ist.

1. Ballon mit Pumpe auf 1.05 bar aufpumpen
2. Drucksensor im Hals befestigen (luftdicht)
3. XIAO + BMP280 messen alle 30 Sekunden
4. Daten via USB Serial loggen
5. Nach 4 Stunden: Leak-Rate berechnen

Erwartet: Gute Ballons verlieren < 1 mbar/Stunde.

### Test 2: Langzeittest (24-72 Stunden)

Ziel: Realistische Simulation eines mehrtagigen Flugs.

1. Ballon auf 1.05 bar aufpumpen
2. Messintervall: 5 Minuten
3. Temperatur mitloggen (Druck aendert sich mit Temperatur!)
4. 24-72 Stunden laufen lassen
5. Druckverlauf plotten

Temperatur-Kompensation:
```
Ideale Gasgleichung: P*V = n*R*T
Wenn V konstant (Ballon dehnt nicht weiter): P ~ T
Delta P (mbar) = P * Delta T / T
z.B. bei 1050 mbar und 5 K Aenderung: Delta P = 1050 * 5/293 = 18 mbar
```

### Test 3: Multi-Ballon Vergleich

Ziel: Verschiedene Marken/Groessen vergleichen.

- 3-4 Ballons gleichzeitig testen
- Gleicher Startdruck
- Ueber 24 Stunden vergleichen
- Kandidaten: Qualatex 36", Aeon 36", Amazon-Billig, AliExpress

### Test 4: Temperatur-Extrem (optional)

- Ballon in Kuehlschrank (-18 C) oder Gefriertruhe testen
- Simuliert Stratosphaeren-Temperaturen (teilweise)
- Beobachten ob Nahte bei Kaelte reissen

## Firmware: balloon_pressure_test

Neues ESP-IDF Mini-Projekt unter `tools/balloon_pressure_test/`.

Funktionalitaet:
- BMP290/BMP280 alle N Sekunden lesen (Druck + Temperatur)
- Ausgabe auf USB Serial: Timestamp, Druck (mbar), Temperatur (C)
- Konfigurierbares Messintervall (default: 30s)
- Deep Sleep zwischen Messungen (optional, fuer Batteriebetrieb)

Beispiel-Output:
```
[00:00:00] 1050.2 mbar  22.3 C
[00:00:30] 1050.1 mbar  22.3 C
[00:01:00] 1049.9 mbar  22.2 C
...
[04:00:00] 1046.3 mbar  21.8 C
```

## Auswertung

### Leak-Rate berechnen

```
Leak-Rate (mbar/h) = (P_start - P_end) / Zeit_h - Temperatur-Korrektur

Temperatur-Korrektur: Delta_P_temp = P * (T_end - T_start) / T_start
Bereinigte Leak-Rate = (P_start - P_end - Delta_P_temp) / Zeit_h
```

### Bewertung

| Leak-Rate | Bewertung | Flug-tauglich? |
|-----------|-----------|----------------|
| < 0.5 mbar/h | Sehr gut | Ja |
| 0.5-2 mbar/h | OK | Ja (mit Reserve) |
| 2-5 mbar/h | Mangelhaft | Eingeschraenkt |
| > 5 mbar/h | Schlecht | Nein |

### Python Auswertung-Script

Ein Script unter `tools/balloon_pressure_test/plot_pressure.py`:
- Liest CSV-Datei von Serial-Log
- Plotet Druck vs. Zeit
- Plotet Temperatur vs. Zeit
- Berechnet temperaturbereinigte Leak-Rate
- Zeigt Trendlinie

## Ballon-Kandidaten

| Ballon | Groesse | Preis | Bezugsquelle | Bemerkung |
|--------|---------|-------|-------------|-----------|
| Qualatex 36" | 91cm Durchmesser | ~3 EUR | Amazon | Standard in Pico-Balloon Community |
| Aeon 36" | 91cm | ~2 EUR | AliExpress | Guenstiger, weniger erprobt |
| Amazon Billig 36" | 91cm | ~1 EUR | Amazon | Unbekannte Qualitaet |
| Qualatex 30" | 76cm | ~2.5 EUR | Amazon | Kleiner, weniger Auftrieb |
| Anagram 36" | 91cm | ~2 EUR | Amazon | Alternative |

Auftrieb bei 36" Ballon (~1.5L Helium):
- Helium: ~0.1785 g/L
- Luft: ~1.225 g/L
- Auftriebskraft pro Liter: ~1.05 g/L
- Gesamt-Auftrieb 36": ~50-60 g
- Payload-Budget bei 36": ~15-20 g (nach Abzug Ballongewicht ~40-50g)
