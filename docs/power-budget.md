# Power-Budget Analyse

## System-Stromverbrauch

### ESP32-C3 Stromverbrauch

| Modus | CPU | Strom | Dauer pro Zyklus | Energie |
|-------|-----|-------|-----------------|---------|
| Deep Sleep | Off | 10-15 uA | 29.5s (von 30s) | 0.44 mAs |
| Modem Sleep | 80 MHz | 8-12 mA | - | - |
| Active (Light Sleep Wake) | 80 MHz | 15-20 mA | ~100 ms | 2.0 mAs |
| Active (SPI/I2C) | 80 MHz | 25-30 mA | ~50 ms | 1.5 mAs |

### LR2021 Stromverbrauch

| Modus | Frequenz | Strom | Dauer pro Zyklus | Energie |
|-------|----------|-------|-----------------|---------|
| Sleep | - | < 1 uA | 29.5s | 0.03 mAs |
| RX (Listen) | 2.4 GHz | 5.7 mA | ~1000 ms | 5.7 mAs |
| TX LoRa SF10 | 2.4 GHz | 31 mA (+12 dBm) | ~400 ms | 12.4 mAs |
| TX LoRa SF12 | Sub-GHz | 120 mA (+22 dBm) | ~2000 ms | 240 mAs |
| TX FLRC | 2.4 GHz | 31 mA (+12 dBm) | ~0.2 ms | 0.006 mAs |
| GNSS Snapshot | - | ~15 mA | ~100 ms | 1.5 mAs |

### SKY66112 FEM Stromverbrauch

| Modus | Strom | Dauer | Energie |
|-------|-------|-------|---------|
| TX (+22 dBm) | ~90 mA | ~400 ms (SF10) | 36 mAs |
| RX (LNA active) | ~5 mA | ~1000 ms | 5 mAs |
| Sleep | < 1 uA | 29.5s | 0.03 mAs |

### BMP280 Stromverbrauch

| Modus | Strom | Dauer | Energie |
|-------|-------|-------|---------|
| Sleep | 0.1 uA | 29.5s | 0.003 mAs |
| Forced Mode (1 measurement) | ~1 mA | ~10 ms | 0.01 mAs |

### u-blox MAX-M10S GPS Stromverbrauch

| Modus | Strom | Dauer | Energie |
|-------|-------|-------|---------|
| Power Off (sleep) | 0.5 uA | ~28s | 0.014 mAs |
| Acquisition (cold start) | ~25 mA | ~25s (once) | 625 mAs (einmalig) |
| Tracking (continuous) | ~8 mA | - | - |
| Power Save Mode (PSM) | ~2.5 mA avg | ~1s | 2.5 mAs |
| Hot Start | ~8 mA | ~1s | 8 mAs |

**GPS-Strategie:** Bei 120s TX-Intervall: GPS PSM aktiv → Hot Start ~1s vor TX →
Position lesen → GPS Sleep. Durchschnitt ~2.5 mAs pro Zyklus.

### SP4T Switch Stromverbrauch

| Modus | Strom |
|-------|-------|
| Any state | < 1 uA |

## Energie pro Sendezyklus (120s Intervall, GPS-enabled)

### Szenario A: LoRa SF7 @ Sub-GHz (Normalbetrieb, Minimal-Variante)

```
Phase                    Dauer    Strom      Energie (mAs)
─────────────────────────────────────────────────────────
Deep Sleep               119s     ~15 uA     1.79
GPS Hot Start + Fix      1000ms   8 mA       8.0
Wake + ADC Read          5 ms     20 mA      0.10
BMP280 Read              10 ms    1 mA       0.01
LR2021 Wake + Config     20 ms    5 mA       0.10
LR2021 TX SF7            17 ms    120 mA     2.04
─────────────────────────────────────────────────────────
TOTAL pro Zyklus (120s):                     ~12.0 mAs
```

### Szenario B: LoRa SF10 @ Sub-GHz (Max Range, GPS-enabled)

```
Phase                    Dauer    Strom      Energie (mAs)
─────────────────────────────────────────────────────────
Deep Sleep               119s     ~15 uA     1.79
GPS Hot Start + Fix      1000ms   8 mA       8.0
Wake + Sensors           35 ms    20 mA      0.70
LR2021 TX SF10           430 ms   120 mA     51.6
─────────────────────────────────────────────────────────
TOTAL pro Zyklus (120s):                     ~62.1 mAs
```

