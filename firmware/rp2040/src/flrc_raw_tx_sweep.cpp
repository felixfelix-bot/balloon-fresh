/*
 * flrc_raw_tx_sweep.cpp — RP2040 FLRC TX with runtime SPI frequency sweep
 *
 * Based on v4 (flrc_raw_tx.cpp). Removes the compile-time #define SPI_FREQ_HZ
 * and instead accepts the SPI frequency via serial command "SETSPI <freq_hz>".
 * After setting, "RUN" executes a 1000-packet TX burst at the current frequency.
 *
 * The earlephilhower SPIClassRP2040::beginTransaction() calls spi_deinit() +
 * spi_init() with the new baudrate whenever the requested frequency differs
 * from the current one.  This means beginTransaction(SPISettings(newFreq,...))
 * DOES change the actual SPI clock at runtime.
 *
 * ── Achievable SPI Frequencies (RP2040 PL022 SSP) ──────────────────────────
 *
 * The RP2040 SPI peripheral (ARM PL022) derives SCK from clk_peri (=125 MHz
 * by default) via a two-stage divider:
 *
 *   SCK = clk_peri / (prescale * postdiv)
 *
 *   prescale : even integer, 2..254  (CPSR register)
 *   postdiv  : integer, 1..256      (SCR field in CR0, stored as postdiv-1)
 *
 * The Pico SDK spi_set_baudrate() algorithm:
 *   1. Find smallest even prescale where  freq_in < prescale * 256 * baudrate
 *   2. Find largest postdiv where  freq_in / (prescale * (postdiv-1)) > baudrate
 *   3. Actual = freq_in / (prescale * postdiv)
 *
 * For clk_peri = 125,000,000 Hz, the achievable frequencies form a discrete
 * set.  Below is a table of common requested frequencies and their actual
 * SCK for prescale/postdiv combinations near the range of interest:
 *
 *   prescale  postdiv    actual_SCK
 *   ────────  ────────    ──────────────────
 *       2        1       62,500,000  (62.5 MHz)
 *       2        2       31,250,000  (31.25 MHz)
 *       2        4       15,625,000  (15.625 MHz)
 *       2        5       12,500,000  (12.5 MHz)
 *       2        6       10,416,666  (~10.42 MHz)
 *       2        8        7,812,500  (~7.81 MHz)
 *       2       10        6,250,000  (6.25 MHz)
 *       4        1       31,250,000  (31.25 MHz)
 *       4        2       15,625,000  (15.625 MHz)
 *       4        3       10,416,666  (~10.42 MHz)
 *       4        4        7,812,500  (~7.81 MHz)
 *       4        5        6,250,000  (6.25 MHz)
 *       6        1       20,833,333  (~20.83 MHz)
 *       6        2       10,416,666  (~10.42 MHz)
 *       6        3        6,944,444  (~6.94 MHz)
 *       8        1       15,625,000  (15.625 MHz)
 *       8        2        7,812,500  (~7.81 MHz)
 *       10       1       12,500,000  (12.5 MHz)
 *       10       2        6,250,000  (6.25 MHz)
 *       12       1       10,416,666  (~10.42 MHz)
 *       16       1        7,812,500  (~7.81 MHz)
 *       20       1        6,250,000  (6.25 MHz)
 *
 * Key observations:
 *   - Requesting 20 MHz → prescale=6, postdiv=1 → actual=20.833 MHz
 *   - Requesting 15.625 MHz → prescale=8, postdiv=1 → actual=15.625 MHz
 *   - Requesting 10 MHz → prescale=12, postdiv=1 → actual=10.417 MHz
 *   - The actual frequency returned by spi_get_baudrate() is what matters.
 *   - Minimum achievable SCK: 125MHz / (254*256) ≈ 1,924 Hz
 *   - Maximum achievable SCK: 125MHz / (2*1) = 62.5 MHz
 *
 * The LR2021 datasheet specifies 20 MHz max SPI clock, so practical sweep
 * range is ~2 MHz to ~20 MHz.
 *
 * ── Runtime SPI clock change confirmation ──────────────────────────────────
 * SPIClassRP2040::beginTransaction(SPISettings) in SPI.cpp line 154:
 *   - If new settings.getClockFreq() != _spis.getClockFreq():
 *       spi_deinit(_spi)  → disables SPI peripheral
 *       spi_init(_spi, newFreq)  → calls spi_set_baudrate() which reprograms
 *                                  CPSR and SCR registers
 *   - So YES: beginTransaction with a new SPISettings frequency DOES change
 *     the actual SCK clock at runtime.  The old peripheral is de-initialized
 *     and re-initialized at the new frequency.
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13
 */

#include <Arduino.h>
#include <SPI.h>
#include <hardware/spi.h>

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
#define XTAL_MHZ        52.0f

