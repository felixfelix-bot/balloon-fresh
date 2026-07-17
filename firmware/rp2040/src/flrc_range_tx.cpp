/*
 * flrc_range_tx.cpp — RP2040 FLRC TX with RUNTIME-CONFIGURABLE parameters
 *
 * Based on flrc_raw_tx.cpp v4 (proven: 1377 kbps, 1000/1000 TX_DONE).
 * Extends with serial commands to change TX power, packet size, frequency,
 * and packet count at runtime — avoids reflashing between range test points.
 *
 * Serial commands (USB CDC or UART GP12/GP13):
 *   POWER <dbm>   — set TX power (0..12.5, stored as power*2)
 *   PKTLEN <n>    — set packet payload size (1..255)
 *   FREQ <mhz>    — set RF frequency (2400..2500 MHz)
 *   COUNT <n>     — set packet count for next RUN burst
 *   RUN           — transmit burst at current settings
 *   STATUS        — print current config
 *   INIT          — re-initialize radio
 *   HELP          — list commands
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13  LED=GP25 LED_ALT=GP16
 *
 * LR2021 register protocol (Semtech Gen 4, 0x01=read 0x02=write prefix):
 *   Reg 0x00 (3B): RF frequency  frf = (MHz * 2^18) / XTAL_MHZ
 *   Reg 0x01 (2B): PA config     {0x01, 0x00}  (HF PA select bit 7)
 *   Reg 0x03 (2B): TX params     {power*2, ramp=0x04}
 *   Reg 0x49 (4B): Packet params {preamble, syncWordLen, variableLen, payloadSize}
 *   Reg 0x23 (8B): FE cal        feFreq = (MHz/4 + 0.5) | 0x8000
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

// ─── Defaults (compile-time fallbacks, overridable at runtime) ───────
#define SPI_FREQ_HZ     16000000UL  // 16MHz — proven stable
#define XTAL_MHZ        52.0f

// Sync word — MUST match RX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── Runtime-configurable parameters ─────────────────────────────────
static volatile float  g_freqMhz   = 2440.0f;   // RF frequency MHz
static volatile int    g_powerDbm  = 12;         // TX power dBm
static volatile int    g_pktSize   = 255;        // payload bytes
static volatile int    g_pktCount  = 1000;       // packets per burst

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// ─── Dual output (USB CDC + UART) ────────────────────────────────────
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

// ─── SPI helpers (Arduino-only, CDC-safe) ────────────────────────────
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

// ─── Runtime parameter setters ───────────────────────────────────────
// These update specific LR2021 registers without full re-init.

static void rfSetFrequency(float mhz) {
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

static void rfSetTxPower(int dbm) {
    // LR2021 expects power register value doubled
    uint8_t p = (uint8_t)(dbm * 2);
    if (dbm == 12.5) p = 0x19;  // 12.5 dBm special case (0x0D * 2 rounded)
    uint8_t cmd[] = { 0x02, 0x03, p, 0x04 };
    rfWriteCmd(cmd, 4);
}

static void rfSetPacketSize(int len) {
    if (len < 1) len = 1;
    if (len > 255) len = 255;
    uint8_t cmd[] = {
        0x02, 0x49,
        0x0C,  // preamble type
        0x4C,  // sync word length
        0x00,  // variable length = fixed
        (uint8_t)len
    };
    rfWriteCmd(cmd, 6);
}

// ─── Full radio init (uses current runtime params) ───────────────────
static volatile bool radioReady = false;

static bool rawInitRadio() {
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    // Clear errors
    { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // Set STDBY_RC
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; rfWriteCmd(cmd, 3); }
    delay(5);

    // Set packet type FLRC (0x05)
    { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // RF frequency
    rfSetFrequency(g_freqMhz);
    delay(1);

    // PA config — HF select (bit 7)
    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // FE calibration params
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

    // TX fallback mode
    { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x25 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // Sync word
    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

    // Packet params (uses runtime pktSize)
    rfSetPacketSize(g_pktSize);
    delay(1);

    // Modulation params: FLRC 2600 kbps, BT=1, BW=2400
    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);

    // TX params (uses runtime power)
    rfSetTxPower(g_powerDbm);
    delay(1);

    // Buffer base address
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // IRQ enable: TX_DONE + RX_TX_TIMEOUT
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // DIO mapping
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
    if (!radioReady) { dualPrintln("ERR: radio not initialized — send INIT"); return; }

    int pktSize = g_pktSize;
    int pktCount = g_pktCount;

    dualPrintf("TX_START count=%d pktSize=%d freq=%.1f power=%d",
               pktCount, pktSize, (double)g_freqMhz, g_powerDbm);
    delay(10);

    uint8_t pkt[255];
    for (int j = 4; j < pktSize; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t irqMask = 1UL << PIN_IRQ;
    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    for (int i = 0; i < pktCount; i++) {
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        rfClearIrq();
        rfWriteTxFifo(pkt, pktSize);
        rfSetTx();

        // Wait for TX_DONE — IRQ pin HIGH
        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 500000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
        }

        if (i < 3) {
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
                       i + 1, pktCount,
                       (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);
        }
    }

    // DEADBEEF end marker — signals RX that burst is complete
    pkt[0] = 0xDE; pkt[1] = 0xAD; pkt[2] = 0xBE; pkt[3] = 0xEF;
    pkt[4] = (uint8_t)(pktCount >> 24);
    pkt[5] = (uint8_t)(pktCount >> 16);
    pkt[6] = (uint8_t)(pktCount >> 8);
    pkt[7] = (uint8_t)(pktCount & 0xFF);
    rfClearTxFifo();
    rfWriteTxFifo(pkt, pktSize);
    rfSetTx();
    delay(5);

    uint32_t elapsed = millis() - startMs;
    float tput = ((float)pktCount * pktSize * 8.0f) / elapsed;

    dualPrintln("=============================================");
    dualPrintf("  TX sent:     %d", pktCount);
    dualPrintf("  TX_DONE:     %lu", (unsigned long)txDoneCount);
    dualPrintf("  Timeouts:    %lu", (unsigned long)txTimeoutCount);
    dualPrintf("  Elapsed:     %lu ms", (unsigned long)elapsed);
    dualPrintf("  PktSize:     %d bytes", pktSize);
    dualPrintf("  Throughput:  %.1f kbps", tput);
    dualPrintln("=============================================");
    dualPrintf("RESULT_TX,sent=%d,tx_done=%lu,timeout=%lu,elapsed_ms=%lu,throughput_kbps=%.1f,pkt_size=%d",
               pktCount, (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
               (unsigned long)elapsed, tput, pktSize);
}

// ─── Status report ───────────────────────────────────────────────────
static void printStatus() {
    dualPrintln("=== RANGE TX CONFIG ===");
    dualPrintf("  freq=%.1f MHz", (double)g_freqMhz);
    dualPrintf("  power=%d dBm", g_powerDbm);
    dualPrintf("  pktSize=%d bytes", g_pktSize);
    dualPrintf("  pktCount=%d", g_pktCount);
    dualPrintf("  modulation=FLRC 2600 kbps");
    dualPrintf("  syncWord=0x12AD101B");
    dualPrintf("  radio: %s", radioReady ? "READY" : "NOT_INIT");
    dualPrintf("  SPI=%.2f MHz", SPI_FREQ_HZ / 1e6f);
    dualPrintln("========================");
}

static void printHelp() {
    dualPrintln("=== RANGE TX COMMANDS ===");
    dualPrintln("  POWER <dbm>   Set TX power (0,3,6,9,12,12.5)");
    dualPrintln("  PKTLEN <n>    Set packet size (1-255)");
    dualPrintln("  FREQ <mhz>    Set RF frequency (2400-2500)");
    dualPrintln("  COUNT <n>     Set packet count");
    dualPrintln("  RUN           Transmit burst");
    dualPrintln("  STATUS        Show current config");
    dualPrintln("  INIT          Re-init radio");
    dualPrintln("  HELP          This message");
    dualPrintln("==========================");
}

// ─── Command parser ──────────────────────────────────────────────────
static void processCommand(const char *cmd) {
    while (*cmd == ' ' || *cmd == '\t') cmd++;
    if (*cmd == '\0') return;

    // Convert to uppercase for command matching (not args)
    char upper[64];
    size_t i;
    for (i = 0; i < 63 && cmd[i]; i++) {
        upper[i] = toupper((unsigned char)cmd[i]);
    }
    upper[i] = '\0';

    if (strncmp(upper, "POWER ", 6) == 0) {
        float p = strtof(cmd + 6, nullptr);
        if (p >= 0.0f && p <= 12.5f) {
            g_powerDbm = (p == 12.5f) ? 13 : (int)p;  // store 13 for 12.5
            rfSetTxPower(g_powerDbm);
            dualPrintf("OK power=%d dBm (reg=0x%02X)", g_powerDbm, (uint8_t)(g_powerDbm * 2));
        } else {
            dualPrintln("ERR: power range 0..12.5 dBm");
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
    else if (strncmp(upper, "FREQ ", 5) == 0) {
        float f = strtof(cmd + 5, nullptr);
        if (f >= 2400.0f && f <= 2500.0f) {
            g_freqMhz = f;
            rfSetFrequency(f);
            dualPrintf("OK freq=%.1f MHz", (double)f);
        } else {
            dualPrintln("ERR: freq range 2400..2500 MHz");
        }
    }
    else if (strncmp(upper, "COUNT ", 6) == 0) {
        int n = atoi(cmd + 6);
        if (n >= 1 && n <= 100000) {
            g_pktCount = n;
            dualPrintf("OK pktCount=%d", n);
        } else {
            dualPrintln("ERR: count range 1..100000");
        }
    }
    else if (strcmp(upper, "RUN") == 0) {
        runTransmit();
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

    Serial1.println();
    Serial1.println("=== RP2040 FLRC RANGE TX ===");
    Serial1.println("Runtime-configurable: POWER/PKTLEN/FREQ/COUNT/RUN");

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    Serial1.println("SPI init done");

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
    static unsigned long lastHB = 0;
    if (millis() - lastHB > 5000) {
        lastHB = millis();
        Serial1.println("HB tx_ready");
    }

    // Process commands from both USB CDC and UART
    static char cmdBuf[80];
    static size_t cmdLen = 0;
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
