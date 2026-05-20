# ADR 008: Telemetrie-Paketformat

## Status
Akzeptiert

## Kontext
Der Ballon sendet periodisch Telemetrie-Daten zur Bodenstation. Das Paketformat muss kompakt sein (minimale Airtime = minimaler Stromverbrauch) aber alle kritischen Daten enthalten.

## Entscheidung
**24 Byte binieres Telemetrie-Paket** mit CRC-16 Pruefsumme.

## Paketformat

```
Offset  Laenge  Feld              Typ       Beschreibung
------  ------  ----              ---       -----------
0       1       HEADER            uint8     Paket-Typ + Version
                                          Bits [7:5] = Version (0x01)
                                          Bits [4:0] = Typ (0x01=Telemetrie)
1-4     4       LATITUDE          int32     Breitengrad (1e-7 Grad)
5-8     4       LONGITUDE         int32     Laengengrad (1e-7 Grad)
9-10    2       ALTITUDE          uint16    Hoehe in Metern (0-65535m)
11      1       TEMPERATURE       int8      Temperatur in °C (-128..+127)
12-13   2       PRESSURE          uint16    Luftdruck in hPa * 10
14      1       VCAP_VOLTAGE      uint8     Supercap-Spannung (V * 20)
                                          3.0V = 60, 5.0V = 100, 5.4V = 108
15      1       TX_COUNTER        uint8     Zaehler (Rollover bei 255)
16      1       ANTENNA_ID        uint8     Aktive Antenne (0-3) im Leuchtturm
17      1       STATUS_FLAGS      uint8     Bitfield (siehe unten)
18-19   2       CRC16             uint16    CRC-16/CCITT Pruefsumme
20-23   4       GNSS_HASH         uint32    GNSS-Snapshot Hash (optional)
------  ------
Total:  24 Bytes
```

## Status-Flags (Byte 17)

```
Bit 7: GPS_VALID       (1 = Gueltige GPS-Position im Paket)
Bit 6: GPS_ASSISTED    (1 = Position wurde serverseitig berechnet)
Bit 5: SOLAR_ACTIVE    (1 = Solarzellen liefern Strom)
Bit 4: TX_MODE_24GHZ   (1 = 2.4 GHz, 0 = Sub-GHz)
Bit 3: TX_MODE_FLRC    (1 = FLRC Modulation aktiv)
Bit 2: TX_MODE_LORAWAN (1 = LoRaWAN, 0 = P2P LoRa)
Bit 1: LOW_POWER       (1 = Supercap < 3.5V, sparsamer Modus)
Bit 0: DEBUG_FLAG      (1 = Debug-Modus aktiv)
```

## Paket-Typen (Header Byte)

```
0x01 = Standard Telemetrie (24 Bytes)
0x02 = GNSS Snapshot Raw (variabel, ~200 Bytes)
0x03 = Command ACK (8 Bytes, Bodenstations-Bestaetigung)
0x04 = Debug Log (variabel, nur im Entwickler-Modus)
0x05 = Mode Change (4 Bytes, Bodenstations-Kommando)
```

## Airtime-Berechnung

| Modus | Bytes | Spreading Factor | Bandwidth | Airtime | Stromkosten |
|-------|-------|-----------------|-----------|---------|------------|
| FLRC | 24 | - | 1.3 Mbps | **~0.2 ms** | 0.006 mAs |
| LoRa SF7 | 24 | 7 | 500 kHz | **~15 ms** | 0.47 mAs |
| LoRa SF10 | 24 | 10 | 125 kHz | **~400 ms** | 12.4 mAs |
| LoRa SF12 | 24 | 12 | 125 kHz | **~2 s** | 62 mAs |

## Begruendung

1. **24 Bytes**: Kompakt aber informativ genug fuer Bodenstation-Tracking
2. **CRC-16**: Zuverlaessige Fehlerkennung bei schwachen Signalen
3. **Antenna_ID**: Bodenstation weiss welche Yagi das Signal geliefert hat
4. **GNSS_HASH**: Optionaler Hash des GNSS-Snapshots fuer Positionierungs-Server
5. **VCAP_VOLTAGE**: Kritisch fuer Missions-Status (lebt der Ballon noch?)
6. **Biniaer**: Kein ASCII/JSON-Overhead, jedes Byte zaehlt bei der Airtime
