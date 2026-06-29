/*
 * flrc_rx_main.cpp — RP2040 FLRC Speed RX (RadioLib init + raw SPI hot loop)
 *
 * Receives FLRC packets from the ESP32 TX at maximum speed
 * (2450 MHz, BR=2600, uncoded, 255-byte fixed). RadioLib's beginFLRC() is
 * used for correct modulation configuration; the per-packet hot path is a
 * tight raw-SPI loop (read FIFO → clear IRQ → re-arm RX) using the same SPI0
 * bus, bypassing RadioLib's heavier per-packet readData() for minimum latency.
 *
 * This is the RX half of the speed-record test. Build env: rp2040-flrc-rx.
 * (Does NOT touch main.cpp / radio.cpp — the UART coprocessor firmware.)
 *
 * Hardware (pins.h):
 *   SPI0: SCK=GP2, MOSI=GP3, MISO=GP4, CS=GP5
 *   BUSY=GP6, IRQ(DIO9)=GP7, RST=GP8
 *
 * Serial commands (USB CDC, 115200):
 *   RUN     — start receiving (stops on DEADBEEF end marker or silence timeout)
 *   CONFIG  — print current radio configuration
 *   RESULTS — print accumulated statistics
 *   HELP    — list commands
 */

#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>
#include "pins.h"

// ─── Radio configuration ────────────────────────────────────────────
#define FLRC_FREQ_HZ      2450.0f    // 2.4 GHz
#define FLRC_BR           2600        // bit rate kbps (max)
#define FLRC_CR           RADIOLIB_LR2021_FLRC_CR_1_0   // uncoded
#define FLRC_PWR_DBM      22
#define FLRC_PREAMBLE     16
#define FLRC_SHAPING      RADIOLIB_SHAPING_0_5
#define FLRC_TCXO_V       0.0f        // no TCXO (crystal)
#define FLRC_PKT_SIZE     255         // fixed-length packets
#define SPI_FREQ_HZ       16000000UL  // 16 MHz (LR2021 SPI max ~18 MHz)

// LR2021 SPI opcodes — verified against RadioLib LR2021_commands.h.
// NOTE: the existing radio.h/radio.cpp use a WRONG FIFO opcode (0x0200 = SET_RF)
// and a wrong RX_DONE bit (3 instead of 19). This file uses the correct values
// inline and does not depend on radio.h.
#define OP_READ_RX_FIFO   0x0001u     // followed by <len> bytes read
#define OP_CLEAR_IRQ      0x0116u     // + 4-byte mask (0xFFFFFFFF = all)
#define OP_SET_RX         0x020Cu     // + periodBase + 3-byte timeout
// RX_DONE is IRQ status bit 19 on the LR2021 (not bit 3).
#define IRQ_RX_DONE_BIT   (1UL << 19)
// SET_RX timeout = RADIOLIB_LR2021_RX_TIMEOUT_INF (0xFFFFFF) = continuous RX.
#define RX_TIMEOUT_INF    0xFFFFFFul

#define RX_LISTEN_MS      12000       // hard cap on a RUN session
#define RX_SILENCE_MS     3000        // stop after this much silence (once started)
#define PRINT_EVERY       100         // progress line cadence

// ─── SPI bus: SPI0 on our pins (shared by RadioLib + raw hot loop) ───
// The mbed core's global `SPI` is on GP16/18/19, so we MUST bring our own
// MbedSPI and hand it to RadioLib via the Module(SPIClass&) constructor.
static MbedSPI spiRf(PIN_SPI_MOSI, PIN_SPI_MISO, PIN_SPI_SCK);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// ─── RadioLib module on our SPI ─────────────────────────────────────
// Module(cs, irq, rst, busy/gpio, SPIClass&, SPISettings)
static Module radioMod(PIN_SPI_CS, PIN_IRQ, PIN_RST, PIN_BUSY, spiRf, spiSettings);
static LR2021 radio(&radioMod);

static volatile bool radioReady = false;

