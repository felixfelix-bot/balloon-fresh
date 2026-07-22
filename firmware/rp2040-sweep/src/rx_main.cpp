/*
 * rx_main.cpp — FLRC receiver using LR2021Raw
 * Fixed mode: continuous RX at 2600 kbps, 127-byte packets
 * Link verification before multi-mode sweep
 */
#ifdef ROLE_RX

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

    Serial1.println("\n=== FLRC RX FIXED 2600 (LR2021Raw) ===");
    Serial1.flush();

    radio.begin(PIN_SCK, PIN_MOSI, PIN_MISO, PIN_CS, PIN_BUSY, PIN_IRQ, PIN_RST);
    radio.initFLRC(2440.0, 2600, 12, 127, true);

    // Configure for RX
    radio.setDioIrq(9, IRQ_RX_DONE);
    radio.clearIrq();
    radio.clearRxFifo();
    radio.setRx();

    Serial1.println("RX LISTENING — continuous 2600 kbps");
    Serial1.flush();
}

void loop() {
    static uint32_t pktCount = 0;
    static uint32_t lastReport = millis();
    static int8_t lastRssi = 0;

    if (digitalRead(PIN_IRQ) == HIGH) {
        uint8_t buf[127];
        radio.readRxFifo(buf, 127);
        int8_t rssi = radio.getRSSI();

        // Check mode marker
        if (buf[0] == 0xAA) {
            pktCount++;
            lastRssi = rssi;

            uint32_t seq = ((uint32_t)buf[1] << 24) | ((uint32_t)buf[2] << 16) |
                           ((uint32_t)buf[3] << 8) | buf[4];

            if (pktCount <= 5 || pktCount % 100 == 0) {
                Serial1.printf("PKT#%lu seq=%lu RSSI=%d dBm\n",
                               (unsigned long)pktCount, (unsigned long)seq, rssi);
                Serial1.flush();
            }
        }

        // Re-arm
        radio.clearRxFifo();
        radio.clearErrors();
        radio.clearIrq();
        radio.setRx();

        digitalWrite(PIN_LED, pktCount & 1);
    }

    // Report every 2s
    if (millis() - lastReport > 2000) {
        if (pktCount == 0) {
            Serial1.println("RX: 0 pkts (no signal)");
        } else {
            Serial1.printf("RX: %lu pkts, last RSSI=%d dBm\n",
                           (unsigned long)pktCount, lastRssi);
        }
        Serial1.flush();
        lastReport = millis();
    }
}

#endif
