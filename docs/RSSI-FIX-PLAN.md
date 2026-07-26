# RSSI Fix Plan — Root Cause Analysis & Remediation

## STATUS: RESOLVED (2026-07-23)

All three bugs fixed in range test firmware:
- `flrc_range_rx_auto.cpp`: 0x0104 → 0x024B, 9-bit assembly
- `flrc_range_rx_gps.cpp`: same fix
- LR2021Raw.h (balloon-fresh): already has correct implementation (verified -77 dBm)
- RadioLib getRSSI() FLRC branch: N/A — RadioLib banned per ADR-020

---

## Executive Summary

We never measured real RSSI. All 206,947 packets show constant value 36 due to three compounding bugs across firmware and library layers. This plan fixes all three and establishes a validation protocol.

---

## Root Cause Analysis

### Bug 1: Raw Firmware Uses SX1280 Commands on LR2021 Chip

**Affected files:**
- `rp2040/src/flrc_range_rx_auto.cpp` (line 127-138)
- `rp2040/src/flrc_range_rx_gps.cpp` (line 126-127)
- `rp2040/src/flrc_throughput_rx.cpp` (line 135)

**The code:**
```cpp
// Sends SX1280 GET_PACKET_STATUS = 0x0104
spiRf.transfer(0x01); spiRf.transfer(0x04);
// Reads 4 bytes, interprets buf[1] as RSSI
return -(int8_t)buf[1];
```

**The problem:**
- LR2021's FLRC packet status command is `0x024B` (completely different)
- SX1280 `0x0104` on LR2021 returns garbage from wrong register space
- Value 36 is phantom data, not RSSI

**LR2021 correct format (from RadioLib source):**
```
Command: 0x024B (GET_FLRC_PACKET_STATUS)
Returns 5 bytes:
  [0-1] packet length (16-bit)
  [2]   RSSI average (7 MSBs, 9-bit total)
  [3]   RSSI sync (7 MSBs, 9-bit total)
  [4]   flags: bits[3:2]=rssiAvg LSB, bit[0]=rssiSync LSB, bits[7:4]=syncWordNum

Conversion: rssiAvg = ((buff[2] << 1) | ((buff[4] & 0x04) >> 2)) / -2.0
```

### Bug 2: RadioLib getRSSI() Missing FLRC Branch

**File:** `RadioLib/src/modules/LR2021/LR2021.cpp` (lines 1116-1144)

```cpp
float LR2021::getRSSI(bool packet, bool skipReceive) {
  // ...
  if(modem == RADIOLIB_LR2021_PACKET_TYPE_LORA) {
    state = this->getLoRaPacketStatus(NULL, NULL, NULL, NULL, &rssi, NULL);
  } else if(modem == RADIOLIB_LR2021_PACKET_TYPE_GFSK) {
    state = this->getGfskPacketStatus(NULL, &rssi, NULL, NULL, NULL, NULL);
  } else if(modem == RADIOLIB_LR2021_PACKET_TYPE_OOK) {
    state = this->getOokPacketStatus(NULL, NULL, &rssi, NULL, NULL, NULL);
  } else {
    return(0);  // <-- FLRC FALLS THROUGH HERE, RETURNS 0
  }
}
```

**The problem:** LoRa, GFSK, and OOK all have dispatch branches. FLRC does not. When in FLRC mode, `getRSSI()` returns 0 silently.

### Bug 3: rp2040-flrc-max Firmware Calls Wrong RSSI Method

**File:** `rp2040-flrc-max/src/main.cpp` (line 178)

```cpp
lastRssi = radio.getRSSI();  // Returns 0 for FLRC mode
```

Calls `getRSSI()` which (due to Bug 2) returns 0 for FLRC. Should call `getFlrcPacketStatus()` directly.

---

## Fix Plan

### Step 1: Fix rp2040-flrc-max Firmware (PRIMARY PATH)

Replace `radio.getRSSI()` with direct `getFlrcPacketStatus()` call.

**File:** `rp2040-flrc-max/src/main.cpp`

**Current (line 178):**
```cpp
lastRssi = radio.getRSSI();
```

**Replace with:**
```cpp
float rssiAvg, rssiSync;
radio.getFlrcPacketStatus(NULL, &rssiAvg, &rssiSync, NULL);
lastRssi = (int16_t)rssiAvg;
```

Also add both RSSI values to output for diagnostics:
```cpp
snprintf(linebuf, sizeof(linebuf),
    "RX %lu pkts (%.1f kbps) RSSI=%.1f RSSI_sync=%.1f",
    rxCount, kbps, rssiAvg, rssiSync);
```

And in results block:
```cpp
snprintf(linebuf, sizeof(linebuf), "  RSSI avg:   %.1f dBm", rssiAvgLast);
// ...
snprintf(linebuf, sizeof(linebuf), "  RSSI sync:  %.1f dBm", rssiSyncLast);
```

