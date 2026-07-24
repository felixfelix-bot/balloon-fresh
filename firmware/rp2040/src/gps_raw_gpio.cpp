/*
 * gps_raw_gpio.cpp — Raw GPIO test for GP1
 * Reads GP1 as digital input, counts transitions over 5 seconds.
 * If GP1 never changes state, the wire isn't connected or GPS isn't powered.
 * Also tries Serial2 (UART1) on GP9 as a second test point.
 */
#include <Arduino.h>

void setup() {
    Serial.begin(115200);
    delay(2000);
    Serial.println("GPS RAW GPIO TEST");
    Serial.println("Reading GP1 as digital input for 5 seconds...");
    Serial.println("Also reading GP9 (UART1 alt RX) for comparison.");
    Serial.println("---");

    pinMode(25, OUTPUT);
    pinMode(16, OUTPUT);

    // GP1 as input with pullup
    pinMode(1, INPUT_PULLUP);
    // GP9 as input with pullup  
    pinMode(9, INPUT_PULLUP);
    // Also check GP0
    pinMode(0, INPUT_PULLUP);

    // Blink
    for (int i = 0; i < 3; i++) {
        digitalWrite(25, HIGH); digitalWrite(16, HIGH);
        delay(200);
        digitalWrite(25, LOW); digitalWrite(16, LOW);
        delay(200);
    }
}

void loop() {
    uint32_t start = millis();
    uint32_t gp1_high = 0, gp1_low = 0;
    uint32_t gp1_transitions = 0;
    uint32_t gp9_transitions = 0;
    uint32_t gp0_transitions = 0;
    int last_gp1 = digitalRead(1);
    int last_gp9 = digitalRead(9);
    int last_gp0 = digitalRead(0);
    uint32_t samples = 0;

    // Sample for 5 seconds
    while (millis() - start < 5000) {
        int gp1 = digitalRead(1);
        int gp9 = digitalRead(9);
        int gp0 = digitalRead(0);

        if (gp1 != last_gp1) { gp1_transitions++; last_gp1 = gp1; }
        if (gp9 != last_gp9) { gp9_transitions++; last_gp9 = gp9; }
        if (gp0 != last_gp0) { gp0_transitions++; last_gp0 = gp0; }

        if (gp1) gp1_high++; else gp1_low++;
        samples++;

        // Toggle LED fast to show we're sampling
        if (samples % 10000 == 0) {
            digitalWrite(25, !digitalRead(25));
        }
    }

    Serial.printf("Samples: %lu\n", samples);
    Serial.printf("GP1: transitions=%lu  high=%lu (%.1f%%)  low=%lu (%.1f%%)\n",
                  gp1_transitions, gp1_high, 100.0*gp1_high/samples,
                  gp1_low, 100.0*gp1_low/samples);
    Serial.printf("GP9: transitions=%lu (comparison - no GPS wire)\n", gp9_transitions);
    Serial.printf("GP0: transitions=%lu (GPS TX pad if wired)\n", gp0_transitions);

    if (gp1_transitions == 0) {
        Serial.println("\n*** GP1 NEVER CHANGES STATE ***");
        Serial.println("GPS TX is NOT driving GP1. Check:");
        Serial.println("  1. GPS module has power (LED on module?)");
        Serial.println("  2. GPS TX wire actually reaches GP1 pad");
        Serial.println("  3. GPS TX wire on correct pad (GP1 = pad #1 left edge)");
    } else if (gp1_transitions < 10) {
        Serial.println("\nGP1 has some activity but very little.");
        Serial.println("May be noise or weak signal.");
    } else {
        Serial.println("\nGP1 HAS SIGNAL! GPS may be working.");
        Serial.println("Issue is likely baud rate mismatch or UART config.");
    }

    Serial.println("---");
    delay(3000);
}
