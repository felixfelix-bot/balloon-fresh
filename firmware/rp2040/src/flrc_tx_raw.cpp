/*
 * flrc_tx_raw.cpp — RP2040 FLRC TX with RAW SPI (no RadioLib)
 *
 * Uses identical init sequence to flrc_rx_raw.cpp to guarantee parameter match.
 * Transmits 2000 packets of 255 bytes, then sends DEADBEEF end marker.
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13
 */

#include <Arduino.h>
#include <SPI.h>

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

#define FLRC_FREQ_HZ   2440.0f
#define FLRC_BR        2600
#define FLRC_PWR_DBM   13
#define FLRC_PREAMBLE  16
#define FLRC_PKT_SIZE  255
#define SPI_FREQ_HZ    16000000UL
#define TX_PKT_COUNT   2000

static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

static inline void rfCsLow()  { digitalWrite(PIN_CS, LOW); }
static inline void rfCsHigh() { digitalWrite(PIN_CS, HIGH); }
static inline void rfWaitBusy() {
    uint32_t to = millis() + 50;
    while (digitalRead(PIN_BUSY) == HIGH) { if (millis() > to) return; }
}

static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
    rfCsHigh();
    spiRf.endTransaction();
}

static uint8_t rfReadStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    uint8_t st = spiRf.transfer(0x00);
    rfCsHigh();
    spiRf.endTransaction();
    return st;
}

// ─── TX helpers ──────────────────────────────────────────────────────
static void rfSetStandby() {
    uint8_t cmd[] = { 0x01, 0x28, 0x01 };
    rfWriteCmd(cmd, 3);
}

static void rfWriteTxFifo(const uint8_t *data, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    rfCsLow();
    spiRf.transfer(0x00); // opcode MSB
    spiRf.transfer(0x02); // opcode LSB = WRITE_TX_FIFO
    for (size_t i = 0; i < len; i++) spiRf.transfer(data[i]);
    rfCsHigh();
    spiRf.endTransaction();
}

static void rfSetTx() {
    // SET_TX with timeout = 0xFFFFFF (no timeout)
    uint8_t cmd[] = { 0x02, 0x0D, 0x00, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 6);
}

static void rfClearIrq() {
    uint8_t cmd[] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 6);
}

