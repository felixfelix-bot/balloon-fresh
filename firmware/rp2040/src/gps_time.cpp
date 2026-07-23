/*
 * gps_time.cpp — GPS NMEA parser + PPS handler + time abstraction
 *
 * Implementation notes (per PLAN-adaptive-sweep-firmware.md Phase 1):
 *
 * - Parse only $GPRMC / $GNRMC sentences (time + date + valid flag).
 *   Other sentences ($GPGGA, $GPGSV, etc.) are skipped to save CPU.
 *
 * - PPS interrupt (GP9, rising edge): stores millis() on the edge.
 *   The GPRMC sentence arriving ~100-900 ms after each PPS reports the
 *   UTC time *at* that PPS edge.  After parsing, we compute:
 *       millisOffset = utcSeconds*1000 - ppsMillis
 *   which lets us convert any millis() reading to UTC milliseconds.
 *
 * - getScheduleTimeMs():
 *       GPS locked  → utcSeconds*1000 + (millis() - ppsMillis)
 *       No GPS      → millis()
 *   Both are monotonically increasing uint32_t values suitable for the
 *   sweep scheduler's modular arithmetic.
 *
 * - UART0 on RP2040 (earlephilhower core) = Serial2.
 *   GPS TX → GP1 (Serial2 RX), GPS RX → GP0 (Serial2 TX).
 *
 * - update() is fully non-blocking: reads whatever chars are available,
 *   parses on newline.  Never calls delay().
 */

#include "gps_time.h"

// ─── Static ISR trampoline ───────────────────────────────────────────
// attachInterrupt needs a plain function pointer, not a member function.
// We store the active instance and forward to its onPPS().
static GpsTimeModule *s_gpsInstance = nullptr;

void GpsTimeModule::ppsIsrTrampoline() {
    if (s_gpsInstance) {
        s_gpsInstance->onPPS();
    }
}

// ─── Constructor-equivalent: begin() ─────────────────────────────────
void GpsTimeModule::begin(uint8_t gpsRxPin, uint8_t gpsTxPin, uint8_t ppsPin,
                           uint32_t baud) {
    rxPin      = gpsRxPin;
    txPin      = gpsTxPin;
    ppsPinNum  = ppsPin;
    baudRate   = baud;
    initialized = true;

    // Reset all state
    nmeaPos         = 0;
    sentenceComplete = false;
    gpsValid        = false;
    utcSeconds      = 0;
    ppsMillis       = 0;
    ppsCount        = 0;
    ppsNewFlag      = false;
    millisOffset    = 0;
    lastGprmcMs     = 0;

    gpsTime.hour           = 0;
    gpsTime.minute         = 0;
    gpsTime.second         = 0;
    gpsTime.millisFraction = 0;
    gpsTime.valid          = false;

    // Configure UART0 as Serial2 (GP0=TX, GP1=RX)
    // earlephilhower core: Serial2 = UART0, Serial1 = UART1
    Serial2.setRX(rxPin);   // GP1 — data from GPS
    Serial2.setTX(txPin);   // GP0 — config to GPS (optional)
    Serial2.begin(baudRate);

    // Configure PPS interrupt (rising edge)
    pinMode(ppsPinNum, INPUT_PULLDOWN);  // GPS PPS is active-high pulse
    s_gpsInstance = this;
    attachInterrupt(ppsPinNum, GpsTimeModule::ppsIsrTrampoline, RISING);
}

// ─── Main loop call: non-blocking NMEA reader ────────────────────────
void GpsTimeModule::update() {
    if (!initialized) return;

    // Read all available characters without blocking
    while (Serial2.available()) {
        char c = Serial2.read();

        if (c == '$') {
            // Start of a new NMEA sentence
            nmeaPos = 0;
            nmeaBuf[nmeaPos++] = c;
        } else if (c == '\n' || c == '\r') {
            // End of sentence — parse if we have enough data
            if (nmeaPos > 6) {
                nmeaBuf[nmeaPos] = '\0';
                sentenceComplete = true;
                parseNMEA(nmeaBuf);
            }
            nmeaPos = 0;
        } else {
            // Accumulate character (bounds-checked)
            if (nmeaPos < sizeof(nmeaBuf) - 1) {
                nmeaBuf[nmeaPos++] = c;
            }
            // If buffer overflows, we just drop chars until next '$'
        }
    }
}

