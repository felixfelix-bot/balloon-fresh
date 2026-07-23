# PLAN: Adaptive Bitrate Sweep Firmware for Outdoor Range Testing

**Date:** 2026-07-23
**Status:** Ready for implementation
**Prerequisite:** GPS module not required for Phase 1 (millis fallback)

## GOAL

Both TX and RX boards auto-cycle through 4 FLRC bitrates (2600/1300/650/325 kbps)
on a fixed time schedule. Operator flashes once, walks to test position, sits for
12 minutes = one full cycle. No reflashing between bitrates.

When GPS is soldered: schedule anchors to UTC time via PPS. Zero drift.
Without GPS: schedule anchors to boot time via millis(). ~5s skew acceptable.

## ARCHITECTURE

```
┌─────────────────────────────────────────┐
│           TX (rp2040-range-tx-sweep)     │
│                                         │
│  ┌─────────┐  ┌──────────┐  ┌────────┐ │
│  │GPS Time │→ │ Scheduler│→ │Burst TX│ │
│  │ Module  │  │ (4-mode) │  │ Engine │ │
│  └─────────┘  └──────────┘  └────────┘ │
│       ↕             ↕                    │
│  millis()      rfSetBitrate()           │
│  fallback      + CALIBRATE              │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│           RX (rp2040-range-rx-sweep)     │
│                                         │
│  ┌─────────┐  ┌──────────┐  ┌────────┐ │
│  │GPS Time │→ │ Scheduler│→ │Receive │ │
│  │ Module  │  │ (4-mode) │  │ + RSSI │ │
│  └─────────┘  └──────────┘  └────────┘ │
│       ↕             ↕                    │
│  millis()      rfSetBitrate()           │
│  fallback      + CALIBRATE              │
└─────────────────────────────────────────┘
```

## NEW FILES

```
firmware/rp2040/src/
├── gps_time.h          # GPS NMEA parser + PPS handler + time abstraction
├── gps_time.cpp        # Implementation
├── sweep_scheduler.h   # Bitrate schedule state machine
├── sweep_scheduler.cpp # Implementation
├── flrc_range_tx_sweep.cpp  # TX sweep firmware (based on tx_auto)
├── flrc_range_rx_sweep.cpp  # RX sweep firmware (based on raw_rx)
```

## RP2040 PIN MAP (available GPIOs)

Currently used:
- GP2=SCK, GP3=MOSI, GP4=MISO, GP5=CS (SPI to LR2021)
- GP6=BUSY, GP7=IRQ, GP8=RST (LR2021 control)
- GP12=UART_TX, GP13=UART_RX (ESP32 bridge)
- GP16=LED_ALT, GP25=LED

FREE for GPS:
- GP0=UART0_TX (GPS NMEA TX, usually not needed)
- GP1=UART0_RX (GPS NMEA RX — data from GPS module)
- GP9=PPS interrupt (GPS 1PPS pulse)
- GP10, GP11, GP14, GP15, GP17-GP24, GP26-GP28 = spare

GPS wiring (when soldered):
- GPS TX → GP1 (RP2040 UART0 RX)
- GPS RX → GP0 (RP2040 UART0 TX, for config commands)
- GPS PPS → GP9 (interrupt)
- GPS VCC → 3.3V
- GPS GND → GND

---

## PHASE 1: GPS Time Module (gps_time.h/cpp)
**Worker:** Leaf, glm-5.2
**Depends on:** Nothing
**Estimated:** 30 min

### Deliverable
`gps_time.h` + `gps_time.cpp` — self-contained GPS time abstraction.

### Interface
```cpp
// gps_time.h
#pragma once
#include <Arduino.h>

enum TimeSource { TIME_NONE, TIME_MILLIS, TIME_GPS };

struct GpsTime {
    uint8_t hour;       // UTC 0-23
    uint8_t minute;     // 0-59
    uint8_t second;     // 0-59
    uint32_t millisFraction; // 0-999 (from PPS + millis drift)
    bool valid;         // GPS fix obtained
};

class GpsTimeModule {
public:
    void begin(uint8_t gpsRxPin, uint8_t gpsTxPin, uint8_t ppsPin,
               uint32_t baud = 9600);
    void update();       // Call in loop() — reads UART, parses NMEA

    TimeSource getSource();     // TIME_GPS if locked, TIME_MILLIS if fallback
    bool isLocked();            // GPS has valid fix
    uint32_t getUtcSeconds();   // Seconds since UTC midnight (for scheduling)
    uint32_t getBootMillis();   // Raw millis() (fallback clock)
    GpsTime getTime();          // Full structured time

    // For scheduling: returns a monotonically increasing "schedule time"
    // that is either UTC-anchored (GPS) or boot-anchored (millis).
    uint32_t getScheduleTimeMs();

private:
    void parseNMEA(const char* sentence);
    void onPPS();  // Interrupt handler — resyncs millis offset

    // NMEA parser state
    char nmeaBuf[128];
    uint8_t nmeaPos;
    bool sentenceComplete;

    // GPS state
    bool gpsValid;
    GpsTime gpsTime;
    uint32_t ppsMillis;   // millis() at last PPS edge
    uint32_t ppsCount;    // PPS pulses since boot
    int32_t millisOffset; // (gpsUtcSeconds*1000) - millis() at last PPS

    // Pins
    uint8_t rxPin, txPin, ppsPinNum;
};
```