### Szenario C: LoRa SF12 @ Sub-GHz (Maximale Reichweite, GPS-enabled)

```
Phase                    Dauer    Strom      Energie (mAs)
─────────────────────────────────────────────────────────
Deep Sleep               119s     ~15 uA     1.79
GPS Hot Start + Fix      1000ms   8 mA       8.0
Wake + Sensors           35 ms    20 mA      0.70
LR2021 TX SF12           2100ms   120 mA     252.0
─────────────────────────────────────────────────────────
TOTAL pro Zyklus (120s):                     ~262.5 mAs
```

## Supercapacitor Kapazitaet

### Konfiguration
- 2x AVX SCC 3.3F 2.7V in Serie
- Effektive Kapazitaet: **1.65F @ 5.4V**
- Maximale Energie: E = 0.5 * C * V^2 = 0.5 * 1.65 * 5.4^2 = **24.1 Joule**
- Nutzbare Energie (5.4V → 3.0V Min): E = 0.5 * 1.65 * (5.4^2 - 3.0^2) = **16.7 Joule**

### Spannungsabfall pro Sendezyklus (120s, 1.65F Supercaps)

| Szenario | Energie (mAs) | Delta V = I*t/C | Spannungsabfall |
|----------|--------------|-----------------|-----------------|
| LoRa SF7 Sub-GHz + GPS | 12.0 mAs | 0.012/1.65 = 0.007V | **-0.01V** |
| LoRa SF10 Sub-GHz + GPS | 62.1 mAs | 0.062/1.65 = 0.038V | **-0.04V** |
| LoRa SF12 Sub-GHz + GPS | 262.5 mAs | 0.263/1.65 = 0.159V | **-0.16V** |

> Alle Szenarien sind problemlos: Supercaps verlieren weniger als 0.16V pro Zyklus.

## Solar-Aufladung

### Solar-Array Leistung

```
4 Wings, je 3 Zellen in Serie = 12 Zellen gesamt
4 Wings in Serie geschaltet:
  = 6.0V, 400mA = 2.4W Peak (direktes Sonnenlicht)
```

### Ladezeit zwischen Sendezyklen (120s Intervall)

```
Verfuegbare Solar-Power: ~320 mW avg (8 Zellen, bewoelkt ~80 mW)
Supercap Lade-Strom: ~100 mA avg

Nach LoRa SF7 Zyklus (12 mAs verbraucht):
  Nachlade-Zeit = 12 mAs / 100 mA = 0.12 Sekunden!

Nach LoRa SF12 Zyklus (263 mAs):
  Nachlade-Zeit = 263 mAs / 100 mA = 2.6 Sekunden!

→ Selbst bei bewoelkt (80 mW) laden die Supercaps zwischen den Zyklen voll auf.
```

### Dunkelheits-Reserve

```
Voll geladene Supercaps: 5.4V, 1.65F
Nutzbare Energie: 16.7 Joule

Stromverbrauch Deep Sleep: 15 uA
Deep Sleep Dauer bei voller Ladung:
  t = C * dV / I = 1.65 * (5.4 - 3.0) / 0.000015 = 264.000 Sekunden
  = ~73 Stunden Deep Sleep ohne ein bisschen Sonnenlicht!

In der Praxis: Selbst bei Nachtueberflug ueberleben die Supercaps
den dunklen Teil der Erdumrundung problemlos.
```

## Optimierungs-Empfehlungen

1. **Sende-Intervall**: 30s bei Tag, 60-120s bei Nacht (erkannt ueber Solar-Spannung)
2. **FLRC bevorzugen**: Wenn moeglich FLRC statt LoRa verwenden (200x weniger Energie)
3. **CPU-Takt**: 80 MHz statt 160 MHz (halbiert Active-Strom)
4. **WiFi/BLE**: Immer deaktiviert (spart ~30 mA im Idle)
5. **Sub-GHz nur wenn noetig**: SF12 verbraucht 10x mehr als SF10 bei 2.4 GHz

---

## Mesh Relay Power Budget (Mai 2026 Update)

### Mesh V1: Adaptive TX Relay (Night-Off Default)

