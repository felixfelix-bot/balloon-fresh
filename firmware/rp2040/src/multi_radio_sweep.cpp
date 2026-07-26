/*
 * multi_radio_sweep.cpp — Dual-radio characterization firmware
 *
 * Walk-around TX: battery powered, auto-cycles ALL configs, loop forever.
 * Laptop RX: serial output, cycles matching configs.
 *
 * One binary, two roles via -D TX_ROLE or -D RX_ROLE.
 * Both boards auto-start after 8s countdown.
 * Each phase has fixed time budget — TX and RX stay in sync.
 *
 * Phase schedule (one full cycle ≈ 2 min):
 *   0: HF 2440 LoRa SF7  BW812  — 50 pkts,  5s slot
 *   1: HF 2440 LoRa SF9  BW812  — 50 pkts,  8s slot
 *   2: HF 2440 LoRa SF12 BW812  — 30 pkts, 25s slot
 *   3: HF 2440 FLRC 2600        — 200 pkts, 3s slot
 *   4: HF 2440 FLRC 1300        — 200 pkts, 3s slot
 *   5: HF 2440 FLRC 650         — 200 pkts, 3s slot
 *   6: HF 2440 FLRC 325         — 200 pkts, 3s slot
 *   7: LF 868  LoRa SF7  BW250  — 50 pkts,  8s slot
 *   8: LF 868  LoRa SF9  BW250  — 50 pkts, 20s slot
 *   9: LF 868  LoRa SF12 BW250  — 20 pkts, 50s slot
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13  LED=GP25
 */

#include <Arduino.h>
#include <SPI.h>
#include <stdarg.h>

// ─── Dual serial output (USB CDC + UART1→ESP32 bridge) ───────────────
// RP2040 direct USB CDC is unreliable with earlephilhower core.
// ESP32 UART bridge (GP12/GP13 → ESP32 → USB CDC) is the reliable path.
static void dualPrintf(const char* fmt, ...) {
    char buf[300];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.print(buf);
    Serial1.print(buf);
}

// ─── Role selection ──────────────────────────────────────────────────
#if !defined(TX_ROLE) && !defined(RX_ROLE)
#error "Define either -D TX_ROLE or -D RX_ROLE"
#endif

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

// ─── Phase table ─────────────────────────────────────────────────────
enum PacketType { PT_LORA = 0x00, PT_FLRC = 0x05 };

typedef struct {
    const char* name;
    uint8_t  pktType;    // 0x00=LoRa, 0x05=FLRC
    float    freqMHz;    // 2440.0 or 868.0
    uint8_t  rfPath;     // 1=HF, 0=LF
    uint8_t  sf;         // 7/9/12 (LoRa only, 0 for FLRC)
    uint8_t  bwCode;     // LoRa BW code
    uint8_t  cr;         // LoRa CR (1-4)
    uint16_t flrcBr;     // FLRC bitrate (0 for LoRa)
    uint16_t pktCount;   // TX: packets to send
    uint16_t slotMs;     // time budget for this phase
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
    // ── 868 MHz LF FLRC path (UNTESTED — may not be supported by chip) ──
    {"LF-FLRC-2600",  PT_FLRC,  868.0, 0,  0, 0x00, 0, 2600, 200,  8000},
    {"LF-FLRC-1300",  PT_FLRC,  868.0, 0,  0, 0x00, 0, 1300, 200,  8000},
    {"LF-FLRC-650",   PT_FLRC,  868.0, 0,  0, 0x00, 0,  650, 200,  8000},
    {"LF-FLRC-325",   PT_FLRC,  868.0, 0,  0, 0x00, 0,  325, 200,  8000},
};
static const int NUM_PHASES = sizeof(phases) / sizeof(phases[0]);

#define TX_POWER_DBM   12.5f   // Code 25 = PA enabled (binary PA, see power sweep results)
#define LORA_PKT_SIZE  127
#define FLRC_PKT_SIZE  255
#define AUTO_START_DELAY_MS  8000

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
    spiRf.transfer(cmd, nullptr, len);
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

static uint8_t rfReadStatus() {
    rfWaitBusy();
    uint8_t cmd[2] = {0x01, 0x24};
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(cmd, 2);
    uint8_t st = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    return st;
}

static void rfClearIrq() {
    uint8_t cmd[6] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 6);
}

static void rfSetTx() {
    uint8_t cmd[5] = {0x02, 0x0D, 0x00, 0x00, 0x00};
    rfWriteCmd(cmd, 5);
}

