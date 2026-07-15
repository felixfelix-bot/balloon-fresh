/*
 * flrc_tx_raw.cpp — RP2040 FLRC TX with RAW SPI init (no RadioLib)
 *
 * IDENTICAL radio config as flrc_rx_raw.cpp — same sync word, same params.
 * This ensures TX and RX can communicate.
 *
 * Auto-transmits 3s after boot. 2000 packets × 255 bytes + DEADBEEF end marker.
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

// ─── FLRC Config (MUST match flrc_rx_raw.cpp) ────────────────────────
#define FLRC_FREQ_HZ   2440.0f
#define FLRC_BR        2600
#define FLRC_PWR_DBM   13
#define FLRC_PREAMBLE  12
#define FLRC_PKT_SIZE  255
#define SPI_FREQ_HZ    16000000UL

#define PKT_COUNT      2000

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// ─── Raw SPI helpers (IDENTICAL to flrc_rx_raw.cpp) ──────────────────
static inline void rfCsLow()  { digitalWrite(PIN_CS, LOW); }
static inline void rfCsHigh() { digitalWrite(PIN_CS, HIGH); }
static inline void rfWaitBusy() {
    uint32_t timeout = millis() + 50;
    while (digitalRead(PIN_BUSY) == HIGH) {
        if (millis() > timeout) return;
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

static uint32_t rfReadIrqStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    spiRf.transfer(0x01); spiRf.transfer(0x17);
    rfCsHigh();
    spiRf.endTransaction();
    rfWaitBusy();
    uint8_t buf[6];
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    for (int i = 0; i < 6; i++) buf[i] = spiRf.transfer(0x00);
    rfCsHigh();
    spiRf.endTransaction();
    return ((uint32_t)buf[2] << 24) | ((uint32_t)buf[3] << 16) |
           ((uint32_t)buf[4] << 8) | (uint32_t)buf[5];
}

static void rfClearIrq() {
    uint8_t cmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 6);
}

// ─── TX-specific SPI commands ────────────────────────────────────────
static void rfClearTxFifo() {
    uint8_t cmd[2] = { 0x01, 0x1F };
    rfWriteCmd(cmd, 2);
}

static void rfWriteTxFifo(const uint8_t *data, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    spiRf.transfer(0x00); // opcode MSB
    spiRf.transfer(0x02); // opcode LSB (WRITE_TX_FIFO)
    for (size_t i = 0; i < len; i++) spiRf.transfer(data[i]);
    rfCsHigh();
    spiRf.endTransaction();
}

static void rfSetTx() {
    // SET_TX = 0x020D, timeout=0 (no timeout)
    uint8_t cmd[6] = { 0x02, 0x0D, 0x00, 0x00, 0x00, 0x00 };
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

// ─── Raw SPI Init (IDENTICAL to flrc_rx_raw.cpp) ─────────────────────
static bool rawInitRadio() {
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50); // wait for crystal stabilization

    // Step 0b: Set Rx/Tx fallback mode to STBY_RC (matches RadioLib config())
    { uint8_t cmd[] = { 0x02, 0x06, 0x01 }; rfWriteCmd(cmd, 3); } delay(1);

    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; rfWriteCmd(cmd, 3); } delay(5);  // Standby XOSC
    { uint8_t cmd[] = { 0x01, 0x22, 0x6F }; rfWriteCmd(cmd, 3); } delay(5);  // Calibrate all
    { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; rfWriteCmd(cmd, 3); } delay(1);  // Packet type FLRC

    // RF Frequency 2440 MHz — send freq_Hz directly (radio does internal conversion)
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

    // FLRC mod params: brBw=0x00 (2600), cr|shaping=0x25
    { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x25 }; rfWriteCmd(cmd, 4); } delay(1);

    // FLRC packet params: preamble=12, syncLen=4, syncTx=1, syncMatch=1, fixed=1, crc=0
    {
        uint8_t cmd[] = {
            0x02, 0x49,
            (uint8_t)(((FLRC_PREAMBLE & 0x0F) << 2) | (4 / 2)),
            (uint8_t)(((1 & 0x03) << 6) | ((1 & 0x07) << 3) | (1 << 2) | 0),
            (uint8_t)(FLRC_PKT_SIZE >> 8),
            (uint8_t)(FLRC_PKT_SIZE & 0xFF)
        };
        rfWriteCmd(cmd, 6);
    }
    delay(1);

    // Sync word — MUST match RX: {0x12, 0xAD, 0x10, 0x1B}
    {
        uint8_t cmd[] = {
            0x02, 0x4C,
            0x01,           // syncWordNum = 1
            0x12, 0xAD, 0x10, 0x1B
        };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

    // PA Config
    { uint8_t cmd[] = { 0x02, 0x02, 0x01, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); } delay(1);

    // TX Params
    { uint8_t cmd[] = { 0x02, 0x03, FLRC_PWR_DBM, 0x02 }; rfWriteCmd(cmd, 4); } delay(1);

    // DIO9 = IRQ
    { uint8_t cmd[] = { 0x01, 0x12, 0x10 }; rfWriteCmd(cmd, 3); } delay(1);

    // IRQ config — TX_DONE (bit 19) on DIO9
    {
        uint32_t irqMask = (1UL << 19);  // TX_DONE
        uint32_t dio2Mask = (1UL << 19);
        uint8_t cmd[] = {
            0x01, 0x15,
            (uint8_t)(irqMask >> 24), (uint8_t)(irqMask >> 16),
            (uint8_t)(irqMask >> 8),  (uint8_t)(irqMask & 0xFF),
            0x00, 0x00, 0x00, 0x00,
            (uint8_t)(dio2Mask >> 24), (uint8_t)(dio2Mask >> 16),
            (uint8_t)(dio2Mask >> 8),  (uint8_t)(dio2Mask & 0xFF)
        };
        rfWriteCmd(cmd, 14);
    }
    delay(1);

    rfClearIrq();
    return true;
}

// ─── TX burst ────────────────────────────────────────────────────────
static bool radioReady = false;

void runTX() {
    dualPrintf("TX: %d packets x %d bytes", PKT_COUNT, FLRC_PKT_SIZE);
    dualPrintln("Starting in 3 seconds...");
    delay(3000);

    uint8_t buf[FLRC_PKT_SIZE];
    uint32_t sentOk = 0, sentErr = 0;
    uint32_t startMs = millis();

    for (uint32_t i = 0; i < PKT_COUNT; i++) {
        // Sequence number (big endian)
        buf[0] = (i >> 24) & 0xFF;
        buf[1] = (i >> 16) & 0xFF;
        buf[2] = (i >> 8) & 0xFF;
        buf[3] = i & 0xFF;
        memset(buf + 4, 0xAA, FLRC_PKT_SIZE - 4);

        // Clear TX FIFO
        rfClearTxFifo();

        // Write packet to TX FIFO
        rfWriteTxFifo(buf, FLRC_PKT_SIZE);

        // Clear IRQ before TX
        rfClearIrq();

        // Start TX
        rfSetTx();

        // Wait for TX_DONE IRQ (bit 19) or timeout
        uint32_t txStart = millis();
        bool txDone = false;
        while (millis() - txStart < 10) {
            if (digitalRead(PIN_IRQ) == HIGH) {
                uint32_t irq = rfReadIrqStatus();
                if (irq & (1UL << 19)) {  // TX_DONE
                    txDone = true;
                    break;
                }
                if (irq & (1UL << 21)) {  // TIMEOUT
                    break;
                }
            }
        }

        if (txDone) sentOk++;
        else sentErr++;

        if ((i + 1) % 500 == 0) {
            uint32_t elapsed = millis() - startMs;
            float kbps = (float)(i + 1) * FLRC_PKT_SIZE * 8.0f / (float)elapsed;
            dualPrintf("TX %d/%d (%.1f kbps)", (int)(i + 1), PKT_COUNT, kbps);
        }
    }

    // Send end marker
    delay(10);
    rfClearTxFifo();
    uint8_t endMarker[] = {0xDE, 0xAD, 0xBE, 0xEF};
    rfWriteTxFifo(endMarker, 4);
    rfClearIrq();
    rfSetTx();
    delay(5);

    uint32_t elapsedMs = millis() - startMs;
    float elapsedSec = elapsedMs / 1000.0f;
    float throughput = (sentOk * FLRC_PKT_SIZE * 8.0f) / (elapsedSec * 1000.0f);

    dualPrintln("=============================================");
    dualPrintln("  TX RESULTS (RAW SPI)");
    dualPrintln("=============================================");
    dualPrintf("  Sent OK:    %d / %d", sentOk, PKT_COUNT);
    dualPrintf("  Errors:     %d", sentErr);
    dualPrintf("  Elapsed:    %.2f sec", elapsedSec);
    dualPrintf("  Throughput: %.1f kbps", throughput);
    dualPrintf("  Per-pkt:    %.3f ms", elapsedMs / (float)sentOk);
    dualPrintf("  Pkt rate:   %.1f pkt/s", sentOk / elapsedSec);
    dualPrintln("=============================================");
    dualPrintln("TX COMPLETE - DEADBEEF end marker sent");
}

void setup() {
    Serial.begin(115200);
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, HIGH);

    spiRf.begin();

    // Boot blink
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(120);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(120);
    }
    delay(500);

    dualPrintln("");
    dualPrintln("=== RP2040 FLRC TX (RAW SPI) ===");
    dualPrintln("No RadioLib — matching RX raw SPI config");

    radioReady = rawInitRadio();
    if (radioReady) {
        dualPrintln("RADIO_INIT_OK");
    } else {
        dualPrintln("RADIO_INIT_FAILED");
    }

    if (radioReady) {
        runTX();
    }
}

void loop() {
    // Heartbeat
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
    delay(1000);
}
