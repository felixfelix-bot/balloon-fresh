#include <Arduino.h>

/*
 * ESP32-C3 RP2040 BOOTSEL Controller — Diagnostic Loop v1
 * 
 * PROVEN WORKING 2026-07-15. Triggers BOOTSEL every ~16 seconds.
 * 
 * The trigger happens during blink(5,150) after Phase 2's 3-second reset:
 * the RP2040 reboots during a GPIO8 LOW blink window and enters BOOTSEL.
 * 
 * For reliable flashing, use `make bootsel-1200 PORT=/dev/ttyACM0` instead.
 * This firmware is useful for: proving the circuit works, watchdog RESET.
 *
 * Wiring:
 *   GPIO1  → RP2040 RUN (RESET)
 *   GPIO8  → RP2040 GP0 (BOOTSEL)
 *   GND    → RP2040 GND
 */

#define PIN_RESET   1
#define PIN_BOOTSEL 8

void blink(int count, int ms) {
    for (int i = 0; i < count; i++) {
        digitalWrite(PIN_BOOTSEL, LOW); delay(ms);
        digitalWrite(PIN_BOOTSEL, HIGH); delay(ms);
    }
}

void setup() {
    pinMode(PIN_RESET, OUTPUT);
    pinMode(PIN_BOOTSEL, OUTPUT);
    digitalWrite(PIN_RESET, HIGH);
    digitalWrite(PIN_BOOTSEL, HIGH);
}

void loop() {
    // Phase 1: 3 slow blinks
    blink(3, 500);
    delay(1000);

    // Phase 2: Long reset + blinks (accidentally triggers BOOTSEL)
    digitalWrite(PIN_RESET, LOW);
    delay(3000);
    digitalWrite(PIN_RESET, HIGH);
    blink(5, 150);
    delay(2000);

    // Phase 3: Intentional BOOTSEL sequence  
    digitalWrite(PIN_BOOTSEL, LOW);
    delay(50);
    digitalWrite(PIN_RESET, LOW);
    delay(100);
    digitalWrite(PIN_RESET, HIGH);
    delay(500);
    digitalWrite(PIN_BOOTSEL, HIGH);
    blink(5, 150);
    delay(3000);
}