static void rfSetRx() {
    uint8_t cmd[5] = {0x02, 0x0C, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 5);
}

static void rfWriteTxFifo(const uint8_t *data, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00);
    spiRf.transfer(0x02);  // WRITE_TX_FIFO
    for (size_t i = 0; i < len; i++) spiRf.transfer(data[i]);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfReadRxFifo(uint8_t *data, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00);
    spiRf.transfer(0x03);  // READ_RX_FIFO
    for (size_t i = 0; i < len; i++) data[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfClearTxFifo() {
    uint8_t cmd[] = {0x01, 0x1F};
    rfWriteCmd(cmd, 2);
}

static void rfClearRxFifo() {
    uint8_t cmd[] = {0x01, 0x20};
    rfWriteCmd(cmd, 2);
}

static int16_t rfGetLoraRssi() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02); spiRf.transfer(0x2A);  // GET_LORA_PACKET_STATUS
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    // Read 8 bytes: [stat_msb][stat_lsb][rssiSync][snr]...
    uint8_t buf[8];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 8; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    // Raw format: [stat_msb][stat_lsb][flag][snr][rssi_avg][rssi_sync][?][?]
    // buf[4] = rssiAvg (verified: varies per-packet, gives realistic dBm)
    // buf[3] = snr (0x7F = 31.75 dB, matches proven value)
    // Return in tenths of dBm: -buf[4] * 5 = -(val/2) * 10
    return -(int16_t)buf[4] * 5;  // e.g. val=51 → -255 → -25.5 dBm
}

// ─── FLRC RSSI (was missing — caused rssi_avg=0.0 in FLRC phases) ────
static int16_t rfGetFlrcRssi() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02); spiRf.transfer(0x4B);  // GET_FLRC_PACKET_STATUS
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[8];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 8; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    // RSSI in 0.5 dBm units (same as LoRa — verified via raw byte analysis)
    // buf[4] = raw RSSI value, resolution 0.5 dBm
    // Return in tenths of dBm: -buf[4] * 5
    return -(int16_t)buf[4] * 5;  // e.g. val=49 → -245 → -24.5 dBm
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

// ─── Radio init per phase ────────────────────────────────────────────
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
    // CALIB_FRONT_END — HF: bit15 set, LF: no bit15 (MANDATORY per plan)
    uint16_t feFreq = (uint16_t)((freqMHz / 4.0f) + 0.5f);
    if (rfPath == 1) feFreq |= 0x8000;  // HF path
    uint8_t c1[] = {0x01, 0x23,
                    (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
                    0, 0, 0, 0, 0, 0};
    rfWriteCmd(c1, 10);
    delay(5);
    // CALIBRATE (all blocks)
    uint8_t c2[] = {0x01, 0x22, 0x5F};
    rfWriteCmd(c2, 3);
    delay(5);
}