#define TX_PKT_COUNT    1000
#define TX_POWER_DBM    12

// Sync word — MUST match RX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── Runtime SPI frequency (replaces compile-time #define SPI_FREQ_HZ) ──
uint32_t g_spiFreqHz = 15625000UL;  // default = 125MHz / 8 = 15.625 MHz

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);

// ─── Direct HW SPI helpers (hot loop) ────────────────────────────────
// These use spi0_hw->dr directly, bypassing Arduino SPI overhead.
// Requires spiRf.beginTransaction(SPISettings(g_spiFreqHz, ...)) called
// before the hot loop (never endTransaction), so the peripheral stays
// configured at the current g_spiFreqHz.

// Wait for TX FIFO to have space, write one byte to the data register
static inline void spiWriteByte(uint8_t b) {
    while (!(spi0_hw->sr & SPI_SSPSR_TNF_BITS)) tight_loop_contents();
    spi0_hw->dr = (uint32_t)b;
}

// Write a burst of bytes, then drain RX FIFO and wait for idle
static inline void spiWriteBurst(const uint8_t *buf, size_t len) {
    const size_t fifo_depth = 8;
    size_t rx_remaining = len, tx_remaining = len;
    while (rx_remaining || tx_remaining) {
        if (tx_remaining && (spi0_hw->sr & SPI_SSPSR_TNF_BITS) &&
            rx_remaining < tx_remaining + fifo_depth) {
            spi0_hw->dr = (uint32_t)*buf++;
            --tx_remaining;
        }
        if (rx_remaining && (spi0_hw->sr & SPI_SSPSR_RNE_BITS)) {
            (void)spi0_hw->dr;
            --rx_remaining;
        }
    }
    // Wait for BSY to clear
    while (spi0_hw->sr & SPI_SSPSR_BSY_BITS) tight_loop_contents();
    // Drain any leftover RX
    while (spi0_hw->sr & SPI_SSPSR_RNE_BITS) (void)spi0_hw->dr;
}

// Drain the RX FIFO (discard received data)
static inline void spiDrain() {
    while (spi0_hw->sr & SPI_SSPSR_RNE_BITS) (void)spi0_hw->dr;
}

// ─── SPI helpers (Arduino SPI for cold-path init) ────────────────────
static inline bool rfWaitBusy() {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 100000;
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
    return timeout > 0;
}

static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(SPISettings(g_spiFreqHz, MSBFIRST, SPI_MODE0));
    digitalWrite(PIN_CS, LOW);
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static uint8_t rfReadStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(SPISettings(g_spiFreqHz, MSBFIRST, SPI_MODE0));
    digitalWrite(PIN_CS, LOW);
    uint8_t st = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    return st;
}

static uint32_t rfReadIrqStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(SPISettings(g_spiFreqHz, MSBFIRST, SPI_MODE0));
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x01); spiRf.transfer(0x17);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[6];
    spiRf.beginTransaction(SPISettings(g_spiFreqHz, MSBFIRST, SPI_MODE0));
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
    spiRf.beginTransaction(SPISettings(g_spiFreqHz, MSBFIRST, SPI_MODE0));
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

// ─── Hot-loop SPI operations (direct HW SPI, no begin/endTransaction) ──
// These assume spiRf.beginTransaction was called once in the burst and the
// peripheral stays configured. Each does: CS LOW → write → CS HIGH.

// CLR_IRQ: 6 bytes, includes rfWaitBusy (chip transitioning TX→STDBY)
static inline void hotClearIrq() {
    rfWaitBusy();
    digitalWrite(PIN_CS, LOW);
    static const uint8_t cmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    spiWriteBurst(cmd, 6);
    digitalWrite(PIN_CS, HIGH);
}

// WRITE_FIFO: 2 header bytes + payload, NO rfWaitBusy (chip idle after CLR_IRQ)
static inline void hotWriteFifo(const uint8_t *data, size_t len) {
    digitalWrite(PIN_CS, LOW);
    spiWriteByte(0x00);  // FIFO write command
    spiWriteByte(0x02);  // offset 0
    spiWriteBurst(data, len);
    digitalWrite(PIN_CS, HIGH);
}

