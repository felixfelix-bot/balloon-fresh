/*
 * esp32-uart-bridge — UART → USB Serial forwarder for RP2040
 *
 * ESP32-C3 SuperMini (USB JTAG serial debug unit, 303a:1001)
 * 
 * Serial = USB JTAG serial (what the PC sees)
 * Hardware UART0 = GPIO1(TX) / GPIO0(RX) by default
 *
 * Wiring:
 *   RP2040 GP12 (UART0 TX) → ESP32 GPIO0 (UART0 RX, D0)
 *   RP2040 GP13 (UART0 RX) ← ESP32 GPIO1 (UART0 TX, D1)  
 *   GND → GND
 *
 * NOTE: GPIO0 is a strapping pin but UART RX is input-only, safe.
 */

#include <Arduino.h>

#define UART_BAUD 115200

// On ESP32-C3 with Arduino core:
// Serial = USB JTAG CDC
// We use HardwareSerial on UART0 with custom pins
// GPIO0 = RX (from RP2040 TX)
// GPIO1 = TX (to RP2040 RX)

HardwareSerial UartBridge(0);  // UART0

void setup() {
    // USB JTAG serial — what the PC reads
    Serial.begin(115200);
    
    // Small delay for USB to stabilize
    delay(200);
    
    // Init UART0 on GPIO0(RX)/GPIO1(TX)
    // ESP32 Arduino: Serial0(rx, tx) or begin(baud, config, rx, tx)
    UartBridge.begin(UART_BAUD, SERIAL_8N1, 0, 1);  // RX=GPIO0, TX=GPIO1
    
    delay(100);
    
    // Banner — proves bridge is alive even if RP2040 sends nothing
    Serial.println();
    Serial.println("=== ESP32 UART Bridge v2 ===");
    Serial.println("UART0: RX=GPIO0 TX=GPIO1 @ 115200");
    Serial.println("Listening for RP2040 data...");
    
    // Blink: proves we got past setup()
    Serial.println("[BOOT OK]");
}

unsigned long lastHeartbeat = 0;

void loop() {
    // RP2040 UART → USB Serial
    int avail = UartBridge.available();
    if (avail > 0) {
        uint8_t buf[256];
        int n = UartBridge.readBytes(buf, min(avail, 256));
        if (n > 0) {
            Serial.write(buf, n);
        }
    }
    
    // USB → RP2040 (forward commands)
    while (Serial.available()) {
        UartBridge.write(Serial.read());
    }
    
    // Heartbeat every 5 seconds — proves bridge is running
    if (millis() - lastHeartbeat > 5000) {
        lastHeartbeat = millis();
        Serial.printf("[BRIDGE ALIVE %lus]\n", millis() / 1000);
    }
}
