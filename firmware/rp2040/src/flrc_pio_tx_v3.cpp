/*
 * flrc_pio_tx_v3.cpp — Hybrid Arduino+PIO SPI TX v3 (UART-only during PIO)
 * ============================================================================
 *
 * FIX for v3: UART-only output during PIO mode. No Serial (CDC) calls
 * then switches to PIO+DMA only for the TX hot loop (after CDC established).
 *
 * Sequence:
 *   1. Serial.begin() + Serial1.begin()  — CDC starts
 *   2. spiRf.begin()                     — Arduino SPI (CDC-safe)
 *   3. rawInitRadio() via Arduino SPI    — Radio init (CDC-safe)
 *   4. Print INIT + WAIT messages         — CDC output verified
 *   5. spiRf.end()                        — Release Arduino SPI
 *   6. pioSpiInit()                       — PIO+DMA init (CDC already alive)
 *   7. runTransmit()                      — PIO SPI hot loop
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13 LED=GP25
 */

#include <Arduino.h>
#include <SPI.h>
#include <string.h>
#include "hardware/pio.h"
#include "hardware/dma.h"
#include "hardware/irq.h"
#include "hardware/gpio.h"
#include "hardware/sync.h"
#include "pio_lr2021_rx.pio.h"

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
#define SPI_FREQ_HZ     20000000UL
#define XTAL_MHZ        52.0f
#define TX_PKT_COUNT    1000
#define TX_POWER_DBM    12
#define PIO_CLK_MHZ     20.83f

#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── Arduino SPI (for init only) ────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// ─── Arduino SPI helpers (for radio init) ───────────────────────────
static inline bool ardWaitBusy() {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 100000;
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
    return timeout > 0;
}

static void ardWriteCmd(const uint8_t *buf, size_t len) {
    ardWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static uint8_t ardReadStatus() {
    ardWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    uint8_t st = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    return st;
}

static uint32_t ardReadIrqStatus() {
    ardWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x01); spiRf.transfer(0x17);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    ardWaitBusy();

    uint8_t buf[6];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 6; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    return ((uint32_t)buf[2] << 24) | ((uint32_t)buf[3] << 16) |
           ((uint32_t)buf[4] << 8) | (uint32_t)buf[5];
}

static void ardClearIrq() {
    uint8_t cmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    ardWriteCmd(cmd, 6);
}

// ─── PIO + DMA state (for TX hot loop) ───────────────────────────────
static PIO    g_pio    = pio0;
static uint   g_sm     = 0;
static uint   g_off    = 0;
static int    g_dma_tx = -1;
static int    g_dma_rx = -1;

static uint8_t g_tx_buf[264] __attribute__((aligned(4)));
static uint8_t g_rx_buf[264] __attribute__((aligned(4)));
static volatile bool g_dma_done = false;

static void pio_dma_isr(void) {
    if (g_dma_rx >= 0 && (dma_hw->ints0 & (1u << g_dma_rx))) {
        dma_hw->ints0 = 1u << g_dma_rx;
        dma_channel_set_irq0_enabled((uint)g_dma_rx, false);
        gpio_put(PIN_CS, HIGH);
        g_dma_done = true;
    }
}

