/*
 * gps_time_test.cpp — Standalone test for GpsTimeModule
 *
 * Without GPS hardware: should print TIME_MILLIS and incrementing
 * getScheduleTimeMs().
 * With GPS: would print TIME_GPS (requires hardware).
 *
 * Build: pio run -e rp2040-gps-time-test
 */

#include <Arduino.h>
#include "gps_time.h"

// Default pins (overridable via build flags)
#ifndef GPS_RX_PIN
#define GPS_RX_PIN  1   // GP1 — data from GPS
#endif
#ifndef GPS_TX_PIN
#define GPS_TX_PIN  0   // GP0 — config to GPS
#endif
#ifndef GPS_PPS_PIN
#define GPS_PPS_PIN 9   // GP9 — 1PPS interrupt
#endif
#ifndef GPS_BAUD
#define GPS_BAUD    9600
#endif

static GpsTimeModule gps;
static uint32_t lastPrint = 0;

void setup() {
    Serial.begin(115200);
    delay(2000);  // Wait for USB CDC to connect

    Serial.println();
    Serial.println("=== GPS TIME MODULE TEST ===");
    Serial.printf("Pins: RX=GP%d TX=GP%d PPS=GP%d baud=%d\r\n",
                  GPS_RX_PIN, GPS_TX_PIN, GPS_PPS_PIN, GPS_BAUD);

    gps.begin(GPS_RX_PIN, GPS_TX_PIN, GPS_PPS_PIN, GPS_BAUD);
    Serial.println("GPS module initialized — no GPS hardware expected.");
    Serial.println("Should see TIME_MILLIS with incrementing scheduleMs.");
    Serial.println();
}

void loop() {
    gps.update();

    if (millis() - lastPrint >= 1000) {
        lastPrint = millis();
        gps.printStatus();
    }
}