static void rfInitForPhase(const Phase &p) {
    rfResetAndStandby();

    // SET_PACKET_TYPE
    { uint8_t c[] = {0x02, 0x07, p.pktType}; rfWriteCmd(c, 3); }
    delay(1);

    // SET_RF_FREQUENCY
    rfSetFreq(p.freqMHz);
    delay(1);

    // SET_RX_PATH
    { uint8_t c[] = {0x02, 0x01, p.rfPath, 0x00}; rfWriteCmd(c, 4); }
    delay(1);

    // Calibrate
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

        // SET_LORA_SYNCWORD (0x12 = private)
        { uint8_t c[] = {0x02, 0x23, 0x12}; rfWriteCmd(c, 3); }
        delay(1);

        // SET_LORA_PACKET_PARAMS: preamble=8, payload=127, explicit, CRC on
        { uint8_t flags = 0x04; // explicit header (0<<2), CRC on (1<<1)
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

#ifdef TX_ROLE
    // IRQ: TX_DONE (bit 19 = 0x00080000)
    { uint8_t c[] = {0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00}; rfWriteCmd(c, 7); }
#else
    // IRQ: RX_DONE (bit 18) + CRC_ERROR (bit 22) = 0x00240000
    { uint8_t c[] = {0x01, 0x15, 0x09, 0x00, 0x24, 0x00, 0x00}; rfWriteCmd(c, 7); }
#endif
    delay(1);

    rfClearIrq();
    delay(1);
}

// ─── TX phase runner ─────────────────────────────────────────────────
#ifdef TX_ROLE
static void runTxPhase(const Phase &p, int phaseIdx) {
    rfInitForPhase(p);
    delay(100);

    uint16_t pktSize = (p.pktType == PT_LORA) ? LORA_PKT_SIZE : FLRC_PKT_SIZE;
    uint8_t txBuf[256];
    // Fill payload with recognizable pattern
    for (int i = 0; i < pktSize; i++) txBuf[i] = (uint8_t)(i ^ 0xA5);

    uint32_t startMs = millis();
    uint16_t sent = 0, timeout = 0;

    dualPrintf("PHASE_TX %d %s started uptime=%lu\n", phaseIdx, p.name, startMs);

    // NOTE: No per-phase TX delay — it accumulates across phases and
    // pushes later phases out of RX window. Instead rely on wide slot
    // durations (15s+ each) so both boards overlap naturally.

    for (uint16_t i = 0; i < p.pktCount; i++) {
        txBuf[0] = (uint8_t)(i >> 8);   // seq high
        txBuf[1] = (uint8_t)(i & 0xFF); // seq low
        txBuf[2] = (uint8_t)phaseIdx;   // phase ID

        rfClearIrq();
        rfClearTxFifo();
        rfWriteTxFifo(txBuf, pktSize);
        rfSetTx();

        // Wait for TX_DONE — poll DIO9 GPIO pin (proven method from lora_range_tx.cpp)
        uint32_t irqPinMask = 1UL << PIN_IRQ;
        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 30000000) {
            if (sio_hw->gpio_in & irqPinMask) { irqFired = true; break; }
            spinCount++;
        }

        if (irqFired) sent++;
        else timeout++;

        digitalWrite(PIN_LED, (i & 1) ? HIGH : LOW);

        // Spread packets across slot: wait so last packet ends near slot end.
        // This ensures RX (which may have started later) catches some packets.
        uint32_t elapsedNow = millis() - startMs;
        uint32_t targetTime = (uint32_t)(i + 1) * (uint32_t)p.slotMs / (uint32_t)p.pktCount;
        if (elapsedNow < targetTime) {
            delay(targetTime - elapsedNow);
        }

        if ((millis() - startMs) > (uint32_t)p.slotMs - 200) break;
    }

    digitalWrite(PIN_LED, LOW);
    uint32_t elapsed = millis() - startMs;
    // TX side output — LR2021_RESULT format with tx-side fields
    int bw_khz = p.bwCode == 0x05 ? 250 : (p.bwCode == 0x0F ? 812 : 0);
    int sf = (p.pktType == PT_LORA) ? p.sf : 0;
    int br = (p.pktType == PT_FLRC) ? p.flrcBr : 0;
    int pkt_sz = (p.pktType == PT_LORA) ? LORA_PKT_SIZE : FLRC_PKT_SIZE;
    const char* modStr = (p.pktType == PT_LORA) ? "LORA" : "FLRC";
    const char* pathStr = p.rfPath == 1 ?
        (p.pktType == PT_LORA ? "HF_LORA" : "HF_FLRC") :
        (p.pktType == PT_LORA ? "LF_LORA" : "LF_FLRC");
    const char* paStr = (TX_POWER_DBM >= 12.5f) ? "ON" : "OFF";

    dualPrintf("LR2021_RESULT,path=%s,freq_mhz=%d,modulation=%s,bitrate_kbps=%d,spreading_factor=%d,bandwidth_khz=%d,coding_rate=45,tx_power_dbm=%.1f,pa_state=%s,distance_m=,los=,packets_sent=%u,packets_rx=0,packets_unique=0,per_percent=,throughput_kbps=,rssi_avg_dbm=,rssi_min_dbm=,rssi_max_dbm=,snr_avg_db=%s,pkt_size_bytes=%d,uptime_ms=%lu,notes=tx_side_phase=%d_timeout=%u\n",
                  pathStr, (int)p.freqMHz, modStr, br, sf, bw_khz,
                  (double)TX_POWER_DBM, paStr, sent,
                  (p.pktType == PT_LORA) ? "" : "NA",
                  pkt_sz, startMs, phaseIdx, timeout);
    Serial.flush(); Serial1.flush();
}
#endif

