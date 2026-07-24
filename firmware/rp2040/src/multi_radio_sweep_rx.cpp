/*
 * multi_radio_sweep_rx.cpp — Standalone RX for multi-radio sweep (14 phases)
 *
 * Matching RX counterpart to multi_radio_sweep_gps.cpp (GPS TX).
 * UTC-driven: RX computes its phase from UTC every loop() iteration,
 * exactly like TX. UTC is bootstrapped via "SET_TIME <unix_ts>" from the
 * laptop (NTP-synced) over USB serial. Both boards use the same phase
 * schedule and the same Unix-epoch-modulo-cycle algorithm, so they always
 * agree on which phase they are in as long as both have UTC time.
 *
 * The loop() is NON-BLOCKING: it polls for ONE packet per call and returns
 * immediately, so phase changes are detected within a few ms.
 *
 * Key fix from multi_radio_sweep.cpp: tracks UNIQUE sequence numbers per phase
 * using a bitmap, fixing the bug where "lost" counted 4 billion.
 *
 * Output on both USB Serial and UART GP12/GP13 (ESP32 bridge).
 *
 * Phase schedule matches TX (one full cycle ≈ 202 s):
 *   0-2:  HF 2440 LoRa (SF7/SF9/SF12)
 *   3-6:  HF 2440 FLRC (2600/1300/650/325)
 *   7-9:  LF 868  LoRa (SF7/SF9/SF12)
 *  10-13: LF 868  FLRC (2600/1300/650/325)
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13  LED=GP25
 */

#include <Arduino.h>
#include <SPI.h>
#include <stdarg.h>
#include <string.h>

// ─── Dual serial output (USB CDC + UART1→ESP32 bridge) ───────────────
static uint32_t lastCdcOutputMs = 0;
#define CDC_WATCHDOG_MS 30000

static void dualPrintf(const char* fmt, ...) {
    char buf[300];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.print(buf);
    Serial.flush();
    Serial1.print(buf);
    lastCdcOutputMs = millis();
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

// ─── Phase table (must match TX exactly) ─────────────────────────────
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
} Phase;

static const Phase phases[] = {
    // ── 2.4 GHz HF path ──
    {"HF-LoRa-SF7",   PT_LORA, 2440.0, 1,  7, 0x0F, 1,    0,  50, 15000},
    {"HF-LoRa-SF9",   PT_LORA, 2440.0, 1,  9, 0x0F, 1,    0,  50, 15000},
    {"HF-LoRa-SF12",  PT_LORA, 2440.0, 1, 12, 0x0F, 1,    0,  30, 30000},
    {"HF-FLRC-2600",  PT_FLRC, 2440.0, 1,  0, 0x00, 0, 2600, 200,  8000},
    {"HF-FLRC-1300",  PT_FLRC, 2440.0, 1,  0, 0x00, 0, 1300, 200,  8000},
    {"HF-FLRC-650",   PT_FLRC, 2440.0, 1,  0, 0x00, 0,  650, 200,  8000},
    {"HF-FLRC-325",   PT_FLRC, 2440.0, 1,  0, 0x00, 0,  325, 200,  8000},
    // ── 868 MHz LF path ──
    {"LF-LoRa-SF7",   PT_LORA,  868.0, 0,  7, 0x05, 1,    0,  50,  8000},
    {"LF-LoRa-SF9",   PT_LORA,  868.0, 0,  9, 0x05, 1,    0,  50, 20000},
    {"LF-LoRa-SF12",  PT_LORA,  868.0, 0, 12, 0x05, 1,    0,  20, 50000},
    // ── 868 MHz LF FLRC path ──
    {"LF-FLRC-2600",  PT_FLRC,  868.0, 0,  0, 0x00, 0, 2600, 200,  8000},
    {"LF-FLRC-1300",  PT_FLRC,  868.0, 0,  0, 0x00, 0, 1300, 200,  8000},
    {"LF-FLRC-650",   PT_FLRC,  868.0, 0,  0, 0x00, 0,  650, 200,  8000},
    {"LF-FLRC-325",   PT_FLRC,  868.0, 0,  0, 0x00, 0,  325, 200,  8000},
};
static const int NUM_PHASES = sizeof(phases) / sizeof(phases[0]);

