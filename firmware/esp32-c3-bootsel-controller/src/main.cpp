#include <Arduino.h>

/*
 * ESP32-C3 RP2040 BOOTSEL Controller
 *
 * Wiring (direct, no resistors):
 *   GPIO1  → RP2040 RESET button pad
 *   GPIO8  → RP2040 BOOTSEL button pad
 *   GND    → RP2040 GND (shared)
 *
 * ESP32-C3 SuperMini (303a:1001) note:
 *   USB JTAG serial receives commands but cannot output Arduino Serial.
 *   Send commands blind: printf 'b' > /dev/ttyACM1
 *
 * Commands (single byte, no newline needed):
 *   'b' = force BOOTSEL mode
 *   'r' = reset RP2040 (normal boot)
 *   'i' = invert BOOTSEL (hold low indefinitely — for in-circuit flashing)
 *   'o' = release BOOTSEL (set high)
 *
 * LED: GPIO8 has onboard LED (inverted on SuperMini).
 *   Blinks 3x on boot = firmware running.
 *   After 'b' command: RP2040 reboots into BOOTSEL.
 */

#define PIN_RESET   1
#define PIN_BOOTSEL 8

static void force_bootsel() {
    // 1. Hold BOOTSEL LOW
    digitalWrite(PIN_BOOTSEL, LOW);
    delay(50);

    // 2. Pulse RESET LOW → HIGH
    digitalWrite(PIN_RESET, LOW);
    delay(100);
    digitalWrite(PIN_RESET, HIGH);

    // 3. Hold BOOTSEL LOW during RP2040 boot window
    delay(500);

    // 4. Release BOOTSEL
    digitalWrite(PIN_BOOTSEL, HIGH);
}

static void reset_rp2040() {
    digitalWrite(PIN_RESET, LOW);
    delay(100);
    digitalWrite(PIN_RESET, HIGH);
}

void setup() {
    pinMode(PIN_RESET, OUTPUT);
    pinMode(PIN_BOOTSEL, OUTPUT);
    digitalWrite(PIN_RESET, HIGH);
    digitalWrite(PIN_BOOTSEL, HIGH);

    // Serial for command input (output may not show on USB JTAG)
    Serial.begin(115200);

    // LED blink = firmware alive
    pinMode(PIN_BOOTSEL, OUTPUT);
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_BOOTSEL, LOW);   // LED on (inverted)
        delay(150);
        digitalWrite(PIN_BOOTSEL, HIGH);  // LED off
        delay(150);
    }
}

void loop() {
    if (Serial.available()) {
        char c = Serial.read();
        switch (c) {
            case 'b':
                force_bootsel();
                break;
            case 'r':
                reset_rp2040();
                break;
            case 'i':
                // Hold BOOTSEL low indefinitely (for manual flash window)
                digitalWrite(PIN_BOOTSEL, LOW);
                break;
            case 'o':
                // Release BOOTSEL
                digitalWrite(PIN_BOOTSEL, HIGH);
                break;
            default:
                break;
        }
    }
    delay(1);
}
