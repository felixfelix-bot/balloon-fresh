/*
 * flrc_throughput_tx.cpp — Max-throughput FLRC TX for RP2040 + SX1280/LR2021
 *
 * Continuous back-to-back streaming of 127-byte packets (max SX1280 FLRC).
 * No burst structure, no gaps, no GPS. Pure throughput test.
 *
 * Auto-starts 3s after power-up. Streams forever.
 *
 * Payload (127 bytes):
 *   0-3:   packet sequence (uint32 big-endian)
 *   4-7:   timestamp ms since boot (uint32 big-endian)
 *   8-126: fill pattern 0xAA
 *
 * Prints throughput stats every 1000 packets:
 *   total sent, elapsed time, effective kbps
 *
 * Based on flrc_range_tx_gps.cpp (verified 2026-07-22).
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13 (Serial1, debug)
 *       LED=GP25  LED_ALT=GP16
 */

#include <Arduino.h>
#include <SPI.h>

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

// ─── FLRC Config (MUST match RX) ─────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_PKT_SIZE   127
#define SPI_FREQ_HZ     20000000UL
#define XTAL_MHZ        52.0f

#define TX_POWER_DBM    12
#define AUTO_START_MS   3000
#define STATS_INTERVAL  1000   // print stats every N packets

#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

static inline bool rfWaitBusy() {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 100000;
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
    return timeout > 0;
}

static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
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

static void rfSetTx() {
    uint8_t cmd[5] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
    rfWriteCmd(cmd, 5);
}

static void rfWriteTxFifo(const uint8_t *data, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00);
    spiRf.transfer(0x02);
    for (size_t i = 0; i < len; i++) spiRf.transfer(data[i]);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
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
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0C, 0x4C, 0x00, (uint8_t)FLRC_PKT_SIZE
        };
        rfWriteCmd(cmd, 6);
    }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);
    { uint8_t cmd[] = { 0x02, 0x03, (uint8_t)(TX_POWER_DBM * 2), 0x04 }; rfWriteCmd(cmd, 4); }
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
static uint32_t totalSent = 0;
static uint32_t txDoneCount = 0;
static uint32_t txTimeoutCount = 0;
static uint32_t streamStartMs = 0;

// ─── Continuous TX streaming ─────────────────────────────────────────
static void runTransmitContinuous() {
    if (!radioReady) { dualPrintf("ERR: radio not initialized"); return; }

    dualPrintf("STREAM_START pkt_size=%d", FLRC_PKT_SIZE);

    uint8_t pkt[FLRC_PKT_SIZE];
    // Fill pattern 0xAA for bytes 8-126
    for (int j = 8; j < FLRC_PKT_SIZE; j++) pkt[j] = 0xAA;

    uint32_t irqMask = 1UL << PIN_IRQ;
    streamStartMs = millis();

    while (true) {
        // Packet sequence (big-endian)
        pkt[0] = (uint8_t)(totalSent >> 24);
        pkt[1] = (uint8_t)(totalSent >> 16);
        pkt[2] = (uint8_t)(totalSent >> 8);
        pkt[3] = (uint8_t)(totalSent & 0xFF);

        // Timestamp (ms since boot, big-endian)
        uint32_t now = millis();
        pkt[4] = (uint8_t)(now >> 24);
        pkt[5] = (uint8_t)(now >> 16);
        pkt[6] = (uint8_t)(now >> 8);
        pkt[7] = (uint8_t)(now & 0xFF);

        rfClearIrq();
        rfWriteTxFifo(pkt, FLRC_PKT_SIZE);
        rfSetTx();

        // Wait for TX_DONE
        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 500000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
        }

        if (irqFired) txDoneCount++;
        else txTimeoutCount++;

        totalSent++;

        // Print stats every STATS_INTERVAL packets
        if (totalSent % STATS_INTERVAL == 0) {
            uint32_t elapsed = millis() - streamStartMs;
            float tput = ((float)totalSent * FLRC_PKT_SIZE * 8.0f) / elapsed;
            dualPrintf("STATS sent=%lu done=%lu to=%lu elapsed_ms=%lu tput_kbps=%.1f",
                       (unsigned long)totalSent,
                       (unsigned long)txDoneCount,
                       (unsigned long)txTimeoutCount,
                       (unsigned long)elapsed, tput);
        }

        // Blink LED every 100 packets
        if (totalSent % 100 == 0) {
            digitalWrite(PIN_LED, HIGH);
            delayMicroseconds(50);
            digitalWrite(PIN_LED, LOW);
        }
    }
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);
    delay(100);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);

    for (int i = 0; i < 5; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(100);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(100);
    }

    Serial1.println();
    Serial1.println("=== RP2040 FLRC THROUGHPUT TX ===");

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        dualPrintf("AUTO_START in %dms...", AUTO_START_MS);
        delay(AUTO_START_MS);
    } else {
        digitalWrite(PIN_LED_ALT, LOW);
        while (true) {
            digitalWrite(PIN_LED, HIGH); delay(500);
            digitalWrite(PIN_LED, LOW); delay(500);
        }
    }
}

void loop() {
    runTransmitContinuous();
}