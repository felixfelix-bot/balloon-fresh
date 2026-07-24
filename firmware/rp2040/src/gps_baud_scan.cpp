/*
 * gps_baud_scan.cpp — Scan common GPS baud rates on GP1
 * Tries 4800, 9600, 19200, 38400, 57600, 115200
 * Reports which one gets valid NMEA data.
 */
#include <Arduino.h>

const long bauds[] = {4800, 9600, 19200, 38400, 57600, 115200};
const int numBauds = sizeof(bauds) / sizeof(bauds[0]);

void setup() {
    Serial.begin(115200);
    delay(2000);
    Serial.println("GPS BAUD SCAN — testing GP1 at multiple baud rates");
    Serial.println("GPS TX must be on GP1");
    Serial.println("---");

    pinMode(25, OUTPUT);
    pinMode(16, OUTPUT);

    // Blink to show alive
    for (int i = 0; i < 3; i++) {
        digitalWrite(25, HIGH); digitalWrite(16, HIGH);
        delay(200);
        digitalWrite(25, LOW); digitalWrite(16, LOW);
        delay(200);
    }
}

void loop() {
    for (int b = 0; b < numBauds; b++) {
        long baud = bauds[b];
        Serial.printf("\n=== Testing %ld baud ===\n", baud);

        Serial1.setRX(1);
        Serial1.setTX(0);
        Serial1.begin(baud);
        delay(100);

        // Flush any garbage
        while (Serial1.available()) Serial1.read();

        // Listen for 3 seconds
        uint32_t start = millis();
        int bytes = 0;
        int dollar = 0;  // count $ chars (NMEA start)
        char sample[128];
        int sampleLen = 0;

        while (millis() - start < 3000) {
            while (Serial1.available()) {
                char c = Serial1.read();
                bytes++;
                if (c == '$') dollar++;
                if (sampleLen < 127 && c >= 32 && c <= 126) {
                    sample[sampleLen++] = c;
                }
                digitalWrite(25, !digitalRead(25));
            }
        }

        Serial1.end();
        sample[sampleLen] = '\0';

        Serial.printf("  bytes=%d  $=count=%d\n", bytes, dollar);
        if (bytes > 0) {
            Serial.printf("  raw sample: %.80s\n", sample);
        }
        if (dollar > 0) {
            Serial.printf("  *** FOUND NMEA at %ld baud! ***\n", baud);
        }
    }

    Serial.println("\n=== SCAN COMPLETE ===");
    Serial.println("If no baud worked, check wiring:");
    Serial.println("  GPS TX → GP1 (pad 1, left edge top)");
    Serial.println("  GPS VCC → 3V3 or 5V");
    Serial.println("  GPS GND → GND");
    delay(10000);  // Wait 10s before re-scanning
}