// ─── Laptop time sync (bootstrap fix) ─────────────────────────────────
// RX has no GPS. If it boots on the wrong phase, it listens on the wrong
// frequency, never receives TX packets, and can't correct itself.
// The laptop (NTP-synced) sends "SET_TIME <unix_timestamp>\n" over USB
// serial at capture start. RX uses this as its UTC clock bootstrap.
static uint32_t utcOffset = 0;  // offset from millis()/1000 to UTC seconds

static uint32_t getUtcNow() {
    return millis() / 1000 + utcOffset;
}

// Non-blocking: check Serial for SET_TIME command. Called from loop().
static void checkSerialTimeSync() {
    if (!Serial.available()) return;

    // Read available characters into a line buffer
    static char syncBuf[64];
    static int syncLen = 0;

    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (syncLen > 0) {
                syncBuf[syncLen] = '\0';
                // Parse "SET_TIME <unix_timestamp>"
                if (strncmp(syncBuf, "SET_TIME ", 9) == 0) {
                    uint32_t ts = (uint32_t)strtoul(syncBuf + 9, nullptr, 10);
                    if (ts > 0) {
                        utcOffset = ts - millis() / 1000;
                        dualPrintf("TIME_SYNCED utc=%lu offset=%ld\n",
                                      (unsigned long)getUtcNow(),
                                      (long)utcOffset);
                    }
                }
                syncLen = 0;
            }
        } else {
            if (syncLen < (int)sizeof(syncBuf) - 1) {
                syncBuf[syncLen++] = c;
            }
        }
    }
}

// ─── Phase drift correction state ────────────────────────────────────
// RX has no GPS — uses millis(). When a TX packet arrives with utc_seconds,
// we compute TX's phase from UTC and jump RX to match, eliminating drift.
// If laptop time sync is available (utcOffset > 0), we use getUtcNow()
// instead of raw millis() for initial phase selection, avoiding the
// chicken-and-egg bootstrap problem.
static uint32_t totalCycleSec = 0;
static int currentPhase = -1;       // -1 = not started yet (forces init on first loop)
static uint32_t phaseStartMs = 0;

static int computePhaseFromUTC(uint32_t utcSec) {
    // Both TX and RX use full Unix epoch % cycleSec — same clock domain.
    // TX gets Unix from GPS RMC (date+time→epoch). RX gets Unix from laptop SET_TIME.
    uint32_t cyclePos = utcSec % totalCycleSec;
    uint32_t acc = 0;
    for (int i = 0; i < NUM_PHASES; i++) {
        acc += phases[i].slotMs / 1000;
        if (cyclePos < acc) return i;
    }
    return NUM_PHASES - 1;  // fallback
}

// ─── Non-blocking RX state (UTC-driven loop) ─────────────────────────
// Per-phase statistics, tracked across multiple loop() calls.
// Reset when phase changes (via resetRxPhaseState()).
static uint16_t rxReceived   = 0;
static uint16_t rxCrcErrors  = 0;
static int32_t  rxRssiSum    = 0;
static uint16_t rxRssiCount  = 0;
static int16_t  rxRssiMin    = 0;       // most negative = weakest (tenths dBm)
static float    rxLastTxLat  = 0, rxLastTxLon = 0;
static uint16_t rxLastTxSats = 0, rxLastTxFix = 0;
static uint32_t rxLastTxUtc  = 0;
static bool     rxRadioInRxMode = false;   // tracks whether radio is listening
static uint32_t lastWaitingPrintMs = 0;    // throttle for WAITING_FOR_TIME_SYNC

