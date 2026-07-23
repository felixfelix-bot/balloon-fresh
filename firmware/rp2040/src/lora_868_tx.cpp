/*
 * lora_868_tx.cpp — 868 MHz LoRa Autonomous TX for outdoor range testing
 *
 * Based on lora_power_tx.cpp (proven LoRa TX at 2.4 GHz).
 * Modified for 868 MHz sub-GHz (European ISM band) on LR2021 LF path.
 *
 * THREE CRITICAL CHANGES from 2.4 GHz firmware:
 *   1. TX_FREQ_MHZ = 868.0f (was 2440.0f)
 *   2. SET_RX_PATH = 0x00 (LF=sub-GHz, was 0x01=HF=2.4 GHz)
 *   3. CALIB_FRONT_END feFreq: no 0x8000 bit (HF bit removed for LF)
 *
 * Behavior:
 * - On boot: 3s LED countdown, init radio, auto-start TX bursts
 * - 500-packet bursts, 2s pause, repeat forever
 * - DEADBEEF end marker at end of each burst
 * - LED on during TX, off during pause
 * - Heartbeat on Serial1 every 3s
 * - No serial commands needed — plug into power bank and walk
 *
 * LoRa config: SF7, BW 812 kHz, CR 4/5 (LORA_CR=1)
 *              127-byte packets, 12.5 dBm TX power
 *
 * Output: LORA_868_TX_RESULT,sent=N,fired=N,timeout=N,...,freq=868.0,...
 *
 * IMPORTANT: Antenna MUST be on Pin 9 (sub-GHz LF path), NOT Pin 10 (2.4 GHz)!
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13
 *       LED=GP25 LED_ALT=GP16
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

#define SPI_FREQ_HZ     20000000UL
#define XTAL_MHZ        52.0f

// ─── Compile-time config (868 MHz sub-GHz) ───────────────────────────
#define TX_FREQ_MHZ     868.0f
#define LORA_SF         7
#define LORA_BW_KHZ     812
#define LORA_CR         1   // internal: 1=4/5, 2=4/6, 3=4/7, 4=4/8
#define TX_PKT_SIZE     127
#define TX_POWER_DBM    12.5f
#define TX_PKT_COUNT    500
#define TX_PAUSE_MS     2000

// ─── LoRa BW encoding ────────────────────────────────────────────────
// BW values: 203.13kHz=0x0D, 406.25kHz=0x0E, 812.5kHz=0x0F
static uint8_t bwKhzToCode(int khz) {
    switch (khz) {
        case 203: return 0x0D;
        case 406: return 0x0E;
        case 812: return 0x0F;
        default:  return 0x0F;  // default to 812.5
    }
}

static int bwCodeToKhz(uint8_t code) {
    switch (code) {
        case 0x0D: return 203;
        case 0x0E: return 406;
        case 0x0F: return 812;
        default:   return 812;
    }
}

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

static uint8_t fifoCmd[2 + 255];
static uint8_t spiRxJunk[257];

static volatile bool radioReady = false;

// ─── Runtime config ───────────────────────────────────────────────────
static float    cfgFreq    = TX_FREQ_MHZ;
static uint8_t  cfgSf      = LORA_SF;
static uint8_t  cfgBwCode  = bwKhzToCode(LORA_BW_KHZ);
static uint8_t  cfgCr      = LORA_CR;   // 1=4/5, 2=4/6, 3=4/7, 4=4/8
static uint16_t cfgPktSize = TX_PKT_SIZE;
static float    cfgPower   = TX_POWER_DBM;

// ─── SPI helpers (ALL Arduino, no direct HW registers) ───────────────
static inline bool rfWaitBusy() {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 100000;
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
    return timeout > 0;
}

static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer((uint8_t*)buf, spiRxJunk, len);
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
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    uint8_t cmd[2] = { 0x01, 0x17 };
    spiRf.transfer(cmd, spiRxJunk, 2);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[6];
    uint8_t dummy[6] = {0, 0, 0, 0, 0, 0};
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(dummy, buf, 6);
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
    fifoCmd[0] = 0x00;
    fifoCmd[1] = 0x02;  // WRITE_TX_FIFO
    memcpy(fifoCmd + 2, data, len);

    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(fifoCmd, spiRxJunk, 2 + len);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfClearTxFifo() {
    uint8_t cmd[] = { 0x01, 0x1F };
    rfWriteCmd(cmd, 2);
}

// ─── LoRa-specific setters ───────────────────────────────────────────
static void rfSetFreq(float mhz) {
    uint32_t frf = (uint32_t)((mhz * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    uint8_t cmd[] = {
        0x02, 0x00,
        (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
    };
    rfWriteCmd(cmd, 5);
}

static void rfSetTxPower(float dbm) {
    uint8_t powerRaw = (uint8_t)(dbm * 2.0f + 0.5f);
    uint8_t cmd[] = { 0x02, 0x03, powerRaw, 0x04 };
    rfWriteCmd(cmd, 4);
}

// SET_LORA_MODULATION_PARAMS (0x0220): 2 bytes
// byte0 = ((sf & 0x0F) << 4) | (bw & 0x0F)
// byte1 = ((cr & 0x0F) << 4) | (ldro & 0x01)
static void rfSetLoraModParams(uint8_t sf, uint8_t bwCode, uint8_t cr) {
    uint8_t ldro = 0;
    float symTimeMs = (float)(1UL << sf) / (float)(bwCode == 0x0D ? 203125 :
                                bwCode == 0x0E ? 406250 : 812500) * 1000.0f;
    if (symTimeMs > 16.0f) ldro = 1;

    uint8_t byte0 = ((sf & 0x0F) << 4) | (bwCode & 0x0F);
    uint8_t byte1 = ((cr & 0x0F) << 4) | (ldro & 0x01);
    uint8_t cmd[] = { 0x02, 0x20, byte0, byte1 };
    rfWriteCmd(cmd, 4);
}

// SET_LORA_PACKET_PARAMS (0x0221): 4 bytes
// preambleHi, preambleLo, payloadLen, flags
static void rfSetLoraPacketParams(uint16_t preambleLen, uint8_t payloadLen,
                                   bool explicitHdr, bool crcOn) {
    uint8_t flags = ((explicitHdr ? 0 : 1) << 2) | ((crcOn ? 1 : 0) << 1) | 0;
    uint8_t cmd[] = {
        0x02, 0x21,
        (uint8_t)(preambleLen >> 8), (uint8_t)(preambleLen & 0xFF),
        payloadLen, flags
    };
    rfWriteCmd(cmd, 6);
}

// SET_LORA_SYNCWORD (0x0223): 1 byte
static void rfSetLoraSyncword(uint8_t sw) {
    uint8_t cmd[] = { 0x02, 0x23, sw };
    rfWriteCmd(cmd, 3);
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

// ─── Full LoRa radio init (868 MHz sub-GHz / LF path) ────────────────
static bool rawInitRadio() {
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    // CLEAR_ERRORS
    { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // SET_STANDBY(STDBY_XOSC = 0x01)
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; rfWriteCmd(cmd, 3); }
    delay(5);

    // SET_PACKET_TYPE = LoRa (0x00) — NOT 0x01!
    { uint8_t cmd[] = { 0x02, 0x07, 0x00 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // SET_RF_FREQUENCY
    rfSetFreq(cfgFreq);
    delay(1);

    // *** CHANGE 2: SET_RX_PATH — LF=0x00 for sub-GHz (was HF=0x01 for 2.4 GHz) ***
    { uint8_t cmd[] = { 0x02, 0x01, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // *** CHANGE 3: CALIB_FRONT_END — no 0x8000 HF bit for LF path ***
    uint16_t feFreq = (uint16_t)((cfgFreq / 4.0f) + 0.5f);
    {
        uint8_t cmd[] = {
            0x01, 0x23,
            (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        };
        rfWriteCmd(cmd, 10);
    }
    delay(5);

    // CALIBRATE(0x5F)
    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
    delay(5);

    // SET_LORA_MODULATION_PARAMS
    rfSetLoraModParams(cfgSf, cfgBwCode, cfgCr);
    delay(1);

    // SET_LORA_SYNCWORD (0x12 = private network)
    rfSetLoraSyncword(0x12);
    delay(1);

    // SET_LORA_PACKET_PARAMS: preamble=8, payloadLen=127, explicit header, CRC on
    rfSetLoraPacketParams(8, cfgPktSize, true, true);
    delay(1);

    // SET_PA_CONFIG
    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);

    // SET_TX_PARAMS (12.5 dBm → powerRaw=25)
    rfSetTxPower(cfgPower);
    delay(1);

    // SET_RX_TX_FALLBACK (FS = 0x03)
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // SET_DIO_FUNCTION (DIO9 = IRQ, DIO1 = BUSY)
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // SET_DIO_IRQ_CONFIG: TX_DONE
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
    delay(1);

    rfClearIrq();
    delay(1);

    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    if ((st >> 4) == 0x04 || (st >> 4) == 0x07 || (irq & 0x00020000)) {
        dualPrintln("RADIO_INIT_OK (LoRa TX 868 MHz LF)");
        return true;
    }
    dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

// ─── TX burst ────────────────────────────────────────────────────────
static uint32_t burstNum = 0;

static void runTransmit() {
    if (!radioReady) return;

    uint16_t pktSize = cfgPktSize;
    uint16_t count = TX_PKT_COUNT;

    digitalWrite(PIN_LED, HIGH);
    digitalWrite(PIN_LED_ALT, HIGH);

    int bwKhz = bwCodeToKhz(cfgBwCode);
    uint32_t burstStartMs = millis();
    dualPrintf("LORA_868_BURST %lu START uptime=%lums sf=%d bw=%d cr=4/%d count=%d power=%.1f freq=%.1f",
               (unsigned long)burstNum, (unsigned long)burstStartMs,
               cfgSf, bwKhz, (cfgCr + 4), count, cfgPower, cfgFreq);

    uint8_t pkt[256];
    for (int j = 4; j < pktSize; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t irqMask = 1UL << PIN_IRQ;
    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    for (int i = 0; i < count; i++) {
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        rfClearIrq();
        rfClearTxFifo();
        rfWriteTxFifo(pkt, pktSize);
        rfSetTx();

        // GPIO IRQ pin poll (NOT SPI status read)
        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 30000000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
        }

        if (irqFired) txDoneCount++;
        else txTimeoutCount++;

        // Progress every 50 packets (LoRa is fast at SF7/BW812)
        if (txDoneCount > 0 && (txDoneCount % 50) == 0) {
            uint32_t elapsed = millis() - startMs;
            dualPrintf("TX_PROGRESS sent=%d fired=%lu to=%lu elapsed_ms=%lu",
                       (i + 1), (unsigned long)txDoneCount,
                       (unsigned long)txTimeoutCount, (unsigned long)elapsed);
        }
    }

    // DEADBEEF end marker — RX reads total packet count from this
    pkt[0] = 0xDE; pkt[1] = 0xAD; pkt[2] = 0xBE; pkt[3] = 0xEF;
    pkt[4] = (uint8_t)(count >> 24);
    pkt[5] = (uint8_t)(count >> 16);
    pkt[6] = (uint8_t)(count >> 8);
    pkt[7] = (uint8_t)(count & 0xFF);
    rfClearIrq();
    rfClearTxFifo();
    rfWriteTxFifo(pkt, pktSize);
    rfSetTx();
    delay(5);

    uint32_t elapsed = millis() - startMs;
    float tput = (elapsed > 0) ? ((float)count * pktSize * 8.0f) / (float)elapsed : 0.0f;

    dualPrintf("LORA_868_BURST %lu DONE fired=%lu to=%lu elapsed_ms=%lu tput=%.1fkbps",
               (unsigned long)burstNum,
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
               (unsigned long)elapsed, tput);

    // Structured result line for automated parsing
    dualPrintf("LORA_868_TX_RESULT,burst=%lu,sent=%d,fired=%lu,timeout=%lu,elapsed_ms=%lu,throughput_kbps=%.1f,sf=%d,bw=%d,cr=4/%d,pktSize=%d,power=%.1f,freq=%.1f,uptime_ms=%lu",
               (unsigned long)burstNum, count,
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
               (unsigned long)elapsed, tput,
               cfgSf, bwKhz, (cfgCr + 4), pktSize, cfgPower, cfgFreq,
               (unsigned long)burstStartMs);

    burstNum++;

    digitalWrite(PIN_LED, LOW);
    digitalWrite(PIN_LED_ALT, LOW);
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);
    delay(100);

    // Print BEFORE radio init — if radio hangs, USB CDC stays alive for recovery
    int bwKhz = bwCodeToKhz(cfgBwCode);
    dualPrintln();
    dualPrintln("=============================================");
    dualPrintln("=== RP2040 LORA 868 MHz TX (AUTONOMOUS) ===");
    dualPrintln("=============================================");
    dualPrintf("Config: freq=%.1f MHz sf=%d bw=%d cr=4/%d pktSize=%d power=%.1f count=%d",
               cfgFreq, cfgSf, bwKhz, (cfgCr + 4), cfgPktSize, cfgPower, TX_PKT_COUNT);
    dualPrintln("");
    dualPrintln("*** ANTENNA: Ensure SMA/U.FL on Pin 9 (sub-GHz LF path) ***");
    dualPrintln("***          NOT Pin 10 (2.4 GHz HF path)!            ***");
    dualPrintln("");

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);

    // 3s countdown blink — time to walk away
    dualPrintln("AUTO TX STARTING in 3s — unplug and walk");
    for (int i = 0; i < 6; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH);
        delay(250);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);
        delay(250);
    }

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        dualPrintln("TX BURSTS STARTING — unplug and walk");
    } else {
        dualPrintln("INIT FAILED — retrying...");
        delay(2000);
        radioReady = rawInitRadio();
        if (radioReady) {
            digitalWrite(PIN_LED_ALT, HIGH);
            dualPrintln("TX BURSTS STARTING (2nd init) — unplug and walk");
        } else {
            dualPrintln("INIT FAILED TWICE — stuck");
        }
    }
}

static unsigned long lastHB = 0;

void loop() {
    if (radioReady) {
        runTransmit();
        delay(TX_PAUSE_MS);
        // Heartbeat to keep USB CDC alive
        if (millis() - lastHB > 3000) {
            lastHB = millis();
            dualPrintf("[TX HB %lus] burst=%lu", millis() / 1000, (unsigned long)burstNum);
        }
    } else {
        // Blink SOS if radio dead + heartbeat so USB CDC stays alive
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(500);
        dualPrintf("[TX DEAD %lus]", millis() / 1000);
    }
}