// ─── NMEA sentence parser ────────────────────────────────────────────
// Parses $GPRMC and $GNRMC:
//   $GPRMC,hhmmss.ss,A,ddmm.mmmm,N,dddmm.mmmm,W,sss.s,ccc.c,ddmmyy,...*CS
//   $GNRMC,hhmmss.ss,A,...  (same format, GNSS prefix)
//
// Fields used:
//   [1] time     — UTC hhmmss.ss
//   [2] status   — A=valid fix, V=invalid
//   [9] date     — ddmmyy (parsed but not currently used for scheduling)
//
// We only extract time + status for the scheduler.  Lat/lon/date are
// skipped to keep this module focused on timekeeping.
void GpsTimeModule::parseNMEA(const char *sentence) {
    // Accept both $GPRMC (GPS-only modules like NEO-6M) and $GNRMC
    // (multi-GNSS modules like ATGM336H)
    bool isRmc = (strncmp(sentence, "$GPRMC", 6) == 0 ||
                  strncmp(sentence, "$GNRMC", 6) == 0);
    if (!isRmc) return;

    // Extract time string and status field using sscanf.
    // The full RMC has 12 fields; we only need the first two.
    char   timeStr[16] = {0};
    char   status      = 'V';

    // $G?RMC,time,status,...
    int parsed = sscanf(sentence,
                        "$G%*cRMC,%15[^,],%c,",
                        timeStr, &status);

    if (parsed < 1) return;  // Malformed sentence

    // Parse time: hhmmss.ss → hours, minutes, seconds
    if (strlen(timeStr) >= 6) {
        int hh = (timeStr[0] - '0') * 10 + (timeStr[1] - '0');
        int mm = (timeStr[2] - '0') * 10 + (timeStr[3] - '0');
        int ss = (timeStr[4] - '0') * 10 + (timeStr[5] - '0');

        // Sanity check
        if (hh < 24 && mm < 60 && ss < 60) {
            uint32_t newUtc = (uint32_t)(hh * 3600 + mm * 60 + ss);

            gpsTime.hour   = (uint8_t)hh;
            gpsTime.minute = (uint8_t)mm;
            gpsTime.second = (uint8_t)ss;
            utcSeconds     = newUtc;
            lastGprmcMs    = millis();

            if (status == 'A') {
                // Valid fix
                gpsValid       = true;
                gpsTime.valid  = true;

                // Recompute millis offset:
                // If a PPS fired since the last GPRMC, use the precise
                // PPS timestamp.  Otherwise approximate from arrival time.
                if (ppsCount > 0) {
                    millisOffset = (int32_t)(utcSeconds * 1000UL) -
                                   (int32_t)ppsMillis;
                } else {
                    // No PPS hardware — rough alignment (±0.5s error)
                    millisOffset = (int32_t)(utcSeconds * 1000UL) -
                                   (int32_t)millis();
                }
                ppsNewFlag = false;
            } else {
                // Status 'V' — fix invalid (no satellites / cold start)
                gpsValid      = false;
                gpsTime.valid = false;
            }
        }
    }
}

// ─── PPS interrupt handler ───────────────────────────────────────────
// Called from gpsPpsIsrTrampoline() on rising edge of GPS 1PPS output.
// Must be minimal — no Serial prints, no delay, no allocations.
// On RP2040, millis() reads the hardware timer register directly, so
// it is safe to call from an ISR.
void GpsTimeModule::onPPS() {
    ppsMillis  = millis();
    ppsCount++;
    ppsNewFlag = true;
}

// ─── Public query methods ────────────────────────────────────────────

TimeSource GpsTimeModule::getSource() {
    if (!initialized) return TIME_NONE;
    if (gpsValid)     return TIME_GPS;
    return TIME_MILLIS;
}

bool GpsTimeModule::isLocked() {
    return gpsValid;
}

uint32_t GpsTimeModule::getUtcSeconds() {
    return utcSeconds;
}

uint32_t GpsTimeModule::getBootMillis() {
    return millis();
}

GpsTime GpsTimeModule::getTime() {
    GpsTime t = gpsTime;

    // Compute sub-second fraction from PPS drift
    if (ppsCount > 0 && gpsValid) {
        uint32_t elapsed = millis() - ppsMillis;  // unsigned: handles wrap
        t.millisFraction = elapsed % 1000;
    } else {
        t.millisFraction = 0;
    }
    return t;
}

uint32_t GpsTimeModule::getScheduleTimeMs() {
    if (gpsValid) {
        // UTC-anchored time:
        //   last_utc_second_in_ms + elapsed_millis_since_pps
        // Uses uint32_t unsigned arithmetic — wraps correctly at midnight
        // and across millis() ~49.7-day rollover.
        return utcSeconds * 1000UL + (millis() - ppsMillis);
    }
    // Fallback: boot-anchored millis()
    return millis();
}

// ─── Diagnostic output ───────────────────────────────────────────────
void GpsTimeModule::printStatus() {
    const char *srcStr;
    switch (getSource()) {
        case TIME_GPS:    srcStr = "GPS";   break;
        case TIME_MILLIS: srcStr = "MILLIS"; break;
        default:          srcStr = "NONE";   break;
    }

    Serial.printf("GPS_TIME src=%s locked=%d utc=%02u:%02u:%02u utcSec=%lu "
                  "schedMs=%lu ppsCount=%lu offset=%ld\r\n",
                  srcStr,
                  gpsValid ? 1 : 0,
                  gpsTime.hour, gpsTime.minute, gpsTime.second,
                  (unsigned long)utcSeconds,
                  (unsigned long)getScheduleTimeMs(),
                  (unsigned long)ppsCount,
                  (long)millisOffset);
}
