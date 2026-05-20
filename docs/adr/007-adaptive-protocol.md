# ADR 007: Adaptive Protokoll-Strategie (LoRa/FLRC/Sub-GHz)

## Status
Akzeptiert

## Kontext
Der Ballon muss in verschiedenen Entfernungen zur Bodenstation kommunizieren koennen. Von direkt ueber Kopf (1-5 km) bis weit am Horizont (100-300+ km). Verschiedene LoRa-Modulationen bieten unterschiedliche Kompromisse zwischen Reichweite, Airtime und Stromverbrauch.

## Entscheidung
Die Firmware waehlt automatisch die optimale Modulation und Band basierend auf den aktuellen Bedingungen:

## Modi

| Modus | Frequenz | Modulation | Reichweite | Airtime (24B) | TX-Strom | Einsatz |
|-------|----------|-----------|-----------|---------------|---------|---------|
| **FLRC Schnell** | 2.4 GHz | FLRC 1.3 Mbps | <30 km | ~1 ms | 31 mA | Direkt ueber Kopf |
| **LoRa Nah** | 2.4 GHz | LoRa SF7 | ~50 km | ~50 ms | 31 mA | Sichtlinie nah |
| **LoRa Mittel** | 2.4 GHz | LoRa SF10 | ~100 km | ~400 ms | 31 mA | Horizont naeher |
| **LoRa Fern** | Sub-GHz | LoRa SF12 | ~300+ km | ~2 s | 120 mA | Maximale Reichweite |
| **LoRaWAN** | Sub-GHz | SF7-SF12 (ADR) | Variabel | Variabel | 120 mA | TTN Gateway |

## Adaptive Moduswahl

```
Moduswahl-Logik (vereinfacht):

if (supercap_voltage < 3.5V) {
    // Niedrige Energie → sparsamer Modus
    mode = LORA_24GHZ_SF10;  // 2.4 GHz, mittlere Airtime, niedriger Strom
} else if (last_known_distance < 30km) {
    mode = FLRC_FAST;         // Blitzschnell, minimaler Strom
} else if (last_known_distance < 100km) {
    mode = LORA_24GHZ_SF10;   // Gute Balance
} else {
    mode = LORA_SUBGHZ_SF12;  // Maximale Reichweite, hoher Strom
}

// Fallback: Wenn keine Distanz bekannt → starte mit LoRa Mittel
// Bodestation kann Modus-Wechsel-Kommando senden
```

## Begruendung

1. **FLRC fuer naehe Distanzen**: Extrem kurze Airtime = minimaler Stromverbrauch
2. **2.4 GHz LoRa fuer mittlere Distanzen**: 31 mA TX-Strom, weltweit lizenzfrei
3. **Sub-GHz LoRa fuer ferne Distanzen**: Maximale Sensitivity (-141.5 dBm), +22 dBm PA
4. **Energie-basierte Entscheidung**: Wenn Supercaps fast leer → kein stromhungriger Sub-GHz Modus
5. **LR2021 unterstuetzt alle Modi**: Kein Chip-Wechsel noetig

## LoRaWAN Integration
- Zusaetzlich zur P2P-Kommunikation wird LoRaWAN (OTAA/ABP) unterstuetzt
- Ermglicht Positionierung ueber TDoA (Time Difference of Arrival) durch TTN-Gateways
- Der Ballon kennt seine Position nicht selbst → Position wird serverseitig berechnet
- Nutzt The Things Network (TTN) als Backbone
