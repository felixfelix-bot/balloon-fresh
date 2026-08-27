/*
 * pkt_harmonized_rx.cpp — RP2040 RX firmware with harmonized 23-field PKT format
 *
 * Implements RP-1: Build RP2040 firmware with harmonized 23-field format from
 * start (M1-M7, O4).
 *
 *   M1: FW_HASH in boot banner
 *   M6: Non-resetting uint32 seq counter (persists across phase changes)
 *   M3+M4+M5: 23-field PKT lines
 *   M7: Logs CRC-failed packets with RSSI
 *   O4: CONFIG_START transition markers
 *
 * Based on the proven multi_radio_sweep_rx_v4.cpp radio engine (LR2021 raw SPI
 * RX) but with the harmonized PKT output format built in from scratch.
 *
 * 23-field PKT format:
 *   PKT,session_id,config_id,replicate,seq,ts_ms,rssi_dbm,snr_db,crc_ok,
 *      bit_err,bytes_bad,freq_hz,mod,sf,bw_khz,cr,power_dbm,pkt_size,
 *      gps_fix,gps_lat,gps_lon,gps_alt,gps_sats,gps_hdop
 *
 * Commands (over USB serial):
 *   SESSION <id>     — set session_id
 *   CONFIG <id> <n> — set config_id + replicate, emit CONFIG_START
 *   SET_TIME <ts>   — sync UTC from laptop (NTP)
 *   FW_QUERY         — re-print boot banner
 *   SET_INTERLEAVE <0|1> — toggle interleave mode
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13  LED=GP25
 */

#include <Arduino.h>
#include <SPI.h>
#include <stdarg.h>
#include <string.h>
#include "prbs.h"

// ─── Firmware self-identification (injected at build time) — M1 ───────
#ifndef FW_GIT_HASH
#define FW_GIT_HASH "unknown"
#endif
#ifndef FW_BUILD_TAG
#define FW_BUILD_TAG "UNK0"
#endif
#ifndef FW_BUILD_TIME
#define FW_BUILD_TIME "1970-01-01T00:00Z"
#endif

// ─── Session/config state (set by serial commands) ─────────────────────
static char     session_id[40] = "";
static char     config_id[32]  = "";
static uint16_t replicate_num  = 0;

// ─── PRBS-15 mode gate: ON by default for range test (BER measurement) ──
static bool prbs_enabled = true;

// PRBS payload starts at byte 29 (after sync 0-3, GPS 4-28)
// and ends at pktSize-3 (before 2-byte CRC at pktSize-2..pktSize-1)
#define PRBS_START 29

// ─── M6: Non-resetting uint32 seq counter ─────────────────────────────
// Persists across phase changes — does NOT reset in resetRxPhaseState().
// This is the RX-side monotonic packet counter for the harmonized format.
static uint32_t pktSeq = 0;

// ─── Dual serial output (USB CDC + UART1→ESP32 bridge) ────────────────
static uint32_t lastCdcOutputMs = 0;
#define CDC_WATCHDOG_MS 30000

static void dualPrintf(const char* fmt, ...) {
    char buf[400];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.print(buf);
    Serial.flush();
    Serial1.print(buf);
    lastCdcOutputMs = millis();
}

// ─── M1: Boot banner with FW_HASH ─────────────────────────────────────
static void printBootBanner() {
    dualPrintf("FW_BOOT FW_HASH=%s tag=%s built=%s\r\n",
               FW_GIT_HASH, FW_BUILD_TAG, FW_BUILD_TIME);
}

// ─── Pins ────────────────────────────────────────────────────────────
#define PIN_SCK     2
#define PIN_MOSI    3
#define PIN_MISO    4
#define PIN_CS      5
#define PIN_BUSY    6
#define PIN_IRQ     7
#define PIN_RST     8
#undef PIN_LED
#define PIN_LED     25

#define SPI_FREQ_HZ  20000000UL
#define XTAL_MHZ     52.0f

// ─── Phase table (must match TX exactly) ──────────────────────────────
enum PacketType { PT_LORA = 0x00, PT_FLRC = 0x05 };

typedef struct {
    const char* name;
    uint8_t  pktType;    // 0x00=LoRa, 0x05=FLRC
    float    freqMHz;
    uint8_t  rfPath;     // 1=HF, 0=LF
    uint8_t  sf;         // LoRa only
    uint8_t  bwCode;     // LoRa BW code
    uint8_t  cr;         // LoRa CR
    uint16_t flrcBr;     // FLRC bitrate (0 for LoRa)
    uint16_t pktCount;   // expected packets from TX
    uint16_t slotMs;     // time budget
    uint16_t pktSize;    // payload size (32/64/128/255)
} Phase;

static const Phase phases[] = {
    {"HF-LoRa-SF7",   PT_LORA, 2440.0, 1,  7, 0x0F, 1,    0,  50, 15000, 255},
    {"HF-LoRa-SF9",   PT_LORA, 2440.0, 1,  9, 0x0F, 1,    0,  50, 15000, 255},
    {"HF-FLRC-325",   PT_FLRC, 2440.0, 1,  0, 0x00, 0,  325, 200,  8000, 255},
    {"HF-FLRC-650",   PT_FLRC, 2440.0, 1,  0, 0x00, 0,  650, 200,  8000, 255},
    {"HF-FLRC-1300",  PT_FLRC, 2440.0, 1,  0, 0x00, 0, 1300, 200,  8000, 255},
    {"HF-FLRC-2600",  PT_FLRC, 2440.0, 1,  0, 0x00, 0, 2600, 200,  8000, 255},
    {"HF-LoRa-SF12",  PT_LORA, 2440.0, 1, 12, 0x0F, 1,    0,  15, 30000, 255},
    {"LF-LoRa-SF7",   PT_LORA,  868.0, 0,  7, 0x05, 1,    0,  50,  8000, 255},
    {"LF-LoRa-SF9",   PT_LORA,  868.0, 0,  9, 0x05, 1,    0,  30, 20000, 255},
    {"LF-LoRa-SF12",  PT_LORA,  868.0, 0, 12, 0x05, 1,    0,  10, 50000, 255},
    {"LF-FLRC-325",   PT_FLRC,  868.0, 0,  0, 0x00, 0,  325, 200,  8000, 255},
    {"LF-FLRC-650",   PT_FLRC,  868.0, 0,  0, 0x00, 0,  650, 200,  8000, 255},
    {"LF-FLRC-1300",  PT_FLRC,  868.0, 0,  0, 0x00, 0, 1300, 200,  8000, 255},
    {"LF-FLRC-2600",  PT_FLRC,  868.0, 0,  0, 0x00, 0, 2600, 200,  8000, 255},
};
static const int NUM_PHASES = sizeof(phases) / sizeof(phases[0]);

