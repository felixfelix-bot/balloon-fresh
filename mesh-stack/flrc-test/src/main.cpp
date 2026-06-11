#include <Arduino.h>
#include "EspIdfHal.h"

#ifndef FLRC_PKT_SIZE
#define FLRC_PKT_SIZE 50
#endif
#ifndef LORA_PKT_SIZE
#define LORA_PKT_SIZE 50
#endif

#define LR2021_SCK  6
#define LR2021_MISO 2
#define LR2021_MOSI 7
#define LR2021_CS   10
#define LR2021_IRQ  5
#define LR2021_RST  3
#define LR2021_BUSY 4

static EspIdfHal hal(LR2021_SCK, LR2021_MISO, LR2021_MOSI);
static Module mod(&hal, LR2021_CS, LR2021_IRQ, LR2021_RST, LR2021_BUSY);
static LR2021 radio = LR2021(&mod);

static volatile bool rxFlag = false;
static uint32_t rxCount = 0;
static uint32_t rxErrors = 0;
static int16_t lastRssi = 0;
static float lastSnr = 0;
static uint32_t rxStartTime = 0;
static uint32_t rxLastTime = 0;

#if defined(FLRC_ROLE_TX) || defined(FLRC_ROLE_RX)

void rxISR(void) {
    rxFlag = true;
}

void setup() {
    Serial.begin(115200);
    delay(2000);
    Serial.println("=== FLRC Benchmark ===");

    int16_t state = radio.beginFLRC(
        FLRC_FREQ,
        FLRC_BR,
        FLRC_CR,
        FLRC_PWR,
        16,
        RADIOLIB_SHAPING_0_5,
        0.0f
    );

    if (state != RADIOLIB_ERR_NONE) {
        Serial.printf("FLRC init failed: %d\n", state);
        while (true) { delay(1000); }
    }

    radio.setPacketReceivedAction(rxISR);

    #ifdef FLRC_ROLE_TX
    Serial.printf("Mode: TX, Freq: %.1f MHz, BR: %d kbps, PWR: %d dBm\n",
                  FLRC_FREQ, FLRC_BR, FLRC_PWR);
    Serial.printf("Packets: %d, Size: %d bytes\n", FLRC_PKT_COUNT, FLRC_PKT_SIZE);
    Serial.println("Starting TX in 3 seconds...");
    delay(3000);

    uint8_t buf[FLRC_PKT_SIZE];
    uint32_t startMs = millis();
    uint32_t sentOk = 0;

    for (uint32_t i = 0; i < FLRC_PKT_COUNT; i++) {
        memset(buf, 0, FLRC_PKT_SIZE);
        buf[0] = (i >> 24) & 0xFF;
        buf[1] = (i >> 16) & 0xFF;
        buf[2] = (i >> 8) & 0xFF;
        buf[3] = i & 0xFF;

        state = radio.transmit(buf, FLRC_PKT_SIZE);
        if (state == RADIOLIB_ERR_NONE) {
            sentOk++;
        } else {
            Serial.printf("TX error at pkt %lu: %d\n", i, state);
        }

        if (i > 0 && i % 100 == 0) {
            Serial.printf("TX progress: %lu/%lu\n", i, (uint32_t)FLRC_PKT_COUNT);
        }
    }

    uint32_t elapsedMs = millis() - startMs;
    float elapsedSec = elapsedMs / 1000.0f;
    float throughput = (sentOk * FLRC_PKT_SIZE * 8.0f) / (elapsedSec * 1000.0f);

    Serial.println("=== TX RESULTS ===");
    Serial.printf("Packets sent: %lu / %d\n", sentOk, FLRC_PKT_COUNT);
    Serial.printf("Elapsed: %.2f sec\n", elapsedSec);
    Serial.printf("Effective throughput: %.1f kbps\n", throughput);
    Serial.printf("Time per packet: %.2f ms\n", elapsedMs / (float)sentOk);
    Serial.printf("Packet rate: %.1f pkt/sec\n", sentOk / elapsedSec);

    delay(1000);
    Serial.println("TX COMPLETE. Sending end marker...");
    uint8_t endMarker[] = {0xDE, 0xAD, 0xBE, 0xEF};
    radio.transmit(endMarker, 4);
    Serial.println("Done.");

    #else // FLRC_ROLE_RX
    Serial.printf("Mode: RX, Freq: %.1f MHz, BR: %d kbps\n", FLRC_FREQ, FLRC_BR);
    Serial.println("Waiting for packets...");

    rxStartTime = millis();
    radio.startReceive();

    while (true) {
        if (rxFlag) {
            rxFlag = false;
            int16_t len = radio.getPacketLength();
            if (len > 0) {
                uint8_t buf[256];
                state = radio.readData(buf, len);
                if (state == RADIOLIB_ERR_NONE) {
                    rxCount++;
                    lastRssi = radio.getRSSI();
                    lastSnr = radio.getSNR();
                    rxLastTime = millis();

                    if (len >= 4 && buf[0] == 0xDE && buf[1] == 0xAD &&
                        buf[2] == 0xBE && buf[3] == 0xEF) {
                        uint32_t elapsedMs = rxLastTime - rxStartTime;
                        float elapsedSec = elapsedMs / 1000.0f;
                        float throughput = (rxCount * FLRC_PKT_SIZE * 8.0f) / (elapsedSec * 1000.0f);

                        Serial.println("=== RX RESULTS ===");
                        Serial.printf("Packets received: %lu\n", rxCount);
                        Serial.printf("Errors: %lu\n", rxErrors);
                        Serial.printf("Elapsed: %.2f sec\n", elapsedSec);
                        Serial.printf("Effective throughput: %.1f kbps\n", throughput);
                        Serial.printf("Last RSSI: %d dBm, SNR: %.1f dB\n", lastRssi, lastSnr);
                        Serial.println("RX COMPLETE.");
                    } else {
                        if (rxCount % 100 == 0) {
                            Serial.printf("RX: %lu pkts, RSSI: %d, SNR: %.1f\n",
                                         rxCount, lastRssi, lastSnr);
                        }
                    }
                } else {
                    rxErrors++;
                }
            }
            radio.standby();
            radio.startReceive();
        }
        delay(1);
    }
    #endif
}

