# 3D Hardware-Design: Hub + Wing Boards

## Overview

Das Flug-Board besteht aus 5 PCBs die zu einer 3D-Struktur zusammengeloetet werden:

- **1x Hub-Board** (zentral): Alle aktiven Elektronik-Komponenten
- **4x Wing-Board** (identisch): PCB-Yagi Antennen + Solarzellen

## Hub-Board

### Abmessungen
- **Groesse**: 22mm x 22mm
- **Substrat**: 0.6mm FR4 (oder 0.4mm fuer Gewichtsoptimierung)
- **Lagen**: 2 (Top: Signal/Power, Bottom: GND Plane)
- **Gewicht**: ~0.3g

### Platzierung

```
Hub-Board Top-Ansicht (22x22mm):

┌──────────────────────────┐
│ Slot  Slot  Slot  Slot   │ ← 4 Slots fuer Wing-Boards
│  ┌──────┐  ┌──────────┐ │
│  │ESP32 │  │ LR2021   │ │
│  │ C3   │  │ Module   │ │
│  │ 12F  │  │          │ │
│  └──────┘  └──────────┘ │
│                           │
│ ┌────┐ ┌─────┐ ┌──────┐ │
│ │BMP │ │FEM  │ │ SP4T │ │
│ │280 │ │SKY  │ │Switch│ │
│ └────┘ └─────┘ └──────┘ │
│                           │
│ ┌─────────┐  ┌────────┐ │
│ │2x Super │  │TPS7A02 │ │
│ │Caps     │  │+BAT54  │ │
│ │3.3F Serie│ │+Passiv │ │
│ └─────────┘  └────────┘ │
└──────────────────────────┘
```

### Slots fuer Wing-Boards

Jeder Slot ist ein ~1mm breiter Schlitz in der Kante des Hub-Boards:
- 4 Slots, je 90° versetzt
- Wing-Board-Tab passt hinein und wird verloetet
- Verbindet: RF (vom SP4T), Power (Solar), GND

### Verbindungs-Pins pro Wing-Slot

| Pin | Funktion | ESP32 GPIO |
|-----|----------|-----------|
| RF | Antennen-Signal vom SP4T | (ueber FEM → SP4T) |
| V_SOLAR | Solar-Ausgang des Wings | → BAT54 → Supercaps |
| GND | Masse | GND Plane |

## Wing-Board

### Abmessungen
- **Groesse**: 65mm x 28mm
- **Substrat**: 0.6mm FR4
- **Lagen**: 2 (Top: Solar + Antenne, Bottom: GND)
- **Gewicht**: ~0.8g (nur PCB)

### Layout

```
Wing-Board (65x28mm, identisch x4):

┌────────────────────────────────────────────────────────────┐
│ PCB-YAGI ANTENNE (~60mm lang, geaetzt)                    │
│ ▐▌ ▐▌  ▐▌ ▐▌ ▐▌ ▐▌ ▐▌                                    │
│ Reflector  Driven    Directors → strahlt nach rechts       │
│   Element  Element  (5-7 Elemente)                         │
│                                                            │
│ ┌────────────┐ ┌────────────┐ ┌────────────┐             │
│ │ Solar Cell │ │ Solar Cell │ │ Solar Cell │             │
│ │  52x19mm   │ │  52x19mm   │ │  52x19mm   │             │
│ │  0.5V 400mA│ │  0.5V 400mA│ │  0.5V 400mA│             │
│ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘             │
│       │              │              │                     │
│       └────── Serie ─┘──── Serie ──┘                     │
│              = 1.5V, 400mA                                  │
│                                                            │
│ ╔════╗                                                     │
│ ║TAB ║ ← Steck-Tab (5mm breit, passt in Hub-Slot)        │
│ ╚════╝   Pin 1: RF_IN (Yagi Feed)                        │
│           Pin 2: V_SOLAR (+1.5V)                           │
│           Pin 3: GND                                       │
└────────────────────────────────────────────────────────────┘
```

### PCB-Yagi Antenne (2.4 GHz)

Die Yagi-Antenne wird direkt als Kupferstruktur auf die PCB geaetzt:

