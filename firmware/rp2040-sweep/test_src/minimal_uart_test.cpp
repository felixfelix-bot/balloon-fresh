/*
 * minimal_uart_test.cpp — prints to Serial1 every second, no SPI
 * If this doesn't show through bridge, the UART wiring is broken
 */
#include <Arduino.h>

#define PIN_LED     25
#define PIN_UART_TX 12
#define PIN_UART_RX 13

void setup() {
    Serial.begin(115200);
    Serial1.setRX(PIN_UART_RX);
    Serial1.setTX(PIN_UART_TX);
    Serial1.begin(115200);

    pinMode(PIN_LED, OUTPUT);

    delay(3000);

    Serial1.println("\n=== MINIMAL UART TEST ===");
    Serial1.println("If you see this, Serial1 works.");
    Serial1.flush();
}

void loop() {
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
    Serial1.println("UART heartbeat");
    Serial1.flush();
    delay(1000);
}