// SET_TX: 5 bytes, NO rfWaitBusy (chip idle after FIFO write)
static inline void hotSetTx() {
    digitalWrite(PIN_CS, LOW);
    static const uint8_t cmd[5] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
    spiWriteBurst(cmd, 5);
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

// ─── TX burst — sequential loop using Arduino SPI + IRQ pin poll ─────
static volatile bool radioReady = false;

static void runTransmit() {
    if (!radioReady) { dualPrintln("ERR: radio not initialized"); return; }

    uint32_t actualFreq = spi_get_baudrate(spi0);
    dualPrintf("TX_START count=%d pktSize=%d spiReq=%lu spiActual=%lu",
               TX_PKT_COUNT, FLRC_PKT_SIZE,
               (unsigned long)g_spiFreqHz, (unsigned long)actualFreq);
    delay(10);

    uint8_t pkt[FLRC_PKT_SIZE];
    for (int j = 4; j < FLRC_PKT_SIZE; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t irqMask = 1UL << PIN_IRQ;
    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    // Lock SPI peripheral at current g_spiFreqHz for direct HW access in hot loop
    spiRf.beginTransaction(SPISettings(g_spiFreqHz, MSBFIRST, SPI_MODE0));

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

        // Print spin count for first 5 packets only (no Arduino SPI needed)
        if (i < 5) {
            dualPrintf("PKT %d: irqPin=%d spin=%lu",
                       i, irqFired ? 1 : 0, (unsigned long)spinCount);
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
    dualPrintf("  SPI freq:    req=%lu actual=%lu Hz",
               (unsigned long)g_spiFreqHz, (unsigned long)actualFreq);
    dualPrintf("  Elapsed:     %lu ms", (unsigned long)elapsed);
    dualPrintf("  TX THROUGHPUT: %.1f kbps", tput);
    dualPrintln("=============================================");
    dualPrintf("RESULT_TX,sent=%d,elapsed_ms=%lu,throughput_kbps=%.1f,spi_req=%lu,spi_actual=%lu",
               TX_PKT_COUNT, (unsigned long)elapsed, tput,
               (unsigned long)g_spiFreqHz, (unsigned long)actualFreq);
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
    Serial1.println("=== RP2040 FLRC RAW TX SWEEP ===");
    Serial1.println("Runtime SPI freq control + IRQ poll");

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    Serial1.println("SPI init done");

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        // Print readiness with default frequency
        uint32_t actualFreq = spi_get_baudrate(spi0);
        Serial.print("SWEEP_READY freq=");
        Serial.println((unsigned long)g_spiFreqHz);
        Serial1.print("SWEEP_READY freq=");
        Serial1.println((unsigned long)g_spiFreqHz);
        Serial.print("  actual=");
        Serial.println((unsigned long)actualFreq);
        Serial1.print("  actual=");
        Serial1.println((unsigned long)actualFreq);
        Serial1.println("Commands: SETSPI <freq_hz>  RUN  INIT");
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

                    // Parse "SETSPI <freq_hz>"
                    if (strncmp(cmdBuf, "SETSPI ", 7) == 0) {
                        uint32_t newFreq = strtoul(cmdBuf + 7, nullptr, 10);
                        if (newFreq >= 1000000UL && newFreq <= 62500000UL) {
                            g_spiFreqHz = newFreq;
                            // Re-init SPI at new frequency via beginTransaction
                            spiRf.beginTransaction(SPISettings(g_spiFreqHz, MSBFIRST, SPI_MODE0));
                            spiRf.endTransaction();
                            uint32_t actualFreq = spi_get_baudrate(spi0);
                            Serial.print("SPI_SET ");
                            Serial.println((unsigned long)g_spiFreqHz);
                            Serial1.print("SPI_SET ");
                            Serial1.println((unsigned long)g_spiFreqHz);
                            Serial.print("  actual=");
                            Serial.println((unsigned long)actualFreq);
                            Serial1.print("  actual=");
                            Serial1.println((unsigned long)actualFreq);
                        } else {
                            Serial.print("ERR: freq out of range (1MHz-62.5MHz): ");
                            Serial.println((unsigned long)newFreq);
                            Serial1.print("ERR: freq out of range (1MHz-62.5MHz): ");
                            Serial1.println((unsigned long)newFreq);
                        }
                    }
                    else if (strcmp(cmdBuf, "RUN") == 0) {
                        runTransmit();
                    }
                    else if (strcmp(cmdBuf, "INIT") == 0) {
                        radioReady = rawInitRadio();
                    }
                    else if (strcmp(cmdBuf, "FREQ?") == 0) {
                        uint32_t actualFreq = spi_get_baudrate(spi0);
                        Serial.print("FREQ req=");
                        Serial.print((unsigned long)g_spiFreqHz);
                        Serial.print(" actual=");
                        Serial.println((unsigned long)actualFreq);
                        Serial1.print("FREQ req=");
                        Serial1.print((unsigned long)g_spiFreqHz);
                        Serial1.print(" actual=");
                        Serial1.println((unsigned long)actualFreq);
                    }

                    cmdLen = 0;
                }
            } else if (cmdLen < sizeof(cmdBuf) - 1) {
                cmdBuf[cmdLen++] = c;
            }
        }
    }
}