// ─── Raw SPI helpers (same SPI0 bus, manual NSS + BUSY) ─────────────
static inline void rfCsLow()  { digitalWrite(PIN_SPI_CS, LOW); }
static inline void rfCsHigh() { digitalWrite(PIN_SPI_CS, HIGH); }
static inline void rfWaitBusy() {
    while (digitalRead(PIN_BUSY) == HIGH) { /* spin until chip ready */ }
}

static void rfRawWrite(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
    rfCsHigh();
    spiRf.endTransaction();
}

static void rfRawRead(const uint8_t *cmd, size_t cmdLen, uint8_t *out, size_t outLen) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    for (size_t i = 0; i < cmdLen; i++) spiRf.transfer(cmd[i]);
    for (size_t i = 0; i < outLen; i++) out[i] = spiRf.transfer(0x00);
    rfCsHigh();
    spiRf.endTransaction();
}

// Read `len` bytes from the RX FIFO (READ_RX_FIFO = 0x0001, big-endian opcode).
static inline void rfReadFifo(uint8_t *buf, size_t len) {
    uint8_t cmd[2] = { (uint8_t)(OP_READ_RX_FIFO >> 8), (uint8_t)(OP_READ_RX_FIFO & 0xFF) };
    rfRawRead(cmd, 2, buf, len);
}

// Clear all IRQ flags (CLEAR_IRQ = 0x0116 + mask 0xFFFFFFFF).
static inline void rfClearIrq() {
    uint8_t cmd[6] = {
        (uint8_t)(OP_CLEAR_IRQ >> 8), (uint8_t)(OP_CLEAR_IRQ & 0xFF),
        0xFF, 0xFF, 0xFF, 0xFF
    };
    rfRawWrite(cmd, 6);
}

// Re-arm continuous RX (SET_RX = 0x020C, periodBase=0, timeout=0xFFFFFF = INF).
static inline void rfSetRx() {
    uint8_t cmd[6] = {
        (uint8_t)(OP_SET_RX >> 8), (uint8_t)(OP_SET_RX & 0xFF),
        0x00,
        (uint8_t)(RX_TIMEOUT_INF >> 16), (uint8_t)(RX_TIMEOUT_INF >> 8),
        (uint8_t)(RX_TIMEOUT_INF & 0xFF)
    };
    rfRawWrite(cmd, 6);
}

// ─── Statistics ─────────────────────────────────────────────────────
struct RxStats {
    uint32_t received;        // total packets read
    uint32_t unique;          // seq advanced
    uint32_t duplicates;      // seq unchanged
    uint32_t crcErrors;       // (CRC handled by radio; count if needed)
    uint32_t lastSeq;
    uint32_t maxSeq;          // highest seq seen (for loss estimate)
    uint32_t totalSentByTx;   // from DEADBEEF end marker
    uint32_t startMs;
    uint32_t elapsedMs;

    // per-packet hot-path timing (microseconds)
    uint32_t minTotalUs;
    uint32_t maxTotalUs;
    uint64_t sumTotalUs;
    uint32_t irqToReadMin, irqToReadMax, irqToReadSum;
    uint32_t readClrMin,   readClrMax,   readClrSum;
    uint32_t clrRxMin,     clrRxMax,     clrRxSum;
};

static RxStats stats;

static void resetStats() {
    memset(&stats, 0, sizeof(stats));
    stats.lastSeq = 0xFFFFFFFF;
    stats.minTotalUs = 0xFFFFFFFF;
    stats.irqToReadMin = 0xFFFFFFFF;
    stats.readClrMin = 0xFFFFFFFF;
    stats.clrRxMin = 0xFFFFFFFF;
}

static inline void accMin(uint32_t &mn, uint32_t v) { if (v < mn) mn = v; }
static inline void accMax(uint32_t &mx, uint32_t v) { if (v > mx) mx = v; }

