/*
 * lora_range_rx.cpp — LoRa RX with raw SPI LoRa init and RSSI readback
 *
 * Uses raw 2-byte opcode SPI (ADR-020). No RadioLib.
 * LoRa init sequence verified against RadioLib v7.6.0 source.
 *
 * Behavior:
 * - On boot: init radio in LoRa mode, auto-start RX listen
 * - RX loop: poll IRQ pin → readFifo → re-arm → readLoraRssi (0x022A)
 * - Time-based window: LISTEN_MS=30000, SILENCE_MS=5000
 * - LED blinks on each packet received
 *
 * Structured output: LORA_RX_RESULT,rx=N,unique=N,lost=N,per=X,throughput_kbps=Y,rssi_avg=Z,rssi_min=W,sf=A,bw=B
 *
 * Compile-time defaults: FREQ=2440, SF=7, BW=812, CR=4/5, PKT_SIZE=127
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13
 *       LED=GP25 LED_ALT=GP16
 */

#include <Arduino.h>
#include <SPI.h>
#include "pico/bootrom.h"

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
#ifndef RX_FREQ_MHZ
#define RX_FREQ_MHZ     2440.0f
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
#ifndef RX_LISTEN_MS
#define RX_LISTEN_MS    30000
#endif
#ifndef RX_SILENCE_MS
#define RX_SILENCE_MS   5000
#endif
#ifndef PRINT_EVERY
#define PRINT_EVERY     10
#endif

// ─── LoRa BW encoding ────────────────────────────────────────────────
static uint8_t bwKhzToCode(int khz) {
    switch (khz) {
        case 203: return 0x0D;
        case 406: return 0x0E;
        case 812: return 0x0F;
        default:  return 0x0F;
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

static volatile bool radioReady = false;

// ─── Runtime config ───────────────────────────────────────────────────
static float    cfgFreq    = RX_FREQ_MHZ;
static uint8_t  cfgSf      = LORA_SF;
static uint8_t  cfgBwCode  = bwKhzToCode(LORA_BW_KHZ);
static uint8_t  cfgCr      = LORA_CR;
static uint16_t cfgPktSize = LORA_PKT_SIZE;

// ─── SPI helpers ─────────────────────────────────────────────────────
static inline void rfWaitBusy() {
    uint32_t timeout = millis() + 100;  // LoRa operations can be slow
    while (digitalRead(PIN_BUSY) == HIGH) {
        if (millis() > timeout) return;
    }
}

static void rfWriteCmd(const uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfReadFifo(uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00); spiRf.transfer(0x01);  // READ_RX_FIFO
    for (size_t i = 0; i < len; i++) buf[i] = spiRf.transfer(0x00);
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

static void rfSetRx() {
    // SET_RX with timeout (0xFFFFFF = infinite)
    uint8_t cmd[5] = { 0x02, 0x0C, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 5);
}

static void rfClearRxFifo() {
    uint8_t cmd[] = { 0x01, 0x1E };
    rfWriteCmd(cmd, 2);
}

static void rfClearErrors() {
    uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 };
    rfWriteCmd(cmd, 4);
}

// ─── LoRa RSSI/SNR readback via GET_LORA_PACKET_STATUS (0x022A) ─────
// Response after 2 status bytes (verified against RadioLib SX128x source):
//   buf[0] = status_msb
//   buf[1] = status_lsb
//   buf[2] = rssiSync (packet RSSI)  → dBm = -val / 2
//   buf[3] = SNR (signed)            → dB = val<128 ? val/4 : (val-256)/4
//   buf[4..7] = signal_rssi, flags, etc (unused)
//
// BUG FIX: Previous code had RSSI and SNR byte indices SWAPPED.
// RadioLib SX128x::getRSSI() reads packetStatus[0] for RSSI,
// SX128x::getSNR() reads packetStatus[1] for SNR.

// Forward declarations (defined later)
static void dualPrintf(const char *fmt, ...);

static uint8_t g_lastStatusDump = 0;  // dump raw bytes for first 3 packets

static int8_t rfReadLoraRssi() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02); spiRf.transfer(0x2A);  // GET_LORA_PACKET_STATUS
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    // Read 8 bytes: [stat_msb][stat_lsb][rssiSync][snr][signal_rssi][flags][?][?]
    uint8_t buf[8];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 8; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    // Debug: dump raw bytes for first 3 packets
    if (g_lastStatusDump < 3) {
        g_lastStatusDump++;
        dualPrintf("PKT_STATUS_RAW: %02X %02X %02X %02X %02X %02X %02X %02X",
                   buf[0], buf[1], buf[2], buf[3], buf[4], buf[5], buf[6], buf[7]);
    }

    // RSSI: buf[2] = rssiSync, simple formula: -val / 2
    return -(int8_t)(buf[2] / 2);
}

