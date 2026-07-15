/*
 * flrc_raw_rx.cpp — RP2040 FLRC RX with RAW SPI init (no RadioLib)
 *
 * All init via raw SPI using LR2021 opcodes from TheClams + RadioLib source.
 * Fixes from lr2021-spi-command-reference.md:
 *   - ADD SET_RX_PATH (0x0201) HF path for 2.4 GHz
 *   - ADD CALIB_FRONT_END (0x0123) for 2.4 GHz image rejection
 *   - ADD CLEAR_ERRORS (0x0111) before calibration
 *   - FIX CALIBRATE bitmask 0x6F→0x2F (bit 5 undefined)
 *   - FIX frequency formula (PLL divider, not raw Hz)
 *
 * Output: Serial1 (UART GP12→ESP32 bridge) + Serial (USB, may die)
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

// ─── FLRC Config ─────────────────────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_BR         2600
#define FLRC_PKT_SIZE   255
#define SPI_FREQ_HZ     16000000UL
#define XTAL_MHZ        52.0f

#define RX_LISTEN_MS    12000
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

// Two-phase read: send command, release CS, then read response
static void rfReadFifo(uint8_t *buf, size_t len) {
    // LR2021 READ_RX_FIFO (0x0001) — NO status bytes!
    // RadioLib readRadioRxFifo sets BITS_0 status width (no status bytes returned)
    // Phase 1: send opcode
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00); spiRf.transfer(0x01);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    // Phase 2: read payload directly (NO status bytes)
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
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
    // GET_AND_CLEAR_IRQ_STATUS = 0x0117
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
    // SET_RX = 0x020C + 3-byte timeout (0xFFFFFF = continuous)
    // Total: 5 bytes (NOT 6 — extra byte causes CMD_ERROR)
    uint8_t cmd[5] = { 0x02, 0x0C, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 5);
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

// ─── Raw SPI Init (TheClams + RadioLib fixes) ────────────────────────
static bool rawInitRadio() {
    // 0. Hardware reset
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    // 1. CLEAR_ERRORS (0x0111) — clear any stale errors before init
    { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 2. SET_STANDBY (STDBY_XOSC = 0x01) — start crystal oscillator
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; rfWriteCmd(cmd, 3); }
    delay(5);

    // 3. SET_PACKET_TYPE FLRC (0x05)
    { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // 4. SET_RF_FREQUENCY — correct PLL divider formula
    //    frf = freq_Hz * 2^18 / XTAL_Hz
    uint32_t frf = (uint32_t)((FLRC_FREQ_MHZ * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    dualPrintf("frf=%lu (0x%06lX)", (unsigned long)frf, (unsigned long)frf);
    {
        uint8_t cmd[] = {
            0x02, 0x00,
            (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
        };
        rfWriteCmd(cmd, 5);
    }
    delay(1);

    // 5. SET_RX_PATH (0x0201) — HF path mandatory for 2.4 GHz
    //    byte0=0x01 (HF path), byte1=0x00 (no boost)
    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 6. CALIB_FRONT_END (0x0123) — image rejection calibration for 2.4 GHz
    //    freq/4 = 610, set HF_PATH bit (bit 15)
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

    // 7. CALIBRATE (0x0122) — defined bits only 0x5F (per TheClams reference)
    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
    delay(5);

    // 8. SET_FLRC_MOD_PARAMS (0x0248)
    //    brBw=0x00 (2600 kbps), (CR_1_0=0x02 << 4)|(BT_0_5=0x05) = 0x25
    { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x25 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 9. SET_FLRC_SYNCWORD (0x024C) — sync word 1
    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

    // 10. SET_FLRC_PACKET_PARAMS (0x0249)
    //     preamble=16 → index 3, syncWordLen=4, syncWordTx=1, syncMatch=1, fixed=1, crc=0
    //     byte0: ((3 & 0x0F) << 2) | (4/2) = 0x0E
    //     byte1: ((1 & 0x03) << 6) | ((1 & 0x07) << 3) | (1<<2) | 0 = 0x4C
    //     byte2-3: payloadLen = 255 (big-endian)
    {
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0E,  // preamble idx 3 (16 symbols) | syncLen 4/2=2
            0x4C,  // syncTx=1 | syncMatch=1 | fixed=1 | crc=0
            0x00, (uint8_t)FLRC_PKT_SIZE
        };
        rfWriteCmd(cmd, 6);
    }
    delay(1);

    // 11. SET_RX_TX_FALLBACK (Fs=0x03 per TheClams — keeps PLL warm)
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // 12. DIO function — DIO9 = IRQ output
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 13. DIO IRQ config — map RX_DONE (bit 18 = 0x00040000) to DIO9
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x04, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
    delay(1);

    // 14. Clear IRQ + enter continuous RX
    rfClearIrq();
    delay(1);
    rfSetRx();
    delay(2);

    // Verify
    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    // Status byte upper nibble: 0x05 = RX mode
    if ((st >> 4) == 0x05) {
        dualPrintln("RADIO_INIT_OK (RX mode)");
        return true;
    } else if (irq & 0x00020000) {
        dualPrintf("RADIO_INIT_WARN CMD_ERROR (St=0x%02X) — radio may still work", st);
        return true; // accept partial — radio entered RX despite CMD_ERROR before
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
};
static RxStats stats;
static volatile bool radioReady = false;

static void resetStats() {
    memset(&stats, 0, sizeof(stats));
    stats.lastSeq = 0xFFFFFFFF;
}

// ─── Receive session ─────────────────────────────────────────────────
static void runReceive() {
    if (!radioReady) { dualPrintln("ERR: radio not initialized"); return; }

    // Re-arm RX in case we were in another mode
    rfClearIrq();
    rfSetRx();
    delay(1);

    resetStats();
    stats.startMs = millis();
    uint32_t lastPktMs = millis();
    uint8_t buf[FLRC_PKT_SIZE];

    dualPrintln("RX_START");
    dualPrintln("pkt,seq");

    while (true) {
        uint32_t now = millis();
        if ((now - stats.startMs) >= RX_LISTEN_MS) { dualPrintln("RX_DONE timeout"); break; }
        if (stats.received > 0 && (now - lastPktMs) >= RX_SILENCE_MS) {
            dualPrintln("RX_DONE silence"); break;
        }

        // Poll IRQ via SPI — GET_AND_CLEAR_IRQ_STATUS (0x0117)
        uint32_t irq = rfReadIrqStatus();
        if (!(irq & 0x00040000)) continue;  // bit 18 = RX_DONE

        // Read packet from FIFO (no status bytes — LR2021 READ_RX_FIFO)
        rfReadFifo(buf, FLRC_PKT_SIZE);

        // Clear RX FIFO + CLEAR_ERRORS + re-arm RX
        { uint8_t cmd[] = { 0x01, 0x1E }; rfWriteCmd(cmd, 2); }  // CLEAR_RX_FIFO
        rfWaitBusy();
        { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }  // CLEAR_ERRORS
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
            dualPrintf("%lu,%lu", (unsigned long)stats.received, (unsigned long)seq);
        }
    }

    if (stats.elapsedMs == 0) stats.elapsedMs = millis() - stats.startMs;

    // Print results
    uint32_t n = stats.received;
    uint32_t total = stats.totalSentByTx > 0 ? stats.totalSentByTx : (stats.maxSeq + 1);
    uint32_t lost = (total > n) ? (total - n) : 0;
    float perPct = (total > 0) ? (100.0f * (float)lost / (float)total) : 0.0f;
    float tputKbps = (stats.elapsedMs > 0 && n > 0)
                     ? ((float)n * (float)FLRC_PKT_SIZE * 8.0f) / (float)stats.elapsedMs : 0.0f;

    dualPrintln("=============================================");
    dualPrintf("  Received: %lu (unique %lu, dup %lu)", (unsigned long)n,
               (unsigned long)stats.unique, (unsigned long)stats.duplicates);
    dualPrintf("  TX sent:  %lu (est total %lu)",
               (unsigned long)stats.totalSentByTx, (unsigned long)total);
    dualPrintf("  Lost:     %lu (%.2f%%)", (unsigned long)lost, perPct);
    dualPrintf("  Elapsed:  %lu ms", (unsigned long)stats.elapsedMs);
    dualPrintf("  THROUGHPUT: %.1f kbps", tputKbps);
    dualPrintln("=============================================");
    dualPrintf("RESULT,rx=%lu,unique=%lu,lost=%lu,total=%lu,per=%.2f,elapsed_ms=%lu,throughput_kbps=%.1f",
               (unsigned long)n, (unsigned long)stats.unique, (unsigned long)lost,
               (unsigned long)total, perPct, (unsigned long)stats.elapsedMs, tputKbps);
}

// ─── Config print ────────────────────────────────────────────────────
static void printConfig() {
    dualPrintln("=== FLRC RX CONFIG ===");
    dualPrintf("  freq=%.1f MHz  BR=%d", FLRC_FREQ_MHZ, FLRC_BR);
    dualPrintf("  CR=uncoded  shaping=BT0.5  pktSize=%d", FLRC_PKT_SIZE);
    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("  Status=0x%02X  IRQ=0x%08lX", st, (unsigned long)irq);
    dualPrintf("  radio: %s  listen=%dms  silence=%dms",
               radioReady ? "INIT" : "NOT_INIT", RX_LISTEN_MS, RX_SILENCE_MS);
    dualPrintln("======================");
}

// ─── Command handling ────────────────────────────────────────────────
static char cmdBuf[64];
static size_t cmdLen = 0;

static void processCommand(const char *cmd) {
    if (strcmp(cmd, "RUN") == 0)      { runReceive(); }
    else if (strcmp(cmd, "CONFIG") == 0) { printConfig(); }
    else if (strcmp(cmd, "INIT") == 0)   { radioReady = rawInitRadio(); }
    else if (strcmp(cmd, "RESULTS") == 0) {
        if (stats.received > 0) {
            float tput = (stats.elapsedMs > 0)
                ? ((float)stats.received * FLRC_PKT_SIZE * 8.0f) / stats.elapsedMs : 0;
            dualPrintf("RESULT rx=%lu throughput=%.1fkbps",
                       (unsigned long)stats.received, tput);
        } else { dualPrintln("No results yet"); }
    }
    else if (strcmp(cmd, "HELP") == 0) {
        dualPrintln("Commands: RUN CONFIG INIT RESULTS HELP");
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
    dualPrintln("=== RP2040 FLRC RAW RX ===");
    dualPrintln("Raw SPI init (no RadioLib)");

    // Initialize SPI bus + GPIO pins BEFORE radio init
    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        dualPrintln("Auto-start RX in 8 seconds...");
        delay(8000); // give bridge time to connect
        runReceive();
    } else {
        dualPrintln("INIT FAILED — type INIT to retry");
    }
}

void loop() {
    // Heartbeat every 2s on Serial1
    static unsigned long lastHB = 0;
    if (millis() - lastHB > 2000) {
        lastHB = millis();
        Serial1.println("HB alive");
        Serial1.flush();
    }

    // Read commands from both Serial and Serial1
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
