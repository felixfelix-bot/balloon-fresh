/*
 * flrc_tx_raw.cpp — RP2040 FLRC TX (RadioLib init + raw SPI hot loop)
 *
 * IDENTICAL RadioLib config as flrc_rx_main.cpp — same freq, BR, CR, preamble,
 * shaping, sync word. RadioLib beginFLRC() configures both radios identically.
 * Raw SPI is used ONLY for the per-packet TX hot path (write FIFO → set TX →
 * wait TX_DONE) for minimum inter-packet latency.
 *
 * Auto-transmits 3s after boot. 2000 packets × 255 bytes + DEADBEEF end marker.
 *
 * Build env: rp2040-flrc-tx-raw (earlephilhower core + RadioLib).
 *
 * Pins (pins.h):
 *   SPI0: SCK=GP2, MOSI=GP3, MISO=GP4, CS=GP5
 *   BUSY=GP6, IRQ(DIO9)=GP7, RST=GP8
 *   UART0: TX=GP12, RX=GP13 (Serial1 — survives USB CDC death)
 */

#include <Arduino.h>
#include <SPI.h>
#include <RadioLib.h>
#include <stdarg.h>
#include "pins.h"

// ─── Radio configuration (MUST match flrc_rx_main.cpp EXACTLY) ───────
#define FLRC_FREQ_HZ      2440.0f    // 2.4 GHz
#define FLRC_BR           2600        // bit rate kbps (max)
#define FLRC_CR           RADIOLIB_LR2021_FLRC_CR_1_0   // uncoded
#define FLRC_PWR_DBM      22
#define FLRC_PREAMBLE     16
#define FLRC_SHAPING      RADIOLIB_SHAPING_0_5
#define FLRC_TCXO_V       0.0f        // no TCXO (crystal)
#define FLRC_PKT_SIZE     255         // fixed-length packets
#define SPI_FREQ_HZ       16000000UL  // 16 MHz

#define PKT_COUNT         2000

// ─── LR2021 raw SPI opcodes for TX hot path ──────────────────────────
#define OP_WRITE_TX_FIFO  0x0002u     // + data bytes
#define OP_CLEAR_TX_FIFO  0x011Fu     // clear TX FIFO
#define OP_CLEAR_IRQ      0x0116u     // + 4-byte mask
#define OP_SET_TX         0x020Du     // + periodBase + 3-byte timeout
// TX_DONE is IRQ status bit 19 on the LR2021.
#define IRQ_TX_DONE_BIT   (1UL << 19)

// ─── SPI bus: SPI0 on our pins (shared by RadioLib + raw hot loop) ───
static SPIClassRP2040 spiRf(spi0, PIN_SPI_MISO, PIN_SPI_CS, PIN_SPI_SCK, PIN_SPI_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// ─── RadioLib module on our SPI ─────────────────────────────────────
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

// ─── TX-specific raw SPI commands ───────────────────────────────────
static inline void rfClearTxFifo() {
    uint8_t cmd[2] = { (uint8_t)(OP_CLEAR_TX_FIFO >> 8), (uint8_t)(OP_CLEAR_TX_FIFO & 0xFF) };
    rfRawWrite(cmd, 2);
}

static inline void rfWriteTxFifo(const uint8_t *data, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    spiRf.transfer(0x00); // opcode MSB
    spiRf.transfer(0x02); // opcode LSB (WRITE_TX_FIFO)
    for (size_t i = 0; i < len; i++) spiRf.transfer(data[i]);
    rfCsHigh();
    spiRf.endTransaction();
}

static inline void rfClearIrq() {
    uint8_t cmd[6] = {
        (uint8_t)(OP_CLEAR_IRQ >> 8), (uint8_t)(OP_CLEAR_IRQ & 0xFF),
        0xFF, 0xFF, 0xFF, 0xFF
    };
    rfRawWrite(cmd, 6);
}

static inline void rfSetTx() {
    // SET_TX = 0x020D, timeout=0 (no timeout — single packet)
    uint8_t cmd[6] = { 0x02, 0x0D, 0x00, 0x00, 0x00, 0x00 };
    rfRawWrite(cmd, 6);
}

// ─── Dual output: USB CDC (Serial) + UART (Serial1) ─────────────────
static void dualBegin() {
    Serial.begin(SERIAL_BAUD);
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);
}

static void dualPrintln(const char *s) { Serial.println(s); Serial1.println(s); }
static void dualPrintln() { Serial.println(); Serial1.println(); }
static void dualPrint(const char *s) { Serial.print(s); Serial1.print(s); }
static void dualPrintln(int v) { Serial.println(v); Serial1.println(v); }

