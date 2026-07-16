/*
 * flrc_pio_tx.cpp — RP2040 FLRC TX with PIO+DMA SPI (replaces Arduino per-byte SPI)
 * ============================================================================
 *
 * Based on flrc_raw_tx.cpp (v4, proven baseline: 1377 kbps, 1000/1000 TX_DONE)
 * and pio_lr2021_rx.cpp (PIO SPI master with DMA).
 *
 * Uses the same lr2021_rx_program PIO state machine (2-instruction full-duplex
 * SPI Mode 0 MSB-first master) for SPI, with DMA to feed the PIO TX FIFO.
 * CS framing via DMA completion ISR (same pattern as pio_lr2021_rx.cpp).
 *
 * Expected improvement: Arduino per-byte SPI (~535µs overhead) → PIO+DMA
 * (~103µs at 20.83MHz SCK). Should approach ~1900 kbps if real RF output.
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13 LED=GP25
 */

#include <Arduino.h>
#include <string.h>
#include "hardware/pio.h"
#include "hardware/dma.h"
#include "hardware/irq.h"
#include "hardware/gpio.h"
#include "hardware/sync.h"
#include "pio_lr2021_rx.pio.h"

// ─── Pins (same as v4) ───────────────────────────────────────────────
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
#define XTAL_MHZ        52.0f
#define TX_PKT_COUNT    1000
#define TX_POWER_DBM    12
#define PIO_CLK_MHZ     20.83f

// Sync word — MUST match RX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── PIO + DMA state ─────────────────────────────────────────────────
static PIO    g_pio    = pio0;
static uint   g_sm     = 0;
static uint   g_off    = 0;
static int    g_dma_tx = -1;
static int    g_dma_rx = -1;

// DMA buffers (aligned for 32-bit DMA access)
// Max: [0x00, 0x02] + 255 payload = 257 bytes, padded to 260 → 264 is safe
static uint8_t g_tx_buf[264] __attribute__((aligned(4)));
static uint8_t g_rx_buf[264] __attribute__((aligned(4)));

// DMA completion flag (set in ISR, polled in tight loop)
static volatile bool g_dma_done = false;

// ─── DMA completion ISR (DMA_IRQ_0) ──────────────────────────────────
// Uses RX DMA channel for completion signal: the RX DMA completes after the
// TX DMA (all bits have been clocked by the PIO), so deasserting CS here
// is safe — the transaction is truly finished.
static void pio_dma_isr(void) {
    if (g_dma_rx >= 0 && (dma_hw->ints0 & (1u << g_dma_rx))) {
        dma_hw->ints0 = 1u << g_dma_rx;                    /* W1C clear */
        dma_channel_set_irq0_enabled((uint)g_dma_rx, false);
        gpio_put(PIN_CS, HIGH);                            /* deassert NSS */
        g_dma_done = true;
    }
}

