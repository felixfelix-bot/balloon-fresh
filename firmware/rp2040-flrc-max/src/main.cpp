/*
 * rp2040-flrc-max — Maximum FLRC Throughput Test
 * Target: 2600 kbps air rate (LR2021 FLRC maximum)
 *
 * Pin mapping matches rp2040 coprocessor:
 *   GP2=SCK, GP3=MOSI, GP4=MISO, GP5=CS, GP6=BUSY, GP7=IRQ, GP8=RST
 */

#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>

// ─── Pins ────────────────────────────────────────────────
#define LR2021_SCK   2
#define LR2021_MOSI  3
#define LR2021_MISO  4
#define LR2021_CS    5
#define LR2021_BUSY  6
#define LR2021_IRQ   7
#define LR2021_RST   8

// ─── FLRC MAX SPEED ──────────────────────────────────────
#define FLRC_FREQ     2440.0
#define FLRC_BR       2600
#define FLRC_CR       RADIOLIB_LR2021_FLRC_CR_1_0
#define FLRC_PWR      13
#define FLRC_PREAMBLE 12
#define FLRC_SHAPING  RADIOLIB_SHAPING_0_5

#define PKT_SIZE      255
#define PKT_COUNT     2000
#define RX_TIMEOUT_MS 30000

// ─── Radio ───────────────────────────────────────────────
Module radioMod(LR2021_CS, LR2021_IRQ, LR2021_RST, LR2021_BUSY);
LR2021 radio(&radioMod);

volatile bool rxFlag = false;
void rxISR() { rxFlag = true; }

char linebuf[256];

// Forward declarations
#ifdef ROLE_TX
void runTX();
#else
void runRX();
#endif

void setup() {
    Serial.begin(115200);
    delay(2000);

    Serial.println("=== RP2040 FLRC MAX TEST ===");
#ifdef ROLE_TX
    Serial.println("Mode: TX");
#else
    Serial.println("Mode: RX");
#endif

    // SPI0 default pins on RP2040 mbed: SCK=GP2, MOSI=GP3, MISO=GP4
    // These match our wiring — no custom pin config needed
    SPI.begin();

    Serial.print("Init LR2021...");
    int16_t state = radio.beginFLRC(FLRC_FREQ, FLRC_BR, FLRC_CR, FLRC_PWR,
                                     FLRC_PREAMBLE, FLRC_SHAPING);
    if (state != RADIOLIB_ERR_NONE) {
        snprintf(linebuf, sizeof(linebuf), " FAILED: %d", state);
        Serial.println(linebuf);
        Serial.println("Wiring: GP2=SCK GP3=MOSI GP4=MISO GP5=CS GP6=BUSY GP7=IRQ GP8=RST");
        while (true) { delay(1000); }
    }
    Serial.println(" OK");

    radio.setCRC(0);  // disable CRC for max speed

#ifdef ROLE_TX
    runTX();
#else
    runRX();
#endif
}

#ifdef ROLE_TX
void runTX() {
    snprintf(linebuf, sizeof(linebuf), "TX: %d packets x %d bytes", PKT_COUNT, PKT_SIZE);
    Serial.println(linebuf);
    Serial.println("Starting in 3 seconds...");
    delay(3000);

    uint8_t buf[PKT_SIZE];
    uint32_t sentOk = 0, sentErr = 0;
    uint32_t startMs = millis();

    for (uint32_t i = 0; i < PKT_COUNT; i++) {
        buf[0] = (i >> 24) & 0xFF;
        buf[1] = (i >> 16) & 0xFF;
        buf[2] = (i >> 8) & 0xFF;
        buf[3] = i & 0xFF;
        memset(buf + 4, 0xAA, PKT_SIZE - 4);

        int16_t result = radio.transmit(buf, PKT_SIZE);
        if (result == RADIOLIB_ERR_NONE) sentOk++;
        else sentErr++;

        if ((i + 1) % 500 == 0) {
            uint32_t elapsed = millis() - startMs;
            float kbps = (float)(i + 1) * PKT_SIZE * 8.0f / (float)elapsed;
            snprintf(linebuf, sizeof(linebuf), "TX %lu/%lu (%.1f kbps)",
                     (unsigned long)(i + 1), (unsigned long)PKT_COUNT, kbps);
            Serial.println(linebuf);
        }
    }

    uint32_t elapsedMs = millis() - startMs;
    float elapsedSec = elapsedMs / 1000.0f;
    float throughput = (sentOk * PKT_SIZE * 8.0f) / (elapsedSec * 1000.0f);

    Serial.println("=============================================");
    Serial.println("  TX RESULTS");
    Serial.println("=============================================");
    snprintf(linebuf, sizeof(linebuf), "  Sent OK:    %lu / %d", sentOk, PKT_COUNT);
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf), "  Errors:     %lu", sentErr);
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf), "  Elapsed:    %.2f sec", elapsedSec);
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf), "  Throughput: %.1f kbps", throughput);
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf), "  Per-pkt:    %.3f ms", elapsedMs / (float)sentOk);
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf), "  Pkt rate:   %.1f pkt/s", sentOk / elapsedSec);
    Serial.println(linebuf);
    Serial.println("=============================================");

    delay(100);
    uint8_t endMarker[] = {0xDE, 0xAD, 0xBE, 0xEF};
    radio.transmit(endMarker, 4);
    Serial.println("TX COMPLETE - end marker sent");
}
#endif

