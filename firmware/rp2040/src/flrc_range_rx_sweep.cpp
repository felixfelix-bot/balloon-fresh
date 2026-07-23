/*
 * flrc_range_rx_sweep.cpp — Adaptive bitrate sweep RX for range testing
 *
 * Based on flrc_raw_rx.cpp (proven raw SPI RX with GPIO IRQ polling).
 * Auto-starts RX on boot — same as raw_rx.
 *
 * New behavior (vs raw_rx):
 * - Sweeps through 4 FLRC bitrates (2600/1300/650/325 kbps) on a 12-min cycle
 * - Scheduler syncs to GPS time (UTC) if GPS lock available, else millis fallback
 * - Calls rfSwitchBitrate() at each window boundary (STDBY→MOD_PARAMS→CALIB→CLR_IRQ)
 * - Resets per-window stats on bitrate switch + re-arms RX
 * - RESULT line includes bitrate/sweepIdx/cycle/time_src fields
 *
 * RX behavior (unchanged from raw_rx):
 * - GPIO IRQ polling (sio_hw->gpio_in) for nanosecond latency
 * - FIFO read + CLEAR_RX_FIFO + CLR_IRQ + SET_RX per packet
 * - RSSI (rfReadRssi 0x024B + rfReadRssiInst 0x020B)
 * - PER tracking (burstCount/totalExpected via DEADBEEF markers)
 * - Noise floor measurement at boot
 * - Auto-restart RX continuously
 *
 * Config: FREQ=2440, PKTLEN=127, bitrate=DYNAMIC (set by SweepScheduler)
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13
 *       GPS_RX=GP1 GPS_TX=GP0 GPS_PPS=GP9
 *       LED=GP25 LED_ALT=GP16
 */

#include <Arduino.h>
#include <SPI.h>
#include "pico/bootrom.h"
#include "gps_time.h"
#include "sweep_scheduler.h"
// NOT radio.h — rfSwitchBitrate() implemented locally using SPIClassRP2040
// at 20 MHz (same SPI backend as raw_rx). The radio.cpp version uses MbedSPI
// with a different SPI peripheral — incompatible, so we exclude it via src_filter.
// sio_hw is available via earlephilhower core (rp2040/pico.h)

// ─── GPS pins (overridable via build flags) ──────────────────────────
#ifndef GPS_RX_PIN
#define GPS_RX_PIN   1      // GP1 — data from GPS (Serial2 RX)
#endif
#ifndef GPS_TX_PIN
#define GPS_TX_PIN   0      // GP0 — config to GPS (Serial2 TX)
#endif
#ifndef GPS_PPS_PIN
#define GPS_PPS_PIN  9      // GP9 — 1PPS interrupt
#endif
#ifndef GPS_BAUD
#define GPS_BAUD     9600
#endif

// ─── Radio pins ──────────────────────────────────────────────────────
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

// ─── FLRC Config ─────────────────────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_BR         2600
#ifndef FLRC_PKT_SIZE
#define FLRC_PKT_SIZE   127     // MUST match TX (flrc_range_tx_sweep uses 127)
#endif
#ifndef SPI_FREQ_HZ
#define SPI_FREQ_HZ     20000000UL
#endif
#define XTAL_MHZ        52.0f

#define RX_LISTEN_MS    12000
#define RX_SILENCE_MS   3000
#define PRINT_EVERY     100

// Sync word — MUST match TX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// ─── Raw SPI helpers ─────────────────────────────────────────────────
static inline void rfWaitBusy() {
    uint32_t timeout = millis() + 50;
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

// Two-phase read: send command, release CS, then read response
static void rfReadFifo(uint8_t *buf, size_t len) {
    // LR2021 READ_RX_FIFO (0x0001) — single SPI transaction
    // RadioLib does opcode+data in one CS-low cycle, no CS toggle between
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00); spiRf.transfer(0x01);  // opcode
    // Read data immediately — no CS toggle, no status bytes
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
    // GET_AND_CLEAR_IRQ_STATUS = 0x0117
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

// ─── RSSI readback via GET_FLRC_PACKET_STATUS (0x024B) — 9-bit assembly
// Matches verified implementation from flrc_range_rx_auto.cpp / LR2021Raw.h
static int8_t rfReadRssi() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02); spiRf.transfer(0x4B); // GET_FLRC_PACKET_STATUS
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

    // 9-bit RSSI: bits [8:1] from buf[4], bit[0] from buf[6] bit[2]
    uint16_t raw = ((uint16_t)buf[4] << 1) | ((buf[6] & 0x04) >> 2);
    return -(int8_t)(raw / 2);
}

