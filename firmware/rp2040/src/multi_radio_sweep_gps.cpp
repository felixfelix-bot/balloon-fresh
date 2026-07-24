/*
 * multi_radio_sweep_gps.cpp — GPS-synced multi-radio TX sweep (14 phases)
 *
 * Autonomous TX with GPS time synchronization.
 * Cycles through ALL 14 LR2021 characterization phases using GPS UTC time
 * to select the current phase. Both TX and RX stay in sync because they
 * share the same phase schedule keyed to UTC seconds.
 *
 * GPS: GEPRC GEP-M10nano (u-blox M10) on UART0
 *   GPS TX → GP1 (RP2040 UART0 RX, NMEA data in)
 *   GPS RX → GP0 (RP2040 UART0 TX, config out, optional)
 *   115200 baud NMEA
 *
 * Output: USB CDC Serial ONLY (Serial1 is the GPS UART — do NOT print to it)
 *
 * Phase schedule (one full cycle ≈ 202 s):
 *   0: HF 2440 LoRa SF7  BW812  — 50 pkts, 15s
 *   1: HF 2440 LoRa SF9  BW812  — 50 pkts, 15s
 *   2: HF 2440 LoRa SF12 BW812  — 30 pkts, 30s
 *   3: HF 2440 FLRC 2600        — 200 pkts, 8s
 *   4: HF 2440 FLRC 1300        — 200 pkts, 8s
 *   5: HF 2440 FLRC 650         — 200 pkts, 8s
 *   6: HF 2440 FLRC 325         — 200 pkts, 8s
 *   7: LF 868  LoRa SF7  BW250  — 50 pkts, 8s
 *   8: LF 868  LoRa SF9  BW250  — 50 pkts, 20s
 *   9: LF 868  LoRa SF12 BW250  — 20 pkts, 50s
 *  10: LF 868  FLRC 2600        — 200 pkts, 8s
 *  11: LF 868  FLRC 1300        — 200 pkts, 8s
 *  12: LF 868  FLRC 650         — 200 pkts, 8s
 *  13: LF 868  FLRC 325         — 200 pkts, 8s
 *
 * Pins: SCK=GP2 MOSI=GP3 MISO=GP4 CS=GP5 BUSY=GP6 IRQ=GP7 RST=GP8
 *       GPS_RX=GP1 GPS_TX=GP0
 *       LED=GP25
 */

#include <Arduino.h>
#include <SPI.h>
#include <stdarg.h>

// ─── Output: USB CDC Serial only (Serial1 = GPS UART) ────────────────
static void outPrintf(const char* fmt, ...) {
    char buf[300];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    Serial.print(buf);
}

// ─── Pins ────────────────────────────────────────────────────────────
#define PIN_SCK     2
#define PIN_MOSI    3
#define PIN_MISO    4
#define PIN_CS      5
#define PIN_BUSY    6
#define PIN_IRQ     7
#define PIN_RST     8
#define PIN_GPS_RX  1    // RP2040 RX ← GPS TX (NMEA data)
#define PIN_GPS_TX  0    // RP2040 TX → GPS RX (optional config)
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
    // ── 868 MHz LF FLRC path ──
    {"LF-FLRC-2600",  PT_FLRC,  868.0, 0,  0, 0x00, 0, 2600, 200,  8000},
    {"LF-FLRC-1300",  PT_FLRC,  868.0, 0,  0, 0x00, 0, 1300, 200,  8000},
    {"LF-FLRC-650",   PT_FLRC,  868.0, 0,  0, 0x00, 0,  650, 200,  8000},
    {"LF-FLRC-325",   PT_FLRC,  868.0, 0,  0, 0x00, 0,  325, 200,  8000},
};
static const int NUM_PHASES = sizeof(phases) / sizeof(phases[0]);

// Total cycle duration in seconds (computed at runtime)
static uint32_t totalCycleSec = 0;

#define TX_POWER_DBM   12.5f
#define LORA_PKT_SIZE  127
#define FLRC_PKT_SIZE  255
#define GPS_BAUD       115200
#define GPS_FIX_TIMEOUT_MS 60000
#define GPS_NMEA_MAX   160

// ─── GPS data ────────────────────────────────────────────────────────
struct GpsData {
    float    lat;
    float    lon;
    uint16_t sats;
    bool     fixValid;
    uint32_t timeSec;   // seconds since midnight UTC
    bool     hasTime;   // got at least one valid time (even without fix)
};
static GpsData gps = {0, 0, 0, false, 0, false};

// ─── NMEA parser (copied from flrc_range_tx_gps.cpp) ─────────────────
static char nmeaBuf[GPS_NMEA_MAX];
static size_t nmeaLen = 0;