static int pioSpiInit(void) {
    g_pio = pio0;

    pio_gpio_init(g_pio, PIN_SCK);
    pio_gpio_init(g_pio, PIN_MOSI);
    pio_gpio_init(g_pio, PIN_MISO);

    g_off = pio_add_program(g_pio, &lr2021_rx_program);
    int sm = (int)pio_claim_unused_sm(g_pio, false);
    if (sm < 0) { pio_remove_program(g_pio, &lr2021_rx_program, g_off); return -1; }
    g_sm = (uint)sm;

    pio_sm_config c = lr2021_rx_program_get_default_config(g_off);
    sm_config_set_out_pins(&c, PIN_MOSI, 1);
    sm_config_set_in_pins(&c, PIN_MISO);
    sm_config_set_sideset_pins(&c, PIN_SCK);
    sm_config_set_out_shift(&c, false, true, 32);
    sm_config_set_in_shift(&c, false, true, 32);

    float div = 125.0f / (2.0f * PIO_CLK_MHZ);
    if (div < 1.0f) div = 1.0f;
    sm_config_set_clkdiv(&c, div);

    pio_sm_set_consecutive_pindirs(g_pio, g_sm, PIN_MOSI, 1, true);
    pio_sm_set_consecutive_pindirs(g_pio, g_sm, PIN_SCK, 1, true);
    pio_sm_set_consecutive_pindirs(g_pio, g_sm, PIN_MISO, 1, false);
    pio_sm_init(g_pio, g_sm, g_off, &c);

    g_dma_tx = (int)dma_claim_unused_channel(false);
    g_dma_rx = (int)dma_claim_unused_channel(false);
    if (g_dma_tx < 0 || g_dma_rx < 0) {
        if (g_dma_tx >= 0) dma_channel_unclaim((uint)g_dma_tx);
        if (g_dma_rx >= 0) dma_channel_unclaim((uint)g_dma_rx);
        pio_sm_unclaim(g_pio, g_sm);
        pio_remove_program(g_pio, &lr2021_rx_program, g_off);
        g_dma_tx = g_dma_rx = -1;
        return -2;
    }

    {
        dma_channel_config dc = dma_channel_get_default_config((uint)g_dma_tx);
        channel_config_set_transfer_data_size(&dc, DMA_SIZE_32);
        channel_config_set_read_increment(&dc, true);
        channel_config_set_write_increment(&dc, false);
        channel_config_set_bswap(&dc, true);
        channel_config_set_dreq(&dc, pio_get_dreq(g_pio, g_sm, true));
        dma_channel_configure((uint)g_dma_tx, &dc, &g_pio->txf[g_sm], g_tx_buf, 0, false);
    }
    {
        dma_channel_config dc = dma_channel_get_default_config((uint)g_dma_rx);
        channel_config_set_transfer_data_size(&dc, DMA_SIZE_32);
        channel_config_set_read_increment(&dc, false);
        channel_config_set_write_increment(&dc, true);
        channel_config_set_bswap(&dc, true);
        channel_config_set_dreq(&dc, pio_get_dreq(g_pio, g_sm, false));
        dma_channel_configure((uint)g_dma_rx, &dc, g_rx_buf, &g_pio->rxf[g_sm], 0, false);
    }

    irq_add_shared_handler(DMA_IRQ_0, pio_dma_isr, PICO_SHARED_IRQ_HANDLER_DEFAULT_ORDER_PRIORITY);
    irq_set_enabled(DMA_IRQ_0, true);
    pio_sm_set_enabled(g_pio, g_sm, true);
    return 0;
}

// ─── PIO SPI helpers (for TX hot loop) ────────────────────────────────
static inline void forceSckLow(void) {
    pio_sm_exec(g_pio, g_sm, pio_encode_mov(pio_y, pio_y) | pio_encode_sideset_opt(1, 0));
}

static inline void drainRxFifo(void) {
    uint32_t rx_empty_bit = 1u << (g_sm * 4);
    while (!(g_pio->fstat & rx_empty_bit)) { (void)g_pio->rxf[g_sm]; }
}

static void pioSpiXfer(const uint8_t *tx_data, size_t tx_len) {
    if (tx_data != g_tx_buf) memcpy(g_tx_buf, tx_data, tx_len);
    size_t padded_len = (tx_len + 3u) & ~3u;
    for (size_t i = tx_len; i < padded_len; i++) g_tx_buf[i] = 0x00;
    size_t words = padded_len / 4u;

    drainRxFifo();
    forceSckLow();
    gpio_put(PIN_CS, LOW);

    dma_channel_set_read_addr((uint)g_dma_tx, g_tx_buf, false);
    dma_channel_set_trans_count((uint)g_dma_tx, words, false);
    dma_channel_set_write_addr((uint)g_dma_rx, g_rx_buf, false);
    dma_channel_set_trans_count((uint)g_dma_rx, words, false);
    dma_channel_set_irq0_enabled((uint)g_dma_rx, true);
    g_dma_done = false;
    dma_start_channel_mask((1u << (uint)g_dma_tx) | (1u << (uint)g_dma_rx));
    while (!g_dma_done) {}
}