// ─── Instantaneous RSSI via GET_RSSI_INST (0x020B) — 9-bit assembly
// Used for noise-floor measurement when no packet is being received.
static int8_t rfReadRssiInst() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x02); spiRf.transfer(0x0B); // GET_RSSI_INST
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

    // Response: [rssiMsb][rssiLsb] — 9-bit value
    uint8_t buf[2];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 2; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();

    // 9-bit RSSI: bits [8:1] from buf[0], bit[0] from buf[1] bit[7]
    uint16_t raw = ((uint16_t)buf[0] << 1) | (buf[1] >> 7);
    return -(int8_t)(raw / 2);
}

static void rfSetRx() {
    // SET_RX = 0x020C + 3-byte timeout (0xFFFFFF = continuous)
    // Total: 5 bytes (NOT 6 — extra byte causes CMD_ERROR)
    uint8_t cmd[5] = { 0x02, 0x0C, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 5);
}

// ─── Runtime bitrate setter ──────────────────────────────────────────
static void rfSetBitrate(uint16_t kbps) {
    uint8_t brBw;
    switch (kbps) {
        case 2600: brBw = 0x00; break;  // FLRC_BR_2600
        case 2080: brBw = 0x01; break;  // FLRC_BR_2080
        case 1300: brBw = 0x02; break;  // FLRC_BR_1300
        case 1040: brBw = 0x03; break;  // FLRC_BR_1040
        case 650:  brBw = 0x04; break;  // FLRC_BR_650
        case 520:  brBw = 0x05; break;  // FLRC_BR_520
        case 325:  brBw = 0x06; break;  // FLRC_BR_325
        case 260:  brBw = 0x07; break;  // FLRC_BR_260
        default:   brBw = 0x00; break;
    }
    uint8_t cmd[] = { 0x02, 0x48, brBw, 0x25 };
    rfWriteCmd(cmd, 4);
}

