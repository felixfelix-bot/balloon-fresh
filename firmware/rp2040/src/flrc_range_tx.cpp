/*
 * flrc_range_tx.cpp — Configurable RP2040 FLRC TX for range testing
 *
 * Based on flrc_raw_tx.cpp (v4, proven 1377 kbps 0% loss).
 * Adds runtime serial commands to change RF parameters WITHOUT reflashing:
 *
 *   POWER <dbm>      Set TX power (0,3,6,9,12,12.5) — re-sends SET_TX_PARAMS
 *   PKTLEN <bytes>   Set payload size (12-255) — re-sends SET_FLRC_PACKET_PARAMS
 *   FREQ <mhz>       Set frequency (2400-2480) — re-sends SET_RF_FREQUENCY
 *   BITRATE <kbps>   Set FLRC bitrate (2600,1300,650,325) — re-sends SET_FLRC_MOD_PARAMS
 *   COUNT <n>        Set packet count for next RUN (1-65535)
 *   RUN              Start TX burst with current params
 *   INIT             Full radio re-init (reset + all registers)
 *   STATUS           Print current config + radio status
 *   HELP             Command list
 *
 * Both TX and RX must have matching FREQ, BITRATE, PKTLEN, and SYNC_WORD.
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13
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

#define SPI_FREQ_HZ     20000000UL
#define XTAL_MHZ        52.0f

// Sync word — MUST match RX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── Runtime config (mutable via serial commands) ─────────────────────
struct TxConfig {
    float    freqMhz;     // 2400-2480
    uint16_t bitrateKbps; // 2600,1300,650,325
    uint16_t pktSize;     // 12-255
    float    txPowerDbm;  // 0,3,6,9,12,12.5
    uint16_t pktCount;    // packets per RUN burst
};
static TxConfig cfg = {
    .freqMhz = 2440.0f,
    .bitrateKbps = 2600,
    .pktSize = 255,
    .txPowerDbm = 12.0f,
    .pktCount = 1000,
};

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

static volatile bool radioReady = false;

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

static void rfClearTxFifo() {
    uint8_t cmd[] = { 0x01, 0x1F };
    rfWriteCmd(cmd, 2);
}

// ─── Runtime parameter setters (partial register writes) ─────────────

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
        default:   return 0x00;  // default 2600
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
    // SET_FLRC_MOD_PARAMS (0x0248): [brBw, crBt]
    // brBw from bitrate, CR_1_0=0x02<<4, BT_0_5=0x05 → crBt=0x25
    uint8_t brBw = bitrateToBrBw(kbps);
    uint8_t cmd[] = { 0x02, 0x48, brBw, 0x25 };
    rfWriteCmd(cmd, 4);
}

static void rfSetTxPower(float dbm) {
    // SET_TX_PARAMS (0x0203): [power_raw, rampTime]
    // power_raw = dbm * 2 (register uses 0.5 dB steps)
    uint8_t powerRaw = (uint8_t)(dbm * 2.0f + 0.5f);
    uint8_t cmd[] = { 0x02, 0x03, powerRaw, 0x04 }; // 0x04 = 20us ramp
    rfWriteCmd(cmd, 4);
}

static void rfSetPktSize(uint16_t size) {
    // SET_FLRC_PACKET_PARAMS (0x0249): [preambleSync, control, payloadLenHi, payloadLenLo]
    // preamble idx=2 (8 sym) | syncLen=4/2=2 → byte0=0x0C
    // syncTx=1|syncMatch=1|fixed=1|crc=0 → byte1=0x4C
    uint8_t cmd[] = {
        0x02, 0x49,
        0x0C,
        0x4C,
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

    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);
    rfSetTxPower(cfg.txPowerDbm);
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
        dualPrintln("RADIO_INIT_OK");
        return true;
    }
    dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

// ─── TX burst ────────────────────────────────────────────────────────
static void runTransmit() {
    if (!radioReady) { dualPrintln("ERR: radio not initialized — type INIT"); return; }

    uint16_t pktSize = cfg.pktSize;
    uint16_t count = cfg.pktCount;

    dualPrintf("TX_START count=%d pktSize=%d freq=%.1f br=%d power=%.1f",
               count, pktSize, cfg.freqMhz, cfg.bitrateKbps, cfg.txPowerDbm);

    uint8_t pkt[256]; // max FLRC payload
    for (int j = 4; j < pktSize; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t irqMask = 1UL << PIN_IRQ;
    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    for (int i = 0; i < count; i++) {
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        rfClearIrq();
        rfWriteTxFifo(pkt, pktSize);
        rfSetTx();

        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 500000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
        }

        if (i < 5) {
            uint8_t stPost = rfReadStatus();
            uint32_t irqStatus = rfReadIrqStatus();
            dualPrintf("PKT %d: irqPin=%d st=0x%02X IRQ=0x%08lX spin=%lu",
                       i, irqFired ? 1 : 0, stPost,
                       (unsigned long)irqStatus, (unsigned long)spinCount);
        }

        if (irqFired) txDoneCount++;
        else txTimeoutCount++;

        if ((i + 1) % 200 == 0) {
            dualPrintf("TX %d/%d (done=%lu to=%lu)",
                       i + 1, count,
                       (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);
        }
    }

    dualPrintf("TX_DONE_STATS: fired=%lu timeout=%lu",
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);

    // DEADBEEF end marker — RX reads total packet count from this
    pkt[0] = 0xDE; pkt[1] = 0xAD; pkt[2] = 0xBE; pkt[3] = 0xEF;
    pkt[4] = (uint8_t)(count >> 24);
    pkt[5] = (uint8_t)(count >> 16);
    pkt[6] = (uint8_t)(count >> 8);
    pkt[7] = (uint8_t)(count & 0xFF);
    rfClearTxFifo();
    rfWriteTxFifo(pkt, pktSize);
    rfSetTx();
    delay(5);

    uint32_t elapsed = millis() - startMs;
    float tput = ((float)count * pktSize * 8.0f) / elapsed;

    dualPrintln("=============================================");
    dualPrintf("  TX sent:     %d", count);
    dualPrintf("  Elapsed:     %lu ms", (unsigned long)elapsed);
    dualPrintf("  TX THROUGHPUT: %.1f kbps", tput);
    dualPrintln("=============================================");
    // Structured result line for automated parsing
    dualPrintf("RANGE_RESULT_TX,sent=%d,pktSize=%d,elapsed_ms=%lu,throughput_kbps=%.1f,freq=%.1f,bitrate=%d,power=%.1f",
               count, pktSize, (unsigned long)elapsed, tput,
               cfg.freqMhz, cfg.bitrateKbps, cfg.txPowerDbm);
}

// ─── Config print ────────────────────────────────────────────────────
static void printConfig() {
    dualPrintln("=== FLRC RANGE TX CONFIG ===");
    dualPrintf("  freq=%.1f MHz", cfg.freqMhz);
    dualPrintf("  bitrate=%d kbps", cfg.bitrateKbps);
    dualPrintf("  pktSize=%d bytes", cfg.pktSize);
    dualPrintf("  txPower=%.1f dBm", cfg.txPowerDbm);
    dualPrintf("  pktCount=%d", cfg.pktCount);
    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("  radio: %s  Status=0x%02X  IRQ=0x%08lX",
               radioReady ? "INIT" : "NOT_INIT", st, (unsigned long)irq);
    dualPrintln("============================");
}

static void printHelp() {
    dualPrintln("Commands:");
    dualPrintln("  POWER <dbm>     TX power (0,3,6,9,12,12.5)");
    dualPrintln("  PKTLEN <bytes>  Payload size (12-255)");
    dualPrintln("  FREQ <mhz>      Frequency (2400-2480)");
    dualPrintln("  BITRATE <kbps>  FLRC bitrate (2600,1300,650,325)");
    dualPrintln("  COUNT <n>       Packet count (1-65535)");
    dualPrintln("  RUN             Start TX burst");
    dualPrintln("  INIT            Full radio re-init");
    dualPrintln("  STATUS          Print config");
    dualPrintln("  HELP            This message");
}

// ─── Command processing ──────────────────────────────────────────────
static char cmdBuf[64];
static size_t cmdLen = 0;

static void processCommand(const char *cmd) {
    // Parse "CMD" or "CMD VALUE"
    char verb[16];
    float val = 0;
    int parsed = sscanf(cmd, "%15s %f", verb, &val);

    if (parsed < 1) return;

    if (strcmp(verb, "RUN") == 0) {
        runTransmit();
    }
    else if (strcmp(verb, "INIT") == 0) {
        radioReady = rawInitRadio();
    }
    else if (strcmp(verb, "STATUS") == 0) {
        printConfig();
    }
    else if (strcmp(verb, "HELP") == 0) {
        printHelp();
    }
    else if (strcmp(verb, "POWER") == 0 && parsed == 2) {
        if (val < 0 || val > 12.5) {
            dualPrintln("ERR: power range 0-12.5 dBm");
            return;
        }
        cfg.txPowerDbm = val;
        rfSetTxPower(cfg.txPowerDbm);
        delay(1);
        dualPrintf("OK POWER=%.1f dBm", cfg.txPowerDbm);
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
    else if (strcmp(verb, "COUNT") == 0 && parsed == 2) {
        uint16_t c = (uint16_t)val;
        if (c < 1 || c > 65535) {
            dualPrintln("ERR: count range 1-65535");
            return;
        }
        cfg.pktCount = c;
        dualPrintf("OK COUNT=%d", cfg.pktCount);
    }
    else {
        dualPrintf("ERR: unknown command '%s' — type HELP", verb);
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

    dualPrintln();
    dualPrintln("=== RP2040 FLRC RANGE TX (configurable) ===");
    dualPrintln("Serial commands: POWER PKTLEN FREQ BITRATE COUNT RUN INIT STATUS HELP");

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
    // Do NOT auto-run — wait for explicit RUN command (range test protocol)
    dualPrintln("READY — type commands");
}

void loop() {
    static unsigned long lastHB = 0;
    if (millis() - lastHB > 5000) {
        lastHB = millis();
        Serial1.println("HB alive");
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
