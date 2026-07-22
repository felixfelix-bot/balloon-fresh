/*
 * DEPRECATED — DO NOT USE. This file uses SX1280 raw SPI commands (wrong chip).
 * Our chip is LR2021 (Gen 4), NOT SX1280. See ADR-017.
 * Use firmware/rp2040-flrc-max/ instead (RadioLib LR2021 driver).
 *
 * flrc_range_rx_auto.cpp — FLRC RX with RSSI for outdoor range testing
 *
 * Auto-listens on boot, continuous RX (no timeout), outputs per-packet RSSI.
 * Loops forever. Format optimized for Python logging script.
 *
 * Based on flrc_raw_rx.cpp (verified working 2026-07-22).
 *
 * Output format per packet:
 *   PKT,n,seq,rssi_dbm
 *   PKT,n,seq,rssi_dbm
 *   ...
 *   (no per-packet hex dump in auto mode — too slow for logging)
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13  LED=GP25  LED_ALT=GP16
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
#define FLRC_BR         2600
#define FLRC_PKT_SIZE   255
#define SPI_FREQ_HZ     16000000UL   // 16MHz RX (20MHz TX is fine, RX uses 16)
#define XTAL_MHZ        52.0f

#define PRINT_EVERY     1   // print EVERY packet in auto mode

// Sync word — MUST match TX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// ─── SPI helpers ─────────────────────────────────────────────────────
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

// ─── RSSI readback via GET_FLRC_PACKET_STATUS (0x024B) ─────────────
// LR2021 native command — NOT SX1280's 0x0104!
// Returns 5 bytes: [pktLen_msb][pktLen_lsb][rssiAvg][rssiSync][flags]
// RSSI is 9-bit: bits [8:1] from buf[2], bit [0] from buf[4] bit 2
// Call AFTER RX_DONE, BEFORE clearing IRQ
static int8_t rfReadRssi() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02); spiRf.transfer(0x4B);  // GET_FLRC_PACKET_STATUS = 0x024B
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[7];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 7; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    // LR2021 response: [stat_msb][stat_lsb][pktLen_msb][pktLen_lsb][rssiAvg][rssiSync][flags]
    // 9-bit RSSI average: (buf[4] << 1) | ((buf[6] & 0x04) >> 2), then / -2 for dBm
    uint16_t raw = ((uint16_t)buf[4] << 1) | ((buf[6] & 0x04) >> 2);
    return -(int8_t)(raw / 2);  // Returns dBm (negative)
}

// ─── Dual output ─────────────────────────────────────────────────────
static void dualPrint(const char *s) { Serial.print(s); Serial1.print(s); }
static void dualPrintln(const char *s) { Serial.println(s); Serial1.println(s); }
static void dualPrintln() { Serial.println(); Serial1.println(); }

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
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0C,
            0x4C,
            0x00, (uint8_t)FLRC_PKT_SIZE
        };
        rfWriteCmd(cmd, 6);
    }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }  // Fs fallback
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
        dualPrintln("RADIO_INIT_OK");
        return true;
    }
    dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

// ─── State ───────────────────────────────────────────────────────────
static volatile bool radioReady = false;
static uint32_t totalReceived = 0;
static uint32_t totalUnique = 0;
static uint32_t lastSeq = 0xFFFFFFFF;
static int16_t rssiSum = 0;
static int16_t rssiMin = 0;
static int16_t rssiMax = -128;

// ─── Continuous RX with RSSI logging ─────────────────────────────────
static void runReceiveContinuous() {
    if (!radioReady) { dualPrintln("ERR: radio not initialized"); return; }

    uint8_t buf[FLRC_PKT_SIZE];

    dualPrintln("RX_LISTEN_START");
    rfSetRx();

    uint32_t lastReportMs = millis();

    while (true) {
        // Poll IRQ
        uint32_t irq = rfReadIrqStatus();
        if (!(irq & 0x00040000)) {
            // No packet — check for serial commands
            static char cmdBuf[64];
            static size_t cmdLen = 0;
            while (Serial1.available()) {
                char c = (char)Serial1.read();
                if (c == '\n' || c == '\r') {
                    if (cmdLen > 0) {
                        cmdBuf[cmdLen] = '\0';
                        if (strcmp(cmdBuf, "STATS") == 0) {
                            int16_t rssiAvg = (totalReceived > 0) ? (rssiSum / (int16_t)totalReceived) : 0;
                            dualPrintf("STATS rx=%lu unique=%lu rssi_avg=%d rssi_min=%d rssi_max=%d",
                                       (unsigned long)totalReceived, (unsigned long)totalUnique,
                                       rssiAvg, rssiMin, rssiMax);
                        }
                        cmdLen = 0;
                    }
                } else if (cmdLen < sizeof(cmdBuf) - 1) {
                    cmdBuf[cmdLen++] = c;
                }
            }
            continue;
        }

        // RX_DONE — read RSSI BEFORE clearing IRQ
        int8_t rssi = rfReadRssi();

        // Read packet
        rfReadFifo(buf, FLRC_PKT_SIZE);

        // Clear + re-arm
        { uint8_t cmd[] = { 0x01, 0x1E }; rfWriteCmd(cmd, 2); }  // CLEAR_RX_FIFO
        rfWaitBusy();
        { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
        rfClearIrq();
        rfSetRx();

        // Extract seq (bytes 0-3) and burst_id (bytes 4-7)
        uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                       ((uint32_t)buf[2] << 8)  | (uint32_t)buf[3];
        uint32_t burstId = ((uint32_t)buf[4] << 24) | ((uint32_t)buf[5] << 16) |
                           ((uint32_t)buf[6] << 8)  | (uint32_t)buf[7];

        totalReceived++;
        if (seq != lastSeq) totalUnique++;
        lastSeq = seq;

        rssiSum += rssi;
        if (rssi < rssiMin) rssiMin = rssi;
        if (rssi > rssiMax) rssiMax = rssi;

        // Output EVERY packet: PKT,n,seq,rssi
        dualPrintf("PKT,%lu,%lu,%d",
                   (unsigned long)totalReceived, (unsigned long)seq, (int)rssi);

        // Periodic summary every 100 packets
        if (totalReceived % 100 == 0) {
            digitalWrite(PIN_LED, HIGH); delayMicroseconds(50); digitalWrite(PIN_LED, LOW);
        }
    }
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(2000);
    Serial.println("BOOT RX AUTO");
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

    dualPrintln();
    dualPrintln("=== RP2040 FLRC RANGE RX AUTO ===");
    dualPrintln("Continuous RX with RSSI logging");

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        dualPrintln("Auto-start RX in 2s...");
        delay(2000);
    } else {
        digitalWrite(PIN_LED_ALT, LOW);
        dualPrintln("INIT FAILED");
        while (true) {
            digitalWrite(PIN_LED, HIGH); delay(500);
            digitalWrite(PIN_LED, LOW); delay(500);
        }
    }
}

void loop() {
    // Continuous RX — never returns
    runReceiveContinuous();
}
