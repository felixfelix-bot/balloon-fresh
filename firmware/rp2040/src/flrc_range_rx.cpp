/*
 * flrc_range_rx.cpp — Configurable RP2040 FLRC RX for range testing
 *
 * Based on flrc_raw_rx.cpp (proven 0% loss at bench).
 * Adds runtime serial commands + RSSI readback via GET_PACKET_STATUS.
 *
 *   POWER <dbm>      Ignored on RX (TX-only param) — accepted for sync
 *   PKTLEN <bytes>   Set payload size (12-255) — re-sends SET_FLRC_PACKET_PARAMS
 *   FREQ <mhz>       Set frequency (2400-2480) — re-sends SET_RF_FREQUENCY
 *   BITRATE <kbps>   Set FLRC bitrate (2600,1300,650,325) — re-sends SET_FLRC_MOD_PARAMS
 *   COUNT <n>        Ignored on RX — accepted for sync
 *   RUN              Start RX listen session (default 15s, or until DEADBEEF)
 *   INIT             Full radio re-init
 *   STATUS           Print config + radio status
 *   HELP             Command list
 *
 * RSSI is read after each packet via GET_FLRC_PACKET_STATUS (0x024B).
 * LR2021 returns 9-bit RSSI: (buf[4]<<1)|((buf[6]&0x04)>>2), /2, negate.
 *
 * Output format (for automated parsing):
 *   RANGE_RESULT_RX,rx=<n>,unique=<n>,lost=<n>,total=<n>,per=<f>,
 *     elapsed_ms=<n>,throughput_kbps=<f>,rssi_avg=<f>,rssi_min=<f>,
 *     freq=<f>,bitrate=<d>,pktSize=<d>
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13
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

#define SPI_FREQ_HZ     20000000UL
#define XTAL_MHZ        52.0f

#define RX_LISTEN_MS    15000
#define RX_SILENCE_MS   3000
#define PRINT_EVERY     100

// Sync word — MUST match TX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── Runtime config ──────────────────────────────────────────────────
struct RxConfig {
    float    freqMhz;
    uint16_t bitrateKbps;
    uint16_t pktSize;
};
static RxConfig cfg = {
    .freqMhz = 2440.0f,
    .bitrateKbps = 2600,
    .pktSize = 255,
};

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

static volatile bool radioReady = false;

// ─── Raw SPI helpers ─────────────────────────────────────────────────
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

// ─── RSSI readback via GET_FLRC_PACKET_STATUS (0x024B) — 9-bit assembly
// Matches verified LR2021Raw.h implementation. SX1280's 0x0104 returns garbage.
static int8_t rfReadRssi() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02); spiRf.transfer(0x4B); // GET_FLRC_PACKET_STATUS
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    // Response: [stat_msb][stat_lsb][pktLen_msb][pktLen_lsb][rssiAvg][rssiSync][flags]
    uint8_t buf[7];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 7; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    // 9-bit RSSI: bits [8:1] from buf[4], bit[0] from buf[6] bit[2]
    uint16_t raw = ((uint16_t)buf[4] << 1) | ((buf[6] & 0x04) >> 2);
    return -(int8_t)(raw / 2);
}

// ─── Runtime parameter setters ───────────────────────────────────────
static uint8_t bitrateToBrBw(uint16_t kbps) {
    switch (kbps) {
        case 2600: return 0x00;  // FLRC_BR_2600
        case 2080: return 0x01;  // FLRC_BR_2080
        case 1300: return 0x02;  // FLRC_BR_1300
        case 1040: return 0x03;  // FLRC_BR_1040
        case 650:  return 0x04;  // FLRC_BR_650
        case 520:  return 0x05;  // FLRC_BR_520
        case 325:  return 0x06;  // FLRC_BR_325
        case 260:  return 0x07;  // FLRC_BR_260
        default:   return 0x00;
    }
}

static void rfSetFreq(float mhz) {
    uint32_t frf = (uint32_t)((mhz * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    uint8_t cmd[] = {
        0x02, 0x00,
        (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
    };
    rfWriteCmd(cmd, 5);
}

static void rfSetBitrate(uint16_t kbps) {
    uint8_t brBw = bitrateToBrBw(kbps);
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

    rfSetFreq(cfg.freqMhz);
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    uint16_t feFreq = (uint16_t)((cfg.freqMhz / 4.0f) + 0.5f) | 0x8000;
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

    rfSetBitrate(cfg.bitrateKbps);
    delay(1);

    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

    rfSetPktSize(cfg.pktSize);
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
    // RSSI tracking
    int32_t  rssiSum;      // sum of all RSSI readings (for average)
    int16_t  rssiMin;      // worst (most negative) RSSI
    int16_t  rssiMax;      // best RSSI
    uint16_t rssiCount;    // number of RSSI samples
};
static RxStats stats;

static void resetStats() {
    memset(&stats, 0, sizeof(stats));
    stats.lastSeq = 0xFFFFFFFF;
    stats.rssiMin = 0;
    stats.rssiMax = -128;
}

// ─── Receive session ─────────────────────────────────────────────────
static void runReceive() {
    if (!radioReady) { dualPrintln("ERR: radio not initialized — type INIT"); return; }

    rfClearIrq();
    rfSetRx();
    delay(1);

    resetStats();
    stats.startMs = millis();
    uint32_t lastPktMs = millis();
    uint16_t pktSize = cfg.pktSize;
    uint8_t buf[256]; // max FLRC payload

    dualPrintf("RX_START freq=%.1f br=%d pktSize=%d listen=%dms",
               cfg.freqMhz, cfg.bitrateKbps, pktSize, RX_LISTEN_MS);

    while (true) {
        uint32_t now = millis();
        if ((now - stats.startMs) >= RX_LISTEN_MS) { dualPrintln("RX_DONE timeout"); break; }
        if (stats.received > 0 && (now - lastPktMs) >= RX_SILENCE_MS) {
            dualPrintln("RX_DONE silence"); break;
        }

        // Hardware pin poll — matches proven LR2021Raw.h receive()
        if (digitalRead(PIN_IRQ) == LOW) continue;

        // Read packet
        rfReadFifo(buf, pktSize);

        // Read RSSI before clearing IRQ (status valid until next packet)
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
    dualPrintf("RANGE_RESULT_RX,rx=%lu,unique=%lu,lost=%lu,total=%lu,per=%.2f,elapsed_ms=%lu,throughput_kbps=%.1f,rssi_avg=%.1f,rssi_min=%d,freq=%.1f,bitrate=%d,pktSize=%d",
               (unsigned long)n, (unsigned long)stats.unique, (unsigned long)lost,
               (unsigned long)total, perPct, (unsigned long)stats.elapsedMs, tputKbps,
               rssiAvg, stats.rssiMin, cfg.freqMhz, cfg.bitrateKbps, pktSize);
}

// ─── Config print ────────────────────────────────────────────────────
static void printConfig() {
    dualPrintln("=== FLRC RANGE RX CONFIG ===");
    dualPrintf("  freq=%.1f MHz", cfg.freqMhz);
    dualPrintf("  bitrate=%d kbps", cfg.bitrateKbps);
    dualPrintf("  pktSize=%d bytes", cfg.pktSize);
    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("  radio: %s  Status=0x%02X  IRQ=0x%08lX",
               radioReady ? "INIT" : "NOT_INIT", st, (unsigned long)irq);
    dualPrintf("  listen=%dms  silence=%dms", RX_LISTEN_MS, RX_SILENCE_MS);
    dualPrintln("=============================");
}

static void printHelp() {
    dualPrintln("Commands:");
    dualPrintln("  FREQ <mhz>      Frequency (2400-2480)");
    dualPrintln("  BITRATE <kbps>  FLRC bitrate (2600,1300,650,325)");
    dualPrintln("  PKTLEN <bytes>  Payload size (12-255)");
    dualPrintln("  RUN             Start RX listen session");
    dualPrintln("  INIT            Full radio re-init");
    dualPrintln("  STATUS          Print config");
    dualPrintln("  BOOTSEL         Reboot to BOOTSEL mode");
    dualPrintln("  HELP            This message");
}

// ─── Command processing ──────────────────────────────────────────────
static char cmdBuf[64];
static size_t cmdLen = 0;

static void processCommand(const char *cmd) {
    char verb[16];
    float val = 0;
    int parsed = sscanf(cmd, "%15s %f", verb, &val);

    if (parsed < 1) return;

    if (strcmp(verb, "RUN") == 0) {
        runReceive();
    }
    else if (strcmp(verb, "INIT") == 0) {
        radioReady = rawInitRadio();
    }
    else if (strcmp(verb, "STATUS") == 0) {
        printConfig();
    }
    else if (strcmp(verb, "BOOTSEL") == 0) {
        Serial.println("REBOOT TO BOOTSEL");
        delay(100);
        reset_usb_boot(0, 0);
    }
    else if (strcmp(verb, "HELP") == 0) {
        printHelp();
    }
    else if (strcmp(verb, "POWER") == 0 || strcmp(verb, "COUNT") == 0) {
        // Accepted for command sync with TX — no-op on RX
        dualPrintf("OK (RX no-op for %s)", verb);
    }
    else if (strcmp(verb, "FREQ") == 0 && parsed == 2) {
        if (val < 2400 || val > 2480) {
            dualPrintln("ERR: freq range 2400-2480 MHz");
            return;
        }
        cfg.freqMhz = val;
        rfSetFreq(cfg.freqMhz);
        delay(1);
        dualPrintf("OK FREQ=%.1f MHz", cfg.freqMhz);
    }
    else if (strcmp(verb, "BITRATE") == 0 && parsed == 2) {
        uint16_t br = (uint16_t)val;
        if (br != 2600 && br != 1300 && br != 650 && br != 325) {
            dualPrintln("ERR: bitrate must be 2600,1300,650,325");
            return;
        }
        cfg.bitrateKbps = br;
        rfSetBitrate(cfg.bitrateKbps);
        delay(1);
        dualPrintf("OK BITRATE=%d kbps", cfg.bitrateKbps);
    }
    else if (strcmp(verb, "PKTLEN") == 0 && parsed == 2) {
        uint16_t sz = (uint16_t)val;
        if (sz < 12 || sz > 255) {
            dualPrintln("ERR: pktlen range 12-255");
            return;
        }
        cfg.pktSize = sz;
        rfSetPktSize(cfg.pktSize);
        delay(1);
        dualPrintf("OK PKTLEN=%d bytes", cfg.pktSize);
    }
    else {
        dualPrintf("ERR: unknown command '%s' — type HELP", verb);
    }
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(2000);  // give TinyUSB time to enumerate
    Serial.println("BOOT RX RANGE");
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
    dualPrintln("=== RP2040 FLRC RANGE RX (configurable) ===");
    dualPrintln("Serial commands: FREQ BITRATE PKTLEN RUN INIT STATUS BOOTSEL HELP");

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
    } else {
        dualPrintln("INIT FAILED — type INIT to retry");
    }
    dualPrintln("READY — type commands (or RUN to listen)");
}

void loop() {
    static unsigned long lastHB = 0;
    if (millis() - lastHB > 5000) {
        lastHB = millis();
        Serial1.println("HB alive");
        Serial1.flush();
    }

    for (int src = 0; src < 2; src++) {
        Stream *s = (src == 0) ? (Stream*)&Serial : (Stream*)&Serial1;
        while (s->available()) {
            char c = (char)s->read();
            if (c == '\n' || c == '\r') {
                if (cmdLen > 0) {
                    cmdBuf[cmdLen] = '\0';
                    processCommand(cmdBuf);
                    cmdLen = 0;
                }
            } else if (cmdLen < sizeof(cmdBuf) - 1) {
                cmdBuf[cmdLen++] = c;
            }
        }
    }
}
