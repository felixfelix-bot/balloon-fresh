# PLAN: FLRC Byte Alignment + Firmware Identification — Comprehensive Fix

**Created:** 2026-07-24
**Status:** PROPOSED
**Authors:** Felix (orchestrator) + FIPS track independent analysis
**Related:** PLAN-FIRMWARE-INTEGRITY.md, FIRMWARE-BUILD-AUDIT.md, walk-analysis-20260724.md

## PROBLEM SUMMARY

Three bugs found from the 2026-07-24 walk test:

1. **Firmware mismatch** — TX and RX running different commits, different payload layouts. Root cause of 100% garbage data. (FIXED — firmware integrity system implemented in commit 4fb6b9c)

2. **FLRC byte alignment drift** — Even with matching firmware, first 1-3 packets per phase decode correctly, then byte framing drifts. Gets worse at lower FLRC bitrates. RX reads mid-frame garbage.

3. **CRC false positive** — `crc_err=0` on all packets including garbage. The LR2021 hardware CRC passes corrupt data.

---

## BUG 2: FLRC BYTE ALIGNMENT DRIFT

### What Happens

The RX calls `rfReadRxFifo(rxBuf, pktSize)` which reads a FIXED number of bytes (255 for FLRC) from the FIFO. But the actual received packet may be shorter than 255 bytes if the TX doesn't fill the entire buffer.

TX sends 255 bytes: bytes 0-3 sync header, bytes 4-22 GPS payload, bytes 23-254 fill pattern (`i ^ 0xA5`). The FIFO should contain exactly what TX wrote. But...

### Root Cause Analysis

**Theory A: FIFO pointer not reset between packets.**

After reading packet N, RX calls `rfSetRx()` to re-enter RX mode. But it does NOT clear the RX FIFO first. If the chip appends partial data or the read pointer doesn't reset, packet N+1 starts at the wrong byte offset.

Evidence: The existing code has `rfClearRxFifo()` (opcode 0x01, 0x20) but it is NEVER called in `rxPacketPoll()`. It's defined but unused.

**Theory B: FLRC hardware strips sync word differently per bitrate.**

The LR2021 FLRC sync word handling may differ between bitrate settings. At higher bitrates (2600 kbps), the sync word detection is more reliable. At lower bitrates, the sync correlator may miss the sync word and start reading mid-packet.

Evidence: FIPS analysis shows FLRC-2600 works but 1300/650/325 fail. This correlates with sync word detection sensitivity.

**Theory C: RX reads 255 bytes but actual packet is shorter.**

If the TX payload is 22 bytes of meaningful data + 233 bytes of fill pattern, and the radio hardware truncates the packet at the actual data boundary, the FIFO read gets garbage after the valid bytes.

Evidence: TX fills bytes 19-254 with `i ^ 0xA5` pattern. If the chip doesn't transmit all 255 bytes, the FIFO has fewer bytes than expected.

### Fix: Multi-layer Defense

**Fix 2A: Clear RX FIFO before each re-arm (15 min)**

```cpp
// In rxPacketPoll(), after processing a packet:
rfClearIrq();
rfClearRxFifo();  // ← ADD THIS: opcode 0x01 0x20
rfSetRx();
```

**Fix 2B: Application-layer sync word validation (30 min)**

Before parsing GPS data, verify the app sync header is present at bytes 0-3:

```cpp
// Check application sync header (not hardware sync word)
if (rxBuf[0] != 0xA5 || rxBuf[1] != 0x5A || 
    rxBuf[2] != 0x42 || rxBuf[3] != 0x24) {
    // Byte alignment lost — skip this packet
    dualPrintf("SYNC_LOST got=%02X%02X%02X%02X\n", 
               rxBuf[0], rxBuf[1], rxBuf[2], rxBuf[3]);
    rfClearIrq();
    rfClearRxFifo();
    rfSetRx();
    return;
}
```

This prevents garbage from entering the statistics. If sync is lost, we know immediately.

**Fix 2C: GPS range sanity check (15 min)**