### Implementation Notes
- Parse only `$GPRMC` sentence (has time + date + valid flag). Skip other sentences.
- PPS interrupt: store `millis()` on rising edge. After next GPRMC parse, compute offset.
- `getScheduleTimeMs()`: if GPS locked → return `(utcSeconds * 1000 + (millis() - ppsMillis))`. If not → return `millis()`.
- NMEA baud defaults to 9600 (ATGM336H, NEO-6M default). Override via build flag.
- UART0 on RP2040: `Serial2.setRX(GP1); Serial2.setTX(GP0); Serial2.begin(9600);`
- Do NOT block in update(). Read available chars, parse incrementally.

### Test (no hardware)
Build with a test main that prints `getSource()` and `getScheduleTimeMs()` every second.
Without GPS: should print TIME_MILLIS and incrementing millis().
(With GPS: would print TIME_GPS — but can't test without hardware.)

### Build Verification
Create `firmware/rp2040/src/gps_time_test.cpp` that includes gps_time.h and prints source.
Build with: `pio run -e rp2040-gps-time-test`

---

## PHASE 2: Bitrate Switching Function (radio layer)
**Worker:** Leaf, glm-5.2
**Depends on:** Nothing (can run parallel with Phase 1)
**Estimated:** 15 min

### Deliverable
Add `rfSwitchBitrate(uint16_t newBitrate)` to radio layer.

### Function
```cpp
// Switches FLRC bitrate at runtime without full chip reset.
// Must be called from standby mode.
static void rfSwitchBitrate(uint16_t newBitrate) {
    // 1. Enter standby
    uint8_t stdby[] = { 0x02, 0x00, 0x01 }; // STDBY_RC
    rfWriteCmd(stdby, 3);
    delay(1);

    // 2. Set new modulation params (bitrate + bandwidth)
    rfSetBitrate(newBitrate);
    delay(1);

    // 3. Recalibrate (bandwidth changes with bitrate)
    uint8_t calib[] = { 0x01, 0x22, 0x5F };
    rfWriteCmd(calib, 3);
    delay(5);

    // 4. Clear IRQs
    uint8_t clrIrq[] = { 0x02, 0x0B, 0x02 };
    rfWriteCmd(clrIrq, 3);
    delay(1);
}
```

### Verification
The function compiles and is callable. Actual RF verification needs hardware.
Add to a shared header so both TX and RX can call it.

### Key Insight
The existing `rfSetBitrate()` only writes SET_FLRC_MOD_PARAMS (0x0248).
The new function wraps it with: STDBY → MOD_PARAMS → CALIBRATE → CLEAR_IRQ.
This mirrors what `rawInitRadio()` does at lines 237-244 of tx_auto but skips
the full reset + frequency + sync word + packet params (those stay the same).

---

## PHASE 3: Sweep Scheduler (sweep_scheduler.h/cpp)
**Worker:** Leaf, glm-5.2
**Depends on:** Phase 1 (gps_time.h interface only — header dep)
**Estimated:** 25 min

### Deliverable
`sweep_scheduler.h` + `sweep_scheduler.cpp`

### Interface
```cpp
// sweep_scheduler.h
#pragma once
#include <Arduino.h>
#include "gps_time.h"

struct SweepEntry {
    uint16_t bitrateKbps;
    uint32_t durationMs;    // How long to stay in this mode
};

class SweepScheduler {
public:
    // Default schedule: 2600, 1300, 650, 325 kbps, 3 min each
    void begin(GpsTimeModule* gps, uint32_t cycleOffsetMs = 0);

    // Check if it's time to switch. Returns true if bitrate changed this call.
    bool update();

    uint16_t getCurrentBitrate();
    uint8_t getCurrentIndex();     // 0-3
    uint8_t getCurrentCycle();     // Which repetition (0,1,2...)
    uint32_t getTimeInWindowMs();  // Elapsed time in current window
    uint32_t getTimeUntilSwitchMs(); // Time remaining

    void setSchedule(const SweepEntry* entries, uint8_t count);
    void printStatus();

    // Static default schedule (4 entries)
    static const SweepEntry DEFAULT_SCHEDULE[];
    static const uint8_t DEFAULT_SCHEDULE_LEN;

private:
    GpsTimeModule* gps;
    SweepEntry schedule[8];
    uint8_t scheduleLen;
    uint8_t currentIndex;
    uint32_t cycleStartTimeMs;  // When current cycle started (schedule time)
    uint32_t lastSwitchMs;      // When current window started
    uint32_t cycleCount;
};
```

### Default Schedule
```
Window 0: 2600 kbps, 180000 ms (3 min)
Window 1: 1300 kbps, 180000 ms (3 min)
Window 2: 650 kbps,  180000 ms (3 min)
Window 3: 325 kbps,  180000 ms (3 min)
Total cycle: 720000 ms (12 min), then repeats
```

### Implementation Notes
- `update()` checks `gps->getScheduleTimeMs()` against window boundaries.
- If GPS locked: schedule aligns to UTC minute boundaries. Both TX+RX switch at same UTC time.
- If GPS not locked: schedule uses millis(). Some boot skew between TX and RX.
- `cycleOffsetMs`: allows staggering TX window by a small offset to avoid simultaneous TX/RX switching.
- At each boundary: call `rfSwitchBitrate()`, reset window stats, print `SWEEP_SWITCH idx=%d bitrate=%d source=%s`.

### Synchronization Logic
```cpp
uint32_t now = gps->getScheduleTimeMs();
uint32_t elapsedInCycle = (now - cycleStartTimeMs) % totalCycleMs;
uint8_t newIndex = 0;
uint32_t accum = 0;
for (uint8_t i = 0; i < scheduleLen; i++) {
    accum += schedule[i].durationMs;
    if (elapsedInCycle < accum) { newIndex = i; break; }
}
if (newIndex != currentIndex) {
    // Time to switch!
    currentIndex = newIndex;
    return true; // Caller switches bitrate + resets stats
}
return false;
```

---

## PHASE 4: TX Sweep Firmware (flrc_range_tx_sweep.cpp)
**Worker:** Leaf, glm-5.2
**Depends on:** Phase 1 + Phase 2 + Phase 3
**Estimated:** 30 min

### Deliverable
`flrc_range_tx_sweep.cpp` + platformio.ini env `rp2040-range-tx-sweep`

### Based On
`flrc_range_tx_auto.cpp` — keep all SPI, init, burst, heartbeat logic.

### Changes
1. Include `gps_time.h` + `sweep_scheduler.h`
2. Add GPS module + scheduler instances
3. In setup():
   - After radio init: `gps.begin(GPS_RX_PIN, GPS_TX_PIN, GPS_PPS_PIN)`
   - `scheduler.begin(&gps)`
   - Print schedule: `SWEEP_SCHEDULE cycle=12min modes=2600,1300,650,325 x3min`
4. In loop():
   - `gps.update()` (reads NMEA)
   - `scheduler.update()` → if bitrate changed: `rfSwitchBitrate()`, print switch
   - Then existing burst logic with `scheduler.getCurrentBitrate()` in output
5. Output line format:
   ```
   RANGE_RESULT_TX,window=N,burst=M,sent=500,fired=500,timeout=0,bitrate=2600,sweepIdx=0,cycle=0,time_src=GPS,utc_hhmmss=140327,...
   ```
6. Add `bitrate=%d,sweepIdx=%d,cycle=%d,time_src=%s` to all BURST and RESULT lines.

### platformio.ini
```ini
[env:rp2040-range-tx-sweep]
extends = env:rp2040-range-tx-auto
build_flags = ${env:rp2040-range-tx-auto.build_flags}
src_filter = +<*> -<flrc_range_tx_auto.cpp> +<flrc_range_tx_sweep.cpp>
```

### GPS Pin Defines (build flags)
```ini
-D GPS_RX_PIN=1
-D GPS_TX_PIN=0
-D GPS_PPS_PIN=9
-D GPS_BAUD=9600
```

---

## PHASE 5: RX Sweep Firmware (flrc_range_rx_sweep.cpp)
**Worker:** Leaf, glm-5.2
**Depends on:** Phase 1 + Phase 2 + Phase 3
**Estimated:** 30 min

### Deliverable
`flrc_range_rx_sweep.cpp` + platformio.ini env `rp2040-range-rx-sweep`

### Based On
`flrc_raw_rx.cpp` — keep all SPI, GPIO IRQ poll, FIFO read, RSSI, PER logic.

### Changes
1. Include `gps_time.h` + `sweep_scheduler.h`
2. Add GPS module + scheduler instances
3. In setup():
   - After radio init: `gps.begin()` + `scheduler.begin(&gps)`
   - Noise floor measurement (existing)
   - Print schedule
4. In receive loop:
   - `gps.update()` (non-blocking NMEA read)
   - `scheduler.update()` → if bitrate changed: `rfSwitchBitrate()`, `resetStats()`, re-arm RX
5. PER window alignment:
   - RX window resets at each bitrate boundary
   - RESULT line includes `bitrate=%d,sweepIdx=%d,cycle=%d`
   - This gives clean per-bitrate PER + RSSI data
6. Output line format:
   ```
   RANGE_RESULT_RX,window=N,rx=2500,unique=2500,lost=0,total=2500,per=0.00,bitrate=2600,sweepIdx=0,cycle=0,time_src=GPS,rssi_avg=-60.0,rssi_min=-61,noise_floor=-103,...
   ```

### Key Difference from TX
RX must re-arm the receiver after each bitrate switch:
```cpp
rfSetRx();  // Re-enter RX continuous mode after switch
```

---

## PHASE 6: Build Verification + PlatformIO Envs
**Worker:** Leaf, glm-4.5-flash
**Depends on:** Phase 4 + Phase 5
**Estimated:** 10 min

### Tasks
1. Add envs to platformio.ini:
   - `rp2040-range-tx-sweep` (TX sweep with GPS + millis fallback)
   - `rp2040-range-rx-sweep` (RX sweep with GPS + millis fallback)
   - `rp2040-gps-time-test` (standalone GPS time test)
2. Build all three. Fix compile errors.
3. Verify `pio run -e rp2040-range-tx-sweep` and `rp2040-range-rx-sweep` pass.
4. Run gps_time_test to verify millis fallback works (no GPS hardware needed).

### Acceptance Criteria
- All 3 new envs compile with zero errors
- Existing 11 envs still compile (no regressions)
- gps_time_test prints `TIME_MILLIS` and incrementing schedule time

---

## DEPENDENCY GRAPH

```
Phase 1 (GPS Time)  ────────┐
                             ├──→ Phase 4 (TX Sweep) ──┐
Phase 2 (Bitrate)   ────────┤                           ├──→ Phase 6 (Build)
                     ├──→ Phase 3 (Scheduler)          │
                     │         │                        │
                     └─────────┴──→ Phase 5 (RX Sweep) ─┘
```

Phase 1 + 2 run in parallel (independent).
Phase 3 depends on Phase 1 (header only).
Phase 4 + 5 depend on 1+2+3, can run in parallel.
Phase 6 depends on 4+5.

## WORKER ASSIGNMENT

| Worker | Phase | Model | Parallel? |
|--------|-------|-------|-----------|
| W1     | Phase 1: GPS Time Module | glm-5.2 | Yes (with W2) |
| W2     | Phase 2: Bitrate Switch + Phase 3: Scheduler | glm-5.2 | Yes (with W1) |
| W3     | Phase 4: TX Sweep Firmware | glm-5.2 | After W1+W2 |
| W4     | Phase 5: RX Sweep Firmware | glm-5.2 | After W1+W2, parallel with W3 |
| W5     | Phase 6: Build + Verify | glm-4.5-flash | After W3+W4 |

Optimal dispatch: W1+W2 parallel → W3+W4 parallel → W5.

## OUTPUT FORMAT (for outdoor test data)

Each 12-minute cycle produces 4 RESULT lines (one per bitrate):

```
RANGE_RESULT_RX,cycle=0,sweepIdx=0,bitrate=2600,distance=10m,rx=2500,lost=0,per=0.0,rssi_avg=-47.0,rssi_min=-48,noise_floor=-103,time_src=GPS
RANGE_RESULT_RX,cycle=0,sweepIdx=1,bitrate=1300,distance=10m,rx=2500,lost=0,per=0.0,rssi_avg=-47.0,rssi_min=-48,noise_floor=-103,time_src=GPS
RANGE_RESULT_RX,cycle=0,sweepIdx=2,bitrate=650, distance=10m,rx=2500,lost=0,per=0.0,rssi_avg=-48.0,rssi_min=-49,noise_floor=-103,time_src=GPS
RANGE_RESULT_RX,cycle=0,sweepIdx=3,bitrate=325, distance=10m,rx=2500,lost=0,per=0.0,rssi_avg=-48.0,rssi_min=-49,noise_floor=-103,time_src=GPS
```

Operator stands at each distance for 12+ minutes. One cycle = all 4 bitrates.

## WHAT THE OPERATOR DOES (physical — deferred)

1. Solder GPS module to RP2040 (GP0, GP1, GP9, 3.3V, GND)
2. Flash TX with rp2040-range-tx-sweep
3. Flash RX with rp2040-range-rx-sweep
4. Go outside. Position TX at fixed point.
5. Walk to 10m. Wait 12 min. Record cycle.
6. Walk to 50m. Wait 12 min. Record cycle.
7. Walk to 100m. Wait 12 min. Record cycle.
8. Walk to 500m. Wait 12 min. Record cycle.
9. Come back. Plug RX into laptop. Parse CSV.

Total outdoor time: ~1 hour for 4 distances.
