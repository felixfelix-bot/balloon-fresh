/*
 * esp32-uart-bridge — UART → USB Serial forwarder for RP2040
 *
 * ESP32-C3 SuperMini (303a:1001 = USB JTAG/serial debug unit)
 *
 * Serial  = USB JTAG CDC (what the PC reads)
 * Serial1 = UART1 (remapped to GPIO0/GPIO1 — the soldered wires)
 *
 * Wiring (already soldered):
 *   RP2040 GP12 (UART0 TX) → ESP32 GPIO0 (D0, UART1 RX)
 *   RP2040 GP13 (UART0 RX) ← ESP32 GPIO1 (D1, UART1 TX)
 *   GND → GND
 *
 * IMPORTANT: We use UART1 (Serial1), NOT UART0 (Serial0).
 * UART0 conflicts with USB CDC on ESP32-C3.
 * UART1 can be remapped to any pin via the GPIO matrix.
 *
 * Build:  pio run -e esp32-uart-bridge
 * Flash:  make esp32-flash-bridge PORT=/dev/ttyACMX
 */

#include <Arduino.h>

#define UART_BAUD 115200

void setup() {
    // USB JTAG CDC — what the PC reads
    Serial.begin(115200);
    delay(300);

    // UART1 on GPIO1(RX)/GPIO0(TX) — the soldered wires
    // RP2040 GP12 (TX) → ESP32 GPIO1 (UART1 RX)
    // RP2040 GP13 (RX) ← ESP32 GPIO0 (UART1 TX)
    // Serial1.begin(baud, config, rxPin, txPin)
    Serial1.begin(UART_BAUD, SERIAL_8N1, GPIO_NUM_1, GPIO_NUM_0);

    delay(100);

    Serial.println();
    Serial.println("=== ESP32 UART Bridge v4 ===");
    Serial.println("UART1: RX=GPIO1 TX=GPIO0 @ 115200");
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
