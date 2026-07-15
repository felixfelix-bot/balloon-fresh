/*
 * bootsel_ctrl.cpp — ESP32-C3 BOOTSEL Controller for RP2040
 *
 * AUTO-TRIGGERS RP2040 BOOTSEL on every boot. No serial input needed.
 *
 * Why no serial: ESP32-C3 SuperMini (303a:1001) uses USB JTAG/Serial.
 * Arduino Serial.available() never receives data on this interface.
 * Auto-trigger on boot is the reliable approach.
 *
 * Wiring (DIRECT WIRE, NO RESISTORS):
 *   GPIO1 (D1) → RP2040 RESET button pad (3V3 signal side)
 *   GPIO8 (D8) → RP2040 BOOTSEL button pad (3V3 signal side)
 *   GND        → GND
 *
 * After BOOTSEL trigger, RP2040 appears as RPI-RP2 mass storage device.
 * Copy UF2 firmware file to that drive. RP2040 reboots automatically.
 *
 * Build: make bootsel-flash PORT=/dev/ttyACMx
 */

#include <Arduino.h>

#define PIN_RESET   1   // ESP32 GPIO1 / D1 → RP2040 RESET button pad
#define PIN_BOOTSEL 8   // ESP32 GPIO8 / D8 → RP2040 BOOTSEL button pad

static void trigger_bootsel() {
    // 1. Hold BOOTSEL LOW (GP0 LOW during boot = bootloader mode)
    digitalWrite(PIN_BOOTSEL, LOW);
    delay(50);

    // 2. Pulse RESET LOW (reset the RP2040 while BOOTSEL is held)
    digitalWrite(PIN_RESET, LOW);
    delay(100);
    digitalWrite(PIN_RESET, HIGH);

    // 3. Hold BOOTSEL LOW while RP2040 boots
    delay(500);

    // 4. Release BOOTSEL
    digitalWrite(PIN_BOOTSEL, HIGH);
}

void setup() {
    // Configure both pins as output, start HIGH (idle)
    pinMode(PIN_RESET, OUTPUT);
    pinMode(PIN_BOOTSEL, OUTPUT);
    digitalWrite(PIN_RESET, HIGH);
    digitalWrite(PIN_BOOTSEL, HIGH);

    // Brief delay to let power rails settle
    delay(100);

    // AUTO-TRIGGER BOOTSEL on every boot
    trigger_bootsel();
}

void loop() {
    // Heartbeat blink via onboard LED (GPIO8, inverted on SuperMini)
    digitalWrite(PIN_BOOTSEL, LOW);   // LED ON
    delay(100);
    digitalWrite(PIN_BOOTSEL, HIGH);  // LED OFF
    delay(900);
}