static float rfReadLoraSnr() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02); spiRf.transfer(0x2A);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[8];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 8; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    // SNR: buf[3], signed byte / 4
    uint8_t snrRaw = buf[3];
    if (snrRaw < 128) {
        return (float)snrRaw / 4.0f;
    } else {
        return ((float)snrRaw - 256.0f) / 4.0f;
    }
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
    rfClearErrors();
    delay(1);

    // SET_STANDBY(STDBY_XOSC = 0x01)
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; rfWriteCmd(cmd, 3); }
    delay(5);

    // SET_PACKET_TYPE = LoRa (0x00)
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

    // SET_PA_CONFIG (needed even for RX — chip uses it for fallback)
    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);

    // SET_RX_TX_FALLBACK (FS = 0x03)
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // SET_DIO_FUNCTION (DIO9 = IRQ, DIO1 = BUSY)
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // SET_DIO_IRQ_CONFIG: RX_DONE (bit18=0x00040000) + CRC_ERROR (bit22=0x00200000)
    // dioNum=0x09 (DIO9), IRQ mask = 0x00240000
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x24, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
    delay(1);

    rfClearIrq();
    delay(1);
    rfSetRx();
    delay(2);

    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    if ((st >> 4) == 0x05) {
        dualPrintln("RADIO_INIT_OK (LoRa RX mode)");
        return true;
    } else if (irq & 0x00020000) {
        dualPrintf("RADIO_INIT_WARN CMD_ERROR (St=0x%02X)", st);
        return true;
    } else {
        dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
        return false;
    }
}

// ─── Statistics ──────────────────────────────────────────────────────
struct RxStats {
    uint32_t received;      // per-window count
    uint32_t cumulativeRx;  // total across all windows (never reset)
    uint32_t unique;
    uint32_t duplicates;
    uint32_t lastSeq;
    uint32_t maxSeq;
    uint32_t startMs;
    uint32_t elapsedMs;
    int32_t  rssiSum;
    int16_t  rssiMin;
    int16_t  rssiMax;
    uint16_t rssiCount;
    float    snrSum;
    uint16_t snrCount;
};
static RxStats stats;

static void resetStats() {
    // Preserve cumulativeRx across windows
    uint32_t savedCum = stats.cumulativeRx;
    memset(&stats, 0, sizeof(stats));
    stats.cumulativeRx = savedCum;
    stats.lastSeq = 0xFFFFFFFF;
    stats.rssiMin = 0;
    stats.rssiMax = -128;
}

// ─── Receive session ─────────────────────────────────────────────────
static uint32_t windowNum = 0;

