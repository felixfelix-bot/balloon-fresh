/*
 * flrc_rx_raw.cpp — RP2040 FLRC RX with RAW SPI init (no RadioLib)
 *
 * Bypasses RadioLib beginFLRC() entirely to avoid:
 *   1. Error -707 (SPIClassRP2040 incompatible with RadioLib SPI HAL)
 *   2. Mode A USB death (RadioLib SPI burst kills TinyUSB enumeration)
 *
 * Init sequence extracted from RadioLib source with 1-5ms delays between
 * commands to keep USB CDC alive.
 *
 * Output: Serial (USB CDC) AND Serial1 (UART GP12→ESP32 bridge)
 *
 * Commands: RUN  CONFIG  INIT  RESULTS  HELP
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
#define FLRC_FREQ_HZ   2440.0f
#define FLRC_BR        2600
#define FLRC_PWR_DBM   13
#define FLRC_PREAMBLE  16
#define FLRC_PKT_SIZE  255
#define SPI_FREQ_HZ    16000000UL

#define RX_LISTEN_MS   12000
#define RX_SILENCE_MS  3000
#define PRINT_EVERY    100

// ─── SPI ─────────────────────────────────────────────────────────────
// earlephilhower: SPIClassRP2040(spi_inst, rx(MISO), cs, sck, tx(MOSI))
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// ─── Raw SPI helpers ─────────────────────────────────────────────────
static inline void rfCsLow()  { digitalWrite(PIN_CS, LOW); }
static inline void rfCsHigh() { digitalWrite(PIN_CS, HIGH); }
static inline void rfWaitBusy() {
    uint32_t timeout = millis() + 50;
    while (digitalRead(PIN_BUSY) == HIGH) {
        if (millis() > timeout) return; // don't hang forever
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

static void rfReadCmd(const uint8_t *cmd, size_t cmdLen, uint8_t *out, size_t outLen) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    for (size_t i = 0; i < cmdLen; i++) spiRf.transfer(cmd[i]);
    for (size_t i = 0; i < outLen; i++) out[i] = spiRf.transfer(0x00);
    rfCsHigh();
    spiRf.endTransaction();
}

static uint8_t rfReadStatus() {
    uint8_t st = 0;
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    st = spiRf.transfer(0x00); // NOP returns status byte
    rfCsHigh();
    spiRf.endTransaction();
    return st;
}

// ─── RX hot path helpers ─────────────────────────────────────────────
// LR2021 read protocol: TWO separate SPI transactions
// Phase 1: send opcode (CS LOW → send 2 bytes → CS HIGH)
// Phase 2: read response (CS LOW → send NOP 0x00 → read status 2 bytes → read data → CS HIGH)

static void rfReadFifoTwoPhase(uint8_t *buf, size_t len) {
    // Phase 1: send READ_RX_FIFO command (0x0001)
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    spiRf.transfer(0x00); // opcode MSB
    spiRf.transfer(0x01); // opcode LSB
    rfCsHigh();
    spiRf.endTransaction();

    // Wait for BUSY to go LOW (command processing)
    rfWaitBusy();

    // Phase 2: read response — NOP bytes come back as status, then data
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    // First 2 bytes are status (16-bit per LR2021 SPI config)
    spiRf.transfer(0x00); // NOP MSB → returns status byte 1
    spiRf.transfer(0x00); // NOP LSB → returns status byte 2
    // Now read payload data
    for (size_t i = 0; i < len; i++) buf[i] = spiRf.transfer(0x00);
    rfCsHigh();
    spiRf.endTransaction();
}

static uint32_t rfReadIrqStatus() {
    // GET_AND_CLEAR_IRQ_STATUS = 0x0117
    // Phase 1: send command
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    spiRf.transfer(0x01); spiRf.transfer(0x17);
    rfCsHigh();
    spiRf.endTransaction();
    rfWaitBusy();

    // Phase 2: read 2 status + 4 IRQ bytes
    uint8_t buf[6];
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    for (int i = 0; i < 6; i++) buf[i] = spiRf.transfer(0x00);
    rfCsHigh();
    spiRf.endTransaction();
    // bytes 0-1 = status, bytes 2-5 = IRQ flags (big-endian)
    return ((uint32_t)buf[2] << 24) | ((uint32_t)buf[3] << 16) |
           ((uint32_t)buf[4] << 8) | (uint32_t)buf[5];
}

static void rfClearIrq() {
    uint8_t cmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 6);
}

static void rfSetRx() {
    uint8_t cmd[6] = { 0x02, 0x0C, 0x00, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 6);
}

// ─── Raw SPI Init Sequence (matches TheClams lr2021-apps FLRC reference) ─
static bool rawInitRadio() {
    // Step 0: Hardware reset
    digitalWrite(PIN_RST, LOW);
        delayMicroseconds(200);
        digitalWrite(PIN_RST, HIGH);
        delay(50);

        // Step 1: SET_RF_FREQUENCY (0x0200) — freq in Hz, big-endian
        // TheClams: set_rf(2_400_000_000) — value IS in Hz
        uint32_t rfFreq = (uint32_t)(FLRC_FREQ_HZ * 1000000.0f);
        {
            uint8_t cmd[] = {
                0x02, 0x00,
                (uint8_t)(rfFreq >> 24), (uint8_t)(rfFreq >> 16),
                (uint8_t)(rfFreq >> 8),  (uint8_t)(rfFreq & 0xFF)
            };
            rfWriteCmd(cmd, 6);
        }
        delay(1);

        // Step 2: SET_RX_PATH (0x0201) — MUST select HF path for 2.4 GHz!
        // TheClams: set_rx_path(RxPath::HfPath, 0)
        // Without this, radio uses LF path → CMD_ERROR on 2.4 GHz commands
        { uint8_t cmd[] = { 0x02, 0x01, 0x01 }; rfWriteCmd(cmd, 3); } delay(1);

        // Step 3: CALIBRATE (0x0122) — all defined blocks = 0x5F (NOT 0x6F)
        // Rust driver: bit6=pa_offset, bit4=meas_unit, bit3=aaf, bit2=pll, bit1=hf_rc, bit0=lf_rc
        // 0x6F has bit5 set which is UNDEFINED → likely CMD_ERROR source
        { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
        delay(5);
        rfWaitBusy(); // wait for calibration to complete

        // Step 4: CALIB_FE (0x0123) — front-end calibration (REQUIRED before RX)
        // Datasheet: "If image rejection calibration was not done, RXFREQ_NO_CAL_ERR"
        // TheClams: calib_fe(&[]) — defaults
        { uint8_t cmd[] = { 0x01, 0x23, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 }; rfWriteCmd(cmd, 8); }
        delay(5);
        rfWaitBusy();

        // Step 5: SET_PACKET_TYPE (0x0207) — FLRC=5
        // TheClams: set_packet_type(PacketType::Flrc)
        { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; rfWriteCmd(cmd, 3); } delay(1);

        // Step 6: SET_FLRC_MODULATION_PARAMS (0x0248)
        // TheClams: Br2600=0, None=2, Bt1p0=7 → byte3 = (2<<4)|7 = 0x27
        // Bt1p0 matches reference. Bt0p5=5 also valid but use reference value.
        { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x27 }; rfWriteCmd(cmd, 4); } delay(1);

        // Step 7: SET_FLRC_SYNCWORD (0x024C) — 32-bit sync word at slot 1
        // TheClams: 0xCD05CAFE at slot 1
        {
            uint8_t cmd[] = {
                0x02, 0x4C,
                0x01,               // sw_num = 1
                0xCD, 0x05, 0xCA, 0xFE  // syncword MSB first
            };
            rfWriteCmd(cmd, 7);
        }
        delay(1);

        // Step 8: SET_FLRC_PACKET_PARAMS (0x0249)
        // TheClams: 16b preamble, 32b SW, SwTx=1, Match1, Dynamic, CRC24, PLD=255
        // byte2 = (agc_pbl_len << 2) | sw_len = (3<<2)|2 = 0x0E
        // byte3 = (sw_tx<<6)|(sw_match<<3)|(pkt_fmt<<2)|crc = (1<<6)|(1<<3)|(1<<2)|0 = 0x4C
        //         Fixed=1, CRC=0 — MUST match TX (RadioLib fixedPacketLengthMode + CRC disabled)
        // byte4-5 = pld_len = 255
        {
            uint8_t cmd[] = {
                0x02, 0x49,
                0x0E,   // 16b preamble (3<<2) | 32b SW (2)
                0x4C,   // SwTx=1(1<<6) | Match1(1<<3) | Fixed(1) | CRC_OFF(0)
                0x00, 0xFF  // pld_len = 255
            };
            rfWriteCmd(cmd, 6);
        }
        delay(1);

        // Step 9: SET_RX_TX_FALLBACK_MODE (0x0206) — Fs=3 (TheClams uses FS)
        { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); } delay(1);

        // Step 10: SET_DIO_FUNCTION (0x0112) — DIO9 = IRQ
        { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); } delay(1);

        // Step 11: SET_DIO_IRQ_CONFIG (0x0115) — RX_DONE+TX_DONE to DIO9
        // RX_DONE=bit18=0x00040000, TX_DONE=bit19=0x00080000 → 0x000C0000
        {
            uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x0C, 0x00, 0x00 };
            rfWriteCmd(cmd, 7);
        } delay(1);

        // Step 12: CLEAR_IRQ (0x0116) — clear all
        { uint8_t cmd[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF }; rfWriteCmd(cmd, 6); } delay(1);

        // Step 13: SET_RX (0x020C) — enter RX continuous
        { uint8_t cmd[] = { 0x02, 0x0C }; rfWriteCmd(cmd, 2); } delay(1);

    // Verify: read status
    uint8_t st = rfReadStatus();
    char b[64];
    snprintf(b, sizeof(b), "Init done. Status=0x%02X", st);
    Serial.println(b);
    Serial1.println(b);

    // Status byte: upper nibble = chip mode
    // 0x2X = RX mode (good), 0x1X = standby, 0x0X = unused
    uint8_t mode = (st >> 4) & 0x0F;
    if (mode == 0x02 || mode == 0x03 || mode == 0x06) {
        return true; // RX or FS mode = radio alive
    }
    // Even if not in RX, radio is alive if status != 0x00 or 0xFF
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
static bool radioReady = false;

static void resetStats() {
    memset(&stats, 0, sizeof(stats));
    stats.lastSeq = 0xFFFFFFFF;
}

// ─── Dual serial output ──────────────────────────────────────────────
static void dualPrint(const char *s) {
    Serial.print(s);
    Serial1.print(s);
}
static void dualPrintln(const char *s) {
    Serial.println(s);
    Serial1.println(s);
}

// ─── Receive session ─────────────────────────────────────────────────
static void runReceive() {
    if (!radioReady) {
        dualPrintln("ERR: radio not initialized");
        return;
    }

    resetStats();
    stats.startMs = millis();
    uint32_t lastPktMs = millis();
    uint8_t buf[FLRC_PKT_SIZE];

    // Clear any stale IRQ and re-arm RX
    rfClearIrq();
    rfSetRx();
    delay(1);

    dualPrintln("RX_START listening for FLRC packets...");

    bool stopped = false;
    while (!stopped) {
        uint32_t now = millis();
        if ((now - stats.startMs) >= RX_LISTEN_MS) { stopped = true; break; }
        if (stats.received > 0 && (now - lastPktMs) >= RX_SILENCE_MS) {
            dualPrintln("RX_TIMEOUT: silence, stopping");
            stopped = true;
            break;
        }

        // Poll DIO9 IRQ pin
        if (digitalRead(PIN_IRQ) != HIGH) continue;

        // Read IRQ status to verify it's RX_DONE
        uint32_t irqFlags = rfReadIrqStatus();

        // 1. Read FIFO (two-phase read)
        rfReadFifoTwoPhase(buf, FLRC_PKT_SIZE);

        // 2. Clear IRQ (de-asserts DIO9)
        rfClearIrq();

        // 3. Re-arm RX
        rfSetRx();

        // Extract big-endian seq from first 4 bytes
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

        // Progress output
        if (stats.received <= 5 || (stats.received % PRINT_EVERY) == 0) {
            char b[80];
            snprintf(b, sizeof(b), "PKT rx=%lu seq=%lu",
                     (unsigned long)stats.received, (unsigned long)seq);
            dualPrintln(b);
        }
    }

    if (stats.elapsedMs == 0) stats.elapsedMs = millis() - stats.startMs;

    // Print results
    uint32_t n = stats.received;
    uint32_t total = stats.totalSentByTx > 0 ? stats.totalSentByTx : (stats.maxSeq + 1);
    uint32_t lost = (total > n) ? (total - n) : 0;
    float perPct = (total > 0) ? (100.0f * (float)lost / (float)total) : 0.0f;
    float tputKbps = (stats.elapsedMs > 0 && n > 0)
                     ? ((float)n * (float)FLRC_PKT_SIZE * 8.0f) / ((float)stats.elapsedMs)
                     : 0.0f;

    dualPrintln("=============================================");
    {
        char b[128];
        snprintf(b, sizeof(b), "  Received:    %lu (unique %lu, dup %lu)",
                 (unsigned long)n, (unsigned long)stats.unique,
                 (unsigned long)stats.duplicates);
        dualPrintln(b);
        snprintf(b, sizeof(b), "  TX sent:     %lu  (est total %lu)",
                 (unsigned long)stats.totalSentByTx, (unsigned long)total);
        dualPrintln(b);
        snprintf(b, sizeof(b), "  Lost:        %lu  (%.2f%%)", (unsigned long)lost, perPct);
        dualPrintln(b);
        snprintf(b, sizeof(b), "  Elapsed:     %lu ms", (unsigned long)stats.elapsedMs);
        dualPrintln(b);
        snprintf(b, sizeof(b), "  Throughput:  %.1f kbps", tputKbps);
        dualPrintln(b);
    }
    dualPrintln("=============================================");
    {
        char b[160];
        snprintf(b, sizeof(b),
                 "RESULT,rx=%lu,unique=%lu,dup=%lu,lost=%lu,total=%lu,per=%.2f,elapsed_ms=%lu,throughput_kbps=%.1f",
                 (unsigned long)n, (unsigned long)stats.unique, (unsigned long)stats.duplicates,
                 (unsigned long)lost, (unsigned long)total, perPct,
                 (unsigned long)stats.elapsedMs, tputKbps);
        dualPrintln(b);
    }
}

// ─── Commands ────────────────────────────────────────────────────────
static char cmdBuf[64];
static uint8_t cmdLen = 0;

static void printConfig() {
    dualPrintln("=== FLRC RX RAW SPI CONFIG ===");
    char b[96];
    snprintf(b, sizeof(b), "  freq=%.1f MHz  BR=%d  CR=uncoded", FLRC_FREQ_HZ, FLRC_BR);
    dualPrintln(b);
    snprintf(b, sizeof(b), "  power=%d dBm  preamble=%d  pktSize=%d", FLRC_PWR_DBM, FLRC_PREAMBLE, FLRC_PKT_SIZE);
    dualPrintln(b);
    snprintf(b, sizeof(b), "  SPI=%.2f MHz  pins: SCK=%d MOSI=%d MISO=%d CS=%d BUSY=%d IRQ=%d RST=%d",
             SPI_FREQ_HZ / 1.0e6f, PIN_SCK, PIN_MOSI, PIN_MISO, PIN_CS, PIN_BUSY, PIN_IRQ, PIN_RST);
    dualPrintln(b);
    snprintf(b, sizeof(b), "  radio: %s  UART: TX=GP%d RX=GP%d",
             radioReady ? "READY" : "NOT_INIT", PIN_UART_TX, PIN_UART_RX);
    dualPrintln(b);
}

static void processCommand(const char *cmd) {
    while (*cmd == ' ' || *cmd == '\t') cmd++;
    if (*cmd == '\0') return;

    if (strcmp(cmd, "RUN") == 0 || strcmp(cmd, "run") == 0) {
        runReceive();
    } else if (strcmp(cmd, "CONFIG") == 0 || strcmp(cmd, "config") == 0) {
        printConfig();
    } else if (strcmp(cmd, "INIT") == 0 || strcmp(cmd, "init") == 0) {
        dualPrintln("Re-initializing radio (raw SPI)...");
        radioReady = rawInitRadio();
        if (radioReady) dualPrintln("RADIO_INIT_OK");
        else dualPrintln("RADIO_INIT_FAILED — check wiring");
    } else if (strcmp(cmd, "RESULTS") == 0 || strcmp(cmd, "results") == 0) {
        if (stats.received == 0) {
            dualPrintln("No results yet (send RUN first)");
        }
        // Re-print last results
    } else if (strcmp(cmd, "HELP") == 0 || strcmp(cmd, "help") == 0) {
        dualPrintln("Commands: RUN  CONFIG  INIT  RESULTS  HELP");
    } else {
        char b[80];
        snprintf(b, sizeof(b), "ERR: unknown '%s' (try HELP)", cmd);
        dualPrintln(b);
    }
}

// ─── Setup ───────────────────────────────────────────────────────────
void setup() {
    // USB CDC
    Serial.begin(115200);

    // UART1 on GP12/GP13 (earlephilhower requires setTX/setRX before begin)
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);

    // LED
    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);

    // Radio pins
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, HIGH);

    // SPI
    spiRf.begin();

    // Boot blink
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(120);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(120);
    }

    delay(500); // Let USB enumerate

    dualPrintln("");
    dualPrintln("=== RP2040 FLRC RX (RAW SPI) ===");
    dualPrintln("No RadioLib — raw SPI init with delays");

    // Init radio
    radioReady = rawInitRadio();
    if (radioReady) {
        dualPrintln("RADIO_INIT_OK");
        digitalWrite(PIN_LED_ALT, HIGH);
    } else {
        dualPrintln("RADIO_INIT_FAILED — type INIT to retry, CONFIG for info");
    }

    resetStats();
    dualPrintln("Commands: RUN  CONFIG  INIT  RESULTS  HELP");
}

// ─── Main loop ───────────────────────────────────────────────────────
static uint32_t lastHB = 0;

void loop() {
    // Process serial commands (from USB or UART)
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

    // Also accept commands from UART bridge
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

    // Heartbeat every 2 seconds
    uint32_t now = millis();
    if (now - lastHB >= 2000) {
        lastHB = now;
        uint8_t st = rfReadStatus();
        uint32_t irq = rfReadIrqStatus();
        char b[96];
        snprintf(b, sizeof(b), "HB rx=%lu St=0x%02X IRQ=0x%08lX",
                 (unsigned long)stats.received, st, (unsigned long)irq);
        dualPrintln(b);
        digitalWrite(PIN_LED, !digitalRead(PIN_LED)); // toggle heartbeat
    }
}
