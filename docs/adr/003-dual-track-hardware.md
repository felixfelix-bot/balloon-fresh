# ADR 003: Dual-Track Hardware-Design (Dev + Flight)

## Status
Akzeptiert

## Kontext
Wir brauchen eine Plattform zum Entwickeln und Testen der Firmware UND ein minimales Flug-Board unter 15g. Die Anforderungen an Prototyping (einfaches Flashen, Debug, USB) und Flug (minimalgewicht, keine Stecker) widersprechen sich.

## Entscheidung
Zwei separate Hardware-Varianten:

### Track A: Entwickler-Board (XIAO Carrier)
- XIAO ESP32C3 als steckbares MCU-Modul
- 78x39mm Solarzellen (einfacher zu handhaben)
- Vollstaendige Debug-Ausstattung (USB, UART-Header, LEDs)
- LoRa-Modul-Slot (LR2021 oder LR1121)
- Supercap-Bank mit groesserer Kapazitaet
- Kein Gewichts-Limit
- Zweck: Firmware-Entwicklung, Funk-Tests am Boden

### Track B: Flug-Board (Bare-Chip, 3D-Struktur)
- ESP-C3-12F Bare Module direkt auf PCB
- 52x19mm Solarzellen auf Wing-Boards
- Keine Stecker/Header (Programmierung ueber Pads)
- Hub-Board + 4 Wing-Boards als 3D-Struktur
- Zielgewicht: <15g (Komfort-Modus)
- Zweck: Tatsaechlicher Flug

## Begruendung

1. **XIAO bereits vorhanden**: Perfekt fuer schnelles Prototyping
2. **Gleiche Pin-Belegung**: Beide Boards nutzen identische GPIO-Zuordnung
3. **Gleiche Firmware**: ESP-IDF Code laeuft auf beiden Varianten
4. **Risikominimierung**: Fehler auf dem Dev-Board kosten keine Flug-Hardware
5. **78x39mm Zellen vorhanden**: Leichter zu handhaben fuer erste Tests

## Konsequenzen
- Pin-Belegung muss auf beiden Boards identisch sein (fuer gleiche Firmware)
- Dev-Board dient als Referenz fuer elektrische Tests vor dem Flug-Board-Loeten
- Flug-Board wird erst gebaut wenn Firmware auf Dev-Board validiert ist
