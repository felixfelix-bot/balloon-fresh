/*
 * flrc_cont_tx.cpp — Continuous FLRC TX for sustained throughput testing
 *
 * Based on flrc_range_tx_auto.cpp (proven 1377 kbps, 0% loss).
 * Removes the 2000ms inter-burst pause — sends packets continuously.
 *
 * Behavior:
 * - On boot: init radio, wait for RUN command (or auto-start after 3s)
 * - TX loop: clearIrq → clearTxFifo → writeTxFifo → setTx → wait IRQ → loop
 * - No DEADBEEF marker, no pause — pure sustained throughput
 * - LED on during TX
 * - Serial commands for runtime configuration
 *
 * Serial commands:
 *   BITRATE <kbps>  — set FLRC bitrate (2600/2080/1300/1040/650/520/325/260)
 *   COUNT <n>       — set packet count per run
 *   DURATION <sec>  — set max run duration (0 = unlimited by count)
 *   PKTLEN <bytes>  — set payload size (max 255)
 *   POWER <dbm>     — set TX power
 *   RUN             — start TX run
 *   STATUS          — print current config
 *
 * Compile-time defaults: FREQ=2440, BITRATE=2600, PKT_SIZE=127, POWER=12
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13
 *       LED=GP25 LED_ALT=GP16
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

#define SPI_FREQ_HZ     40000000UL  // OPT 4: 20→40 MHz SPI overclock
#define XTAL_MHZ        52.0f

// ─── Compile-time config (overridable via -D flags) ──────────────────
#ifndef TX_FREQ_MHZ
#define TX_FREQ_MHZ     2440.0f
#endif
#ifndef TX_BITRATE_KBPS
#define TX_BITRATE_KBPS 2600
#endif
#ifndef TX_PKT_SIZE
#define TX_PKT_SIZE     255
#endif
#ifndef TX_POWER_DBM
#define TX_POWER_DBM    12.0f
#endif
#ifndef TX_PKT_COUNT
#define TX_PKT_COUNT    0       // 0 = infinite
#endif
#ifndef TX_DURATION_SEC
#define TX_DURATION_SEC 0   // 0 = use COUNT only
#endif
#ifndef TX_AUTO_START
#define TX_AUTO_START   1   // 1 = auto-start after 3s, 0 = wait for RUN
#endif

// Sync word — MUST match RX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// Pre-allocated combined buffer for single-batch FIFO write
static uint8_t fifoCmd[2 + 255];
// Dummy RX buffer for write-only transfers (nullptr crashes on some cores)
static uint8_t spiRxJunk[257];

static volatile bool radioReady = false;

// ─── Runtime config (mutable via serial) ──────────────────────────────
static float    cfgFreq    = TX_FREQ_MHZ;
static uint16_t cfgBitrate = TX_BITRATE_KBPS;
static uint16_t cfgPktSize = TX_PKT_SIZE;
static float    cfgPower   = TX_POWER_DBM;
static uint32_t cfgCount   = TX_PKT_COUNT;
static uint32_t cfgDurationSec = TX_DURATION_SEC;
static bool     autoStart  = TX_AUTO_START;

// ─── SPI helpers (ALL Arduino, no direct HW registers) ───────────────
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
    spiRf.transfer((uint8_t*)buf, spiRxJunk, len);  // SINGLE BATCH — continuous SCK
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
    uint8_t cmd[2] = { 0x01, 0x17 };
    spiRf.transfer(cmd, spiRxJunk, 2);  // SINGLE BATCH
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[6];
    uint8_t dummy[6] = {0, 0, 0, 0, 0, 0};
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(dummy, buf, 6);  // batch read
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

// OPT 3: Batch WRITE_TX_FIFO + SET_TX in one CS-low session
// Saves 1× rfWaitBusy + 1× CS toggle + 1× beginTransaction/endTransaction per packet
static void rfWriteFifoAndTx(const uint8_t *data, size_t len) {
    // Build combined command: WRITE_TX_FIFO(0x0002) + data + SET_TX(0x020D,0,0,0)
    static uint8_t batch[2 + 255 + 5];
    batch[0] = 0x00;  // WRITE_TX_FIFO header MSB
    batch[1] = 0x02;  // WRITE_TX_FIFO header LSB
    memcpy(batch + 2, data, len);
    batch[2 + len]     = 0x02;  // SET_TX opcode MSB
    batch[2 + len + 1] = 0x0D;  // SET_TX opcode LSB
    batch[2 + len + 2] = 0x00;
    batch[2 + len + 3] = 0x00;
    batch[2 + len + 4] = 0x00;

    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(batch, spiRxJunk, 2 + len + 5);  // single continuous SCK burst
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfWriteTxFifo(const uint8_t *data, size_t len) {
    fifoCmd[0] = 0x00;  // header MSB
    fifoCmd[1] = 0x02;  // header LSB (WRITE_TX_FIFO)
    memcpy(fifoCmd + 2, data, len);

    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(fifoCmd, spiRxJunk, 2 + len);  // SINGLE BATCH — continuous SCK
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfClearTxFifo() {
    uint8_t cmd[] = { 0x01, 0x1F };
    rfWriteCmd(cmd, 2);
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
        case 2080: brBw = 0x01; break;
        case 1300: brBw = 0x02; break;
        case 1040: brBw = 0x03; break;
        case 650:  brBw = 0x04; break;
        case 520:  brBw = 0x05; break;
        case 325:  brBw = 0x06; break;
        case 260:  brBw = 0x07; break;
        default:   brBw = 0x00; break;
    }
    uint8_t cmd[] = { 0x02, 0x48, brBw, 0x25 };
    rfWriteCmd(cmd, 4);
}

static void rfSetTxPower(float dbm) {
    uint8_t powerRaw = (uint8_t)(dbm * 2.0f + 0.5f);
    uint8_t cmd[] = { 0x02, 0x03, powerRaw, 0x04 };
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

    { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }  // CLEAR_ERRORS
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; rfWriteCmd(cmd, 3); }  // SET_STANDBY(XOSC)
    delay(5);
    { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; rfWriteCmd(cmd, 3); }  // SET_PACKET_TYPE=FLRC
    delay(1);

    rfSetFreq(cfgFreq);
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }  // SET_RX_PATH(HF)
    delay(1);

    uint16_t feFreq = (uint16_t)((cfgFreq / 4.0f) + 0.5f) | 0x8000;
    {
        uint8_t cmd[] = {
            0x01, 0x23,  // CALIB_FRONT_END
            (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        };
        rfWriteCmd(cmd, 10);
    }
    delay(5);

    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }  // CALIBRATE(0x5F)
    delay(5);

    rfSetBitrate(cfgBitrate);
    delay(1);

    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

    rfSetPktSize(cfgPktSize);
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }  // SET_PA_CONFIG
    delay(1);
    rfSetTxPower(cfgPower);
    delay(1);
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }  // SET_RX_TX_FALLBACK(FS)
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }  // SET_DIO_FUNCTION
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }  // SET_DIO_IRQ_CONFIG (TX_DONE)
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

// ─── Continuous TX run ──────────────────────────────────────────────
static bool txRunning = false;

static void runTransmit() {
    if (!radioReady) return;

    uint16_t pktSize = cfgPktSize;
    uint32_t count = cfgCount;
    uint32_t durationMs = cfgDurationSec > 0 ? (cfgDurationSec * 1000) : 0;

    digitalWrite(PIN_LED, HIGH);
    digitalWrite(PIN_LED_ALT, HIGH);

    dualPrintf("CONT_TX START bitrate=%d pktSize=%d count=%lu duration_ms=%lu power=%.1f",
               cfgBitrate, pktSize, (unsigned long)count,
               (unsigned long)durationMs, cfgPower);

    uint8_t pkt[256];
    for (int j = 4; j < pktSize; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t irqMask = 1UL << PIN_IRQ;
    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    // Determine print interval: every 1000 for fast modes, every 10 for slow
    uint32_t printInterval = (cfgBitrate >= 1000) ? 1000 : 10;

    txRunning = true;
    uint32_t i;
    for (i = 0; txRunning; i++) {
        // Check count limit
        if (count > 0 && i >= count) break;
        // Check duration limit
        if (durationMs > 0 && (millis() - startMs) >= durationMs) break;

        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        // OPT 1+2: Skip rfClearTxFifo() (auto-cleared on TX_DONE)
        //         Skip rfClearIrq() (poll IRQ pin, clear once at start)
        // OPT 3: REVERTED — LR2021 needs CS HIGH between commands to parse opcodes
        rfWriteTxFifo(pkt, pktSize);
        rfSetTx();

        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 500000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
        }

        if (irqFired) {
            txDoneCount++;
            rfClearIrq();  // Clear IRQ after detecting, not before
        } else {
            txTimeoutCount++;
            rfClearIrq();  // Clear any stuck IRQ
        }

        // Progress print
        if (txDoneCount > 0 && (txDoneCount % printInterval) == 0) {
            uint32_t elapsed = millis() - startMs;
            float tput = ((float)txDoneCount * pktSize * 8.0f) / (elapsed > 0 ? elapsed : 1);
            dualPrintf("TX_PROGRESS sent=%lu fired=%lu to=%lu elapsed_ms=%lu tput=%.1fkbps",
                       (unsigned long)(i + 1),
                       (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
                       (unsigned long)elapsed, tput);
        }

        // Check for serial STOP command
        if (Serial.available()) {
            String line = Serial.readStringUntil('\n');
            line.trim();
            line.toUpperCase();
            if (line.startsWith("STOP")) {
                dualPrintln("TX_STOPPED by serial command");
                break;
            }
        }
    }
    txRunning = false;

    uint32_t elapsed = millis() - startMs;
    float tput = (elapsed > 0) ? ((float)txDoneCount * pktSize * 8.0f) / (float)elapsed : 0.0f;

    dualPrintf("CONT_TX DONE sent=%lu fired=%lu to=%lu elapsed_ms=%lu tput=%.1fkbps",
               (unsigned long)i, (unsigned long)txDoneCount,
               (unsigned long)txTimeoutCount, (unsigned long)elapsed, tput);

    // Structured result line for automated parsing
    dualPrintf("SUSTAINED_TX_RESULT,sent=%lu,fired=%lu,timeout=%lu,elapsed_ms=%lu,throughput_kbps=%.1f,bitrate=%d,pktSize=%d,power=%.1f,freq=%.1f",
               (unsigned long)i, (unsigned long)txDoneCount,
               (unsigned long)txTimeoutCount, (unsigned long)elapsed, tput,
               cfgBitrate, pktSize, cfgPower, cfgFreq);

    digitalWrite(PIN_LED, LOW);
    digitalWrite(PIN_LED_ALT, LOW);
}

// ─── Serial command processing ──────────────────────────────────────
static void processSerial() {
    if (!Serial.available() && !Serial1.available()) return;

    String line;
    if (Serial.available()) line = Serial.readStringUntil('\n');
    else line = Serial1.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    String cmd = line;
    cmd.toUpperCase();

    if (cmd.startsWith("BITRATE ")) {
        int val = cmd.substring(8).toInt();
        if (val == 2600 || val == 2080 || val == 1300 || val == 1040 ||
            val == 650 || val == 520 || val == 325 || val == 260) {
            cfgBitrate = val;
            rfSetBitrate(cfgBitrate);
            dualPrintf("BITRATE set to %d kbps", cfgBitrate);
        } else {
            dualPrintln("ERROR: invalid bitrate (2600/2080/1300/1040/650/520/325/260)");
        }
    }
    else if (cmd.startsWith("COUNT ")) {
        cfgCount = (uint32_t)strtoul(cmd.substring(6).c_str(), NULL, 10);
        dualPrintf("COUNT set to %lu", (unsigned long)cfgCount);
    }
    else if (cmd.startsWith("DURATION ")) {
        cfgDurationSec = (uint32_t)strtoul(cmd.substring(9).c_str(), NULL, 10);
        dualPrintf("DURATION set to %lu seconds", (unsigned long)cfgDurationSec);
    }
    else if (cmd.startsWith("PKTLEN ")) {
        int val = cmd.substring(7).toInt();
        if (val > 0 && val <= 255) {
            cfgPktSize = val;
            rfSetPktSize(cfgPktSize);
            dualPrintf("PKTLEN set to %d", cfgPktSize);
        } else {
            dualPrintln("ERROR: invalid pktlen (1-255)");
        }
    }
    else if (cmd.startsWith("POWER ")) {
        cfgPower = cmd.substring(6).toFloat();
        rfSetTxPower(cfgPower);
        dualPrintf("POWER set to %.1f dBm", cfgPower);
    }
    else if (cmd == "RUN") {
        dualPrintln("RUN command received");
        runTransmit();
    }
    else if (cmd == "STOP") {
        txRunning = false;
        dualPrintln("STOP command received");
    }
    else if (cmd == "STATUS") {
        dualPrintf("STATUS: freq=%.1f bitrate=%d pktSize=%d power=%.1f count=%lu duration=%lu autoStart=%d radioReady=%d",
                   cfgFreq, cfgBitrate, cfgPktSize, cfgPower,
                   (unsigned long)cfgCount, (unsigned long)cfgDurationSec,
                   autoStart, radioReady);
    }
    else if (cmd == "INIT") {
        radioReady = rawInitRadio();
    }
    else if (cmd == "HELP") {
        dualPrintln("Commands: BITRATE <kbps> COUNT <n> DURATION <sec> PKTLEN <bytes> POWER <dbm> RUN STOP STATUS INIT HELP");
    }
    else {
        dualPrintf("UNKNOWN: %s (type HELP)", line.c_str());
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

    // 3s countdown blink
    for (int i = 0; i < 6; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH);
        delay(250);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);
        delay(250);
    }

    dualPrintln();
    dualPrintln("=== RP2040 FLRC CONTINUOUS TX ===");
    dualPrintf("Config: freq=%.1f br=%d pktSize=%d power=%.1f count=%lu duration=%lu",
               cfgFreq, cfgBitrate, cfgPktSize, cfgPower,
               (unsigned long)cfgCount, (unsigned long)cfgDurationSec);

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        if (autoStart) {
            dualPrintln("AUTO TX STARTING in 3s — type STOP to abort");
            delay(3000);
            runTransmit();
        } else {
            dualPrintln("READY — type RUN to start TX");
        }
    } else {
        dualPrintln("INIT FAILED — retrying...");
        delay(2000);
        radioReady = rawInitRadio();
        if (radioReady) {
            digitalWrite(PIN_LED_ALT, HIGH);
            if (autoStart) {
                dualPrintln("AUTO TX STARTING (2nd init) in 3s");
                delay(3000);
                runTransmit();
            } else {
                dualPrintln("READY (2nd init) — type RUN to start TX");
            }
        } else {
            dualPrintln("INIT FAILED TWICE — stuck");
        }
    }
}

void loop() {
    processSerial();

    if (!radioReady) {
        // Blink SOS if radio dead
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(500);
    } else if (!txRunning && autoStart) {
        // Auto-start loop: run again after previous run completes
        delay(1000);
        runTransmit();
    }
}