```
2.4 GHz PCB Yagi Design (auf FR4, er = 4.4):

Element-Abstaende und Laenge (lambda/2 @ 2.4 GHz ≈ 61mm in air, ~29mm auf FR4):

Reflector:  ~31mm lang, ~15mm vom Driven Element
Driven:     ~29mm lang (lambda/2 auf FR4)
Director 1: ~27mm lang, ~15mm nach dem Driven
Director 2: ~25mm lang, ~15mm nach Director 1
Director 3: ~24mm lang, ~15mm nach Director 2
Director 4: ~23mm lang, ~15mm nach Director 3

Gesamtlaenge: ~60-65mm (passt auf das Wing-Board)
Geschaetzter Gewinn: ~6-9 dBi
Impedanz: 50 Ohm (Coplanar Waveguide Feed)

Feed-Point:
Driven Element → 50 Ohm CPW → TAB-Pin (RF_IN) → Hub-Board → SP4T → FEM → LR2021
```

### Solarzellen-Anordnung

```
3x 52x19mm Zellen in Serie auf dem Wing:

[Zelle 1]─[Zelle 2]─[Zelle 3] = 1.5V, 400mA
    +0.5V      +0.5V     +0.5V

Die Zellen werden mit 30AWG Kupferdraht verbunden und
mit doppelseitigem Klebeband auf dem PCB befestigt.

Ferrite Bead am Uebergang Solarbereich → Antennenbereich:
Verhindert dass HF-Stoerungen von den Solar-Zuleitungen
die Antenne beeinflussen.
```

## 3D-Assembly

### Zusammenbau

```
Schritt 1: Hub-Board waagerecht halten
Schritt 2: Wing 1 durch N-Slot stecken (horizontal, Yagi zeigt nach Norden)
Schritt 3: Wing 2 durch O-Slot stecken (horizontal, Yagi zeigt nach Osten)
Schritt 4: Wing 3 durch S-Slot stecken (nach unten geneigt ~30°, Yagi zeigt nach SW)
Schritt 5: Wing 4 durch W-Slot stecken (nach unten geneigt ~30°, Yagi zeigt nach NW)
Schritt 6: Alle Tabs anloeten (RF, Solar, GND)

Ergebnis:
         N (Wing 1, horizontal)
         ↑
    W ←──┼──→ O (Wing 2, horizontal)
         │
         ↓
         S (Wing 3, ~30° nach unten geneigt)

+ Wing 4 diagonal, ~30° nach unten

= Abdeckung des gesamten unteren Halbraums
```

### Mechanische Stabilitaet

- Loetverbindungen an allen 4 Slots tragen mechanisch
- 4 Wings stuetzen sich gegenseitig
- Hub-Board oben → waechst in der Mitte des Ballons
- Aufhaengung: 30AWG Draht vom Hub-Board zum Ballon

## Dev-Board (Track A)

### XIAO Carrier Board

```
┌─────────────────────────────────────────────┐
│  XIAO ESP32C3 Carrier                       │
│  ~50mm x 70mm, 0.8mm FR4                    │
│                                              │
│  [XIAO Socket]  [LR2021/LR1121 Module Slot] │
│                                              │
│  [BMP280]  [SP4T Switch]  [FEM]             │
│                                              │
│  [2x Supercap 4.7F in Serie]                │
│                                              │
│  [78x39mm Solar Cells Area]                 │
│  5-6 cells in series, boost to 5V           │
│                                              │
│  [Debug Header: UART, GPIO]                  │
│  [LEDs: Power, TX, RX]                      │
│  [USB via XIAO onboard]                     │
└─────────────────────────────────────────────┘
```

### Unterschiede zum Flight-Board

| Aspekt | Dev-Board | Flight-Board |
|--------|-----------|-------------|
| MCU | XIAO ESP32C3 (steckbar) | ESP-C3-12F (gelötet) |
| Solar | 78x39mm Zellen | 52x19mm Zellen auf Wings |
| Supercaps | 2x 4.7F (groesser) | 2x 3.3F |
| Antennen | Test-Pads fuer VNA | PCB-Yagis auf Wings |
| Debug | USB + UART Header | Nur Pads |
| Gewicht | Kein Limit | <15g |
| PCB | 0.8mm FR4 | 0.6mm FR4 |
| Boost Converter | Ja (78x39mm Zellen) | Nein (direkt 6V Series) |
