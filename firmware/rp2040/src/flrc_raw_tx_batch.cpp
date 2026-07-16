/*
 * flrc_raw_tx_batch.cpp — RP2040 FLRC TX with batch SPI transfer
 *
 * Variant of flrc_raw_tx.cpp using SPIClassRP2040::transfer(txbuf, nullptr, count)
 * (the 3-arg batch method) instead of per-byte transfer(byte) loops.
 *
 * The earlephilhower SPIClassRP2040 provides:
 *   void transfer(const void *txbuf, void *rxbuf, size_t count)
 * For MSBFIRST mode with rxbuf=nullptr, this calls the Pico SDK's
 * spi_write_blocking() — a true batch transfer with proper FIFO management,
 * eliminating per-byte function call overhead.
 *
 * Replaces:
 *   for (size_t i = 0; i < len; i++) spiRf.transfer(data[i]);
 * with:
 *   spiRf.transfer(data, nullptr, len);
 *
 * Also replaces the direct HW register access (spiWriteBurst) in the hot
 * loop with the SDK batch function, providing cleaner code at similar speed.
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

// ─── FLRC Config (MUST match RX) ─────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_BR         2600
#define FLRC_PKT_SIZE   255
#define SPI_FREQ_HZ     20000000UL  // 20MHz Stage 2
#define XTAL_MHZ        52.0f

#define TX_PKT_COUNT    1000
#define TX_POWER_DBM    12

// Sync word — MUST match RX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// ─── SPI helpers ──────────────────────────────────────────────────────
static inline bool rfWaitBusy() {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 100000;
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
    return timeout > 0;
}

// Batch write: uses spi_write_blocking under the hood (MSBFIRST + rxbuf=null)
static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(buf, nullptr, len);  // BATCH: single SDK call
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static uint8_t rfReadStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    uint8_t st = spiRf.transfer(0x00);  // single byte, no batch benefit
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    return st;
}

static uint32_t rfReadIrqStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    uint8_t cmd[2] = { 0x01, 0x17 };
    spiRf.transfer(cmd, nullptr, 2);  // BATCH: write command bytes
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[6];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    uint8_t dummy[6] = {0, 0, 0, 0, 0, 0};
    spiRf.transfer(dummy, buf, 6);  // BATCH: spi_write_read_blocking
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
    uint8_t hdr[2] = { 0x00, 0x02 };
    spiRf.transfer(hdr, nullptr, 2);      // BATCH: FIFO write header
    spiRf.transfer(data, nullptr, len);   // BATCH: payload (255 bytes, one call)
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfClearTxFifo() {
    uint8_t cmd[] = { 0x01, 0x1F };
    rfWriteCmd(cmd, 2);
}

// ─── Hot-loop SPI operations (batch transfer, no begin/endTransaction) ──
// These assume spiRf.beginTransaction was called once in setup() and the
// peripheral stays configured at 20MHz. Each does: CS LOW → batch write → CS HIGH.

// CLR_IRQ: 6 bytes, includes rfWaitBusy (chip transitioning TX→STDBY)
static inline void hotClearIrq() {
    rfWaitBusy();
    digitalWrite(PIN_CS, LOW);
    static uint8_t cmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    spiRf.transfer(cmd, nullptr, 6);  // BATCH
    digitalWrite(PIN_CS, HIGH);
}

// WRITE_FIFO: 2 header bytes + payload, NO rfWaitBusy (chip idle after CLR_IRQ)
static inline void hotWriteFifo(const uint8_t *data, size_t len) {
    digitalWrite(PIN_CS, LOW);
    uint8_t hdr[2] = { 0x00, 0x02 };
    spiRf.transfer(hdr, nullptr, 2);      // BATCH: FIFO header
    spiRf.transfer(data, nullptr, len);   // BATCH: 255 bytes in one SDK call
    digitalWrite(PIN_CS, HIGH);
}

// SET_TX: 5 bytes, NO rfWaitBusy (chip idle after FIFO write)
static inline void hotSetTx() {
    digitalWrite(PIN_CS, LOW);
    static const uint8_t cmd[5] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
    spiRf.transfer(cmd, nullptr, 5);  // BATCH
    digitalWrite(PIN_CS, HIGH);
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

// ─── Raw SPI Init ────────────────────────────────────────────────────
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

    uint32_t frf = (uint32_t)((FLRC_FREQ_MHZ * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    {
        uint8_t cmd[] = {
            0x02, 0x00,
            (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
        };
        rfWriteCmd(cmd, 5);
    }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

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

    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
    delay(5);
    { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x25 }; rfWriteCmd(cmd, 4); }
    delay(1);

    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

    {
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0C,  // preamble=8 (was 16)
            0x4C,
            0x00, (uint8_t)FLRC_PKT_SIZE
        };
        rfWriteCmd(cmd, 6);
    }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);
    { uint8_t cmd[] = { 0x02, 0x03, (uint8_t)(TX_POWER_DBM * 2), 0x04 }; rfWriteCmd(cmd, 4); }
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

// ─── TX burst — batch SPI + IRQ pin poll ──────────────────────────────
static volatile bool radioReady = false;

static void runTransmit() {
    if (!radioReady) { dualPrintln("ERR: radio not initialized"); return; }

    dualPrintf("TX_START count=%d pktSize=%d [BATCH]", TX_PKT_COUNT, FLRC_PKT_SIZE);
    delay(10);

    uint8_t pkt[FLRC_PKT_SIZE];
    for (int j = 4; j < FLRC_PKT_SIZE; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t irqMask = 1UL << PIN_IRQ;
    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    // Lock SPI peripheral for batch transfer in hot loop
    spiRf.beginTransaction(spiSettings);

    for (int i = 0; i < TX_PKT_COUNT; i++) {
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        // 1. Clear IRQ (keep rfWaitBusy — chip transitioning TX→STDBY)
        hotClearIrq();

        // 2. Write TX FIFO (no rfWaitBusy — chip idle after CLR_IRQ)
        hotWriteFifo(pkt, FLRC_PKT_SIZE);

        // 3. Trigger TX (no rfWaitBusy — chip idle after FIFO write)
        hotSetTx();

        // 4. Wait for TX_DONE — IRQ pin HIGH
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
                       i + 1, TX_PKT_COUNT,
                       (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);
        }
    }

    dualPrintf("TX_DONE_STATS: fired=%lu timeout=%lu",
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);

    // DEADBEEF end marker
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
    dualPrintf("  TX sent:     %d [BATCH]", TX_PKT_COUNT);
    dualPrintf("  Elapsed:     %lu ms", (unsigned long)elapsed);
    dualPrintf("  TX THROUGHPUT: %.1f kbps", tput);
    dualPrintln("=============================================");
    dualPrintf("RESULT_TX,sent=%d,elapsed_ms=%lu,throughput_kbps=%.1f,variant=batch",
               TX_PKT_COUNT, (unsigned long)elapsed, tput);
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
    Serial1.println("=== RP2040 FLRC RAW TX v4 BATCH ===");
    Serial1.println("Batch SPI transfer (spi_write_blocking) + IRQ poll + 20MHz");

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    Serial1.println("SPI init done");

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        for (int w = 8; w > 0; w--) {
            Serial.print("WAIT "); Serial.println(w);
            Serial1.print("WAIT "); Serial1.println(w);
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
        Serial1.println("HB alive [BATCH]");
    }

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