// ─── RX phase runner ─────────────────────────────────────────────────
#ifndef TX_ROLE
static void runRxPhase(const Phase &p, int phaseIdx) {
    rfInitForPhase(p);
    delay(100);

    uint16_t pktSize = (p.pktType == PT_LORA) ? LORA_PKT_SIZE : FLRC_PKT_SIZE;
    uint8_t rxBuf[256];

    uint32_t startMs = millis();
    uint32_t slotBudget = (uint32_t)p.slotMs + 3000; // Match TX cycle length (3s delay per phase)
    uint16_t received = 0, crcErrors = 0;
    int32_t rssiSum = 0;
    uint16_t rssiCount = 0;
    uint16_t lastSeq = 0xFFFF;

    rfClearRxFifo();
    rfClearIrq();
    rfSetRx();

    dualPrintf("PHASE_RX %d %s listening=%lums\n", phaseIdx, p.name, slotBudget);

    uint32_t irqPinMask = 1UL << PIN_IRQ;

    while ((millis() - startMs) < slotBudget) {
        // Poll DIO9 IRQ pin (proven method, not SPI register read)
        if (sio_hw->gpio_in & irqPinMask) {
            // IRQ fired — check what happened via SPI
            uint32_t irq = rfReadIrqStatus();
            if (irq & 0x00200000) {
                // CRC error
                crcErrors++;
                rfClearIrq();
                rfSetRx();
                continue;
            }
            if (irq & 0x00040000) {
                // RX_DONE — read RSSI FIRST (before FIFO, which may clear status)
                if (p.pktType == PT_LORA) {
                    int16_t rssi = rfGetLoraRssi();
                    rssiSum += rssi;
                    rssiCount++;
                    if (received < 3) {
                        // Dump raw SPI bytes for RSSI debugging
                        rfWaitBusy();
                        spiRf.beginTransaction(spiSettings);
                        digitalWrite(PIN_CS, LOW);
                        spiRf.transfer(0x02); spiRf.transfer(0x2A);
                        digitalWrite(PIN_CS, HIGH);
                        spiRf.endTransaction();
                        rfWaitBusy();
                        uint8_t raw[8];
                        spiRf.beginTransaction(spiSettings);
                        digitalWrite(PIN_CS, LOW);
                        for (int j = 0; j < 8; j++) raw[j] = spiRf.transfer(0x00);
                        digitalWrite(PIN_CS, HIGH);
                        spiRf.endTransaction();
                        dualPrintf("DEBUG_RSSI pkt=%d raw=[%02X %02X %02X %02X %02X %02X %02X %02X] rssi=%d\n",
                                      received, raw[0],raw[1],raw[2],raw[3],raw[4],raw[5],raw[6],raw[7], rssi);
                    }
                } else {
                    // FLRC RSSI — GET_FLRC_PACKET_STATUS (0x024B)
                    int16_t rssi = rfGetFlrcRssi();
                    rssiSum += rssi;
                    rssiCount++;
                    if (received < 3) {
                        // Dump raw SPI bytes for FLRC RSSI debugging
                        rfWaitBusy();
                        spiRf.beginTransaction(spiSettings);
                        digitalWrite(PIN_CS, LOW);
                        spiRf.transfer(0x02); spiRf.transfer(0x4B);
                        digitalWrite(PIN_CS, HIGH);
                        spiRf.endTransaction();
                        rfWaitBusy();
                        uint8_t raw[8];
                        spiRf.beginTransaction(spiSettings);
                        digitalWrite(PIN_CS, LOW);
                        for (int j = 0; j < 8; j++) raw[j] = spiRf.transfer(0x00);
                        digitalWrite(PIN_CS, HIGH);
                        spiRf.endTransaction();
                        dualPrintf("DEBUG_FLRC_RSSI pkt=%d raw=[%02X %02X %02X %02X %02X %02X %02X %02X] rssi=%d\n",
                                      received, raw[0],raw[1],raw[2],raw[3],raw[4],raw[5],raw[6],raw[7], rssi);
                    }
                }

                rfReadRxFifo(rxBuf, pktSize);

                // Count packet — accept any phase (TX/RX may be in different phases
                // due to boot timing drift). Phase ID still in rxBuf[2] for analysis.
                received++;

                rfClearRxFifo();
                rfClearIrq();
                rfSetRx();
            }
        }
    }

    float rssiAvg = rssiCount > 0 ? (float)rssiSum / rssiCount / 10.0f : 0.0f;  // tenths → dBm
    float per = (p.pktCount > 0 && received < p.pktCount) ?
                (float)(p.pktCount - received) / p.pktCount * 100.0f : 0.0f;

    // Build unified CSV path/pa fields
    const char* pathStr = p.rfPath == 1 ?
        (p.pktType == PT_LORA ? "HF_LORA" : "HF_FLRC") :
        (p.pktType == PT_LORA ? "LF_LORA" : "LF_FLRC");
    const char* paStr = (TX_POWER_DBM >= 12.5f) ? "ON" : "OFF";

    // Output in LR2021_RESULT unified CSV format (plan section 3.1)
    // Fields the firmware can't know (distance_m, los, gps_time) left for post-processing
    int bw_khz = p.bwCode == 0x05 ? 250 : (p.bwCode == 0x0F ? 812 : 0);
    int sf = (p.pktType == PT_LORA) ? p.sf : 0;
    int br = (p.pktType == PT_FLRC) ? p.flrcBr : 0;
    int pkt_sz = (p.pktType == PT_LORA) ? LORA_PKT_SIZE : FLRC_PKT_SIZE;
    const char* modStr = (p.pktType == PT_LORA) ? "LORA" : "FLRC";

    dualPrintf("LR2021_RESULT,path=%s,freq_mhz=%d,modulation=%s,bitrate_kbps=%d,spreading_factor=%d,bandwidth_khz=%d,coding_rate=45,tx_power_dbm=%.1f,pa_state=%s,distance_m=,los=,packets_sent=%u,packets_rx=%u,packets_unique=%u,per_percent=%.1f,throughput_kbps=,rssi_avg_dbm=%.0f,rssi_min_dbm=,rssi_max_dbm=,snr_avg_db=%s,pkt_size_bytes=%d,uptime_ms=%lu,notes=phase=%d_crc_err=%u\n",
                  pathStr, (int)p.freqMHz, modStr, br, sf, bw_khz,
                  (double)TX_POWER_DBM, paStr,
                  p.pktCount, received, received, per, rssiAvg,
                  (p.pktType == PT_LORA) ? "" : "NA",
                  pkt_sz, startMs, phaseIdx, crcErrors);
    Serial.flush(); Serial1.flush();
}
#endif

