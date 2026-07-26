/*
<<<<<<< HEAD
 * DEPRECATED — DO NOT USE. This file uses SX1280 raw SPI commands (wrong chip).
 * Our chip is LR2021 (Gen 4), NOT SX1280. See ADR-017.
 * Use firmware/rp2040-flrc-max/ instead (RadioLib LR2021 driver).
 *
 * flrc_range_rx_gps.cpp — FLRC RX with RSSI + GPS extraction
 *
 * Backward compatible: parses GPS fields from TX payload if present.
 * If TX has no GPS (fix=0), still outputs seq + rssi normally.
 *
 * Output per packet:
 *   With GPS:    PKT,n,seq,rssi,lat,lon,alt,sats,hdop,fix
 *   Without GPS: PKT,n,seq,rssi,0,0,0,0,0,0
 *
 * Based on flrc_range_rx_auto.cpp (verified 2026-07-22).
=======
 * flrc_range_rx_gps.cpp — Autonomous RX with GPS distance calc
 *
 * Based on flrc_range_rx_auto.cpp.
 * Extracts GPS coords from received TX packets, computes distance.
 *
 * Behavior:
 * - 2s LED blink on boot
 * - Auto-starts RX listen, 30s windows, re-arms forever
 * - Extracts GPS from bytes 4-19 of each packet:
 *     bytes 4-7:   latitude  (float)
 *     bytes 8-11:  longitude (float)
 *     bytes 12-13: num_sats  (uint16_t)
 *     bytes 14-15: fix_valid (uint16_t)
 *     bytes 16-19: gps_time  (uint32_t)
 * - Computes Haversine distance from base station position
 * - Logs per-packet: seq, rssi, lat, lon, distance_m
 * - LED blinks on each packet
 *
 * Base station GPS: set via serial command BASE lat lon, or
 * hardcoded in BASE_LAT/BASE_LON below.
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       LED=GP25 LED_ALT=GP16
>>>>>>> range-tests
 */

#include <Arduino.h>
#include <SPI.h>
<<<<<<< HEAD
=======
#include <math.h>
>>>>>>> range-tests
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

<<<<<<< HEAD
// ─── FLRC Config ─────────────────────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_PKT_SIZE   255
#define SPI_FREQ_HZ     16000000UL
#define XTAL_MHZ        52.0f

=======
#define SPI_FREQ_HZ     20000000UL
#define XTAL_MHZ        52.0f

// ─── Config ──────────────────────────────────────────────────────────
#define RX_FREQ_MHZ     2440.0f
#define RX_BITRATE_KBPS 2600
#define RX_PKT_SIZE     255
#define RX_LISTEN_MS    30000
#define RX_SILENCE_MS   3000
#define PRINT_EVERY     100

// Base station position (set before test, or via serial BASE lat lon)
static float BASE_LAT = 0.0f;
static float BASE_LON = 0.0f;
static bool baseSet = false;

// Sync word
>>>>>>> range-tests
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

<<<<<<< HEAD
=======
// ─── Haversine distance ──────────────────────────────────────────────
static float haversineM(float lat1, float lon1, float lat2, float lon2) {
    const float R = 6371000.0f;  // Earth radius in meters
    float dLat = (lat2 - lat1) * M_PI / 180.0f;
    float dLon = (lon2 - lon1) * M_PI / 180.0f;
    float a = sinf(dLat/2) * sinf(dLat/2) +
              cosf(lat1 * M_PI / 180.0f) * cosf(lat2 * M_PI / 180.0f) *
              sinf(dLon/2) * sinf(dLon/2);
    float c = 2.0f * atan2f(sqrtf(a), sqrtf(1.0f - a));
    return R * c;
}

>>>>>>> range-tests
// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

<<<<<<< HEAD
=======
// Dummy RX buffer for write-only transfers (nullptr crashes on some cores)
static uint8_t spiRxJunk[257];

static volatile bool radioReady = false;

>>>>>>> range-tests
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
<<<<<<< HEAD
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
=======
    spiRf.transfer((uint8_t*)buf, spiRxJunk, len);
>>>>>>> range-tests
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfReadFifo(uint8_t *buf, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00); spiRf.transfer(0x01);
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
    uint8_t cmd[5] = { 0x02, 0x0C, 0xFF, 0xFF, 0xFF };
    rfWriteCmd(cmd, 5);
}

