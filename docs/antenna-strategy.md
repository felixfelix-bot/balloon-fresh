# Antennen-Strategie: Yagi vs. Patch + Circular Polarization

## PCB Yagi vs. Patch Antenna

### PCB Yagi (Linear Polarisiert)

```
Reflector → Driven → Director → Director → Director
   31mm     29mm     27mm       25mm       23mm
   |---15mm---|---15mm---|---15mm---|---15mm---|
   Gesamt: ~65mm auf FR4 @ 2.4 GHz
   Gewinn: ~6-9 dBi
   Polarisation: LINEAR
   Oeffnungswinkel: ~60-80°
```

Vorteile:
- Hoher Gewinn (6-9 dBi)
- Starke Richtwirkung (gute Peilung moeglich)
- Nutzt Laenge des Wing-Boards, Solarzellen daneben platzierbar
- Einfacher zu designen und abzustimmen
- Hoher Front-to-Back-Ratio (~15-20 dB)

Nachteile:
- Linear polarisiert: 20-30 dB Verlust bei 90° Rotation des Ballons
- Schmaler Oeffnungswinkel: braucht 4 Stk fuer 3D-Abdeckung

### Patch Antenne (Zirkular Polarisiert, CP)

```
   ┌─────────────┐
   │  ████████   │  ~29x29mm auf FR4 @ 2.4 GHz
   │  ██  ████   │  Ecken abgeschnitten fuer RHCP
   │  ████████   │
   └─────────────┘
   Gewinn: ~5-8 dBi
   Polarisation: ZIRKULAR (RHCP/LHCP)
   Oeffnungswinkel: ~80-120°
```

Vorteile:
- Zirkular polarisiert: immun gegen Ballon-Rotation
- Breiterer Oeffnungswinkel
- Kompakter (29x29mm)
- Kein 20+ dB Polarisationsverlust

Nachteile:
- Platzkonflikt mit Solarzellen auf Wing-Board
- Schwerer abzustimmen (Axial Ratio < 3dB braucht Praezision)
- Breiterer Strahl: weniger Richtwirkung beim Switching
- Nur bei 2.4 GHz machbar (868 MHz Patch = ~80x80mm)

### Polarisationsverlust: Der entscheidende Faktor

```
Ballon-Rotation  Linear Yagi → Linear Boden  Linear Yagi → CP Boden
────────────────  ──────────────────────────  ────────────────────────
0 Grad            0 dB                         3 dB
45 Grad           3 dB                         3 dB
90 Grad           20-30 dB (!!!)               3 dB
180 Grad          0 dB                         3 dB
Beliebig          0 bis 30 dB (unberechenbar)  IMMER 3 dB (konstant)
```

## Empfehlung: Hybrid-Strategie

### Ballon: Linear PCB Yagis

Begruendung:
1. Hoeherer Roh-Gewinn pro Antenne
2. Praezise Richtwirkung fuer Leuchtturm-Modus
3. Solarzellen-kompatibel (Yagi am Rand, Solar in der Mitte)
4. Einfacher zu designen als CP-Patch
5. Das Rotations-Problem wird am Boden geloest (siehe unten)

### Boden: Zirkular Polarisierte Antenne

Das ist der Trick: Circular Polarization am Boden, nicht am Ballon.

```
Ballon:  4x Linear-Yagis (drehen mit)
             ↕ immer exakt 3 dB Polarisationsverlust
Boden:   1x Helical oder Cross-Yagi (RHCP)
```

Fixer, vorhersagbarer 3 dB Verlust statt unvorhersagbarer 0-30 dB.

### Bodenstation-Antennen

| Antenne | Frequenz | Polarisation | Gewinn | Kosten | Aufwand |
|---------|----------|-------------|--------|--------|---------|
| 868 MHz Yagi | Sub-GHz | Linear | ~12 dBi | ~15 EUR | Mittel |
| 2.4 GHz Helical (3-5 Windungen) | 2.4 GHz | **RHCP** | ~12-15 dBi | ~15 EUR | Mittel |
| 2.4 GHz Cross-Yagi | 2.4 GHz | **RHCP** | ~12 dBi | ~20 EUR | Mittel |
| 2.4 GHz LHCP Patch-Array | 2.4 GHz | **LHCP** | ~10 dBi | ~25 EUR | Hoch |