#define TX_POWER_DBM   12.5f   // only for init, not used for RX
#define LORA_PKT_SIZE  127
#define FLRC_PKT_SIZE  255

// ─── Unique sequence tracking ────────────────────────────────────────
// Max pktCount is 200, so 256-entry bitmap covers all seq values
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

// ─── SPI ─────────────────────────────────────────────────────────────
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
    spiRf.transfer(0x01);  // READ_RX_FIFO (LR2021 opcode = 0x01, NOT 0x03)
    for (size_t i = 0; i < len; i++) data[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfClearRxFifo() {
    uint8_t cmd[] = {0x01, 0x20};
    rfWriteCmd(cmd, 2);
}

// ─── RSSI readers ────────────────────────────────────────────────────
// GET_LORA_PACKET_STATUS (0x022A) response after 2 status bytes:
//   buf[2] = rssiSync (packet RSSI)  → dBm = -val / 2
//   buf[3] = SNR (signed)            → dB = val<128 ? val/4 : (val-256)/4
//   (verified against RadioLib SX128x source + lr2021-complete-learnings)
static int16_t rfGetLoraRssi() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02); spiRf.transfer(0x2A);  // GET_LORA_PACKET_STATUS
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[8];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 8; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    // buf[2] = rssiSync, dBm = -val/2. In tenths of dBm: -val * 5
    // Debug: dump raw bytes for first few LoRa packets
    static uint8_t loraDumpCount = 0;
    if (loraDumpCount < 5) {
        loraDumpCount++;
        dualPrintf("LORA_STATUS: %d %d %d %d %d %d %d %d\n",
                   buf[0], buf[1], buf[2], buf[3], buf[4], buf[5], buf[6], buf[7]);
    }

    // LR2021 GET_LORA_PACKET_STATUS: buf[4] has RSSI avg (proven working in this firmware)
    return -(int16_t)buf[4] * 5;  // tenths of dBm
}

// GET_FLRC_PACKET_STATUS (0x024B) — LR2021 returns 7 bytes:
//   [0] stat_msb  [1] stat_lsb  (status prefix)
//   [2] pktLen_msb  [3] pktLen_lsb
//   [4] rssiAvg (7 MSBs of 9-bit value)
//   [5] rssiSync (7 MSBs of 9-bit value)
//   [6] flags: bits[3:2]=rssiAvg LSB, bit[0]=rssiSync LSB, bits[7:4]=syncWordNum
// Correct conversion (verified in flrc_range_rx_auto.cpp, -60 dBm at 30cm):
//   raw = (buf[4] << 1) | ((buf[6] & 0x04) >> 2)
//   rssiAvg = raw / -2.0  → dBm (float)
static int16_t rfGetFlrcRssi() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02); spiRf.transfer(0x4B);  // GET_FLRC_PACKET_STATUS
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    // Response: [stat_msb][stat_lsb][pktLen_msb][pktLen_lsb][rssiAvg][rssiSync][flags]
    uint8_t buf[7];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 7; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    // RSSI: buf[4] = rssiAvg (7 MSBs). Formula: dBm = -val / 2.0
    // Same as LoRa (buf[2] / -2.0). The 9-bit assembly with <<1 was WRONG —
    // it doubled the value: (107<<1)/-2 = -107 instead of -107/2 = -53.5 dBm.
    // Return in tenths of dBm: -val * 5 (matches LoRa convention)
    return -(int16_t)buf[4] * 5;
}

// ─── Frequency + power setters ───────────────────────────────────────
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

// ─── FLRC bitrate code ───────────────────────────────────────────────
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

