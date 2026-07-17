/*
 * flrc_range_rx.cpp — RP2040 FLRC RX with RUNTIME-CONFIGURABLE parameters
 *
 * Based on flrc_rx_raw.cpp (proven: 997/1000 RX at <1m) but with:
 *   1. TX-matching init protocol (same freq calc, sync word, pkt params)
 *   2. Serial commands to change frequency and packet size at runtime
 *   3. No auto-start — waits for LISTEN command
 *
 * Serial commands (USB CDC or UART GP12/GP13):
 *   FREQ <mhz>    — set RF frequency (2400..2500)
 *   PKTLEN <n>    — set expected payload size (1..255)
 *   LISTEN        — enter RX mode, listen for packets (also: RUN)
 *   RESULTS       — re-print last results
 *   STATUS        — print current config
 *   INIT          — re-initialize radio
 *   HELP          — list commands
 *
 * Output: RESULT,rx=N,unique=N,dup=N,lost=N,total=N,per=PCT,elapsed_ms=N,throughput_kbps=N
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13  LED=GP25 LED_ALT=GP16
 *
 * Init matches flrc_range_tx.cpp exactly: same freq formula, same sync word
 * 0x12AD101B, same packet params register layout.
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

// ─── Defaults (overridable at runtime) ───────────────────────────────
#define SPI_FREQ_HZ     16000000UL  // 16MHz — proven stable
#define XTAL_MHZ        52.0f
#define RX_LISTEN_MS    30000       // max listen window
#define RX_SILENCE_MS   4000        // stop after N ms of silence
#define PRINT_EVERY     100

// Sync word — MUST match TX (flrc_range_tx.cpp)
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── Runtime-configurable parameters ─────────────────────────────────
static volatile float  g_freqMhz   = 2440.0f;
static volatile int    g_pktSize   = 255;

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

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

// ─── SPI helpers ─────────────────────────────────────────────────────
static inline void rfCsLow()  { digitalWrite(PIN_CS, LOW); }
static inline void rfCsHigh() { digitalWrite(PIN_CS, HIGH); }

static inline void rfWaitBusy() {
    uint32_t timeout = millis() + 50;
    while (digitalRead(PIN_BUSY) == HIGH) {
        if (millis() > timeout) return;
    }
}

static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
    rfCsHigh();
    spiRf.endTransaction();
}

static uint8_t rfReadStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    uint8_t st = spiRf.transfer(0x00);
    rfCsHigh();
    spiRf.endTransaction();
    return st;
}

// ─── RX-specific SPI reads (two-phase protocol from proven RX) ───────
static void rfReadFifoTwoPhase(uint8_t *buf, size_t len) {
    // Phase 1: send READ_RX_FIFO command
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    spiRf.transfer(0x00);
    spiRf.transfer(0x01);
    rfCsHigh();
    spiRf.endTransaction();
    rfWaitBusy();

    // Phase 2: read response (2 status bytes + payload)
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    spiRf.transfer(0x00);  // status MSB
    spiRf.transfer(0x00);  // status LSB
    for (size_t i = 0; i < len; i++) buf[i] = spiRf.transfer(0x00);
    rfCsHigh();
    spiRf.endTransaction();
}

static uint32_t rfReadIrqStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    spiRf.transfer(0x01); spiRf.transfer(0x17);
    rfCsHigh();
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[6];
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    for (int i = 0; i < 6; i++) buf[i] = spiRf.transfer(0x00);
    rfCsHigh();
    spiRf.endTransaction();
    return ((uint32_t)buf[2] << 24) | ((uint32_t)buf[3] << 16) |
           ((uint32_t)buf[4] << 8) | (uint32_t)buf[5];
}

static void rfClearIrq() {
    uint8_t cmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 6);
}

static void rfSetRx() {
    // SET_RX with continuous timeout (0xFFFFFF = forever)
    uint8_t cmd[6] = { 0x02, 0x0C, 0x00, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 6);
}

// ─── Runtime parameter setters ───────────────────────────────────────
static void rfSetFrequency(float mhz) {
    // Same formula as TX: frf = (MHz * 2^18) / XTAL_MHZ
    uint32_t frf = (uint32_t)((mhz * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    uint8_t cmd[] = {
        0x02, 0x00,
        (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
    };
    rfWriteCmd(cmd, 5);

    // FE frequency error calibration
    uint16_t feFreq = (uint16_t)((mhz / 4.0f) + 0.5f) | 0x8000;
    uint8_t feCmd[] = {
        0x01, 0x23,
        (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
        0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    };
    rfWriteCmd(feCmd, 10);

    // Re-run calibration
    uint8_t calCmd[] = { 0x01, 0x22, 0x5F };
    rfWriteCmd(calCmd, 3);
    delay(5);
}

static void rfSetPacketSize(int len) {
    if (len < 1) len = 1;
    if (len > 255) len = 255;
    // Same format as TX: preamble=0x0C, sync_len=0x4C, fixed, payloadSize
    uint8_t cmd[] = {
        0x02, 0x49,
        0x0C,  // preamble type
        0x4C,  // sync word length + match
        0x00,  // fixed length
        (uint8_t)len
    };
    rfWriteCmd(cmd, 6);
}

// ─── Full radio init (matches TX init) ───────────────────────────────
static volatile bool radioReady = false;

static bool rawInitRadio() {
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    // Clear errors
    { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // STDBY_RC
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; rfWriteCmd(cmd, 3); }
    delay(5);

    // Packet type FLRC (0x05)
    { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // RF frequency (runtime param)
    rfSetFrequency(g_freqMhz);
    delay(1);

    // PA config / RX path — HF select (bit 7 of byte 0)
    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // FE calibration
    uint16_t feFreq = (uint16_t)((g_freqMhz / 4.0f) + 0.5f) | 0x8000;
    {
        uint8_t cmd[] = {
            0x01, 0x23,
            (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        };
        rfWriteCmd(cmd, 10);
    }
    delay(5);

    // Calibration image
    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
    delay(5);

    // RX fallback mode
    { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x27 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // Sync word — matches TX: 0x12AD101B
    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

    // Packet params (runtime pktSize)
    rfSetPacketSize(g_pktSize);
    delay(1);

    // Modulation params: FLRC 2600 kbps
    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);

    // Buffer base address
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // DIO function: DIO9 = IRQ
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // IRQ enable: RX_DONE + TX_DONE
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x0C, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
    delay(1);

    rfClearIrq();
    delay(1);

    // Verify
    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    uint8_t mode = (st >> 4) & 0x0F;
    if (mode == 0x02 || mode == 0x03 || mode == 0x04 || mode == 0x06 || mode == 0x07 ||
        (irq & 0x00020000)) {
        dualPrintln("RADIO_INIT_OK");
        return true;
    }
    dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
    return (st != 0x00 && st != 0xFF);
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
};

static RxStats stats;

static void resetStats() {
    memset(&stats, 0, sizeof(stats));
    stats.lastSeq = 0xFFFFFFFF;
}

// ─── Receive session ─────────────────────────────────────────────────
static void runReceive() {
    if (!radioReady) { dualPrintln("ERR: radio not initialized — send INIT"); return; }

    resetStats();
    stats.startMs = millis();
    uint32_t lastPktMs = millis();

    int pktSize = g_pktSize;
    uint8_t buf[255];

    rfClearIrq();
    rfSetRx();
    delay(1);

    dualPrintf("RX_START listening freq=%.1f pktSize=%d (max %ds)",
               (double)g_freqMhz, pktSize, RX_LISTEN_MS / 1000);

    bool stopped = false;
    while (!stopped) {
        uint32_t now = millis();
        if ((now - stats.startMs) >= RX_LISTEN_MS) { stopped = true; break; }
        if (stats.received > 0 && (now - lastPktMs) >= RX_SILENCE_MS) {
            dualPrintln("RX_TIMEOUT: silence, stopping");
            stopped = true;
            break;
        }

        // Poll IRQ pin (DIO9) for HIGH = packet received
        if (digitalRead(PIN_IRQ) != HIGH) continue;

        // Read IRQ status
        rfReadIrqStatus();

        // Read FIFO (two-phase)
        rfReadFifoTwoPhase(buf, pktSize);

        // Clear IRQ + re-arm RX
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
            dualPrintln("RX_END: received DEADBEEF end marker");
            break;
        }

        stats.received++;
        if (stats.lastSeq != 0xFFFFFFFF && seq == stats.lastSeq) {
            stats.duplicates++;
        } else {
            stats.unique++;
        }
        stats.lastSeq = seq;
        if (seq > stats.maxSeq) stats.maxSeq = seq;
        lastPktMs = millis();

        if (stats.received <= 5 || (stats.received % PRINT_EVERY) == 0) {
            dualPrintf("PKT rx=%lu seq=%lu",
                       (unsigned long)stats.received, (unsigned long)seq);
        }
    }

    if (stats.elapsedMs == 0) stats.elapsedMs = millis() - stats.startMs;

    // Print results
    uint32_t n = stats.received;
    uint32_t total = stats.totalSentByTx > 0 ? stats.totalSentByTx : (stats.maxSeq + 1);
    uint32_t lost = (total > n) ? (total - n) : 0;
    float perPct = (total > 0) ? (100.0f * (float)lost / (float)total) : 0.0f;
    float tputKbps = (stats.elapsedMs > 0 && n > 0)
                     ? ((float)n * (float)pktSize * 8.0f) / ((float)stats.elapsedMs)
                     : 0.0f;

    dualPrintln("=============================================");
    {
        dualPrintf("  Received:    %lu (unique %lu, dup %lu)",
                   (unsigned long)n, (unsigned long)stats.unique,
                   (unsigned long)stats.duplicates);
        dualPrintf("  TX sent:     %lu  (total %lu)",
                   (unsigned long)stats.totalSentByTx, (unsigned long)total);
        dualPrintf("  Lost:        %lu  (%.2f%%)", (unsigned long)lost, (double)perPct);
        dualPrintf("  Elapsed:     %lu ms", (unsigned long)stats.elapsedMs);
        dualPrintf("  PktSize:     %d bytes", pktSize);
        dualPrintf("  Throughput:  %.1f kbps", (double)tputKbps);
    }
    dualPrintln("=============================================");
    dualPrintf("RESULT_RX,rx=%lu,unique=%lu,dup=%lu,lost=%lu,total=%lu,per=%.2f,elapsed_ms=%lu,throughput_kbps=%.1f,pkt_size=%d",
               (unsigned long)n, (unsigned long)stats.unique, (unsigned long)stats.duplicates,
               (unsigned long)lost, (unsigned long)total, (double)perPct,
               (unsigned long)stats.elapsedMs, (double)tputKbps, pktSize);
}

// ─── Status + help ───────────────────────────────────────────────────
static void printStatus() {
    dualPrintln("=== RANGE RX CONFIG ===");
    dualPrintf("  freq=%.1f MHz", (double)g_freqMhz);
    dualPrintf("  pktSize=%d bytes", g_pktSize);
    dualPrintf("  modulation=FLRC 2600 kbps");
    dualPrintf("  syncWord=0x12AD101B (matches TX)");
    dualPrintf("  radio: %s", radioReady ? "READY" : "NOT_INIT");
    dualPrintf("  SPI=%.2f MHz", SPI_FREQ_HZ / 1e6f);
    dualPrintln("========================");
}

static void printHelp() {
    dualPrintln("=== RANGE RX COMMANDS ===");
    dualPrintln("  FREQ <mhz>    Set RF frequency (2400-2500)");
    dualPrintln("  PKTLEN <n>    Set payload size (1-255)");
    dualPrintln("  LISTEN        Start receiving (alias: RUN)");
    dualPrintln("  RESULTS       Re-print last results");
    dualPrintln("  STATUS        Show current config");
    dualPrintln("  INIT          Re-init radio");
    dualPrintln("  HELP          This message");
    dualPrintln("==========================");
}

// ─── Command parser ──────────────────────────────────────────────────
static char cmdBuf[80];
static uint8_t cmdLen = 0;

static void processCommand(const char *cmd) {
    while (*cmd == ' ' || *cmd == '\t') cmd++;
    if (*cmd == '\0') return;

    char upper[80];
    size_t i;
    for (i = 0; i < 79 && cmd[i]; i++) {
        upper[i] = toupper((unsigned char)cmd[i]);
    }
    upper[i] = '\0';

    if (strncmp(upper, "FREQ ", 5) == 0) {
        float f = strtof(cmd + 5, nullptr);
        if (f >= 2400.0f && f <= 2500.0f) {
            g_freqMhz = f;
            rfSetFrequency(f);
            dualPrintf("OK freq=%.1f MHz", (double)f);
        } else {
            dualPrintln("ERR: freq range 2400..2500 MHz");
        }
    }
    else if (strncmp(upper, "PKTLEN ", 7) == 0) {
        int n = atoi(cmd + 7);
        if (n >= 1 && n <= 255) {
            g_pktSize = n;
            rfSetPacketSize(n);
            dualPrintf("OK pktSize=%d bytes", n);
        } else {
            dualPrintln("ERR: pktlen range 1..255");
        }
    }
    else if (strcmp(upper, "LISTEN") == 0 || strcmp(upper, "RUN") == 0) {
        runReceive();
    }
    else if (strcmp(upper, "RESULTS") == 0) {
        if (stats.received == 0) dualPrintln("No results yet (send LISTEN first)");
        // Results are printed at end of runReceive, re-trigger not stored
    }
    else if (strcmp(upper, "STATUS") == 0 || strcmp(upper, "CONFIG") == 0) {
        printStatus();
    }
    else if (strcmp(upper, "INIT") == 0) {
        dualPrintln("Re-initializing radio...");
        radioReady = rawInitRadio();
    }
    else if (strcmp(upper, "HELP") == 0 || strcmp(upper, "?") == 0) {
        printHelp();
    }
    else {
        dualPrintf("ERR: unknown '%s' (try HELP)", cmd);
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
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(120);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(120);
    }

    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, HIGH);

    spiRf.begin();

    delay(500);

    Serial1.println();
    Serial1.println("=== RP2040 FLRC RANGE RX ===");
    Serial1.println("Runtime-configurable: FREQ/PKTLEN/LISTEN");

    radioReady = rawInitRadio();
    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        dualPrintln("RADIO READY — send commands (HELP for list)");
        printStatus();
    } else {
        dualPrintln("INIT FAILED — type INIT to retry");
    }
    // Do NOT auto-start. Wait for operator commands.
}

void loop() {
    // Heartbeat every 5s
    static unsigned long lastHB = 0;
    if (millis() - lastHB > 5000) {
        lastHB = millis();
        Serial1.println("HB rx_ready");
    }

    // Process commands from USB CDC + UART
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (cmdLen > 0) {
                cmdBuf[cmdLen] = '\0';
                processCommand(cmdBuf);
                cmdLen = 0;
            }
        } else if (cmdLen < (sizeof(cmdBuf) - 1)) {
            cmdBuf[cmdLen++] = c;
        }
    }

    while (Serial1.available()) {
        char c = (char)Serial1.read();
        if (c == '\n' || c == '\r') {
            if (cmdLen > 0) {
                cmdBuf[cmdLen] = '\0';
                processCommand(cmdBuf);
                cmdLen = 0;
            }
        } else if (cmdLen < (sizeof(cmdBuf) - 1)) {
            cmdBuf[cmdLen++] = c;
        }
    }
}
