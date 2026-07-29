/*
 * tx_main.cpp — FLRC transmitter using LR2021Raw
 * Fixed mode: continuous TX at 2600 kbps, 127-byte packets
 * Link verification before multi-mode sweep
 */
#ifdef ROLE_TX

#include <Arduino.h>
#include "LR2021Raw.h"
#include "sweep_config.h"

#define PIN_SCK     2
#define PIN_MOSI    3
#define PIN_MISO    4
#define PIN_CS      5
#define PIN_BUSY    6
#define PIN_IRQ     7
#define PIN_RST     8
#define PIN_UART_TX 12
#define PIN_UART_RX 13
#define PIN_LED     25

LR2021Raw radio;

void setup() {
    Serial.begin(115200);
    Serial1.setRX(PIN_UART_RX);
    Serial1.setTX(PIN_UART_TX);
    Serial1.begin(115200);
    pinMode(PIN_LED, OUTPUT);
    delay(2000);

    Serial1.println("\n=== FLRC TX FIXED 2600 (LR2021Raw) ===");
    Serial1.flush();

    radio.begin(PIN_SCK, PIN_MOSI, PIN_MISO, PIN_CS, PIN_BUSY, PIN_IRQ, PIN_RST);
    radio.initFLRC(2440.0, 2600, 12, 127, true);

    Serial1.println("TX READY — continuous 2600 kbps");
    Serial1.flush();
    delay(1000);
}

void loop() {
    static uint32_t pktCount = 0;
    static uint32_t failCount = 0;
    static uint32_t lastReport = millis();

    uint8_t pkt[127];
    pkt[0] = 0xAA; // mode marker
    pkt[1] = (pktCount >> 24) & 0xFF;
    pkt[2] = (pktCount >> 16) & 0xFF;
    pkt[3] = (pktCount >> 8) & 0xFF;
    pkt[4] = pktCount & 0xFF;
    for (int j = 5; j < 127; j++) pkt[j] = (uint8_t)(j & 0xFF);

    bool ok = radio.transmit(pkt, 127, 100000);
    if (ok) pktCount++;
    else failCount++;

    digitalWrite(PIN_LED, pktCount & 1);

    // Report every 2s
    if (millis() - lastReport > 2000) {
        Serial1.printf("TX: %lu pkts, %lu fails\n",
                       (unsigned long)pktCount, (unsigned long)failCount);
        Serial1.flush();
        lastReport = millis();
    }
}

#endif