// ─── Radio init per phase (RX mode) ──────────────────────────────────
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
    // CALIB_FRONT_END (0x0123) — MANDATORY before RX
    uint16_t feFreq = (uint16_t)((freqMHz / 4.0f) + 0.5f);
    if (rfPath == 1) feFreq |= 0x8000;  // HF path
    uint8_t c1[] = {0x01, 0x23,
                    (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
                    0, 0, 0, 0, 0, 0};
    rfWriteCmd(c1, 10);
    delay(5);
    // CALIBRATE (0x0122) mask 0x5F (NOT 0x6F)
    uint8_t c2[] = {0x01, 0x22, 0x5F};
    rfWriteCmd(c2, 3);
    delay(5);
}

static void rfInitForPhaseRX(const Phase &p) {
    rfResetAndStandby();

    // SET_PACKET_TYPE
    { uint8_t c[] = {0x02, 0x07, p.pktType}; rfWriteCmd(c, 3); }
    delay(1);

    // SET_RF_FREQUENCY
    rfSetFreq(p.freqMHz);
    delay(1);

    // SET_RX_PATH — MANDATORY: HF=1, LF=0
    { uint8_t c[] = {0x02, 0x01, p.rfPath, 0x00}; rfWriteCmd(c, 4); }
    delay(1);

    // Calibrate (MANDATORY for RX)
    rfCalibrate(p.freqMHz, p.rfPath);

    if (p.pktType == PT_LORA) {
        // SET_LORA_MODULATION_PARAMS (0x0220)
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

        // SET_LORA_SYNCWORD
        { uint8_t c[] = {0x02, 0x23, 0x12}; rfWriteCmd(c, 3); }
        delay(1);

        // SET_LORA_PACKET_PARAMS
        { uint8_t flags = 0x04;
          uint8_t c[] = {0x02, 0x21, 0x00, 0x08, LORA_PKT_SIZE, flags};
          rfWriteCmd(c, 6); }
        delay(1);

    } else {
        // SET_FLRC_MODULATION_PARAMS (0x0248)
        uint8_t brBw = flrcBitrateToCode(p.flrcBr);
        { uint8_t c[] = {0x02, 0x48, brBw, 0x25}; rfWriteCmd(c, 4); }
        delay(1);

        // SET_FLRC_SYNC_WORD (0x024C)
        { uint8_t c[] = {0x02, 0x4C, 0x01, 0x12, 0xAD, 0x10, 0x1B}; rfWriteCmd(c, 7); }
        delay(1);

        // SET_FLRC_PACKET_PARAMS (0x0249)
        { uint8_t c[] = {0x02, 0x49, 0x0C, 0x4C, 0x00, FLRC_PKT_SIZE}; rfWriteCmd(c, 6); }
        delay(1);
    }

    // SET_PA_CONFIG
    { uint8_t c[] = {0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10}; rfWriteCmd(c, 7); }
    delay(1);

    // SET_TX_PARAMS
    rfSetTxPower(TX_POWER_DBM);
    delay(1);

    // SET_RX_TX_FALLBACK
    { uint8_t c[] = {0x02, 0x06, 0x03}; rfWriteCmd(c, 3); }
    delay(1);

    // SET_DIO_FUNCTION
    { uint8_t c[] = {0x01, 0x12, 0x09, 0x11}; rfWriteCmd(c, 4); }
    delay(1);

    // IRQ: RX_DONE (bit 18) + CRC_ERROR (bit 22) = 0x00240000
    { uint8_t c[] = {0x01, 0x15, 0x09, 0x00, 0x24, 0x00, 0x00}; rfWriteCmd(c, 7); }
    delay(1);

    rfClearIrq();
    delay(1);
}

// ─── RX phase state management (UTC-driven, non-blocking) ────────────

// Reset per-phase RX statistics. Called on phase change.
static void resetRxPhaseState() {
    rxReceived   = 0;
    rxCrcErrors  = 0;
    rxRssiSum    = 0;
    rxRssiCount  = 0;
    rxRssiMin    = 0;
    rxLastTxLat  = 0;
    rxLastTxLon  = 0;
    rxLastTxSats = 0;
    rxLastTxFix  = 0;
    rxLastTxUtc  = 0;
    resetSeenSeq();
    rxRadioInRxMode = false;
}