// ─── PIO SPI initialization ──────────────────────────────────────────
static int pioSpiInit(void) {
    g_pio = pio0;

    // Pins: SCK/MOSI/MISO to PIO, CS to plain GPIO
    pio_gpio_init(g_pio, PIN_SCK);
    pio_gpio_init(g_pio, PIN_MOSI);
    pio_gpio_init(g_pio, PIN_MISO);
    gpio_init(PIN_CS);
    gpio_set_dir(PIN_CS, GPIO_OUT);
    gpio_put(PIN_CS, HIGH);       /* NSS idle high */

    // Load PIO program + claim state machine
    g_off = pio_add_program(g_pio, &lr2021_rx_program);
    int sm = (int)pio_claim_unused_sm(g_pio, false);
    if (sm < 0) {
        pio_remove_program(g_pio, &lr2021_rx_program, g_off);
        return -1;
    }
    g_sm = (uint)sm;

    // SM config (same as pio_lr2021_rx.cpp)
    pio_sm_config c = lr2021_rx_program_get_default_config(g_off);
    sm_config_set_out_pins(&c, PIN_MOSI, 1);
    sm_config_set_in_pins(&c, PIN_MISO);
    sm_config_set_sideset_pins(&c, PIN_SCK);
    sm_config_set_out_shift(&c, /*shift_right=*/false, /*autopull=*/true,  32);
    sm_config_set_in_shift (&c, /*shift_right=*/false, /*autopush=*/true,  32);

    // SCK = sysclk / (2 * div).  At 125MHz / div=3 → 20.83 MHz
    float div = 125.0f / (2.0f * PIO_CLK_MHZ);
    if (div < 1.0f)     div = 1.0f;
    if (div > 65535.0f)  div = 65535.0f;
    sm_config_set_clkdiv(&c, div);

    // Pin directions
    pio_sm_set_consecutive_pindirs(g_pio, g_sm, PIN_MOSI, 1, /*out=*/true);
    pio_sm_set_consecutive_pindirs(g_pio, g_sm, PIN_SCK,  1, /*out=*/true);
    pio_sm_set_consecutive_pindirs(g_pio, g_sm, PIN_MISO, 1, /*out=*/false);
    pio_sm_init(g_pio, g_sm, g_off, &c);

    // Claim DMA channels
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

    // TX DMA: SRAM(g_tx_buf) → PIO TX FIFO, 32-bit, read-increment, BSWAP.
    // BSWAP + MSB-first shift ⇒ wire-order bytes in SRAM leave the pin in order.
    {
        dma_channel_config dc = dma_channel_get_default_config((uint)g_dma_tx);
        channel_config_set_transfer_data_size(&dc, DMA_SIZE_32);
        channel_config_set_read_increment(&dc, true);
        channel_config_set_write_increment(&dc, false);
        channel_config_set_bswap(&dc, true);
        channel_config_set_dreq(&dc, pio_get_dreq(g_pio, g_sm, /*is_tx=*/true));
        dma_channel_configure((uint)g_dma_tx, &dc,
            /*write_addr*/ &g_pio->txf[g_sm],
            /*read_addr*/  g_tx_buf,
            /*count*/      0,            /* set per-transfer */
            /*trigger*/    false);
    }

    // RX DMA: PIO RX FIFO → SRAM(g_rx_buf), 32-bit, write-increment, BSWAP.
    // Drains the RX FIFO so the PIO never stalls on `in` (FIFO full).
    // BSWAP + MSB-first shift ⇒ wire-order bytes land in SRAM in order.
    {
        dma_channel_config dc = dma_channel_get_default_config((uint)g_dma_rx);
        channel_config_set_transfer_data_size(&dc, DMA_SIZE_32);
        channel_config_set_read_increment(&dc, false);
        channel_config_set_write_increment(&dc, true);
        channel_config_set_bswap(&dc, true);
        channel_config_set_dreq(&dc, pio_get_dreq(g_pio, g_sm, /*is_tx=*/false));
        dma_channel_configure((uint)g_dma_rx, &dc,
            /*write_addr*/ g_rx_buf,
            /*read_addr*/  &g_pio->rxf[g_sm],
            /*count*/      0,
            /*trigger*/    false);
    }

    // DMA completion IRQ
    irq_add_shared_handler(DMA_IRQ_0, pio_dma_isr,
                            PICO_SHARED_IRQ_HANDLER_DEFAULT_ORDER_PRIORITY);
    irq_set_enabled(DMA_IRQ_0, true);

    // Start SM: runs the 2-instruction loop, stalled on `out` (TX FIFO empty)
    // with SCK LOW.  This is the idle state between transactions.
    pio_sm_set_enabled(g_pio, g_sm, true);
    return 0;
}

// ─── PIO SPI helpers ─────────────────────────────────────────────────

// Force SCK low via exec (same as pio_lr2021_rx.cpp arm()).
// Injects MOV Y,Y side 0 to set SCK low before asserting CS.
static inline void forceSckLow(void) {
    pio_sm_exec(g_pio, g_sm,
                pio_encode_mov(pio_y, pio_y) | pio_encode_sideset_opt(1, 0));
}

// Drain PIO RX FIFO (clear any stale data from previous transactions).
static inline void drainRxFifo(void) {
    uint32_t rx_empty_bit = 1u << (g_sm * 4);   /* FSTAT: RXEMPTY at sm*4 */
    while (!(g_pio->fstat & rx_empty_bit)) {
        (void)g_pio->rxf[g_sm];
    }
}

// Synchronous PIO SPI transfer.
// g_tx_buf must be pre-filled with the bytes to send (wire order).
// tx_len is the number of bytes (padded to 4-byte boundary internally).
// On return, g_rx_buf contains received bytes (wire order, padded).
//
// Sequence: drain RX FIFO → force SCK low → assert CS → start TX+RX DMA
//           → wait for RX DMA completion ISR (deasserts CS) → return.
static void pioSpiXferRaw(const uint8_t *tx_data, size_t tx_len) {
    // Copy to DMA buffer if not already there
    if (tx_data != g_tx_buf) {
        memcpy(g_tx_buf, tx_data, tx_len);
    }
    // Pad to 4-byte boundary (DMA moves 32-bit words)
    size_t padded_len = (tx_len + 3u) & ~3u;
    for (size_t i = tx_len; i < padded_len; i++)
        g_tx_buf[i] = 0x00;
    size_t words = padded_len / 4u;

    // Drain stale RX data
    drainRxFifo();

    // Force SCK low for clean SPI Mode 0 entry
    forceSckLow();

    // Assert NSS
    gpio_put(PIN_CS, LOW);

    // Configure DMA channels for this transfer
    dma_channel_set_read_addr((uint)g_dma_tx, g_tx_buf, /*trigger=*/false);
    dma_channel_set_trans_count((uint)g_dma_tx, words, /*trigger=*/false);
    dma_channel_set_write_addr((uint)g_dma_rx, g_rx_buf, /*trigger=*/false);
    dma_channel_set_trans_count((uint)g_dma_rx, words, /*trigger=*/false);

    // Enable RX DMA completion IRQ
    dma_channel_set_irq0_enabled((uint)g_dma_rx, true);
    g_dma_done = false;

    // Start both channels simultaneously (lockstep from first bit)
    dma_start_channel_mask((1u << (uint)g_dma_tx) | (1u << (uint)g_dma_rx));

    // Wait for completion (ISR deasserts CS and sets g_dma_done)
    while (!g_dma_done) {
        /* tight poll */
    }
}

