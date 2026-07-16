/*
 * flrc_raw_tx.cpp — RP2040 FLRC TX with RAW SPI init (no RadioLib)
 *
 * v2: CDC-safe init + FIFO pipelining + reduced preamble
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13
 */

#include <Arduino.h>
#include <SPI.h>
#include <hardware/dma.h>
#include <hardware/irq.h>

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

// ─── FLRC Config (MUST match RX) ─────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_BR         2600
#define FLRC_PKT_SIZE   255
#define SPI_FREQ_HZ     20000000UL
#define XTAL_MHZ        52.0f

#define TX_PKT_COUNT    1000
#define TX_POWER_DBM    12  // HF FLRC max per RadioLib (range: -19 to +12)

// Sync word — MUST match RX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// ─── Direct SPI helpers ──────────────────────────────────────────────
// Wait for BUSY pin LOW. Returns false on timeout (chip not responding).
static inline bool rfWaitBusy() {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 100000;
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
    return timeout > 0;
}

// Direct SPI write — uses RP2040 hardware SPI FIFO (8-deep)
static inline void spiWriteBurst(const uint8_t *buf, size_t len) {
    spi_hw_t *hw = spi0_hw;
    for (size_t i = 0; i < len; i++) {
        while (!(hw->sr & SPI_SSPSR_TNF_BITS)) {}
        *(volatile uint8_t *)&hw->dr = buf[i];
    }
    while (!(hw->sr & SPI_SSPSR_TFE_BITS)) {}
}

static inline void spiWriteByte(uint8_t b) {
    spi_hw_t *hw = spi0_hw;
    while (!(hw->sr & SPI_SSPSR_TNF_BITS)) {}
    *(volatile uint8_t *)&hw->dr = b;
}

static inline void spiDrain() {
    spi_hw_t *hw = spi0_hw;
    while (!(hw->sr & SPI_SSPSR_TFE_BITS)) {}
    while (hw->sr & SPI_SSPSR_RNE_BITS) (void)hw->dr;
}

// Combined: wait busy + assert CS + write + deassert CS + drain
static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    digitalWrite(PIN_CS, LOW);
    spiWriteBurst(buf, len);
    digitalWrite(PIN_CS, HIGH);
    spiDrain();
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

static void rfSetStandby() {
    uint8_t cmd[] = { 0x01, 0x28, 0x01 };
    rfWriteCmd(cmd, 3);
}

static void rfWriteTxFifo(const uint8_t *data, size_t len) {
    rfWaitBusy();
    digitalWrite(PIN_CS, LOW);
    spiWriteByte(0x00);
    spiWriteByte(0x02);
    spiWriteBurst(data, len);
    digitalWrite(PIN_CS, HIGH);
    spiDrain();
}

