#include <Arduino.h>

/*
 * ESP32-C3 RP2040 BOOTSEL Controller v6
 *
 * Uses EXACT sequence from diagnostic firmware (proven working 2026-07-15).
 * Loop-based with 3 attempts, then idle.
 *
 * The diagnostic firmware that works has Phase 2 (3-second RESET) before
 * Phase 3 (BOOTSEL sequence). This long reset may be important.
 *
 * Wiring:
 *   GPIO1  → RP2040 RUN (RESET)
 *   GPIO8  → RP2040 GP0 (BOOTSEL)
 *   GND    → RP2040 GND
 */

#define PIN_RESET   1
#define PIN_BOOTSEL 8

static int attempts = 0;
static bool done = false;

void blink(int count, int ms) {
    for (int i = 0; i < count; i++) {
        digitalWrite(PIN_BOOTSEL, LOW);
        delay(ms);
        digitalWrite(PIN_BOOTSEL, HIGH);
        delay(ms);
    }
}

void setup() {
    pinMode(PIN_RESET, OUTPUT);
    pinMode(PIN_BOOTSEL, OUTPUT);
    digitalWrite(PIN_RESET, HIGH);
    digitalWrite(PIN_BOOTSEL, HIGH);
}

void loop() {
    if (done) {
        delay(1000);
        return;
    }

    // Phase 1: 3 slow blinks
    blink(3, 500);
    delay(1000);

    // Phase 2: Long reset (3 seconds LOW)
    digitalWrite(PIN_RESET, LOW);
    delay(3000);
    digitalWrite(PIN_RESET, HIGH);
    blink(5, 150);
    delay(2000);

    // Phase 3: BOOTSEL sequence
    digitalWrite(PIN_BOOTSEL, LOW);
    delay(50);
    digitalWrite(PIN_RESET, LOW);
    delay(100);
    digitalWrite(PIN_RESET, HIGH);
    delay(500);
    digitalWrite(PIN_BOOTSEL, HIGH);
    blink(5, 150);
    delay(3000);

    attempts++;
    if (attempts >= 3) {
        done = true;
        // Continuous slow blink = done
        while (true) {
            blink(1, 1000);
        }
    }
}
