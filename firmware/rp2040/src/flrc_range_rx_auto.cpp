/*
 * flrc_range_rx_auto.cpp — Autonomous RX for outdoor range testing
 *
 * Based on flrc_range_rx.cpp (proven 0% loss at bench).
 * Auto-starts RX listen on boot — NO serial commands needed.
 * Stays connected to computer to log results.
 *
 * Behavior:
 * - 2s LED blink on boot (time for TX operator to walk)
 * - Enters RX mode immediately, listens for 30s windows
 * - After each window: prints summary + RANGE_RESULT_RX line
 * - Re-arms RX automatically, runs forever
 * - RSSI readback per packet via GET_PACKET_STATUS
 * - LED blinks on each packet received
 *
 * Config is compile-time only:
 *   FREQ=2440, BITRATE=2600, PKTLEN=255
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13
 *       LED=GP25 LED_ALT=GP16
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

#define SPI_FREQ_HZ     16000000UL
#define XTAL_MHZ        52.0f

// ─── Compile-time config ─────────────────────────────────────────────
#define RX_FREQ_MHZ     2440.0f
#define RX_BITRATE_KBPS 2600
#define RX_PKT_SIZE     255
#define RX_LISTEN_MS    30000
#define RX_SILENCE_MS   3000
#define PRINT_EVERY     100

// Sync word — MUST match TX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

static volatile bool radioReady = false;

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

// ─── RSSI readback via GET_PACKET_STATUS (0x0104) ───────────────────
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

    return (int8_t)buf[1];
}

// ─── Runtime parameter setters ───────────────────────────────────────
static void rfSetFreq(float mhz) {
    uint32_t frf = (uint32_t)((mhz * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    uint8_t cmd[] = {
        0x02, 0x00,
        (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
    };
    rfWriteCmd(cmd, 5);
}

static void rfSetBitrate(uint16_t kbps) {
    uint8_t brBw;
    switch (kbps) {
        case 2600: brBw = 0x00; break;
        case 1300: brBw = 0x01; break;
        case 650:  brBw = 0x02; break;
        case 325:  brBw = 0x03; break;
        default:   brBw = 0x00; break;
    }
    uint8_t cmd[] = { 0x02, 0x48, brBw, 0x25 };
    rfWriteCmd(cmd, 4);
}

static void rfSetPktSize(uint16_t size) {
    uint8_t cmd[] = {
        0x02, 0x49,
        0x0C, 0x4C,
        (uint8_t)(size >> 8), (uint8_t)(size & 0xFF)
    };
    rfWriteCmd(cmd, 6);
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

// ─── Full radio init ─────────────────────────────────────────────────
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

    rfSetFreq(RX_FREQ_MHZ);
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    uint16_t feFreq = (uint16_t)((RX_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
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

    rfSetBitrate(RX_BITRATE_KBPS);
    delay(1);

    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

    rfSetPktSize(RX_PKT_SIZE);
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x04, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
    delay(1);

    rfClearIrq();
    delay(1);
    rfSetRx();
    delay(2);

    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    if ((st >> 4) == 0x05) {
        dualPrintln("RADIO_INIT_OK (RX mode)");
        return true;
    } else if (irq & 0x00020000) {
        dualPrintf("RADIO_INIT_WARN CMD_ERROR (St=0x%02X)", st);
        return true;
    } else {
        dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
        return false;
    }
}

// ─── Statistics ──────────────────────────────────────────────────────
struct RxStats {
    uint32_t received;
    uint32_t unique;
    uint32_t duplicates;
    uint32_t lastSeq;
    uint32_t maxSeq;
    uint32_t totalSentByTx;
    uint32_t startMs;
    uint32_t elapsedMs;
    int32_t  rssiSum;
    int16_t  rssiMin;
    int16_t  rssiMax;
    uint16_t rssiCount;
};
static RxStats stats;

static void resetStats() {
    memset(&stats, 0, sizeof(stats));
    stats.lastSeq = 0xFFFFFFFF;
    stats.rssiMin = 0;
    stats.rssiMax = -128;
}

// ─── Receive session ─────────────────────────────────────────────────
static uint32_t windowNum = 0;

static void runReceive() {
    if (!radioReady) return;

    rfClearIrq();
    rfSetRx();
    delay(1);

    resetStats();
    stats.startMs = millis();
    uint32_t lastPktMs = millis();
    uint16_t pktSize = RX_PKT_SIZE;
    uint8_t buf[256];

    dualPrintf("RX_WINDOW %lu START listen=%dms",
               (unsigned long)windowNum, RX_LISTEN_MS);

    while (true) {
        uint32_t now = millis();
        if ((now - stats.startMs) >= RX_LISTEN_MS) {
            dualPrintln("RX_DONE timeout");
            break;
        }
        if (stats.received > 0 && (now - lastPktMs) >= RX_SILENCE_MS) {
            dualPrintln("RX_DONE silence");
            break;
        }

        uint32_t irq = rfReadIrqStatus();
        if (!(irq & 0x00040000)) continue;  // bit 18 = RX_DONE

        // Read packet
        rfReadFifo(buf, pktSize);

        // Read RSSI before clearing IRQ
        int8_t rssi = rfReadRssi();
        stats.rssiSum += rssi;
        stats.rssiCount++;
        if (rssi < stats.rssiMin) stats.rssiMin = rssi;
        if (rssi > stats.rssiMax) stats.rssiMax = rssi;

        // Clear FIFO + errors + re-arm RX
        { uint8_t cmd[] = { 0x01, 0x1E }; rfWriteCmd(cmd, 2); }
        rfWaitBusy();
        { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
        rfClearIrq();
        rfSetRx();

        // Extract big-endian seq
        uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                       ((uint32_t)buf[2] << 8)  | (uint32_t)buf[3];

        // DEADBEEF end marker
        if (buf[0] == 0xDE && buf[1] == 0xAD &&
            buf[2] == 0xBE && buf[3] == 0xEF) {
            stats.totalSentByTx = ((uint32_t)buf[4] << 24) | ((uint32_t)buf[5] << 16) |
                                  ((uint32_t)buf[6] << 8)  | (uint32_t)buf[7];
            stats.elapsedMs = millis() - stats.startMs;
            dualPrintln("RX_END DEADBEEF");
            break;
        }

        stats.received++;
        if (stats.lastSeq != 0xFFFFFFFF && seq == stats.lastSeq) stats.duplicates++;
        else stats.unique++;
        stats.lastSeq = seq;
        if (seq > stats.maxSeq) stats.maxSeq = seq;
        lastPktMs = millis();

        // Blink LED on packet
        digitalWrite(PIN_LED, HIGH);
        delayMicroseconds(1000);
        digitalWrite(PIN_LED, LOW);

        if (stats.received <= 5 || (stats.received % PRINT_EVERY) == 0) {
            dualPrintf("PKT %lu seq=%lu rssi=%d",
                       (unsigned long)stats.received, (unsigned long)seq, rssi);
        }
    }

    if (stats.elapsedMs == 0) stats.elapsedMs = millis() - stats.startMs;

    // Compute results
    uint32_t n = stats.received;
    uint32_t total = stats.totalSentByTx > 0 ? stats.totalSentByTx : (stats.maxSeq + 1);
    uint32_t lost = (total > n) ? (total - n) : 0;
    float perPct = (total > 0) ? (100.0f * (float)lost / (float)total) : 0.0f;
    float tputKbps = (stats.elapsedMs > 0 && n > 0)
                     ? ((float)n * (float)pktSize * 8.0f) / (float)stats.elapsedMs : 0.0f;
    float rssiAvg = (stats.rssiCount > 0)
                    ? (float)stats.rssiSum / (float)stats.rssiCount : 0.0f;

    dualPrintln("=============================================");
    dualPrintf("  Window:   %lu", (unsigned long)windowNum);
    dualPrintf("  Received: %lu (unique %lu, dup %lu)", (unsigned long)n,
               (unsigned long)stats.unique, (unsigned long)stats.duplicates);
    dualPrintf("  TX sent:  %lu", (unsigned long)stats.totalSentByTx);
    dualPrintf("  Lost:     %lu (%.2f%%)", (unsigned long)lost, perPct);
    dualPrintf("  Elapsed:  %lu ms", (unsigned long)stats.elapsedMs);
    dualPrintf("  THROUGHPUT: %.1f kbps", tputKbps);
    if (stats.rssiCount > 0) {
        dualPrintf("  RSSI: avg=%.1f dBm min=%d dBm max=%d dBm (n=%d)",
                   rssiAvg, stats.rssiMin, stats.rssiMax, stats.rssiCount);
    } else {
        dualPrintln("  RSSI: (no packets received)");
    }
    dualPrintln("=============================================");

    // Structured result line for automated parsing
    dualPrintf("RANGE_RESULT_RX,window=%lu,rx=%lu,unique=%lu,lost=%lu,total=%lu,per=%.2f,elapsed_ms=%lu,throughput_kbps=%.1f,rssi_avg=%.1f,rssi_min=%d,freq=%.1f,bitrate=%d,pktSize=%d",
               (unsigned long)windowNum,
               (unsigned long)n, (unsigned long)stats.unique, (unsigned long)lost,
               (unsigned long)total, perPct, (unsigned long)stats.elapsedMs, tputKbps,
               rssiAvg, stats.rssiMin, RX_FREQ_MHZ, RX_BITRATE_KBPS, RX_PKT_SIZE);

    windowNum++;
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(2000);  // give TinyUSB time to enumerate
    Serial.println("BOOT RX RANGE AUTO");
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);
    delay(100);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);
    for (int i = 0; i < 4; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(250);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(250);
    }

    dualPrintln();
    dualPrintln("=== RP2040 FLRC RANGE RX (AUTONOMOUS) ===");
    dualPrintf("Config: freq=%.1f br=%d pktSize=%d listen=%dms",
               RX_FREQ_MHZ, RX_BITRATE_KBPS, RX_PKT_SIZE, RX_LISTEN_MS);

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        dualPrintln("AUTO RX LISTENING");
    } else {
        dualPrintln("INIT FAILED — retrying...");
        delay(2000);
        radioReady = rawInitRadio();
        if (radioReady) {
            digitalWrite(PIN_LED_ALT, HIGH);
            dualPrintln("AUTO RX LISTENING (2nd init)");
        } else {
            dualPrintln("INIT FAILED TWICE — stuck");
        }
    }
}

void loop() {
    if (radioReady) {
        runReceive();
        delay(500);  // brief pause between windows
    } else {
        // Blink SOS if radio dead
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(500);
    }
}