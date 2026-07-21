/*
 * flrc_range_tx_gps.cpp — Autonomous TX with GPS for outdoor range testing
 *
 * Based on flrc_range_tx_auto.cpp (proven 1733 kbps with single-batch SPI).
 * Adds GPS NMEA parsing over Serial2 (UART1, GP20/GP21, 9600 baud).
 * Embeds lat/lon in TX packet payload.
 *
 * Behavior:
 * - 3s LED blink countdown on boot
 * - Waits for GPS fix (up to 60s) — LED blinks fast during search
 * - Once fix acquired: LED solid, starts TX bursts
 * - 500-packet bursts, 2s pause, repeat forever
 * - GPS coords embedded in bytes 4-19 of each packet:
 *     bytes 4-7:   latitude  (float, degrees)
 *     bytes 8-11:  longitude (float, degrees)
 *     bytes 12-13: num_sats  (uint16_t)
 *     bytes 14-15: gps_fix   (uint16_t, 1=valid)
 *     bytes 16-19: gps_time  (uint32_t, seconds since midnight UTC)
 * - DEADBEEF marker at end of each burst (same as auto)
 *
 * GPS module wiring:
 *   GPS TX → GP21 (UART1 RX)
 *   GPS RX → GP20 (UART1 TX)
 *   GPS VCC → 3V3
 *   GPS GND → GND
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART1_TX=GP20 UART1_RX=GP21 (GPS)
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
#define PIN_GPS_TX  20   // RP2040 TX → GPS RX (for config, optional)
#define PIN_GPS_RX  21   // RP2040 RX ← GPS TX (NMEA data)
#define PIN_LED     25
#define PIN_LED_ALT 16

#define SPI_FREQ_HZ     20000000UL
#define XTAL_MHZ        52.0f

// ─── Compile-time RF config ─────────────────────────────────────────
#define TX_FREQ_MHZ     2440.0f
#define TX_BITRATE_KBPS 2600
#define TX_PKT_SIZE     255
#define TX_POWER_DBM    12.0f
#define TX_PKT_COUNT    500
#define TX_PAUSE_MS     2000

// ─── GPS config ─────────────────────────────────────────────────────
#define GPS_BAUD        9600
#define GPS_FIX_TIMEOUT 60000   // 60s to acquire fix
#define GPS_NMEA_MAX    160     // max NMEA sentence length

// Sync word — MUST match RX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── GPS data ───────────────────────────────────────────────────────
struct GpsData {
    float    lat;
    float    lon;
    uint16_t sats;
    bool     fixValid;
    uint32_t timeSec;  // seconds since midnight UTC
    bool     hasData;
};
static GpsData gps = {0, 0, 0, false, 0, false};

// ─── NMEA parser ─────────────────────────────────────────────────────
static char nmeaBuf[GPS_NMEA_MAX];
static size_t nmeaLen = 0;

// Parse $GPGGA or $GPRMC sentence
static void parseNMEA(const char *sentence) {
    // $GPGGA,time,lat,N/S,lon,E/W,fix,nsat,hdop,alt,M,...
    // $GPRMC,time,status,lat,N/S,lon,E/W,speed,course,date,...
    if (strncmp(sentence, "$GPGGA", 6) == 0) {
        // Parse: time, lat, N/S, lon, E/W, fix, nsat
        char timeStr[16] = {0};
        char latStr[16] = {0};
        char ns = 'N';
        char lonStr[16] = {0};
        char ew = 'E';
        int fix = 0;
        int nsat = 0;

        // $GPGGA,hhmmss.ss,dddd.dddd,N,ddd.dd.dd,E,fix,nsat,...
        int parsed = sscanf(sentence,
            "$GPGGA,%15[^,],%15[^,],%c,%15[^,],%c,%d,%d,",
            timeStr, latStr, &ns, lonStr, &ew, &fix, &nsat);

        if (parsed >= 6 && fix > 0) {
            // Convert NMEA lat/lon to decimal degrees
            // Format: ddmm.mmmm or dddmm.mmmm
            float rawLat = atof(latStr);
            float rawLon = atof(lonStr);

            int latDeg = (int)(rawLat / 100);
            float latMin = rawLat - (latDeg * 100);
            gps.lat = latDeg + latMin / 60.0f;
            if (ns == 'S') gps.lat = -gps.lat;

            int lonDeg = (int)(rawLon / 100);
            float lonMin = rawLon - (lonDeg * 100);
            gps.lon = lonDeg + lonMin / 60.0f;
            if (ew == 'W') gps.lon = -gps.lon;

            gps.sats = (uint16_t)nsat;
            gps.fixValid = true;
            gps.hasData = true;

            // Parse time: hhmmss.ss → seconds since midnight
            if (strlen(timeStr) >= 6) {
                int hh = (timeStr[0]-'0')*10 + (timeStr[1]-'0');
                int mm = (timeStr[2]-'0')*10 + (timeStr[3]-'0');
                int ss = (timeStr[4]-'0')*10 + (timeStr[5]-'0');
                gps.timeSec = (uint32_t)(hh*3600 + mm*60 + ss);
            }
        }
    }
    else if (strncmp(sentence, "$GPRMC", 6) == 0) {
        // $GPRMC,time,status,lat,N/S,lon,E/W,...
        char timeStr[16] = {0};
        char status = 'V';
        char latStr[16] = {0};
        char ns = 'N';
        char lonStr[16] = {0};
        char ew = 'E';

        int parsed = sscanf(sentence,
            "$GPRMC,%15[^,],%c,%15[^,],%c,%15[^,],%c,",
            timeStr, &status, latStr, &ns, lonStr, &ew);

        if (parsed >= 6 && status == 'A') {
            float rawLat = atof(latStr);
            float rawLon = atof(lonStr);

            int latDeg = (int)(rawLat / 100);
            float latMin = rawLat - (latDeg * 100);
            gps.lat = latDeg + latMin / 60.0f;
            if (ns == 'S') gps.lat = -gps.lat;

            int lonDeg = (int)(rawLon / 100);
            float lonMin = rawLon - (lonDeg * 100);
            gps.lon = lonDeg + lonMin / 60.0f;
            if (ew == 'W') gps.lon = -gps.lon;

            gps.fixValid = true;
            gps.hasData = true;

            if (strlen(timeStr) >= 6) {
                int hh = (timeStr[0]-'0')*10 + (timeStr[1]-'0');
                int mm = (timeStr[2]-'0')*10 + (timeStr[3]-'0');
                int ss = (timeStr[4]-'0')*10 + (timeStr[5]-'0');
                gps.timeSec = (uint32_t)(hh*3600 + mm*60 + ss);
            }
        } else if (status == 'V') {
            gps.fixValid = false;
        }
    }
}

static void gpsPoll() {
    while (Serial1.available()) {
        char c = Serial1.read();
        if (c == '$') {
            nmeaLen = 0;
            nmeaBuf[nmeaLen++] = c;
        } else if (c == '\n' || c == '\r') {
            if (nmeaLen > 6) {
                nmeaBuf[nmeaLen] = '\0';
                parseNMEA(nmeaBuf);
            }
            nmeaLen = 0;
        } else if (nmeaLen < GPS_NMEA_MAX - 1) {
            nmeaBuf[nmeaLen++] = c;
        }
    }
}

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

static volatile bool radioReady = false;

// ─── SPI helpers (single-batch from speed-tests) ────────────────────
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
    spiRf.transfer(buf, nullptr, len);
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

static void rfSetTx() {
    uint8_t cmd[5] = { 0x02, 0x0D, 0x00, 0x00, 0x00 };
    rfWriteCmd(cmd, 5);
}

static void rfWriteTxFifo(const uint8_t *data, size_t len) {
    rfWaitBusy();
    spiRf.beginTransaction(spiSettings);
    digitalWrite(PIN_CS, LOW);
    spiRf.transfer(0x00);
    spiRf.transfer(0x02);
    spiRf.transfer(data, nullptr, len);
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

static void rfClearTxFifo() {
    uint8_t cmd[] = { 0x01, 0x1F };
    rfWriteCmd(cmd, 2);
}

// ─── Parameter setters ───────────────────────────────────────────────
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
        case 2600: brBw = 0x00; break;
        case 1300: brBw = 0x01; break;
        case 650:  brBw = 0x02; break;
        case 325:  brBw = 0x03; break;
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

// ─── Output ──────────────────────────────────────────────────────────
static void dualPrint(const char *s) { Serial.print(s); Serial1.print(s); }
static void dualPrintln(const char *s) { Serial.println(s); Serial1.println(s); }

static void dualPrintf(const char *fmt, ...) {
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.println(buf);
    Serial1.println(buf);
}

// ─── Radio init ──────────────────────────────────────────────────────
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
    delay(1);

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

// ─── Embed GPS data in packet ────────────────────────────────────────
static void embedGPS(uint8_t *pkt) {
    // bytes 4-7: latitude (float, little-endian)
    memcpy(&pkt[4], &gps.lat, 4);
    // bytes 8-11: longitude (float, little-endian)
    memcpy(&pkt[8], &gps.lon, 4);
    // bytes 12-13: num_sats
    pkt[12] = (uint8_t)(gps.sats >> 8);
    pkt[13] = (uint8_t)(gps.sats & 0xFF);
    // bytes 14-15: fix valid
    pkt[14] = 0;
    pkt[15] = gps.fixValid ? 1 : 0;
    // bytes 16-19: GPS time (seconds since midnight UTC)
    pkt[16] = (uint8_t)(gps.timeSec >> 24);
    pkt[17] = (uint8_t)(gps.timeSec >> 16);
    pkt[18] = (uint8_t)(gps.timeSec >> 8);
    pkt[19] = (uint8_t)(gps.timeSec & 0xFF);
}

// ─── TX burst ────────────────────────────────────────────────────────
static uint32_t burstNum = 0;

static void runTransmit() {
    if (!radioReady) return;

    uint16_t pktSize = TX_PKT_SIZE;
    uint16_t count = TX_PKT_COUNT;

    digitalWrite(PIN_LED, HIGH);
    digitalWrite(PIN_LED_ALT, HIGH);

    uint32_t burstStartMs = millis();
    dualPrintf("BURST %lu START uptime=%lums count=%d gps_fix=%d sats=%d lat=%.5f lon=%.5f",
               (unsigned long)burstNum, (unsigned long)burstStartMs, count,
               gps.fixValid ? 1 : 0, gps.sats, gps.lat, gps.lon);

    uint8_t pkt[256];
    for (int j = 20; j < pktSize; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t irqMask = 1UL << PIN_IRQ;
    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    for (int i = 0; i < count; i++) {
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

        // Embed GPS data in bytes 4-19
        embedGPS(pkt);

        rfClearIrq();
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

        // Poll GPS between packets (non-blocking)
        gpsPoll();
    }

    // DEADBEEF end marker
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

    dualPrintf("BURST %lu DONE fired=%lu to=%lu elapsed=%lums tput=%.1fkbps",
               (unsigned long)burstNum,
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
               (unsigned long)elapsed, tput);
    dualPrintf("RANGE_RESULT_TX,burst=%lu,sent=%d,fired=%lu,timeout=%lu,elapsed_ms=%lu,throughput_kbps=%.1f,freq=%.1f,bitrate=%d,power=%.1f,pktSize=%d,uptime_ms=%lu,gps_fix=%d,gps_sats=%d,gps_lat=%.5f,gps_lon=%.5f",
               (unsigned long)burstNum, count,
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
               (unsigned long)elapsed, tput,
               TX_FREQ_MHZ, TX_BITRATE_KBPS, TX_POWER_DBM, TX_PKT_SIZE,
               (unsigned long)burstStartMs,
               gps.fixValid ? 1 : 0, gps.sats, gps.lat, gps.lon);

    burstNum++;

    digitalWrite(PIN_LED, LOW);
    digitalWrite(PIN_LED_ALT, LOW);
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(2000);
    Serial.println("BOOT TX RANGE GPS");

    // UART1 for GPS (9600 baud)
    Serial1.setRX(PIN_GPS_RX);  // GP21 — receives from GPS TX
    Serial1.setTX(PIN_GPS_TX);  // GP20 — sends to GPS RX (optional)
    Serial1.begin(GPS_BAUD);
    delay(100);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);

    // 3s countdown blink
    for (int i = 0; i < 6; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH);
        delay(250);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);
        delay(250);
    }

    Serial.println("=== RP2040 FLRC RANGE TX (GPS) ===");
    Serial.printf("RF: freq=%.1f br=%d pktSize=%d power=%.1f count=%d\n",
                  TX_FREQ_MHZ, TX_BITRATE_KBPS, TX_PKT_SIZE, TX_POWER_DBM, TX_PKT_COUNT);
    Serial.printf("GPS: baud=%d RX=GP%d TX=GP%d\n", GPS_BAUD, PIN_GPS_RX, PIN_GPS_TX);

    // Init radio
    spiRf.begin();
    pinMode(PIN_CS, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    pinMode(PIN_BUSY, INPUT);
    pinMode(PIN_IRQ, INPUT);

    radioReady = rawInitRadio();

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        Serial.println("RADIO OK — waiting for GPS fix...");
    } else {
        Serial.println("INIT FAILED — retrying...");
        delay(2000);
        radioReady = rawInitRadio();
    }

    // Wait for GPS fix (up to 60s)
    uint32_t gpsStart = millis();
    Serial.println("GPS: searching for fix...");
    while (!gps.fixValid && (millis() - gpsStart) < GPS_FIX_TIMEOUT) {
        gpsPoll();
        // Fast blink during GPS search
        digitalWrite(PIN_LED, HIGH); delay(50);
        digitalWrite(PIN_LED, LOW); delay(50);
    }

    if (gps.fixValid) {
        Serial.printf("GPS FIX: lat=%.5f lon=%.5f sats=%d time=%lus\n",
                      gps.lat, gps.lon, gps.sats, (unsigned long)gps.timeSec);
        Serial.println("AUTO TX STARTING — unplug and walk");
    } else {
        Serial.println("GPS: NO FIX — starting TX anyway (no GPS data in packets)");
        Serial.println("AUTO TX STARTING — unplug and walk");
    }

    // Solid LED = ready
    digitalWrite(PIN_LED_ALT, HIGH);
}

void loop() {
    if (radioReady) {
        // Poll GPS before each burst
        gpsPoll();
        runTransmit();
        delay(TX_PAUSE_MS);
    } else {
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(500);
    }
}