// Emit PHASE_RESULT summary for the phase we're leaving.
static void emitPhaseResult(int phaseIdx) {
    const Phase &p = phases[phaseIdx];

    int unique = countUniqueSeq();
    int lost = (int)p.pktCount - unique;
    if (lost < 0) lost = 0;
    float per = (p.pktCount > 0)
              ? (float)lost / p.pktCount * 100.0f : 0.0f;
    float rssiAvg = (rxRssiCount > 0)
                  ? (float)rxRssiSum / rxRssiCount / 10.0f : 0.0f;
    float rssiMinDbm = (float)rxRssiMin / 10.0f;

    dualPrintf("PHASE_RESULT %d %s rx=%u unique=%d lost=%d per=%.1f rssi_avg=%.0f rssi_min=%.0f crc_err=%u tx_lat=%.5f tx_lon=%.5f sats=%u fix=%u utc=%lu\n",
                  phaseIdx, p.name, rxReceived, unique, lost, per,
                  rssiAvg, rssiMinDbm, rxCrcErrors,
                  rxLastTxLat, rxLastTxLon, rxLastTxSats, rxLastTxFix,
                  (unsigned long)rxLastTxUtc);
    Serial.flush(); Serial1.flush();

    digitalWrite(PIN_LED, LOW);
}