// ─── V4: Interleave mode ─────────────────────────────────────────────
static const uint16_t SWEEP_SIZES[] = {32, 64, 128, 255};
#define NUM_SWEEP_SIZES 4
static Phase interleavePhases[128];
static int   numInterleavePhases = 0;
static bool  interleaveMode = true;

// V4: Channel sweep frequencies
static const float SWEEP_FREQS_HF[] = {
    2412.0, 2417.0, 2422.0, 2427.0, 2432.0, 2437.0,
    2442.0, 2447.0, 2452.0, 2457.0, 2462.0, 2467.0, 2472.0
};
#define NUM_SWEEP_FREQS_HF 13
static const float SWEEP_FREQS_LF[] = {
    863.0, 864.0, 865.0, 866.0, 867.0, 868.0, 869.0, 870.0
};
#define NUM_SWEEP_FREQS_LF 8

static uint32_t totalCycleSec = 0;
static uint32_t totalCycleMs = 0;

static void buildInterleaveTable() {
    int idx = 0;
    static char nameBufs[128][32];
    for (int mode = 0; mode < NUM_PHASES; mode++) {
        const Phase &base = phases[mode];
        for (int s = 0; s < NUM_SWEEP_SIZES; s++) {
            Phase &exp = interleavePhases[idx];
            exp = base;
            exp.pktSize = SWEEP_SIZES[s];
            if (base.pktType == PT_FLRC) {
                exp.pktCount = 100; exp.slotMs = 3000;
            } else {
                float msPerByte;
                if (base.rfPath == 1) {
                    if (base.sf == 7) msPerByte = 0.44f;
                    else if (base.sf == 9) msPerByte = 1.71f;
                    else msPerByte = 31.0f;
                } else {
                    if (base.sf == 7) msPerByte = 1.6f;
                    else if (base.sf == 9) msPerByte = 12.8f;
                    else msPerByte = 410.0f;
                }
                float airMs = msPerByte * SWEEP_SIZES[s] + 10.0f;
                if (base.rfPath == 0 && base.sf == 12 && s > 0) {
                    exp.pktCount = 0; exp.slotMs = 1000;
                    snprintf(nameBufs[idx], 32, "%s-SKIP", base.name);
                } else {
                    int tp = (int)(3000.0f / airMs);
                    if (tp < 1) tp = 1; if (tp > 20) tp = 20;
                    exp.pktCount = tp;
                    float st = tp * airMs * 1.3f + 500.0f;
                    if (st < 2000.0f) st = 2000.0f; if (st > 15000.0f) st = 15000.0f;
                    exp.slotMs = (uint16_t)st;
                    snprintf(nameBufs[idx], 32, "%s-%d", base.name, SWEEP_SIZES[s]);
                }
            }
            if (interleavePhases[idx].pktCount != 0 || nameBufs[idx][0]=='\0')
                snprintf(nameBufs[idx], 32, "%s-%d", base.name, SWEEP_SIZES[s]);
            exp.name = nameBufs[idx];
            idx++;
        }
    }

    // V4: Channel sweep
    for (int f = 0; f < NUM_SWEEP_FREQS_HF; f++) {
        Phase &exp = interleavePhases[idx];
        exp = phases[3];
        exp.freqMHz = SWEEP_FREQS_HF[f];
        exp.pktSize = 64;
        exp.pktCount = 100;
        exp.slotMs = 3000;
        snprintf(nameBufs[idx], 32, "CH-%d-FLRC1300-64", (int)SWEEP_FREQS_HF[f]);
        exp.name = nameBufs[idx];
        idx++;
    }
    for (int f = 0; f < NUM_SWEEP_FREQS_LF; f++) {
        Phase &exp = interleavePhases[idx];
        exp = phases[11];
        exp.freqMHz = SWEEP_FREQS_LF[f];
        exp.pktSize = 64;
        exp.pktCount = 100;
        exp.slotMs = 3000;
        snprintf(nameBufs[idx], 32, "CH-%d-FLRC1300-64", (int)SWEEP_FREQS_LF[f]);
        exp.name = nameBufs[idx];
        idx++;
    }

    numInterleavePhases = idx;
}

// ─── Laptop time sync ─────────────────────────────────────────────────
static uint32_t utcOffset = 0;

static uint32_t getUtcNow() {
    return millis() / 1000 + utcOffset;
}

// ─── Serial command processing (SESSION, CONFIG, SET_TIME, etc.) ─────
static char cmdBuf[128];
static int   cmdLen = 0;

