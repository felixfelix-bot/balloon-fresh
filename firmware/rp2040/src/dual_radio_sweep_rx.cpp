/*
 * dual_radio_sweep_rx.cpp — Dual-radio sweep RX for LR2021 balloon range test
 *
 * RX counterpart to dual_radio_sweep_tx.cpp. Same 4-mode 12-minute cycle:
 *
 *   MODE 0 (0-3min):  HF FLRC 2600 kbps @ 2440 MHz (pin 10)
 *   MODE 1 (3-6min):  HF FLRC 325 kbps  @ 2440 MHz (pin 10)
 *   MODE 2 (6-9min):  LF LoRa SF7       @ 868 MHz  (pin 9)
 *   MODE 3 (9-12min): LF LoRa SF12      @ 868 MHz  (pin 9)
 *
 * Shares pins, SPI helpers, mode definitions, and initMode with TX.
 * Adds RX-specific: rfSetRx, rfReadRxFifo, rfReadRssiFlrc, rfReadRssiLora.
 * GPIO IRQ polling only (never SPI IRQ read — prevents FIFO race).
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13 LED=GP25 LED_ALT=GP16
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

#define TX_PKT_SIZE     127
#define TX_POWER_DBM    12.5f

// FLRC sync word — MUST match TX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

#define MODE_DURATION_MS  (3UL * 60UL * 1000UL)  // 3 minutes per mode
#define NUM_MODES         4

// ─── Mode definitions ────────────────────────────────────────────────
struct RadioMode {
    const char* name;
    bool isFlrc;        // true=FLRC, false=LoRa
    bool isHF;          // true=HF path (2.4GHz pin 10), false=LF path (sub-GHz pin 9)
    float freqMhz;
    uint16_t flrcBitrate; // FLRC only
    uint8_t loraSf;       // LoRa only
    uint8_t loraBwCode;   // LoRa only (0x0D=203kHz, 0x0E=406kHz, 0x0F=812kHz)
    uint8_t loraCr;       // LoRa only (1=4/5, 2=4/6, ...)
    uint16_t txPktCount;  // packets per burst
    uint32_t txPauseMs;   // pause between bursts
};

static const RadioMode modes[NUM_MODES] = {
    {"HF_FLRC_2600", true,  true,  2440.0f, 2600, 0,  0,    0, 500, 2000},
    {"HF_FLRC_325",  true,  true,  2440.0f, 325,  0,  0,    0, 500, 2000},
    {"LF_LORA_SF7",  false, false, 868.0f,  0,    7,  0x0F, 1, 50,  2000},
    {"LF_LORA_SF12", false, false, 868.0f,  0,    12, 0x0D, 1, 50,  2000},
};

// ─── SPI (VERBATIM from dual_radio_sweep_tx.cpp) ─────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// Pre-allocated combined buffer for single-batch SPI transfers
static uint8_t fifoCmd[2 + 255];
// Dummy RX buffer for write-only transfers
static uint8_t spiRxJunk[257];

static volatile bool radioReady = false;

// ─── SPI helpers (ALL Arduino, no direct HW registers for transfer) ──
// VERBATIM from dual_radio_sweep_tx.cpp
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
    spiRf.transfer((uint8_t*)buf, spiRxJunk, len);  // SINGLE BATCH — continuous SCK
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
    spiRf.transfer(cmd, spiRxJunk, 2);  // SINGLE BATCH
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    uint8_t buf[6];
    uint8_t dummy[6] = {0, 0, 0, 0, 0, 0};
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(dummy, buf, 6);  // batch read
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    return ((uint32_t)buf[2] << 24) | ((uint32_t)buf[3] << 16) |
           ((uint32_t)buf[4] << 8) | (uint32_t)buf[5];
}

static void rfClearIrq() {
    uint8_t cmd[6] = { 0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 6);
}

// ─── Runtime parameter setters (VERBATIM from dual_radio_sweep_tx.cpp) ─
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

// ─── Dual output (VERBATIM from dual_radio_sweep_tx.cpp) ─────────────
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

// ─── FLRC bitrate encoding (VERBATIM) ────────────────────────────────
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

// ─── LoRa LDRO computation (VERBATIM) ────────────────────────────────
static uint8_t computeLdro(uint8_t sf, uint8_t bwCode) {
    float bwHz = (bwCode == 0x0D) ? 203125.0f :
                 (bwCode == 0x0E) ? 406250.0f : 812500.0f;
    float symTimeMs = (float)(1UL << sf) / bwHz * 1000.0f;
    return (symTimeMs > 16.0f) ? 1 : 0;
}

// ═══ RX-SPECIFIC FUNCTIONS ═══════════════════════════════════════════

// SET_RX = 0x020C + 3-byte timeout (0xFFFFFF = continuous)
static void rfSetRx() {
    uint8_t cmd[5] = { 0x02, 0x0C, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 5);
}

// READ_RX_FIFO = 0x0001, then read N bytes — single SPI transaction
// Uses batch transfer (same style as TX's rfWriteCmd) for speed.
static void rfReadRxFifo(uint8_t *buf, size_t len) {
    // fifoCmd[0..1] = opcode; fifoCmd[2..] = 0x00 (static zero-init = dummy TX)
    fifoCmd[0] = 0x00;
    fifoCmd[1] = 0x01;

    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(fifoCmd, spiRxJunk, 2 + len);  // SINGLE BATCH — opcode + data
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    // Response: first 2 bytes are opcode echo, rest is FIFO data
    memcpy(buf, spiRxJunk + 2, len);
}

// GET_FLRC_PACKET_STATUS = 0x024B — 9-bit RSSI assembly
// Matches proven implementation from flrc_raw_rx.cpp / LR2021Raw.h
static int16_t rfReadRssiFlrc() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02);
    spiRf.transfer(0x4B);  // GET_FLRC_PACKET_STATUS
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    // Response: [stat_msb][stat_lsb][pktLen_msb][pktLen_lsb][rssiAvg][rssiSync][flags]
    uint8_t buf[7];
    uint8_t dummy[7] = {0, 0, 0, 0, 0, 0, 0};
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(dummy, buf, 7);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    // 9-bit RSSI: bits [8:1] from buf[4], bit[0] from buf[6] bit[2]
    uint16_t raw = ((uint16_t)buf[4] << 1) | ((buf[6] & 0x04) >> 2);
    return -(int16_t)(raw / 2);
}

// GET_LORA_PACKET_STATUS = 0x022A
// buf[2] = RSSI raw → dBm = -(val / 2)
// buf[3] = SNR → dB = buf[3]<128 ? buf[3]/4 : (buf[3]-256)/4
static int16_t rfReadRssiLora() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02);
    spiRf.transfer(0x2A);  // GET_LORA_PACKET_STATUS
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    // Response: [dummy][dummy][rssi][snr][...]
    uint8_t buf[5];
    uint8_t dummy[5] = {0, 0, 0, 0, 0};
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(dummy, buf, 5);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    // buf[2] = RSSI raw → dBm = -(val / 2)
    return -(int16_t)(buf[2] / 2);
}

// ─── Mode scheduling (VERBATIM from dual_radio_sweep_tx.cpp) ─────────
static int currentMode = -1;
static uint32_t cycleStartMs = 0;

static int getCurrentMode() {
    uint32_t elapsed = millis() - cycleStartMs;
    uint32_t cycleLen = MODE_DURATION_MS * NUM_MODES;
    uint32_t cyclePos = elapsed % cycleLen;
    return (int)(cyclePos / MODE_DURATION_MS);
}

static void printModeSwitch(int mode) {
    const RadioMode& m = modes[mode];
    if (m.isFlrc) {
        dualPrintf("MODE_SWITCH mode=%d type=FLRC freq=%.0f bitrate=%d",
                   mode, m.freqMhz, m.flrcBitrate);
    } else {
        dualPrintf("MODE_SWITCH mode=%d type=LoRa freq=%.0f SF=%d",
                   mode, m.freqMhz, m.loraSf);
    }
}

// ─── Per-mode RX statistics ──────────────────────────────────────────
struct ModeStats {
    uint32_t received;
    uint32_t lastSeq;
    uint32_t maxSeq;
    int32_t  rssiSum;
    int16_t  rssiMin;
    int16_t  rssiMax;
    uint16_t rssiCount;
    uint32_t startMs;
};

static ModeStats modeStats[NUM_MODES];

static void resetModeStats(int mode) {
    ModeStats& s = modeStats[mode];
    s.received  = 0;
    s.lastSeq   = 0xFFFFFFFF;
    s.maxSeq    = 0;
    s.rssiSum   = 0;
    s.rssiMin   = 0;       // first negative RSSI will be < 0, updating it
    s.rssiMax   = -128;    // first RSSI will be > -128, updating it
    s.rssiCount = 0;
    s.startMs   = millis();
}

// Print accumulated RESULT line for a completed mode
static void printModeResult(int mode) {
    const RadioMode& m = modes[mode];
    ModeStats& s = modeStats[mode];
    float rssiAvg = (s.rssiCount > 0)
                    ? ((float)s.rssiSum / (float)s.rssiCount) : 0.0f;

    if (m.isFlrc) {
        dualPrintf("SWEEP_RX_RESULT,mode=%d,type=FLRC,freq=%.0f,bitrate=%d,received=%lu,rssi_avg=%.1f,rssi_min=%d,rssi_max=%d,max_seq=%lu,start_ms=%lu",
                   mode, m.freqMhz, m.flrcBitrate,
                   (unsigned long)s.received, rssiAvg,
                   (int)s.rssiMin, (int)s.rssiMax,
                   (unsigned long)s.maxSeq, (unsigned long)s.startMs);
    } else {
        int bwKhz = (m.loraBwCode == 0x0D) ? 203 :
                    (m.loraBwCode == 0x0E) ? 406 : 812;
        dualPrintf("SWEEP_RX_RESULT,mode=%d,type=LoRa,freq=%.0f,SF=%d,bw=%d,received=%lu,rssi_avg=%.1f,rssi_min=%d,rssi_max=%d,max_seq=%lu,start_ms=%lu",
                   mode, m.freqMhz, m.loraSf, bwKhz,
                   (unsigned long)s.received, rssiAvg,
                   (int)s.rssiMin, (int)s.rssiMax,
                   (unsigned long)s.maxSeq, (unsigned long)s.startMs);
    }
}

// ─── Mode init — COMPLETE radio re-init for each mode ────────────────
// Based on dual_radio_sweep_tx.cpp initMode with RX adaptations:
//   - IRQ mask: RX_DONE (0x04) instead of TX_DONE (0x08)
//   - Enters continuous RX via SET_RX at the end
static bool initMode(int mode) {
    const RadioMode& m = modes[mode];

    // 1. SET_STANDBY (0x0200, STDBY_RC=0x01) — known state
    { uint8_t cmd[] = { 0x02, 0x00, 0x01 }; rfWriteCmd(cmd, 3); }
    delay(5);

    // 2. SET_PACKET_TYPE (FLRC=0x04 proven, LoRa=0x00 proven)
    uint8_t pktType = m.isFlrc ? 0x04 : 0x00;
    { uint8_t cmd[] = { 0x02, 0x07, pktType }; rfWriteCmd(cmd, 3); }
    delay(1);

    // 4. SET_RF_FREQUENCY
    rfSetFreq(m.freqMhz);
    delay(1);

    // 5. SET_RX_PATH (HF=0x01 for 2.4GHz, LF=0x00 for sub-GHz)
    uint8_t rxPath = m.isHF ? 0x01 : 0x00;
    { uint8_t cmd[] = { 0x02, 0x01, rxPath, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 6. CALIB_FRONT_END — HF path sets bit 15, LF path does NOT
    uint16_t feFreq = (uint16_t)((m.freqMhz / 4.0f) + 0.5f);
    if (m.isHF) feFreq |= 0x8000;
    {
        uint8_t cmd[] = {
            0x01, 0x23,
            (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        };
        rfWriteCmd(cmd, 10);
    }
    delay(5);

    // 7. CALIBRATE (mask 0x5F)
    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
    delay(5);

    // 8. SET_MOD_PARAMS + SET_PACKET_PARAMS (mode-specific)
    if (m.isFlrc) {
        // SET_FLRC_MOD_PARAMS (0x0248): brBw, CR=4/5|BT=0.5=0x25
        uint8_t brBw = flrcBitrateToCode(m.flrcBitrate);
        { uint8_t cmd[] = { 0x02, 0x48, brBw, 0x25 }; rfWriteCmd(cmd, 4); }
        delay(1);

        // SET_FLRC_SYNCWORD (0x024C)
        { uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 }; rfWriteCmd(cmd, 7); }
        delay(1);

        // SET_FLRC_PACKET_PARAMS (0x0249)
        { uint8_t cmd[] = { 0x02, 0x49, 0x0C, 0x4C, (uint8_t)(TX_PKT_SIZE >> 8), (uint8_t)(TX_PKT_SIZE & 0xFF) }; rfWriteCmd(cmd, 6); }
        delay(1);
    } else {
        // SET_LORA_MOD_PARAMS (0x0220): sfBwByte, crLdroByte
        uint8_t ldro = computeLdro(m.loraSf, m.loraBwCode);
        uint8_t sfBwByte = ((m.loraSf & 0x0F) << 4) | (m.loraBwCode & 0x0F);
        uint8_t crLdroByte = ((m.loraCr & 0x0F) << 4) | (ldro & 0x01);
        { uint8_t cmd[] = { 0x02, 0x20, sfBwByte, crLdroByte }; rfWriteCmd(cmd, 4); }
        delay(1);

        // SET_LORA_SYNCWORD (0x0223): 0x12 = private network
        { uint8_t cmd[] = { 0x02, 0x23, 0x12 }; rfWriteCmd(cmd, 3); }
        delay(1);

        // SET_LORA_PACKET_PARAMS (0x0221): preamble=8, payloadLen, explicit hdr, CRC on
        uint8_t flags = (0 << 2) | (1 << 1) | 0;  // explicit=0bit, CRC=1bit
        { uint8_t cmd[] = { 0x02, 0x21, 0x00, 0x08, (uint8_t)TX_PKT_SIZE, flags }; rfWriteCmd(cmd, 6); }
        delay(1);
    }

    // 9. SET_PA_CONFIG (0x0202)
    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);

    // 10. SET_TX_PARAMS (0x0203)
    rfSetTxPower(TX_POWER_DBM);
    delay(1);

    // 11. SET_RX_TX_FALLBACK (FS=0x03)
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // 12. SET_DIO_FUNCTION (DIO9=IRQ)
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 13. SET_DIO_IRQ_CONFIG (RX_DONE bit 0x00040000 — NOT TX_DONE 0x08)
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x04, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
    delay(1);

    // 14. CLEAR_IRQ
    rfClearIrq();
    delay(10);

    // 15. Enter continuous RX mode (RX-specific — TX calls SET_TX per-burst instead)
    rfSetRx();
    delay(2);

    // Verify
    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("INIT mode=%d Status=0x%02X IRQ=0x%08lX", mode, st, (unsigned long)irq);

    // Accept: STDBY(0x03), FS(0x04), RX(0x05), or CMD_ERROR (partial)
    if ((st >> 4) == 0x03 || (st >> 4) == 0x04 ||
        (st >> 4) == 0x05 || (st >> 4) == 0x07 ||
        (irq & 0x00020000)) {
        dualPrintf("MODE_INIT_OK mode=%d", mode);
        return true;
    }
    dualPrintf("MODE_INIT_FAIL mode=%d (St=0x%02X)", mode, st);
    return false;
}

// ─── RX packet poll (non-blocking) ───────────────────────────────────
// Called once per loop() iteration. Returns immediately if no packet.
// GPIO IRQ polling ONLY — never reads IRQ status via SPI (FIFO race).
static uint32_t lastPktLedMs = 0;

static void pollRx() {
    // LED off after brief flash
    if (digitalRead(PIN_LED) == HIGH && (millis() - lastPktLedMs) > 50) {
        digitalWrite(PIN_LED, LOW);
    }

    // Poll GPIO IRQ pin — DIO9 goes HIGH when RX_DONE fires
    uint32_t irqMask = 1UL << PIN_IRQ;
    if (!(sio_hw->gpio_in & irqMask)) return;  // no packet yet

    // ── Packet received — process immediately ──
    // Order: rfClearIrq → read FIFO → read RSSI → rfSetRx (re-arm)
    rfClearIrq();

    uint8_t buf[TX_PKT_SIZE];
    rfReadRxFifo(buf, TX_PKT_SIZE);

    // Read RSSI (mode-specific)
    int16_t rssi = modes[currentMode].isFlrc ? rfReadRssiFlrc() : rfReadRssiLora();

    // Re-arm RX for next packet
    rfSetRx();

    // Skip DEADBEEF burst markers (TX sends these at end of each burst)
    if (buf[0] == 0xDE && buf[1] == 0xAD &&
        buf[2] == 0xBE && buf[3] == 0xEF) {
        uint32_t burstPkts = ((uint32_t)buf[4] << 24) | ((uint32_t)buf[5] << 16) |
                             ((uint32_t)buf[6] << 8)  | (uint32_t)buf[7];
        dualPrintf("BURST_END mode=%d n=%lu", currentMode, (unsigned long)burstPkts);
        return;
    }

    // Update per-mode stats
    ModeStats& s = modeStats[currentMode];
    s.received++;
    s.rssiSum += rssi;
    s.rssiCount++;
    if (rssi < s.rssiMin) s.rssiMin = rssi;
    if (rssi > s.rssiMax) s.rssiMax = rssi;

    // Extract big-endian seq from first 4 bytes
    uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                   ((uint32_t)buf[2] << 8)  | (uint32_t)buf[3];
    s.lastSeq = seq;
    if (seq > s.maxSeq) s.maxSeq = seq;

    // LED blink on packet
    digitalWrite(PIN_LED, HIGH);
    lastPktLedMs = millis();

    // Progress print (first 5 + every 100)
    if (s.received <= 5 || (s.received % 100) == 0) {
        dualPrintf("PKT %lu mode=%d seq=%lu rssi=%d",
                   (unsigned long)s.received, currentMode,
                   (unsigned long)seq, (int)rssi);
    }
}

// ─── Arduino entry points ────────────────────────────────────────────
static unsigned long lastHB = 0;

void setup() {
    Serial.begin(115200);
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);
    delay(100);

    // Print banner BEFORE any radio init — if init hangs, USB CDC is alive
    dualPrintln();
    dualPrintln("=========================================");
    dualPrintln("=== RP2040 DUAL RADIO SWEEP RX       ===");
    dualPrintln("=========================================");
    dualPrintf("Modes: 0=FLRC2600 1=FLRC325 2=LoRaSF7 3=LoRaSF12");
    dualPrintf("Cycle: %d min (%d min per mode)", NUM_MODES * 3, 3);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    // Hardware reset before first init
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    // Initialize all mode stats
    for (int i = 0; i < NUM_MODES; i++) {
        modeStats[i].received  = 0;
        modeStats[i].lastSeq   = 0xFFFFFFFF;
        modeStats[i].maxSeq    = 0;
        modeStats[i].rssiSum   = 0;
        modeStats[i].rssiMin   = 0;
        modeStats[i].rssiMax   = -128;
        modeStats[i].rssiCount = 0;
        modeStats[i].startMs   = 0;
    }

    cycleStartMs = millis();
    currentMode = getCurrentMode();
    resetModeStats(currentMode);
    radioReady = initMode(currentMode);

    if (!radioReady) {
        dualPrintln("INIT FAILED — retrying...");
        delay(2000);
        radioReady = initMode(currentMode);
    }

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        printModeSwitch(currentMode);
        dualPrintln("SWEEP RX LISTENING");
    } else {
        dualPrintln("INIT FAILED TWICE — stuck");
    }
}

void loop() {
    if (radioReady) {
        // Check mode boundary
        int newMode = getCurrentMode();
        if (newMode != currentMode) {
            // Print RESULT for the mode we're leaving
            printModeResult(currentMode);

            // Switch to new mode
            printModeSwitch(newMode);
            radioReady = initMode(newMode);
            if (radioReady) {
                currentMode = newMode;
                resetModeStats(currentMode);
            } else {
                dualPrintf("MODE_INIT_RETRY mode=%d", newMode);
                delay(1000);
                radioReady = initMode(newMode);
                if (radioReady) {
                    currentMode = newMode;
                    resetModeStats(currentMode);
                }
            }
        }

        if (radioReady) {
            // Non-blocking RX poll — checks GPIO IRQ, processes packet if ready
            pollRx();

            // Heartbeat to keep USB CDC alive
            if (millis() - lastHB > 5000) {
                lastHB = millis();
                dualPrintf("[RX HB %lus] mode=%d rx=%lu",
                           millis() / 1000, currentMode,
                           (unsigned long)modeStats[currentMode].received);
            }
        }
    } else {
        // Blink SOS if radio dead + heartbeat so USB CDC stays alive
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(500);
        dualPrintf("[RX DEAD %lus]", millis() / 1000);

        // Retry init
        int targetMode = getCurrentMode();
        radioReady = initMode(targetMode);
        if (radioReady) {
            currentMode = targetMode;
            resetModeStats(currentMode);
        }
    }
}
