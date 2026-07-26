/*
<<<<<<< HEAD
 * flrc_range_tx_gps.cpp — FLRC TX with optional GPS for outdoor range testing
 *
 * BACKWARD COMPATIBLE: Works with or without GPS module connected.
 * - On boot, listens UART0 (GP0/GP1) for NMEA sentences.
 * - If valid GGA received within 5s → GPS active, embeds position in every packet.
 * - If timeout → no GPS, fills GPS fields with zeros (fix=0).
 *
 * GPS Module: Any NMEA 9600 baud module (NEO-6M, ATGM336H, etc.)
 *   Wiring: GPS TX → GP1 (RP2040 UART0 RX)
 *           GPS VCC → 3V3, GPS GND → GND
 *
 * Auto-starts 3s after GPS detection. Loops forever.
 *
 * Payload (255 bytes):
 *   0-3:   packet sequence (uint32 big-endian)
 *   4-7:   burst ID (uint32 big-endian)
 *   8-11:  latitude  (int32, scaled ×1e7)
 *   12-15: longitude (int32, scaled ×1e7)
 *   16-17: altitude  (int16, meters)
 *   18:    satellites (uint8)
 *   19:    hdop      (uint8, ×10)
 *   20-23: gps_seconds_since_midnight (uint32)
 *   24:    gps_fix   (0=none, 1=2D, 2=3D)
 *   25-254: pattern 0x55 (integrity fill)
 *
 * Based on flrc_range_tx_auto.cpp (verified 2026-07-22).
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13 (Serial1, debug)
 *       GPS_RX=GP1 (UART0, GPS input)
 *       LED=GP25  LED_ALT=GP16
=======
 * flrc_range_tx_gps.cpp — Autonomous TX with GPS for outdoor range testing
 *
 * Based on flrc_range_tx_auto.cpp (proven 1733 kbps with single-batch SPI).
 * Adds GPS NMEA parsing over Serial2 (UART1, GP20/GP21, 115200 baud).
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
 *   GPS TX → GP1 (UART0 RX)
 *   GPS RX → GP0 (UART0 TX, optional)
 *   GPS VCC → 3V3 or 5V
 *   GPS GND → GND
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART0_TX=GP0 UART0_RX=GP1 (GPS)
 *       LED=GP25 LED_ALT=GP16
>>>>>>> range-tests
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
<<<<<<< HEAD
#define PIN_UART_TX 12
#define PIN_UART_RX 13
#define PIN_LED     25
#define PIN_LED_ALT 16

// ─── FLRC Config (MUST match RX) ─────────────────────────────────────
#define FLRC_FREQ_MHZ   2440.0f
#define FLRC_PKT_SIZE   255
#define SPI_FREQ_HZ     20000000UL
#define XTAL_MHZ        52.0f

#define TX_PKT_COUNT    1000
#define TX_POWER_DBM    12
#define BURST_DELAY_MS  1000
#define AUTO_START_MS   3000
#define GPS_DETECT_MS   9000   // total detection budget (3s per baud × 3 bauds)

=======
#define PIN_GPS_TX  0    // RP2040 TX → GPS RX (for config, optional)
#define PIN_GPS_RX  1    // RP2040 RX ← GPS TX (NMEA data)
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
#define GPS_BAUD        115200
#define GPS_FIX_TIMEOUT 60000   // 60s to acquire fix
#define GPS_NMEA_MAX    160     // max NMEA sentence length

// Sync word — MUST match RX
>>>>>>> range-tests
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

<<<<<<< HEAD
// ─── GPS State ───────────────────────────────────────────────────────
struct GpsData {
    int32_t  lat1e7 = 0;    // latitude × 1e7 (e.g. 326394400 = 32.63944°)
    int32_t  lon1e7 = 0;    // longitude × 1e7
    int16_t  altMeters = 0;
    uint8_t  satellites = 0;
    uint8_t  hdopX10 = 0;
    uint32_t secondsSinceMidnight = 0;
    uint8_t  fix = 0;       // 0=no fix, 1=2D, 2=3D
    bool     present = false;
};

static GpsData gpsData;
static char nmeaBuf[160];
static size_t nmeaLen = 0;

// NMEA checksum (XOR of chars between $ and *)
static bool nmeaValid(const char *s) {
    if (!s || s[0] != '$') return false;
    const char *star = strchr(s, '*');
    if (!star) return false;
    uint8_t ck = 0;
    for (const char *p = s + 1; p < star; p++) ck ^= (uint8_t)*p;
    // Parse hex checksum after *
    uint8_t recv = 0;
    for (const char *p = star + 1; *p && p < star + 3; p++) {
        recv <<= 4;
        if (*p >= '0' && *p <= '9') recv |= (*p - '0');
        else if (*p >= 'A' && *p <= 'F') recv |= (*p - 'A' + 10);
        else if (*p >= 'a' && *p <= 'f') recv |= (*p - 'a' + 10);
    }
    return ck == recv;
}

// Parse GGA: $xxGGA,hhmmss.ss,llll.ll,a,yyyyy.yy,a,x,xx,x.x,h.h,M,h.h,M,x.x,xxxx*hh
static void parseGGA(const char *s) {
    // Field index: 0=sentence ID, 1=time, 2=lat, 3=N/S, 4=lon, 5=E/W,
    //              6=fix quality, 7=sats, 8=hdop, 9=alt, 10=alt_unit
    char fields[16][20];
    int fi = 0, ci = 0;

    for (const char *p = s; *p && *p != '*'; p++) {
        if (*p == ',') {
            if (fi < 16) { fields[fi][ci] = 0; fi++; ci = 0; }
        } else {
            if (fi < 16 && ci < 19) { fields[fi][ci] = *p; ci++; }
        }
    }
    if (fi < 16) fields[fi][ci] = 0;

    if (fi < 7) return;

    // Fix quality
    int fixQ = atoi(fields[6]);
    gpsData.fix = (fixQ >= 1) ? (fixQ == 2 ? 2 : 1) : 0;

    // Sats
    gpsData.satellites = (uint8_t)atoi(fields[7]);

    // HDOP
    if (fields[8][0]) {
        gpsData.hdopX10 = (uint8_t)(atof(fields[8]) * 10.0 + 0.5);
    }

    // Altitude
    if (fields[9][0]) {
        gpsData.altMeters = (int16_t)(atof(fields[9]) + 0.5);
    }

    // Latitude: ddmm.mmmm
    if (fields[2][0] && fields[3][0]) {
        double raw = atof(fields[2]);
        int deg = (int)(raw / 100);
        double min = raw - deg * 100;
        double lat = deg + min / 60.0;
        if (fields[3][0] == 'S') lat = -lat;
        gpsData.lat1e7 = (int32_t)(lat * 1e7);
    }

    // Longitude: dddmm.mmmm
    if (fields[4][0] && fields[5][0]) {
        double raw = atof(fields[4]);
        int deg = (int)(raw / 100);
        double min = raw - deg * 100;
        double lon = deg + min / 60.0;
        if (fields[5][0] == 'W') lon = -lon;
        gpsData.lon1e7 = (int32_t)(lon * 1e7);
    }

    // Time → seconds since midnight
    if (fields[1][0]) {
        double t = atof(fields[1]);
        int hh = (int)(t / 10000);
        int mm = ((int)t / 100) % 100;
        int ss = (int)t % 100;
        int ms = (int)((t - (int)t) * 1000);
        gpsData.secondsSinceMidnight = hh * 3600 + mm * 60 + ss;
    }
}

static void gpsProcessChar(char c) {
    if (c == '$') {
        nmeaLen = 0;
    }
    if (nmeaLen < sizeof(nmeaBuf) - 1) {
        nmeaBuf[nmeaLen++] = c;
    }
    if (c == '\n') {
        nmeaBuf[nmeaLen] = 0;
        if (nmeaValid(nmeaBuf)) {
            // Check for GGA sentence
            if (strstr(nmeaBuf, "GGA")) {
                parseGGA(nmeaBuf);
                gpsData.present = true;
            }
        }
        nmeaLen = 0;
    }
}

// Detect GPS module with baud rate auto-detection.
// Tries: 9600, 38400 (M10 default), 115200. Blocks up to GPS_DETECT_MS per baud.
static bool tryBaud(SerialUART &gpsSerial, uint32_t baud, uint32_t timeout_ms) {
    gpsSerial.begin(baud);
    delay(50);

    uint32_t start = millis();
    uint32_t charCount = 0;

    while (millis() - start < timeout_ms) {
        while (gpsSerial.available()) {
            char c = gpsSerial.read();
            charCount++;
            gpsProcessChar(c);
            if (gpsData.present) return true;
        }
        delay(5);
    }
    return gpsData.present;
}

static void gpsInit(SerialUART &gpsSerial) {
    // Baud rates to try — M10 defaults to 38400, older modules to 9600
    const uint32_t bauds[] = {9600, 38400, 115200};
    const int numBauds = 3;
    uint32_t perBaudMs = GPS_DETECT_MS / numBauds;

    Serial1.println("GPS: Auto-detecting baud (9600/38400/115200)...");

    for (int i = 0; i < numBauds; i++) {
        Serial1.printf("GPS: Trying %lu baud...\n", (unsigned long)bauds[i]);

        // Count chars to detect if any UART data at all
        uint32_t beforeCount = 0;
        // We'll count via tryBaud's internal processing
        bool found = tryBaud(gpsSerial, bauds[i], perBaudMs);

        if (gpsData.present) {
            Serial1.printf("GPS: DETECTED at %lu baud\n", (unsigned long)bauds[i]);
            Serial1.printf("GPS: fix=%d sats=%d lat=%.5f lon=%.5f\n",
                           gpsData.fix, gpsData.satellites,
                           gpsData.lat1e7 / 1e7, gpsData.lon1e7 / 1e7);
            return;
        }

        // Check if we got any raw data at this baud
        // If we got garbage chars, the baud is wrong. If zero chars, module not connected.
    }

    // Final check — try one more time at 9600 with longer timeout
    // (some M10 boards ship at 9600 despite datasheet saying 38400)
    Serial1.println("GPS: No valid GGA. Retrying 9600 baud (3s)...");
    bool found = tryBaud(gpsSerial, 9600, 3000);

    if (gpsData.present) {
        Serial1.println("GPS: DETECTED at 9600 baud");
        return;
    }

    Serial1.println("GPS: No module detected. Running without GPS.");
=======
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
>>>>>>> range-tests
}

// ─── SPI ─────────────────────────────────────────────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

<<<<<<< HEAD
=======
static volatile bool radioReady = false;

// Dummy RX buffer for write-only transfers (nullptr crashes on some cores)
static uint8_t spiRxJunk[257];

// ─── SPI helpers (single-batch from speed-tests) ────────────────────
>>>>>>> range-tests
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
<<<<<<< HEAD
    for (size_t i = 0; i < len; i++) spiRf.transfer(buf[i]);
=======
    spiRf.transfer((uint8_t*)buf, spiRxJunk, len);
>>>>>>> range-tests
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
<<<<<<< HEAD
    for (size_t i = 0; i < len; i++) spiRf.transfer(data[i]);
=======
    spiRf.transfer((uint8_t*)data, spiRxJunk, len);
>>>>>>> range-tests
    digitalWrite(PIN_CS, HIGH);
    spiRf.endTransaction();
}

<<<<<<< HEAD
// ─── Dual output ─────────────────────────────────────────────────────
=======
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

// ─── Output ──────────────────────────────────────────────────────────
static void dualPrint(const char *s) { Serial.print(s); }
static void dualPrintln(const char *s) { Serial.println(s); }

>>>>>>> range-tests
static void dualPrintf(const char *fmt, ...) {
    char buf[256];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.println(buf);
<<<<<<< HEAD
    Serial1.println(buf);
}

// ─── Raw SPI Init ────────────────────────────────────────────────────
=======
}

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
    rfSetFreq(TX_FREQ_MHZ);
>>>>>>> range-tests
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x01, 0x01, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

<<<<<<< HEAD
    uint16_t feFreq = (uint16_t)((FLRC_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
=======
    uint16_t feFreq = (uint16_t)((TX_FREQ_MHZ / 4.0f) + 0.5f) | 0x8000;
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
=======

    rfSetBitrate(TX_BITRATE_KBPS);
>>>>>>> range-tests
    delay(1);

    {
        uint8_t cmd[] = { 0x02, 0x4C, 0x01, SYNC_WORD_0, SYNC_WORD_1, SYNC_WORD_2, SYNC_WORD_3 };
        rfWriteCmd(cmd, 7);
    }
    delay(1);

<<<<<<< HEAD
    {
        uint8_t cmd[] = {
            0x02, 0x49,
            0x0C, 0x4C, 0x00, (uint8_t)FLRC_PKT_SIZE
        };
        rfWriteCmd(cmd, 6);
    }
=======
    rfSetPktSize(TX_PKT_SIZE);
>>>>>>> range-tests
    delay(1);

    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);
<<<<<<< HEAD
    { uint8_t cmd[] = { 0x02, 0x03, (uint8_t)(TX_POWER_DBM * 2), 0x04 }; rfWriteCmd(cmd, 4); }
=======
    rfSetTxPower(TX_POWER_DBM);
>>>>>>> range-tests
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
<<<<<<< HEAD
        dualPrintf("RADIO_INIT_OK");
=======
        dualPrintln("RADIO_INIT_OK");
>>>>>>> range-tests
        return true;
    }
    dualPrintf("RADIO_INIT_FAIL (St=0x%02X)", st);
    return false;
}

<<<<<<< HEAD
// ─── State ───────────────────────────────────────────────────────────
static volatile bool radioReady = false;
static uint32_t burstId = 0;

// ─── GPS UART ────────────────────────────────────────────────────────
// UART0 on GP0(TX)/GP1(RX) for GPS. Serial1 is UART1 on GP12/GP13.
// Use SerialUART on UART0.
SerialUART gpsSerial(uart0, 1, 0);  // GP1=RX, GP0=TX

// ─── Embed GPS data into packet ─────────────────────────────────────
static void embedGps(uint8_t *pkt) {
    // bytes 8-11: lat1e7
    pkt[8]  = (uint8_t)(gpsData.lat1e7 >> 24);
    pkt[9]  = (uint8_t)(gpsData.lat1e7 >> 16);
    pkt[10] = (uint8_t)(gpsData.lat1e7 >> 8);
    pkt[11] = (uint8_t)(gpsData.lat1e7 & 0xFF);
    // bytes 12-15: lon1e7
    pkt[12] = (uint8_t)(gpsData.lon1e7 >> 24);
    pkt[13] = (uint8_t)(gpsData.lon1e7 >> 16);
    pkt[14] = (uint8_t)(gpsData.lon1e7 >> 8);
    pkt[15] = (uint8_t)(gpsData.lon1e7 & 0xFF);
    // bytes 16-17: altitude
    pkt[16] = (uint8_t)(gpsData.altMeters >> 8);
    pkt[17] = (uint8_t)(gpsData.altMeters & 0xFF);
    // byte 18: sats
    pkt[18] = gpsData.satellites;
    // byte 19: hdop×10
    pkt[19] = gpsData.hdopX10;
    // bytes 20-23: seconds since midnight
    pkt[20] = (uint8_t)(gpsData.secondsSinceMidnight >> 24);
    pkt[21] = (uint8_t)(gpsData.secondsSinceMidnight >> 16);
    pkt[22] = (uint8_t)(gpsData.secondsSinceMidnight >> 8);
    pkt[23] = (uint8_t)(gpsData.secondsSinceMidnight & 0xFF);
    // byte 24: fix quality
    pkt[24] = gpsData.fix;
}

// ─── TX burst ────────────────────────────────────────────────────────
static void runTransmit() {
    if (!radioReady) { dualPrintf("ERR: radio not initialized"); return; }

    dualPrintf("BURST_START n=%d burst_id=%lu gps=%s fix=%d",
               TX_PKT_COUNT, (unsigned long)burstId,
               gpsData.present ? "PRESENT" : "ABSENT",
               gpsData.fix);
    delay(10);

    uint8_t pkt[FLRC_PKT_SIZE];
    // Fill pattern
    for (int j = 25; j < FLRC_PKT_SIZE; j++) pkt[j] = (uint8_t)(j & 0xFF);

    // Embed burst ID (static per burst)
    pkt[4] = (uint8_t)(burstId >> 24);
    pkt[5] = (uint8_t)(burstId >> 16);
    pkt[6] = (uint8_t)(burstId >> 8);
    pkt[7] = (uint8_t)(burstId & 0xFF);
=======
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
>>>>>>> range-tests

    uint32_t irqMask = 1UL << PIN_IRQ;
    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

<<<<<<< HEAD
    for (int i = 0; i < TX_PKT_COUNT; i++) {
        // Packet sequence
=======
    for (int i = 0; i < count; i++) {
>>>>>>> range-tests
        pkt[0] = (uint8_t)(i >> 24);
        pkt[1] = (uint8_t)(i >> 16);
        pkt[2] = (uint8_t)(i >> 8);
        pkt[3] = (uint8_t)(i & 0xFF);

<<<<<<< HEAD
        // Embed current GPS data (updates between packets)
        embedGps(pkt);

        rfClearIrq();
        rfWriteTxFifo(pkt, FLRC_PKT_SIZE);
        rfSetTx();

        // Poll GPS while waiting for TX_DONE
=======
        // Embed GPS data in bytes 4-19
        embedGPS(pkt);

        rfClearIrq();
        rfWriteTxFifo(pkt, pktSize);
        rfSetTx();

>>>>>>> range-tests
        uint32_t spinCount = 0;
        bool irqFired = false;
        while (spinCount < 500000) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
<<<<<<< HEAD

            // Read GPS during TX wait (non-blocking)
            while (gpsSerial.available()) {
                gpsProcessChar(gpsSerial.read());
            }
=======
>>>>>>> range-tests
        }

        if (irqFired) txDoneCount++;
        else txTimeoutCount++;

<<<<<<< HEAD
        // Blink every 100 packets
        if ((i + 1) % 100 == 0) {
            digitalWrite(PIN_LED, HIGH);
            delayMicroseconds(100);
            digitalWrite(PIN_LED, LOW);
        }
    }

    uint32_t elapsed = millis() - startMs;
    float tput = ((float)TX_PKT_COUNT * FLRC_PKT_SIZE * 8.0f) / elapsed;

    dualPrintf("BURST_DONE id=%lu sent=%d done=%lu to=%lu elapsed_ms=%lu tput_kbps=%.1f gps_fix=%d sats=%d lat=%.5f lon=%.5f",
               (unsigned long)burstId, TX_PKT_COUNT,
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
               (unsigned long)elapsed, tput,
               gpsData.fix, gpsData.satellites,
               gpsData.lat1e7 / 1e7, gpsData.lon1e7 / 1e7);

    burstId++;
=======
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
>>>>>>> range-tests
}

// ─── Arduino entry points ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
<<<<<<< HEAD
    Serial1.setTX(PIN_UART_TX);
    Serial1.setRX(PIN_UART_RX);
    Serial1.begin(115200);
    delay(100);

    // GPS UART0: GP0=TX, GP1=RX
    gpsSerial.begin(9600);
=======
    delay(2000);
    Serial.println("BOOT TX RANGE GPS");

    // UART0 for GPS (115200 baud, GP0/GP1)
    Serial1.setRX(PIN_GPS_RX);  // GP1 — receives from GPS TX
    Serial1.setTX(PIN_GPS_TX);  // GP0 — sends to GPS RX (optional)
    Serial1.begin(GPS_BAUD);
>>>>>>> range-tests
    delay(100);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);

<<<<<<< HEAD
    for (int i = 0; i < 5; i++) {
        digitalWrite(PIN_LED, HIGH); digitalWrite(PIN_LED_ALT, HIGH); delay(100);
        digitalWrite(PIN_LED, LOW);  digitalWrite(PIN_LED_ALT, LOW);  delay(100);
    }

    Serial1.println();
    Serial1.println("=== RP2040 FLRC RANGE TX + GPS ===");

=======
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

        // GPS detection (up to 5s)
        gpsInit(gpsSerial);

        dualPrintf("AUTO_START in %dms...", AUTO_START_MS);
        delay(AUTO_START_MS);
    } else {
        digitalWrite(PIN_LED_ALT, LOW);
        while (true) {
            digitalWrite(PIN_LED, HIGH); delay(500);
            digitalWrite(PIN_LED, LOW); delay(500);
        }
    }
}

void loop() {
    // Drain GPS between bursts
    while (gpsSerial.available()) {
        gpsProcessChar(gpsSerial.read());
    }

    runTransmit();
    delay(BURST_DELAY_MS);

    digitalWrite(PIN_LED, HIGH); delay(50); digitalWrite(PIN_LED, LOW);
}
=======
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
>>>>>>> range-tests
