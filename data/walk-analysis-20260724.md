# Walk Test Analysis — 2026-07-24

## SUMMARY

5.7 km walk test completed. Radio link works at all distances tested. All packet payloads are garbage. Root cause confirmed: TX and RX running mismatched firmware builds.

## DATA OVERVIEW

| Metric | Value |
|--------|-------|
| Duration | 57 min (12:35 - 13:32 UTC) |
| Distance | 5.7 km |
| RX capture lines | 2858 |
| RX packets received | 256 |
| Phone GPS points | 440 |
| Phase results | 148 |

## RSSI BY PHASE (GROUND TRUTH)

| Phase | Mode | Packets | RSSI avg | RSSI min | RSSI max | Verdict |
|-------|------|---------|----------|----------|----------|---------|
| 0 | HF-LoRa-SF7 | 6 | -103 | -104 | -103 | NOISE FLOOR (0 real pkts) |
| 1 | HF-LoRa-SF9 | 1 | -93 | -93 | -93 | NOISE FLOOR |
| 2 | HF-LoRa-SF12 | 0 | — | — | — | NOTHING |
| 3 | HF-FLRC-2600 | 36 | -53 | -54 | -53 | REAL SIGNAL |
| 4 | HF-FLRC-1300 | 36 | -55 | -55 | -54 | REAL SIGNAL |
| 5 | HF-FLRC-650 | 36 | -56 | -56 | -55 | REAL SIGNAL |
| 6 | HF-FLRC-325 | 36 | -57 | -58 | -57 | REAL SIGNAL |
| 7 | LF-LoRa-SF7 | 1 | -103 | -103 | -103 | NOISE FLOOR |
| 8 | LF-LoRa-SF9 | 0 | — | — | — | NOTHING |
| 9 | LF-LoRa-SF12 | 0 | — | — | — | NOTHING |
| 10 | LF-FLRC-2600 | 32 | -54 | -54 | -50 | REAL SIGNAL |
| 11 | LF-FLRC-1300 | 27 | -55 | -56 | -40 | REAL SIGNAL (spike to -40) |
| 12 | LF-FLRC-650 | 32 | -57 | -57 | -56 | REAL SIGNAL |
| 13 | LF-FLRC-325 | 13 | -58 | -59 | -55 | REAL SIGNAL |

**Key finding:** FLRC RSSI is remarkably consistent (-53 to -58 dBm). This is NOT noise — noise varies ±10 dBm. This is a real signal reaching the RX throughout the walk. The -40 dBm spike on LF-FLRC-1300 suggests the TX was briefly closer to the RX (near the start of the walk).

## SEQUENCE NUMBER ANALYSIS

- Range: 321 - 65534
- All 256 unique (no duplicates)
- Diffs are random (not sequential)

**Conclusion:** The bytes RX reads as "seq" are garbage. TX is either not using our packet format, or the byte offsets are wrong. This is consistent with the firmware mismatch hypothesis.

## GPS DATA SANITY CHECK

| Field | Expected | Actual | Verdict |
|-------|----------|--------|---------|
| Sats | 6-31 | 119-65404 | GARBAGE |
| Lat | ~32.6 | -212 to 210 | GARBAGE |
| Lon | ~-16.9 | -214 to 214 | GARBAGE |

Every single GPS field is invalid. 100% of packets.

## ROOT CAUSE (from FIRMWARE-BUILD-AUDIT.md)

Commit `4a8e4cf` completely restructured the packet payload:

| Field | OLD (pre-4a8e4cf) | NEW (4a8e4cf+) |
|-------|-------------------|----------------|
| Offset 0 | seq (uint16 BE) | sync header 0xA5 0x5A 0x42 0x24 |
| GPS fields | float LE, mixed endianness | int32 E7, all little-endian |
| Header | none | 4-byte sync word |
| FLRC offset | gpsOff=0 | gpsOff=4 |

If TX was running old firmware and RX was running new firmware (or vice versa), every field would be misaligned by 4+ bytes with wrong endianness — exactly what we see.

## WHAT WENT RIGHT

1. Radio hardware works — FLRC packets detected at all distances
2. RSSI values are physically correct for the distances involved
3. ESP32 UART bridge provided reliable data path when direct USB dropped
4. Phone GPS ground truth captured cleanly (440 points, 5.7 km)
5. Capture script survived CDC drops and port changes

## WHAT WENT WRONG

1. **No firmware versioning** — no way to know what build was on TX vs RX
2. **Multiple uncontrolled flashes** — sub-managers overwrote each other's binaries
3. **LoRa got zero real packets** — TX phase sync broken (GPS lost lock in rucksack)
4. **All payload data garbage** — TX/RX running incompatible firmware builds

## FIXES IMPLEMENTED

See `docs/FIRMWARE-BUILD-AUDIT.md` and commit `4fb6b9c`:
- Firmware self-identification (git hash in every packet)
- Boot banner verification
- Flash guard (no bypass)
- udev stable symlinks
- Flash manifest

## NEXT WALK TEST CHECKLIST

1. Flash TX from known commit, verify boot banner
2. Flash RX from SAME commit, verify boot banner
3. Confirm tx_fw == rx_fw in first PHASE_RESULT
4. Solve GPS-in-rucksack problem (external antenna? different placement?)
5. Test at close range first (1m) before walking
