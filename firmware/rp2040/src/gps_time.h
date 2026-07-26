/*
 * gps_time.h — GPS NMEA parser + PPS handler + time abstraction
 *
 * Provides a unified time source for the adaptive bitrate sweep scheduler.
 * When a GPS module with valid fix is connected (Serial2 UART + PPS interrupt),
 * time is anchored to UTC.  When no GPS is available, falls back to millis()
 * (boot-anchored).  Both modes expose the same getScheduleTimeMs() interface
 * so the scheduler does not need to know which clock is active.
 *
 * Hardware wiring (per PLAN-adaptive-sweep-firmware.md):
 *   GPS TX → GP1  (RP2040 UART0 RX, Serial2)
 *   GPS RX → GP0  (RP2040 UART0 TX, Serial2 — config commands, optional)
 *   GPS PPS → GP9 (rising-edge interrupt)
 *   GPS VCC → 3V3,  GPS GND → GND
 *
 * NMEA: parses $GPRMC and $GNRMC (ATGM336H / NEO-6M / modern GNSS).
 * Only RMC is used — it carries UTC time, date, and the A/V valid flag.
 */

#pragma once
#include <Arduino.h>

// ─── Time source enum ────────────────────────────────────────────────
enum TimeSource {
    TIME_NONE,       // begin() not called yet
    TIME_MILLIS,     // No GPS fix — using boot-anchored millis()
    TIME_GPS         // GPS fix obtained — UTC-anchored via PPS
};

// ─── Structured UTC time ─────────────────────────────────────────────
struct GpsTime {
    uint8_t  hour;            // UTC 0-23
    uint8_t  minute;          // 0-59
    uint8_t  second;          // 0-59
    uint32_t millisFraction;  // 0-999 (sub-second from PPS + millis drift)
    bool     valid;           // true = GPS fix obtained
};

// ─── GPS time module ─────────────────────────────────────────────────
class GpsTimeModule {
public:
    // Initialize UART + PPS interrupt.
    //   gpsRxPin  — RP2040 pin connected to GPS TX (NMEA data in)
    //   gpsTxPin  — RP2040 pin connected to GPS RX (config out, optional)
    //   ppsPin    — RP2040 pin connected to GPS 1PPS output
    //   baud      — NMEA baud rate (default 9600 for ATGM336H / NEO-6M)
    void begin(uint8_t gpsRxPin, uint8_t gpsTxPin, uint8_t ppsPin,
               uint32_t baud = 115200);  // GEPRC GEP-M10nano default

    // Call in loop() — reads UART non-blocking, parses NMEA incrementally.
    void update();

    TimeSource getSource();          // TIME_GPS if locked, TIME_MILLIS fallback
    bool       isLocked();           // GPS has valid fix
    uint32_t   getUtcSeconds();      // Seconds since UTC midnight (for scheduling)
    uint32_t   getBootMillis();      // Raw millis() (fallback clock)
    GpsTime    getTime();            // Full structured time

    // Monotonically increasing "schedule time" in ms:
    //   GPS locked  → UTC-anchored (utcSeconds*1000 + elapsed since PPS)
    //   No GPS      → boot-anchored millis()
    uint32_t   getScheduleTimeMs();

    // Diagnostic — prints source, UTC time, PPS stats to Serial.
    void       printStatus();

private:
    static void ppsIsrTrampoline();  // ISR entry point (for attachInterrupt)

    void parseNMEA(const char *sentence);
    void onPPS();                    // Interrupt handler — resyncs millis offset

    // NMEA parser state
    char    nmeaBuf[128];
    uint8_t nmeaPos;
    bool    sentenceComplete;

    // GPS state
    bool     gpsValid;
    GpsTime  gpsTime;
    uint32_t utcSeconds;     // seconds since UTC midnight (cached)

    // PPS / offset tracking
    volatile uint32_t ppsMillis;    // millis() at last PPS edge (ISR-written)
    volatile uint32_t ppsCount;     // PPS pulses since boot (ISR-written)
    volatile bool     ppsNewFlag;   // PPS fired since last GPRMC parse
    int32_t  millisOffset;  // (utcSeconds*1000) - millis() at last PPS
    uint32_t lastGprmcMs;   // millis() when last valid GPRMC was parsed

    // Pins
    uint8_t rxPin, txPin, ppsPinNum;
    uint32_t baudRate;
    bool     initialized;
};
