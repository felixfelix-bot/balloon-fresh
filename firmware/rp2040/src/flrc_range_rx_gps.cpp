/*
 * flrc_range_rx_gps.cpp — FLRC RX with RSSI + GPS extraction
 *
 * Backward compatible: parses GPS fields from TX payload if present.
 * If TX has no GPS (fix=0), still outputs seq + rssi normally.
 *
 * Output per packet:
 *   With GPS:    PKT,n,seq,rssi,lat,lon,alt,sats,hdop,fix
 *   Without GPS: PKT,n,seq,rssi,0,0,0,0,0,0
 *
 * Based on flrc_range_rx_auto.cpp (verified 2026-07-22).
 */

#include <Arduino.h>
#include <SPI.h>
#include "pico/bootrom.h"

// ─── Pins ────────────────────────────────────────────────────────────
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
#define PIN_LED_ALT 16

// ─── FLRC Config ─────────────────────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_PKT_SIZE   255
#define SPI_FREQ_HZ     16000000UL
#define XTAL_MHZ        52.0f

#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

static inline void rfWaitBusy() {
    uint32_t timeout = millis() + 50;
    while (digitalRead(PIN_BUSY) == HIGH) {
        if (millis() > timeout) return;
    }
}

static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfReadFifo(uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00); spiRf.transfer(0x01);
    for (size_t i = 0; i < len; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static uint8_t rfReadStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    uint8_t st = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    return st;
}

static uint32_t rfReadIrqStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x01); spiRf.transfer(0x17);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[6];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 6; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    return ((uint32_t)buf[2] << 24) | ((uint32_t)buf[3] << 16) |
           ((uint32_t)buf[4] << 8) | (uint32_t)buf[5];
}

static void rfClearIrq() {
    uint8_t cmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 6);
}

static void rfSetRx() {
    uint8_t cmd[5] = { 0x02, 0x0C, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 5);
}

static int8_t rfReadRssi() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x01); spiRf.transfer(0x04);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[4];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 4; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    // SX1280/LR2021: PACKET_STATUS buf[0]=status, buf[1]=RSSI (unsigned, negate for dBm)
    // RadioLib negates this value: RSSI_dBm = -buf[1]
    return -(int8_t)buf[1];
}

// ─── Dual output ─────────────────────────────────────────────────────
static void dualPrintf(const char *fmt, ...) {
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.println(buf);
    Serial1.println(buf);
}

// ─── Raw SPI Init ────────────────────────────────────────────────────
static bool rawInitRadio() {
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; rfWriteCmd(cmd, 3); }
    delay(5);
    { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; rfWriteCmd(cmd, 3); }
    delay(1);

    uint32_t frf = (uint32_t)((FLRC_FREQ_MHZ * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    {
        uint8_t cmd[] = {
            0x02, 0x00,
            (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
        };
        rfWriteCmd(cmd, 5);
    }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    uint16_t feFreq = (uint16_t)((FLRC_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
    {
        uint8_t cmd[] = {
            0x01, 0x23,
            (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        };
        rfWriteCmd(cmd, 10);
    }
    delay(5);

    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
    delay(5);
    { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x25 }; rfWriteCmd(cmd, 4); }
    delay(1);

    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

    {
        uint8_t cmd[] = { 0x02, 0x49, 0x0C, 0x4C, 0x00, (uint8_t)FLRC_PKT_SIZE };
        rfWriteCmd(cmd, 6);
    }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
    delay(1);

    rfClearIrq();
    delay(1);

    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    if ((st >> 4) == 0x04 || (st >> 4) == 0x07 || (irq & 0x00020000)) {
        dualPrintf("RADIO_INIT_OK");
        return true;
    }
    dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

// ─── State ───────────────────────────────────────────────────────────
static volatile bool radioReady = false;
static uint32_t totalReceived = 0;

// ─── Extract GPS from packet ─────────────────────────────────────────
struct PacketGps {
    int32_t  lat1e7;
    int32_t  lon1e7;
    int16_t  altMeters;
    uint8_t  satellites;
    uint8_t  hdopX10;
    uint8_t  fix;
};

static PacketGps extractGps(const uint8_t *buf) {
    PacketGps g;
    g.lat1e7 = ((int32_t)buf[8] << 24) | ((int32_t)buf[9] << 16) |
               ((int32_t)buf[10] << 8) | (int32_t)buf[11];
    g.lon1e7 = ((int32_t)buf[12] << 24) | ((int32_t)buf[13] << 16) |
               ((int32_t)buf[14] << 8) | (int32_t)buf[15];
    g.altMeters = (int16_t)(((uint16_t)buf[16] << 8) | buf[17]);
    g.satellites = buf[18];
    g.hdopX10 = buf[19];
    g.fix = buf[24];
    return g;
}

// ─── Continuous RX ───────────────────────────────────────────────────
static void runReceiveContinuous() {
    if (!radioReady) { dualPrintf("ERR: radio not initialized"); return; }

    uint8_t buf[FLRC_PKT_SIZE];
    dualPrintf("RX_LISTEN_START");
    rfSetRx();

    while (true) {
        uint32_t irq = rfReadIrqStatus();
        if (!(irq & 0x00040000)) {
            // No packet — check serial
            static char cmdBuf[64];
            static size_t cmdLen = 0;
            while (Serial1.available()) {
                char c = (char)Serial1.read();
                if (c == '\n' || c == '\r') {
                    if (cmdLen > 0) {
                        cmdBuf[cmdLen] = '\0';
                        if (strcmp(cmdBuf, "STATS") == 0) {
                            dualPrintf("STATS rx=%lu", (unsigned long)totalReceived);
                        }
                        cmdLen = 0;
                    }
                } else if (cmdLen < sizeof(cmdBuf) - 1) {
                    cmdBuf[cmdLen++] = c;
                }
            }
            continue;
        }

        int8_t rssi = rfReadRssi();
        rfReadFifo(buf, FLRC_PKT_SIZE);

        { uint8_t cmd[] = { 0x01, 0x1E }; rfWriteCmd(cmd, 2); }
        rfWaitBusy();
        { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
        rfClearIrq();
        rfSetRx();

        uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                       ((uint32_t)buf[2] << 8)  | (uint32_t)buf[3];

        PacketGps g = extractGps(buf);

        totalReceived++;

        // Output: PKT,n,seq,rssi,lat,lon,alt,sats,hdop,fix
        dualPrintf("PKT,%lu,%lu,%d,%ld,%ld,%d,%d,%d,%d",
                   (unsigned long)totalReceived, (unsigned long)seq, (int)rssi,
                   (long)g.lat1e7, (long)g.lon1e7, (int)g.altMeters,
                   (int)g.satellites, (int)g.hdopX10, (int)g.fix);

        if (totalReceived % 100 == 0) {
            digitalWrite(PIN_LED, HIGH); delayMicroseconds(50); digitalWrite(PIN_LED, LOW);
        }
    }
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(2000);
    Serial.println("BOOT RX GPS");
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);
    delay(100);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(120);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(120);
    }

    dualPrintf("=== RP2040 FLRC RANGE RX + GPS ===");

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        dualPrintf("Auto-start RX in 2s...");
        delay(2000);
    } else {
        digitalWrite(PIN_LED_ALT, LOW);
        while (true) {
            digitalWrite(PIN_LED, HIGH); delay(500);
            digitalWrite(PIN_LED, LOW); delay(500);
        }
    }
}

void loop() {
    runReceiveContinuous();
}