static inline bool pioWaitBusy() {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 100000;
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
    return timeout > 0;
}

static void pioWriteCmd(const uint8_t *buf, size_t len) {
    pioWaitBusy();
    pioSpiXfer(buf, len);
    pioWaitBusy();
}

static void pioWriteTxFifo(const uint8_t *data, size_t len) {
    pioWaitBusy();
    g_tx_buf[0] = 0x00;
    g_tx_buf[1] = 0x02;
    memcpy(g_tx_buf + 2, data, len);
    pioSpiXfer(g_tx_buf, len + 2);
    pioWaitBusy();
}

static void pioClearIrq() {
    uint8_t cmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    pioWriteCmd(cmd, 6);
}

static void pioSetTx() {
    uint8_t cmd[5] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
    pioWriteCmd(cmd, 5);
}

static void pioClearTxFifo() {
    uint8_t cmd[] = { 0x01, 0x1F };
    pioWriteCmd(cmd, 2);
}

// ─── Dual output ─────────────────────────────────────────────────────
static void dualPrint(const char *s) { Serial.print(s); Serial1.print(s); }
static void dualPrintln(const char *s) { Serial.println(s); Serial1.println(s); }
static void dualPrintln() { Serial.println(); Serial1.println(); }

// UART-only output (for PIO mode — never touches CDC)
static void uartPrintf(const char *fmt, ...) {
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial1.println(buf);
}
static void uartPrintln(const char *s) { Serial1.println(s); }

static void dualPrintf(const char *fmt, ...) {
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.println(buf);
    Serial1.println(buf);
}

// ─── Radio init (using Arduino SPI — CDC-safe) ───────────────────────
static volatile bool radioReady = false;

static bool rawInitRadio() {
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; ardWriteCmd(cmd, 4); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; ardWriteCmd(cmd, 3); }
    delay(5);
    { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; ardWriteCmd(cmd, 3); }
    delay(1);

    uint32_t frf = (uint32_t)((FLRC_FREQ_MHZ * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    {
        uint8_t cmd[] = { 0x02, 0x00, (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF) };
        ardWriteCmd(cmd, 5);
    }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; ardWriteCmd(cmd, 4); }
    delay(1);

    uint16_t feFreq = (uint16_t)((FLRC_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
    {
        uint8_t cmd[] = { 0x01, 0x23, (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
                          0x00, 0x00, 0x00, 0x00, 0x00, 0x00 };
        ardWriteCmd(cmd, 10);
    }
    delay(5);

    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; ardWriteCmd(cmd, 3); }
    delay(5);
    { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x25 }; ardWriteCmd(cmd, 4); }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
      ardWriteCmd(cmd, 7); }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x49, 0x0C, 0x4C, 0x00, (uint8_t)FLRC_PKT_SIZE };
      ardWriteCmd(cmd, 6); }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; ardWriteCmd(cmd, 7); }
    delay(1);
    { uint8_t cmd[] = { 0x02, 0x03, (uint8_t)(TX_POWER_DBM * 2), 0x04 }; ardWriteCmd(cmd, 4); }
    delay(1);
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; ardWriteCmd(cmd, 3); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; ardWriteCmd(cmd, 4); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 }; ardWriteCmd(cmd, 7); }
    delay(1);

    ardClearIrq();
    delay(1);

    uint8_t st = ardReadStatus();
    uint32_t irq = ardReadIrqStatus();
    dualPrintf("INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    if ((st >> 4) == 0x04 || (st >> 4) == 0x07 || (irq & 0x00020000)) {
        dualPrintln("RADIO_INIT_OK");
        return true;
    }
    dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