static void processCommand(const char *cmd) {
    if (strncmp(cmd, "SET_TIME ", 9) == 0) {
        uint32_t ts = (uint32_t)strtoul(cmd + 9, nullptr, 10);
        if (ts > 0) {
            utcOffset = ts - millis() / 1000;
            dualPrintf("TIME_SYNCED utc=%lu offset=%ld\n",
                      (unsigned long)getUtcNow(), (long)utcOffset);
        }
    } else if (strcmp(cmd, "FW_QUERY") == 0) {
        printBootBanner();
    } else if (strncmp(cmd, "SESSION ", 9) == 0) {
        // SESSION <id> — set session_id
        strncpy(session_id, cmd + 9, sizeof(session_id) - 1);
        session_id[sizeof(session_id) - 1] = '\0';
        dualPrintf("OK SESSION SET\r\n");
    } else if (strncmp(cmd, "CONFIG ", 7) == 0) {
        // CONFIG <id> <replicate> — set config_id + replicate, emit CONFIG_START
        char cid[32] = "";
        unsigned repl = 0;
        if (sscanf(cmd + 7, "%31s %u", cid, &repl) >= 1) {
            strncpy(config_id, cid, sizeof(config_id) - 1);
            config_id[sizeof(config_id) - 1] = '\0';
            replicate_num = (uint16_t)repl;
            uint32_t ts_ms = millis();
            // O4: CONFIG_START transition marker
            dualPrintf("CONFIG_START,%s,%u,%u\r\n", config_id,
                       (unsigned)replicate_num, (unsigned)ts_ms);
            dualPrintf("OK CONFIG SET\r\n");
        } else {
            dualPrintf("ERR CONFIG SYNTAX\r\n");
        }
    } else if (strncmp(cmd, "SET_INTERLEAVE ", 15) == 0) {
        int val = atoi(cmd + 15);
        interleaveMode = (val != 0);
        totalCycleSec = 0;
        totalCycleMs = 0;
        if (interleaveMode) {
            for (int i = 0; i < numInterleavePhases; i++) {
                totalCycleSec += interleavePhases[i].slotMs / 1000;
                totalCycleMs += interleavePhases[i].slotMs;
            }
            dualPrintf("INTERLEAVE_ON phases=%d cycle=%lus (%lums)\n",
                       numInterleavePhases, (unsigned long)totalCycleSec,
                       (unsigned long)totalCycleMs);
        } else {
            for (int i = 0; i < NUM_PHASES; i++)
                totalCycleSec += phases[i].slotMs / 1000;
            dualPrintf("INTERLEAVE_OFF phases=%d cycle=%lus\n",
                       NUM_PHASES, (unsigned long)totalCycleSec);
        }
    } else if (strncmp(cmd, "PRBS ", 5) == 0) {
        // PRBS ON|OFF — toggle PRBS-15 BER verification mode
        if (strcmp(cmd + 5, "ON") == 0 || strcmp(cmd + 5, "1") == 0) {
            prbs_enabled = true;
            dualPrintf("OK PRBS ON\r\n");
        } else if (strcmp(cmd + 5, "OFF") == 0 || strcmp(cmd + 5, "0") == 0) {
            prbs_enabled = false;
            dualPrintf("OK PRBS OFF\r\n");
        } else {
            dualPrintf("ERR PRBS SYNTAX (use: PRBS ON|OFF)\r\n");
        }
    }
}

static void checkSerialCommands() {
    if (!Serial.available()) return;

    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (cmdLen > 0) {
                cmdBuf[cmdLen] = '\0';
                processCommand(cmdBuf);
                cmdLen = 0;
            }
        } else {
            if (cmdLen < (int)sizeof(cmdBuf) - 1) {
                cmdBuf[cmdLen++] = c;
            }
        }
    }
}

// ─── Phase computation ────────────────────────────────────────────────
static int currentPhase = -1;
static uint32_t phaseStartMs = 0;

static int computePhaseFromUTC(uint32_t utcSec) {
    if (totalCycleMs == 0) return 0;
    uint32_t cyclePosMs = (utcSec * 1000) % totalCycleMs;
    uint32_t accMs = 0;
    if (interleaveMode) {
        for (int i = 0; i < numInterleavePhases; i++) {
            accMs += interleavePhases[i].slotMs;
            if (cyclePosMs < accMs) return i;
        }
        return numInterleavePhases - 1;
    }
    for (int i = 0; i < NUM_PHASES; i++) {
        accMs += phases[i].slotMs;
        if (cyclePosMs < accMs) return i;
    }
    return NUM_PHASES - 1;
}

static const Phase* getPhaseEntry(int idx) {
    if (interleaveMode) return &interleavePhases[idx];
    return &phases[idx];
}

// ─── Per-phase RX statistics ───────────────────────────────────────────
static uint16_t rxReceived   = 0;
static uint16_t rxCrcErrors  = 0;
static uint16_t rxGarbageCount = 0;
static int32_t  rxRssiSum    = 0;
static uint16_t rxRssiCount  = 0;
static int16_t  rxRssiMin    = 0;
static float    rxLastTxLat  = 0, rxLastTxLon = 0;
static uint16_t rxLastTxSats = 0, rxLastTxFix = 0;
static uint32_t rxLastTxUtc  = 0;
static char     rxLastTxFw[8] = {0};
static bool     rxRadioInRxMode = false;
static uint32_t lastWaitingPrintMs = 0;

// ─── Time sync statistics ──────────────────────────────────────────────
#define TIME_CORRECT_THRESHOLD_SEC 5
#define TIME_STATS_INTERVAL_MS     60000
static int32_t  timeOffsetMinMs = INT32_MAX;
static int32_t  timeOffsetMaxMs = INT32_MIN;
static int64_t  timeOffsetSumMs = 0;
static uint32_t timeOffsetCount = 0;
static uint32_t timeCorrections = 0;
static uint32_t lastTimeStatsMs = 0;

// ─── Sync header cache ───────────────────────────────────────────────
static int8_t  lastSyncOffset[64];
static uint8_t syncFailCount[64] = {0};

#define TX_POWER_DBM   12.5f

// ─── Unique sequence tracking ─────────────────────────────────────────
#define MAX_SEQ 256
static bool seenSeq[MAX_SEQ];

static void resetSeenSeq() {
    memset(seenSeq, 0, sizeof(seenSeq));
}

static int countUniqueSeq() {
    int count = 0;
    for (int i = 0; i < MAX_SEQ; i++) {
        if (seenSeq[i]) count++;
    }
    return count;
}

// ─── SPI ──────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

static inline bool rfWaitBusy() {
    uint32_t busyMask = 1UL << PIN_BUSY;
    uint32_t timeout = 100000;
    while ((sio_hw->gpio_in & busyMask) && --timeout) {}
    return timeout > 0;
}

static void rfWriteCmd(const uint8_t *cmd, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer((uint8_t*)cmd, nullptr, len);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static uint32_t rfReadIrqStatus() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x01); spiRf.transfer(0x17);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[6] = {0};
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 6; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    return ((uint32_t)buf[2] << 24) | ((uint32_t)buf[3] << 16) |
           ((uint32_t)buf[4] << 8) | (uint32_t)buf[5];
}

static void rfClearIrq() {
    uint8_t cmd[6] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 6);
}

static void rfSetRx() {
    uint8_t cmd[5] = {0x02, 0x0C, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 5);
}

static void rfReadRxFifo(uint8_t *data, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00);
    spiRf.transfer(0x01);
    for (size_t i = 0; i < len; i++) data[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfClearRxFifo() {
    uint8_t cmd[] = {0x01, 0x20};
    rfWriteCmd(cmd, 2);
}

// ─── App-layer CRC-16 (CCITT 0x1021) ───────────────────────────────────
static uint16_t crc16(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int b = 0; b < 8; b++)
            crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : (crc << 1);
    }
    return crc;
}

