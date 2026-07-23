/*
 * lora_range_tx.cpp — LoRa TX with raw SPI LoRa init for range testing
 *
 * Uses raw 2-byte opcode SPI (ADR-020). No RadioLib.
 * LoRa init sequence verified against RadioLib v7.6.0 source.
 *
 * Behavior:
 * - On boot: init radio in LoRa mode, wait for RUN command (or auto-start)
 * - TX loop: clearIrq → clearTxFifo → writeTxFifo → setTx → wait IRQ → loop
 * - LED on during TX
 * - Serial commands for runtime configuration
 *
 * Serial commands:
 *   SF <n>          — set spreading factor (5-12)
 *   BW <kHz>        — set bandwidth (203/406/812)
 *   CR <n>          — set coding rate (5=4/5, 6=4/6, 7=4/7, 8=4/8)
 *   COUNT <n>       — set packet count per run
 *   DURATION <sec>  — set max run duration (0 = unlimited by count)
 *   RUN             — start TX run
 *   STATUS          — print current config
 *
 * Structured output: LORA_TX_RESULT,sent=N,elapsed_ms=M,throughput_kbps=X,sf=Y,bw=Z
 *
 * Compile-time defaults: FREQ=2440, SF=7, BW=812, CR=4/5, PKT_SIZE=127, POWER=12
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

// ─── Compile-time config (overridable via -D flags) ──────────────────
#ifndef TX_FREQ_MHZ
#define TX_FREQ_MHZ     2440.0f
#endif
#ifndef LORA_SF
#define LORA_SF         7
#endif
#ifndef LORA_BW_KHZ
#define LORA_BW_KHZ     812
#endif
#ifndef LORA_CR
#define LORA_CR         1   // internal: 1=4/5, 2=4/6, 3=4/7, 4=4/8
#endif
#ifndef LORA_PKT_SIZE
#define LORA_PKT_SIZE   127
#endif
#ifndef LORA_POWER_DBM
#define LORA_POWER_DBM  12.0f
#endif
#ifndef LORA_PKT_COUNT
#define LORA_PKT_COUNT  1000
#endif
#ifndef LORA_DURATION_SEC
#define LORA_DURATION_SEC 0
#endif
#ifndef LORA_AUTO_START
#define LORA_AUTO_START 0   // 0 = wait for RUN (LoRa is slow, auto-start optional)
#endif

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
static uint16_t cfgPktSize = LORA_PKT_SIZE;
static float    cfgPower   = LORA_POWER_DBM;
static uint32_t cfgCount   = LORA_PKT_COUNT;
static uint32_t cfgDurationSec = LORA_DURATION_SEC;
static bool     autoStart  = LORA_AUTO_START;

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
    // LowDataRateOptimize: enable if symbol time > 16ms
    // symbol time = (2^SF) / BW seconds
    // For SF12 @ 203kHz: 4096/203125 = 20.2ms → enable
    // For SF7 @ 812kHz: 128/812500 = 0.157ms → disable
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
// flags = ((hdrType & 0x01) << 2) | ((crcType & 0x01) << 1) | (invertIQ & 0x01)
// hdrType: 0=explicit, 1=implicit
// crcType: 0=disabled, 1=enabled
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

// ─── Full LoRa radio init ─────────────────────────────────────────────
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

    // SET_RX_PATH (HF = 0x01)
    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // CALIB_FRONT_END
    uint16_t feFreq = (uint16_t)((cfgFreq / 4.0f) + 0.5f) | 0x8000;
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

    // SET_TX_PARAMS
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
        dualPrintln("RADIO_INIT_OK (LoRa TX)");
        return true;
    }
    dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

// ─── LoRa TX run ─────────────────────────────────────────────────────
static bool txRunning = false;

static void runTransmit() {
    if (!radioReady) return;

    uint16_t pktSize = cfgPktSize;
    uint32_t count = cfgCount;
    uint32_t durationMs = cfgDurationSec > 0 ? (cfgDurationSec * 1000) : 0;

    digitalWrite(PIN_LED, HIGH);
    digitalWrite(PIN_LED_ALT, HIGH);

    int bwKhz = bwCodeToKhz(cfgBwCode);
    dualPrintf("LORA_TX START sf=%d bw=%d cr=4/%d pktSize=%d count=%lu duration_ms=%lu power=%.1f",
               cfgSf, bwKhz, (cfgCr + 4), pktSize,
               (unsigned long)count, (unsigned long)durationMs, cfgPower);

    uint8_t pkt[256];
    for (int j = 4; j < pktSize; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t irqMask = 1UL << PIN_IRQ;
    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    // LoRa is slow — print every 10 packets
    uint32_t printInterval = 10;

    txRunning = true;
    uint32_t i;
    for (i = 0; txRunning; i++) {
        if (count > 0 && i >= count) break;
        if (durationMs > 0 && (millis() - startMs) >= durationMs) break;

        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        rfClearIrq();
        rfClearTxFifo();
        rfWriteTxFifo(pkt, pktSize);
        rfSetTx();

        // LoRa TX takes much longer — use longer timeout
        uint32_t spinCount = 0;
        bool irqFired = false;
        // For SF12 @ 203kHz, a 127-byte packet can take >10 seconds
        // Use a generous timeout of 30M iterations (~30s at ~1us/iter)
        while (spinCount < 30000000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
        }

        if (irqFired) txDoneCount++;
        else txTimeoutCount++;

        if (txDoneCount > 0 && (txDoneCount % printInterval) == 0) {
            uint32_t elapsed = millis() - startMs;
            float tput = ((float)txDoneCount * pktSize * 8.0f) / (elapsed > 0 ? elapsed : 1);
            dualPrintf("TX_PROGRESS sent=%lu fired=%lu to=%lu elapsed_ms=%lu tput=%.1fkbps",
                       (unsigned long)(i + 1),
                       (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
                       (unsigned long)elapsed, tput);
        }

        // Check for serial STOP command
        if (Serial.available()) {
            String line = Serial.readStringUntil('\n');
            line.trim();
            line.toUpperCase();
            if (line.startsWith("STOP")) {
                dualPrintln("TX_STOPPED by serial command");
                break;
            }
        }
    }
    txRunning = false;

    uint32_t elapsed = millis() - startMs;
    float tput = (elapsed > 0) ? ((float)txDoneCount * pktSize * 8.0f) / (float)elapsed : 0.0f;

    dualPrintf("LORA_TX DONE sent=%lu fired=%lu to=%lu elapsed_ms=%lu tput=%.1fkbps",
               (unsigned long)i, (unsigned long)txDoneCount,
               (unsigned long)txTimeoutCount, (unsigned long)elapsed, tput);

    // Structured result line
    dualPrintf("LORA_TX_RESULT,sent=%lu,fired=%lu,timeout=%lu,elapsed_ms=%lu,throughput_kbps=%.1f,sf=%d,bw=%d,cr=4/%d,pktSize=%d,power=%.1f,freq=%.1f",
               (unsigned long)i, (unsigned long)txDoneCount,
               (unsigned long)txTimeoutCount, (unsigned long)elapsed, tput,
               cfgSf, bwKhz, (cfgCr + 4), pktSize, cfgPower, cfgFreq);

    digitalWrite(PIN_LED, LOW);
    digitalWrite(PIN_LED_ALT, LOW);
}

// ─── Serial command processing ──────────────────────────────────────
static void processSerial() {
    if (!Serial.available() && !Serial1.available()) return;

    String line;
    if (Serial.available()) line = Serial.readStringUntil('\n');
    else line = Serial1.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    String cmd = line;
    cmd.toUpperCase();

    if (cmd.startsWith("SF ")) {
        int val = cmd.substring(3).toInt();
        if (val >= 5 && val <= 12) {
            cfgSf = val;
            rfSetLoraModParams(cfgSf, cfgBwCode, cfgCr);
            dualPrintf("SF set to %d", cfgSf);
        } else {
            dualPrintln("ERROR: invalid SF (5-12)");
        }
    }
    else if (cmd.startsWith("BW ")) {
        int val = cmd.substring(3).toInt();
        if (val == 203 || val == 406 || val == 812) {
            cfgBwCode = bwKhzToCode(val);
            rfSetLoraModParams(cfgSf, cfgBwCode, cfgCr);
            dualPrintf("BW set to %d kHz", val);
        } else {
            dualPrintln("ERROR: invalid BW (203/406/812)");
        }
    }
    else if (cmd.startsWith("CR ")) {
        int val = cmd.substring(3).toInt();
        if (val >= 5 && val <= 8) {
            cfgCr = val - 4;  // 5→1, 6→2, 7→3, 8→4
            rfSetLoraModParams(cfgSf, cfgBwCode, cfgCr);
            dualPrintf("CR set to 4/%d", val);
        } else {
            dualPrintln("ERROR: invalid CR (5-8, meaning 4/5 to 4/8)");
        }
    }
    else if (cmd.startsWith("COUNT ")) {
        cfgCount = (uint32_t)strtoul(cmd.substring(6).c_str(), NULL, 10);
        dualPrintf("COUNT set to %lu", (unsigned long)cfgCount);
    }
    else if (cmd.startsWith("DURATION ")) {
        cfgDurationSec = (uint32_t)strtoul(cmd.substring(9).c_str(), NULL, 10);
        dualPrintf("DURATION set to %lu seconds", (unsigned long)cfgDurationSec);
    }
    else if (cmd == "RUN") {
        dualPrintln("RUN command received");
        runTransmit();
    }
    else if (cmd == "STOP") {
        txRunning = false;
        dualPrintln("STOP command received");
    }
    else if (cmd == "STATUS") {
        int bwKhz = bwCodeToKhz(cfgBwCode);
        dualPrintf("STATUS: freq=%.1f sf=%d bw=%d cr=4/%d pktSize=%d power=%.1f count=%lu duration=%lu autoStart=%d radioReady=%d",
                   cfgFreq, cfgSf, bwKhz, (cfgCr + 4), cfgPktSize, cfgPower,
                   (unsigned long)cfgCount, (unsigned long)cfgDurationSec,
                   autoStart, radioReady);
    }
    else if (cmd == "INIT") {
        radioReady = rawInitRadio();
    }
    else if (cmd == "HELP") {
        dualPrintln("Commands: SF <n> BW <kHz> CR <n> COUNT <n> DURATION <sec> RUN STOP STATUS INIT HELP");
    }
    else {
        dualPrintf("UNKNOWN: %s (type HELP)", line.c_str());
    }
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

    // 2s countdown blink
    for (int i = 0; i < 4; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH);
        delay(250);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);
        delay(250);
    }

    int bwKhz = bwCodeToKhz(cfgBwCode);
    dualPrintln();
    dualPrintln("=== RP2040 LORA RANGE TX ===");
    dualPrintf("Config: freq=%.1f sf=%d bw=%d cr=4/%d pktSize=%d power=%.1f count=%lu",
               cfgFreq, cfgSf, bwKhz, (cfgCr + 4), cfgPktSize, cfgPower,
               (unsigned long)cfgCount);

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        if (autoStart) {
            dualPrintln("AUTO TX STARTING in 3s — type STOP to abort");
            delay(3000);
            runTransmit();
        } else {
            dualPrintln("READY — type RUN to start TX");
        }
    } else {
        dualPrintln("INIT FAILED — retrying...");
        delay(2000);
        radioReady = rawInitRadio();
        if (radioReady) {
            digitalWrite(PIN_LED_ALT, HIGH);
            if (autoStart) {
                dualPrintln("AUTO TX STARTING (2nd init) in 3s");
                delay(3000);
                runTransmit();
            } else {
                dualPrintln("READY (2nd init) — type RUN to start TX");
            }
        } else {
            dualPrintln("INIT FAILED TWICE — stuck");
        }
    }
}

void loop() {
    processSerial();

    if (!radioReady) {
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(500);
    }
}