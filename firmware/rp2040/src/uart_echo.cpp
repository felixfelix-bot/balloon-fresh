#include <Arduino.h>

/*
 * UART Bridge Echo — earlephilhower core
 * GP12 (UART0 TX) → ESP32 GPIO1 (RX)
 * GP13 (UART0 RX) ← ESP32 GPIO0 (TX)
 *
 * Heartbeat in loop() ensures host sees output regardless of connect timing.
 */

void setup() {
    Serial.begin(115200);
    Serial1.setTX(12);
    Serial1.setRX(13);
    Serial1.begin(115200);

    // LED blink
    pinMode(25, OUTPUT);
    for (int i = 0; i < 5; i++) {
        digitalWrite(25, HIGH); delay(100);
        digitalWrite(25, LOW);  delay(100);
    }
}

unsigned long lastHeartbeat = 0;

void loop() {
    // Heartbeat every 2 seconds — host sees this on connect
    if (millis() - lastHeartbeat > 2000) {
        lastHeartbeat = millis();
        Serial.println("UART_ECHO_READY GP12=TX GP13=RX 115200baud");
        Serial1.println("UART_LINK_OK");
    }

    // UART (GP13) → USB
    while (Serial1.available()) {
        char c = Serial1.read();
        Serial.print(c);
    }

    // USB → UART (GP12)
    while (Serial.available()) {
        char c = Serial.read();
        Serial1.print(c);
    }

    delay(1);
}