// Non-blocking packet poll: checks IRQ pin ONCE, reads ONE packet if
// RX_DONE. Returns immediately whether or not a packet was received.
// Per-phase statistics are tracked in file-scope state (rxReceived etc.).
static void rxPacketPoll(int phaseIdx) {
    const Phase &p = phases[phaseIdx];
    uint16_t pktSize = (p.pktType == PT_LORA) ? LORA_PKT_SIZE : FLRC_PKT_SIZE;
    uint8_t rxBuf[256];

    uint32_t irqPinMask = 1UL << PIN_IRQ;

    // No IRQ pin asserted → nothing to do, return immediately
    if (!(sio_hw->gpio_in & irqPinMask)) return;

    uint32_t irq = rfReadIrqStatus();

    if (irq & 0x00200000) {
        // CRC error
        rxCrcErrors++;
        rfClearIrq();
        rfSetRx();
        return;
    }

    if (!(irq & 0x00040000)) {
        // Other IRQ source — clear and re-arm RX
        rfClearIrq();
        rfSetRx();
        return;
    }

    // RX_DONE — read FIFO FIRST (before RSSI), matching proven code.
    // GET_PACKET_STATUS may reset FIFO read pointer.
    rfReadRxFifo(rxBuf, pktSize);

    // Now read RSSI
    int16_t rssi;
    if (p.pktType == PT_LORA) {
        rssi = rfGetLoraRssi();
    } else {
        rssi = rfGetFlrcRssi();
    }
    rxRssiSum += rssi;
    rxRssiCount++;
    if (rxRssiCount == 1 || rssi < rxRssiMin) rxRssiMin = rssi;

    // Extract GPS data from TX payload — MUST MATCH embedGPS() in TX
    // TX packet layout (with 4-byte sync header at bytes 0-3):
    //   bytes 0-3:   sync header (0xA5 0x5A 0x42 0x24)
    //   bytes 4-7:   latE7 (int32 LE)
    //   bytes 8-11:  lonE7 (int32 LE)
    //   bytes 12-13: sats  (uint16 LE)
    //   byte  14:    fixQ  (uint8)
    //   bytes 15-18: utcSec (uint32 LE)
    //   byte  19:    phaseId (uint8)
    //   bytes 20-21: seq   (uint16 BE)
    //
    // FLRC hardware strips the sync word before FIFO:
    //   LoRa FIFO starts at TX byte 0 (sync header present)
    //   FLRC FIFO starts at TX byte 4 (sync header stripped)
    // Application sync header (0xA5 0x5A 0x42 0x24) is part of TX payload,
    // NOT the hardware sync word. Both LoRa and FLRC FIFO contain it at bytes 0-3.
    // Hardware sync word (FLRC: 0x12AD10B1B) is stripped by chip before FIFO.
    int gpsOff = 4;  // skip app sync header in both modes
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
    // Sequence from bytes (gpsOff+16)-(gpsOff+17) (uint16 BE)
    uint16_t seq = ((uint16_t)rxBuf[gpsOff+16] << 8) | rxBuf[gpsOff+17];
    if (seq < MAX_SEQ) {
        seenSeq[seq] = true;
    }
    rxReceived++;

    // Convert E7 to float degrees
    float txLat = pktLatE7 / 1e7f;
    float txLon = pktLonE7 / 1e7f;

    // Save for phase result
    rxLastTxLat = txLat; rxLastTxLon = txLon;
    rxLastTxSats = txSats; rxLastTxFix = txFix;
    rxLastTxUtc = txUtc;

    // ─── Time difference logging (measurement only) ────
    // GPS time from TX is NOT used for RX phase control.
    // Laptop time (SET_TIME) is the primary clock.
    if (txUtc > 0 && utcOffset > 0) {
        uint32_t laptopUtc = getUtcNow();
        dualPrintf("TIME_DIFF gps_utc=%lu laptop_utc=%lu\n",
                      (unsigned long)txUtc,
                      (unsigned long)laptopUtc);
    }

    // Log first few packets per phase for debugging
    if (rxReceived <= 3) {
        // Raw byte dump for first FLRC packet — 32 bytes to find sync header offset
        if (p.pktType != PT_LORA && rxReceived == 1) {
            dualPrintf("FLRC_RAW32: %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d\n",
                       rxBuf[0], rxBuf[1], rxBuf[2], rxBuf[3],
                       rxBuf[4], rxBuf[5], rxBuf[6], rxBuf[7],
                       rxBuf[8], rxBuf[9], rxBuf[10], rxBuf[11],
                       rxBuf[12], rxBuf[13], rxBuf[14], rxBuf[15],
                       rxBuf[16], rxBuf[17], rxBuf[18], rxBuf[19],
                       rxBuf[20], rxBuf[21], rxBuf[22], rxBuf[23],
                       rxBuf[24], rxBuf[25], rxBuf[26], rxBuf[27],
                       rxBuf[28], rxBuf[29], rxBuf[30], rxBuf[31]);
        }
        if (p.pktType == PT_LORA && rxReceived == 1) {
            dualPrintf("LORA_RAW: %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d %d\n",
                       rxBuf[0], rxBuf[1], rxBuf[2], rxBuf[3],
                       rxBuf[4], rxBuf[5], rxBuf[6], rxBuf[7],
                       rxBuf[8], rxBuf[9], rxBuf[10], rxBuf[11],
                       rxBuf[12], rxBuf[13], rxBuf[14], rxBuf[15],
                       rxBuf[16], rxBuf[17]);
        }
        dualPrintf("PKT rx=%d seq=%u rssi=%d phase=%d rx_ms=%lu tx_lat=%.5f tx_lon=%.5f sats=%u fix=%u utc=%lu\n",
                      rxReceived, seq, rssi / 10, phaseIdx,
                      (unsigned long)millis(),
                      txLat, txLon, txSats, txFix, (unsigned long)txUtc);
    }

    digitalWrite(PIN_LED, (rxReceived & 1) ? HIGH : LOW);

    rfClearRxFifo();
    rfClearIrq();
    rfSetRx();
}