// ─── SPI helpers (PIO+DMA replaces Arduino SPI) ──────────────────────

static inline bool rfWaitBusy() {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 100000;
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
    return timeout > 0;
}

// Write command: wait BUSY → CS frame + DMA send → wait BUSY
static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    pioSpiXferRaw(buf, len);
    rfWaitBusy();
}

// Write TX FIFO: [0x00, 0x02] header + payload bytes
static void rfWriteTxFifo(const uint8_t *data, size_t len) {
    rfWaitBusy();
    g_tx_buf[0] = 0x00;
    g_tx_buf[1] = 0x02;
    memcpy(g_tx_buf + 2, data, len);
    pioSpiXferRaw(g_tx_buf, len + 2);
    rfWaitBusy();
}

// Read status register (single byte, padded to 4 for DMA 32-bit alignment)
static uint8_t rfReadStatus() {
    rfWaitBusy();
    g_tx_buf[0] = 0x00;           /* read status command */
    g_tx_buf[1] = 0x00;
    g_tx_buf[2] = 0x00;
    g_tx_buf[3] = 0x00;
    pioSpiXferRaw(g_tx_buf, 4);  /* 4 bytes = 1 DMA word */
    return g_rx_buf[0];           /* first received byte = status */
}

// Read IRQ status register (two CS-framed transactions, same as v4)
static uint32_t rfReadIrqStatus() {
    rfWaitBusy();
    // First transaction: send read command [0x01, 0x17]
    g_tx_buf[0] = 0x01;
    g_tx_buf[1] = 0x17;
    pioSpiXferRaw(g_tx_buf, 2);

    rfWaitBusy();

    // Second transaction: send 8 dummy bytes (padded to 8 for DMA 32-bit)
    memset(g_tx_buf, 0x00, 8);
    pioSpiXferRaw(g_tx_buf, 8);
    // g_rx_buf[0..1] = status/echo (discarded), g_rx_buf[2..5] = IRQ status
    return ((uint32_t)g_rx_buf[2] << 24) | ((uint32_t)g_rx_buf[3] << 16) |
           ((uint32_t)g_rx_buf[4] << 8) | (uint32_t)g_rx_buf[5];
}

static void rfClearIrq() {
    uint8_t cmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 6);
}

static void rfSetTx() {
    uint8_t cmd[5] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
    rfWriteCmd(cmd, 5);
}

static void rfClearTxFifo() {
    uint8_t cmd[] = { 0x01, 0x1F };
    rfWriteCmd(cmd, 2);
}

// ─── Dual output (Serial USB CDC + Serial1 UART) ─────────────────────
// NO Serial.flush() — it blocks CDC.
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

// ─── Raw SPI Init (EXACT same sequence as v4, using PIO+DMA) ──────────
static volatile bool radioReady = false;

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
            0x0C,  // preamble=8
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

// ─── TX burst (same structure as v4, using PIO+DMA SPI) ──────────────
static void runTransmit() {
    if (!radioReady) { dualPrintln("ERR: radio not initialized"); return; }

    dualPrintf("TX_START count=%d pktSize=%d", TX_PKT_COUNT, FLRC_PKT_SIZE);
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

        // 1. Clear IRQ
        rfClearIrq();

        // 2. Write TX FIFO
        rfWriteTxFifo(pkt, FLRC_PKT_SIZE);

        // 3. Trigger TX
        rfSetTx();

        // 4. Wait for TX_DONE — IRQ pin HIGH
        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 500000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
        }

        // Print spin count for first 5 packets — smoke test for fake results
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
    dualPrintf("  TX sent:     %d", TX_PKT_COUNT);
    dualPrintf("  Elapsed:     %lu ms", (unsigned long)elapsed);
    dualPrintf("  TX THROUGHPUT: %.1f kbps", tput);
    dualPrintln("=============================================");
    dualPrintf("RESULT_TX,sent=%d,elapsed_ms=%lu,throughput_kbps=%.1f",
               TX_PKT_COUNT, (unsigned long)elapsed, tput);
}

// ─── Arduino entry points ───────────────────────────────────────────
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
    Serial1.println("=== RP2040 FLRC PIO TX ===");
    Serial1.println("PIO+DMA SPI @ 20.83MHz + IRQ poll");

    // Initialize PIO SPI
    int rc = pioSpiInit();
    if (rc != 0) {
        Serial1.print("PIO SPI init FAILED: ");
        Serial1.println(rc);
        Serial.println("PIO INIT FAILED");
        return;
    }
    Serial1.println("PIO SPI init OK");

    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        // 8-second wait window with heartbeat (gives RX time to enter RX mode)
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