## Komplette Antennen-Konfiguration

### Sub-GHz (868 MHz) - Primaer fuer Langstrecke

Ballon: Draht-Dipol (~16.4 cm)
- lambda/2 @ 868 MHz = 17.3 cm in Luft, ~16.4 cm auf Draht
- ~2 dBi Gewinn, omnidirektional
- +22 dBm direkt vom LR2021
- ~480 km Reichweite (Horizont-Limit bei 18 km Hoehe)
- Unabhaengig von Ballon-Rotation

Boden: 868 MHz Yagi (~12 dBi)
- Linear polarisiert (kein CP noetig, Ballon-Dipol ist omnidirektional)
- Einfacher Nachbau aus Messingdraht oder Alurohr

### 2.4 GHz - Sekundaer mit Richtantennen

Ballon: 4x PCB-Yagis + SP4T (Komfort) oder 1-2x Yagis (Mittel)
- ~6-9 dBi pro Yagi
- Leuchtturm-Modus: TX auf Ant1 → Ant2 → Ant3 → Ant4
- Bodenstation waehlt staerkstes Signal
- +12 dBm (ohne FEM) oder +22 dBm (mit FEM)

Boden: 2.4 GHz Helical Antenne (RHCP)
- 3-5 Windungen aus Kupferdraht auf PVC-Rohr
- ~12-15 dBi Gewinn
- Circular polarisiert → 3 dB fester Verlust, kein 20+ dB Ausfall
- Einfach und guenstig selbst zu bauen

## Gewichtsbudget Antennen-System

| Konfiguration | Gewicht |
|--------------|---------|
| Nur Sub-GHz Draht-Dipol | 0.3g |
| Sub-GHz + 2.4 GHz Draht-Dipol | 0.4g |
| Sub-GHz + 1x PCB-Yagi (Mittel) | ~0.9g (+ PCB) |
| Sub-GHz + 2x PCB-Yagi + SP2T | ~1.5g (+ PCBs) |
| Sub-GHz + 4x PCB-Yagi + SP4T (Komfort) | ~2.4g (+ PCBs) |

Hinweis: Die Wing-PCBs mit Yagis sind gleichzeitig Solarzellen-Traeger.
Das "zusaetzliche" Gewicht fuer Yagis betraegt effektiv nur den SP4T-Switch (+0.1g),
da die PCBs ohnehin fuer die Solarzellen benoetigt werden.

---

## Produktrecherche (Mai 2026)

### Ergebnis: Keine handelsueblichen 2.4 GHz CP Patch-Antennen fuer Pico-Balloons

Umfassende Suche auf AliExpress, DigiKey, Mouser, Taoglas, Linx/TE Connectivity und Johanson Technology.

| Produkt | Frequenz | Polarisation | Gewinn | Gewicht | Geeignet? |
|---------|----------|-------------|--------|---------|-----------|
| AliExpress FPC Streifen | 2.4 GHz | Linear (nicht CP) | ~1-2 dBi (trotz "5 dBi" Angabe) | ~0.2g | Nein — omnidirektional, keine Richtwirkung |
| Foxeer Lollipop 2.4G | 2.4 GHz | RHCP | 2.6 dBi | ~3g pro Stueck (x4 = 12g) | Nein — zu schwer fuer 4x Diversity |
| iFlight 2.4G CP Panel | 2.4 GHz | RHCP/LHCP | ~5-8 dBi | ~15-25g | Nein — zu schwer fuer Ballon |
| Custom CP PCB Patch | 2.4 GHz | RHCP | ~5-7 dBi | ~0.5g | Moeglich — braucht EM-Simulation + VNA |
| PCB Yagi (unser Design) | 2.4 GHz | Linear | ~6-9 dBi | ~0g (geaetzt) | Ja — bereits designt |