After parsing GPS fields, validate they're physically possible:

```cpp
// Sanity check: reject impossible GPS values
if (abs(pktLatE7) > 90*10000000L || abs(pktLonE7) > 180*10000000L 
    || txSats > 50 || txFix > 2) {
    dualPrintf("GPS_REJECT lat=%.5f lon=%.5f sats=%u fix=%u\n",
               pktLatE7/1e7f, pktLonE7/1e7f, txSats, txFix);
    rxGarbageCount++;  // new counter
    // Don't trust this packet's data — but count it as received
    rxReceived++;
    rfClearIrq();
    rfClearRxFifo();
    rfSetRx();
    return;
}
```

---

## BUG 3: CRC FALSE POSITIVE

### What Happens

The LR2021 CRC check (IRQ bit 22) reports no errors on ALL packets, including ones with garbage payloads. The hardware CRC passes corrupt data.

### Root Cause

The LR2021 hardware CRC covers the FLRC/LoRa PDU as configured by `SET_PACKET_PARAMS`. Looking at the code:

For FLRC (line 463 of RX, line 513 of TX):
```cpp
{ 0x02, 0x49, 0x0C, 0x4C, 0x00, FLRC_PKT_SIZE }
```

The `0x0C` byte at position 2 controls CRC type. The LR2021 has CRC options that may only cover the header, not the payload. The datasheet specifies this in the packet parameters.

For LoRa (line 498 of TX):
```cpp
uint8_t flags = 0x04; // explicit header, CRC on
```

The CRC flag is set but the CRC coverage scope is ambiguous.

### Fix: Application-Layer CRC (45 min)

Don't trust hardware CRC alone. Add a CRC-16 over the GPS payload bytes in software:

**TX side (embedGPS):**
```cpp
// After writing all GPS fields (bytes 4-21), compute CRC-16
uint16_t appCrc = crc16(&pkt[4], 18);  // bytes 4-21
pkt[29] = (uint8_t)(appCrc >> 8);      // CRC high byte
pkt[30] = (uint8_t)(appCrc & 0xFF);    // CRC low byte
```

**RX side (rxPacketPoll):**
```cpp
// Verify application CRC before trusting payload
uint16_t expectedCrc = ((uint16_t)rxBuf[gpsOff+25] << 8) | rxBuf[gpsOff+26];
uint16_t actualCrc = crc16(&rxBuf[gpsOff], 18);  // bytes 4-21 relative
if (expectedCrc != actualCrc) {
    rxCrcErrors++;  // count real CRC failures
    dualPrintf("APP_CRC_FAIL expected=%04X actual=%04X\n", expectedCrc, actualCrc);
    rfClearIrq();
    rfClearRxFifo();
    rfSetRx();
    return;
}
```

**CRC-16 implementation (CCITT polynomial 0x1021):**
```cpp
static uint16_t crc16(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int b = 0; b < 8; b++) {
            crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : (crc << 1);
        }
    }
    return crc;
}
```

---

## FIRMWARE IDENTIFICATION (Already Implemented)

The firmware self-identification system from PLAN-FIRMWARE-INTEGRITY.md is DONE (commit 4fb6b9c):

- [x] Build-time git hash injection (inject_git_version.py)
- [x] Boot banner on serial output
- [x] FW_QUERY serial command
- [x] TX payload includes hash (bytes 22-28)
- [x] RX parses hash, includes in PHASE_RESULT
- [x] Flash guard with no bypass
- [x] verify_flash.sh post-flash verification
- [x] FLASH-MANIFEST.csv tracking
- [x] udev rules for stable symlinks

**What's still needed for full data traceability:**

### Capture Header (10 min)

Every capture file should start with a metadata header identifying the firmware:

```
# CAPTURE START 2026-07-25T09:00Z
# RX_FIRMWARE hash=abc123d tag=RX0 built=2026-07-25T08:45Z
# TX_FIRMWARE hash=abc123d tag=TX0 built=2026-07-25T08:45Z (verified via boot banner)
# OPERATOR: Felix
# WALK_TEST: 2026-07-25 walk #2
# NOTES: Both boards flashed from same commit, verified before walk
```

