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
