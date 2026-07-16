/*
 * flrc_dma_tx.cpp — RP2040 FLRC TX with DMA-based SPI FIFO writes
 *
 * Phase 3: Uses RP2040 DMA to feed spi0 TX FIFO autonomously,
 * eliminating CPU wait time for the 255-byte FIFO write.
 *
 * While the radio is transmitting packet N, the CPU can prepare
 * packet N+1's DMA buffer. The DMA engine fills the SPI TX FIFO
 * at hardware speed instead of polling TNF bit in a loop.
 *
 * Output: Serial (USB) + Serial1 (UART GP12→ESP32 bridge)
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13
 */

#include <Arduino.h>
#include <SPI.h>
#include "hardware/dma.h"
#include "hardware/spi.h"

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

// ─── DMA ─────────────────────────────────────────────────────────────
static int dma_chan = -1;

// DMA transfer buffer: WRITE_TX_FIFO header (2 bytes) + payload (255 bytes)
static uint8_t dma_fifo_buf[2 + FLRC_PKT_SIZE];  // 257 bytes

// ─── Raw SPI helpers (same as flrc_raw_tx.cpp) ───────────────────────
static inline void rfWaitBusy() {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 500000;  // ~4ms at 125MHz
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
}

static inline void spiDrain() {
    spi_hw_t *hw = spi0_hw;
    while (!(hw->sr & SPI_SSPSR_TFE_BITS)) {}
    while (hw->sr & SPI_SSPSR_RNE_BITS) (void)hw->dr;
}

// ─── DMA SPI write ───────────────────────────────────────────────────
// Transfers 'len' bytes from 'src' to spi0->dr using DMA.
// Caller is responsible for CS toggle and BUSY wait before/after.
// Blocks until DMA transfer completes and SPI FIFO fully drained.
static inline void dmaSpiWrite(const uint8_t *src, size_t len) {
    dma_channel_config c = dma_channel_get_default_config(dma_chan);
    channel_config_set_transfer_data_size(&c, DMA_SIZE_8);
    channel_config_set_dreq(&c, spi_get_dreq(spi0, true));  // TX DREQ
    channel_config_set_read_increment(&c, true);   // Increment source pointer
    channel_config_set_write_increment(&c, false);  // Fixed dest (SPI DR)

    dma_channel_configure(dma_chan, &c,
        &spi0_hw->dr,    // dest: SPI TX FIFO data register
        src,              // src: command + data
        len,              // transfer count in bytes
        false             // don't start yet
    );
    dma_channel_start(dma_chan);
    dma_channel_wait_for_finish_blocking(dma_chan);

    // Wait for SPI TX FIFO to fully drain (DMA wrote to FIFO, SPI still clocking out)
    while (!(spi0_hw->sr & SPI_SSPSR_TFE_BITS)) {}
    // Drain RX FIFO (SPI is full-duplex, reads come back)
    while (spi0_hw->sr & SPI_SSPSR_RNE_BITS) (void)spi0_hw->dr;
}

// ─── RF command wrappers using DMA ───────────────────────────────────
static void dmaWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    gpio_put(PIN_CS, 0);   // CS LOW — direct SIO for speed
    dmaSpiWrite(buf, len);
    gpio_put(PIN_CS, 1);   // CS HIGH
}

static void rfClearIrq() {
    static const uint8_t cmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    dmaWriteCmd(cmd, 6);
}

static void rfSetTx() {
    static const uint8_t cmd[5] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
    dmaWriteCmd(cmd, 5);
}

static void rfSetStandby() {
    uint8_t cmd[] = { 0x01, 0x28, 0x01 };
    dmaWriteCmd(cmd, 3);
}

// DMA-based TX FIFO write — builds header + payload into contiguous buffer
// and DMAs it in one shot (no CPU per-byte loop)
static void rfWriteTxFifoDMA(const uint8_t *data, size_t len) {
    // Pre-build contiguous buffer: WRITE_TX_FIFO opcode + payload
    dma_fifo_buf[0] = 0x00;  // opcode MSB
    dma_fifo_buf[1] = 0x02;  // opcode LSB (WRITE_TX_FIFO)
    memcpy(&dma_fifo_buf[2], data, len);

    rfWaitBusy();
    gpio_put(PIN_CS, 0);
    dmaSpiWrite(dma_fifo_buf, 2 + len);
    gpio_put(PIN_CS, 1);
}

static void rfClearTxFifo() {
    uint8_t cmd[] = { 0x01, 0x1F };
    dmaWriteCmd(cmd, 2);
}