static void rfClearTxFifo() {
    uint8_t cmd[] = { 0x01, 0x1F };
    rfWriteCmd(cmd, 2);
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

// ─── Raw SPI Init (identical to RX) ──────────────────────────────────
static bool rawInitRadio() {
    // 0. Hardware reset
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    // 1. CLEAR_ERRORS
    { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 2. SET_STANDBY (STDBY_XOSC = 0x01)
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; rfWriteCmd(cmd, 3); }
    delay(5);

    // 3. SET_PACKET_TYPE FLRC
    { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // 4. SET_RF_FREQUENCY
    uint32_t frf = (uint32_t)((FLRC_FREQ_MHZ * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    {
        uint8_t cmd[] = {
            0x02, 0x00,
            (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
        };
        rfWriteCmd(cmd, 5);
    }
    delay(1);

    // 5. SET_RX_PATH (HF path for 2.4 GHz)
    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 6. CALIB_FRONT_END
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

    // 7. CALIBRATE — 0x5F (per TheClams reference)
    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
    delay(5);

    // 8. SET_FLRC_MOD_PARAMS
    { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x25 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 9. SET_FLRC_SYNCWORD
    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

    // 10. SET_FLRC_PACKET_PARAMS (MUST match RX: preamble idx 3 | syncLen 2)
    {
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0E,  // preamble idx 3 (16) | syncLen 2
            0x4C,  // syncTx=1 | syncMatch=1 | fixed=1 | crc=0
            0x00, (uint8_t)FLRC_PKT_SIZE
        };
        rfWriteCmd(cmd, 6);
    }
    delay(1);

    // 11. SET_PA_CONFIG (HF PA select via bit 7)
    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);

    // 12. SET_TX_PARAMS (power + ramp)
    { uint8_t cmd[] = { 0x02, 0x03, (uint8_t)(TX_POWER_DBM * 2), 0x04 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 14. SET_RX_TX_FALLBACK (Fs=0x03 keeps PLL warm between TX)
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // 15. DIO function — DIO9 = IRQ for TX_DONE
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 16. DIO IRQ config — map TX_DONE (bit 19 = 0x00080000) to DIO9
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
    delay(1);

    rfClearIrq();
    delay(1);

    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    // Status 0x04 = STDBY, 0x07 = TX
    if ((st >> 4) == 0x04 || (st >> 4) == 0x07 || (irq & 0x00020000)) {
        dualPrintln("RADIO_INIT_OK");
        return true;
    }
    dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

// ─── TX burst with FIFO pipelining ───────────────────────────────────
static volatile bool radioReady = false;

static void runTransmit() {
    if (!radioReady) { dualPrintln("ERR: radio not initialized"); return; }

    dualPrintf("TX_START count=%d pktSize=%d", TX_PKT_COUNT, FLRC_PKT_SIZE);
    delay(10);

    // Pre-build packet payload ONCE
    uint8_t pkt[FLRC_PKT_SIZE];
    for (int j = 4; j < FLRC_PKT_SIZE; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t irqMask = 1UL << PIN_IRQ;

    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    // Static command arrays (avoid stack alloc per iteration)
    static const uint8_t clrCmd[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    static const uint8_t fifoCmd[] = { 0x00, 0x02 }; // WRITE_TX_FIFO header
    static const uint8_t txCmd[] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };

    // === STAGE 1: FIFO PIPELINING ===
    // Strategy: write packet 0 to FIFO + trigger TX.
    // Then for each subsequent packet:
    //   1. Wait for TX_DONE (IRQ pin)
    //   2. Immediately clear IRQ + write next packet to FIFO + trigger TX
    //   This minimizes the gap between TX_DONE and next SET_TX.

    // Prime: write first packet to FIFO
    pkt[0] = 0; pkt[1] = 0; pkt[2] = 0; pkt[3] = 0;
    rfWaitBusy();
    digitalWrite(PIN_CS, LOW);
    spiWriteBurst(fifoCmd, 2);
    spiWriteBurst(pkt, FLRC_PKT_SIZE);
    digitalWrite(PIN_CS, HIGH);
    spiDrain();

    // Trigger TX for first packet
    rfWaitBusy();
    digitalWrite(PIN_CS, LOW);
    spiWriteBurst(txCmd, 5);
    digitalWrite(PIN_CS, HIGH);
    spiDrain();

    for (int i = 0; i < TX_PKT_COUNT; i++) {
        // Wait for TX_DONE — tight GPIO spin
        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 500000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
        }

        if (irqFired) txDoneCount++;
        else txTimeoutCount++;

        // Diagnostic for first 5 packets
        if (i < 5) {
            uint8_t stPost = rfReadStatus();
            uint32_t irqStatus = rfReadIrqStatus();
            dualPrintf("PKT %d: irqPin=%d st=0x%02X IRQ=0x%08lX spin=%lu",
                       i, irqFired ? 1 : 0, stPost,
                       (unsigned long)irqStatus, (unsigned long)spinCount);
        }

        // === STAGE 2: MERGED CLR_IRQ + FIFO WRITE + SET_TX ===
        // Overlap: clear IRQ from previous TX, write next packet, trigger TX
        // all in rapid succession. Minimizes dead time between packets.

        if (i + 1 < TX_PKT_COUNT) {
            // Update seq bytes for next packet
            int next = i + 1;
            pkt[0] = (uint8_t)(next >> 24);
            pkt[1] = (uint8_t)(next >> 16);
            pkt[2] = (uint8_t)(next >> 8);
            pkt[3] = (uint8_t)(next & 0xFF);

            // 1. Clear IRQ (acknowledges previous TX_DONE)
            rfWaitBusy();
            digitalWrite(PIN_CS, LOW);
            spiWriteBurst(clrCmd, 6);
            digitalWrite(PIN_CS, HIGH);
            spiDrain();

            // 2. Write next packet to FIFO
            rfWaitBusy();
            digitalWrite(PIN_CS, LOW);
            spiWriteBurst(fifoCmd, 2);
            spiWriteBurst(pkt, FLRC_PKT_SIZE);
            digitalWrite(PIN_CS, HIGH);
            spiDrain();

            // 3. Trigger TX immediately
            rfWaitBusy();
            digitalWrite(PIN_CS, LOW);
            spiWriteBurst(txCmd, 5);
            digitalWrite(PIN_CS, HIGH);
            spiDrain();
        }

        // Progress every 200
        if ((i + 1) % 200 == 0) {
            dualPrintf("TX %d/%d (done=%lu to=%lu)",
                       i + 1, TX_PKT_COUNT,
                       (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);
        }
    }

    dualPrintf("TX_DONE_STATS: fired=%lu timeout=%lu",
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);

    // Send DEADBEEF end marker
    pkt[0] = 0xDE; pkt[1] = 0xAD; pkt[2] = 0xBE; pkt[3] = 0xEF;
    pkt[4] = (uint8_t)(TX_PKT_COUNT >> 24);
    pkt[5] = (uint8_t)(TX_PKT_COUNT >> 16);
    pkt[6] = (uint8_t)(TX_PKT_COUNT >> 8);
    pkt[7] = (uint8_t)(TX_PKT_COUNT & 0xFF);
    rfClearTxFifo();
    rfWriteTxFifo(pkt, FLRC_PKT_SIZE);
    rfSetTx();
    delay(5);

    uint32_t elapsed = millis() - startMs;
    float tput = ((float)TX_PKT_COUNT * FLRC_PKT_SIZE * 8.0f) / elapsed;

    dualPrintln("=============================================");
    dualPrintf("  TX sent:     %d", TX_PKT_COUNT);
    dualPrintf("  Elapsed:     %lu ms", (unsigned long)elapsed);
    dualPrintf("  TX THROUGHPUT: %.1f kbps", tput);
    dualPrintln("=============================================");
    dualPrintf("RESULT_TX,sent=%d,elapsed_ms=%lu,throughput_kbps=%.1f",
               TX_PKT_COUNT, (unsigned long)elapsed, tput);
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);
    delay(100);

    // NOTE: Do NOT call Serial.flush() — it blocks if no host has CDC open.
    // Just print and let TinyUSB buffer drain asynchronously.

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(120);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(120);
    }

    Serial1.println("=== RP2040 FLRC RAW TX v2 ===");
    Serial1.println("FIFO pipelining + reduced preamble + 20MHz SPI");

    // Initialize SPI bus + configure clock/format via beginTransaction
    spiRf.begin();
    spiRf.beginTransaction(spiSettings);
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    Serial1.println("SPI_INIT_DONE");

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        Serial1.println("RADIO_OK — TX starts in 8s");
        // Heartbeat loop during wait — host catches output whenever it connects
        for (int w = 8; w > 0; w--) {
            Serial.print("WAIT ");
            Serial.println(w);
            Serial1.print("WAIT ");
            Serial1.println(w);
            delay(1000);
        }
        runTransmit();
    } else {
        Serial1.println("INIT FAILED — type INIT to retry");
        Serial.println("INIT FAILED");
    }
}

void loop() {
    static unsigned long lastHB = 0;
    if (millis() - lastHB > 2000) {
        lastHB = millis();
        Serial1.println("HB alive");
        Serial1.flush();
    }

    // Command interface
    static char cmdBuf[64];
    static size_t cmdLen = 0;
    for (int src = 0; src < 2; src++) {
        Stream *s = (src == 0) ? (Stream*)&Serial : (Stream*)&Serial1;
        while (s->available()) {
            char c = (char)s->read();
            if (c == '\n' || c == '\r') {
                if (cmdLen > 0) {
                    cmdBuf[cmdLen] = '\0';
                    if (strcmp(cmdBuf, "RUN") == 0) runTransmit();
                    else if (strcmp(cmdBuf, "INIT") == 0) radioReady = rawInitRadio();
                    cmdLen = 0;
                }
            } else if (cmdLen < sizeof(cmdBuf) - 1) {
                cmdBuf[cmdLen++] = c;
            }
        }
    }
}
