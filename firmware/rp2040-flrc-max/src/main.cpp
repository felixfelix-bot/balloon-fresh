/*
 * rp2040-flrc-max — Continuous FLRC Range Logger + TX
 * Target: 2600 kbps air rate (LR2021 FLRC maximum)
 * RX: Continuous logging with fixed RSSI via getFlrcPacketStatus
 * TX: Continuous transmission for range testing
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

// earlephilhower: explicit SPI0 on our pins
static SPIClassRP2040 spiRf(spi0, LR2021_MISO, LR2021_CS, LR2021_SCK, LR2021_MOSI);
static SPISettings spiSettings(16000000, MSBFIRST, SPI_MODE0);

// ─── FLRC CONFIG ─────────────────────────────────────────
#define FLRC_FREQ     2440.0
#define FLRC_BR       2600
#define FLRC_CR       RADIOLIB_LR2021_FLRC_CR_1_0
#define FLRC_PWR      13
#define FLRC_PREAMBLE 12
#define FLRC_SHAPING  RADIOLIB_SHAPING_0_5

#define PKT_SIZE      127

// ─── Radio ───────────────────────────────────────────────
Module radioMod(LR2021_CS, LR2021_IRQ, LR2021_RST, LR2021_BUSY, spiRf, spiSettings);
LR2021 radio(&radioMod);

volatile bool rxFlag = false;
void rxISR() { rxFlag = true; }

// Dual output: USB Serial + UART Serial1 (to ESP32 bridge)
// Serial1 works even when USB CDC dies during SPI
#define DUAL_PRINT(s)    do { Serial1.print(s); } while(0)
#define DUAL_PRINTLN(s)  do { Serial1.println(s); } while(0)

char linebuf[256];

void setup() {
    Serial.begin(115200);
    // Serial1 remapped to GP12(TX)/GP13(RX) for ESP32 UART bridge
    // Default is GP0/GP1 — MUST remap or bridge gets nothing
    Serial1.setTX(12);
    Serial1.setRX(13);
    Serial1.begin(115200);
    delay(2000);

    DUAL_PRINTLN("=== RP2040 FLRC RANGE LOGGER ===");
#ifdef ROLE_TX
    DUAL_PRINTLN("Mode: TX (continuous)");
#else
    DUAL_PRINTLN("Mode: RX (continuous)");
#endif

    spiRf.begin();
    radio.irqDioNum = 9;

    DUAL_PRINT("Init LR2021 FLRC...");
    int16_t state = radio.beginFLRC(FLRC_FREQ, FLRC_BR, FLRC_CR, FLRC_PWR,
                                     FLRC_PREAMBLE, FLRC_SHAPING);
    if (state != RADIOLIB_ERR_NONE) {
        snprintf(linebuf, sizeof(linebuf), " FAILED: %d", state);
        DUAL_PRINTLN(linebuf);
        while (true) { delay(1000); }
    }
    DUAL_PRINTLN(" OK");
    radio.setCRC(0);

#ifdef ROLE_TX
    // TX mode handled in loop()
    DUAL_PRINTLN("TX ready");
#else
    radio.setPacketReceivedAction(rxISR);
    radio.startReceive();
    DUAL_PRINTLN("RX listening (continuous)");
#endif
}

#ifdef ROLE_TX
// ─── TX: Continuous transmission ─────────────────────────
void loop() {
    static uint32_t seq = 0;
    static uint32_t startMs = millis();
    static uint32_t sentOk = 0;

    uint8_t buf[PKT_SIZE];
    buf[0] = (seq >> 24) & 0xFF;
    buf[1] = (seq >> 16) & 0xFF;
    buf[2] = (seq >> 8) & 0xFF;
    buf[3] = seq & 0xFF;
    memset(buf + 4, 0xAA, PKT_SIZE - 4);

    int16_t result = radio.transmit(buf, PKT_SIZE);
    if (result == RADIOLIB_ERR_NONE) {
        sentOk++;
    }
    seq++;

    if (seq % 1000 == 0) {
        uint32_t elapsed = millis() - startMs;
        float kbps = (float)sentOk * PKT_SIZE * 8.0f / (float)elapsed;
        snprintf(linebuf, sizeof(linebuf), "TX %lu pkts (%.1f kbps)", sentOk, kbps);
        DUAL_PRINTLN(linebuf);
    }
}
#else
// ─── RX: Continuous logging with fixed RSSI ──────────────
void loop() {
    static uint32_t rxCount = 0;
    static uint32_t startMs = millis();

    if (rxFlag) {
        rxFlag = false;
        int16_t len = radio.getPacketLength();
        if (len > 0 && len <= 200) {
            uint8_t buf[200];
            int16_t state = radio.readData(buf, len);
            if (state == RADIOLIB_ERR_NONE) {
                rxCount++;

                // RSSI: getRSSI() patched to dispatch to getFlrcPacketStatus for FLRC
                float rssi = radio.getRSSI();

                // Extract sequence number from first 4 bytes
                uint32_t seq = 0;
                if (len >= 4) {
                    seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                          ((uint32_t)buf[2] << 8) | (uint32_t)buf[3];
                }

                // Output PKT format that rx_range_logger.py expects:
                // PKT,n,seq,rssi_dbm
                snprintf(linebuf, sizeof(linebuf), "PKT,%lu,%lu,%.0f",
                         rxCount, seq, rssi);
                DUAL_PRINTLN(linebuf);

                // Periodic stats
                if (rxCount % 500 == 0) {
                    uint32_t elapsed = millis() - startMs;
                    float kbps = (float)rxCount * PKT_SIZE * 8.0f / (float)elapsed;
                    snprintf(linebuf, sizeof(linebuf),
                        "STATS rx=%lu kbps=%.1f rssi_last=%.1f",
                        rxCount, kbps, rssi);
                    DUAL_PRINTLN(linebuf);
                }
            } else {
                snprintf(linebuf, sizeof(linebuf), "ERR rx_error=%d", state);
                DUAL_PRINTLN(linebuf);
            }
        }
        radio.startReceive();
    }
}
#endif