// ─── Legacy SPI helpers for init diagnostics ─────────────────────────
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

// ─── Raw SPI Init (identical to flrc_raw_tx.cpp rawInitRadio) ────────
static bool rawInitRadio() {
    // 0. Hardware reset
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    // 1. CLEAR_ERRORS
    { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; dmaWriteCmd(cmd, 4); }
    delay(1);

    // 2. SET_STANDBY (STDBY_XOSC = 0x01)
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; dmaWriteCmd(cmd, 3); }
    delay(5);

    // 3. SET_PACKET_TYPE FLRC
    { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; dmaWriteCmd(cmd, 3); }
    delay(1);

    // 4. SET_RF_FREQUENCY
    uint32_t frf = (uint32_t)((FLRC_FREQ_MHZ * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    {
        uint8_t cmd[] = {
            0x02, 0x00,
            (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
        };
        dmaWriteCmd(cmd, 5);
    }
    delay(1);

    // 5. SET_RX_PATH (HF path for 2.4 GHz) — needed even on TX for PLL
    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; dmaWriteCmd(cmd, 4); }
    delay(1);

    // 6. CALIB_FRONT_END
    uint16_t feFreq = (uint16_t)((FLRC_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
    {
        uint8_t cmd[] = {
            0x01, 0x23,
            (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        };
        dmaWriteCmd(cmd, 10);
    }
    delay(5);

    // 7. CALIBRATE — defined bits only 0x5F (per TheClams reference)
    // Bit 5 is undefined on LR2021 Gen4, was 0x6F before
    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; dmaWriteCmd(cmd, 3); }
    delay(5);

    // 8. SET_FLRC_MOD_PARAMS
    { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x25 }; dmaWriteCmd(cmd, 4); }
    delay(1);

    // 9. SET_FLRC_SYNCWORD
    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        dmaWriteCmd(cmd, 7);
    }
    delay(1);

    // 10. SET_FLRC_PACKET_PARAMS (same as RX, but with syncWordTx=1)
    {
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0E,  // preamble idx 3 (16) | syncLen 2
            0x4C,  // syncTx=1 | syncMatch=1 | fixed=1 | crc=0
            0x00, (uint8_t)FLRC_PKT_SIZE
        };
        dmaWriteCmd(cmd, 6);
    }
    delay(1);

    // 11. SET_PA_CONFIG (HF PA select via bit 7)
    //     RadioLib: setPaConfig(highFreq=1, ...) → byte0 = (1 << 7) = 0x80
    //     BUGFIX: was 0x01 (bit 0), must be 0x80 (bit 7) for HF PA
    {
        uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 };
        dmaWriteCmd(cmd, 7);
    }
    delay(1);

    // 12. SET_TX_PARAMS (power + ramp)
    //     RadioLib: setTxParams sends txPower*2 as raw byte
    //     BUGFIX: was sending raw dBm, must multiply by 2
    { uint8_t cmd[] = { 0x02, 0x03, (uint8_t)(TX_POWER_DBM * 2), 0x04 }; dmaWriteCmd(cmd, 4); }
    delay(1);

    // 14. SET_RX_TX_FALLBACK (Fs=0x03 per TheClams reference)
    // Fs mode keeps PLL running between TX cycles — no PLL re-lock delay
    // STDBY_RC (0x00) stops PLL → 90% CMD_ERROR on subsequent SET_TX
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; dmaWriteCmd(cmd, 3); }
    delay(1);

    // 15. DIO function — DIO9 = IRQ for TX_DONE
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; dmaWriteCmd(cmd, 4); }
    delay(1);

    // 16. DIO IRQ config — map TX_DONE (bit 19 = 0x00080000) to DIO9
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 }; dmaWriteCmd(cmd, 7); }
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

// ─── TX burst (DMA hot loop) ─────────────────────────────────────────
static volatile bool radioReady = false;

