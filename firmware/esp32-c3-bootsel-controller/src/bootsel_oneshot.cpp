#include <Arduino.h>

/*
 * ESP32-C3 RP2040 BOOTSEL Controller — One-Shot Trigger
 *
 * Triggers BOOTSEL ONCE on power-up, then idles forever.
 * This lets us flash RX firmware to the RP2040 without physical access.
 *
 * Wiring (same as diagnostic loop version):
 *   GPIO1  → RP2040 RUN (RESET)  [D1]
 *   GPIO8  → RP2040 GP0 (BOOTSEL) [D8/NeoPixel]
 *   GND    → RP2040 GND
 *
 * After BOOTSEL trigger: reflash this ESP32 as UART bridge.
 */

#define PIN_RESET   1
#define PIN_BOOTSEL 8

void setup() {
    pinMode(PIN_RESET, OUTPUT);
    pinMode(PIN_BOOTSEL, OUTPUT);
    
    // Start with both HIGH (RP2040 running normally)
    digitalWrite(PIN_RESET, HIGH);
    digitalWrite(PIN_BOOTSEL, HIGH);
    delay(100);
    
    // --- BOOTSEL trigger sequence ---
    // 1. Hold BOOTSEL pin LOW (tells RP2040 to enter bootloader on next reset)
    digitalWrite(PIN_BOOTSEL, LOW);
    delay(50);
    
    // 2. Pulse RESET LOW (reboot the RP2040)
    digitalWrite(PIN_RESET, LOW);
    delay(100);
    
    // 3. Release RESET — RP2040 reboots, reads BOOTSEL=LOW, enters BOOTSEL
    digitalWrite(PIN_RESET, HIGH);
    delay(500);
    
    // 4. Release BOOTSEL pin (RP2040 is now in BOOTSEL, stays there until UF2 written)
    digitalWrite(PIN_BOOTSEL, HIGH);
    
    // Blink onboard LED to indicate done
    for (int i = 0; i < 10; i++) {
        digitalWrite(PIN_BOOTSEL, LOW); delay(100);
        digitalWrite(PIN_BOOTSEL, HIGH); delay(100);
    }
    
    // Now idle — RP2040 is in BOOTSEL mode waiting for UF2
    digitalWrite(PIN_BOOTSEL, HIGH);
    digitalWrite(PIN_RESET, HIGH);
}

void loop() {
    // Nothing — one-shot already done in setup()
    delay(10000);
}
