/*
 * bootsel_loop.cpp — Loop-based BOOTSEL trigger
 * Fires every 5 seconds. Multiple chances to catch RP2040 reset.
 */

#include <Arduino.h>

#define PIN_RESET   1   // ESP32 GPIO1 → RP2040 RESET
#define PIN_BOOTSEL 8   // ESP32 GPIO8 → RP2040 GP0

void trigger_bootsel() {
    digitalWrite(PIN_BOOTSEL, LOW);
    delay(50);
    digitalWrite(PIN_RESET, LOW);
    delay(100);
    digitalWrite(PIN_RESET, HIGH);
    delay(500);
    digitalWrite(PIN_BOOTSEL, HIGH);
}

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("BOOTSEL_LOOP_START");
    
    pinMode(PIN_RESET, OUTPUT);
    pinMode(PIN_BOOTSEL, OUTPUT);
    digitalWrite(PIN_RESET, HIGH);
    digitalWrite(PIN_BOOTSEL, HIGH);
    delay(200);
}

void loop() {
    Serial.println("BOOTSEL_TRIGGER");
    Serial.flush();
    trigger_bootsel();
    delay(5000);
}
