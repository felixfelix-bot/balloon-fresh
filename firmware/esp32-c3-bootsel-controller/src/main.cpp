/*
 * ESP32-C3 RP2040 BOOTSEL Controller v2 (FIXED)
 * 
 * Correct RP2040 BOOTSEL logic:
 *   GP0 LOW during reset  → USB bootloader mode (BOOTSEL)
 *   GP0 HIGH during reset → boot from flash (normal)
 *   RUN LOW for ≥1µs      → global reset
 *
 * Serial commands (115200 baud, newline-terminated):
 *   BOOTSEL  - force RP2040 into USB bootloader mode
 *   RESET    - reset RP2040 to run flash firmware  
 *   PINS     - report current pin assignment
 *   SETPINS <run> <bootsel> - reconfigure GPIO pins at runtime
 *   STATUS   - report GPIO states
 *   HELP     - list commands
 *
 * Default pins (per balloon-flight-test-guide.md):
 *   RUN_PIN = GPIO2 → 1kΩ → RP2040 RUN (pin 30)
 *   BOOTSEL_PIN = GPIO8 → 1kΩ → RP2040 GP0 (pin 1)
 */

#include <Arduino.h>

// Pin assignment (configurable via SETPINS command)
int RUN_PIN = 2;
int BOOTSEL_PIN = 8;

void configure_pins() {
    pinMode(RUN_PIN, OUTPUT);
    pinMode(BOOTSEL_PIN, OUTPUT);
    // Idle: RUN HIGH (not reset), BOOTSEL HIGH (not bootloader)
    digitalWrite(RUN_PIN, HIGH);
    digitalWrite(BOOTSEL_PIN, HIGH);
}

void pulse_reset(int hold_ms) {
    digitalWrite(RUN_PIN, LOW);
    delay(hold_ms);
    digitalWrite(RUN_PIN, HIGH);
}

void force_bootsel() {
    // 1. Drive GP0 LOW (bootloader mode)
    digitalWrite(BOOTSEL_PIN, LOW);
    delay(5);
    // 2. Pulse RUN LOW (reset RP2040 while GP0 is LOW)
    pulse_reset(10);
    // 3. Hold GP0 LOW for RP2040 to sample BOOTSEL
    delay(100);
    // 4. Release GP0
    digitalWrite(BOOTSEL_PIN, HIGH);
    Serial.println("OK BOOTSEL");
}

void reset_to_firmware() {
    digitalWrite(BOOTSEL_PIN, HIGH);
    delay(2);
    pulse_reset(10);
    delay(50);
    Serial.println("OK RESET");
}

void setup() {
    Serial.begin(115200);
    delay(200);
    configure_pins();
    Serial.println("=== ESP32 RP2040 BOOTSEL Controller v2 ===");
    Serial.printf("RUN=GPIO%d BOOTSEL=GPIO%d\n", RUN_PIN, BOOTSEL_PIN);
    Serial.println("Ready. Send HELP for commands.");
}

void loop() {
    if (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        cmd.toUpperCase();

        if (cmd == "BOOTSEL") {
            force_bootsel();
        } else if (cmd == "RESET") {
            reset_to_firmware();
        } else if (cmd == "PINS") {
            Serial.printf("PINS RUN=GPIO%d BOOTSEL=GPIO%d\n", RUN_PIN, BOOTSEL_PIN);
        } else if (cmd == "STATUS") {
            Serial.printf("STATUS RUN_PIN=%d(%s) BOOTSEL_PIN=%d(%s)\n",
                          RUN_PIN, digitalRead(RUN_PIN) ? "HIGH" : "LOW",
                          BOOTSEL_PIN, digitalRead(BOOTSEL_PIN) ? "HIGH" : "LOW");
        } else if (cmd == "HELP") {
            Serial.println("COMMANDS: BOOTSEL RESET PINS SETPINS<run><bootsel> STATUS HELP");
        } else if (cmd.startsWith("SETPINS")) {
            int space1 = cmd.indexOf(' ');
            int space2 = cmd.indexOf(' ', space1 + 1);
            if (space1 > 0 && space2 > 0) {
                int nr = cmd.substring(space1 + 1, space2).toInt();
                int nb = cmd.substring(space2 + 1).toInt();
                if (nr >= 0 && nr <= 21 && nb >= 0 && nb <= 21) {
                    digitalWrite(RUN_PIN, HIGH);
                    digitalWrite(BOOTSEL_PIN, HIGH);
                    RUN_PIN = nr;
                    BOOTSEL_PIN = nb;
                    configure_pins();
                    Serial.printf("OK SETPINS RUN=GPIO%d BOOTSEL=GPIO%d\n", RUN_PIN, BOOTSEL_PIN);
                } else {
                    Serial.println("ERR pin range 0-21");
                }
            } else {
                Serial.println("ERR usage: SETPINS <run> <bootsel>");
            }
        } else if (cmd.length() > 0) {
            Serial.printf("ERR unknown: %s\n", cmd.c_str());
        }
    }
    delay(10);
}