static void runTransmit() {
    if (!radioReady) { dualPrintln("ERR: radio not initialized"); return; }

    dualPrintf("TX_START count=%d pktSize=%d (DMA SPI)", TX_PKT_COUNT, FLRC_PKT_SIZE);
    delay(10);

    // Pre-build packet payload ONCE — only update seq bytes per iteration
    uint8_t pkt[FLRC_PKT_SIZE];
    for (int j = 4; j < FLRC_PKT_SIZE; j++) pkt[j] = (uint8_t)(j & 0xFF);

    // IRQ pin mask for fast GPIO polling (avoid digitalRead overhead)
    uint32_t irqMask = 1UL << PIN_IRQ;
    uint32_t busyMask = 1UL << PIN_BUSY;

    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    // Static command arrays (avoid stack alloc per iteration)
    static const uint8_t clrCmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    static const uint8_t txCmd[5] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };

    for (int i = 0; i < TX_PKT_COUNT; i++) {
        // Update only seq bytes (4 bytes, no inner loop)
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        // === DMA HOT LOOP — DMA feeds SPI FIFO at hardware speed ===

        // 1. Clear IRQ flags (CLR_IRQ = 0x0116)
        rfWaitBusy();
        gpio_put(PIN_CS, 0);
        dmaSpiWrite(clrCmd, 6);
        gpio_put(PIN_CS, 1);

        // 2. Write TX FIFO via DMA (WRITE_TX_FIFO = 0x0002 + payload)
        //    DMA writes 257 bytes to SPI FIFO autonomously — zero CPU wait
        rfWaitBusy();
        gpio_put(PIN_CS, 0);

        // Build contiguous buffer: header + payload
        dma_fifo_buf[0] = 0x00;
        dma_fifo_buf[1] = 0x02;
        memcpy(&dma_fifo_buf[2], pkt, FLRC_PKT_SIZE);

        dmaSpiWrite(dma_fifo_buf, 2 + FLRC_PKT_SIZE);
        gpio_put(PIN_CS, 1);

        // Diagnostic for first 5 packets only
        uint8_t stPre = 0;
        if (i < 5) stPre = rfReadStatus();

        // 3. Trigger TX (SET_TX = 0x020D + 3-byte timeout)
        rfWaitBusy();
        gpio_put(PIN_CS, 0);
        dmaSpiWrite(txCmd, 5);
        gpio_put(PIN_CS, 1);

        // 4. Wait for TX_DONE — TIGHT GPIO spin (no millis() in inner loop)
        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 500000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
        }

        // Diagnostic for first 5 packets
        if (i < 5) {
            uint8_t stPost = rfReadStatus();
            uint32_t irqStatus = rfReadIrqStatus();
            dualPrintf("PKT %d: preSt=0x%02X irqPin=%d postSt=0x%02X IRQ=0x%08lX spin=%lu",
                       i, stPre, irqFired ? 1 : 0, stPost,
                       (unsigned long)irqStatus, (unsigned long)spinCount);
        }

        if (irqFired) txDoneCount++;
        else txTimeoutCount++;

        // Progress every 500 (less Serial overhead)
        if ((i + 1) % 500 == 0) {
            dualPrintf("TX %d/%d (done=%lu to=%lu)",
                       i + 1, TX_PKT_COUNT,
                       (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);
        }
    }

    dualPrintf("TX_DONE_STATS: fired=%lu timeout=%lu",
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);

    // Send DEADBEEF end marker with total count
    pkt[0] = 0xDE; pkt[1] = 0xAD; pkt[2] = 0xBE; pkt[3] = 0xEF;
    pkt[4] = (uint8_t)(TX_PKT_COUNT >> 24);
    pkt[5] = (uint8_t)(TX_PKT_COUNT >> 16);
    pkt[6] = (uint8_t)(TX_PKT_COUNT >> 8);
    pkt[7] = (uint8_t)(TX_PKT_COUNT & 0xFF);
    rfClearTxFifo();
    rfWriteTxFifoDMA(pkt, FLRC_PKT_SIZE);
    rfSetTx();
    delay(5);

    uint32_t elapsed = millis() - startMs;
    float tput = ((float)TX_PKT_COUNT * FLRC_PKT_SIZE * 8.0f) / elapsed;

    dualPrintln("=============================================");
    dualPrintf("  TX sent:     %d", TX_PKT_COUNT);
    dualPrintf("  Elapsed:     %lu ms", (unsigned long)elapsed);
    dualPrintf("  TX THROUGHPUT: %.1f kbps (DMA SPI)", tput);
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

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(120);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(120);
    }

    dualPrintln();
    dualPrintln("=== RP2040 FLRC DMA TX ===");
    dualPrintln("DMA SPI FIFO writes — zero CPU wait");

    // Initialize SPI bus + GPIO pins BEFORE radio init
    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    // Claim DMA channel for SPI TX FIFO writes
    dma_chan = dma_claim_unused_channel(true);
    dualPrintf("DMA channel claimed: %d", dma_chan);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        dualPrintln("Auto-start TX in 10 seconds...");
        delay(10000); // wait for RX board to be ready
        runTransmit();
    } else {
        dualPrintln("INIT FAILED — type INIT to retry");
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