// ─── RSSI readers ─────────────────────────────────────────────────────
static int16_t rfGetLoraRssi() {
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

    return -(int16_t)buf[4] * 5;  // tenths of dBm
}

static int16_t rfGetFlrcRssi() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02); spiRf.transfer(0x4B);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[7];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 7; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    return -(int16_t)buf[4] * 5;  // tenths of dBm
}

// ─── LoRa SNR reader ──────────────────────────────────────────────────
static int16_t rfGetLoraSnr() {
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

    // buf[3] = SNR (signed), dB = val/4
    int16_t snr = (int16_t)buf[3];
    if (snr >= 128) snr -= 256;
    return snr / 4;  // dB
}

// ─── Frequency + power setters ────────────────────────────────────────
static void rfSetFreq(float mhz) {
    uint32_t frf = (uint32_t)((mhz * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    uint8_t cmd[] = {0x02, 0x00, (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)};
    rfWriteCmd(cmd, 5);
}

static void rfSetTxPower(float dbm) {
    uint8_t powerRaw = (uint8_t)(dbm * 2.0f + 0.5f);
    uint8_t cmd[] = {0x02, 0x03, powerRaw, 0x04};
    rfWriteCmd(cmd, 4);
}

// ─── FLRC bitrate code ────────────────────────────────────────────────
static uint8_t flrcBitrateToCode(uint16_t kbps) {
    switch (kbps) {
        case 2600: return 0x00;
        case 2080: return 0x01;
        case 1300: return 0x02;
        case 1040: return 0x03;
        case 650:  return 0x04;
        case 520:  return 0x05;
        case 325:  return 0x06;
        case 260:  return 0x07;
        default:   return 0x00;
    }
}

// ─── Radio init per phase (RX mode) ───────────────────────────────────
static void rfResetAndStandby() {
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);
    { uint8_t c[] = {0x01, 0x11, 0x00, 0x00}; rfWriteCmd(c, 4); }
    delay(1);
    { uint8_t c[] = {0x01, 0x28, 0x01}; rfWriteCmd(c, 3); }
    delay(5);
}

static void rfCalibrate(float freqMHz, uint8_t rfPath) {
    uint16_t feFreq = (uint16_t)((freqMHz / 4.0f) + 0.5f);
    if (rfPath == 1) feFreq |= 0x8000;
    uint8_t c1[] = {0x01, 0x23,
                    (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
                    0, 0, 0, 0, 0, 0};
    rfWriteCmd(c1, 10);
    delay(5);
    uint8_t c2[] = {0x01, 0x22, 0x5F};
    rfWriteCmd(c2, 3);
    delay(5);
}

// ─── Channel sweep ────────────────────────────────────────────────────
static const float HF_CHANNELS[] = {
    2422.0, 2437.0, 2440.0, 2452.0, 2462.0, 2478.0, 2483.0,
};
#define NUM_HF_CHANNELS 7
static const float LF_CHANNELS[] = {
    863.0, 865.0, 867.0, 868.0, 869.5,
};
#define NUM_LF_CHANNELS 5
static bool channelSweepMode = true;
static float currentChanFreq = 0;

static float getChannelFreq(uint8_t rfPath, uint32_t utcSec) {
    if (!channelSweepMode) return 0;
    uint32_t divisor = (totalCycleSec > 0) ? totalCycleSec : 158;
    uint32_t cycle = utcSec / divisor;
    if (rfPath == 1) return HF_CHANNELS[cycle % NUM_HF_CHANNELS];
    else return LF_CHANNELS[cycle % NUM_LF_CHANNELS];
}

static void rfInitForPhaseRX(const Phase &p) {
    rfResetAndStandby();

    { uint8_t c[] = {0x02, 0x07, p.pktType}; rfWriteCmd(c, 3); }
    delay(1);

    float useFreq = p.freqMHz;
    if (channelSweepMode) {
        float chanFreq = getChannelFreq(p.rfPath, getUtcNow());
        if (chanFreq > 0) useFreq = chanFreq;
    }
    currentChanFreq = useFreq;
    rfSetFreq(useFreq);
    delay(1);

    { uint8_t c[] = {0x02, 0x01, p.rfPath, 0x00}; rfWriteCmd(c, 4); }
    delay(1);

    if (p.pktType == PT_LORA) {
        dualPrintf("LORA_CFG path=%d bw=0x%02X sf=%d freq=%.1f\n",
                   p.rfPath, p.bwCode, p.sf, useFreq);
    }

    rfCalibrate(useFreq, p.rfPath);

    if (p.pktType == PT_LORA) {
        float symTimeMs = (float)(1UL << p.sf) /
                          (float)(p.bwCode == 0x05 ? 250000 :
                                  p.bwCode == 0x06 ? 500000 :
                                  p.bwCode == 0x0D ? 203125 :
                                  p.bwCode == 0x0E ? 406250 : 812500) * 1000.0f;
        uint8_t ldro = (symTimeMs > 16.0f) ? 1 : 0;
        uint8_t byte0 = ((p.sf & 0x0F) << 4) | (p.bwCode & 0x0F);
        uint8_t byte1 = ((p.cr & 0x0F) << 4) | (ldro & 0x01);
        { uint8_t c[] = {0x02, 0x20, byte0, byte1}; rfWriteCmd(c, 4); }
        delay(1);
        { uint8_t c[] = {0x02, 0x23, 0x12}; rfWriteCmd(c, 3); }
        delay(1);
        { uint8_t flags = 0x04;
          uint8_t c[] = {0x02, 0x21, 0x00, 0x08, (uint8_t)p.pktSize, flags};
          rfWriteCmd(c, 6); }
        delay(1);
    } else {
        uint8_t brBw = flrcBitrateToCode(p.flrcBr);
        { uint8_t c[] = {0x02, 0x48, brBw, 0x15}; rfWriteCmd(c, 4); }
        delay(1);
        { uint8_t c[] = {0x02, 0x4C, 0x01, 0x12, 0xAD, 0x10, 0x1B}; rfWriteCmd(c, 7); }
        delay(1);
        { uint8_t c[] = {0x02, 0x49, 0x0C, 0x4C, 0x00, (uint8_t)p.pktSize}; rfWriteCmd(c, 6); }
        delay(1);
    }

    { uint8_t c[] = {0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10}; rfWriteCmd(c, 7); }
    delay(1);
    rfSetTxPower(TX_POWER_DBM);
    delay(1);
    { uint8_t c[] = {0x02, 0x06, 0x03}; rfWriteCmd(c, 3); }
    delay(1);
    { uint8_t c[] = {0x01, 0x12, 0x09, 0x11}; rfWriteCmd(c, 4); }
    delay(1);
    { uint8_t c[] = {0x01, 0x15, 0x09, 0x00, 0x24, 0x00, 0x00}; rfWriteCmd(c, 7); }
    delay(1);
    rfClearIrq();
    delay(1);
}

// ─── RX phase state management ────────────────────────────────────────
// M6: resetRxPhaseState does NOT reset pktSeq — it persists across phases.
static void resetRxPhaseState() {
    rxReceived   = 0;
    rxCrcErrors  = 0;
    rxGarbageCount = 0;
    rxRssiSum    = 0;
    rxRssiCount  = 0;
    rxRssiMin    = 0;
    rxLastTxLat  = 0;
    rxLastTxLon  = 0;
    rxLastTxSats = 0;
    rxLastTxFix  = 0;
    rxLastTxUtc  = 0;
    memset(rxLastTxFw, 0, sizeof(rxLastTxFw));
    resetSeenSeq();
    rxRadioInRxMode = false;
    // NOTE: pktSeq is intentionally NOT reset here — M6 requirement.
}

static void emitPhaseResult(int phaseIdx) {
    const Phase &p = *getPhaseEntry(phaseIdx);

    int unique = countUniqueSeq();
    int lost = (int)p.pktCount - unique;
    if (lost < 0) lost = 0;
    float per = (p.pktCount > 0)
              ? (float)lost / p.pktCount * 100.0f : 0.0f;
    float rssiAvg = (rxRssiCount > 0)
                  ? (float)rxRssiSum / rxRssiCount / 10.0f : 0.0f;
    float rssiMinDbm = (float)rxRssiMin / 10.0f;

    dualPrintf("PHASE_RESULT %d %s pktSize=%d rx=%u unique=%d lost=%d per=%.1f rssi_avg=%.0f rssi_min=%.0f crc_err=%u garbage=%u tx_lat=%.5f tx_lon=%.5f sats=%u fix=%u utc=%lu tx_fw=%s rx_fw=%s\n",
              phaseIdx, p.name, p.pktSize, rxReceived, unique, lost, per,
              rssiAvg, rssiMinDbm, rxCrcErrors, rxGarbageCount,
              rxLastTxLat, rxLastTxLon, rxLastTxSats, rxLastTxFix,
              (unsigned long)rxLastTxUtc,
              rxLastTxFw[0] ? rxLastTxFw : "none",
              FW_GIT_HASH);
    Serial.flush(); Serial1.flush();

    digitalWrite(PIN_LED, LOW);
}

// ─── Helper: emit harmonized 23-field PKT line ────────────────────────
// M3+M4+M5: Outputs the 23-field PKT format:
//   PKT,session_id,config_id,replicate,seq,ts_ms,rssi_dbm,snr_db,crc_ok,
//      bit_err,bytes_bad,freq_hz,mod,sf,bw_khz,cr,power_dbm,pkt_size,
//      gps_fix,gps_lat,gps_lon,gps_alt,gps_sats,gps_hdop
static void emitPktLine(
    uint32_t seq, uint32_t ts_ms,
    int16_t rssi_dbm, int16_t snr_db, int crc_ok,
    uint16_t bit_err, uint16_t bytes_bad,
    uint32_t freq_hz, const char *mod_str,
    uint8_t sf, uint32_t bw_khz, uint8_t cr,
    int power_dbm, uint16_t pkt_size,
    uint8_t gps_fix, int32_t gps_lat_e7, int32_t gps_lon_e7,
    int32_t gps_alt, uint8_t gps_sats, float gps_hdop)
{
    dualPrintf(
        "PKT,%s,%s,%u,%lu,%u,%d,%d,%d,%u,%u,%lu,%s,%u,%lu,%u,%d,%u,%u,%d,%d,%d,%u,%.1f\r\n",
        session_id,            // 1. session_id
        config_id,             // 2. config_id
        (unsigned)replicate_num, // 3. replicate
        (unsigned long)seq,    // 4. seq
        (unsigned)ts_ms,       // 5. ts_ms
        rssi_dbm,              // 6. rssi_dbm
        (int)snr_db,           // 7. snr_db
        crc_ok,                // 8. crc_ok
        (unsigned)bit_err,     // 9. bit_err
        (unsigned)bytes_bad,   // 10. bytes_bad
        (unsigned long)freq_hz, // 11. freq_hz
        mod_str,               // 12. mod
        (unsigned)sf,          // 13. sf
        (unsigned long)bw_khz, // 14. bw_khz
        (unsigned)cr,          // 15. cr
        power_dbm,             // 16. power_dbm
        (unsigned)pkt_size,    // 17. pkt_size
        (unsigned)gps_fix,     // 18. gps_fix
        (int)gps_lat_e7,       // 19. gps_lat (E7 integer)
        (int)gps_lon_e7,       // 20. gps_lon (E7 integer)
        (int)gps_alt,          // 21. gps_alt
        (unsigned)gps_sats,    // 22. gps_sats
        gps_hdop              // 23. gps_hdop
    );
}

// ─── Helper: get BW in kHz from LoRa BW code ───────────────────────────
static uint32_t loraBwCodeToKHz(uint8_t bwCode) {
    switch (bwCode) {
        case 0x05: return 250;
        case 0x06: return 500;
        case 0x0D: return 203;   // 203.125 kHz
        case 0x0E: return 406;  // 406.250 kHz
        case 0x0F: return 812;
        default:   return 812;
    }
}

// ─── Non-blocking packet poll ─────────────────────────────────────────
static void rxPacketPoll(int phaseIdx) {
    const Phase &p = *getPhaseEntry(phaseIdx);
    uint16_t pktSize = p.pktSize;
    uint8_t rxBuf[264];

    uint32_t irqPinMask = 1UL << PIN_IRQ;
    if (!(sio_hw->gpio_in & irqPinMask)) return;

    uint32_t irq = rfReadIrqStatus();

    // M7: CRC error — log with RSSI as a 23-field PKT line
    if (irq & 0x00200000) {
        rxCrcErrors++;

        // Read RSSI even on CRC failure (M7)
        int16_t rssi;
        if (p.pktType == PT_LORA) {
            rssi = rfGetLoraRssi();
        } else {
            rssi = rfGetFlrcRssi();
        }
        int16_t rssi_dbm = rssi / 10;  // convert tenths to dBm

        uint32_t ts_ms = millis();
        uint32_t freq_hz = (uint32_t)(currentChanFreq * 1000000.0f);
        const char *modStr = (p.pktType == PT_LORA) ? "LORA" : "FLRC";
        uint32_t bw_khz = (p.pktType == PT_LORA) ? loraBwCodeToKHz(p.bwCode) : 0;
        int16_t snr_db = 0;
        if (p.pktType == PT_LORA) {
            snr_db = rfGetLoraSnr();
        }

        // M7: Emit CRC-failed PKT line with RSSI
        // seq=0 (corrupt), snr=0 for FLRC, crc_ok=0, bit_err=0, bytes_bad=0
        // GPS fields all 0 (no valid GPS data from corrupt packet)
        emitPktLine(
            0,              // seq=0 (corrupt — buffer contents unreliable)
            ts_ms,
            rssi_dbm,       // RSSI populated even on CRC failure (M7)
            snr_db,         // SNR for LoRa, 0 for FLRC
            0,              // crc_ok=0
            0,              // bit_err=0
            0,              // bytes_bad=0
            freq_hz,
            modStr,
            p.sf,
            bw_khz,
            p.cr,
            (int)TX_POWER_DBM,
            pktSize,
            0, 0, 0, 0, 0, 0.0f  // GPS all zero
        );

        rfClearRxFifo();
        rfClearIrq();
        rfSetRx();
        return;
    }

    if (!(irq & 0x00040000)) {
        rfClearRxFifo();
        rfClearIrq();
        rfSetRx();
        return;
    }

    // RX_DONE — read FIFO FIRST
    size_t readLen = pktSize + 8;
    if (readLen > sizeof(rxBuf)) readLen = sizeof(rxBuf);
    rfReadRxFifo(rxBuf, readLen);

    // Sync header search
    int syncOffset = -1;
    if (phaseIdx >= 0 && phaseIdx < 64) {
        int8_t cached = lastSyncOffset[phaseIdx];
        if (cached >= 0 && cached <= (int)pktSize - 31 &&
            rxBuf[cached]   == 0xA5 && rxBuf[cached+1] == 0x5A &&
            rxBuf[cached+2] == 0x42 && rxBuf[cached+3] == 0x24) {
            syncOffset = cached;
        }
    }
    if (syncOffset < 0) {
        for (int i = 0; i <= (int)pktSize - 31; i++) {
            if (rxBuf[i] == 0xA5 && rxBuf[i+1] == 0x5A &&
                rxBuf[i+2] == 0x42 && rxBuf[i+3] == 0x24) {
                syncOffset = i;
                break;
            }
        }
    }
    if (syncOffset < 0) {
        dualPrintf("SYNC_NOT_FOUND first4=%02X%02X%02X%02X\n",
                   rxBuf[0], rxBuf[1], rxBuf[2], rxBuf[3]);
        rxGarbageCount++;
        if (phaseIdx >= 0 && phaseIdx < 64) {
            syncFailCount[phaseIdx]++;
            if (syncFailCount[phaseIdx] >= 3 && lastSyncOffset[phaseIdx] >= 0) {
                dualPrintf("SYNC_LOST phase=%d consecutive=%u cached_off=%d\n",
                           phaseIdx, syncFailCount[phaseIdx],
                           (int)lastSyncOffset[phaseIdx]);
                lastSyncOffset[phaseIdx] = -1;
            }
        }
        rfClearRxFifo();
        rfClearIrq();
        rfSetRx();
        return;
    }
    if (phaseIdx >= 0 && phaseIdx < 64) {
        if (lastSyncOffset[phaseIdx] != (int8_t)syncOffset) {
            dualPrintf("SYNC_OFFSET phase=%d off=%d prev=%d\n",
                       phaseIdx, syncOffset,
                       (int)lastSyncOffset[phaseIdx]);
        }
        lastSyncOffset[phaseIdx] = (int8_t)syncOffset;
        syncFailCount[phaseIdx] = 0;
    }
    int gpsOff = syncOffset + 4;

    // Read RSSI
    int16_t rssi;
    if (p.pktType == PT_LORA) {
        rssi = rfGetLoraRssi();
    } else {
        rssi = rfGetFlrcRssi();
    }
    rxRssiSum += rssi;
    rxRssiCount++;
    if (rxRssiCount == 1 || rssi < rxRssiMin) rxRssiMin = rssi;

    // Extract GPS data from TX payload
    int32_t pktLatE7 = (int32_t)((uint32_t)rxBuf[gpsOff+0] |
        ((uint32_t)rxBuf[gpsOff+1] << 8) | ((uint32_t)rxBuf[gpsOff+2] << 16) |
        ((uint32_t)rxBuf[gpsOff+3] << 24));
    int32_t pktLonE7 = (int32_t)((uint32_t)rxBuf[gpsOff+4] |
        ((uint32_t)rxBuf[gpsOff+5] << 8) | ((uint32_t)rxBuf[gpsOff+6] << 16) |
        ((uint32_t)rxBuf[gpsOff+7] << 24));
    uint16_t txSats = (uint16_t)rxBuf[gpsOff+8] | ((uint16_t)rxBuf[gpsOff+9] << 8);
    uint8_t  txFix  = rxBuf[gpsOff+10];
    uint32_t txUtc  = (uint32_t)rxBuf[gpsOff+11] |
        ((uint32_t)rxBuf[gpsOff+12] << 8) | ((uint32_t)rxBuf[gpsOff+13] << 16) |
        ((uint32_t)rxBuf[gpsOff+14] << 24);
    uint16_t seq = ((uint16_t)rxBuf[gpsOff+16] << 8) | rxBuf[gpsOff+17];

    // App-layer CRC-16
    uint16_t crcLen = pktSize - 6;
    if (gpsOff + crcLen + 2 > readLen) {
        dualPrintf("SYNC_OOB gpsOff=%d crcLen=%d readLen=%d — skipping\n",
                   gpsOff, crcLen, readLen);
        rxGarbageCount++;
        rfClearRxFifo();
        rfClearIrq();
        rfSetRx();
        return;
    }
    uint16_t expectedCrc = ((uint16_t)rxBuf[syncOffset + pktSize - 2] << 8)
                         | rxBuf[syncOffset + pktSize - 1];
    uint16_t actualCrc = crc16(&rxBuf[gpsOff], crcLen);
    if (expectedCrc != actualCrc) {
        rxCrcErrors++;

        // M7: Emit CRC-failed PKT line with RSSI
        int16_t rssi_dbm = rssi / 10;
        uint32_t ts_ms = millis();
        uint32_t freq_hz = (uint32_t)(currentChanFreq * 1000000.0f);
        const char *modStr = (p.pktType == PT_LORA) ? "LORA" : "FLRC";
        uint32_t bw_khz = (p.pktType == PT_LORA) ? loraBwCodeToKHz(p.bwCode) : 0;
        int16_t snr_db = 0;
        if (p.pktType == PT_LORA) {
            snr_db = rfGetLoraSnr();
        }

        emitPktLine(
            0,              // seq=0 (corrupt)
            ts_ms,
            rssi_dbm,
            snr_db,
            0,              // crc_ok=0
            0, 0,           // bit_err=0, bytes_bad=0
            freq_hz,
            modStr,
            p.sf, bw_khz, p.cr,
            (int)TX_POWER_DBM, pktSize,
            0, 0, 0, 0, 0, 0.0f
        );

        dualPrintf("APP_CRC_FAIL exp=%04X got=%04X seq=%u syncOff=%d pSz=%d\n",
                   expectedCrc, actualCrc, seq, syncOffset, pktSize);
        rfClearRxFifo();
        rfClearIrq();
        rfSetRx();
        return;
    }

    // GPS sanity check
    if (abs(pktLatE7) > 900000000L ||
        abs(pktLonE7) > 1800000000L ||
        txSats > 50) {
        dualPrintf("CRC_FALSE_POS lat=%.5f lon=%.5f sats=%u seq=%u syncOff=%d\n",
                   pktLatE7/1e7f, pktLonE7/1e7f, txSats, seq, syncOffset);
        rxGarbageCount++;
        rfClearRxFifo();
        rfClearIrq();
        rfSetRx();
        return;
    }

    if (seq < MAX_SEQ) {
        seenSeq[seq] = true;
    }

    // Extract TX firmware git hash
    memcpy(rxLastTxFw, &rxBuf[gpsOff+18], 7);
    rxLastTxFw[7] = '\0';

    rxReceived++;

    // Phase sync from TX packet
    uint8_t txPhaseId = rxBuf[gpsOff + 15];
    if (txPhaseId != currentPhase && txPhaseId < numInterleavePhases) {
        dualPrintf("PHASE_SYNC old=%d new=%d (from TX packet)\n", currentPhase, txPhaseId);
        currentPhase = txPhaseId;
        const Phase &np = *getPhaseEntry(currentPhase);
        rfInitForPhaseRX(np);
    }

    // Save GPS data for phase result
    rxLastTxLat = pktLatE7 / 1e7f;
    rxLastTxLon = pktLonE7 / 1e7f;
    rxLastTxSats = txSats;
    rxLastTxFix = txFix;
    rxLastTxUtc = txUtc;

    // Closed-loop time sync
    if (txUtc > 0 && utcOffset > 0) {
        uint32_t laptopUtc = getUtcNow();
        int32_t offset = (int32_t)(txUtc - laptopUtc);

        int32_t offsetMs = offset * 1000;
        if (offsetMs < timeOffsetMinMs) timeOffsetMinMs = offsetMs;
        if (offsetMs > timeOffsetMaxMs) timeOffsetMaxMs = offsetMs;
        timeOffsetSumMs += offsetMs;
        timeOffsetCount++;

        if (offset > TIME_CORRECT_THRESHOLD_SEC ||
            offset < -TIME_CORRECT_THRESHOLD_SEC) {
            uint32_t oldOffset = utcOffset;
            utcOffset = utcOffset + (uint32_t)offset;
            timeCorrections++;
            dualPrintf("TIME_CORRECT old_offset=%lu new_offset=%lu delta=%ld\n",
                          (unsigned long)oldOffset,
                          (unsigned long)utcOffset,
                          (long)offset);
        }
    }

    // BER analysis using PRBS-15 verification
    uint16_t bit_err = 0;
    uint16_t bytes_bad = 0;
    if (prbs_enabled && pktSize > PRBS_START + 2) {
        size_t payloadLen = pktSize - PRBS_START - 2;
        // PRBS seed = seq (matches TX's seqInPhase)
        uint32_t prbsSeed = (uint32_t)seq;
        bit_err = prbs15_verify(&rxBuf[syncOffset + PRBS_START], payloadLen,
                                prbsSeed, &bytes_bad);
    }

    // M6: Increment non-resetting uint32 seq counter
    pktSeq++;

    // M3+M4+M5: Emit 23-field harmonized PKT line for successful packet
    int16_t rssi_dbm = rssi / 10;  // tenths → dBm
    int16_t snr_db = 0;
    if (p.pktType == PT_LORA) {
        snr_db = rfGetLoraSnr();
    }
    uint32_t ts_ms = millis();
    uint32_t freq_hz = (uint32_t)(currentChanFreq * 1000000.0f);
    const char *modStr = (p.pktType == PT_LORA) ? "LORA" : "FLRC";
    uint32_t bw_khz = (p.pktType == PT_LORA) ? loraBwCodeToKHz(p.bwCode) : 0;

    emitPktLine(
        pktSeq,         // M6: non-resetting uint32 seq counter
        ts_ms,
        rssi_dbm,
        snr_db,
        1,              // crc_ok=1
        bit_err,        // bit_err (from PRBS-15 verification)
        bytes_bad,      // bytes_bad (from PRBS-15 verification)
        freq_hz,
        modStr,
        p.sf, bw_khz, p.cr,
        (int)TX_POWER_DBM, pktSize,
        txFix, pktLatE7, pktLonE7,
        (int32_t)0,     // gps_alt (not in TX payload, 0)
        txSats,
        0.0f            // gps_hdop (not in TX payload, 0.0)
    );

    // Debug output for first few packets
    if (rxReceived <= 3) {
        dualPrintf("PKT_DEBUG rx=%d seq=%u pktSeq=%lu rssi=%d phase=%d rx_ms=%lu tx_lat=%.5f tx_lon=%.5f sats=%u fix=%u utc=%lu tx_fw=%s\n",
                      rxReceived, seq, (unsigned long)pktSeq, rssi / 10, phaseIdx,
                      (unsigned long)millis(),
                      rxLastTxLat, rxLastTxLon, txSats, txFix, (unsigned long)txUtc,
                      rxLastTxFw);
        dualPrintf("BER seq=%u bit_err=%u bytes_bad=%u prbs=%s\n",
                   seq, bit_err, bytes_bad,
                   prbs_enabled ? "ON" : "OFF");
    }

    digitalWrite(PIN_LED, (rxReceived & 1) ? HIGH : LOW);

    rfClearRxFifo();
    rfClearIrq();
    rfSetRx();
}

// ─── Setup ────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial1.setTX(12);
    Serial1.setRX(13);
    Serial1.begin(115200);
    delay(2000);

    // M1: Boot banner with FW_HASH
    printBootBanner();

    pinMode(PIN_CS, OUTPUT);
    pinMode(PIN_RST, OUTPUT);
    pinMode(PIN_IRQ, INPUT);
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    digitalWrite(PIN_RST, HIGH);
    digitalWrite(PIN_LED, LOW);

    spiRf.begin();

    // Init sync offset cache + build interleave table
    for (int i = 0; i < 64; i++) lastSyncOffset[i] = -1;
    buildInterleaveTable();

    // Compute total cycle time
    totalCycleSec = 0;
    totalCycleMs = 0;
    if (interleaveMode) {
        for (int i = 0; i < numInterleavePhases; i++) {
            totalCycleSec += interleavePhases[i].slotMs / 1000;
            totalCycleMs += interleavePhases[i].slotMs;
        }
    } else {
        for (int i = 0; i < NUM_PHASES; i++) {
            totalCycleSec += phases[i].slotMs / 1000;
            totalCycleMs += phases[i].slotMs;
        }
    }

    dualPrintf("=== HARMONIZED RX V1 (23-field PKT) ===\n");
    dualPrintf("FW_HASH=%s  Phases: %d  Cycle: %lus  Interleave: %d phases\n",
                FW_GIT_HASH, NUM_PHASES, (unsigned long)totalCycleSec,
                numInterleavePhases);
    dualPrintf("Commands: SESSION <id>, CONFIG <id> <n>, SET_TIME <ts>, FW_QUERY, PRBS ON|OFF\n");
    for (int i = 0; i < NUM_PHASES; i++) {
        dualPrintf("  [%2d] %-16s %s %.0fMHz %dpkts %ds %dB\n",
                      i, phases[i].name,
                      phases[i].pktType == PT_LORA ? "LoRa" : "FLRC",
                      phases[i].freqMHz,
                      phases[i].pktCount, phases[i].slotMs / 1000,
                      phases[i].pktSize);
    }

    dualPrintf("=== AUTO START IN 8s ===\n");
    for (int i = 8; i > 0; i--) {
        dualPrintf("  Starting in %d...\n", i);
        digitalWrite(PIN_LED, HIGH); delay(400);
        digitalWrite(PIN_LED, LOW);  delay(600);
    }
    dualPrintf("=== STARTING HARMONIZED RX ===\n");
}

// ─── Main loop (UTC-driven, non-blocking) ─────────────────────────────
void loop() {
    // CDC watchdog
    if (lastCdcOutputMs > 0 && (millis() - lastCdcOutputMs) > CDC_WATCHDOG_MS) {
        dualPrintf("CDC_WATCHDOG_TIMEOUT\n");
        Serial.end();
        delay(100);
        Serial.begin(115200);
        delay(100);
        lastCdcOutputMs = millis();
        dualPrintf("CDC_REINIT_DONE\n");
    }

    // Check for serial commands (SESSION, CONFIG, SET_TIME, etc.)
    checkSerialCommands();

    // Wait for UTC time sync
    if (utcOffset == 0) {
        if (lastWaitingPrintMs == 0 || (millis() - lastWaitingPrintMs) >= 5000) {
            dualPrintf("WAITING_FOR_TIME_SYNC uptime=%lu\n", (unsigned long)millis());
            lastWaitingPrintMs = millis();
        }
        delay(100);
        return;
    }

    // TIME_STATS every 60 seconds
    if (timeOffsetCount > 0) {
        if (lastTimeStatsMs == 0) lastTimeStatsMs = millis();
        if ((millis() - lastTimeStatsMs) >= TIME_STATS_INTERVAL_MS) {
            int32_t avgMs = (int32_t)(timeOffsetSumMs / (int64_t)timeOffsetCount);
            dualPrintf("TIME_STATS min=%ldms max=%ldms avg=%ldms corrections=%u\n",
                          (long)timeOffsetMinMs,
                          (long)timeOffsetMaxMs,
                          (long)avgMs,
                          timeCorrections);
            lastTimeStatsMs = millis();
        }
    }

    // Compute current phase from UTC
    int phase = computePhaseFromUTC(getUtcNow());

    // Phase change detection
    if (phase != currentPhase) {
        if (currentPhase >= 0) {
            emitPhaseResult(currentPhase);
        }

        uint32_t guardMs = 500;
        if (currentPhase >= 0 && phase < numInterleavePhases) {
            if (interleavePhases[currentPhase].pktType != interleavePhases[phase].pktType ||
                interleavePhases[currentPhase].rfPath   != interleavePhases[phase].rfPath) {
                guardMs = 1000;
            }
        }
        dualPrintf("PHASE_GUARD %lu\n", (unsigned long)guardMs);

        currentPhase = phase;
        resetRxPhaseState();
        phaseStartMs = millis();

        const Phase *ph = getPhaseEntry(phase);
        rfInitForPhaseRX(*ph);
        delay(50);

        rfClearRxFifo();
        rfClearIrq();
        rfSetRx();
        rxRadioInRxMode = true;

        if (ph->pktCount == 0) {
            dualPrintf("PHASE_START %d %s SKIP pktSize=%d\n", phase, ph->name, ph->pktSize);
        } else {
            dualPrintf("PHASE_START %d %s pktSize=%d\n", phase, ph->name, ph->pktSize);
        }
        return;
    }

    // Poll for one packet (non-blocking)
    rxPacketPoll(phase);
}