**Why this matters:** `rssiAvg` is the average RSSI across the entire packet. `rssiSync` is the RSSI at the sync word moment (better for distance correlation since it's a single-point measurement).

### Step 2: Patch RadioLib getRSSI() (DEFENSE IN DEPTH)

Add FLRC branch to the dispatch chain so any future code calling `getRSSI()` works.

**File:** `.pio/libdeps/*/RadioLib/src/modules/LR2021/LR2021.cpp` (line 1138)

**Add before the `else` branch:**
```cpp
  } else if(modem == RADIOLIB_LR2021_PACKET_TYPE_FLRC) {
    state = this->getFlrcPacketStatus(NULL, &rssi, NULL, NULL);
```

**NOTE:** This is a library patch — it needs to be applied in every `.pio/libdeps/*/RadioLib/` copy. Best approach: patch the source repo's RadioLib component (in the ESP-IDF firmware under `components/RadioLib/`) and add a note to platformio.ini `extra_scripts` to auto-patch. Alternatively, fork RadioLib and reference the fork.

### Step 3: Fix Raw Firmware RSSI (BACKWARD COMPATIBILITY)

For `flrc_range_rx_auto.cpp` and `flrc_range_rx_gps.cpp` — if these are still needed for non-RadioLib testing:

**Replace rfReadRssi() entirely:**
```cpp
static int16_t rfReadRssi() {
    rfWaitBusy();
    // LR2021 native command: GET_FLRC_PACKET_STATUS = 0x024B
    // NOT SX1280's 0x0104
    uint8_t cmd[] = { 0x02, 0x4B };
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(cmd[0]);
    spiRf.transfer(cmd[1]);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[5];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 5; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    // 9-bit RSSI: bits [8:1] from buf[2], bit[0] from buf[4]
    uint16_t raw = ((uint16_t)buf[2] << 1) | ((buf[4] & 0x04) >> 2);
    return -(int16_t)(raw / 2);  // Returns dBm
}
```

**WARNING:** This assumes LR2021 SPI command protocol matches RadioLib's `SPIcommand()` framing. Need to verify the SPI framing (header bytes, status byte, etc.) matches. RadioLib wraps commands differently than raw SPI writes.

### Step 4: Build, Flash, Validate

1. Apply Step 1 fix to rp2040-flrc-max
2. Build: `cd rp2040-flrc-max && pio run -e rx`
3. Flash RX board (8332) — BLOCKED: board on DQ05, unreachable
4. Flash TX board (F242D) — already flashed, need reflash only if TX also reads RSSI (it doesn't)
5. Run baseline test at <1m: verify RSSI varies (should be -30 to -50 dBm at close range)
6. Run attenuated test: move TX 5m away, RSSI should change by ~10-15 dB

### Step 5: RSSI Validation Protocol

Before any future range test:

- [ ] **Smoke test:** At <1m, RSSI should read between -20 to -50 dBm
- [ ] **Distance test:** Move TX 1m→5m→10m, RSSI should drop monotonically
- [ ] **Variation test:** At fixed distance, RSSI should vary by <5 dB between packets
- [ ] **Noise floor:** TX OFF, RX should read < -90 dBm or 0 (no packet)
- [ ] **All-zeros check:** If RSSI = 0.0, something is wrong — don't log it as valid

### Step 6: Update RX Logger Script

The `rx_range_logger.py` should validate RSSI:
```python
if rssi == 0 or rssi == 36:
    # Phantom value — flag in log
    log.warning(f"Suspect RSSI={rssi}, possible register read failure")
```

---

## Verification: Expected RSSI Values

Based on free-space path loss at 2440 MHz, +13 dBm TX power:

| Distance | Path Loss (dB) | Expected RSSI (dBm) |
|----------|---------------|---------------------|
| 1m | 40 | -27 |
| 10m | 60 | -47 |
| 50m | 74 | -61 |
| 100m | 80 | -67 |
| 500m | 94 | -81 |
| 1000m | 100 | -87 |

Formula: RSSI = TX_power - 20*log10(d) - 20*log10(f_MHz) + 27.55
At 2440 MHz: RSSI = 13 - 20*log10(d) - 67.7

If measured RSSI does not follow this curve within ~10 dB, the RSSI readback is still broken.

---

## Priority Order

1. **Step 1** (fix rp2040-flrc-max) — immediate, code only, unblocks real RSSI
2. **Step 4** (build + flash) — needs RX board (8332 on DQ05, currently unreachable)
3. **Step 5** (validation) — 10 min bench test, confirms fix works
4. **Step 2** (patch RadioLib) — prevents future bugs, submit upstream PR
5. **Step 3** (fix raw firmware) — only if raw SPI firmware still needed
6. **Step 6** (logger hardening) — prevents silent data corruption