// ─── Raw SPI Init (identical to RX, but no SET_RX at end) ────────────
static bool rawInitRadio() {
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(10);

    { uint8_t c[] = { 0x01, 0x28, 0x01 }; rfWriteCmd(c, 3); } delay(2);
    { uint8_t c[] = { 0x01, 0x22, 0x6F }; rfWriteCmd(c, 3); } delay(5);
    { uint8_t c[] = { 0x02, 0x07, 0x05 }; rfWriteCmd(c, 3); } delay(1);

    uint32_t rfFreq = (uint32_t)(FLRC_FREQ_HZ * 1000000.0f / 0.00390625f);
    {
        uint8_t c[] = { 0x02, 0x00,
            (uint8_t)(rfFreq >> 24), (uint8_t)(rfFreq >> 16),
            (uint8_t)(rfFreq >> 8),  (uint8_t)(rfFreq & 0xFF) };
        rfWriteCmd(c, 6);
    }
    delay(1);

    // FLRC mod params: brBw=0x00 (2600), cr|shaping=0x05 (CR_1_0, BT0.5)
    { uint8_t c[] = { 0x02, 0x48, 0x00, 0x05 }; rfWriteCmd(c, 4); } delay(1);

    // FLRC packet params: preamble=16, syncWordLen=4, syncMatch=1, fixed=1, crc=0
    {
        uint8_t c[] = { 0x02, 0x49,
            (uint8_t)(((FLRC_PREAMBLE & 0x0F) << 2) | (4 / 2)),
            (uint8_t)(((1 & 0x07) << 3) | (1 << 2) | 0),
            (uint8_t)(FLRC_PKT_SIZE >> 8),
            (uint8_t)(FLRC_PKT_SIZE & 0xFF) };
        rfWriteCmd(c, 6);
    }
    delay(1);

    // FLRC sync word: {0x12, 0xAD, 0x10, 0x1B} at slot 1
    { uint8_t c[] = { 0x02, 0x4C, 0x01, 0x12, 0xAD, 0x10, 0x1B }; rfWriteCmd(c, 7); } delay(1);

    // PA config
    { uint8_t c[] = { 0x02, 0x02, 0x01, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(c, 7); } delay(1);
    // TX params
    { uint8_t c[] = { 0x02, 0x03, FLRC_PWR_DBM, 0x02 }; rfWriteCmd(c, 4); } delay(1);
    // DIO function
    { uint8_t c[] = { 0x01, 0x12, 0x10 }; rfWriteCmd(c, 3); } delay(1);
    // IRQ config: TX_DONE bit 19
    {
        uint32_t irqMask = (1UL << 19);
        uint32_t dio2Mask = (1UL << 19);
        uint8_t c[] = { 0x01, 0x15,
            (uint8_t)(irqMask >> 24), (uint8_t)(irqMask >> 16),
            (uint8_t)(irqMask >> 8),  (uint8_t)(irqMask & 0xFF),
            0x00, 0x00, 0x00, 0x00,
            (uint8_t)(dio2Mask >> 24), (uint8_t)(dio2Mask >> 16),
            (uint8_t)(dio2Mask >> 8),  (uint8_t)(dio2Mask & 0xFF) };
        rfWriteCmd(c, 14);
    }
    delay(1);
    rfClearIrq();
    delay(1);

    uint8_t st = rfReadStatus();
    char b[64];
    snprintf(b, sizeof(b), "TX init done. Status=0x%02X", st);
    Serial.println(b);
    Serial1.println(b);
    return (st != 0x00 && st != 0xFF);
}

static void dualPrintln(const char *s) { Serial.println(s); Serial1.println(s); }

// ─── TX burst ────────────────────────────────────────────────────────
static void runTX() {
    uint8_t pkt[FLRC_PKT_SIZE];
    // Fill with pattern: seq (4 bytes) + counter payload
    memset(pkt, 0xAA, FLRC_PKT_SIZE);

    dualPrintln("TX_START transmitting...");

    uint32_t startMs = millis();
    for (uint32_t i = 0; i < TX_PKT_COUNT; i++) {
        // Sequence number (big-endian)
        pkt[0] = (i >> 24) & 0xFF;
        pkt[1] = (i >> 16) & 0xFF;
        pkt[2] = (i >> 8) & 0xFF;
        pkt[3] = i & 0xFF;

        // 1. Set standby
        rfSetStandby();
        // 2. Write TX FIFO
        rfWriteTxFifo(pkt, FLRC_PKT_SIZE);
        // 3. Set TX (triggers transmission)
        rfSetTx();
        // 4. Wait for TX_DONE (poll BUSY)
        rfWaitBusy();

        rfClearIrq();

        if (i < 5 || (i % 200) == 0) {
            char b[64];
            snprintf(b, sizeof(b), "TX pkt=%lu/%lu", (unsigned long)(i+1), (unsigned long)TX_PKT_COUNT);
            dualPrintln(b);
        }
    }

    // Send end marker: DEADBEEF + total count
    pkt[0] = 0xDE; pkt[1] = 0xAD; pkt[2] = 0xBE; pkt[3] = 0xEF;
    pkt[4] = (TX_PKT_COUNT >> 24) & 0xFF;
    pkt[5] = (TX_PKT_COUNT >> 16) & 0xFF;
    pkt[6] = (TX_PKT_COUNT >> 8) & 0xFF;
    pkt[7] = TX_PKT_COUNT & 0xFF;
    rfSetStandby();
    rfWriteTxFifo(pkt, FLRC_PKT_SIZE);
    rfSetTx();
    rfWaitBusy();

    uint32_t elapsed = millis() - startMs;
    float kbps = ((float)TX_PKT_COUNT * (float)FLRC_PKT_SIZE * 8.0f) / (float)elapsed;

    char b[128];
    snprintf(b, sizeof(b), "TX_DONE pkts=%lu elapsed=%lums tput=%.1fkbps",
             (unsigned long)TX_PKT_COUNT, (unsigned long)elapsed, kbps);
    dualPrintln(b);
}

// ─── Setup ───────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_CS, OUTPUT); digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);
    pinMode(PIN_RST, OUTPUT); digitalWrite(PIN_RST, HIGH);

    spiRf.begin();

    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); delay(120);
        digitalWrite(PIN_LED, LOW); delay(120);
    }

    delay(500);

    dualPrintln("=== RP2040 FLRC TX (RAW SPI) ===");

    if (rawInitRadio()) {
        dualPrintln("RADIO_INIT_OK — transmitting in 2s");
        digitalWrite(PIN_LED, HIGH);
        delay(2000);
        runTX();
    } else {
        dualPrintln("RADIO_INIT_FAILED");
    }
}

void loop() {
    // Blink heartbeat
    digitalWrite(PIN_LED, !digitalRead(PIN_LED));
    delay(1000);
}