// ─── Runtime bitrate switching ───────────────────────────────────────
// Implements rfSwitchBitrate() LOCALLY using this firmware's own SPI helpers
// (SPIClassRP2040 at 20 MHz, same as raw_rx). The radio.cpp version uses
// MbedSPI with a different SPI backend — we can't link both, so we provide
// the implementation here. radio.cpp is excluded from the build via src_filter.
//
// Sequence: STDBY_RC → MOD_PARAMS → CALIBRATE → CLEAR_IRQ
static void rfSwitchBitrate(uint16_t newBitrate) {
    // 1. Enter STDBY_RC — required before changing modulation params
    uint8_t stdby[] = { 0x02, 0x00, 0x01 };
    rfWriteCmd(stdby, 3);
    delay(1);

    // 2. Set new modulation params (bitrate + bandwidth)
    rfSetBitrate(newBitrate);
    delay(1);

    // 3. Recalibrate — bandwidth changes with bitrate, PLL/Image cal needed
    uint8_t calib[] = { 0x01, 0x22, 0x5F };
    rfWriteCmd(calib, 3);
    delay(5);

    // 4. Clear any IRQs generated by the mode transition
    uint8_t clrIrq[] = { 0x02, 0x0B, 0x02 };
    rfWriteCmd(clrIrq, 3);
    delay(1);
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

// ─── Raw SPI Init (TheClams + RadioLib fixes) ────────────────────────
static bool rawInitRadio() {
    // 0. Hardware reset
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    // 1. CLEAR_ERRORS (0x0111) — clear any stale errors before init
    { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 2. SET_STANDBY (STDBY_XOSC = 0x01) — start crystal oscillator
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; rfWriteCmd(cmd, 3); }
    delay(5);

    // 3. SET_PACKET_TYPE FLRC (0x05)
    { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // 4. SET_RF_FREQUENCY — correct PLL divider formula
    //    frf = freq_Hz * 2^18 / XTAL_Hz
    uint32_t frf = (uint32_t)((FLRC_FREQ_MHZ * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    dualPrintf("frf=%lu (0x%06lX)", (unsigned long)frf, (unsigned long)frf);
    {
        uint8_t cmd[] = {
            0x02, 0x00,
            (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
        };
        rfWriteCmd(cmd, 5);
    }
    delay(1);

    // 5. SET_RX_PATH (0x0201) — HF path mandatory for 2.4 GHz
    //    byte0=0x01 (HF path), byte1=0x00 (no boost)
    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 6. CALIB_FRONT_END (0x0123) — image rejection calibration for 2.4 GHz
    //    freq/4 = 610, set HF_PATH bit (bit 15)
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

    // 7. CALIBRATE (0x0122) — defined bits only 0x5F (per TheClams reference)
    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
    delay(5);

    // 8. SET_FLRC_MOD_PARAMS (0x0248)
    //    brBw=0x00 (2600 kbps), (CR_1_0=0x02 << 4)|(BT_0_5=0x05) = 0x25
    { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x25 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 9. SET_FLRC_SYNCWORD (0x024C) — sync word 1
    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

    // 10. SET_FLRC_PACKET_PARAMS (0x0249)
    //     preamble=8 → index 2, syncWordLen=4, syncWordTx=1, syncMatch=1, fixed=1, crc=0
    //     byte0: ((2 & 0x0F) << 2) | (4/2) = 0x0C
    //     byte1: ((1 & 0x03) << 6) | ((1 & 0x07) << 3) | (1<<2) | 0 = 0x4C
    //     byte2-3: payloadLen = FLRC_PKT_SIZE (big-endian)
    {
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0C,  // preamble idx 2 (8 symbols, was 16) | syncLen 4/2=2
            0x4C,  // syncTx=1 | syncMatch=1 | fixed=1 | crc=0
            0x00, (uint8_t)FLRC_PKT_SIZE
        };
        rfWriteCmd(cmd, 6);
    }
    delay(1);

    // 11. SET_RX_TX_FALLBACK (Fs=0x03 per TheClams — keeps PLL warm)
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // 12. DIO function — DIO9 = IRQ output
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 13. DIO IRQ config — map RX_DONE (bit 18 = 0x00040000) to DIO9
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x04, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
    delay(1);

    // 14. Clear IRQ + enter continuous RX
    rfClearIrq();
    delay(1);
    rfSetRx();
    delay(2);

    // Verify
    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    // Status byte upper nibble: 0x05 = RX mode
    if ((st >> 4) == 0x05) {
        dualPrintln("RADIO_INIT_OK (RX mode)");
        return true;
    } else if (irq & 0x00020000) {
        dualPrintf("RADIO_INIT_WARN CMD_ERROR (St=0x%02X) — radio may still work", st);
        return true; // accept partial — radio entered RX despite CMD_ERROR before
    } else {
        dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
        return false;
    }
}

// ─── Statistics ──────────────────────────────────────────────────────
struct RxStats {
    uint32_t received;
    uint32_t unique;
    uint32_t duplicates;
    uint32_t lastSeq;
    uint32_t maxSeq;
    uint32_t totalSentByTx;
    uint32_t startMs;
    uint32_t elapsedMs;
    int32_t  rssiSum;
    int16_t  rssiMin;
    int16_t  rssiMax;
    uint16_t rssiCount;
    // Burst tracking — TX sends 500-pkt bursts with DEADBEEF end marker,
    // restarting seq at 0 for each burst. We must accumulate totals across
    // all bursts seen during the listen window, not just the last one.
    uint32_t burstCount;      // number of DEADBEEF markers seen this session
    uint32_t totalExpected;   // accumulated: sum of per-burst packet counts
    int8_t  noiseFloor;       // boot-time noise floor measurement (dBm)
};
static RxStats stats;
static volatile bool radioReady = false;
static int8_t bootNoiseFloor = -128;  // measured at boot, -128 = not yet measured

static void resetStats() {
    memset(&stats, 0, sizeof(stats));
    stats.lastSeq = 0xFFFFFFFF;
    stats.rssiMin  = 0;      // will be overwritten by first packet
    stats.rssiMax  = -128;   // will be overwritten by first packet
}

// ─── GPS time + sweep scheduler ──────────────────────────────────────
static GpsTimeModule gpsTime;
static SweepScheduler scheduler;

// Current runtime bitrate (updated by scheduler, used in RX output)
static uint16_t currentBitrateKbps = FLRC_BR;

// Helper: time source string for output
static const char* timeSrcStr() {
    switch (gpsTime.getSource()) {
        case TIME_GPS:    return "GPS";
        case TIME_MILLIS: return "MILLIS";
        default:          return "NONE";
    }
}

// ─── Receive session ─────────────────────────────────────────────────
static void runReceive() {
    if (!radioReady) { dualPrintln("ERR: radio not initialized"); return; }

    // Re-arm RX in case we were in another mode
    rfClearIrq();
    rfSetRx();
    delay(1);

    resetStats();
    stats.noiseFloor = bootNoiseFloor;
    stats.startMs = millis();
    uint32_t lastPktMs = millis();
    uint8_t buf[FLRC_PKT_SIZE];

    dualPrintln("RX_START");
    dualPrintln("pkt,seq");

    while (true) {
        // ─── GPS time + scheduler update (non-blocking) ──────────────
        // Called every loop iteration — if bitrate window changed, switch
        // the radio, reset per-window stats, and re-arm RX.
        gpsTime.update();
        if (scheduler.update()) {
            uint16_t newBitrate = scheduler.getCurrentBitrate();
            if (newBitrate != currentBitrateKbps) {
                dualPrintf("SWEEP_SWITCH idx=%d bitrate=%d→%d cycle=%d time_src=%s untilSwitch=%lums",
                           scheduler.getCurrentIndex(),
                           currentBitrateKbps, newBitrate,
                           scheduler.getCurrentCycle(), timeSrcStr(),
                           (unsigned long)scheduler.getTimeUntilSwitchMs());
                currentBitrateKbps = newBitrate;
                rfSwitchBitrate(currentBitrateKbps);

                // Reset per-window stats for clean measurement of new bitrate
                resetStats();
                stats.noiseFloor = bootNoiseFloor;
                stats.startMs = millis();
                lastPktMs = millis();

                // Re-arm RX after bitrate switch (radio is in STDBY after switch)
                rfClearIrq();
                rfSetRx();
            }
        }

        uint32_t now = millis();
        if ((now - stats.startMs) >= RX_LISTEN_MS) { dualPrintln("RX_DONE timeout"); break; }
        if (stats.received > 0 && (now - lastPktMs) >= RX_SILENCE_MS) {
            dualPrintln("RX_DONE silence"); break;
        }

        // Poll IRQ via GPIO (nanoseconds) — NOT SPI (microseconds, loses packets)
        // DIO9 = GP7. When RX_DONE fires, DIO9 goes HIGH.
        uint32_t irqMask = 1UL << PIN_IRQ;
        if (!(sio_hw->gpio_in & irqMask)) continue;  // no IRQ yet

        // READ FIFO IMMEDIATELY — before chip receives next packet
        rfReadFifo(buf, FLRC_PKT_SIZE);

        // Now clear FIFO + errors + re-arm RX (minimize dead time)
        { uint8_t cmd[] = { 0x01, 0x1E }; rfWriteCmd(cmd, 2); }  // CLEAR_RX_FIFO
        rfWaitBusy();
        rfClearIrq();
        rfSetRx();

        // Read packet RSSI (from last received packet's status)
        int8_t rssi = rfReadRssi();
        stats.rssiSum += rssi;
        stats.rssiCount++;
        if (rssi < stats.rssiMin) stats.rssiMin = rssi;
        if (rssi > stats.rssiMax) stats.rssiMax = rssi;

        // Extract big-endian seq
        uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                       ((uint32_t)buf[2] << 8)  | (uint32_t)buf[3];

#ifdef RX_DEBUG_HEX
        // Full 16-byte hex dump for first 5 packets
        if (stats.received < 5) {
            dualPrintf("PKT[%lu] RAW16: %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X %02X",
                (unsigned long)stats.received,
                buf[0], buf[1], buf[2], buf[3],
                buf[4], buf[5], buf[6], buf[7],
                buf[8], buf[9], buf[10], buf[11],
                buf[12], buf[13], buf[14], buf[15]);
        }
#endif

        // DEADBEEF end marker — TX burst boundary.
        // TX restarts seq at 0 for each burst, so we accumulate per-burst
        // totals across the entire listen window. Do NOT break out of the
        // receive loop — keep listening for more bursts. Only break on
        // timeout/silence. Do NOT count DEADBEEF itself in stats.received.
        if (buf[0] == 0xDE && buf[1] == 0xAD &&
            buf[2] == 0xBE && buf[3] == 0xEF) {
            uint32_t burstPackets = ((uint32_t)buf[4] << 24) | ((uint32_t)buf[5] << 16) |
                                    ((uint32_t)buf[6] << 8)  | (uint32_t)buf[7];
            stats.burstCount++;
            stats.totalExpected += burstPackets;
            stats.totalSentByTx = burstPackets;  // last burst's count (compat field)
            dualPrintf("BURST_END n=%lu bursts=%lu totalExpected=%lu",
                       (unsigned long)burstPackets,
                       (unsigned long)stats.burstCount,
                       (unsigned long)stats.totalExpected);
            // Reset per-burst seq tracker so first pkt of next burst isn't
            // flagged as a duplicate of the last pkt of this burst.
            stats.lastSeq = 0xFFFFFFFF;
            lastPktMs = millis();  // burst marker = recent activity (extends silence timer)
            continue;  // keep listening — only break on timeout/silence
        }

        stats.received++;
        if (stats.lastSeq != 0xFFFFFFFF && seq == stats.lastSeq) stats.duplicates++;
        else stats.unique++;
        stats.lastSeq = seq;
        if (seq > stats.maxSeq) stats.maxSeq = seq;
        lastPktMs = millis();

        if (stats.received <= 5 || (stats.received % PRINT_EVERY) == 0) {
            dualPrintf("PKT %lu seq=%lu rssi=%d", (unsigned long)stats.received,
                       (unsigned long)seq, (int)rssi);
            // Hex dump first 8 bytes of first 3 packets
            if (stats.received <= 3) {
                dualPrintf("  HEX: %02X %02X %02X %02X %02X %02X %02X %02X",
                    buf[0], buf[1], buf[2], buf[3],
                    buf[4], buf[5], buf[6], buf[7]);
            }
        }
    }

    if (stats.elapsedMs == 0) stats.elapsedMs = millis() - stats.startMs;

    // Print results
    uint32_t n = stats.received;
    // PER calculation — use accumulated burst totals from DEADBEEF markers.
    uint32_t total;
    if (stats.totalExpected > 0) {
        total = stats.totalExpected;
    } else if (stats.maxSeq > 0) {
        total = stats.maxSeq + 1;  // estimate: one burst's worth
    } else {
        total = 0;
    }
    uint32_t lost = (total > n) ? (total - n) : 0;
    float perPct = (total > 0) ? (100.0f * (float)lost / (float)total) : 0.0f;
    float tputKbps = (stats.elapsedMs > 0 && n > 0)
                     ? ((float)n * (float)FLRC_PKT_SIZE * 8.0f) / (float)stats.elapsedMs : 0.0f;
    float rssiAvg = (stats.rssiCount > 0) ? ((float)stats.rssiSum / (float)stats.rssiCount) : 0.0f;

    uint8_t sweepIdx = scheduler.getCurrentIndex();
    uint8_t sweepCycle = scheduler.getCurrentCycle();
    GpsTime gpsT = gpsTime.getTime();

    dualPrintln("=============================================");
    dualPrintf("  Received: %lu (unique %lu, dup %lu)", (unsigned long)n,
               (unsigned long)stats.unique, (unsigned long)stats.duplicates);
    dualPrintf("  TX sent:  %lu (est total %lu)",
               (unsigned long)stats.totalSentByTx, (unsigned long)total);
    dualPrintf("  Bursts detected: %lu", (unsigned long)stats.burstCount);
    dualPrintf("  Lost:     %lu (%.2f%%)", (unsigned long)lost, perPct);
    dualPrintf("  Elapsed:  %lu ms", (unsigned long)stats.elapsedMs);
    dualPrintf("  THROUGHPUT: %.1f kbps", tputKbps);
    if (stats.rssiCount > 0) {
        dualPrintf("  RSSI: avg=%.1f dBm min=%d dBm max=%d dBm (n=%d)",
                   rssiAvg, (int)stats.rssiMin, (int)stats.rssiMax, (int)stats.rssiCount);
    }
    dualPrintf("  Bitrate:  %d kbps (sweepIdx=%d cycle=%d time_src=%s)",
               currentBitrateKbps, sweepIdx, sweepCycle, timeSrcStr());
    dualPrintln("=============================================");
    dualPrintf("RESULT,rx=%lu,unique=%lu,lost=%lu,total=%lu,per=%.2f,elapsed_ms=%lu,throughput_kbps=%.1f,rssi_avg=%.1f,rssi_min=%d,rssi_max=%d,bursts=%lu,noise_floor=%d,bitrate=%d,sweepIdx=%d,cycle=%d,time_src=%s,utc_hhmmss=%02u%02u%02u",
               (unsigned long)n, (unsigned long)stats.unique, (unsigned long)lost,
               (unsigned long)total, perPct, (unsigned long)stats.elapsedMs, tputKbps,
               rssiAvg, (int)stats.rssiMin, (int)stats.rssiMax,
               (unsigned long)stats.burstCount, (int)stats.noiseFloor,
               currentBitrateKbps, sweepIdx, sweepCycle, timeSrcStr(),
               gpsT.hour, gpsT.minute, gpsT.second);
}

// ─── Config print ────────────────────────────────────────────────────
static void printConfig() {
    dualPrintln("=== FLRC RX SWEEP CONFIG ===");
    dualPrintf("  freq=%.1f MHz  BR=%d (initial, scheduler overrides)", FLRC_FREQ_MHZ, FLRC_BR);
    dualPrintf("  CR=uncoded  shaping=BT0.5  pktSize=%d", FLRC_PKT_SIZE);
    dualPrintf("  GPS pins: RX=GP%d TX=GP%d PPS=GP%d baud=%d",
               GPS_RX_PIN, GPS_TX_PIN, GPS_PPS_PIN, GPS_BAUD);
    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("  Status=0x%02X  IRQ=0x%08lX", st, (unsigned long)irq);
    dualPrintf("  radio: %s  listen=%dms  silence=%dms",
               radioReady ? "INIT" : "NOT_INIT", RX_LISTEN_MS, RX_SILENCE_MS);
    dualPrintf("  bitrate=%d kbps  sweepIdx=%d  cycle=%d  time_src=%s",
               currentBitrateKbps, scheduler.getCurrentIndex(),
               scheduler.getCurrentCycle(), timeSrcStr());
    dualPrintln("======================");
}

// ─── Command handling ────────────────────────────────────────────────
static char cmdBuf[64];
static size_t cmdLen = 0;

static void processCommand(const char *cmd) {
    if (strcmp(cmd, "RUN") == 0)      { runReceive(); }
    else if (strcmp(cmd, "CONFIG") == 0) { printConfig(); }
    else if (strcmp(cmd, "INIT") == 0)   { radioReady = rawInitRadio(); }
    else if (strcmp(cmd, "BOOTSEL") == 0) { Serial.println("REBOOT TO BOOTSEL"); delay(100); reset_usb_boot(0, 0); }
    else if (strcmp(cmd, "RESULTS") == 0) {
        if (stats.received > 0) {
            float tput = (stats.elapsedMs > 0)
                ? ((float)stats.received * FLRC_PKT_SIZE * 8.0f) / stats.elapsedMs : 0;
            dualPrintf("RESULT rx=%lu throughput=%.1fkbps bitrate=%d time_src=%s",
                       (unsigned long)stats.received, tput,
                       currentBitrateKbps, timeSrcStr());
        } else { dualPrintln("No results yet"); }
    }
    else if (strcmp(cmd, "NOISE") == 0) {
        // Measure noise floor — TX should be OFF for accurate reading
        int32_t sum = 0;
        for (int i = 0; i < 10; i++) {
            sum += rfReadRssiInst();
            delay(10);
        }
        int8_t avg = (int8_t)(sum / 10);
        dualPrintf("NOISE_FLOOR rssi_inst=%d dBm (avg of 10, bitrate=%d)", (int)avg, currentBitrateKbps);
    }
    else if (strcmp(cmd, "HELP") == 0) {
        dualPrintln("Commands: RUN CONFIG INIT RESULTS NOISE HELP");
    }
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(2000);  // CRITICAL: give TinyUSB time to enumerate
    Serial.println("BOOT RX SWEEP");
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

    dualPrintln();
    dualPrintln("=== RP2040 FLRC RAW RX (SWEEP) ===");
    dualPrintln("Raw SPI init (no RadioLib) + adaptive bitrate sweep");
    dualPrintf("GPS pins: RX=GP%d TX=GP%d PPS=GP%d baud=%d",
               GPS_RX_PIN, GPS_TX_PIN, GPS_PPS_PIN, GPS_BAUD);

    // Initialize SPI bus + GPIO pins BEFORE radio init
    Serial.println("PRE_SPI");
    spiRf.begin();
    Serial.println("POST_SPI");
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    Serial.println("PRE_INIT");
    radioReady = rawInitRadio();
    Serial.println("POST_INIT");

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        dualPrintln("Auto-start RX in 8 seconds...");
        delay(8000); // give bridge time to connect

        // Measure noise floor before entering RX (TX should be OFF)
        dualPrintln("MEASURING NOISE FLOOR...");
        {
            int32_t sum = 0;
            for (int i = 0; i < 10; i++) {
                sum += rfReadRssiInst();
                delay(10);
            }
            bootNoiseFloor = (int8_t)(sum / 10);
            stats.noiseFloor = bootNoiseFloor;
            dualPrintf("NOISE_FLOOR=%d dBm (measured at boot, n=10)", (int)bootNoiseFloor);
        }

        // ─── GPS time + sweep scheduler init ─────────────────────────
        gpsTime.begin(GPS_RX_PIN, GPS_TX_PIN, GPS_PPS_PIN, GPS_BAUD);
        delay(10);
        gpsTime.update();  // First NMEA read (likely empty, but prime the parser)

        scheduler.begin(&gpsTime);
        delay(5);

        // Sync radio to scheduler's initial bitrate window.
        // The scheduler may start mid-cycle (especially with GPS lock),
        // so we must switch the radio to match.
        currentBitrateKbps = scheduler.getCurrentBitrate();
        if (currentBitrateKbps != FLRC_BR) {
            dualPrintf("SWEEP_INIT switching bitrate %d→%d (scheduler window %d)",
                       FLRC_BR, currentBitrateKbps, scheduler.getCurrentIndex());
            rfSwitchBitrate(currentBitrateKbps);
        } else {
            dualPrintf("SWEEP_INIT bitrate=%d matches scheduler window %d",
                       currentBitrateKbps, scheduler.getCurrentIndex());
        }

        // Print schedule + current state
        scheduler.printStatus();

        dualPrintln("SWEEP RX STARTING — listening for TX");
    } else {
        dualPrintln("INIT FAILED — type INIT to retry");
    }
}

void loop() {
    // ─── GPS time + scheduler update (non-blocking) ──────────────────
    // Check between RX sessions too — bitrate may change during the 2s pause.
    gpsTime.update();
    if (radioReady && scheduler.update()) {
        uint16_t newBitrate = scheduler.getCurrentBitrate();
        if (newBitrate != currentBitrateKbps) {
            dualPrintf("SWEEP_SWITCH idx=%d bitrate=%d→%d cycle=%d time_src=%s untilSwitch=%lums",
                       scheduler.getCurrentIndex(),
                       currentBitrateKbps, newBitrate,
                       scheduler.getCurrentCycle(), timeSrcStr(),
                       (unsigned long)scheduler.getTimeUntilSwitchMs());
            currentBitrateKbps = newBitrate;
            rfSwitchBitrate(currentBitrateKbps);
            // runReceive() will rfClearIrq + rfSetRx + resetStats at its start
        }
    }

    // Auto-restart RX continuously (ESP32 bridge can't forward serial commands)
    if (radioReady) {
        runReceive();
        delay(2000); // brief pause between windows
    } else {
        // Heartbeat + retry init
        static unsigned long lastHB = 0;
        if (millis() - lastHB > 2000) {
            lastHB = millis();
            Serial1.println("RX DEAD - retrying init");
            Serial1.flush();
        }
        radioReady = rawInitRadio();
        delay(1000);
    }
}
