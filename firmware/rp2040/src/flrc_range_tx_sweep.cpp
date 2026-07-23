/*
 * flrc_range_tx_sweep.cpp — Adaptive bitrate sweep TX for range testing
 *
 * Based on flrc_range_tx_auto.cpp (proven 2600 kbps, 0% loss).
 * Auto-starts TX on boot — NO serial commands needed.
 *
 * New behavior (vs tx_auto):
 * - Sweeps through 4 FLRC bitrates (2600/1300/650/325 kbps) on a 12-min cycle
 * - Scheduler syncs to GPS time (UTC) if GPS lock available, else millis fallback
 * - Calls rfSwitchBitrate() at each window boundary (STDBY→MOD_PARAMS→CALIB→CLR_IRQ)
 * - All output lines include bitrate/sweepIdx/cycle/time_src fields
 *
 * TX behavior (unchanged from tx_auto):
 * - 3s LED blink countdown on boot (time to walk away)
 * - Transmits 500-packet bursts, pauses 2s, repeat forever
 * - DEADBEEF marker at end of each burst (RX knows burst done)
 * - LED on during TX, off during pause
 * - Heartbeat on Serial1 every 3s
 *
 * Config is compile-time only (change via reflash if needed):
 *   FREQ=2440, PKTLEN=127, POWER=12 dBm, COUNT=500
 *   Bitrate is DYNAMIC — set by SweepScheduler
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13
 *       GPS_RX=GP1 GPS_TX=GP0 GPS_PPS=GP9
 *       LED=GP25 LED_ALT=GP16
 */

#include <Arduino.h>
#include <SPI.h>
#include "gps_time.h"
#include "sweep_scheduler.h"
#include "radio.h"          // rfSwitchBitrate() declaration

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

#define SPI_FREQ_HZ     20000000UL
#define XTAL_MHZ        52.0f

// ─── Compile-time config ─────────────────────────────────────────────
#define TX_FREQ_MHZ     2440.0f
#ifndef TX_BITRATE_KBPS
#define TX_BITRATE_KBPS 2600    // Initial bitrate (overridden by scheduler)
#endif
#define TX_PKT_SIZE     127
#ifndef TX_POWER_DBM
#define TX_POWER_DBM    12.5f
#endif
#define TX_PKT_COUNT    500
#define TX_PAUSE_MS     2000

// Sync word — MUST match RX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// Pre-allocated combined buffer for single-batch FIFO write
// Header (2 bytes) + payload (255 bytes) = 257 bytes in ONE transfer call
static uint8_t fifoCmd[2 + 255];
// Dummy RX buffer for write-only transfers (nullptr crashes on some cores)
static uint8_t spiRxJunk[257];

static volatile bool radioReady = false;

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

static void rfSetTx() {
    uint8_t cmd[5] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
    rfWriteCmd(cmd, 5);
}

