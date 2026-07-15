/*
 * esp32-uart-bridge — UART → USB CDC forwarder
 *
 * Reads UART1 from RP2040, forwards every byte to ESP32-C3 native USB CDC.
 * This bypasses the RP2040's dead USB CDC (RadioLib beginFLRC kills TinyUSB).
 *
 * Wiring:
 *   RP2040 GP12 (UART0 TX) → ESP32 GPIO1 (UART1 RX, pin D1)
 *   RP2040 GP13 (UART0 RX) ← ESP32 GPIO0 (UART1 TX, pin D0)
 *   GND → GND
 *
 * Also forwards USB→UART so host can send commands to the RP2040
 * (e.g. "RUN\n" to start receiving).
 *
 * Board: ESP32-C3 SuperMini (native USB-C, USB CDC = Serial)
 */

#include <Arduino.h>

#define UART_RX_PIN  1   // GPIO1 — connected to RP2040 GP12 (TX)
#define UART_TX_PIN  0   // GPIO0 — connected to RP2040 GP13 (RX)

void setup() {
    // Native USB CDC — this is what the host computer sees
    Serial.begin(115200);

    // UART1 on our pins — reads from RP2040
    Serial1.begin(115200, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);

    delay(100);
    Serial.println();
    Serial.println("=== ESP32 UART Bridge ===");
    Serial.println("RP2040 UART → USB CDC forwarder");
    Serial.println("Waiting for data from RP2040...");
}

void loop() {
    // RP2040 → USB (forward telemetry/results)
    while (Serial1.available()) {
        // Read in chunks for efficiency
        uint8_t buf[256];
        int n = Serial1.readBytes(buf, min((int)Serial1.available(), 256));
        if (n > 0) {
            Serial.write(buf, n);
        }
    }

    // USB → RP2040 (forward commands like "RUN")
    while (Serial.available()) {
        Serial1.write(Serial.read());
    }
}