<<<<<<< HEAD
=======
// RSSI via GET_FLRC_PACKET_STATUS (0x024B) — 9-bit assembly (not SX1280 0x0104)
>>>>>>> range-tests
static int8_t rfReadRssi() {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
<<<<<<< HEAD
    spiRf.transfer(0x01); spiRf.transfer(0x04);
=======
    spiRf.transfer(0x02); spiRf.transfer(0x4B); // GET_FLRC_PACKET_STATUS
>>>>>>> range-tests
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    rfWaitBusy();

<<<<<<< HEAD
    uint8_t buf[4];
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    for (int i = 0; i < 4; i++) buf[i] = spiRf.transfer(0x00);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
    // SX1280/LR2021: PACKET_STATUS buf[0]=status, buf[1]=RSSI (unsigned, negate for dBm)
    // RadioLib negates this value: RSSI_dBm = -buf[1]
    return -(int8_t)buf[1];
}

// ─── Dual output ─────────────────────────────────────────────────────
=======
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
        case 325: brBw = 0x06; break;  // FLRC_BR_325
        case 260:  brBw = 0x07; break;  // FLRC_BR_260
        default:   brBw = 0x00; break;
    }
    uint8_t cmd[] = { 0x02, 0x48, brBw, 0x25 };
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

// ─── Output ──────────────────────────────────────────────────────────
static void dualPrint(const char *s) { Serial.print(s); Serial1.print(s); }
static void dualPrintln(const char *s) { Serial.println(s); Serial1.println(s); }

>>>>>>> range-tests
static void dualPrintf(const char *fmt, ...) {
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.println(buf);
    Serial1.println(buf);
}

<<<<<<< HEAD
// ─── Raw SPI Init ────────────────────────────────────────────────────
=======
// ─── Radio init ──────────────────────────────────────────────────────
>>>>>>> range-tests
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

<<<<<<< HEAD
    uint32_t frf = (uint32_t)((FLRC_FREQ_MHZ * 1e6 * (double)(1ULL << 18)) / (XTAL_MHZ * 1e6));
    {
        uint8_t cmd[] = {
            0x02, 0x00,
            (uint8_t)(frf >> 16), (uint8_t)(frf >> 8), (uint8_t)(frf & 0xFF)
        };
        rfWriteCmd(cmd, 5);
    }
=======
    rfSetFreq(RX_FREQ_MHZ);
>>>>>>> range-tests
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