void loop() {
#ifdef FLRC_ROLE_TX
    delay(1000);
#endif
}

#elif defined(LORA_ROLE_TX) || defined(LORA_ROLE_RX)

void rxISR(void) {
    rxFlag = true;
}

void setup() {
    Serial.begin(115200);
    delay(2000);
    Serial.println("=== LoRa Benchmark ===");

    int16_t state = radio.begin(
        LORA_FREQ,
        LORA_BW,
        LORA_SF,
        LORA_CR,
        RADIOLIB_LR2021_LORA_SYNC_WORD_PRIVATE,
        LORA_PWR,
        8,
        0.0f
    );

    if (state != RADIOLIB_ERR_NONE) {
        Serial.printf("LoRa init failed: %d\n", state);
        while (true) { delay(1000); }
    }

    radio.setPacketReceivedAction(rxISR);

    #ifdef LORA_ROLE_TX
    Serial.printf("Mode: TX, Freq: %.1f MHz, SF: %d, BW: %.0f, PWR: %d dBm\n",
                  LORA_FREQ, LORA_SF, LORA_BW, LORA_PWR);
    Serial.printf("Packets: %d, Size: %d bytes\n", LORA_PKT_COUNT, LORA_PKT_SIZE);
    Serial.println("Starting TX in 3 seconds...");
    delay(3000);

    uint8_t buf[LORA_PKT_SIZE];
    uint32_t startMs = millis();
    uint32_t sentOk = 0;

    for (uint32_t i = 0; i < LORA_PKT_COUNT; i++) {
        memset(buf, 0, LORA_PKT_SIZE);
        buf[0] = (i >> 24) & 0xFF;
        buf[1] = (i >> 16) & 0xFF;
        buf[2] = (i >> 8) & 0xFF;
        buf[3] = i & 0xFF;

        state = radio.transmit(buf, LORA_PKT_SIZE);
        if (state == RADIOLIB_ERR_NONE) {
            sentOk++;
        } else {
            Serial.printf("TX error at pkt %lu: %d\n", i, state);
        }

        if (i > 0 && i % 10 == 0) {
            Serial.printf("TX progress: %lu/%lu\n", i, (uint32_t)LORA_PKT_COUNT);
        }
    }

    uint32_t elapsedMs = millis() - startMs;
    float elapsedSec = elapsedMs / 1000.0f;
    float throughput = (sentOk * LORA_PKT_SIZE * 8.0f) / (elapsedSec * 1000.0f);

    Serial.println("=== TX RESULTS ===");
    Serial.printf("Packets sent: %lu / %d\n", sentOk, LORA_PKT_COUNT);
    Serial.printf("Elapsed: %.2f sec\n", elapsedSec);
    Serial.printf("Effective throughput: %.1f kbps\n", throughput);
    Serial.printf("Time per packet: %.2f ms\n", elapsedMs / (float)sentOk);

    delay(1000);
    Serial.println("TX COMPLETE.");
    uint8_t endMarker[] = {0xDE, 0xAD, 0xBE, 0xEF};
    radio.transmit(endMarker, 4);

    #else // LORA_ROLE_RX
    Serial.printf("Mode: RX, Freq: %.1f MHz, SF: %d, BW: %.0f\n",
                  LORA_FREQ, LORA_SF, LORA_BW);
    Serial.println("Waiting for packets...");

    rxStartTime = millis();
    radio.startReceive();

    while (true) {
        if (rxFlag) {
            rxFlag = false;
            int16_t len = radio.getPacketLength();
            if (len > 0) {
                uint8_t buf[256];
                state = radio.readData(buf, len);
                if (state == RADIOLIB_ERR_NONE) {
                    rxCount++;
                    lastRssi = radio.getRSSI();
                    lastSnr = radio.getSNR();
                    rxLastTime = millis();

                    if (len >= 4 && buf[0] == 0xDE && buf[1] == 0xAD &&
                        buf[2] == 0xBE && buf[3] == 0xEF) {
                        uint32_t elapsedMs = rxLastTime - rxStartTime;
                        float elapsedSec = elapsedMs / 1000.0f;
                        float throughput = (rxCount * LORA_PKT_SIZE * 8.0f) / (elapsedSec * 1000.0f);

                        Serial.println("=== RX RESULTS ===");
                        Serial.printf("Packets received: %lu\n", rxCount);
                        Serial.printf("Errors: %lu\n", rxErrors);
                        Serial.printf("Elapsed: %.2f sec\n", elapsedSec);
                        Serial.printf("Effective throughput: %.1f kbps\n", throughput);
                        Serial.printf("Last RSSI: %d dBm, SNR: %.1f dB\n", lastRssi, lastSnr);
                        Serial.println("RX COMPLETE.");
                    } else {
                        if (rxCount % 10 == 0) {
                            Serial.printf("RX: %lu pkts, RSSI: %d, SNR: %.1f\n",
                                         rxCount, lastRssi, lastSnr);
                        }
                    }
                } else {
                    rxErrors++;
                }
            }
            radio.standby();
            radio.startReceive();
        }
        delay(1);
    }
    #endif
}

void loop() {
    #ifdef LORA_ROLE_TX
    delay(1000);
    #endif
}

#else
#error "Define FLRC_ROLE_TX, FLRC_ROLE_RX, LORA_ROLE_TX, or LORA_ROLE_RX"
#endif
