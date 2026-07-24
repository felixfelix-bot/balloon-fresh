/*
 * gps_test.cpp — Minimal GPS NMEA echo
 * Reads UART0 on GP1 at 115200 baud, echoes to USB CDC.
 * Used to verify GPS module soldering.
 *
 * GPS TX → GP1, GPS VCC → 3V3, GPS GND → GND
 */
#include <Arduino.h>

void setup() {
    Serial.begin(115200);
    delay(2000);
    Serial.println("GPS TEST — listening on GP1 at 115200 baud");
    Serial.println("GPS TX → GP1, UART0 RX");
    Serial.println("---");

    // UART0 on GP0/GP1
    Serial1.setRX(1);  // GP1 = UART0 RX
    Serial1.setTX(0);  // GP0 = UART0 TX (not used, but needed for begin)
    Serial1.begin(115200);

    // Blink LED to show we're alive
    pinMode(25, OUTPUT);
    pinMode(16, OUTPUT);
    for (int i = 0; i < 5; i++) {
        digitalWrite(25, HIGH); digitalWrite(16, HIGH);
        delay(100);
        digitalWrite(25, LOW); digitalWrite(16, LOW);
        delay(100);
    }
    Serial.println("Listening for NMEA...");
}

uint32_t lastData = 0;
uint32_t byteCount = 0;

void loop() {
    while (Serial1.available()) {
        char c = Serial1.read();
        Serial.write(c);
        byteCount++;
        lastData = millis();
    }

    // Every 5 seconds, report status
    static uint32_t lastReport = 0;
    if (millis() - lastReport > 5000) {
        lastReport = millis();
        Serial.printf("\n[STATUS] bytes=%lu last_data=%lu ms ago\n",
                      byteCount,
                      lastData > 0 ? (millis() - lastData) : 99999);
        if (lastData == 0) {
            Serial.println("[WARNING] No GPS data received on GP1!");
            Serial.println("Check: GPS TX → GP1, GPS VCC → 3V3, GPS GND → GND");
        }
        digitalWrite(25, !digitalRead(25));
    }
}