<<<<<<< HEAD
    uint16_t feFreq = (uint16_t)((FLRC_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
=======
    uint16_t feFreq = (uint16_t)((RX_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
>>>>>>> range-tests
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
<<<<<<< HEAD
    { uint8_t cmd[] = { 0x02, 0x48, 0x00, 0x25 }; rfWriteCmd(cmd, 4); }
    delay(1);
=======

    rfSetBitrate(RX_BITRATE_KBPS);
    delay(5);

    // Recalibrate after bitrate change (bandwidth changes with bitrate)
    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
    delay(5);
>>>>>>> range-tests

    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

<<<<<<< HEAD
    {
        uint8_t cmd[] = { 0x02, 0x49, 0x0C, 0x4C, 0x00, (uint8_t)FLRC_PKT_SIZE };
        rfWriteCmd(cmd, 6);
    }
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);
=======
    rfSetPktSize(RX_PKT_SIZE);
    delay(1);

>>>>>>> range-tests
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);
<<<<<<< HEAD
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
=======
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x04, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
>>>>>>> range-tests
    delay(1);

    rfClearIrq();
    delay(1);
<<<<<<< HEAD
=======
    rfSetRx();
    delay(2);
>>>>>>> range-tests

    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("INIT Status=0x%02X IRQ=0x%08lX", st, (unsigned long)irq);

<<<<<<< HEAD
    if ((st >> 4) == 0x04 || (st >> 4) == 0x07 || (irq & 0x00020000)) {
        dualPrintf("RADIO_INIT_OK");
        return true;
    }
    dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

// ─── State ───────────────────────────────────────────────────────────
static volatile bool radioReady = false;
static uint32_t totalReceived = 0;

// ─── Extract GPS from packet ─────────────────────────────────────────
struct PacketGps {
    int32_t  lat1e7;
    int32_t  lon1e7;
    int16_t  altMeters;
    uint8_t  satellites;
    uint8_t  hdopX10;
    uint8_t  fix;
};

static PacketGps extractGps(const uint8_t *buf) {
    PacketGps g;
    g.lat1e7 = ((int32_t)buf[8] << 24) | ((int32_t)buf[9] << 16) |
               ((int32_t)buf[10] << 8) | (int32_t)buf[11];
    g.lon1e7 = ((int32_t)buf[12] << 24) | ((int32_t)buf[13] << 16) |
               ((int32_t)buf[14] << 8) | (int32_t)buf[15];
    g.altMeters = (int16_t)(((uint16_t)buf[16] << 8) | buf[17]);
    g.satellites = buf[18];
    g.hdopX10 = buf[19];
    g.fix = buf[24];
    return g;
}

// ─── Continuous RX ───────────────────────────────────────────────────
static void runReceiveContinuous() {
    if (!radioReady) { dualPrintf("ERR: radio not initialized"); return; }

    uint8_t buf[FLRC_PKT_SIZE];
    dualPrintf("RX_LISTEN_START");
    rfSetRx();

    while (true) {
        uint32_t irq = rfReadIrqStatus();
        if (!(irq & 0x00040000)) {
            // No packet — check serial
            static char cmdBuf[64];
            static size_t cmdLen = 0;
            while (Serial1.available()) {
                char c = (char)Serial1.read();
                if (c == '\n' || c == '\r') {
                    if (cmdLen > 0) {
                        cmdBuf[cmdLen] = '\0';
                        if (strcmp(cmdBuf, "STATS") == 0) {
                            dualPrintf("STATS rx=%lu", (unsigned long)totalReceived);
                        }
                        cmdLen = 0;
                    }
                } else if (cmdLen < sizeof(cmdBuf) - 1) {
                    cmdBuf[cmdLen++] = c;
                }
            }
            continue;
        }

        int8_t rssi = rfReadRssi();
        rfReadFifo(buf, FLRC_PKT_SIZE);
=======
    if ((st >> 4) == 0x05) {
        dualPrintln("RADIO_INIT_OK (RX mode)");
        return true;
    } else if (irq & 0x00020000) {
        dualPrintf("RADIO_INIT_WARN CMD_ERROR (St=0x%02X)", st);
        return true;
    } else {
        dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
        return false;
    }
}

// ─── Extract GPS from packet ─────────────────────────────────────────
static void extractGPS(const uint8_t *buf, float *lat, float *lon,
                       uint16_t *sats, bool *fix, uint32_t *timeSec) {
    memcpy(lat, &buf[4], 4);
    memcpy(lon, &buf[8], 4);
    *sats = ((uint16_t)buf[12] << 8) | buf[13];
    *fix = (buf[15] == 1);
    *timeSec = ((uint32_t)buf[16] << 24) | ((uint32_t)buf[17] << 16) |
               ((uint32_t)buf[18] << 8) | (uint32_t)buf[19];
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
    // GPS tracking
    float    lastLat;
    float    lastLon;
    float    maxDistance;
    float    minDistance;
    uint16_t gpsPktCount;  // packets with valid GPS
};
static RxStats stats;

static void resetStats() {
    memset(&stats, 0, sizeof(stats));
    stats.lastSeq = 0xFFFFFFFF;
    stats.rssiMin = 0;
    stats.rssiMax = -128;
    stats.maxDistance = 0;
    stats.minDistance = 999999.0f;
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
    uint16_t pktSize = RX_PKT_SIZE;
    uint8_t buf[256];

    dualPrintf("RX_WINDOW %lu START uptime=%lums listen=%dms",
               (unsigned long)windowNum, (unsigned long)stats.startMs, RX_LISTEN_MS);

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

        // Hardware pin poll — matches proven LR2021Raw.h receive()
        if (digitalRead(PIN_IRQ) == LOW) continue;

        rfReadFifo(buf, pktSize);
        int8_t rssi = rfReadRssi();
        stats.rssiSum += rssi;
        stats.rssiCount++;
        if (rssi < stats.rssiMin) stats.rssiMin = rssi;
        if (rssi > stats.rssiMax) stats.rssiMax = rssi;
>>>>>>> range-tests

        { uint8_t cmd[] = { 0x01, 0x1E }; rfWriteCmd(cmd, 2); }
        rfWaitBusy();
        { uint8_t cmd[] = { 0x01, 0x11, 0x00, 0x00 }; rfWriteCmd(cmd, 4); }
        rfClearIrq();
        rfSetRx();

        uint32_t seq = ((uint32_t)buf[0] << 24) | ((uint32_t)buf[1] << 16) |
                       ((uint32_t)buf[2] << 8)  | (uint32_t)buf[3];

<<<<<<< HEAD
        PacketGps g = extractGps(buf);

        totalReceived++;

        // Output: PKT,n,seq,rssi,lat,lon,alt,sats,hdop,fix
        dualPrintf("PKT,%lu,%lu,%d,%ld,%ld,%d,%d,%d,%d",
                   (unsigned long)totalReceived, (unsigned long)seq, (int)rssi,
                   (long)g.lat1e7, (long)g.lon1e7, (int)g.altMeters,
                   (int)g.satellites, (int)g.hdopX10, (int)g.fix);

        if (totalReceived % 100 == 0) {
            digitalWrite(PIN_LED, HIGH); delayMicroseconds(50); digitalWrite(PIN_LED, LOW);
        }
=======
        // DEADBEEF end marker
        if (buf[0] == 0xDE && buf[1] == 0xAD &&
            buf[2] == 0xBE && buf[3] == 0xEF) {
            stats.totalSentByTx = ((uint32_t)buf[4] << 24) | ((uint32_t)buf[5] << 16) |
                                  ((uint32_t)buf[6] << 8)  | (uint32_t)buf[7];
            stats.elapsedMs = millis() - stats.startMs;
            dualPrintln("RX_END DEADBEEF");
            break;
        }

        stats.received++;
        if (stats.lastSeq != 0xFFFFFFFF && seq == stats.lastSeq) stats.duplicates++;
        else stats.unique++;
        stats.lastSeq = seq;
        if (seq > stats.maxSeq) stats.maxSeq = seq;
        lastPktMs = millis();

        // Extract GPS
        float pktLat, pktLon;
        uint16_t pktSats;
        bool pktFix;
        uint32_t pktTime;
        extractGPS(buf, &pktLat, &pktLon, &pktSats, &pktFix, &pktTime);

        float distM = 0;
        if (pktFix && baseSet) {
            distM = haversineM(BASE_LAT, BASE_LON, pktLat, pktLon);
            if (distM > stats.maxDistance) stats.maxDistance = distM;
            if (distM < stats.minDistance) stats.minDistance = distM;
            stats.lastLat = pktLat;
            stats.lastLon = pktLon;
            stats.gpsPktCount++;
        }

        digitalWrite(PIN_LED, HIGH);
        delayMicroseconds(50);
        digitalWrite(PIN_LED, LOW);

        if (stats.received <= 5 || (stats.received % PRINT_EVERY) == 0) {
            if (pktFix && baseSet) {
                dualPrintf("PKT %lu seq=%lu rssi=%d uptime=%lums lat=%.5f lon=%.5f dist=%.1fm sats=%d",
                           (unsigned long)stats.received, (unsigned long)seq, rssi,
                           (unsigned long)millis(), pktLat, pktLon, distM, pktSats);
            } else {
                dualPrintf("PKT %lu seq=%lu rssi=%d uptime=%lums gps=%s",
                           (unsigned long)stats.received, (unsigned long)seq, rssi,
                           (unsigned long)millis(), pktFix ? "nofix" : "noGps");
            }
        }
    }

    if (stats.elapsedMs == 0) stats.elapsedMs = millis() - stats.startMs;

    uint32_t n = stats.received;
    uint32_t total = stats.totalSentByTx > 0 ? stats.totalSentByTx : (stats.maxSeq + 1);
    uint32_t lost = (total > n) ? (total - n) : 0;
    float perPct = (total > 0) ? (100.0f * (float)lost / (float)total) : 0.0f;
    float tputKbps = (stats.elapsedMs > 0 && n > 0)
                     ? ((float)n * (float)pktSize * 8.0f) / (float)stats.elapsedMs : 0.0f;
    float rssiAvg = (stats.rssiCount > 0)
                    ? (float)stats.rssiSum / (float)stats.rssiCount : 0.0f;

    dualPrintln("=============================================");
    dualPrintf("  Window:   %lu", (unsigned long)windowNum);
    dualPrintf("  Received: %lu (unique %lu, dup %lu)", (unsigned long)n,
               (unsigned long)stats.unique, (unsigned long)stats.duplicates);
    dualPrintf("  TX sent:  %lu", (unsigned long)stats.totalSentByTx);
    dualPrintf("  Lost:     %lu (%.2f%%)", (unsigned long)lost, perPct);
    dualPrintf("  Elapsed:  %lu ms", (unsigned long)stats.elapsedMs);
    dualPrintf("  THROUGHPUT: %.1f kbps", tputKbps);
    if (stats.rssiCount > 0) {
        dualPrintf("  RSSI: avg=%.1f dBm min=%d dBm max=%d dBm (n=%d)",
                   rssiAvg, stats.rssiMin, stats.rssiMax, stats.rssiCount);
    }
    if (stats.gpsPktCount > 0) {
        dualPrintf("  GPS: %d pkts with fix, dist min=%.1f max=%.1f m",
                   stats.gpsPktCount, stats.minDistance, stats.maxDistance);
        dualPrintf("  Last GPS: lat=%.5f lon=%.5f", stats.lastLat, stats.lastLon);
    }
    dualPrintln("=============================================");

    dualPrintf("RANGE_RESULT_RX,window=%lu,rx=%lu,unique=%lu,lost=%lu,total=%lu,per=%.2f,elapsed_ms=%lu,throughput_kbps=%.1f,rssi_avg=%.1f,rssi_min=%d,freq=%.1f,bitrate=%d,pktSize=%d,uptime_ms=%lu,gps_pkts=%d,gps_dist_min=%.1f,gps_dist_max=%.1f,gps_lat=%.5f,gps_lon=%.5f",
               (unsigned long)windowNum,
               (unsigned long)n, (unsigned long)stats.unique, (unsigned long)lost,
               (unsigned long)total, perPct, (unsigned long)stats.elapsedMs, tputKbps,
               rssiAvg, stats.rssiMin, RX_FREQ_MHZ, RX_BITRATE_KBPS, RX_PKT_SIZE,
               (unsigned long)stats.startMs,
               stats.gpsPktCount, stats.minDistance, stats.maxDistance,
               stats.lastLat, stats.lastLon);

    windowNum++;
}

// ─── Serial command (set base station GPS) ──────────────────────────
static char cmdBuf[64];
static size_t cmdLen = 0;

static void processCommand(const char *cmd) {
    char verb[16];
    float lat = 0, lon = 0;
    int parsed = sscanf(cmd, "%15s %f %f", verb, &lat, &lon);

    if (strcmp(verb, "BASE") == 0 && parsed >= 3) {
        BASE_LAT = lat;
        BASE_LON = lon;
        baseSet = true;
        dualPrintf("OK BASE lat=%.5f lon=%.5f", BASE_LAT, BASE_LON);
    }
    else if (strcmp(verb, "STATUS") == 0) {
        dualPrintf("Base: %s lat=%.5f lon=%.5f", baseSet ? "SET" : "NOT_SET", BASE_LAT, BASE_LON);
        dualPrintf("Window: %lu", (unsigned long)windowNum);
    }
    else if (strcmp(verb, "HELP") == 0) {
        dualPrintln("Commands:");
        dualPrintln("  BASE <lat> <lon>  Set base station GPS position");
        dualPrintln("  STATUS             Print status");
>>>>>>> range-tests
    }
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(2000);
<<<<<<< HEAD
    Serial.println("BOOT RX GPS");
=======
    Serial.println("BOOT RX RANGE GPS");
>>>>>>> range-tests
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);
    delay(100);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);
<<<<<<< HEAD
    for (int i = 0; i < 3; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(120);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(120);
    }

    dualPrintf("=== RP2040 FLRC RANGE RX + GPS ===");
=======
    for (int i = 0; i < 4; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(250);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(250);
    }

    dualPrintln("");
    dualPrintln("=== RP2040 FLRC RANGE RX (GPS) ===");
    dualPrintf("Config: freq=%.1f br=%d pktSize=%d listen=%dms",
               RX_FREQ_MHZ, RX_BITRATE_KBPS, RX_PKT_SIZE, RX_LISTEN_MS);
    dualPrintln("Serial: BASE <lat> <lon> to set base station position");
>>>>>>> range-tests

    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
<<<<<<< HEAD
        dualPrintf("Auto-start RX in 2s...");
        delay(2000);
    } else {
        digitalWrite(PIN_LED_ALT, LOW);
        while (true) {
            digitalWrite(PIN_LED, HIGH); delay(500);
            digitalWrite(PIN_LED, LOW); delay(500);
=======
        dualPrintln("AUTO RX LISTENING (GPS mode)");
        if (!baseSet) {
            dualPrintln("WARNING: BASE not set — distance will not be computed");
            dualPrintln("Send: BASE <lat> <lon>  (e.g. BASE 48.12345 11.67890)");
        }
    } else {
        dualPrintln("INIT FAILED — retrying...");
        delay(2000);
        radioReady = rawInitRadio();
        if (radioReady) {
            digitalWrite(PIN_LED_ALT, HIGH);
            dualPrintln("AUTO RX LISTENING (2nd init)");
>>>>>>> range-tests
        }
    }
}

void loop() {
<<<<<<< HEAD
    runReceiveContinuous();
}
=======
    // Process serial commands (non-blocking)
    while (Serial.available()) {
        char c = (char)Serial.read();
        if (c == '\n' || c == '\r') {
            if (cmdLen > 0) {
                cmdBuf[cmdLen] = '\0';
                processCommand(cmdBuf);
                cmdLen = 0;
            }
        } else if (cmdLen < sizeof(cmdBuf) - 1) {
            cmdBuf[cmdLen++] = c;
        }
    }

    if (radioReady) {
        runReceive();
        delay(500);
    } else {
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(500);
    }
}
>>>>>>> range-tests