static void dualPrintf(const char *fmt, ...) {
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.println(buf);
    Serial1.println(buf);
}

// ─── Radio init (RadioLib — IDENTICAL to flrc_rx_main.cpp) ──────────
static bool initRadio() {
    // DIO9 carries TX_DONE on the NiceRF LR2021.
    radio.irqDioNum = 9;

    int16_t state = radio.beginFLRC(FLRC_FREQ_HZ, FLRC_BR, FLRC_CR, FLRC_PWR_DBM,
                                    FLRC_PREAMBLE, FLRC_SHAPING, FLRC_TCXO_V);
    if (state != RADIOLIB_ERR_NONE) {
        dualPrint("ERR: beginFLRC failed, code ");
        dualPrintln(state);
        return false;
    }

    // Fixed 255-byte packets — matches RX.
    state = radio.fixedPacketLengthMode(FLRC_PKT_SIZE);
    if (state != RADIOLIB_ERR_NONE) {
        dualPrint("ERR: fixedPacketLengthMode failed, code ");
        dualPrintln(state);
        return false;
    }

    // Set sync word to MATCH RX (0xCD05CAFE) — RadioLib default is different!
    state = radio.setFlrcSyncWord(1, 0xCD05CAFE);
    if (state != RADIOLIB_ERR_NONE) {
        dualPrint("ERR: setFlrcSyncWord failed, code ");
        dualPrintln(state);
        return false;
    }

    // Disable CRC — RX has CRC=0, must match
    state = radio.setCRC(0);
    if (state != RADIOLIB_ERR_NONE) {
        dualPrint("ERR: setCRC failed, code ");
        dualPrintln(state);
        return false;
    }

    // Standby RC mode (we'll SET_TX per-packet via raw SPI).
    state = radio.standby();
    if (state != RADIOLIB_ERR_NONE) {
        dualPrint("ERR: standby failed, code ");
        dualPrintln(state);
        return false;
    }

    // Clear any pending IRQs.
    rfClearIrq();

    radioReady = true;
    return true;
}

// ─── TX burst ────────────────────────────────────────────────────────
void runTX() {
    if (!radioReady) {
        dualPrintln("ERR: radio not initialized");
        return;
    }

    dualPrintf("TX: %d packets x %d bytes", PKT_COUNT, FLRC_PKT_SIZE);
    dualPrintln("Starting in 3 seconds...");
    delay(3000);

    uint8_t buf[FLRC_PKT_SIZE];
    uint32_t sentOk = 0, sentErr = 0;
    uint32_t startMs = millis();

    for (uint32_t i = 0; i < PKT_COUNT; i++) {
        // Sequence number (big endian) + payload
        buf[0] = (i >> 24) & 0xFF;
        buf[1] = (i >> 16) & 0xFF;
        buf[2] = (i >> 8) & 0xFF;
        buf[3] = i & 0xFF;
        memset(buf + 4, 0xAA, FLRC_PKT_SIZE - 4);

        // TX hot path: clear FIFO → write packet → clear IRQ → SET_TX
        rfClearTxFifo();
        rfWriteTxFifo(buf, FLRC_PKT_SIZE);
        rfClearIrq();
        rfSetTx();

        // Wait for TX_DONE IRQ (DIO9 pin goes HIGH) or timeout
        uint32_t txStart = micros();
        bool txDone = false;
        while ((micros() - txStart) < 10000) {  // 10ms timeout
            if (digitalRead(PIN_IRQ) == HIGH) {
                uint32_t irq = rfReadIrqStatus();
                if (irq & IRQ_TX_DONE_BIT) {
                    txDone = true;
                    break;
                }
                if (irq & (1UL << 21)) {  // TIMEOUT
                    break;
                }
            }
        }

        if (txDone) {
            sentOk++;
            rfClearIrq();  // clear TX_DONE for next iteration
        } else {
            sentErr++;
        }

        if ((i + 1) % 500 == 0) {
            uint32_t elapsed = millis() - startMs;
            float kbps = (float)(i + 1) * FLRC_PKT_SIZE * 8.0f / (float)elapsed;
            dualPrintf("TX %d/%d (%.1f kbps)", (int)(i + 1), PKT_COUNT, kbps);
        }
    }

    // Send end marker: DEADBEEF + total sent count (big endian)
    delay(10);
    rfClearTxFifo();
    uint8_t endMarker[8] = {
        0xDE, 0xAD, 0xBE, 0xEF,
        (uint8_t)((PKT_COUNT >> 24) & 0xFF),
        (uint8_t)((PKT_COUNT >> 16) & 0xFF),
        (uint8_t)((PKT_COUNT >> 8) & 0xFF),
        (uint8_t)(PKT_COUNT & 0xFF)
    };
    rfWriteTxFifo(endMarker, 8);
    rfClearIrq();
    rfSetTx();
    delay(5);

    uint32_t elapsedMs = millis() - startMs;
    float elapsedSec = elapsedMs / 1000.0f;
    float throughput = (sentOk * FLRC_PKT_SIZE * 8.0f) / (elapsedSec * 1000.0f);

    dualPrintln("=============================================");
    dualPrintln("  TX RESULTS (RadioLib init + raw SPI TX)");
    dualPrintln("=============================================");
    dualPrintf("  Sent OK:    %d / %d", sentOk, PKT_COUNT);
    dualPrintf("  Errors:     %d", sentErr);
    dualPrintf("  Elapsed:    %.2f sec", elapsedSec);
    dualPrintf("  Throughput: %.1f kbps", throughput);
    dualPrintf("  Per-pkt:    %.3f ms", elapsedMs / (float)sentOk);
    dualPrintf("  Pkt rate:   %.1f pkt/s", sentOk / elapsedSec);
    dualPrintln("=============================================");
    dualPrintln("TX COMPLETE - DEADBEEF end marker sent");
}