**Warum keine CP Patches existieren:**
- 2.4 GHz Markt dominiert von WiFi/BT (linear)
- CP Markt bei 5.8 GHz (FPV Drohnen) und GPS L1 (1.575 GHz)
- FPC flex Antennen bei 2.4 GHz sind alle linear
- Custom CP Patch moeglich (~29x29mm auf 0.4mm FR4) aber braucht EM-Simulation (openEMS/HFSS) und VNA-Abgleich

---

## V1 Entscheidung: Omnidirektionale Dipole (Mai 2026 Update)

**Siehe ADR-009 fuer vollstaendige Begrundung.**

### Ballon: Wire-Dipole fuer beide Baender

| Band | Antenne | Laenge | Gewinn | Rotation? |
|------|---------|--------|--------|-----------|
| 868 MHz | Draht-Dipol | ~16.4 cm | ~2 dBi | Immun (omnidirektional) |
| 2.4 GHz | Draht-Dipol | ~6 cm | ~2 dBi | Immun (omnidirektional) |

Kein SP4T Switch, keine Antennen-Umschaltung, keine Wing-Board Antennen-Design.

### Link-Budget Rechtfertigung

```
TX: +22 dBm (SKY66112 FEM) + 2 dBi Dipol = +24 dBm EIRP
FSPL @ 300 km, 2.4 GHz: -149.6 dB
RX: 18 dBi Boden-Yagi = -107.6 dBm empfangen
Empfaengerempfindlichkeit SF9/1625: -117 dBm
Margin: +9.4 dB → funktioniert!

22 kbps Luftrate, ~9 kbps netto nach Erasure Coding + TDMA Overhead
4x MultiWAN Bonding: ~36 kbps aggregiert
```

### Bodenstation: Dual-Band

| Band | Antenne | Polarisation | Gewinn | Kosten | Zweck |
|------|---------|-------------|--------|--------|-------|
| 868 MHz | Linear Yagi | Linear | ~12 dBi | ~EUR 15 | Sub-GHz Telemetrie + Fallback |
| 2.4 GHz | CP Helical (5-Windung) | RHCP | ~14 dBi | ~EUR 15 (DIY) | 2.4 GHz Hochrat, rotationsimmun |

Die CP Helical kompensiert die Ballon-Rotation mit festem 3 dB Polarisationsverlust.

### Warum nicht Yagis auf dem Ballon (fuer V1)?

1. **Link-Budget funktioniert ohne** — 22 kbps bei 300 km mit einfachen Dipolen
2. **Keine passenden CP Patches verfuegbar** — Produktrecherche zeigt keine Optionen
3. **Einfachere Hardware** — kein SP4T, keine Umschalt-Firmware
4. **Gewicht** — Spart ~1-2g (SP4T + Antennen-Montage)
5. **Rotation** — Dipole sind omnidirektional, kein Rotationsproblem

---

## V2 Upgrade-Pfad: Richtantennen wenn mehr Throughput noetig

Wenn V1-Throughput (22 kbps) nicht ausreicht, koennen Richtantennen nachgeruestet werden:

| Option | Gewinn | Gewicht | Aufwand |
|--------|--------|---------|---------|
| PCB Yagis auf Wing-Boards (ADR-004) | 6-9 dBi | +0g (geaetzt) + SP4T (+0.1g) | Mittel |
| Custom CP PCB Patches | 5-7 dBi | +0.5g | Hoch (EM-Sim + VNA) |
| Gekaufte FPC Sticker | ~1-2 dBi | +0.8g (4x0.2g) | Niedrig (aber kein Richtgewinn) |

V2 bringt ~2-3x mehr Throughput pro Link (38-87 kbps bei 300 km).

Das PCB ist bereits mit SP4T-Footprint und Wing-Board Connectors designt —
Hardware-Upgrade durch Bestueckung der optionalen Bauteile.
