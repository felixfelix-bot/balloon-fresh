/*
 * esp32-uart-bridge-v2 — UART Bridge + BOOTSEL Controller
 * 
 * Combines UART forwarding with BOOTSEL trigger via serial command.
 * 
 * Commands (via USB serial):
 *   BOOTSEL  — trigger RP2040 BOOTSEL mode (hold BOOTSEL pin + reset)
 *   RESET    — reset RP2040 only (no BOOTSEL)
 * 
 * Wiring:
 *   UART:  RP2040 GP12 → ESP32 GPIO3 (RX), RP2040 GP13 ← ESP32 GPIO2 (TX)
 *   BOOT:  ESP32 GPIO8 → RP2040 GP0 (BOOTSEL)
 *   RESET: ESP32 GPIO1 → RP2040 RUN (RESET)
 *   GND → GND
 */

#include <Arduino.h>

#define UART_BAUD 115200
#define PIN_RESET   1
#define PIN_BOOTSEL 8

void triggerBootsel() {
    Serial.println("[BOOTSEL TRIGGER]");
    
    // Hold BOOTSEL pin LOW (tells RP2040 to enter bootloader on next reset)
    pinMode(PIN_BOOTSEL, OUTPUT);
    digitalWrite(PIN_BOOTSEL, LOW);
    
    // Reset RP2040
    pinMode(PIN_RESET, OUTPUT);
    digitalWrite(PIN_RESET, LOW);
    delay(100);
    digitalWrite(PIN_RESET, HIGH);
    
    // Hold BOOTSEL for 500ms more while RP2040 boots
    delay(500);
    digitalWrite(PIN_BOOTSEL, HIGH);
    
    // Wait for RP2040 to enter BOOTSEL mode
    delay(500);
    Serial.println("[BOOTSEL DONE — RP2040 in bootloader mode]");
}

void resetRP2040() {
    Serial.println("[RESET RP2040]");
    pinMode(PIN_RESET, OUTPUT);
    digitalWrite(PIN_RESET, LOW);
    delay(100);
    digitalWrite(PIN_RESET, HIGH);
    delay(500);
    Serial.println("[RESET DONE]");
}

String inputBuf = "";

void setup() {
    Serial.begin(115200);
    delay(300);

    // UART1: GPIO3=RX (from RP2040 GP12 TX), GPIO2=TX (to RP2040 GP13 RX)
    Serial1.begin(UART_BAUD, SERIAL_8N1, GPIO_NUM_3, GPIO_NUM_2);
    delay(100);

    // Control pins — idle HIGH
    pinMode(PIN_RESET, OUTPUT);
    pinMode(PIN_BOOTSEL, OUTPUT);
    digitalWrite(PIN_RESET, HIGH);
    digitalWrite(PIN_BOOTSEL, HIGH);

    Serial.println();
    Serial.println("=== ESP32 UART Bridge v7 (BOOTSEL) ===");
    Serial.println("Commands: BOOTSEL  RESET");
    Serial.println("[BOOT OK]");
}

unsigned long lastHeartbeat = 0;

void loop() {
    // RP2040 UART → USB Serial
    int avail = Serial1.available();
    if (avail > 0) {
        uint8_t buf[256];
        int n = Serial1.readBytes(buf, min(avail, (int)sizeof(buf)));
        if (n > 0) {
            Serial.write(buf, n);
        }
    }

    // USB → RP2040 + command processing
    while (Serial.available()) {
        char c = Serial.read();
        
        // Check for commands (newline-terminated)
        if (c == '\n' || c == '\r') {
            if (inputBuf.length() > 0) {
                inputBuf.trim();
                inputBuf.toUpperCase();
                
                if (inputBuf == "BOOTSEL") {
                    triggerBootsel();
                } else if (inputBuf == "RESET") {
                    resetRP2040();
                } else {
                    // Forward to RP2040 as serial command
                    Serial1.println(inputBuf);
                }
                inputBuf = "";
            }
        } else {
            inputBuf += c;
            // Also forward raw to RP2040 (for non-command data)
            Serial1.write(c);
        }
    }

    // Heartbeat every 5 seconds
    if (millis() - lastHeartbeat > 5000) {
        lastHeartbeat = millis();
        Serial.printf("[BRIDGE ALIVE %lus]\n", millis() / 1000);
    }
    
    yield();  // Feed watchdog
}
