# Link-Budget Analyse

## System-Konfiguration

- **Transceiver**: Semtech LR2021 (Gen 4)
- **FEM**: Skyworks SKY66112-11 (+22 dBm TX, +14 dB LNA RX)
- **Antenne Ballon**: PCB-Yagi ~6 dBi gain (pro Wing)
- **Antenne Boden**: 2.4 GHz Yagi ~16 dBi gain (oder Parabol)
- **Frequenz**: 2400 MHz (2.4 GHz ISM)
- **Flughoehe**: 18 km (60.000 ft)
- **Max. Distanz**: 300 km Slant Range

## Link-Budget Berechnung

### 2.4 GHz LoRa (SF12, BW 203 kHz)

```
TX Seite (Ballon):
  LR2021 TX Power:           +12.0 dBm
  SKY66112 PA Gain:          +10.0 dBm (Boost auf +22 dBm)
  PCB Yagi Gain:             + 6.0 dBi
  SP4T Switch Loss:          - 0.8 dB
  Feedline/Connector Loss:   - 0.5 dB
  ──────────────────────────────────
  EIRP (Ballon):             +36.7 dBm  (= ~4.7 Watt EIRP)
```

```
Pfadverlust (Free Space Path Loss):
  FSPL @ 100 km, 2.4 GHz:   -140.5 dB
  FSPL @ 300 km, 2.4 GHz:   -150.0 dB
```

```
RX Seite (Bodenstation):
  Ground Yagi Gain:          +16.0 dBi
  Coax/Connector Loss:       - 1.0 dB
  SKY66112 LNA Gain:         +14.0 dB (wenn am Ballon)
  (Bodenstation hat eigenen LNA)
  ──────────────────────────────────
  RX System Gain:            +15.0 dB
```

### Link-Margin bei verschiedenen Distanzen

| Distanz | FSPL | EIRP | RX Gain | Received Power | RX Sensitivity | Link Margin |
|---------|------|------|---------|---------------|---------------|-------------|
| 30 km | -130.0 dB | +36.7 dBm | +15.0 dB | **-78.3 dBm** | -141.5 dBm | **+63.2 dB** |
| 50 km | -134.4 dB | +36.7 dBm | +15.0 dB | **-82.7 dBm** | -141.5 dBm | **+58.8 dB** |
| 100 km | -140.5 dB | +36.7 dBm | +15.0 dB | **-88.8 dBm** | -141.5 dBm | **+52.7 dB** |
| 200 km | -146.5 dB | +36.7 dBm | +15.0 dB | **-94.8 dBm** | -141.5 dBm | **+46.7 dB** |
| 300 km | -150.0 dB | +36.7 dBm | +15.0 dB | **-98.3 dBm** | -141.5 dBm | **+43.2 dB** |

> **Ergebnis**: Selbst bei 300 km Slant Range bleibt ein Link-Margin von +43 dB. Die Verbindung ist hochzuverlaessig.

### Link-Margin bei Sub-GHz (868/915 MHz, SF12)

```
TX Seite:
  LR2021 TX Power:           +22.0 dBm (kein FEM noetig)
  Wire Antenna Gain:          + 2.0 dBi
  ──────────────────────────────────
  EIRP:                      +24.0 dBm
```

| Distanz | FSPL (868 MHz) | EIRP | RX Gain (+10 dBi Yagi) | Received | Sensitivity | Margin |
|---------|----------------|------|------------------------|----------|-------------|--------|
| 100 km | -131.2 dB | +24.0 dBm | +10.0 dB | **-97.2 dBm** | -141.5 dBm | **+44.3 dB** |
| 300 km | -140.8 dB | +24.0 dBm | +10.0 dB | **-106.8 dBm** | -141.5 dBm | **+34.7 dB** |
| 480 km | -144.8 dB | +24.0 dBm | +10.0 dB | **-110.8 dBm** | -141.5 dBm | **+30.7 dB** |

> **Ergebnis**: Sub-GHz erreicht bis zu 480 km (Horizont-Limit bei 18 km Hoehe).

## FLRC Modus (Kurze Distanz)

```
FLRC @ 1.3 Mbps, 2.4 GHz:
  TX Power (kein FEM):        +12.0 dBm
  PCB Yagi Gain:              + 6.0 dBi
  EIRP:                       +18.0 dBm
  RX Sensitivity (FLRC):      ~ -105 dBm
  
  Max. Reichweite (10 dB Margin):
  FSPL max = EIRP + RX_Gain - Sensitivity - Margin
           = 18 + 16 - (-105) - 10 = 129 dB
  → Distanz ~ 25-30 km (perfekt fuer direkten Ueberflug)
```

## Horizont-Limit

Bei 18 km (60.000 ft) Flughoehe:

```
Radio Horizont = sqrt(2 * R_earth * h) = sqrt(2 * 6371 * 18) = ~479 km

Ueber 480 km faellt der Ballon hinter die Erdkruemmung.
Unabhaengig von Sendeleistung: KEINE Verbindung moeglich!
```

## Real-Welt Abschaetzung

Die obigen Berechnungen sind Free-Space (ideal). In der Praxis:

| Faktor | Verlust | Grund |
|--------|---------|-------|
| Atmosphaerische Daempfung | -0.5 dB | Sauerstoff/Wasserdampf bei 2.4 GHz |
| Polarizationsverlust | -3 to -20 dB | Ballon dreht sich (linear polarisierte Yagi) |
| Antennen-Fehlausrichtung | -3 to -6 dB | Ballon pendelt |
| Yagi Fertigungstoleranz | -1 to -3 dB | PCB-Yagi nicht perfekt |
| **Gesamt Real-Welt-Zuschlag** | **-8 to -30 dB** | |

Konservative Abschaetzung (mit -20 dB Polarisation):

| Distanz | Ideal Margin | Real Margin | Bewertung |
|---------|-------------|-------------|-----------|
| 30 km | +63 dB | **+43 dB** | Ausgezeichnet |
| 100 km | +53 dB | **+33 dB** | Sehr gut |
| 300 km | +43 dB | **+23 dB** | Gut (200x ueber Minimum) |
| 480 km | - | **+11 dB** | Marginal (Sub-GHz) |