// ─── Serial command interface ───────────────────────────────────────
static void printConfig() {
    dualPrintln("=== FLRC TX CONFIG ===");
    char b[96];
    snprintf(b, sizeof(b), "  freq=%.1f MHz  BR=%d  CR=0x%02X (uncoded)",
             FLRC_FREQ_HZ, FLRC_BR, (unsigned)FLRC_CR);
    dualPrintln(b);
    snprintf(b, sizeof(b), "  power=%d dBm  preamble=%d  shaping=BT0.5",
             FLRC_PWR_DBM, FLRC_PREAMBLE);
    dualPrintln(b);
    snprintf(b, sizeof(b), "  pktSize=%d  SPI=%.2f MHz  irqDio=%d",
             FLRC_PKT_SIZE, SPI_FREQ_HZ / 1.0e6f, (int)radio.irqDioNum);
    dualPrintln(b);
    snprintf(b, sizeof(b), "  pins: SCK=%d MOSI=%d MISO=%d CS=%d BUSY=%d IRQ=%d RST=%d",
             PIN_SPI_SCK, PIN_SPI_MOSI, PIN_SPI_MISO, PIN_SPI_CS,
             PIN_BUSY, PIN_IRQ, PIN_RST);
    dualPrintln(b);
    snprintf(b, sizeof(b), "  radio: %s", radioReady ? "READY" : "NOT_INIT");
    dualPrintln(b);
    dualPrintln("======================");
}

static void printHelp() {
    dualPrintln("Commands: RUN  CONFIG  HELP");
}

static char cmdBuf[64];
static uint8_t cmdLen = 0;

static void processCommand(const char *cmd) {
    while (*cmd == ' ' || *cmd == '\t') cmd++;
    if (*cmd == '\0') return;

    if (strcmp(cmd, "RUN") == 0 || strcmp(cmd, "run") == 0) {
        runTX();
    } else if (strcmp(cmd, "CONFIG") == 0 || strcmp(cmd, "config") == 0) {
        printConfig();
    } else if (strcmp(cmd, "HELP") == 0 || strcmp(cmd, "help") == 0) {
        printHelp();
    } else {
        dualPrint("ERR: unknown command '");
        dualPrint(cmd);
        dualPrintln("' (try HELP)");
    }
}

// ─── Arduino entry points ───────────────────────────────────────────
void setup() {
    dualBegin();

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(120);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(120);
    }

    dualPrintln();
    dualPrintln("=== RP2040 FLRC TX (RadioLib + raw SPI) ===");
    dualPrintln("RadioLib init + raw SPI TX hot loop");
    delay(50);

    if (initRadio()) {
        dualPrintln("RADIO_INIT_OK");
        digitalWrite(PIN_LED_ALT, HIGH);
    } else {
        dualPrintln("RADIO_INIT_FAILED");
    }

    printHelp();

    // Auto-start TX after 3 seconds
    dualPrintln("AUTO_START in 3 seconds...");
    delay(3000);
    runTX();
}

void loop() {
    // Command parsing over USB CDC + UART
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

    // Heartbeat
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
    delay(1000);
}