// ─── Radio init (RadioLib for modulation, then arm RX) ──────────────
static bool initRadio() {
    // DIO9 carries RX_DONE on the NiceRF LR2021.
    radio.irqDioNum = 9;

    int16_t state = radio.beginFLRC(FLRC_FREQ_HZ, FLRC_BR, FLRC_CR, FLRC_PWR_DBM,
                                    FLRC_PREAMBLE, FLRC_SHAPING, FLRC_TCXO_V);
    if (state != RADIOLIB_ERR_NONE) {
        Serial.print("ERR: beginFLRC failed, code ");
        Serial.println(state);
        return false;
    }

    // Fixed 255-byte packets → we can read the FIFO without querying length.
    state = radio.fixedPacketLengthMode(FLRC_PKT_SIZE);
    if (state != RADIOLIB_ERR_NONE) {
        Serial.print("ERR: fixedPacketLengthMode failed, code ");
        Serial.println(state);
        return false;
    }

    // Arm RX (configures DIO IRQ mapping + enters continuous RX). After this
    // we take over the hot path with raw SPI; DIO9 stays mapped to RX_DONE.
    state = radio.startReceive();
    if (state != RADIOLIB_ERR_NONE) {
        Serial.print("ERR: startReceive failed, code ");
        Serial.println(state);
        return false;
    }

    radioReady = true;
    return true;
}

// ─── Receive session ────────────────────────────────────────────────
static void printResultsInline();  // forward declaration

static void runReceive() {
    if (!radioReady) {
        Serial.println("ERR: radio not initialized");
        return;
    }

    resetStats();
    stats.startMs = millis();
    uint32_t lastPktMs = millis();

    uint8_t buf[FLRC_PKT_SIZE];

    Serial.println("RX_START listening for FLRC packets...");
    Serial.println("pkt,seq,irq2read_us,read2clr_us,clr2rx_us,total_us");

    bool stopped = false;
    while (!stopped) {
        uint32_t now = millis();
        // Stop on hard cap, or on silence once we have started receiving.
        if ((now - stats.startMs) >= RX_LISTEN_MS) { stopped = true; break; }
        if (stats.received > 0 && (now - lastPktMs) >= RX_SILENCE_MS) {
            Serial.println("RX_TIMEOUT: silence, stopping");
            stopped = true; break;
        }

        // RX_DONE is signaled on the DIO9 IRQ pin (configured by startReceive).
        if (digitalRead(PIN_IRQ) != HIGH) continue;

        uint32_t tIrq = micros();

        // 1. Read the full 255-byte packet from the FIFO.
        rfReadFifo(buf, FLRC_PKT_SIZE);
        uint32_t tRead = micros();

        // 2. Clear IRQ flags (de-asserts DIO9).
        rfClearIrq();
        uint32_t tClr = micros();

        // 3. Re-arm continuous RX immediately.
        rfSetRx();
        uint32_t tRx = micros();

        // Extract big-endian seq# from first 4 bytes.
        uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                       ((uint32_t)buf[2] << 8)  | (uint32_t)buf[3];

        // DEADBEEF end marker: {DE AD BE EF, totalSent(4 bytes big-endian)}
        if (buf[0] == 0xDE && buf[1] == 0xAD &&
            buf[2] == 0xBE && buf[3] == 0xEF) {
            stats.totalSentByTx = ((uint32_t)buf[4] << 24) | ((uint32_t)buf[5] << 16) |
                                  ((uint32_t)buf[6] << 8)  | (uint32_t)buf[7];
            stats.elapsedMs = millis() - stats.startMs;
            Serial.println("RX_END: received DEADBEEF end marker");
            break;
        }

        // Counting
        stats.received++;
        if (stats.lastSeq != 0xFFFFFFFF && seq == stats.lastSeq) {
            stats.duplicates++;
        } else {
            stats.unique++;
        }
        stats.lastSeq = seq;
        if (seq > stats.maxSeq) stats.maxSeq = seq;

        // Per-packet timing accumulation
        uint32_t irq2read = tRead - tIrq;
        uint32_t read2clr = tClr - tRead;
        uint32_t clr2rx   = tRx - tClr;
        uint32_t total    = tRx - tIrq;

        accMin(stats.irqToReadMin, irq2read); accMax(stats.irqToReadMax, irq2read); stats.irqToReadSum += irq2read;
        accMin(stats.readClrMin,   read2clr); accMax(stats.readClrMax,   read2clr); stats.readClrSum   += read2clr;
        accMin(stats.clrRxMin,     clr2rx);   accMax(stats.clrRxMax,     clr2rx);   stats.clrRxSum     += clr2rx;
        accMin(stats.minTotalUs,   total);    accMax(stats.maxTotalUs,   total);    stats.sumTotalUs   += total;

        lastPktMs = millis();

        // Per-packet CSV (first few + every PRINT_EVERY)
        if (stats.received <= 5 || (stats.received % PRINT_EVERY) == 0) {
            char line[80];
            snprintf(line, sizeof(line), "%lu,%lu,%lu,%lu,%lu,%lu",
                     (unsigned long)stats.received, (unsigned long)seq,
                     (unsigned long)irq2read, (unsigned long)read2clr,
                     (unsigned long)clr2rx, (unsigned long)total);
            Serial.println(line);
        }
    }

    if (stats.elapsedMs == 0) stats.elapsedMs = millis() - stats.startMs;
    printResultsInline();
}