// ─── Setup ───────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial1.setTX(12);  // GP12 = UART TX → ESP32 bridge
    Serial1.setRX(13);  // GP13 = UART RX ← ESP32 bridge
    Serial1.begin(115200);
    delay(2000);

    pinMode(PIN_CS, OUTPUT);
    pinMode(PIN_RST, OUTPUT);
    pinMode(PIN_IRQ, INPUT);
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    digitalWrite(PIN_RST, HIGH);
    digitalWrite(PIN_LED, LOW);

    spiRf.begin();

    // Compute total cycle seconds for phase drift correction
    totalCycleSec = 0;
    for (int i = 0; i < NUM_PHASES; i++) {
        totalCycleSec += phases[i].slotMs / 1000;
    }

    dualPrintf("=== MULTI-RADIO RX SWEEP (14 phases) ===\n");
    dualPrintf("Phases: %d  Cycle: %lus\n", NUM_PHASES, (unsigned long)totalCycleSec);
    for (int i = 0; i < NUM_PHASES; i++) {
        dualPrintf("  [%2d] %-16s %s %.0fMHz %dpkts %ds\n",
                      i, phases[i].name,
                      phases[i].pktType == PT_LORA ? "LoRa" : "FLRC",
                      phases[i].freqMHz,
                      phases[i].pktCount, phases[i].slotMs / 1000);
    }

    dualPrintf("=== AUTO START IN 8s ===\n");
    // LED blink countdown
    for (int i = 8; i > 0; i--) {
        dualPrintf("  Starting in %d...\n", i);
        digitalWrite(PIN_LED, HIGH); delay(400);
        digitalWrite(PIN_LED, LOW);  delay(600);
    }
    dualPrintf("=== STARTING RX SWEEP ===\n");
}

// ─── Main loop (UTC-driven, non-blocking) ────────────────────────────
// Computes phase from UTC every iteration, just like TX.
// Never blocks for more than a few ms — returns to loop() frequently
// so phase changes are detected immediately.
void loop() {
    // CDC watchdog — reinitialize USB if no output for 30s
    if (lastCdcOutputMs > 0 && (millis() - lastCdcOutputMs) > CDC_WATCHDOG_MS) {
        dualPrintf("CDC_WATCHDOG_TIMEOUT\n");
        Serial.end();
        delay(100);
        Serial.begin(115200);
        delay(100);
        lastCdcOutputMs = millis();
        dualPrintf("CDC_REINIT_DONE\n");
    }

    // Check for laptop time sync command (SET_TIME)
    checkSerialTimeSync();

    // If we don't have UTC time yet, wait for it
    if (utcOffset == 0) {
        if (lastWaitingPrintMs == 0 || (millis() - lastWaitingPrintMs) >= 5000) {
            dualPrintf("WAITING_FOR_TIME_SYNC uptime=%lu\n", (unsigned long)millis());
            lastWaitingPrintMs = millis();
        }
        delay(100);
        return;
    }

    // Compute current phase from UTC — same algorithm as TX
    int phase = computePhaseFromUTC(getUtcNow());

    // Phase change detection — re-init radio and reset state
    if (phase != currentPhase) {
        // Emit PHASE_RESULT for the phase we're leaving
        if (currentPhase >= 0 && currentPhase < NUM_PHASES) {
            emitPhaseResult(currentPhase);
        }

        dualPrintf("PHASE_GUARD 500\n");

        currentPhase = phase;
        resetRxPhaseState();
        phaseStartMs = millis();

        // Re-init radio for new phase
        rfInitForPhaseRX(phases[phase]);
        delay(50);

        // Put radio into RX mode (continuous, no timeout)
        rfClearRxFifo();
        rfClearIrq();
        rfSetRx();
        rxRadioInRxMode = true;

        dualPrintf("PHASE_START %d %s\n", phase, phases[phase].name);
        return;  // return immediately — next loop() will start polling
    }

    // Still in the same phase — poll for ONE packet (non-blocking)
    rxPacketPoll(phase);

    // No delay needed — rxPacketPoll returns instantly if no IRQ.
    // loop() is called again immediately, recomputing phase from UTC.
}
