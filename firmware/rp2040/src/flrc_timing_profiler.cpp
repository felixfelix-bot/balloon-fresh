/*
 * flrc_timing_profiler.cpp — Measure exact per-operation SPI timing
 *
 * Toggles a GPIO pin at key points and uses RP2040's 64-bit timer
 * to measure microsecond-level timing of every SPI operation.
 *
 * This gives us the SOFTWARE timing view to complement the LOGIC ANALYZER's
 * electrical view. Together they show exactly where time is lost.
 *
 * Output format:
 *   PROFILE,<operation>,<duration_us>,<bytes>
 *
 * Pins: Same as v4 TX. Plus GP14 = timing probe (for scope/LA trigger)
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
#define PIN_PROBE   14  // Toggle for scope/LA trigger
#define PIN_LED     25

// ─── FLRC Config (MUST match RX) ─────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_PKT_SIZE   255
#define SPI_FREQ_HZ     16000000UL
#define XTAL_MHZ        52.0f

#define TX_PKT_COUNT    100
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// ─── Timing ──────────────────────────────────────────────────────────
static inline uint64_t time_us_64_fast() {
    absolute_time_t t = get_absolute_time();
    return to_us_since_boot(t);
}

#define TIMING_START(var)  uint64_t var##_start = time_us_64_fast()
#define TIMING_END(var)    uint64_t var##_end = time_us_64_fast(); uint32_t var = (uint32_t)(var##_end - var##_start)

#define TOGGLE_PROBE() (sio_hw->gpio_togl = (1UL << PIN_PROBE))

// ─── SPI helpers ─────────────────────────────────────────────────────
static inline bool rfWaitBusy() {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 100000;
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
    return timeout > 0;
}

static uint32_t profiledWriteCmd(const uint8_t *buf, size_t len, const char *name) {
    TIMING_START(t);
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    TIMING_END(t);
    return t;
}

static uint32_t profiledWriteTxFifo(const uint8_t *data, size_t len) {
    TIMING_START(t);
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00);
    spiRf.transfer(0x02);
    for (size_t i = 0; i < len; i++) spiRf.transfer(data[i]);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    TIMING_END(t);
    return t;
}

static uint32_t profiledClearIrq() {
    uint8_t cmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    return profiledWriteCmd(cmd, 6, "CLR_IRQ");
}

static uint32_t profiledSetTx() {
    uint8_t cmd[5] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
    return profiledWriteCmd(cmd, 5, "SET_TX");
}

// Dummy wrapper for init (no profiling during init)
static void rfWriteCmd_dummy(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

// ─── Raw SPI Init (same as v4) ───────────────────────────────────────
static void rawInitRadio() {
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd_dummy(cmd, 4); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; rfWriteCmd_dummy(cmd, 3); }
    delay(5);
    { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; rfWriteCmd_dummy(cmd, 3); }
    delay(1);

    uint32_t frf = (uint32_t)((FLRC_FREQ_MHZ * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    {
        uint8_t cmd[] = {
            0x02, 0x00,
            (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
        };
        rfWriteCmd_dummy(cmd, 5);
    }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd_dummy(cmd, 4); }
    delay(1);

    uint16_t feFreq = (uint16_t)((FLRC_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
    {
        uint8_t cmd[] = {
            0x01, 0x23,
            (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        };
        rfWriteCmd_dummy(cmd, 10);
    }
    delay(5);

    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd_dummy(cmd, 3); }
    delay(5);
    { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x25 }; rfWriteCmd_dummy(cmd, 4); }
    delay(1);

    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd_dummy(cmd, 7);
    }
    delay(1);

    {
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0C,
            0x4C,
            0x00, (uint8_t)FLRC_PKT_SIZE
        };
        rfWriteCmd_dummy(cmd, 6);
    }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd_dummy(cmd, 7); }
    delay(1);
    { uint8_t cmd[] = { 0x02, 0x03, 0x18, 0x04 }; rfWriteCmd_dummy(cmd, 4); }
    delay(1);
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd_dummy(cmd, 4); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd_dummy(cmd, 4); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 }; rfWriteCmd_dummy(cmd, 7); }
    delay(1);

    // Clear IRQ
    uint8_t cmd[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    rfWriteCmd_dummy(cmd, 6);
}

// ─── Profiled TX burst ───────────────────────────────────────────────
static void runProfiledTx() {
    Serial.println("\n=== TIMING PROFILE ===");
    Serial.println("operation,duration_us,bytes");

    uint8_t pkt[FLRC_PKT_SIZE];
    for (int j = 4; j < FLRC_PKT_SIZE; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t irqMask = 1UL << PIN_IRQ;

    uint32_t totalClrIrq = 0, totalWriteFifo = 0, totalSetTx = 0, totalWaitTxDone = 0;
    uint32_t totalLoop = 0;

    for (int i = 0; i < TX_PKT_COUNT; i++) {
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        TIMING_START(loop);

        // 1. Clear IRQ
        uint32_t t_clr = profiledClearIrq();
        totalClrIrq += t_clr;

        // 2. Write TX FIFO
        uint32_t t_fifo = profiledWriteTxFifo(pkt, FLRC_PKT_SIZE);
        totalWriteFifo += t_fifo;

        // 3. Trigger TX
        uint32_t t_settx = profiledSetTx();
        totalSetTx += t_settx;

        // 4. Wait for TX_DONE — IRQ pin HIGH
        TIMING_START(txdone);
        TOGGLE_PROBE(); // Mark TX start for scope
        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 500000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
        }
        TIMING_END(txdone);
        TOGGLE_PROBE(); // Mark TX_DONE
        totalWaitTxDone += txdone;

        TIMING_END(loop);
        totalLoop += loop;

        // Print per-operation timing for first 10 packets
        if (i < 10) {
            Serial.printf("PKT,%d,clr=%u,fifo=%u,settx=%u,txdone=%u,total=%u\n",
                         i, t_clr, t_fifo, t_settx, txdone, loop);
        }
    }

    // Averages
    Serial.println("\n=== AVERAGE TIMING (100 packets) ===");
    Serial.printf("AVG_CLR_IRQ,%.1f,6\n", (float)totalClrIrq / TX_PKT_COUNT);
    Serial.printf("AVG_WRITE_FIFO,%.1f,%d\n", (float)totalWriteFifo / TX_PKT_COUNT, FLRC_PKT_SIZE + 2);
    Serial.printf("AVG_SET_TX,%.1f,5\n", (float)totalSetTx / TX_PKT_COUNT);
    Serial.printf("AVG_TX_DONE_WAIT,%.1f,0\n", (float)totalWaitTxDone / TX_PKT_COUNT);
    Serial.printf("AVG_TOTAL_LOOP,%.1f,0\n", (float)totalLoop / TX_PKT_COUNT);

    // Breakdown
    float avgLoop = (float)totalLoop / TX_PKT_COUNT;
    Serial.println("\n=== BREAKDOWN ===");
    Serial.printf("  CLR_IRQ:      %5.1f us (%4.1f%%)\n", (float)totalClrIrq / TX_PKT_COUNT, 100.0f * totalClrIrq / totalLoop);
    Serial.printf("  WRITE_FIFO:   %5.1f us (%4.1f%%)\n", (float)totalWriteFifo / TX_PKT_COUNT, 100.0f * totalWriteFifo / totalLoop);
    Serial.printf("  SET_TX:       %5.1f us (%4.1f%%)\n", (float)totalSetTx / TX_PKT_COUNT, 100.0f * totalSetTx / totalLoop);
    Serial.printf("  TX_DONE_WAIT: %5.1f us (%4.1f%%)\n", (float)totalWaitTxDone / TX_PKT_COUNT, 100.0f * totalWaitTxDone / totalLoop);
    Serial.printf("  TOTAL:        %5.1f us\n", avgLoop);

    float tput = ((float)TX_PKT_COUNT * FLRC_PKT_SIZE * 8.0f) / ((float)totalLoop / TX_PKT_COUNT * TX_PKT_COUNT / 1000.0f);
    Serial.printf("\n  THROUGHPUT:   %.1f kbps\n", ((float)FLRC_PKT_SIZE * 8.0f) / avgLoop * 1000.0f);

    Serial.println("\n=== PER-BYTE SPI ANALYSIS ===");
    // Measure single-byte transfer time
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    TIMING_START(byte10);
    for (int i = 0; i < 10; i++) spiRf.transfer(0x00);
    TIMING_END(byte10);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    Serial.printf("  10 bytes: %u us = %.2f us/byte\n", byte10, (float)byte10 / 10.0f);

    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    TIMING_START(byte255);
    for (int i = 0; i < 255; i++) spiRf.transfer(0x00);
    TIMING_END(byte255);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    Serial.printf("  255 bytes: %u us = %.2f us/byte\n", byte255, (float)byte255 / 255.0f);

    // Measure with beginTransaction overhead per byte
    TIMING_START(perByte);
    for (int i = 0; i < 10; i++) {
        spiRf.beginTransaction(spiSettings);
        digitalWrite(PIN_CS, LOW);
        spiRf.transfer(0x00);
        digitalWrite(PIN_CS, HIGH);
        spiRf.endTransaction();
    }
    TIMING_END(perByte);
    Serial.printf("  10 separate transactions: %u us = %.2f us/byte (incl CS+txn overhead)\n", perByte, (float)perByte / 10.0f);

    Serial.println("\nDONE");
}

// ─── Setup ───────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(2000); // Wait for CDC

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_PROBE, OUTPUT);
    digitalWrite(PIN_PROBE, LOW);

    Serial.println("\n=== RP2040 FLRC TIMING PROFILER ===");
    Serial.println("Measures per-operation SPI timing for LR2021");

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    rawInitRadio();
    delay(500);

    Serial.println("Radio initialized. Type RUN to profile.");
}

void loop() {
    static unsigned long lastHB = 0;
    if (millis() - lastHB > 2000) {
        lastHB = millis();
        Serial.println("HB type RUN to profile");
    }

    static char cmdBuf[64];
    static size_t cmdLen = 0;
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (cmdLen > 0) {
                cmdBuf[cmdLen] = '\0';
                if (strcmp(cmdBuf, "RUN") == 0) runProfiledTx();
                else if (strcmp(cmdBuf, "BOOTSEL") == 0) { delay(100); reset_usb_boot(0, 0); }
                cmdLen = 0;
            }
        } else if (cmdLen < sizeof(cmdBuf) - 1) {
            cmdBuf[cmdLen++] = c;
        }
    }
}