TDMA Frame (2s Dauer, 50/50 RX/TX):

```
Slot    Funktion              Dauer    Strom      Energie (mAs)
──────────────────────────────────────────────────────────────
Slot 1  RX von GS-nah         500ms    11 mA      5.5
Slot 2  TX zu GS-fern         500ms    150 mA     75.0
Slot 3  RX von GS-fern        500ms    11 mA      5.5
Slot 4  TX zu GS-nah (low pwr) 500ms   30 mA      15.0
──────────────────────────────────────────────────────────────
Total pro Frame (2s):                             ~101 mAs
Durchschnittsleistung: 101 mAs / 2s x 3.3V = ~167 mW
```

Adaptive TX spart 38% vs fixed +22 dBm (265 mW).

### Mesh V1: Fixed +22 dBm Relay

```
Slot    Funktion              Dauer    Strom      Energie (mAs)
──────────────────────────────────────────────────────────────
Slot 1  RX von GS-nah         500ms    11 mA      5.5
Slot 2  TX zu GS-fern         500ms    150 mA     75.0
Slot 3  RX von GS-fern        500ms    11 mA      5.5
Slot 4  TX zu GS-nah          500ms    150 mA     75.0
──────────────────────────────────────────────────────────────
Total pro Frame (2s):                             ~161 mAs
Durchschnittsleistung: 161 mAs / 2s x 3.3V = ~265 mW
```

### Night-Off vs Night-Active

| Parameter | Night-Active | Night-Off |
|-----------|-------------|-----------|
| Supercaps | 2x 3.3F 2.7V Serie (1.65F) | 1x 0.47F 5.5V |
| Cap Gewicht | 3.0g | 0.5g |
| Solarzellen | 12x (6.0g) | 6-8x (3.0-4.0g) |
| Gesamtgewicht Mesh V1 | ~17g | ~14g |
| Nacht-Reserve | 73h Deep Sleep | ~8h (nur fuer TX-Bursts) |
| Nacht-Betrieb | Ja (relaying) | Nein (schlafen) |
| Position bei Nacht | GPS aktiv | Geschetzt aus Winddaten |

### Night-Off Ablauf

```
1. Solar-Spannung faellt unter Schwellwert (z.B. <2.5V)
2. Letzte TX: "SLEEPING" Announcement
3. Deep Sleep (15 µA) — kein RX, kein TX, kein GPS
4. Solar-Spannung steigt ueber Schwellwert (GPIO Wake)
5. GPS Lock (~30s)
6. TX: "AWAKE" Announcement mit neuer Position
7. Mesh TDMA Resume
```

Bodenstationen interpolieren Nacht-Position aus:
- Letzte bekannte Position + Hoehe
- Winddaten (z.B. von OpenMeteo API)
- Barometrische Hoehe vom letzten TX

### Solar-Auslegung: Mesh Relay

| Szenario | Avg Power | 8-Zellen Solar (320 mW avg) | 12-Zellen Solar (480 mW avg) |
|----------|-----------|----------------------------|------------------------------|
| Tracker | ~7 mW | 73h Reserve | 73h Reserve |
| Mesh adaptive TX | ~167 mW | 5.3h Reserve | 8.8h Reserve |
| Mesh fixed +22 dBm | ~265 mW | 3.2h Reserve | 5.4h Reserve |
| Mesh +30 dBm adaptive | ~350 mW | 2.3h Reserve | 3.2h Reserve → 16 Zellen noetig |

Night-Off Default (6-8 Zellen): Tageszeit-Margin komfortabel (240-320 mW Solar avg vs 167 mW Last).

### Mesh V2: +30 dBm Directional Relay

```
TDMA Frame (2s Dauer):
Slot 1  RX von GS-nah         500ms    11 mA      5.5
Slot 2  TX zu GS-fern (+30)   500ms    350 mA     175.0
Slot 3  RX von GS-fern        500ms    11 mA      5.5
Slot 4  TX zu GS-nah (+22)    500ms    150 mA     75.0
Total pro Frame (2s):                             ~261 mAs
Durchschnittsleistung: 261 mAs / 2s x 3.3V = ~431 mW
```

Benötigt 16-20 Solarzellen fuer night-active Betrieb (~640-800 mW avg).
