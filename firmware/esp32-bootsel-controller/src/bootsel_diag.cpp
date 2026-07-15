/*
 * bootsel_diag.cpp — GPIO diagnostic for ESP32-C3 SuperMini
 *
 * Toggles GPIO1 and GPIO8 at visible rates so user can verify with multimeter.
 * Also tries GPIO3 and GPIO10 as alternates.
 *
 * LED pattern:
 *   Phase 1 (5 blinks, fast): firmware running OK
 *   Phase 2 (2s): GPIO1 LOW, all others HIGH — check D1 with multimeter = 0V
 *   Phase 3 (2s): GPIO1 HIGH, GPIO8 LOW — check D8 with multimeter = 0V
 *   Phase 4 (2s): ALL HIGH — everything should read 3.3V
 *   Repeat
 */

#include <Arduino.h>

// All candidate BOOTSEL/RESET pins
#define PIN_RESET   1   // GPIO1 / D1
#define PIN_BOOTSEL 8   // GPIO8 / D8
#define PIN_ALT_A   3   // GPIO3 / D3 (alternate)
#define PIN_ALT_B   10  // GPIO10 / D10 (alternate)

void allHigh() {
    digitalWrite(PIN_RESET, HIGH);
    digitalWrite(PIN_BOOTSEL, HIGH);
    digitalWrite(PIN_ALT_A, HIGH);
    digitalWrite(PIN_ALT_B, HIGH);
}

void setup() {
    pinMode(PIN_RESET, OUTPUT);
    pinMode(PIN_BOOTSEL, OUTPUT);
    pinMode(PIN_ALT_A, OUTPUT);
    pinMode(PIN_ALT_B, OUTPUT);
    allHigh();
    delay(200);

    // Phase 1: 5 fast blinks (firmware alive)
    for (int i = 0; i < 5; i++) {
        digitalWrite(PIN_BOOTSEL, LOW);  // LED ON
        delay(100);
        digitalWrite(PIN_BOOTSEL, HIGH); // LED OFF
        delay(100);
    }
    delay(500);
}

void loop() {
    // Phase 2: GPIO1 LOW for 2s — check D1 = 0V
    digitalWrite(PIN_RESET, LOW);
    digitalWrite(PIN_BOOTSEL, HIGH);
    delay(2000);

    // Phase 3: GPIO8 LOW for 2s — check D8 = 0V (LED ON)
    digitalWrite(PIN_RESET, HIGH);
    digitalWrite(PIN_BOOTSEL, LOW);
    delay(2000);

    // Phase 4: ALL HIGH for 2s — check all = 3.3V
    allHigh();
    delay(2000);
}