static void runReceive() {
    if (!radioReady) return;

    rfClearIrq();
    rfSetRx();
    delay(1);

    resetStats();
    stats.startMs = millis();
    uint32_t lastPktMs = millis();
    uint16_t pktSize = cfgPktSize;
    uint8_t buf[256];

    int bwKhz = bwCodeToKhz(cfgBwCode);
    dualPrintf("LORA_RX_WINDOW %lu START uptime=%lums listen=%dms sf=%d bw=%d",
               (unsigned long)windowNum, (unsigned long)stats.startMs,
               RX_LISTEN_MS, cfgSf, bwKhz);

    while (true) {
        uint32_t now = millis();
        if ((now - stats.startMs) >= RX_LISTEN_MS) {
            dualPrintln("RX_DONE timeout");
            break;
        }
        if (stats.received > 0 && (now - lastPktMs) >= RX_SILENCE_MS) {
            dualPrintln("RX_DONE silence");
            break;
        }

        // Hardware pin poll — IRQ goes HIGH on RX_DONE
        if (digitalRead(PIN_IRQ) == LOW) continue;

        // Read packet
        rfReadFifo(buf, pktSize);

        // Re-arm FIRST (before RSSI) to minimize dead time
        rfClearRxFifo();
        rfClearErrors();
        rfClearIrq();
        rfSetRx();
        rfWaitBusy();

        // Read LoRa RSSI via GET_LORA_PACKET_STATUS (0x022A)
        int8_t rssi = rfReadLoraRssi();
        float snr = rfReadLoraSnr();
        stats.rssiSum += rssi;
        stats.rssiCount++;
        if (rssi < stats.rssiMin) stats.rssiMin = rssi;
        if (rssi > stats.rssiMax) stats.rssiMax = rssi;
        stats.snrSum += snr;
        stats.snrCount++;

        // Extract big-endian seq
        uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                       ((uint32_t)buf[2] << 8)  | (uint32_t)buf[3];

        stats.received++;
        stats.cumulativeRx++;
        if (stats.lastSeq != 0xFFFFFFFF && seq == stats.lastSeq) stats.duplicates++;
        else stats.unique++;
        stats.lastSeq = seq;
        if (seq > stats.maxSeq) stats.maxSeq = seq;
        lastPktMs = millis();

        // Blink LED on packet
        digitalWrite(PIN_LED, HIGH);
        delayMicroseconds(50);
        digitalWrite(PIN_LED, LOW);

        if (stats.received <= 5 || (stats.received % PRINT_EVERY) == 0) {
            dualPrintf("PKT %lu seq=%lu rssi=%d snr=%.1f uptime=%lums",
                       (unsigned long)stats.received, (unsigned long)seq,
                       rssi, snr, (unsigned long)millis());
        }
    }

    stats.elapsedMs = millis() - stats.startMs;

    // Compute results — use cumulative count for PER (maxSeq is global)
    uint32_t n = stats.received;
    uint32_t cumRx = stats.cumulativeRx;
    uint32_t total = stats.maxSeq + 1;  // no DEADBEEF marker in LoRa mode
    uint32_t lost = (total > cumRx) ? (total - cumRx) : 0;
    float perPct = (total > 0) ? (100.0f * (float)lost / (float)total) : 0.0f;
    float tputKbps = (stats.elapsedMs > 0 && n > 0)
                     ? ((float)n * (float)pktSize * 8.0f) / (float)stats.elapsedMs : 0.0f;
    float rssiAvg = (stats.rssiCount > 0)
                    ? (float)stats.rssiSum / (float)stats.rssiCount : 0.0f;
    float snrAvg = (stats.snrCount > 0)
                   ? stats.snrSum / (float)stats.snrCount : 0.0f;

    dualPrintln("=============================================");
    dualPrintf("  Window:   %lu", (unsigned long)windowNum);
    dualPrintf("  Received: %lu this window (cumulative %lu, unique %lu, dup %lu)", (unsigned long)n,
               (unsigned long)cumRx, (unsigned long)stats.unique, (unsigned long)stats.duplicates);
    dualPrintf("  Max seq:  %lu", (unsigned long)stats.maxSeq);
    dualPrintf("  Lost:     %lu (%.2f%% cumulative)", (unsigned long)lost, perPct);
    dualPrintf("  Elapsed:  %lu ms", (unsigned long)stats.elapsedMs);
    dualPrintf("  THROUGHPUT: %.1f kbps", tputKbps);
    if (stats.rssiCount > 0) {
        dualPrintf("  RSSI: avg=%.1f dBm min=%d dBm max=%d dBm (n=%d)",
                   rssiAvg, stats.rssiMin, stats.rssiMax, stats.rssiCount);
        dualPrintf("  SNR:  avg=%.1f dB (n=%d)", snrAvg, stats.snrCount);
    } else {
        dualPrintln("  RSSI: (no packets received)");
    }
    dualPrintln("=============================================");

    // Structured result line for automated parsing
    dualPrintf("LORA_RX_RESULT,window=%lu,rx=%lu,cum_rx=%lu,unique=%lu,lost=%lu,total=%lu,per=%.2f,elapsed_ms=%lu,throughput_kbps=%.1f,rssi_avg=%.1f,rssi_min=%d,snr_avg=%.1f,sf=%d,bw=%d,cr=4/%d,pktSize=%d,freq=%.1f,uptime_ms=%lu",
               (unsigned long)windowNum,
               (unsigned long)n, (unsigned long)cumRx, (unsigned long)stats.unique, (unsigned long)lost,
               (unsigned long)total, perPct, (unsigned long)stats.elapsedMs, tputKbps,
               rssiAvg, stats.rssiMin, snrAvg,
               cfgSf, bwKhz, (cfgCr + 4), cfgPktSize, cfgFreq,
               (unsigned long)stats.startMs);

    windowNum++;
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
            // Re-init needed for LoRa mod params change
            radioReady = rawInitRadio();
        } else {
            dualPrintln("ERROR: invalid SF (5-12)");
        }
    }
    else if (cmd.startsWith("BW ")) {
        int val = cmd.substring(3).toInt();
        if (val == 203 || val == 406 || val == 812) {
            cfgBwCode = bwKhzToCode(val);
            radioReady = rawInitRadio();
        } else {
            dualPrintln("ERROR: invalid BW (203/406/812)");
        }
    }
    else if (cmd.startsWith("CR ")) {
        int val = cmd.substring(3).toInt();
        if (val >= 5 && val <= 8) {
            cfgCr = val - 4;
            radioReady = rawInitRadio();
        } else {
            dualPrintln("ERROR: invalid CR (5-8)");
        }
    }
    else if (cmd == "STATUS") {
        int bwKhz = bwCodeToKhz(cfgBwCode);
        dualPrintf("STATUS: freq=%.1f sf=%d bw=%d cr=4/%d pktSize=%d radioReady=%d window=%lu",
                   cfgFreq, cfgSf, bwKhz, (cfgCr + 4), cfgPktSize, radioReady,
                   (unsigned long)windowNum);
    }
    else if (cmd == "INIT") {
        radioReady = rawInitRadio();
    }
    else if (cmd == "HELP") {
        dualPrintln("Commands: SF <n> BW <kHz> CR <n> STATUS INIT HELP");
    }
    else {
        dualPrintf("UNKNOWN: %s (type HELP)", line.c_str());
    }
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(2000);  // give TinyUSB time to enumerate
    Serial.println("BOOT LORA RX RANGE");
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);
    delay(100);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);
    for (int i = 0; i < 4; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(250);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(250);
    }

    int bwKhz = bwCodeToKhz(cfgBwCode);
    dualPrintln();
    dualPrintln("=== RP2040 LORA RANGE RX ===");
    dualPrintf("Config: freq=%.1f sf=%d bw=%d cr=4/%d pktSize=%d listen=%dms",
               cfgFreq, cfgSf, bwKhz, (cfgCr + 4), cfgPktSize, RX_LISTEN_MS);

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        dualPrintln("AUTO RX LISTENING (LoRa)");
    } else {
        dualPrintln("INIT FAILED — retrying...");
        delay(2000);
        radioReady = rawInitRadio();
        if (radioReady) {
            digitalWrite(PIN_LED_ALT, HIGH);
            dualPrintln("AUTO RX LISTENING (2nd init, LoRa)");
        } else {
            dualPrintln("INIT FAILED TWICE — stuck");
        }
    }
}

void loop() {
    if (radioReady) {
        runReceive();
        delay(500);  // brief pause between windows
    } else {
        // Blink SOS if radio dead
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(500);
    }

    processSerial();
}