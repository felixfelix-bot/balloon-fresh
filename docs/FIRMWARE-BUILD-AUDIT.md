# Firmware Build History Audit — multi_radio_sweep_gps.cpp

**Audited:** 2026-07-24  
**Scope:** All commits touching `firmware/rp2040/src/multi_radio_sweep_gps.cpp` in the last 48 hours  
**Purpose:** Determine if TX and RX could have been running incompatible builds during walk tests

## PAYLOAD LAYOUT TIMELINE

### Pre-4a8e4cf (ORIGINAL LAYOUT — now obsolete)
```
bytes 0-1:   seq      (uint16 BE)
byte  2:     phaseId  (uint8)
bytes 3-6:   lat      (float, LE)     ← raw IEEE 754
bytes 7-10:  lon      (float, LE)
bytes 11-12: sats     (uint16 BE)     ← big-endian!
bytes 13-14: fixValid (uint16 BE)
bytes 15-18: utcSec   (uint32 BE)     ← big-endian!
```
- No sync header
- RX gpsOff: LoRa=4, FLRC=0 (FLRC stripped to offset 0)

---

### 4a8e4cf — "fix: TX/RX payload byte alignment — sync header + E7 + LE + gpsOff=4"
**THIS IS THE BREAKING CHANGE.** Every field offset, type, and endianness changed:

```
bytes 0-3:   sync header (0xA5 0x5A 0x42 0x24)   ← NEW (4 bytes)
bytes 4-7:   latE7  (int32 LE)   ← was float LE at offset 3
bytes 8-11:  lonE7  (int32 LE)   ← was float LE at offset 7
bytes 12-13: sats   (uint16 LE)  ← was uint16 BE at offset 11
byte  14:    fixQ   (uint8)      ← was uint16 BE
bytes 15-18: utcSec (uint32 LE)  ← was uint32 BE
byte  19:    phaseId
bytes 20-21: seq    (uint16 BE)  ← moved from bytes 0-1
```

RX changed: gpsOff = 4 for BOTH LoRa and FLRC (was 4/0 split).

**Impact:** A TX board running pre-4a8e4cf firmware talking to an RX running 4a8e4cf+ firmware produces complete garbage:
- Old bytes 3-6 (float lat) → RX interprets as int32 latE7
- Old bytes 11-12 (uint16 BE sats) → lands in middle of int32 lonE7
- Every field misaligned by 4+ bytes
- **This is the sats=52195, lat=-209 bug from walk tests**

---

### aaa7ebf — "fix: align embedGPS/parseGPS byte offsets — sync header + FLRC strip"
**DOCUMENTATION FIX ONLY.** No byte offset changes in embedGPS(). Only updated stale comment block. The code was already correct from 4a8e4cf.

---

### 543e96f, 57ea008, be354b0
No changes to embedGPS/parseGPS. These were data captures, RX loop fixes, and platformio.ini changes.

---

### Other commits (dd43245, d93deea, be049db, a3b51b1, 99f7705, 08e038d)
Changed GPS parsing (NMEA, time sync, watchdog) but **NOT the packet payload layout**. embedGPS byte offsets unchanged.

---

## CONCLUSION

**TX and RX were definitely running incompatible builds during the walk tests.**

The payload layout changed completely at commit `4a8e4cf`. With no firmware versioning:
1. TX could have been flashed from pre-4a8e4cf (old float/BE layout)
2. RX could have been flashed from 4a8e4cf+ (new int32E7/LE layout)
3. Result: every GPS field garbage — sats=52195, lat=-209
4. **There was no way to know which build was on which board**

This is exactly the problem the Firmware Integrity System (Layers 1-5) solves.
