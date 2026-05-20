# ADR 004: 3D Yagi-Antennen-Struktur (4 Wings + Hub)

## Status
Akzeptiert

## Kontext
Der Ballon muss in mehrere Raumrichtungen funken koennen, da er sich dreht, pendelt und die Bodenstation an verschiedenen Positionen stehen kann. Eine einzelne omnidirektionale Antenne hat keinen Gewinn. Eine Patch-Antenne wurde evaluiert aber verworfen.

## Entscheidung
**4 identische Wing-Boards** mit je einer PCB-Yagi-Antenne, die orthogonal in verschiedene Raumrichtungen zeigen. Verbunden durch ein zentrales Hub-Board ueber Loetstellen. SP4T RF-Switch fuer "Leuchtturm-Modus" (Round-Robin TX).

## Alternativen

| Option | Gewinn | Gewicht | Polarisation | Komplexitaet |
|--------|--------|---------|-------------|-------------|
| **4x Yagi 3D** | ~6-9 dBi pro Antenne | ~3.2g (PCBs) | Linear | Mittel (SP4T) |
| Circular Patch | ~6-9 dBi | 0g (geaetzt) | Zirkular | Niedrig |
| Cloverleaf | ~2 dBi | ~1.5g | Zirkular | Niedrig |
| Dipol/Monopol | ~2 dBi | ~0.5g | Linear | Sehr niedrig |
| 4x Yagi flach | ~6-9 dBi | ~3g | Linear | Mittel |

## Begruendung fuer 4x Yagi 3D

1. **Maximaler Gewinn**: ~6-9 dBi pro Yagi vs ~2 dBi bei omnidirektionalen Antennen
2. **3D-Abdeckung**: Durch orthogonale Anordnung zeigen die Yagis in verschiedene Raumebenen, nicht nur in eine flache Ebene
3. **Dual-Purpose PCBs**: Wing-Boards tragen gleichzeitig Solarzellen
4. **3D-Solarernte**: 4 Wings in 4 Winkeln = fast immer mindestens 1-2 Wings in direktem Sonnenlicht
5. **Identische Boards**: 4x das gleiche Wing-Board = einfachere Fertigung
6. **Mechanische Stabilitaet**: Kreuzfoermige 3D-Struktur ist selbsttragend
7. **Experimentell**: Leuchtturm-Modus mit SP4T ist ein spannendes RF-Experiment

## Warum nicht Patch-Antenne
Obwohl eine zirkular polarisierte Patch-Antenne einfacher waere (kein Switch, immun gegen Drehung), wurde sich der Benutzer bewusst fuer das 4x Yagi 3D-Design entschieden wegen:
- Hoeherer moeglicher Gewinn bei jeder einzelnen Richtung
- Das 3D-Antennen-Array als Lern- und Experimentierplattform
- Die Kombination aus Antennen und Solar auf denselben Boards

## Leuchtturm-Modus (Round-Robin)
```
Sendezyklus:
1. SP4T → Wing 1 (Nord) → TX Paket (enthilt Antennen-ID)
2. SP4T → Wing 2 (Sued) → TX Paket
3. SP4T → Wing 3 (Ost)  → TX Paket
4. SP4T → Wing 4 (West) → TX Paket
Bodenstation waehlt staerkstes Signal
```

## 3D-Assembly
- 4 Wing-Boards stecken durch Slots im zentralen Hub-Board
- Verbindungen werden verloetet (mechanisch + elektrisch)
- RF, Power und Ground laufen ueber die Loetverbindungen
- Hub-Board sitzt oben (nahe am Ballon), Wings breiten sich nach unten/ausen aus
