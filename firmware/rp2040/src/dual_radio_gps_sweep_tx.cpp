/*
 * dual_radio_gps_sweep_tx.cpp — GPS time-disciplined dual-radio sweep TX
 *
 * GPS-disciplined version of dual_radio_sweep_tx.cpp. Uses GPS UTC time
 * (from RMC/GGA NMEA sentences) as the master clock for mode scheduling.
 * Falls back to millis() if no GPS module is detected within 5s.
 *
 * GPS module on UART0: GP1=RX, GP0=TX (SerialUART gpsSerial(uart0, 1, 0))
 * 9600 baud NMEA. Parses RMC for UTC time + GGA for position.
 *
 * MODE SCHEDULE (GPS-disciplined, CYCLE_LENGTH_SEC = 600 = 10 min):
 *   Mode 0 (0-150s):   HF FLRC 2600 kbps @ 2440 MHz (pin 10, HF path)
 *   Mode 1 (150-300s): HF FLRC 325 kbps  @ 2440 MHz (pin 10, HF path)
 *   Mode 2 (300-450s): LF LoRa SF7       @ 868 MHz  (pin 9, LF path, BW=250kHz)
 *   Mode 3 (450-600s): LF LoRa SF12      @ 868 MHz  (pin 9, LF path, BW=250kHz)
 *
 * Built from proven dual_radio_sweep_tx.cpp SPI patterns (VERBATIM).
 * GPS NMEA from flrc_range_tx_gps.cpp (VERBATIM) + new parseRMC().
 * No RadioLib. Raw 2-byte opcode SPI.
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       UART_TX=GP12 UART_RX=GP13 (Serial1, debug)
 *       GPS_RX=GP1 GPS_TX=GP0 (UART0, GPS NMEA input)
 *       LED=GP25  LED_ALT=GP16
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
#ifndef TX_POWER_DBM
#define TX_POWER_DBM    12.5f
#endif

// FLRC sync word — MUST match RX
#define SYNC_WORD_0   0x12
#define SYNC_WORD_1   0xAD
#define SYNC_WORD_2   0x10
#define SYNC_WORD_3   0x1B

// ─── GPS-disciplined schedule ────────────────────────────────────────
#define CYCLE_LENGTH_SEC  600    // 10-minute cycle
#define MODE_DURATION_SEC 150    // 150s per mode
#define NUM_GPS_MODES     4
#define GPS_DETECT_TIMEOUT_MS 5000  // 5s timeout for GPS detection

// ─── Mode definitions ────────────────────────────────────────────────
struct RadioMode {
    const char* name;
    bool isFlrc;        // true=FLRC, false=LoRa
    bool isHF;          // true=HF path (2.4GHz pin 10), false=LF path (sub-GHz pin 9)
    float freqMhz;
    uint16_t flrcBitrate; // FLRC only
    uint8_t loraSf;       // LoRa only
    uint8_t loraBwCode;   // LoRa only (0x05=250kHz, 0x0D=203kHz, 0x0E=406kHz, 0x0F=812kHz)
    uint8_t loraCr;       // LoRa only (1=4/5, 2=4/6, ...)
    uint16_t txPktCount;  // packets per burst
    uint32_t txPauseMs;   // pause between bursts
};

static const RadioMode modes[NUM_GPS_MODES] = {
    // Mode 0: HF FLRC 2600 kbps @ 2440 MHz
    {"HF_FLRC_2600", true,  true,  2440.0f, 2600, 0,  0,    0, 500, 2000},
    // Mode 1: HF FLRC 325 kbps @ 2440 MHz
    {"HF_FLRC_325",  true,  true,  2440.0f, 325,  0,  0,    0, 500, 2000},
    // Mode 2: LF LoRa SF7 @ 868 MHz, BW=250kHz
    {"LF_LORA_SF7",  false, false, 868.0f,  0,    7,  0x05, 1, 50,  2000},
    // Mode 3: LF LoRa SF12 @ 868 MHz, BW=250kHz
    {"LF_LORA_SF12", false, false, 868.0f,  0,    12, 0x05, 1, 50,  2000},
};

// ─── GPS State ───────────────────────────────────────────────────────
struct GpsData {
    int32_t  lat1e7 = 0;    // latitude × 1e7
    int32_t  lon1e7 = 0;    // longitude × 1e7
    int16_t  altMeters = 0;
    uint8_t  satellites = 0;
    uint8_t  hdopX10 = 0;
    uint32_t secondsSinceMidnight = 0;
    uint8_t  fix = 0;       // 0=no fix, 1=2D, 2=3D
    bool     present = false;
    bool     timeValid = false;  // RMC time parsed
};

static GpsData gpsData;
static char nmeaBuf[160];
static size_t nmeaLen = 0;
static bool usingGpsClock = false;  // true=GPS, false=millis() fallback
static uint32_t bootMs = 0;         // for millis() fallback

// GPS UART: UART0 on GP1(RX)/GP0(TX)
SerialUART gpsSerial(uart0, 1, 0);

// ─── NMEA checksum (XOR of chars between $ and *) ────────────────────
static bool nmeaValid(const char *s) {
    if (!s || s[0] != '$') return false;
    const char *star = strchr(s, '*');
    if (!star) return false;
    uint8_t ck = 0;
    for (const char *p = s + 1; p < star; p++) ck ^= (uint8_t)*p;
    uint8_t recv = 0;
    for (const char *p = star + 1; *p && p < star + 3; p++) {
        recv <<= 4;
        if (*p >= '0' && *p <= '9') recv |= (*p - '0');
        else if (*p >= 'A' && *p <= 'F') recv |= (*p - 'A' + 10);
        else if (*p >= 'a' && *p <= 'f') recv |= (*p - 'a' + 10);
    }
    return ck == recv;
}

// ─── Parse GGA for position ──────────────────────────────────────────
static void parseGGA(const char *s) {
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

    int fixQ = atoi(fields[6]);
    gpsData.fix = (fixQ >= 1) ? (fixQ == 2 ? 2 : 1) : 0;
    gpsData.satellites = (uint8_t)atoi(fields[7]);

    if (fields[8][0]) gpsData.hdopX10 = (uint8_t)(atof(fields[8]) * 10.0 + 0.5);
    if (fields[9][0]) gpsData.altMeters = (int16_t)(atof(fields[9]) + 0.5);

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

    // Time from GGA (backup if no RMC)
    if (fields[1][0]) {
        double t = atof(fields[1]);
        int hh = (int)(t / 10000);
        int mm = ((int)t / 100) % 100;
        int ss = (int)t % 100;
        gpsData.secondsSinceMidnight = hh * 3600 + mm * 60 + ss;
    }
}

// ─── Parse RMC for time ──────────────────────────────────────────────
// $GPRMC,hhmmss.ss,A,llll.ll,N,yyyyy.yy,W,speed,course,ddmmyy,mag,w*CS
// Fields: [0]=ID [1]=time [2]=status(A/V) [3]=lat [4]=N/S [5]=lon [6]=E/W
static void parseRMC(const char *s) {
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
    if (fi < 2) return;  // need at least time field

    // Parse time field [1]: HHMMSS.SS → seconds_since_midnight
    if (fields[1][0]) {
        double t = atof(fields[1]);
        int hh = (int)(t / 10000);
        int mm = ((int)t / 100) % 100;
        int ss = (int)t % 100;
        gpsData.secondsSinceMidnight = hh * 3600 + mm * 60 + ss;
        gpsData.timeValid = true;
    }

    // Status field [2]: A=valid fix, V=void
    if (fields[2][0] == 'A') {
        gpsData.fix = (gpsData.fix >= 1) ? gpsData.fix : 1;  // keep GGA fix quality if higher
    }

    // RMC also has position — use it if GGA hasn't provided it
    if (fields[3][0] && fields[4][0]) {
        double raw = atof(fields[3]);
        int deg = (int)(raw / 100);
        double min = raw - deg * 100;
        double lat = deg + min / 60.0;
        if (fields[4][0] == 'S') lat = -lat;
        gpsData.lat1e7 = (int32_t)(lat * 1e7);
    }
    if (fields[5][0] && fields[6][0]) {
        double raw = atof(fields[5]);
        int deg = (int)(raw / 100);
        double min = raw - deg * 100;
        double lon = deg + min / 60.0;
        if (fields[6][0] == 'W') lon = -lon;
        gpsData.lon1e7 = (int32_t)(lon * 1e7);
    }
}

// ─── GPS char processing ─────────────────────────────────────────────
static void gpsProcessChar(char c) {
    if (c == '$') nmeaLen = 0;
    if (nmeaLen < sizeof(nmeaBuf) - 1) nmeaBuf[nmeaLen++] = c;
    if (c == '\n') {
        nmeaBuf[nmeaLen] = 0;
        if (nmeaValid(nmeaBuf)) {
            if (strstr(nmeaBuf, "GGA")) {
                parseGGA(nmeaBuf);
                gpsData.present = true;
            } else if (strstr(nmeaBuf, "RMC")) {
                parseRMC(nmeaBuf);
                gpsData.present = true;
            }
        }
        nmeaLen = 0;
    }
}

// Non-blocking GPS poll — call frequently to keep NMEA buffer fresh
static void gpsPoll() {
    while (gpsSerial.available()) {
        gpsProcessChar(gpsSerial.read());
    }
}

// ─── GPS init with baud auto-detect ──────────────────────────────────
static bool tryBaud(uint32_t baud, uint32_t timeout_ms) {
    gpsSerial.begin(baud);
    delay(50);

    uint32_t start = millis();
    while (millis() - start < timeout_ms) {
        while (gpsSerial.available()) {
            gpsProcessChar(gpsSerial.read());
            if (gpsData.present) return true;
        }
        delay(5);
    }
    return gpsData.present;
}

static void gpsInit() {
    const uint32_t bauds[] = {9600, 38400, 115200};
    const int numBauds = 3;
    uint32_t perBaudMs = GPS_DETECT_TIMEOUT_MS / numBauds;

    Serial1.println("GPS: Auto-detecting baud (9600/38400/115200)...");

    for (int i = 0; i < numBauds; i++) {
        Serial1.printf("GPS: Trying %lu baud...\n", (unsigned long)bauds[i]);
        bool found = tryBaud(bauds[i], perBaudMs);
        if (gpsData.present) {
            Serial1.printf("GPS: DETECTED at %lu baud\n", (unsigned long)bauds[i]);
            return;
        }
    }

    // Final retry at 9600
    Serial1.println("GPS: Retrying 9600 baud...");
    tryBaud(9600, 2000);
    if (gpsData.present) {
        Serial1.println("GPS: DETECTED at 9600 baud");
        return;
    }
    Serial1.println("GPS: No module detected. Using millis() fallback.");
}

// ─── Clock source: get seconds_since_midnight ────────────────────────
static uint32_t getSecondsSinceMidnight() {
    gpsPoll();  // keep NMEA buffer fresh
    if (usingGpsClock && gpsData.timeValid) {
        return gpsData.secondsSinceMidnight;
    }
    // millis() fallback: virtual seconds from boot
    return (millis() - bootMs) / 1000;
}

// Format GPS time as HH:MM:SS string
static void formatGpsTime(uint32_t sec, char *buf, size_t buflen) {
    uint32_t hh = (sec / 3600) % 24;
    uint32_t mm = (sec / 60) % 60;
    uint32_t ss = sec % 60;
    snprintf(buf, buflen, "%02lu:%02lu:%02lu",
             (unsigned long)hh, (unsigned long)mm, (unsigned long)ss);
}

// ─── SPI (VERBATIM from dual_radio_sweep_tx.cpp) ──────────────────────
static SPIClassRP2040 spiRf(spi0, PIN_MISO, PIN_CS, PIN_SCK, PIN_MOSI);
static SPISettings spiSettings(SPI_FREQ_HZ, MSBFIRST, SPI_MODE0);

// Pre-allocated combined buffer for single-batch FIFO write
static uint8_t fifoCmd[2 + 255];
// Dummy RX buffer for write-only transfers
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

static void rfSetTxPower(float dbm) {
    uint8_t powerRaw = (uint8_t)(dbm * 2.0f + 0.5f);
    uint8_t cmd[] = { 0x02, 0x03, powerRaw, 0x04 };
    rfWriteCmd(cmd, 4);
}

// ─── Dual output ─────────────────────────────────────────────────────
static void dualPrint(const char *s) { Serial.print(s); Serial1.print(s); }
static void dualPrintln(const char *s) { Serial.println(s); Serial1.println(s); }
static void dualPrintln() { Serial.println(); Serial1.println(); }

static void dualPrintf(const char *fmt, ...) {
    char buf[512];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.println(buf);
    Serial1.println(buf);
}

// ─── FLRC bitrate encoding ───────────────────────────────────────────
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

// ─── LoRa LDRO computation ───────────────────────────────────────────
static uint8_t computeLdro(uint8_t sf, uint8_t bwCode) {
    float bwHz = (bwCode == 0x0D) ? 203125.0f :
                 (bwCode == 0x0E) ? 406250.0f :
                 (bwCode == 0x05) ? 250000.0f : 812500.0f;
    float symTimeMs = (float)(1UL << sf) / bwHz * 1000.0f;
    return (symTimeMs > 16.0f) ? 1 : 0;
}

// ─── Unified CSV field helpers ───────────────────────────────────────
static const char* getPath(const RadioMode& m) {
    if (m.isHF && m.isFlrc)  return "HF_FLRC";
    if (m.isHF && !m.isFlrc) return "HF_LORA";
    if (!m.isHF && m.isFlrc) return "LF_FLRC";
    return "LF_LORA";
}

static const char* getPaState() {
    return (TX_POWER_DBM >= 12.5f) ? "ON" : "OFF";
}

static int getBandwidthKhz(const RadioMode& m) {
    if (m.isFlrc) return m.flrcBitrate;  // FLRC BW ≈ bitrate
    switch (m.loraBwCode) {
        case 0x0D: return 203;
        case 0x0E: return 406;
        case 0x05: return 250;
        default:   return 812;  // 0x0F
    }
}

// ─── GPS-disciplined mode scheduling ─────────────────────────────────
static int currentMode = -1;
static uint32_t burstNum = 0;

static int getCurrentMode() {
    uint32_t sec = getSecondsSinceMidnight();
    return (int)((sec % CYCLE_LENGTH_SEC) / MODE_DURATION_SEC);
}

static void printModeSwitch(int mode) {
    const RadioMode& m = modes[mode];
    char timeStr[16];
    uint32_t sec = getSecondsSinceMidnight();
    formatGpsTime(sec, timeStr, sizeof(timeStr));

    if (m.isFlrc) {
        dualPrintf("MODE_SWITCH mode=%d type=FLRC freq=%.0f bitrate=%d gps_time=%s gps_sec=%lu path=%s",
                   mode, m.freqMhz, m.flrcBitrate, timeStr, (unsigned long)sec, getPath(m));
    } else {
        dualPrintf("MODE_SWITCH mode=%d type=LoRa freq=%.0f SF=%d gps_time=%s gps_sec=%lu path=%s",
                   mode, m.freqMhz, m.loraSf, timeStr, (unsigned long)sec, getPath(m));
    }
}

// ─── Mode init — COMPLETE radio re-init for each mode ────────────────
static bool initMode(int mode) {
    const RadioMode& m = modes[mode];

    // 1. SET_STANDBY (0x0200, STDBY_RC=0x01) — known state
    { uint8_t cmd[] = { 0x02, 0x00, 0x01 }; rfWriteCmd(cmd, 3); }
    delay(5);

    // 2. SET_PACKET_TYPE (FLRC=0x04 proven, LoRa=0x00 proven)
    uint8_t pktType = m.isFlrc ? 0x04 : 0x00;
    { uint8_t cmd[] = { 0x02, 0x07, pktType }; rfWriteCmd(cmd, 3); }
    delay(1);

    // 3. SET_RF_FREQUENCY
    rfSetFreq(m.freqMhz);
    delay(1);

    // 4. SET_RX_PATH (HF=0x01 for 2.4GHz, LF=0x00 for sub-GHz) — MANDATORY
    uint8_t rxPath = m.isHF ? 0x01 : 0x00;
    { uint8_t cmd[] = { 0x02, 0x01, rxPath, 0x00 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 5. CALIB_FRONT_END — HF path sets bit 15, LF path does NOT — MANDATORY
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

    // 6. CALIBRATE (mask 0x5F — NOT 0x6F)
    { uint8_t cmd[] = { 0x01, 0x22, 0x5F }; rfWriteCmd(cmd, 3); }
    delay(5);

    // 7. SET_MOD_PARAMS + SET_PACKET_PARAMS (mode-specific)
    if (m.isFlrc) {
        // SET_FLRC_MOD_PARAMS (0x0248): brBw, CR=None+BT0.5=0x25
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

    // 8. SET_PA_CONFIG (0x0202) — PA config {0x80, 0x00, 0x60, 0x07, 0x10}
    { uint8_t cmd[] = { 0x02, 0x02, 0x80, 0x00, 0x60, 0x07, 0x10 }; rfWriteCmd(cmd, 7); }
    delay(1);

    // 9. SET_TX_PARAMS (0x0203) — TX power
    rfSetTxPower(TX_POWER_DBM);
    delay(1);

    // 10. SET_RX_TX_FALLBACK (FS=0x03)
    { uint8_t cmd[] = { 0x02, 0x06, 0x03 }; rfWriteCmd(cmd, 3); }
    delay(1);

    // 11. SET_DIO_FUNCTION (DIO9=IRQ)
    { uint8_t cmd[] = { 0x01, 0x12, 0x09, 0x11 }; rfWriteCmd(cmd, 4); }
    delay(1);

    // 12. SET_DIO_IRQ_CONFIG (TX_DONE bit 0x00080000)
    { uint8_t cmd[] = { 0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00 }; rfWriteCmd(cmd, 7); }
    delay(1);

    // 13. CLEAR_IRQ
    rfClearIrq();
    delay(10);

    // Verify
    uint8_t st = rfReadStatus();
    uint32_t irq = rfReadIrqStatus();
    dualPrintf("INIT mode=%d Status=0x%02X IRQ=0x%08lX", mode, st, (unsigned long)irq);

    if ((st >> 4) == 0x03 || (st >> 4) == 0x04 || (st >> 4) == 0x07 || (irq & 0x00020000)) {
        dualPrintf("MODE_INIT_OK mode=%d", mode);
        return true;
    }
    dualPrintf("MODE_INIT_FAIL mode=%d (St=0x%02X)", mode, st);
    return false;
}

// ─── TX burst ────────────────────────────────────────────────────────
static void runTransmit() {
    if (!radioReady) return;

    const RadioMode& m = modes[currentMode];
    uint16_t pktSize = TX_PKT_SIZE;
    uint16_t count = m.txPktCount;

    digitalWrite(PIN_LED, HIGH);
    digitalWrite(PIN_LED_ALT, HIGH);

    uint32_t burstStartMs = millis();
    char timeStr[16];
    uint32_t gpsSec = getSecondsSinceMidnight();
    formatGpsTime(gpsSec, timeStr, sizeof(timeStr));

    dualPrintf("BURST %lu START mode=%d gps_time=%s gps_sec=%lu uptime=%lums count=%d",
               (unsigned long)burstNum, currentMode, timeStr, (unsigned long)gpsSec,
               (unsigned long)burstStartMs, count);

    uint8_t pkt[256];
    for (int j = 4; j < pktSize; j++) pkt[j] = (uint8_t)(j & 0xFF);

    uint32_t irqMask = 1UL << PIN_IRQ;
    uint32_t startMs = millis();
    uint32_t txDoneCount = 0;
    uint32_t txTimeoutCount = 0;

    // IRQ spin limit: FLRC fast (500k), LoRa slow (30M)
    uint32_t spinLimit = m.isFlrc ? 500000 : 30000000;

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
        while (spinCount < spinLimit) {
            if (sio_hw->gpio_in & irqMask) { irqFired = true; break; }
            spinCount++;
            // Poll GPS during TX wait (non-blocking)
            if ((spinCount & 0xFFF) == 0) gpsPoll();
        }

        if (irqFired) txDoneCount++;
        else txTimeoutCount++;

        // Progress print for LoRa (slow — every 10 packets)
        if (!m.isFlrc && txDoneCount > 0 && (txDoneCount % 10) == 0) {
            dualPrintf("TX_PROGRESS mode=%d sent=%d fired=%lu to=%lu",
                       currentMode, i + 1,
                       (unsigned long)txDoneCount, (unsigned long)txTimeoutCount);
        }
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
    delay(m.isFlrc ? 5 : 50);  // LoRa needs longer for TX to complete

    uint32_t elapsed = millis() - startMs;
    float tput = (elapsed > 0) ? ((float)txDoneCount * pktSize * 8.0f) / elapsed : 0.0f;

    dualPrintf("BURST %lu DONE mode=%d fired=%lu to=%lu elapsed=%lums tput=%.1fkbps",
               (unsigned long)burstNum, currentMode,
               (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
               (unsigned long)elapsed, tput);

    // Structured result line with GPS time fields
    int bwKhz = getBandwidthKhz(m);
    uint32_t resultGpsSec = getSecondsSinceMidnight();
    char resultTimeStr[16];
    formatGpsTime(resultGpsSec, resultTimeStr, sizeof(resultTimeStr));

    if (m.isFlrc) {
        dualPrintf("SWEEP_TX_RESULT,mode=%d,type=FLRC,freq=%.0f,bitrate=%d,sent=%d,fired=%lu,timeout=%lu,elapsed_ms=%lu,throughput_kbps=%.1f,pktSize=%d,power=%.1f,uptime_ms=%lu,path=%s,pa_state=%s,bandwidth_khz=%d,gps_time=%s,gps_sec=%lu,clock=%s",
                   currentMode, m.freqMhz, m.flrcBitrate, count,
                   (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
                   (unsigned long)elapsed, tput, pktSize, TX_POWER_DBM,
                   (unsigned long)burstStartMs,
                   getPath(m), getPaState(), bwKhz,
                   resultTimeStr, (unsigned long)resultGpsSec,
                   usingGpsClock ? "GPS" : "MILLIS");
    } else {
        dualPrintf("SWEEP_TX_RESULT,mode=%d,type=LoRa,freq=%.0f,SF=%d,bw=%d,sent=%d,fired=%lu,timeout=%lu,elapsed_ms=%lu,throughput_kbps=%.1f,pktSize=%d,power=%.1f,uptime_ms=%lu,path=%s,pa_state=%s,bandwidth_khz=%d,gps_time=%s,gps_sec=%lu,clock=%s",
                   currentMode, m.freqMhz, m.loraSf, bwKhz, count,
                   (unsigned long)txDoneCount, (unsigned long)txTimeoutCount,
                   (unsigned long)elapsed, tput, pktSize, TX_POWER_DBM,
                   (unsigned long)burstStartMs,
                   getPath(m), getPaState(), bwKhz,
                   resultTimeStr, (unsigned long)resultGpsSec,
                   usingGpsClock ? "GPS" : "MILLIS");
    }

    burstNum++;

    digitalWrite(PIN_LED, LOW);
    digitalWrite(PIN_LED_ALT, LOW);
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
    dualPrintln("=============================================");
    dualPrintln("=== RP2040 GPS DUAL RADIO SWEEP TX       ===");
    dualPrintln("=============================================");
    dualPrintf("Modes: 0=HF_FLRC_2600 1=HF_FLRC_325 2=LF_LORA_SF7 3=LF_LORA_SF12");
    dualPrintf("GPS Cycle: %d sec (%d sec per mode)", CYCLE_LENGTH_SEC, MODE_DURATION_SEC);

    pinMode(PIN_LED, OUTPUT);
    pinMode(PIN_LED_ALT, OUTPUT);

    // ── GPS detection phase ──
    dualPrintln("GPS: Detecting (5s timeout)...");
    bootMs = millis();
    gpsInit();

    if (gpsData.present) {
        usingGpsClock = true;
        dualPrintf("GPS: ACTIVE clock=GPS sats=%d fix=%d",
                   gpsData.satellites, gpsData.fix);
        if (gpsData.timeValid) {
            char tbuf[16];
            formatGpsTime(gpsData.secondsSinceMidnight, tbuf, sizeof(tbuf));
            dualPrintf("GPS: time=%s sec=%lu", tbuf, (unsigned long)gpsData.secondsSinceMidnight);
        }
    } else {
        usingGpsClock = false;
        bootMs = millis();  // reset fallback clock to now
        dualPrintln("GPS: NOT DETECTED — using millis() fallback clock");
    }

    // LED countdown blink — time to walk away
    dualPrintln("Starting in 3s...");
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

    // Hardware reset before first init
    pinMode(PIN_RST, OUTPUT);
    digitalWrite(PIN_RST, LOW);
    delayMicroseconds(200);
    digitalWrite(PIN_RST, HIGH);
    delay(50);

    currentMode = getCurrentMode();
    radioReady = initMode(currentMode);

    if (!radioReady) {
        dualPrintln("INIT FAILED — retrying...");
        delay(2000);
        radioReady = initMode(currentMode);
    }

    if (radioReady) {
        digitalWrite(PIN_LED_ALT, HIGH);
        printModeSwitch(currentMode);
        dualPrintln("GPS SWEEP TX STARTING — unplug and walk");
    } else {
        dualPrintln("INIT FAILED TWICE — stuck");
    }
}

void loop() {
    if (radioReady) {
        // Check mode boundary using GPS-disciplined clock
        int newMode = getCurrentMode();
        if (newMode != currentMode) {
            printModeSwitch(newMode);
            radioReady = initMode(newMode);
            if (radioReady) {
                currentMode = newMode;
            } else {
                dualPrintf("MODE_INIT_RETRY mode=%d", newMode);
                delay(1000);
                radioReady = initMode(newMode);
                if (radioReady) currentMode = newMode;
            }
        }

        if (radioReady) {
            runTransmit();
            delay(modes[currentMode].txPauseMs);

            // Heartbeat to keep USB CDC alive
            if (millis() - lastHB > 5000) {
                lastHB = millis();
                uint32_t sec = getSecondsSinceMidnight();
                char tbuf[16];
                formatGpsTime(sec, tbuf, sizeof(tbuf));
                dualPrintf("[TX HB %lus] mode=%d burst=%lu gps_time=%s gps_sec=%lu clock=%s",
                           millis() / 1000, currentMode, (unsigned long)burstNum,
                           tbuf, (unsigned long)sec,
                           usingGpsClock ? "GPS" : "MILLIS");
            }
        }
    } else {
        // Blink SOS if radio dead + heartbeat so USB CDC stays alive
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(100);
        digitalWrite(PIN_LED, HIGH); delay(100); digitalWrite(PIN_LED, LOW); delay(500);
        dualPrintf("[TX DEAD %lus]", millis() / 1000);

        // Retry init
        int targetMode = getCurrentMode();
        radioReady = initMode(targetMode);
        if (radioReady) currentMode = targetMode;
    }
}