// Print results immediately at end of a RUN session.
static void printResultsInline() {
    uint32_t n = stats.received;
    uint32_t total = stats.totalSentByTx > 0 ? stats.totalSentByTx
                     : (stats.maxSeq + 1);     // estimate from highest seq
    uint32_t lost  = (total > n) ? (total - n) : 0;
    float perPct   = (total > 0) ? (100.0f * (float)lost / (float)total) : 0.0f;
    float tputKbps = (stats.elapsedMs > 0 && n > 0)
                     ? ((float)n * (float)FLRC_PKT_SIZE * 8.0f) / ((float)stats.elapsedMs)   // kbps
                     : 0.0f;
    float avgTotal = (n > 0) ? ((float)stats.sumTotalUs / (float)n) : 0.0f;

    Serial.println("=============================================");
    {
        char b[96];
        snprintf(b, sizeof(b), "  Received:    %lu (unique %lu, dup %lu)",
                 (unsigned long)n, (unsigned long)stats.unique,
                 (unsigned long)stats.duplicates);
        Serial.println(b);
        snprintf(b, sizeof(b), "  TX sent:     %lu  (est total %lu)",
                 (unsigned long)stats.totalSentByTx, (unsigned long)total);
        Serial.println(b);
        snprintf(b, sizeof(b), "  Lost:        %lu  (%.2f%%)", (unsigned long)lost, perPct);
        Serial.println(b);
        snprintf(b, sizeof(b), "  Elapsed:     %lu ms", (unsigned long)stats.elapsedMs);
        Serial.println(b);
        snprintf(b, sizeof(b), "  Throughput:  %.1f kbps", tputKbps);
        Serial.println(b);
        snprintf(b, sizeof(b), "  Hot-path us: total min=%lu avg=%.0f max=%lu",
                 (unsigned long)stats.minTotalUs, avgTotal, (unsigned long)stats.maxTotalUs);
        Serial.println(b);
        if (n > 0) {
            snprintf(b, sizeof(b), "    irq->read  min=%lu avg=%lu max=%lu",
                     (unsigned long)stats.irqToReadMin,
                     (unsigned long)(stats.irqToReadSum / n),
                     (unsigned long)stats.irqToReadMax);
            Serial.println(b);
            snprintf(b, sizeof(b), "    read->clr  min=%lu avg=%lu max=%lu",
                     (unsigned long)stats.readClrMin,
                     (unsigned long)(stats.readClrSum / n),
                     (unsigned long)stats.readClrMax);
            Serial.println(b);
            snprintf(b, sizeof(b), "    clr->rx    min=%lu avg=%lu max=%lu",
                     (unsigned long)stats.clrRxMin,
                     (unsigned long)(stats.clrRxSum / n),
                     (unsigned long)stats.clrRxMax);
            Serial.println(b);
        }
    }
    Serial.println("=============================================");

    // Machine-readable RESULT line (mirrors the bench format)
    {
        char b[160];
        snprintf(b, sizeof(b),
                 "RESULT,rx=%lu,unique=%lu,dup=%lu,lost=%lu,total=%lu,per=%.2f,elapsed_ms=%lu,throughput_kbps=%.1f,tot_us_avg=%.0f,tot_us_min=%lu,tot_us_max=%lu",
                 (unsigned long)n, (unsigned long)stats.unique, (unsigned long)stats.duplicates,
                 (unsigned long)lost, (unsigned long)total, perPct,
                 (unsigned long)stats.elapsedMs, tputKbps, avgTotal,
                 (unsigned long)stats.minTotalUs, (unsigned long)stats.maxTotalUs);
        Serial.println(b);
    }
}

