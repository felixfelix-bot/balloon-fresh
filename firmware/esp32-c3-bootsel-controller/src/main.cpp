#include <Arduino.h>

// AUTO BOOTSEL TEST — no serial commands needed
// On boot: waits 3s (LED on), then does BOOTSEL sequence
// D1 (GPIO1) → RP2040 RESET button
// D8 (GPIO8) → RP2040 BOOTSEL button

#define PIN_RESET   1
#define PIN_BOOTSEL 8

void setup() {
    // Start idle
    pinMode(PIN_RESET, OUTPUT);
    pinMode(PIN_BOOTSEL, OUTPUT);
    digitalWrite(PIN_RESET, HIGH);
    digitalWrite(PIN_BOOTSEL, HIGH);
    
    // Wait 3 seconds for observer to be ready
    delay(3000);
    
    // BOOTSEL sequence:
    // 1. Hold BOOTSEL LOW
    digitalWrite(PIN_BOOTSEL, LOW);
    delay(50);
    
    // 2. Pulse RESET LOW (100ms)
    digitalWrite(PIN_RESET, LOW);
    delay(100);
    digitalWrite(PIN_RESET, HIGH);
    
    // 3. Hold BOOTSEL LOW while RP2040 boots (500ms)
    delay(500);
    
    // 4. Release BOOTSEL
    digitalWrite(PIN_BOOTSEL, HIGH);
    
    // Done. RP2040 should now be in bootloader mode.
}

void loop() {
    // Nothing — one-shot test
    delay(1000);
}