#ifndef ROLE_TX
void runRX() {
    snprintf(linebuf, sizeof(linebuf), "RX: Listening %d ms...", RX_TIMEOUT_MS);
    Serial.println(linebuf);
    radio.setPacketReceivedAction(rxISR);
    radio.startReceive();

    uint8_t buf[PKT_SIZE + 16];
    uint32_t rxCount = 0, rxErrors = 0;
    uint32_t firstSeq = 0xFFFFFFFF, lastSeq = 0;
    int16_t lastRssi = 0;
    uint32_t startMs = millis();
    bool gotEnd = false;

    while ((millis() - startMs) < RX_TIMEOUT_MS && !gotEnd) {
        if (rxFlag) {
            rxFlag = false;
            int16_t len = radio.getPacketLength();
            if (len > 0 && len <= (int)sizeof(buf)) {
                int16_t state = radio.readData(buf, len);
                if (state == RADIOLIB_ERR_NONE) {
                    if (len >= 4 && buf[0] == 0xDE && buf[1] == 0xAD &&
                        buf[2] == 0xBE && buf[3] == 0xEF) {
                        gotEnd = true;
                        break;
                    }
                    rxCount++;
                    lastRssi = radio.getRSSI();
                    if (len >= 4) {
                        uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                                       ((uint32_t)buf[2] << 8) | (uint32_t)buf[3];
                        if (firstSeq == 0xFFFFFFFF) firstSeq = seq;
                        lastSeq = seq;
                    }
                    if (rxCount % 500 == 0) {
                        uint32_t elapsed = millis() - startMs;
                        float kbps = (float)rxCount * PKT_SIZE * 8.0f / (float)elapsed;
                        snprintf(linebuf, sizeof(linebuf), "RX %lu pkts (%.1f kbps) RSSI=%d",
                                 rxCount, kbps, lastRssi);
                        Serial.println(linebuf);
                    }
                } else {
                    rxErrors++;
                }
            }
            radio.startReceive();
        }
    }

    uint32_t elapsedMs = millis() - startMs;
    float elapsedSec = elapsedMs / 1000.0f;
    float throughput = (rxCount * PKT_SIZE * 8.0f) / (elapsedSec * 1000.0f);
    long lost = (firstSeq != 0xFFFFFFFF) ? (long)(lastSeq - firstSeq + 1 - rxCount) : 0;

    Serial.println("=============================================");
    Serial.println("  RX RESULTS");
    Serial.println("=============================================");
    snprintf(linebuf, sizeof(linebuf), "  Received:   %lu", rxCount);
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf), "  Errors:     %lu", rxErrors);
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf), "  Seq range:  %lu - %lu", firstSeq, lastSeq);
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf), "  Lost:       %ld", lost);
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf), "  Elapsed:    %.2f sec", elapsedSec);
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf), "  Throughput: %.1f kbps", throughput);
    Serial.println(linebuf);
    snprintf(linebuf, sizeof(linebuf), "  RSSI:       %d dBm", lastRssi);
    Serial.println(linebuf);
    Serial.println("=============================================");
}
#endif

void loop() {}