static void rfWriteTxFifo(const uint8_t *data, size_t len) {
    fifoCmd[0] = 0x00;  // header MSB
    fifoCmd[1] = 0x02;  // header LSB (WRITE_TX_FIFO)
    memcpy(fifoCmd + 2, data, len);

    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(fifoCmd, spiRxJunk, 2 + len);  // SINGLE BATCH — continuous SCK
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfClearTxFifo() {
    uint8_t cmd[] = { 0x01, 0x1F };
    rfWriteCmd(cmd, 2);
}

// ─── Runtime parameter setters ───────────────────────────────────────
static void rfSetFreq(float mhz) {
    uint32_t frf = (uint32_t)((mhz * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    uint8_t cmd[] = {
        0x02, 0x00,
        (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
    };
    rfWriteCmd(cmd, 5);
}

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

static void rfSetTxPower(float dbm) {
    uint8_t powerRaw = (uint8_t)(dbm * 2.0f + 0.5f);
    uint8_t cmd[] = { 0x02, 0x03, powerRaw, 0x04 };
    rfWriteCmd(cmd, 4);
}

static void rfSetPktSize(uint16_t size) {
    uint8_t cmd[] = {
        0x02, 0x49,
        0x0C, 0x4C,
        (uint8_t)(size >> 8), (uint8_t)(size & 0xFF)
    };
    rfWriteCmd(cmd, 6);
}

// ─── Runtime bitrate switching ───────────────────────────────────────
// Implements rfSwitchBitrate() declared in radio.h using this firmware's
// own SPI helpers (SPIClassRP2040 at 20 MHz). The radio.cpp version uses
// MbedSPI with different SPI backend — we can't link both, so we provide
// the implementation here.
//
// Sequence: STDBY_RC → MOD_PARAMS → CALIBRATE → CLEAR_IRQ
void rfSwitchBitrate(uint16_t newBitrate) {
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

// ─── GPS time + sweep scheduler ──────────────────────────────────────
static GpsTimeModule gpsTime;
static SweepScheduler scheduler;

// Current runtime bitrate (updated by scheduler, used in TX output)
static uint16_t currentBitrateKbps = TX_BITRATE_KBPS;

// Helper: time source string for output
static const char* timeSrcStr() {
    switch (gpsTime.getSource()) {
        case TIME_GPS:    return "GPS";
        case TIME_MILLIS: return "MILLIS";
        default:          return "NONE";
    }
}

// ─── Dual output ─────────────────────────────────────────────────────
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

// ─── Full radio init ─────────────────────────────────────────────────
static bool rawInitRadio() {
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x28, 0x01 }; rfWriteCmd(cmd, 3); }
    delay(5);
    { uint8_t cmd[] = { 0x02, 0x07, 0x05 }; rfWriteCmd(cmd, 3); }
    delay(1);

    rfSetFreq(TX_FREQ_MHZ);
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    uint16_t feFreq = (uint16_t)((TX_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
    {
        uint8_t cmd[] = {
            0x01, 0x23,
            (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00
        };
        rfWriteCmd(cmd, 10);
    }
    delay(5);

    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
    delay(5);

    rfSetBitrate(TX_BITRATE_KBPS);
    delay(5);

    // Recalibrate after bitrate change (bandwidth changes with bitrate)
    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
    delay(5);

    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

    rfSetPktSize(TX_PKT_SIZE);
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);
    rfSetTxPower(TX_POWER_DBM);
    delay(1);
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
    delay(1);

    rfClearIrq();
    delay(1);

    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

    if ((st >> 4) == 0x04 || (st >> 4) == 0x07 || (irq & 0x00020000)) {
        dualPrintln("RADIO_INIT_OK");
        return true;
    }
    dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

// ─── TX burst ────────────────────────────────────────────────────────
static uint32_t burstNum = 0;

static void runTransmit() {
    if (!radioReady) return;

    uint16_t pktSize = TX_PKT_SIZE;
    uint16_t count = TX_PKT_COUNT;
    uint8_t  sweepIdx = scheduler.getCurrentIndex();
    uint8_t  sweepCycle = scheduler.getCurrentCycle();
    GpsTime  gpsT = gpsTime.getTime();

    digitalWrite(PIN_LED, HIGH);
    digitalWrite(PIN_LED_ALT, HIGH);

    uint32_t burstStartMs = millis();
    dualPrintf("BURST %lu START uptime=%lums count=%d bitrate=%d sweepIdx=%d cycle=%d time_src=%s utc=%02u%02u%02u",
               (unsigned long)burstNum, (unsigned long)burstStartMs, count,
               currentBitrateKbps, sweepIdx, sweepCycle, timeSrcStr(),
               gpsT.hour, gpsT.minute, gpsT.second);

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

        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 500000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
        }

        if (irqFired) txDoneCount++;
        else txTimeoutCount++;
    }

    // DEADBEEF end marker — RX reads total packet count from this
    pkt[0] = 0xDE; pkt[1] = 0xAD; pkt[2] = 0xBE; pkt[3] = 0xEF;
    pkt[4] = (uint8_t)(count >> 24);
    pkt[5] = (uint8_t)(count >> 16);
    pkt[6] = (uint8_t)(count >> 8);
    pkt[7] = (uint8_t)(count & 0xFF);
    rfClearTxFifo();
    rfWriteTxFifo(pkt, pktSize);
    rfSetTx();
    delay(5);

    uint32_t elapsed = millis() - startMs;
    float tput = ((float)count * pktSize * 8.0f) / elapsed;

    dualPrintf("BURST %lu DONE fired=%lu to=%lu elapsed=%lums tput=%.1fkbps bitrate=%d sweepIdx=%d cycle=%d time_src=%s",
               (unsigned long)burstNum,
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
               (unsigned long)elapsed, tput,
               currentBitrateKbps, sweepIdx, sweepCycle, timeSrcStr());
    dualPrintf("RANGE_RESULT_TX,burst=%lu,sent=%d,fired=%lu,timeout=%lu,elapsed_ms=%lu,throughput_kbps=%.1f,freq=%.1f,bitrate=%d,power=%.1f,pktSize=%d,uptime_ms=%lu,sweepIdx=%d,cycle=%d,time_src=%s,utc_hhmmss=%02u%02u%02u",
               (unsigned long)burstNum, count,
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
               (unsigned long)elapsed, tput,
               TX_FREQ_MHZ, currentBitrateKbps, TX_POWER_DBM, TX_PKT_SIZE,
               (unsigned long)burstStartMs,
               sweepIdx, sweepCycle, timeSrcStr(),
               gpsT.hour, gpsT.minute, gpsT.second);

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
    dualPrintln();
    dualPrintln("=== RP2040 FLRC RANGE TX (SWEEP) ===");
    dualPrintf("Config: freq=%.1f pktSize=%d power=%.1f count=%d",
               TX_FREQ_MHZ, TX_PKT_SIZE, TX_POWER_DBM, TX_PKT_COUNT);
    dualPrintf("GPS pins: RX=GP%d TX=GP%d PPS=GP%d baud=%d",
               GPS_RX_PIN, GPS_TX_PIN, GPS_PPS_PIN, GPS_BAUD);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);

    // 3s countdown blink — time to walk away
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
        if (currentBitrateKbps != TX_BITRATE_KBPS) {
            dualPrintf("SWEEP_INIT switching bitrate %d→%d (scheduler window %d)",
                       TX_BITRATE_KBPS, currentBitrateKbps, scheduler.getCurrentIndex());
            rfSwitchBitrate(currentBitrateKbps);
        } else {
            dualPrintf("SWEEP_INIT bitrate=%d matches scheduler window %d",
                       currentBitrateKbps, scheduler.getCurrentIndex());
        }

        // Print schedule + current state
        scheduler.printStatus();

        dualPrintln("SWEEP TX STARTING — unplug and walk");
    } else {
        dualPrintln("INIT FAILED — retrying...");
        delay(2000);
        radioReady = rawInitRadio();
        if (radioReady) {
            digitalWrite(PIN_LED_ALT, HIGH);
            gpsTime.begin(GPS_RX_PIN, GPS_TX_PIN, GPS_PPS_PIN, GPS_BAUD);
            scheduler.begin(&gpsTime);
            currentBitrateKbps = scheduler.getCurrentBitrate();
            if (currentBitrateKbps != TX_BITRATE_KBPS) {
                rfSwitchBitrate(currentBitrateKbps);
            }
            scheduler.printStatus();
            dualPrintln("SWEEP TX STARTING (2nd init) — unplug and walk");
        } else {
            dualPrintln("INIT FAILED TWICE — stuck");
        }
    }
}

static unsigned long lastHB = 0;

void loop() {
    // ─── GPS time + scheduler update (non-blocking) ──────────────────
    gpsTime.update();

    if (radioReady && scheduler.update()) {
        // Bitrate window changed — switch radio
        uint16_t newBitrate = scheduler.getCurrentBitrate();
        if (newBitrate != currentBitrateKbps) {
            dualPrintf("SWEEP_SWITCH idx=%d bitrate=%d→%d cycle=%d time_src=%s untilSwitch=%lums",
                       scheduler.getCurrentIndex(),
                       currentBitrateKbps, newBitrate,
                       scheduler.getCurrentCycle(), timeSrcStr(),
                       (unsigned long)scheduler.getTimeUntilSwitchMs());
            currentBitrateKbps = newBitrate;
            rfSwitchBitrate(currentBitrateKbps);
        }
    }

    if (radioReady) {
        runTransmit();
        delay(TX_PAUSE_MS);
        // Heartbeat to keep USB CDC alive (prevents 1200 baud recovery failure)
        if (millis() - lastHB > 3000) {
            lastHB = millis();
            GpsTime gpsT = gpsTime.getTime();
            dualPrintf("[TX HB %lus] burst=%d bitrate=%d sweepIdx=%d cycle=%d time_src=%s utc=%02u%02u%02u",
                       millis() / 1000, burstNum,
                       currentBitrateKbps,
                       scheduler.getCurrentIndex(),
                       scheduler.getCurrentCycle(),
                       timeSrcStr(),
                       gpsT.hour, gpsT.minute, gpsT.second);
        }
    } else {
        // Blink SOS if radio dead + heartbeat so USB CDC stays alive
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(500);
        dualPrintf("[TX DEAD %lus]", millis() / 1000);
    }
}