This goes at the top of the capture file, BEFORE any data lines.

### Capture Script Enhancement (30 min)

Modify `sweep_capture.py` (or the bash capture script) to:

1. Read RX boot banner at start (`echo "FW_QUERY" > $PORT`, parse response)
2. Write metadata header to capture file
3. If RX firmware hash is unknown or "unknown" — ABORT with warning
4. Log tx_fw hash from first PHASE_RESULT line and verify it matches expected

### Data Directory Convention (5 min)

```
data/
  walk-2026-07-25/
    capture-rx.txt          # raw RX capture with header
    phone-gps.csv           # phone GPS track
    metadata.json           # structured metadata
    plots/                  # generated plots
    analysis.md             # analysis notes
```

metadata.json:
```json
{
  "date": "2026-07-25",
  "tx_firmware": {"hash": "abc123d", "tag": "TX0", "commit": "abc123d-dirty"},
  "rx_firmware": {"hash": "abc123d", "tag": "RX0", "commit": "abc123d-dirty"},
  "match": true,
  "verified_before_walk": true,
  "operator": "Felix",
  "walk_distance_km": 0,
  "environment": "outdoor"
}
```

---

## IMPLEMENTATION ORDER

| Phase | Task | Effort | Blocks walk? |
|-------|------|--------|-------------|
| **1** | Fix 2A: Clear RX FIFO before re-arm | 15 min | YES |
| **2** | Fix 2B: App sync word validation | 30 min | YES |
| **3** | Fix 2C: GPS sanity check | 15 min | Recommended |
| **4** | Fix 3: Application-layer CRC-16 | 45 min | Recommended |
| **5** | Capture script metadata header | 30 min | No |
| **6** | Data directory convention | 5 min | No |
| **7** | Build + flash + 1m verification | 30 min | YES |
| **8** | Walk test | — | — |

**Total engineering effort:** ~3 hours
**Critical path:** Phases 1-4, 7 → ~2.5 hours before next walk can happen

---

## VERIFICATION CHECKLIST (Before Next Walk)

- [ ] Both TX and RX built from same commit
- [ ] Boot banners read and matching
- [ ] FLRC_RAW32 byte dump shows 0xA5 0x5A 0x42 0x24 at bytes 0-3
- [ ] First 5 packets show valid GPS (lat ~32.6, lon ~-16.9, sats 6-31)
- [ ] No SYNC_LOST messages in first minute
- [ ] No APP_CRC_FAIL messages
- [ ] No GPS_REJECT messages
- [ ] tx_fw hash in PHASE_RESULT matches RX fw hash
- [ ] Capture file starts with metadata header
- [ ] Phone GPS recording started
- [ ] TX GPS has lock before walking (check sats > 6, fix=1)

## LESSONS LEARNED (2026-07-24 Walk Test)

1. **No firmware versioning = flying blind.** Multiple uncontrolled flashes made it impossible to diagnose data corruption. Fixed by Layer 1-3 integrity system.

2. **Hardware CRC is not sufficient.** The LR2021 CRC passes corrupt data. Application-layer CRC is mandatory.

3. **FLRC sync word detection is bitrate-dependent.** Lower bitrates lose sync more often. RX must re-validate sync per packet.

4. **GPS antenna in rucksack doesn't work.** Ceramic patch antenna needs clear sky view. Consider external antenna, top-of-pack placement, or different antenna type.

5. **ESP32 UART bridge saved the capture.** When RP2040 direct USB dropped, the ESP32 bridge relayed data reliably for the entire walk. Dual-path serial output is essential.

6. **Radio hardware is proven good.** FLRC signal at -53 to -58 dBm across 5.7 km. The link works. All issues were firmware/data-layer.

7. **Cross-track analysis works.** FIPS track independently found the byte alignment bug from our shared data. Discovery sync is valuable.