// ─── TX burst (using PIO+DMA SPI — fast path) ─────────────────────────
static void runTransmit() {
    if (!radioReady) { uartPrintln("ERR: radio not initialized"); return; }

    uartPrintf("TX_START count=%d pktSize=%d", TX_PKT_COUNT, FLRC_PKT_SIZE);
    delay(10);

    uint8_t pkt[FLRC_PKT_SIZE];
    for (int j = 4; j < FLRC_PKT_SIZE; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t irqMask = 1UL << PIN_IRQ;
    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    for (int i = 0; i < TX_PKT_COUNT; i++) {
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        pioClearIrq();
        pioWriteTxFifo(pkt, FLRC_PKT_SIZE);
        pioSetTx();

        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 500000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
        }

        if (i < 5) {
            uartPrintf("PKT %d: irqPin=%d spin=%lu", i, irqFired ? 1 : 0,
                       (unsigned long)spinCount);
        }

        if (irqFired) txDoneCount++;
        else txTimeoutCount++;

        if ((i + 1) % 200 == 0) {
            uartPrintf("TX %d/%d (done=%lu to=%lu)", i + 1, TX_PKT_COUNT,
                       (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);
        }
    }

    uartPrintf("TX_DONE_STATS: fired=%lu timeout=%lu",
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);

    // DEADBEEF end marker
    pkt[0] = 0xDE; pkt[1] = 0xAD; pkt[2] = 0xBE; pkt[3] = 0xEF;
    pkt[4] = (uint8_t)(TX_PKT_COUNT >> 24);
    pkt[5] = (uint8_t)(TX_PKT_COUNT >> 16);
    pkt[6] = (uint8_t)(TX_PKT_COUNT >> 8);
    pkt[7] = (uint8_t)(TX_PKT_COUNT & 0xFF);
    pioClearTxFifo();
    pioWriteTxFifo(pkt, FLRC_PKT_SIZE);
    pioSetTx();
    delay(5);

    uint32_t elapsed = millis() - startMs;
    float tput = ((float)TX_PKT_COUNT * FLRC_PKT_SIZE * 8.0f) / elapsed;

    uartPrintln("=============================================");
    uartPrintf("  TX sent:     %d", TX_PKT_COUNT);
    uartPrintf("  Elapsed:     %lu ms", (unsigned long)elapsed);
    uartPrintf("  TX THROUGHPUT: %.1f kbps", tput);
    uartPrintln("=============================================");
    uartPrintf("RESULT_TX,sent=%d,elapsed_ms=%lu,throughput_kbps=%.1f",
               TX_PKT_COUNT, (unsigned long)elapsed, tput);
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);
    delay(2000); // CDC fix: TinyUSB needs 2s for enumeration

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(120);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(120);
    }

    Serial1.println();
    Serial1.println("=== RP2040 FLRC PIO TX v3 (Hybrid) ===");
    Serial1.println("Arduino SPI for init, PIO+DMA for TX");

    // Step 1: Arduino SPI init (CDC-safe)
    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    Serial1.println("Arduino SPI init done");

    // Step 2: Radio init via Arduino SPI
    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);

        // Step 3: Wait window with heartbeat (CDC confirmed alive)
        for (int w = 8; w > 0; w--) {
            Serial.print("WAIT ");
            Serial.println(w);
            Serial1.print("WAIT ");
            Serial1.println(w);
            delay(1000);
        }

        // Step 4: Release Arduino SPI, switch to PIO+DMA
        spiRf.end();
        uartPrintln("Arduino SPI released. Starting PIO+DMA...");

        int rc = pioSpiInit();
        if (rc != 0) {
            uartPrintln("PIO SPI init FAILED");
            uartPrintf("  rc=%d", rc);
            uartPrintln("PIO INIT FAILED");
            return;
        }
        uartPrintln("PIO+DMA SPI init OK");
        uartPrintln("PIO INIT OK — starting TX");

        // Step 5: TX burst with PIO+DMA
        runTransmit();
    } else {
        Serial1.println("INIT FAILED");
        Serial.println("INIT FAILED");
    }
}

void loop() {
    static unsigned long lastHB = 0;
    if (millis() - lastHB > 2000) {
        lastHB = millis();
        Serial1.println("HB alive");
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
