#include <Arduino.h>

/*
 * ESP32-C3 RP2040 BOOTSEL Controller v5
 *
 * ROOT CAUSE: One-shot trigger in setup() fails after esptool hard_reset.
 * The ESP32's first boot after esptool is unstable for GPIO.
 * Loop-based triggering works reliably (proven by diagnostic 2026-07-15).
 *
 * STRATEGY: Trigger BOOTSEL 3 times in loop() with 3-second gaps.
 * First attempt may miss (ESP32 boot unstable).
 * Second/third attempt always succeeds.
 * After 3 attempts: idle forever (don't re-trigger after UF2 flash).
 *
 * Wiring:
 *   GPIO1  → RP2040 RUN (RESET)
 *   GPIO8  → RP2040 GP0 (BOOTSEL)
 *   GND    → RP2040 GND
 */

#define PIN_RESET   1
#define PIN_BOOTSEL 8

static int trigger_count = 0;
static unsigned long next_trigger = 0;

void force_bootsel() {
    digitalWrite(PIN_BOOTSEL, LOW);
    delay(50);
    digitalWrite(PIN_RESET, LOW);
    delay(100);
    digitalWrite(PIN_RESET, HIGH);
    delay(500);
    digitalWrite(PIN_BOOTSEL, HIGH);
}

void setup() {
    pinMode(PIN_RESET, OUTPUT);
    pinMode(PIN_BOOTSEL, OUTPUT);
    digitalWrite(PIN_RESET, HIGH);
    digitalWrite(PIN_BOOTSEL, HIGH);

    // Initial delay — let ESP32 stabilize after esptool reset
    delay(1000);
    next_trigger = millis();
}

void loop() {
    if (trigger_count < 3 && millis() >= next_trigger) {
        // LED on during trigger
        digitalWrite(PIN_BOOTSEL, LOW);

        force_bootsel();
        trigger_count++;

        // LED blink = trigger done
        for (int i = 0; i < 3; i++) {
            digitalWrite(PIN_BOOTSEL, HIGH);
            delay(150);
            digitalWrite(PIN_BOOTSEL, LOW);
            delay(150);
        }
        digitalWrite(PIN_BOOTSEL, HIGH);

        // Next attempt in 3 seconds
        next_trigger = millis() + 3000;
    }

    delay(10);
}
