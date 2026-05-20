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

### SP4T Switch Stromverbrauch

| Modus | Strom |
|-------|-------|
| Any state | < 1 uA |

## Energie pro Sendezyklus (30s Intervall)

### Szenario A: LoRa SF10 @ 2.4 GHz (Normalbetrieb)

```
Phase                    Dauer    Strom      Energie (mAs)
─────────────────────────────────────────────────────────
Deep Sleep               29.5s    ~15 uA     0.44
Wake + ADC Read          5 ms     20 mA      0.10
BMP280 Read              10 ms    1 mA       0.01
LR2021 Wake + Config     20 ms    5 mA       0.10
Leuchtturm TX (4 Wings):
  - SP4T Switch          -        < 1 uA     ~0
  - FEM TX Enable        4x400ms  90 mA      144.0
  - LR2021 TX            4x400ms  31 mA      49.6
  - Telemetry Encode     4x1ms    20 mA      0.08
RX Window                1000ms   5.7+5 mA   10.7
─────────────────────────────────────────────────────────
TOTAL pro Zyklus (30s):                      ~205 mAs
```

### Szenario B: FLRC Schnellmodus (naehe Distanz)

```
Phase                    Dauer    Strom      Energie (mAs)
─────────────────────────────────────────────────────────
Deep Sleep               29.5s    ~15 uA     0.44
Wake + Sensors           35 ms    20 mA      0.70
Leuchtturm TX (4 Wings):
  - LR2021 TX FLRC       4x0.2ms  31 mA      0.025
  - FEM TX               4x0.2ms  90 mA      0.072
─────────────────────────────────────────────────────────
TOTAL pro Zyklus (30s):                      ~1.24 mAs
```

### Szenario C: Sub-GHz LoRa SF12 (Maximale Reichweite)

```
Phase                    Dauer    Strom      Energie (mAs)
─────────────────────────────────────────────────────────
Deep Sleep               28s      ~15 uA     0.42
Wake + Sensors           35 ms    20 mA      0.70
LR2021 TX SF12           2000ms   120 mA     240.0
(kein FEM, LR2021 direkt +22 dBm)
─────────────────────────────────────────────────────────
TOTAL pro Zyklus (30s):                      ~241 mAs
```

## Supercapacitor Kapazitaet

### Konfiguration
- 2x AVX SCC 3.3F 2.7V in Serie
- Effektive Kapazitaet: **1.65F @ 5.4V**
- Maximale Energie: E = 0.5 * C * V^2 = 0.5 * 1.65 * 5.4^2 = **24.1 Joule**
- Nutzbare Energie (5.4V → 3.0V Min): E = 0.5 * 1.65 * (5.4^2 - 3.0^2) = **16.7 Joule**

### Spannungsabfall pro Sendezyklus

| Szenario | Energie (mAs) | Delta V = I*t/C | Spannungsabfall |
|----------|--------------|-----------------|-----------------|
| LoRa SF10 (2.4 GHz, 4 Wings) | 205 mAs | 0.205/1.65 = 0.124V | **-0.12V** |
| FLRC Schnell | 1.24 mAs | 0.00124/1.65 = 0.00075V | **-0.001V** |
| Sub-GHz SF12 | 241 mAs | 0.241/1.65 = 0.146V | **-0.15V** |

> Alle Szenarien sind problemlos: Supercaps verlieren weniger als 0.15V pro Zyklus.

## Solar-Aufladung

### Solar-Array Leistung

```
4 Wings, je 3 Zellen in Serie = 12 Zellen gesamt
4 Wings in Serie geschaltet:
  = 6.0V, 400mA = 2.4W Peak (direktes Sonnenlicht)
```

### Ladezeit zwischen Sendezyklen

```
Verfuegbare Solar-Power: 2.4W peak (worst case: ~0.5W bei bewoelkt)
Supercap Lade-Strom ueber BAT54: ~400mA peak (wenn Sonne scheint)

Nach LoRa SF10 Zyklus (205 mAs verbraucht):
  Nachlade-Zeit = 205 mAs / 400 mA = 0.51 Sekunden!
  
Nach Sub-GHz SF12 Zyklus (241 mAs):
  Nachlade-Zeit = 241 mAs / 400 mA = 0.60 Sekunden!

→ Selbst im schlimmsten Fall laden die Supercaps in < 1 Sekunde nach.
→ Mit 30s Sende-Intervall ist genug Reserve fuer Wolken/Dunkelheit.
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
