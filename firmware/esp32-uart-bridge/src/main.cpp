/*
 * esp32-uart-bridge — UART → USB Serial forwarder for RP2040
 *
 * ESP32-C3 SuperMini (303a:1001 = USB JTAG/serial debug unit)
 *
 * Serial  = USB JTAG CDC (what the PC reads)
 * Serial1 = UART1 (remapped via GPIO matrix — avoids USB JTAG conflict)
 *
 * Wiring (verified 2026-07-15):
 *   RP2040 GP12 (UART0 TX) → ESP32 GPIO3 (UART1 RX)  [physical pin 3]
 *   RP2040 GP13 (UART0 RX) ← ESP32 GPIO4 (UART1 TX)  [physical pin 4]
 *   GND → GND
 */

#include <Arduino.h>

#define UART_BAUD 115200

void setup() {
    Serial.begin(115200);
    delay(300);

    // UART1 on GPIO3(RX) / GPIO4(TX) — VERIFIED WORKING 2026-07-15
    // RP2040 GP12 (TX) → ESP32 GPIO3 (UART1 RX)
    // RP2040 GP13 (RX) ← ESP32 GPIO4 (UART1 TX)
    Serial1.begin(UART_BAUD, SERIAL_8N1, GPIO_NUM_3, GPIO_NUM_4);

    delay(100);

    Serial.println();
    Serial.println("=== ESP32 UART Bridge v5 ===");
    Serial.println("UART1: RX=GPIO2 TX=GPIO3 @ 115200");
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

    // USB → RP2040 (forward commands like "RUN")
    while (Serial.available()) {
        Serial1.write(Serial.read());
    }

    // Heartbeat every 5 seconds
    if (millis() - lastHeartbeat > 5000) {
        lastHeartbeat = millis();
        Serial.printf("[BRIDGE ALIVE %lus]\n", millis() / 1000);
    }
}
