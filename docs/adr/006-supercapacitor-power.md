# ADR 006: Supercapacitor-Stromversorgung (Solar + Supercaps)

## Status
Akzeptiert

## Kontext
Der Ballon hat keinen Zugriff zu Batterien die bei -60C in der Stratosphaere funktionieren. Die Energie muss ueber Solarzellen gewonnen und in Supercapacitors gepuffert werden.

## Entscheidung
**Solarzellen → Schottky-Diode → Supercapacitor-Bank → LDO → Elektronik**

### Power-Architektur

```
4 Wings, je 3 Solarzellen in Serie:
  Wing 1: [0.5V]─[0.5V]─[0.5V] = 1.5V, 400mA
  Wing 2: [0.5V]─[0.5V]─[0.5V] = 1.5V, 400mA
  Wing 3: [0.5V]─[0.5V]─[0.5V] = 1.5V, 400mA
  Wing 4: [0.5V]─[0.5V]─[0.5V] = 1.5V, 400mA

Alle 4 Wings in SERIES geschaltet:
= 6.0V, 400mA (2.4W peak in direktem Sonnenlicht!)

      │
[BAT54 Schottky Diode] ← Ruckstrom-Schutz
      │
[2x AVX SCC 3.3F 2.7V in Serie] = 1.65F @ 5.4V
[+ 2x 10kOhm Balancing-Widerstaende]
      │
[TPS7A02 3.3V LDO] ← IQ: 25 nA (!)
      │
[ESP32-C3 + LR2021 + SKY66112 + BMP280]
```

## Komponenten

### Solarzellen
- **Flug**: 12x 52x19mm (0.5V, 400mA) - bereits vorhanden (100er Pack)
- **Prototyp**: 78x39mm (0.54W, 0.5V) - bereits vorhanden (50er Pack)
- 3 Zellen pro Wing in Serie = 1.5V pro Wing
- 4 Wings in Serie = 6.0V Gesamt

### Supercapacitors
- **AVX SCC Serie**: 2x 3.3F, 2.7V in Serie
- Effektiv: 1.65F @ 5.4V
- Gewicht: 2x 1.5g = 3.0g
- Balancing: 2x 10kOhm Parallel-Widerstaende (verhindern Ueberladung eines Caps)

### LDO Regler
- **TPS7A02 3.3V**: Ultra-Low IQ (25 nA!)
- Effizienz bei Deep Sleep: Quasi kein Eigenverbrauch
- Ausgang: 3.3V @ bis 300mA (reicht fuer TX-Bursts)

### Schottky Diode
- **BAT54**: Verhindert Entladung der Supercaps zurueck in Solarzellen bei Nacht/Bewoelkung
- Forward Voltage: ~0.3V @ 100mA
- Gewicht: vernachlaessigbar

## Warum Supercaps statt Batterie

| Aspekt | Supercap | LiPo Batterie |
|--------|----------|---------------|
| Temperaturbereich | **-40C bis +70C** | -20C bis +60C (schlecht bei -60C!) |
| Ladezyklen | **>500.000** | ~300-500 |
| Gewicht | 3.0g (2x 3.3F) | ~3g (100mAh) |
| Selbstentladung | Hoch (kritisches Design) | Niedrig |
| Lebensdauer | **Jahrzehnte** | 2-3 Jahre |
| Schnellladung | **Sekunden** | Stunden |

## 3D-Solar-Vorteil
Durch die 4 Wings in 4 verschiedenen Raumwinkeln:
- Fast immer mindestens 1-2 Wings in direktem Sonnenlicht
- Auch bei tiefem Sonnenstand (Morgen/Abend/Polargebiete)
- Selbst bei Rotation des Ballons werden verschiedene Wings beschienen
- Peak Power: 2.4W (mehr als 10x des Durchschnittsbedarfs)

## Spannungsueberwachung
- ADC an GPIO0 misst Supercap-Spannung ueber Spannungsteiler (2x 1MOhm)
- Firmware bricht TX ab wenn Spannung unter 3.0V faellt (Brownout-Schutz)
- Spannung wird im Telemetrie-Paket mitgesendet