// ─── Serial command interface ───────────────────────────────────────
static void printConfig() {
    Serial.println("=== FLRC RX CONFIG ===");
    char b[96];
    snprintf(b, sizeof(b), "  freq=%.1f MHz  BR=%d  CR=0x%02X (uncoded)",
             FLRC_FREQ_HZ, FLRC_BR, (unsigned)FLRC_CR);
    Serial.println(b);
    snprintf(b, sizeof(b), "  power=%d dBm  preamble=%d  shaping=BT0.5",
             FLRC_PWR_DBM, FLRC_PREAMBLE);
    Serial.println(b);
    snprintf(b, sizeof(b), "  pktSize=%d  SPI=%.2f MHz  irqDio=%d",
             FLRC_PKT_SIZE, SPI_FREQ_HZ / 1.0e6f, (int)radio.irqDioNum);
    Serial.println(b);
    snprintf(b, sizeof(b), "  pins: SCK=%d MOSI=%d MISO=%d CS=%d BUSY=%d IRQ=%d RST=%d",
             PIN_SPI_SCK, PIN_SPI_MOSI, PIN_SPI_MISO, PIN_SPI_CS,
             PIN_BUSY, PIN_IRQ, PIN_RST);
    Serial.println(b);
    snprintf(b, sizeof(b), "  radio: %s  listen_cap=%dms  silence=%dms",
             radioReady ? "READY" : "NOT_INIT", RX_LISTEN_MS, RX_SILENCE_MS);
    Serial.println(b);
    Serial.println("======================");
}

static void printHelp() {
    Serial.println("Commands: RUN  CONFIG  RESULTS  HELP");
}

static char cmdBuf[64];
static uint8_t cmdLen = 0;

static void processCommand(const char *cmd) {
    while (*cmd == ' ' || *cmd == '\t') cmd++;
    if (*cmd == '\0') return;

    if (strcmp(cmd, "RUN") == 0 || strcmp(cmd, "run") == 0) {
        runReceive();
    } else if (strcmp(cmd, "CONFIG") == 0 || strcmp(cmd, "config") == 0) {
        printConfig();
    } else if (strcmp(cmd, "RESULTS") == 0 || strcmp(cmd, "results") == 0) {
        if (stats.received == 0) {
            Serial.println("No results yet (send RUN first)");
        } else {
            printResultsInline();
        }
    } else if (strcmp(cmd, "HELP") == 0 || strcmp(cmd, "help") == 0) {
        printHelp();
    } else {
        Serial.print("ERR: unknown command '");
        Serial.print(cmd);
        Serial.println("' (try HELP)");
    }
}

// ─── Arduino entry points ───────────────────────────────────────────
void setup() {
    Serial.begin(SERIAL_BAUD);
    // Brief LED blink to confirm boot.
    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(120);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(120);
    }

    Serial.println();
    Serial.println("=== RP2040 FLRC Speed RX ===");
    Serial.println("RadioLib init + raw SPI hot loop");
    delay(50);

    if (initRadio()) {
        Serial.println("RADIO_INIT_OK");
        digitalWrite(PIN_LED_ALT, HIGH);  // steady on = ready
    } else {
        Serial.println("RADIO_INIT_FAILED — type CONFIG, check wiring");
    }

    resetStats();
    printHelp();
}

void loop() {
    // Line-buffered command parsing over USB CDC.
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
}
