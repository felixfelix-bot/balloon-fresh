# ADR 008: Telemetrie-Paketformat

## Status
Akzeptiert (v2 - aktualisiert fuer 28-Byte Format mit Sequenznummer)

## Kontext
Der Ballon sendet periodisch Telemetrie-Daten zur Bodenstation. Das Paketformat muss kompakt sein (minimale Airtime = minimaler Stromverbrauch) aber alle kritischen Daten enthalten.

## Entscheidung
**28 Byte binaeres Telemetrie-Paket** mit CRC-16/CCITT Pruefsumme.

## Paketformat (v2)

```
Offset  Laenge  Feld              Typ       Beschreibung
------  ------  ----              ---       -----------
0-3     4       CALLSIGN_HASH     uint32    Identifizierung (FNV-1a Hash)
4-5     2       SEQ               uint16    Sequenznummer (Rollover bei 65535)
6-9     4       LATITUDE          uint32    Breitengrad (deg * 1e5, unsigned)
10-13   4       LONGITUDE         int32     Laengengrad (deg * 1e5, signed)
14-15   2       ALTITUDE          uint16    Hoehe in Metern (0-65535m)
16-17   2       VOLTAGE_MV        uint16    Supercap-Spannung in mV
18-19   2       TEMPERATURE_CDEG  int16     Temperatur in °C * 100 (-40.25 = -4025)
20-21   2       PRESSURE_HPA      uint16    Luftdruck in hPa * 10
22      1       SATS              uint8     Anzahl GPS-Satelliten
23      1       TX_MODE           uint8     Sende-Modus (SF, Band, etc.)
24      1       ANTENNA           uint8     Aktive Antenne (0-3)
25      1       FLAGS             uint8     Status-Flags (siehe unten)
26-27   2       CRC16             uint16    CRC-16/CCITT (Little-Endian)
------  ------
Total:  28 Bytes
```

## Status-Flags (Byte 25)

```
Bit 7: GPS_VALID       (1 = Gueltige GPS-Position im Paket)
Bit 6: GPS_ASSISTED    (1 = Position wurde serverseitig berechnet)
Bit 5: SOLAR_ACTIVE    (1 = Solarzellen liefern Strom)
Bit 4: TX_24GHZ        (1 = 2.4 GHz, 0 = Sub-GHz)
Bit 3: TX_FLRC         (1 = FLRC Modulation aktiv)
Bit 1: LOW_POWER       (1 = Supercap < 3.3V, sparsamer Modus)
```

## Aenderungen zu v1 (24 Byte)

1. **CALLSIGN_HASH** ersetzt HEADER byte — groessere Identifizierung
2. **SEQ** erweitert von uint8 (255) auf uint16 (65535) — laengerer Flug ohne Rollover
3. **VOLTAGE_MV** ersetzt VCAP_VOLTAGE (V*20) — hoehere Aufloesung (1 mV vs 50 mV)
4. **TEMPERATURE_CDEG** erweitert von int8 auf int16*100 — hoehere Praezision
5. **SATS** hinzugefuegt — GPS-Qualitaetsindikator
6. **GNSS_HASH** entfernt — nicht benoetigt fuer erste Fluege
7. CRC-16 in Little-Endian (matcht packed struct auf ESP32-C3)

## Airtime-Berechnung

| Modus | Bytes | Spreading Factor | Bandwidth | Airtime | Stromkosten |
|-------|-------|-----------------|-----------|---------|------------|
| FLRC | 28 | - | 1.3 Mbps | **~0.2 ms** | 0.006 mAs |
| LoRa SF7 | 28 | 7 | 500 kHz | **~17 ms** | 0.53 mAs |
| LoRa SF10 | 28 | 10 | 125 kHz | **~430 ms** | 13.3 mAs |
| LoRa SF12 | 28 | 12 | 125 kHz | **~2.1 s** | 65 mAs |

## Begruendung

1. **28 Bytes**: Kompakt aber informativ genug fuer Bodenstation-Tracking
2. **CRC-16/CCITT**: Zuverlaessige Fehlerkennung bei schwachen Signalen
3. **CALLSIGN_HASH**: Eindeutige Ballon-Identifikation ohne Klartext
4. **SEQ**: Duplikaterkennung und Paketverlust-Tracking ueber mehrtagige Fluege
5. **VOLTAGE_MV**: Kritisch fuer Missions-Status (lebt der Ballon noch?)
6. **SATS**: GPS-Fix-Qualitaet ohne zusaetzliche Pakete
7. **Binaer**: Kein ASCII/JSON-Overhead, jedes Byte zaehlt bei der Airtime