static void parseNMEA(const char *sentence) {
    if (strncmp(sentence, "$GPGGA", 6) == 0 || strncmp(sentence, "$GNGGA", 6) == 0) {
        char timeStr[16] = {0};
        char latStr[16] = {0};
        char ns = 'N';
        char lonStr[16] = {0};
        char ew = 'E';
        int fix = 0;
        int nsat = 0;

        // u-blox M10 sends $GNGGA (not $GPGGA). Pattern skips 2-char talker ID
        // so it works with GP, GN, GL, GA — any GNSS constellation.
        int parsed = sscanf(sentence,
            "$%*2sGGA,%15[^,],%15[^,],%c,%15[^,],%c,%d,%d,",
            timeStr, latStr, &ns, lonStr, &ew, &fix, &nsat);

        if (parsed >= 6) {
            // Parse time even without fix (u-blox sends time before fix)
            if (strlen(timeStr) >= 6) {
                int hh = (timeStr[0]-'0')*10 + (timeStr[1]-'0');
                int mm = (timeStr[2]-'0')*10 + (timeStr[3]-'0');
                int ss = (timeStr[4]-'0')*10 + (timeStr[5]-'0');
                gps.timeSec = (uint32_t)(hh*3600 + mm*60 + ss);
                gps.hasTime = true;
            }

            if (fix > 0) {
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
            }
        }
    }
    else if (strncmp(sentence, "$GPRMC", 6) == 0 || strncmp(sentence, "$GNRMC", 6) == 0) {
        char timeStr[16] = {0};
        char status = 'V';
        char latStr[16] = {0};
        char ns = 'N';
        char lonStr[16] = {0};
        char ew = 'E';

        // u-blox M10 sends $GNRMC. Same talker-skip pattern.
        int parsed = sscanf(sentence,
            "$%*2sRMC,%15[^,],%c,%15[^,],%c,%15[^,],%c,",
            timeStr, &status, latStr, &ns, lonStr, &ew);

        if (parsed >= 5) {
            if (strlen(timeStr) >= 6) {
                int hh = (timeStr[0]-'0')*10 + (timeStr[1]-'0');
                int mm = (timeStr[2]-'0')*10 + (timeStr[3]-'0');
                int ss = (timeStr[4]-'0')*10 + (timeStr[5]-'0');
                gps.timeSec = (uint32_t)(hh*3600 + mm*60 + ss);
                gps.hasTime = true;
            }

            if (status == 'A') {
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
            } else {
                gps.fixValid = false;
            }
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

static void rfClearIrq() {
    uint8_t cmd[6] = {0x01, 0x16, 0xFF, 0xFF, 0xFF, 0xFF};
    rfWriteCmd(cmd, 6);
}

static void rfSetTx() {
    uint8_t cmd[5] = {0x02, 0x0D, 0x00, 0x00, 0x00};
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

static void rfClearTxFifo() {
    uint8_t cmd[] = {0x01, 0x1F};
    rfWriteCmd(cmd, 2);
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
    uint16_t feFreq = (uint16_t)((freqMHz / 4.0f) + 0.5f);
    if (rfPath == 1) feFreq |= 0x8000;  // HF path
    uint8_t c1[] = {0x01, 0x23,
                    (uint8_t)(feFreq >> 8), (uint8_t)(feFreq & 0xFF),
                    0, 0, 0, 0, 0, 0};
    rfWriteCmd(c1, 10);
    delay(5);
    // CALIBRATE mask 0x5F (NOT 0x6F)
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

    // SET_RX_PATH — HF=1 (2.4GHz), LF=0 (868MHz) MANDATORY
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
        { uint8_t flags = 0x04; // explicit header, CRC on
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

    // IRQ: TX_DONE (bit 19 = 0x00080000)
    { uint8_t c[] = {0x01, 0x15, 0x09, 0x00, 0x08, 0x00, 0x00}; rfWriteCmd(c, 7); }
    delay(1);

    rfClearIrq();
    delay(1);
}

// ─── GPS payload embedding ───────────────────────────────────────────
// Packet layout:
//   bytes 0-1:   seq (uint16_t big-endian)
//   byte  2:     phase ID
//   bytes 3-6:   latitude (float, LE)
//   bytes 7-10:  longitude (float, LE)
//   bytes 11-12: num_sats (uint16_t BE)
//   bytes 13-14: fix_valid (uint16_t BE)
//   bytes 15-18: utc_seconds (uint32_t BE)
static void embedGPS(uint8_t *pkt) {
    memcpy(&pkt[3], &gps.lat, 4);
    memcpy(&pkt[7], &gps.lon, 4);
    pkt[11] = (uint8_t)(gps.sats >> 8);
    pkt[12] = (uint8_t)(gps.sats & 0xFF);
    pkt[13] = 0;
    pkt[14] = gps.fixValid ? 1 : 0;
    pkt[15] = (uint8_t)(gps.timeSec >> 24);
    pkt[16] = (uint8_t)(gps.timeSec >> 16);
    pkt[17] = (uint8_t)(gps.timeSec >> 8);
    pkt[18] = (uint8_t)(gps.timeSec & 0xFF);
}

// ─── Phase computation from GPS UTC time ──────────────────────────────
static int computePhaseFromUTC(uint32_t utcSec) {
    uint32_t cyclePos = utcSec % totalCycleSec;
    uint32_t acc = 0;
    for (int i = 0; i < NUM_PHASES; i++) {
        acc += phases[i].slotMs / 1000;
        if (cyclePos < acc) return i;
    }
    return NUM_PHASES - 1;  // fallback
}

static void formatUTCTime(uint32_t sec, char *buf, size_t buflen) {
    uint32_t hh = sec / 3600;
    uint32_t mm = (sec % 3600) / 60;
    uint32_t ss = sec % 60;
    snprintf(buf, buflen, "%02lu:%02lu:%02lu", (unsigned long)hh, (unsigned long)mm, (unsigned long)ss);
}

// ─── TX state ────────────────────────────────────────────────────────
static int currentPhase = -1;
static uint16_t seqInPhase = 0;
static uint32_t phaseStartMs = 0;
static uint32_t sweepStartMs = 0;  // Set when sweep begins (after GPS wait)

// ─── Setup ───────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    // GPS on UART0: GP1=RX, GP0=TX, 115200 baud
    Serial1.setRX(PIN_GPS_RX);
    Serial1.setTX(PIN_GPS_TX);
    Serial1.begin(GPS_BAUD);
    delay(2000);

    pinMode(PIN_CS, OUTPUT);
    pinMode(PIN_RST, OUTPUT);
    pinMode(PIN_IRQ, INPUT);
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    digitalWrite(PIN_RST, HIGH);
    digitalWrite(PIN_LED, LOW);

    spiRf.begin();

    // Compute total cycle seconds
    totalCycleSec = 0;
    for (int i = 0; i < NUM_PHASES; i++) {
        totalCycleSec += phases[i].slotMs / 1000;
    }

    outPrintf("=== GPS-SYNCED MULTI-RADIO TX SWEEP ===\n");
    outPrintf("Phases: %d  Cycle: %lus  Power: %.1f dBm\n",
               NUM_PHASES, (unsigned long)totalCycleSec, TX_POWER_DBM);
    for (int i = 0; i < NUM_PHASES; i++) {
        outPrintf("  [%2d] %-16s %s %.0fMHz %s %dpkts %ds\n",
                      i, phases[i].name,
                      phases[i].pktType == PT_LORA ? "LoRa" : "FLRC",
                      phases[i].freqMHz,
                      phases[i].pktType == PT_LORA ?
                          (phases[i].bwCode == 0x05 ? "BW250" : "BW812") : "",
                      phases[i].pktCount, phases[i].slotMs / 1000);
    }

    // ── Quick GPS detection: check if ANY NMEA data flows in 5s ──
    // If GPS hardware isn't connected (soldering issue), Serial1 will be
    // silent. Skip the full 60s wait and fall back immediately.
    outPrintf("=== GPS DETECTION (5s quick check) ===\n");
    uint32_t detectStart = millis();
    bool nmeaSeen = false;
    while ((millis() - detectStart) < 5000) {
        gpsPoll();
        if (Serial1.available()) { nmeaSeen = true; break; }
        digitalWrite(PIN_LED, ((millis() / 100) & 1) ? HIGH : LOW);
        delay(10);
    }

    // ── Wait for GPS time (up to 60s if NMEA detected) ──
    if (nmeaSeen) {
        outPrintf("NMEA detected — waiting for time sync (up to 60s)\n");
    } else {
        outPrintf("NO NMEA — GPS not connected, skipping to millis() fallback\n");
    }
    uint32_t gpsStart = millis();
    uint32_t timeout = nmeaSeen ? GPS_FIX_TIMEOUT_MS : 0;
    while (!gps.hasTime && (millis() - gpsStart) < timeout) {
        gpsPoll();
        digitalWrite(PIN_LED, ((millis() / 100) & 1) ? HIGH : LOW);
        delay(10);
    }

    if (gps.hasTime) {
        char tbuf[16];
        formatUTCTime(gps.timeSec, tbuf, sizeof(tbuf));
        outPrintf("GPS_TIME_ACQUIRED utc=%s fix=%d sats=%d lat=%.5f lon=%.5f\n",
                   tbuf, gps.fixValid ? 1 : 0, gps.sats, gps.lat, gps.lon);
    } else {
        outPrintf("GPS_TIMEOUT — starting with free-running timer (will drift from RX)\n");
        // Fallback: use millis()-based phase cycling if no GPS
        // This keeps TX running but won't sync with RX
    }

    digitalWrite(PIN_LED, HIGH);
    sweepStartMs = millis();  // Record sweep start for fallback phase computation
    outPrintf("=== STARTING GPS-SYNCED SWEEP ===\n");
    Serial.flush();
}

// ─── Main loop ───────────────────────────────────────────────────────
void loop() {
    gpsPoll();

    // Determine current phase
    int phase;
    if (gps.hasTime) {
        phase = computePhaseFromUTC(gps.timeSec);
    } else {
        // Fallback: millis()-based cycling relative to sweep start
        // sweepStartMs is set in setup() when the sweep actually begins.
        // This keeps TX phases aligned with RX (which starts its own for-loop
        // at approximately the same wall-clock time).
        uint32_t cyclePos = ((millis() - sweepStartMs) / 1000) % totalCycleSec;
        uint32_t acc = 0;
        phase = 0;
        for (int i = 0; i < NUM_PHASES; i++) {
            acc += phases[i].slotMs / 1000;
            if (cyclePos < acc) { phase = i; break; }
        }
    }

    // Phase change detection
    if (phase != currentPhase) {
        currentPhase = phase;
        seqInPhase = 0;
        phaseStartMs = millis();

        const Phase &p = phases[phase];
        rfInitForPhase(p);
        delay(50);

        char tbuf[16] = "NO_GPS";
        if (gps.hasTime) formatUTCTime(gps.timeSec, tbuf, sizeof(tbuf));
        outPrintf("PHASE_START %d %s %s\n", phase, p.name, tbuf);
        Serial.flush();
    }

    const Phase &p = phases[currentPhase];
    uint16_t pktSize = (p.pktType == PT_LORA) ? LORA_PKT_SIZE : FLRC_PKT_SIZE;
    uint8_t txBuf[256];

    // Fill payload pattern
    for (int i = 19; i < pktSize; i++) txBuf[i] = (uint8_t)(i ^ 0xA5);

    // Check if we still have time in this phase
    uint32_t elapsedInPhase = millis() - phaseStartMs;
    if (elapsedInPhase >= (uint32_t)p.slotMs - 200) {
        // Phase nearly over — wait for phase change
        gpsPoll();
        delay(10);
        return;
    }

    // Check if we've sent all packets
    if (seqInPhase >= p.pktCount) {
        // Sent all packets, wait for phase to end
        gpsPoll();
        delay(10);
        return;
    }

    // Build packet
    txBuf[0] = (uint8_t)(seqInPhase >> 8);
    txBuf[1] = (uint8_t)(seqInPhase & 0xFF);
    txBuf[2] = (uint8_t)currentPhase;
    embedGPS(txBuf);

    // TX
    rfClearIrq();
    rfClearTxFifo();
    rfWriteTxFifo(txBuf, pktSize);
    rfSetTx();

    // Wait for TX_DONE — poll DIO9 IRQ pin
    uint32_t irqPinMask = 1UL << PIN_IRQ;
    uint32_t spinCount = 0;
    bool irqFired = false;
    while (spinCount < 30000000) {
        if (sio_hw->gpio_in & irqPinMask) { irqFired = true; break; }
        spinCount++;
    }

    // Output per-packet log
    int16_t rssiDbm = 0; // TX doesn't have RSSI; placeholder for RX sync
    outPrintf("PKT seq=%u rssi=%d phase=%d\n", seqInPhase, rssiDbm, currentPhase);

    digitalWrite(PIN_LED, (seqInPhase & 1) ? HIGH : LOW);

    seqInPhase++;

    // Spread packets across slot
    uint32_t targetTime = (uint32_t)seqInPhase * (uint32_t)p.slotMs / (uint32_t)p.pktCount;
    elapsedInPhase = millis() - phaseStartMs;
    if (elapsedInPhase < targetTime) {
        // Wait, but keep polling GPS
        uint32_t waitMs = targetTime - elapsedInPhase;
        uint32_t waitEnd = millis() + waitMs;
        while (millis() < waitEnd) {
            gpsPoll();
            delay(1);
        }
    }

    // Flush periodically (not every packet to avoid CDC slowdown)
    if ((seqInPhase & 0x0F) == 0) Serial.flush();
}