// ─── Setup ───────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    Serial1.setTX(12);  // GP12 = UART0 TX → ESP32 GPIO3 (RX)
    Serial1.setRX(13);  // GP13 = UART0 RX ← ESP32 GPIO2 (TX)
    Serial1.begin(115200);  // UART1 → ESP32 bridge (reliable serial path)
    delay(2000);

    pinMode(PIN_CS, OUTPUT);
    pinMode(PIN_RST, OUTPUT);
    pinMode(PIN_IRQ, INPUT);
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    digitalWrite(PIN_RST, HIGH);
    digitalWrite(PIN_LED, LOW);

    spiRf.begin();

#ifdef TX_ROLE
    dualPrintf("=== MULTI-RADIO TX SWEEP ===\n");
#else
    dualPrintf("=== MULTI-RADIO RX SWEEP ===\n");
#endif
    dualPrintf("Phases: %d  Power: %.1f dBm\n", NUM_PHASES, TX_POWER_DBM);
    for (int i = 0; i < NUM_PHASES; i++) {
        dualPrintf("  [%d] %-16s %s %.0fMHz SF%d BW%d %dpkts %dms\n",
                      i, phases[i].name,
                      phases[i].pktType == PT_LORA ? "LoRa" : "FLRC",
                      phases[i].freqMHz,
                      phases[i].sf,
                      phases[i].bwCode == 0x05 ? 250 : phases[i].bwCode == 0x0F ? 812 : 0,
                      phases[i].pktCount, phases[i].slotMs);
    }

    dualPrintf("=== AUTO START IN 8s ===\n");
    // LED blink countdown
    for (int i = 8; i > 0; i--) {
        dualPrintf("  Starting in %d...\n", i);
        digitalWrite(PIN_LED, HIGH); delay(400);
        digitalWrite(PIN_LED, LOW);  delay(600);
    }
    dualPrintf("=== STARTING SWEEP ===\n");
}

// ─── Main loop ───────────────────────────────────────────────────────
void loop() {
    static int cycleNum = 0;

    dualPrintf("\n=== CYCLE %d START uptime=%lu ===\n", cycleNum, millis());

    for (int i = 0; i < NUM_PHASES; i++) {
#ifdef TX_ROLE
        runTxPhase(phases[i], i);
#else
        runRxPhase(phases[i], i);
#endif
    }

    dualPrintf("=== CYCLE %d COMPLETE uptime=%lu ===\n", cycleNum, millis());
    cycleNum++;
    delay(1000);
}
