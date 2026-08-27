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
 *       LED=GP16 (WS2812 NeoPixel on Waveshare RP2040-Zero)
 */

#include <Arduino.h>
#include <SPI.h>
#include <stdarg.h>
#include <hardware/watchdog.h>
#include <Adafruit_NeoPixel.h>
#include "prbs.h"

// ─── Firmware self-identification (injected at build time) ───────────
// These come from tools/inject_git_version.py via -D flags.
// Fallback defines allow compilation without the extra_script.
#ifndef FW_GIT_HASH
#define FW_GIT_HASH "unknown"
#endif
#ifndef FW_BUILD_TAG
#define FW_BUILD_TAG "UNK0"
#endif
#ifndef FW_BUILD_TIME
#define FW_BUILD_TIME "1970-01-01T00:00Z"
#endif

// 7-char git hash that gets appended to every TX packet so RX can verify
// firmware compatibility. NUL-terminated for safe printing.
static const char FW_HASH_CHARS[8] = FW_GIT_HASH;

// ─── Output: USB CDC Serial only (Serial1 = GPS UART) ────────────────
// CDC watchdog: track actual USB write success, not just attempts.
// If Serial.write returns 0 for 30s, the TinyUSB CDC stack is dead.
// Fix: hardware watchdog reboot to restart USB cleanly.
static uint32_t lastCdcSuccessMs = 0;   // last time Serial.write succeeded
static uint32_t lastHeartbeatMs = 0;
#define CDC_WATCHDOG_MS       30000
#define HEARTBEAT_INTERVAL_MS 10000

static void outPrintf(const char* fmt, ...) {
    char buf[512];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);
    size_t len = strlen(buf);
    size_t written = Serial.write(buf, len);
    Serial.flush();
    if (written > 0) lastCdcSuccessMs = millis();  // only update on real success
}

// Print the boot banner — first thing on serial, and on FW_QUERY.
// Also printed on USB CDC reconnect (called from setup).
static void printBootBanner() {
    outPrintf("FW_BOOT hash=%s tag=%s built=%s\r\n",
              FW_GIT_HASH, FW_BUILD_TAG, FW_BUILD_TIME);
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
#define PIN_NEOPIXEL 16   // Waveshare RP2040-Zero onboard WS2812
#define PIN_LED       25   // Standard Pi Pico (fallback, no-op on RP2040-Zero)

// Single NeoPixel on GP16
Adafruit_NeoPixel statusLED(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

// LED color helpers — show status as visible colors
void ledColor(uint8_t r, uint8_t g, uint8_t b) {
    statusLED.setPixelColor(0, statusLED.Color(r, g, b));
    statusLED.show();
}

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
    uint16_t pktSize;    // V4: payload size for this phase (32/64/128/255)
} Phase;

static const Phase phases[] = {
    // ── 2.4 GHz HF path ── REORDERED: FLRC before SF12 for gentler transitions
    {"HF-LoRa-SF7",   PT_LORA, 2440.0, 1,  7, 0x0F, 1,    0,  50, 15000, 255},
    {"HF-LoRa-SF9",   PT_LORA, 2440.0, 1,  9, 0x0F, 1,    0,  50, 15000, 255},
    // FLRC first — transitions from fast LoRa (SF9) to FLRC is gentle
    {"HF-FLRC-325",   PT_FLRC, 2440.0, 1,  0, 0x00, 0,  325, 200,  8000, 255},
    {"HF-FLRC-650",   PT_FLRC, 2440.0, 1,  0, 0x00, 0,  650, 200,  8000, 255},
    {"HF-FLRC-1300",  PT_FLRC, 2440.0, 1,  0, 0x00, 0, 1300, 200,  8000, 255},
    {"HF-FLRC-2600",  PT_FLRC, 2440.0, 1,  0, 0x00, 0, 2600, 200,  8000, 255},
    // SF12 last in HF — 500ms extra gap added after SF12→LF transition
    {"HF-LoRa-SF12",  PT_LORA, 2440.0, 1, 12, 0x0F, 1,    0,  15, 30000, 255},
    // ── 868 MHz LF path ──
    {"LF-LoRa-SF7",   PT_LORA,  868.0, 0,  7, 0x05, 1,    0,  50,  8000, 255},
    {"LF-LoRa-SF9",   PT_LORA,  868.0, 0,  9, 0x05, 1,    0,  30, 20000, 255},  // V3: reduced for 255B
    {"LF-LoRa-SF12",  PT_LORA,  868.0, 0, 12, 0x05, 1,    0,  10, 50000, 255},  // V3: halved for 255B
    // ── 868 MHz LF FLRC path ──
    // FLRC reordered narrow→wide for gradual bandwidth transitions
    {"LF-FLRC-325",   PT_FLRC,  868.0, 0,  0, 0x00, 0,  325, 200,  8000, 255},
    {"LF-FLRC-650",   PT_FLRC,  868.0, 0,  0, 0x00, 0,  650, 200,  8000, 255},
    {"LF-FLRC-1300",  PT_FLRC,  868.0, 0,  0, 0x00, 0, 1300, 200,  8000, 255},
    {"LF-FLRC-2600",  PT_FLRC,  868.0, 0,  0, 0x00, 0, 2600, 200,  8000, 255},
};
static const int NUM_PHASES = sizeof(phases) / sizeof(phases[0]);

// ─── V4: Interleave mode — 14 modes × 4 sizes = 56 phases ───────────
// Each mode tested at {32, 64, 128, 255} bytes within a compact time window.
// TX and RX both compute phase from UTC, so they stay synchronized.
static const uint16_t SWEEP_SIZES[] = {32, 64, 128, 255};
#define NUM_SWEEP_SIZES 4

static Phase interleavePhases[128];  // V4: increased for channel sweep
static int   numInterleavePhases = 0;
static bool  interleaveMode = true;   // V4: DEFAULT ON — no serial command needed for walk

// PRBS-15 mode gate: ON by default for range test (BER measurement)
// OFF for throughput testing (PRBS fill costs ~5-10ms on 255B)
static bool prbs_enabled = true;

// PRBS payload starts at byte 29 (after sync 0-3, GPS 4-28)
// and ends at pktSize-3 (before 2-byte CRC at pktSize-2..pktSize-1)
#define PRBS_START 29

// V4: Channel sweep frequencies — WiFi channels (2.4GHz) + EU 868MHz sub-bands
static const float SWEEP_FREQS_HF[] = {
    2412.0, 2417.0, 2422.0, 2427.0, 2432.0, 2437.0,
    2442.0, 2447.0, 2452.0, 2457.0, 2462.0, 2467.0, 2472.0  // WiFi ch1-ch13
};
#define NUM_SWEEP_FREQS_HF 13
static const float SWEEP_FREQS_LF[] = {
    863.0, 864.0, 865.0, 866.0, 867.0, 868.0, 869.0, 870.0
};
#define NUM_SWEEP_FREQS_LF 8

static void buildInterleaveTable() {
    int idx = 0;
    static char nameBufs[128][32];

    for (int mode = 0; mode < NUM_PHASES; mode++) {
        const Phase &base = phases[mode];

        for (int s = 0; s < NUM_SWEEP_SIZES; s++) {
            Phase &exp = interleavePhases[idx];
            exp = base;  // copy base fields
            exp.pktSize = SWEEP_SIZES[s];

            bool skip = false;

            if (base.pktType == PT_FLRC) {
                // FLRC: all sizes trivial (< 7ms air time)
                exp.pktCount = 100;
                exp.slotMs   = 3000;  // V4: match RX, reliable reconfig
            } else {
                // LoRa: compute air time and size accordingly
                // Air time estimate (ms per byte) at given SF and BW:
                //   HF BW812: SF7=0.44, SF9=1.71, SF12=31
                //   LF BW250: SF7=1.6,  SF9=12.8, SF12=410
                float msPerByte;
                if (base.rfPath == 1) {  // HF
                    if (base.sf == 7)       msPerByte = 0.44f;
                    else if (base.sf == 9)  msPerByte = 1.71f;
                    else                    msPerByte = 31.0f;
                } else {                  // LF
                    if (base.sf == 7)       msPerByte = 1.6f;
                    else if (base.sf == 9)  msPerByte = 12.8f;
                    else                    msPerByte = 410.0f;
                }

                float airMs = msPerByte * SWEEP_SIZES[s] + 10.0f;

                // LF-LoRa-SF12 at >32B: air time is impractical (26s+ per packet)
                if (base.rfPath == 0 && base.sf == 12 && s > 0) {
                    skip = true;
                    exp.pktCount = 0;
                    exp.slotMs   = 1000;  // 1s placeholder
                } else {
                    // Target 3-5s of TX time, clamp to reasonable limits
                    int targetPkts = (int)(3000.0f / airMs);
                    if (targetPkts < 1) targetPkts = 1;
                    if (targetPkts > 20) targetPkts = 20;
                    exp.pktCount = targetPkts;

                    float slotTime = targetPkts * airMs * 1.3f + 500.0f;
                    if (slotTime < 2000.0f)  slotTime = 2000.0f;
                    if (slotTime > 15000.0f) slotTime = 15000.0f;
                    exp.slotMs = (uint16_t)slotTime;
                }
            }

            // Build phase name
            if (skip) {
                snprintf(nameBufs[idx], 32, "%s-SKIP", base.name);
            } else {
                snprintf(nameBufs[idx], 32, "%s-%d", base.name, SWEEP_SIZES[s]);
            }
            exp.name = nameBufs[idx];

            idx++;
        }
    }
    
    // V4: Channel sweep — FLRC-1300-64B at every WiFi channel + 868MHz sub-band
    // Purpose: characterize which frequencies are affected by WiFi interference
    for (int f = 0; f < NUM_SWEEP_FREQS_HF; f++) {
        Phase &exp = interleavePhases[idx];
        exp = phases[4];  // HF-FLRC-1300 base (phases[4] = HF-FLRC-1300)
        exp.freqMHz = SWEEP_FREQS_HF[f];
        exp.pktSize = 64;
        exp.pktCount = 100;
        exp.slotMs = 3000;
        snprintf(nameBufs[idx], 32, "CH-%d-FLRC1300-64", (int)SWEEP_FREQS_HF[f]);
        exp.name = nameBufs[idx];
        idx++;
    }
    for (int f = 0; f < NUM_SWEEP_FREQS_LF; f++) {
        Phase &exp = interleavePhases[idx];
        exp = phases[12];  // LF-FLRC-1300 base (phases[12] = LF-FLRC-1300)
        exp.freqMHz = SWEEP_FREQS_LF[f];
        exp.pktSize = 64;
        exp.pktCount = 100;
        exp.slotMs = 3000;
        snprintf(nameBufs[idx], 32, "CH-%d-FLRC1300-64", (int)SWEEP_FREQS_LF[f]);
        exp.name = nameBufs[idx];
        idx++;
    }
    
    numInterleavePhases = idx;
}

// Total cycle duration in seconds (computed at runtime)
static uint32_t totalCycleSec = 0;

#define TX_POWER_DBM   12.5f
#define LORA_PKT_SIZE  255
#define FLRC_PKT_SIZE  255
#define GPS_BAUD       115200  // GEP-M10nano ships at 115200 (confirmed by speed-tests track)
#define GPS_FIX_TIMEOUT_MS 60000
#define GPS_NMEA_MAX   160

// ─── GPS data ────────────────────────────────────────────────────────
struct GpsData {
    float    lat;
    float    lon;
    float    alt;        // MSL altitude (meters) — from GGA field 9
    float    hdop;       // horizontal dilution of precision — from GGA field 8
    uint16_t sats;
    bool     fixValid;
    uint32_t timeSec;   // seconds since midnight UTC
    bool     hasTime;   // got at least one valid time (even without fix)
    uint32_t unixTime;    // true Unix epoch seconds (date + time from RMC)
    bool     hasUnixTime; // GPS gave us a complete date+time → real Unix epoch
};
static GpsData gps = {0, 0, 0, 0, 0, false, 0, false, 0, false};

// ─── Harmonized PKT session/config state (M3) ────────────────────────
// session_id and config_id are set via serial commands (SESSION/CONFIG).
// replicate tracks repeated runs of the same config.
static char     sessionId[32] = "";   // set by SESSION <id> command
static char     configId[32]  = "";   // set by CONFIG <id> command
static uint32_t replicate    = 0;   // incremented on CONFIG_START

// ─── GPS time offset for autonomous clock hold ──────────────────────
// When GPS gives Unix time, we store offset = unixTime - millis()/1000.
// If GPS time becomes stale (module issue, antenna disconnect), we
// extrapolate from millis() + offset. RP2040 crystal is accurate enough
// for phase sync over minutes. This allows TX to keep sweeping even if
// GPS stops sending NMEA sentences entirely.
static int32_t  gpsTimeOffset  = 0;    // unix_time = millis()/1000 + gpsTimeOffset
static uint32_t lastGpsTimeMs  = 0;    // millis() when last GPS unix time was received
#define GPS_TIME_STALE_MS  10000       // after 10s without GPS update, use offset hold

// Forward declarations — defined later in the file
static uint32_t getUtcNow();
static bool     hasLaptopTime();

// Unified time source selector — used by main loop, embedGPS, heartbeat.
// Priority: fresh GPS > GPS hold (millis+offset) > laptop SET_TIME > degraded.
static uint32_t getBestUnixTime() {
    if (gps.hasUnixTime && gps.unixTime > 0 &&
        (millis() - lastGpsTimeMs) < GPS_TIME_STALE_MS)
        return gps.unixTime;                    // fresh GPS — primary
    if (gpsTimeOffset != 0)
        return millis() / 1000 + gpsTimeOffset; // GPS hold — extrapolate
    if (hasLaptopTime())
        return getUtcNow();                     // laptop SET_TIME — bench only
    if (gps.hasUnixTime)
        return gps.unixTime;                    // stale GPS — better than 0
    return gps.timeSec;                         // seconds since midnight (degraded)
}

// ─── Days-since-1970 helper (Howard Hinnant's civil-from-days algorithm) ──
static uint32_t daysSinceEpoch(uint16_t year, uint8_t month, uint8_t day) {
    if (month <= 2) { year--; month += 12; }  // Jan/Feb → months 13/14 of prev year
    uint32_t era = year / 400;
    uint32_t yoe = year - era * 400;                         // [0, 399]
    uint32_t doy = (153 * (month - 3) + 2) / 5 + day - 1;   // [0, 365]
    uint32_t doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;   // [0, 146096]
    return era * 146097 + doe - 719468;                       // days since 1970-01-01
}

// ─── Fault-tolerant DDMMYY date extraction ───────────────────────────
// Scans an NMEA sentence for a 6-digit date pattern instead of relying on
// comma field counting (which fails when characters are dropped and field
// positions shift). Works on garbled/merged sentences.
//
// False-match rejection heuristics:
//   - Stop scanning at '*' (checksum area — hex digits, not dates)
//   - Only scan first 160 chars (merged sentences could be very long)
//   - The 6 digits must NOT be preceded by a digit (avoids matching inside
//     longer numbers like speed/course fields)
//   - The 6 digits must NOT be followed by a digit or '.' (excludes time
//     field HHMMSS.ss and lat/lon DDMM.MMMM fields)
//   - DD must be 01-31, MM must be 01-12
static bool extractDatePattern(const char *sentence,
                               uint8_t *outDay, uint8_t *outMonth, uint16_t *outYear) {
    size_t scanLen = strlen(sentence);
    if (scanLen > 160) scanLen = 160;   // only search first sentence worth of data

    for (size_t i = 0; i + 6 <= scanLen; i++) {
        const char *p = sentence + i;

        // Stop at checksum marker — everything after '*' is hex, not a date
        if (*p == '*') break;

        // Must not be preceded by a digit (avoid matching inside longer numbers)
        if (i > 0 && isdigit((unsigned char)sentence[i - 1])) continue;

        // Must be 6 consecutive digits
        if (!isdigit((unsigned char)p[0]) || !isdigit((unsigned char)p[1]) ||
            !isdigit((unsigned char)p[2]) || !isdigit((unsigned char)p[3]) ||
            !isdigit((unsigned char)p[4]) || !isdigit((unsigned char)p[5]))
            continue;

        // Must not be followed by a digit or '.' (excludes HHMMSS.ss, DDMM.MMMM)
        if (i + 6 < scanLen) {
            char after = sentence[i + 6];
            if (isdigit((unsigned char)after) || after == '.') continue;
        }

        int dd = (p[0] - '0') * 10 + (p[1] - '0');
        int mo = (p[2] - '0') * 10 + (p[3] - '0');
        int yy = (p[4] - '0') * 10 + (p[5] - '0');

        if (dd >= 1 && dd <= 31 && mo >= 1 && mo <= 12) {
            *outDay   = (uint8_t)dd;
            *outMonth = (uint8_t)mo;
            *outYear  = (uint16_t)(2000 + yy);  // NMEA 2-digit year → 20YY
            return true;   // FIRST valid date pattern wins
        }
    }
    return false;
}

// ─── NMEA parser (copied from flrc_range_tx_gps.cpp) ─────────────────
static char nmeaBuf[GPS_NMEA_MAX];
static size_t nmeaLen = 0;

static void parseNMEA(const char *sentence) {
    // u-blox M10 native prefix support: $%*2sGGA matches GP/GN/GL/GA talker IDs
    if (strstr(sentence, "GGA")) {
        char timeStr[16] = {0};
        char latStr[16] = {0};
        char ns = 'N';
        char lonStr[16] = {0};
        char ew = 'E';
        int fix = 0;
        int nsat = 0;

        int parsed = sscanf(sentence,
            "$%*2sGGA,%15[^,],%15[^,],%c,%15[^,],%c,%d,%d,%f,%f,",
            timeStr, latStr, &ns, lonStr, &ew, &fix, &nsat, &gps.hdop, &gps.alt);

        // GGA: $GNGGA,hhmmss.ss,llll.ll,N,yyyyy.yy,E,f,nn,...
        // With no fix: $GNGGA,hhmmss.ss,,,,,0,00,...
        // sscanf stops at first empty field. parsed >= 1 = time present.
        if (parsed >= 1) {
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
    else if (strstr(sentence, "RMC")) {
        char timeStr[16] = {0};
        char status = 'V';
        char latStr[16] = {0};
        char ns = 'N';
        char lonStr[16] = {0};
        char ew = 'E';

        int parsed = sscanf(sentence,
            "$%*2sRMC,%15[^,],%c,%15[^,],%c,%15[^,],%c,",
            timeStr, &status, latStr, &ns, lonStr, &ew);

        // RMC: $GNRMC,hhmmss.ss,V/A,lat,N,lon,E,...,ddmmyy,...
        // With no fix: $GNRMC,hhmmss.ss,V,,,,,,,ddmmyy,,,N,V
        // sscanf stops at first empty field (,,) so parsed < 6 is normal.
        // We only need parsed >= 2 (time + status) to extract time.
        if (parsed >= 2) {
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

        // ── Parse date (DDMMYY) for real Unix epoch ──
        // ROBUSTNESS FIX: Pattern-match instead of comma-counting.
        // Handles garbled/merged sentences where dropped characters shift
        // field positions. Scans the entire (truncated to 160 chars) sentence
        // for a valid DDMMYY pattern, stopping at '*' checksum boundary.
        if (gps.hasTime) {
            uint8_t  dDay, dMo;
            uint16_t dYear;
            if (extractDatePattern(sentence, &dDay, &dMo, &dYear)) {
                uint32_t days = daysSinceEpoch(dYear, dMo, dDay);
                gps.unixTime    = days * 86400UL + gps.timeSec;
                gps.hasUnixTime = true;
                // Track offset for autonomous clock hold — if GPS time
                // becomes stale later, we extrapolate from millis().
                gpsTimeOffset = (int32_t)(gps.unixTime - millis() / 1000);
                lastGpsTimeMs = millis();
                outPrintf("GPS_UNIX: days=%lu timeSec=%lu unix=%lu offset=%ld\n",
                          (unsigned long)days, (unsigned long)gps.timeSec,
                          (unsigned long)gps.unixTime, (long)gpsTimeOffset);
            }
        }
    }
}

// gpsPoll() drains the Serial1 UART ring buffer into the NMEA parser.
// IMPORTANT: Must be called at least every 50ms. During SPI radio ops
// (rfInitForPhase, TX spin), the UART ISR still drains the HW FIFO into
// the 1024-entry software ring buffer, but gpsPoll() must run to parse
// accumulated sentences before the ring buffer overflows on long gaps.
static void gpsPoll() {
    while (Serial1.available()) {
        char c = Serial1.read();
        if (c == '$') {
            nmeaLen = 0;
            nmeaBuf[nmeaLen++] = c;
        } else if (c == '\n' || c == '\r') {
            if (nmeaLen > 6) {
                nmeaBuf[nmeaLen] = '\0';
                // DEBUG: dump any RMC sentence to see date field
                if (strstr(nmeaBuf, "RMC")) {
                    outPrintf("NMEA_RMC: %s\n", nmeaBuf);
                }
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
    // Timeout 0xFFFFFF = max (~262s); 0x000000 = no timeout (TX hangs if IRQ missed). [ESP32 fix]
    uint8_t cmd[5] = {0x02, 0x0D, 0xFF, 0xFF, 0xFF};
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

// ─── Phase transition safety: abort any in-progress TX ──────────────
// SF12 packets have extreme air times:
//   HF-LoRa-SF12-255B: ~7.9s (31ms/byte × 255 + 10ms preamble)
//   LF-LoRa-SF12-32B:  ~13.1s (410ms/byte × 32 + 10ms)
// The TX spin loop below has a bounded timeout (16s). When a phase
// boundary falls while TX is still active, the radio remains mid-TX.
// Calling rfInitForPhase() in that state triggers a hardware reset
// during active transmission — the radio can enter an undefined state.
//
// This function checks if TX_DONE has fired (IRQ pin HIGH). If not, it
// force-aborts by sending SET_STANDBY (STDBY_XOSC) before the next
// phase reconfigures the modem. Called at the TOP of every phase change,
// BEFORE rfInitForPhase.
//
// BUG FIX: The IRQ pin (GP7) is LOW both when TX is mid-transmission AND
// when the radio is idle with no TX ever started. Without a tracking flag,
// every phase transition when GPS gates TX (no fix → no TX) triggered a
// false TX_ABORT. We now track txInProgress so we only abort when a TX was
// actually started and hasn't completed.
static volatile bool txInProgress = false;

static void abortTxIfActive() {
    if (!txInProgress) return;  // No TX was started, nothing to abort

    uint32_t irqPinMask = 1UL << PIN_IRQ;
    if (sio_hw->gpio_in & irqPinMask) {
        // TX_DONE already fired — radio returned to fallback mode (STDBY)
        txInProgress = false;
        return;
    }
    // TX genuinely in progress — force-abort with SET_STANDBY (STDBY_XOSC)
    uint8_t stdby[] = {0x01, 0x28, 0x01};
    rfWriteCmd(stdby, 3);
    outPrintf("TX_ABORT — previous phase TX still active, force SET_STANDBY\n");
    rfClearIrq();   // clear stale IRQ bits from the aborted TX
    txInProgress = false;
    delay(100);     // guard: let the radio settle before reconfiguration
}

// ─── App-layer CRC-16 (CCITT 0x1021) ────────────────────────────────
// Hardware CRC passes garbage — this is the application-layer integrity check.
// Computed over the 18-byte GPS+seq payload (bytes 4-21 of TX buffer).
static uint16_t crc16(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint16_t)data[i] << 8;
        for (int b = 0; b < 8; b++)
            crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : (crc << 1);
    }
    return crc;
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

// ─── Channel sweep: cycle HF/LF frequencies per UTC cycle ──────────
// Both TX and RX derive the same cycle number from UTC, so they auto-sync.
// WiFi channels 1-13: 2412-2472 MHz. Clean spots between/above channels.
static uint32_t getUtcNow();  // forward declare — defined later
static const float HF_CHANNELS[] = {
    2422.0,  // between WiFi ch3/ch4
    2437.0,  // WiFi ch6 center (worst case)
    2440.0,  // current baseline
    2452.0,  // between ch9/ch10
    2462.0,  // WiFi ch11 center
    2478.0,  // above WiFi — cleanest
    2483.0,  // max LR2021 HF freq
};
#define NUM_HF_CHANNELS 7

static const float LF_CHANNELS[] = {
    863.0,   // bottom of EU 868 SRD band
    865.0,
    867.0,
    868.0,   // current baseline
    869.5,   // high-power sub-band center
};
#define NUM_LF_CHANNELS 5

static bool channelSweepMode = true;  // ON for characterization, OFF for walk test
static uint32_t currentCycle = 0;
static float currentChanFreq = 0;

static float getChannelFreq(uint8_t rfPath, uint32_t utcSec) {
    if (!channelSweepMode) return 0;  // 0 = use phase table default
    uint32_t divisor = (totalCycleSec > 0) ? totalCycleSec : 158;
    uint32_t cycle = utcSec / divisor;
    currentCycle = cycle;
    if (rfPath == 1) {
        return HF_CHANNELS[cycle % NUM_HF_CHANNELS];
    } else {
        return LF_CHANNELS[cycle % NUM_LF_CHANNELS];
    }
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

        // SET_LORA_PACKET_PARAMS: preamble=8, payload=pktSize, explicit, CRC on
        { uint8_t flags = 0x04; // explicit header, CRC on
          uint8_t c[] = {0x02, 0x21, 0x00, 0x08, (uint8_t)p.pktSize, flags};
          rfWriteCmd(c, 6); }
        delay(1);

    } else {
        // SET_FLRC_MODULATION_PARAMS (0x0248)
        // CR=3/4 (0x1) + BT=0.5 (0x5) = 0x15 — FEC for error correction
        uint8_t brBw = flrcBitrateToCode(p.flrcBr);
        { uint8_t c[] = {0x02, 0x48, brBw, 0x15}; rfWriteCmd(c, 4); }
        delay(1);

        // SET_FLRC_SYNC_WORD (0x024C)
        { uint8_t c[] = {0x02, 0x4C, 0x01, 0x12, 0xAD, 0x10, 0x1B}; rfWriteCmd(c, 7); }
        delay(1);

        // SET_FLRC_PACKET_PARAMS (0x0249) — V4: dynamic pktSize
        // byte2: 0x0E = agc_pbl_len=3 (16-bit preamble) | sw_len=2 (32-bit sync word)
        // byte3: 0x7C = crc=10 (CRC24) | pkt_format=1 (Fixed) | sw_match=111 (Match123)
        //   was 0x4C (crc=01 CRC16-off, pkt_format=0 Dynamic, sw_match=100 Match1)
        //   matched TheClams reference: CRC24 + Match123, keep Fixed format
        { uint8_t c[] = {0x02, 0x49, 0x0E, 0x7C, 0x00, (uint8_t)p.pktSize}; rfWriteCmd(c, 6); }
        delay(1);
    }

    // SET_TX_PATH (0x0202) -- MANDATORY before TX. HF=1 (2.4GHz), LF=0 (sub-GHz).
    // Same opcode as SET_PA_CONFIG, distinguished by payload. [ESP32 lr2021_radio.c:286]
    { uint8_t c[] = {0x02, 0x02, p.rfPath, 0x00}; rfWriteCmd(c, 4); }
    delay(1);

    // SET_PA_CONFIG (0x0202) -- HF=0x80, LF=0x00 [LR2021Raw.h setPaConfig/setPaConfigLF]
    { uint8_t c[] = {0x02, 0x02, (uint8_t)(p.rfPath ? 0x80 : 0x00), 0x00, 0x60, 0x07, 0x10}; rfWriteCmd(c, 7); }
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
// Packet layout (MUST match RX parseGPS in multi_radio_sweep_rx.cpp):
//   bytes 0-3:   sync header (0xA5 0x5A 0x42 0x24)
//   bytes 4-7:   latE7 (int32 LE)  — lat*1e7
//   bytes 8-11:  lonE7 (int32 LE) — lon*1e7
//   bytes 12-13: sats (uint16 LE)
//   byte  14:    fixQ (uint8)
//   bytes 15-18: utcSec (uint32 LE)
//   byte  19:    phaseId (written by caller)
//   bytes 20-21: seq (written by caller)
//   bytes 22-28: fw_hash (7 ASCII chars, written by caller)
// Note: FLRC hardware strips sync word (bytes 0-3) before FIFO, so RX
//       uses gpsOff=0 for FLRC and gpsOff=4 for LoRa.
// ─── Laptop time sync (SET_TIME) ─────────────────────────────────────
// TX accepts SET_TIME over USB, same as RX.
// Operator plugs TX into laptop, sends SET_TIME, unplugs. RP2040 keeps
// millis() running on battery → UTC stays correct for the walk.
static uint32_t utcOffset = 0;  // offset: unix_time = millis()/1000 + utcOffset

static uint32_t getUtcNow() {
    return millis() / 1000 + utcOffset;
}

static bool hasLaptopTime() {
    return utcOffset > 0;
}

// ─── PRBS-9 hardware test mode (LR2021 TX_TEST_MODE register) ──────────
// When enabled, the LR2021 chip generates PRBS-9 modulation internally,
// bypassing the FIFO data. This is a hardware-level test mode, distinct
// from the software PRBS-15 payload fill (prbs_enabled).
static bool prbs9_enabled = false;

// LR2021 TX_TEST_MODE opcodes (from lr20xx driver: SET_TX_TEST_MODE = 0x020E)
#define LR20XX_TX_TEST_MODE_NORMAL  0x00
#define LR20XX_TX_TEST_MODE_PRBS9   0x03

static void rfSetTxTestMode(uint8_t mode) {
    uint8_t cmd[3] = {0x02, 0x0E, mode};
    rfWriteCmd(cmd, 3);
}

// Safety check: is TX currently in flight (IRQ pin LOW = TX active)?
static bool isTxActive() {
    uint32_t irqPinMask = 1UL << PIN_IRQ;
    return !(sio_hw->gpio_in & irqPinMask);
}

// Non-blocking: check Serial for SET_TIME command
static void checkSerialTimeSync() {
    if (!Serial.available()) return;
    static char syncBuf[128];
    static int syncLen = 0;
    while (Serial.available()) {
        char c = Serial.read();
        if (c == '\n' || c == '\r') {
            if (syncLen > 0) {
                syncBuf[syncLen] = '\0';
                if (strncmp(syncBuf, "SET_TIME ", 9) == 0) {
                    uint32_t ts = (uint32_t)strtoul(syncBuf + 9, nullptr, 10);
                    if (ts > 0) {
                        utcOffset = ts - millis() / 1000;
                        lastCdcSuccessMs = 0;  // Disarm CDC watchdog for battery mode
                        outPrintf("TIME_SYNCED unix=%lu offset=%ld\n",
                                      (unsigned long)getUtcNow(), (long)utcOffset);
                        }
                } else if (strcmp(syncBuf, "FW_QUERY") == 0) {
                    // Firmware identification query — respond with boot banner
                    printBootBanner();
                } else if (strncmp(syncBuf, "SET_INTERLEAVE ", 15) == 0) {
                    // V4: Toggle interleave mode (14 modes × 4 sizes = 56 phases)
                    int val = atoi(syncBuf + 15);
                    interleaveMode = (val != 0);
                    // currentPhase is declared later; phase detection will handle switch
                    // Recompute cycle time
                    totalCycleSec = 0;
                    if (interleaveMode) {
                        for (int i = 0; i < numInterleavePhases; i++)
                            totalCycleSec += interleavePhases[i].slotMs / 1000;
                        outPrintf("INTERLEAVE_ON phases=%d cycle=%lus\n",
                                   numInterleavePhases, (unsigned long)totalCycleSec);
                        for (int i = 0; i < numInterleavePhases; i++) {
                            outPrintf("  [%2d] %-24s %dpkts %ds %dB\n",
                                i, interleavePhases[i].name,
                                interleavePhases[i].pktCount,
                                interleavePhases[i].slotMs / 1000,
                                interleavePhases[i].pktSize);
                        }
                    } else {
                        for (int i = 0; i < NUM_PHASES; i++)
                            totalCycleSec += phases[i].slotMs / 1000;
                        outPrintf("INTERLEAVE_OFF phases=%d cycle=%lus\n",
                                   NUM_PHASES, (unsigned long)totalCycleSec);
                    }
                } else if (strncmp(syncBuf, "SESSION ", 8) == 0) {
                    // SESSION <id> — set session identifier for PKT lines
                    strncpy(sessionId, syncBuf + 8, sizeof(sessionId) - 1);
                    sessionId[sizeof(sessionId) - 1] = '\0';
                    outPrintf("SESSION_SET %s\n", sessionId);
                } else if (strncmp(syncBuf, "CONFIG ", 7) == 0) {
                    // CONFIG <id> — set config identifier and bump replicate
                    strncpy(configId, syncBuf + 7, sizeof(configId) - 1);
                    configId[sizeof(configId) - 1] = '\0';
                    replicate++;
                    outPrintf("CONFIG_SET %s replicate=%lu\n",
                              configId, (unsigned long)replicate);
                } else if (strncmp(syncBuf, "PRBS ", 5) == 0) {
                    if (strcmp(syncBuf + 5, "ON") == 0) {
                        prbs_enabled = true;
                        outPrintf("PRBS_ENABLED\n");
                    } else if (strcmp(syncBuf + 5, "OFF") == 0) {
                        prbs_enabled = false;
                        outPrintf("PRBS_DISABLED\n");
                    } else {
                        outPrintf("ERR PRBS SYNTAX (use: PRBS ON|OFF)\n");
                    }
                } else if (strncmp(syncBuf, "CONFIG PRBS9 ", 13) == 0) {
                    // CONFIG PRBS9 ON|OFF — hardware PRBS-9 test mode via LR2021 register
                    // Safety: cannot enable while TX is in flight (IRQ pin LOW = TX active)
                    if (strcmp(syncBuf + 13, "ON") == 0) {
                        if (isTxActive()) {
                            outPrintf("ERR PRBS9 TX_ACTIVE (STOP FIRST)\n");
                        } else {
                            rfSetTxTestMode(LR20XX_TX_TEST_MODE_PRBS9);
                            prbs9_enabled = true;
                            outPrintf("OK PRBS9 ON\n");
                        }
                    } else if (strcmp(syncBuf + 13, "OFF") == 0) {
                        if (isTxActive()) {
                            outPrintf("ERR PRBS9 TX_ACTIVE (STOP FIRST)\n");
                        } else {
                            rfSetTxTestMode(LR20XX_TX_TEST_MODE_NORMAL);
                            prbs9_enabled = false;
                            outPrintf("OK PRBS9 OFF\n");
                        }
                    } else {
                        outPrintf("ERR PRBS9 SYNTAX (use: CONFIG PRBS9 ON|OFF)\n");
                    }
                }
                syncLen = 0;
            }
        } else {
            if (syncLen < (int)sizeof(syncBuf) - 1) syncBuf[syncLen++] = c;
        }
    }
}

static void embedGPS(uint8_t *pkt) {
    // MUST match RX parseGPS in multi_radio_sweep_rx.cpp
    // pkt[0-3] = sync header (already written by caller)
    // pkt[4-7]:   latE7 (int32 LE)  — lat*1e7
    // pkt[8-11]:  lonE7 (int32 LE)  — lon*1e7
    // pkt[12-13]: sats (uint16 LE)
    // pkt[14]:    fixQ (uint8)
    // pkt[15-18]: utcSec (uint32 LE)
    // pkt[19]:    phaseId (written by caller)
    // pkt[20-21]: seq (written by caller)
    int32_t latE7 = (int32_t)(gps.lat * 1e7f);
    int32_t lonE7 = (int32_t)(gps.lon * 1e7f);
    memcpy(&pkt[4], &latE7, 4);
    memcpy(&pkt[8], &lonE7, 4);
    uint16_t sats = gps.sats;
    memcpy(&pkt[12], &sats, 2);
    pkt[14] = gps.fixValid ? 1 : 0;
    // Embed Unix epoch time — uses unified time source selector.
    // Handles: fresh GPS, GPS hold (millis+offset), laptop SET_TIME.
    uint32_t unixNow = getBestUnixTime();
    memcpy(&pkt[15], &unixNow, 4);  // LE via memcpy
}

// ─── Phase computation from absolute time ─────────────────────────────
// Both TX and RX use the SAME clock: Unix epoch seconds.
// Phase = unixTime % cycleSec. Both boards synced as long as both know Unix time.
// TX gets Unix time from: SET_TIME (laptop), GPS (if available), or millis() fallback.
// V4: Use MILLISECOND precision to avoid integer truncation drift.
// Old code did slotMs/1000 which lost 0.5s+ per slot, accumulating
// 15-28 seconds of error over 56 phases. Now uses totalCycleMs.
static uint32_t totalCycleMs = 0;

static int computePhaseFromUTC(uint32_t utcSec) {
    // Convert to milliseconds for precision
    uint32_t cyclePosMs = (utcSec * 1000) % totalCycleMs;
    uint32_t accMs = 0;
    if (interleaveMode) {
        for (int i = 0; i < numInterleavePhases; i++) {
            accMs += interleavePhases[i].slotMs;  // milliseconds, no truncation!
            if (cyclePosMs < accMs) return i;
        }
        return numInterleavePhases - 1;
    }
    for (int i = 0; i < NUM_PHASES; i++) {
        accMs += phases[i].slotMs;
        if (cyclePosMs < accMs) return i;
    }
    return NUM_PHASES - 1;
}

// V4: Get the active phase entry by index (interleave or base)
static const Phase* getPhaseEntry(int idx) {
    if (interleaveMode) return &interleavePhases[idx];
    return &phases[idx];
}


static void formatUTCTime(uint32_t sec, char *buf, size_t buflen) {
    uint32_t hh = sec / 3600;
    uint32_t mm = (sec % 3600) / 60;
    uint32_t ss = sec % 60;
    snprintf(buf, buflen, "%02lu:%02lu:%02lu", (unsigned long)hh, (unsigned long)mm, (unsigned long)ss);
}

// ─── TX state ────────────────────────────────────────────────────────
static int currentPhase = -1;
// M6: seqInPhase is static uint32_t and NEVER resets (monotonic across phases)
static uint32_t seqInPhase = 0;
static uint32_t phaseStartMs = 0;
// Per-phase packet counter (resets on phase change, used for slot timing)
static uint16_t pktsSentInPhase = 0;

// ─── Setup ───────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    // Wait up to 3s for USB host to connect (prevents watchdog misfire on boot)
    uint32_t bootStart = millis();
    while (!Serial && (millis() - bootStart) < 3000) {
        delay(10);
    }
    // DO NOT initialize lastCdcSuccessMs here — leave it 0 so the watchdog
    // only arms after the first successful Serial.write(). This prevents
    // infinite reboots when USB is disconnected (battery-powered walk test).
    // If USB connects, outPrintf() sets it via line 77. If USB never connects,
    // the watchdog check (lastCdcSuccessMs > 0) stays false forever.

    // Boot banner — FIRST output. Identifies exact firmware build.
    printBootBanner();
    // GPS on UART0: GP1=RX, GP0=TX, 115200 baud
    Serial1.setRX(PIN_GPS_RX);
    Serial1.setTX(PIN_GPS_TX);
    // ROBUSTNESS FIX: Enlarge UART RX ring buffer from default 32 entries.
    // During SPI radio operations (50-100ms+), GPS sends ~500 chars/sec at
    // 115200 baud. The tiny default buffer overflows and drops characters,
    // causing NMEA sentence corruption/merging. Must call BEFORE begin().
    Serial1.setFIFOSize(1024);
    // GPS baud auto-detection: try 115200 first (was working), then 9600
    {
        const uint32_t bauds[] = {115200, 9600, 38400, 19200};
        const int nBauds = 4;
        bool gpsFound = false;
        for (int b = 0; b < nBauds && !gpsFound; b++) {
            Serial1.begin(bauds[b]);
            delay(500);
            uint32_t probeStart = millis();
            int validChars = 0;
            while (millis() - probeStart < 1500) {
                while (Serial1.available()) {
                    char c = Serial1.read();
                    if (c == '$' || c == 'G' || c == 'N' || c == 'M' || c == 'R' ||
                        c == 'C' || c == 'A' || c == ',' || c == '.' || c == '\n') {
                        validChars++;
                    }
                }
            }
            if (validChars > 10) {
                outPrintf("GPS_BAUD_DETECTED=%lu (valid=%d)\n", bauds[b], validChars);
                gpsFound = true;
            } else {
                Serial1.end();
            }
        }
        if (!gpsFound) {
            outPrintf("GPS_BAUD_FAILED — defaulting to 115200\n");
            Serial1.begin(115200);
        }
    }
    delay(500);

    pinMode(PIN_CS, OUTPUT);
    pinMode(PIN_RST, OUTPUT);
    pinMode(PIN_IRQ, INPUT);
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_CS, HIGH);
    digitalWrite(PIN_RST, HIGH);
    // Init NeoPixel on GP16 (Waveshare RP2040-Zero onboard LED)
    statusLED.begin();
    statusLED.show();  // Turn off
    // Boot strobe: blue flash 6x so Felix sees LED working
    for (int i = 0; i < 6; i++) {
        ledColor(0, 0, 255);   // Blue
        delay(100);
        ledColor(0, 0, 0);     // Off
        delay(100);
    }

    spiRf.begin();

    // V4: Build interleave table and default to interleave mode
    buildInterleaveTable();
    interleaveMode = true;  // V4: always interleave — 56 phases (14 modes × 4 sizes)

    // Compute total cycle seconds for interleave mode
    totalCycleSec = 0;
    totalCycleMs = 0;
    for (int i = 0; i < numInterleavePhases; i++) {
        totalCycleSec += interleavePhases[i].slotMs / 1000;
        totalCycleMs += interleavePhases[i].slotMs;
    }

    outPrintf("=== GPS-SYNCED MULTI-RADIO TX SWEEP V4 ===\\n");
    outPrintf("Mode: INTERLEAVE (56 phases: 14 modes x 4 sizes)\\n");
    outPrintf("Cycle: %lus (%lums)  Power: %.1f dBm\\n",
               (unsigned long)totalCycleSec, (unsigned long)totalCycleMs, TX_POWER_DBM);
    outPrintf("Packet sizes: 32 / 64 / 128 / 255 bytes per mode\\n\\n");

    // ── GPS GATE: TX waits for GPS TIME (phase computation needs it) ──
    // GPS gives time (from satellite ephemeris download) BEFORE position fix.
    // Time arrives in ~10-30s. Position fix takes 1-15 min.
    // TX computes phase from GPS time immediately, but does NOT transmit
    // packets until GPS position fix is acquired (Felix requirement —
    // see FIX GATE in main loop). Bench mode: laptop SET_TIME bypasses.
    outPrintf("=== WAITING FOR GPS TIME (phase computation needs UTC) ===\n");
    outPrintf("=== TX will NOT transmit until GPS FIX acquired ===\n");
    outPrintf("=== Bench test: send SET_TIME to override ===\n");
    outPrintf("GPS_DEBUG: UART1 RX=GP1 TX=GP0  LED=GP25(green)  GPS module pin wiring check\n");
    outPrintf("GPS_DEBUG: If no NMEA_RAW lines appear, GPS module is not communicating\n");
    uint32_t gpsStart = millis();
    uint32_t lastNmeaPrint = 0;
    while (!gps.hasTime) {
        gpsPoll();
        checkSerialTimeSync();  // Process SET_TIME during boot gate
        digitalWrite(PIN_LED, ((millis() / 250) & 1) ? HIGH : LOW);
        ledColor(((millis() / 500) & 1) ? 100 : 30, 0, 0);  // Dim red pulse while searching

        // Bench override: laptop SET_TIME received
        if (hasLaptopTime()) {
            outPrintf("LAPTOP_TIME_OVERRIDE — entering bench mode (no GPS required)\n");
            break;
        }

        // V4: Boot gate timeout — don't hang forever if no GPS and no SET_TIME
        if ((millis() - gpsStart) > GPS_FIX_TIMEOUT_MS) {
            outPrintf("GPS_FIX_TIMEOUT %lums — no fix and no SET_TIME, proceeding to main loop\n",
                      (unsigned long)(millis() - gpsStart));
            break;
        }

        // Status every 5s (more frequent for debugging)
        uint32_t elapsed = (millis() - gpsStart) / 1000;
        if (elapsed % 5 == 0 && elapsed > 0) {
            static uint32_t lastReport = 0;
            if (elapsed != lastReport) {
                outPrintf("GPS_WAIT %lus sats=%d fix=%d hasTime=%d fixValid=%d "
                          "timeSec=%lu unixTime=%lu\n",
                          (unsigned long)elapsed, gps.sats,
                          gps.fixValid ? 1 : 0, gps.hasTime ? 1 : 0,
                          gps.fixValid ? 1 : 0,
                          (unsigned long)gps.timeSec,
                          gps.hasUnixTime ? (unsigned long)gps.unixTime : 0UL);
                lastReport = elapsed;
            }
        }

        // NMEA passthrough: print raw GPS sentences every 3s for debugging
        // Helps verify GPS module is alive and outputting valid data
        if (millis() - lastNmeaPrint > 3000) {
            lastNmeaPrint = millis();
            // Read any pending NMEA and show first sentence
            if (Serial1.available()) {
                char nmeaLine[160];
                int n = 0;
                uint32_t to = millis();
                while (millis() - to < 200 && n < 159) {
                    if (Serial1.available()) {
                        char c = Serial1.read();
                        nmeaLine[n++] = c;
                        if (c == '\n') break;
                    }
                }
                nmeaLine[n] = '\0';
                // Trim trailing whitespace
                while (n > 0 && (nmeaLine[n-1] == '\r' || nmeaLine[n-1] == '\n'))
                    nmeaLine[--n] = '\0';
                if (n > 5)
                    outPrintf("NMEA_RAW: %s\n", nmeaLine);
                else
                    outPrintf("NMEA_RAW: (short, %d bytes) GPS module may not be responding\n", n);
            } else {
                outPrintf("NMEA_RAW: (no data) GPS module not sending on UART1\n");
            }
        }
        delay(10);
    }

    // BUG1 FIX: Validate GPS time — timeSec==0 means stale/invalid (soft reboot leftover)
    if (gps.hasTime && gps.timeSec == 0) {
        outPrintf("GPS_HAS_TIME_BUT_STALE timeSec=0 — clearing hasTime\n");
        gps.hasTime = false;
    }

    if (gps.hasTime) {
        char tbuf[16];
        formatUTCTime(gps.timeSec, tbuf, sizeof(tbuf));
        outPrintf("GPS_TIME_ACQUIRED utc=%s fix=%d sats=%d lat=%.5f lon=%.5f unix=%lu\n",
                   tbuf, gps.fixValid ? 1 : 0, gps.sats, gps.lat, gps.lon,
                   gps.hasUnixTime ? (unsigned long)gps.unixTime : 0UL);
        // Compute initial phase from best available time source
        uint32_t phaseTime = getBestUnixTime();
        currentPhase = computePhaseFromUTC(phaseTime);
        uint32_t cyclePos = phaseTime % totalCycleSec;
        outPrintf("INITIAL_PHASE=%d phaseTime=%lu cycle_pos=%lu source=%s\n",
                   currentPhase, (unsigned long)phaseTime, (unsigned long)cyclePos,
                   gps.hasUnixTime ? "GPS_UNIX" : "GPS_TIME_ONLY");
    } else if (hasLaptopTime()) {
        // BENCH MODE: No GPS time, but laptop SET_TIME provides epoch
        outPrintf("BENCH_MODE unix=%lu — using laptop time (no GPS)\n",
                   (unsigned long)getUtcNow());
        currentPhase = computePhaseFromUTC(getUtcNow());
        outPrintf("INITIAL_PHASE=%d source=LAPTOP\n", currentPhase);
    } else {
        // AUTONOMOUS MODE: No GPS time and no laptop time.
        // Enter WAITING_FOR_GPS state — main loop will keep polling GPS
        // and start sweeping as soon as GPS time arrives.
        outPrintf("WAITING_FOR_GPS_TIME — no time source yet, will poll in main loop\n");
        currentPhase = -1;  // sentinel: main loop knows to wait for GPS
    }

    digitalWrite(PIN_LED, HIGH);
    outPrintf("=== STARTING GPS-SYNCED SWEEP ===\n");
    Serial.flush();
}

// ─── Main loop ───────────────────────────────────────────────────────
void loop() {
    // Check for laptop time sync (SET_TIME over USB)
    checkSerialTimeSync();

    // GPS still works if module is alive — used for position data in packets
    gpsPoll();

    // ─── NEOPIXEL STATUS LED ─────────────────────────────────────────
    // Red pulse = GPS searching for time. Yellow = has time, TX active, no fix. Green = GPS locked.
    {
        if (gps.fixValid) {
            ledColor(0, 255, 0);   // Green: GPS locked, full operation
        } else if (gps.hasTime) {
            // Yellow blink at 2Hz
            bool on = ((millis() % 500) < 250);
            ledColor(on ? 255 : 50, on ? 200 : 30, 0);
        } else {
            // Red blink at 1Hz
            bool on = ((millis() % 1000) < 500);
            ledColor(on ? 255 : 30, 0, 0);
        }
    }

    // CDC watchdog — if USB CDC hasn't accepted output for 30s, hard reboot.
    // Serial.begin() doesn't fix a dead TinyUSB stack — only a chip reboot does.
    // GUARD: Only fire when USB host IS present (Serial &&). On power bank / walk
    // test, there's no USB host — Serial.write returns 0 naturally. We must NOT
    // reboot in that case or we lose utcOffset (laptop time sync) and hang.
    if (Serial && lastCdcSuccessMs > 0 && (millis() - lastCdcSuccessMs) > CDC_WATCHDOG_MS) {
        // USB CDC is dead. Hardware watchdog reboot to restart USB cleanly.
        // This reboots the RP2040 — firmware restarts, USB re-enumerates,
        // GPS re-acquires in ~30s. No manual BOOTSEL button needed.
        watchdog_reboot(0, 0, 0);
    }

    // Heartbeat every 10s
    if (lastHeartbeatMs == 0 || (millis() - lastHeartbeatMs) > HEARTBEAT_INTERVAL_MS) {
        uint32_t utcNow = getBestUnixTime();
        const char *src =
            (gps.hasUnixTime && gps.unixTime > 0 &&
             (millis() - lastGpsTimeMs) < GPS_TIME_STALE_MS) ? "GPS" :
            (gpsTimeOffset != 0) ? "GPS_HOLD" :
            hasLaptopTime() ? "LAPTOP" : "NONE";
        outPrintf("HEARTBEAT millis=%lu phase=%d utc=%lu src=%s fix=%d sats=%d\n",
                  (unsigned long)millis(), currentPhase, (unsigned long)utcNow,
                  src, gps.fixValid ? 1 : 0, gps.sats);
        lastHeartbeatMs = millis();
    }

    // ─── AUTONOMOUS TIME SOURCE: GPS is primary, laptop is bench backup ──
    // Fresh GPS time → use directly. Stale GPS (>10s) → extrapolate from
    // millis() + last GPS offset. Laptop SET_TIME → bench test only.
    // No time source at all → WAIT for GPS (do not transmit unsynced).
    uint32_t timeNow = getBestUnixTime();
    bool hasTimeSource = (gpsTimeOffset != 0) || hasLaptopTime() ||
                         (gps.hasUnixTime && gps.unixTime > 0);

    if (!hasTimeSource) {
        // No time source — keep polling GPS, don't transmit unsynced.
        // This is the WAITING_FOR_GPS state after boot gate timeout.
        static uint32_t lastWaitMsg = 0;
        if (millis() - lastWaitMsg > 3000) {
            outPrintf("WAIT_GPS_TIME sats=%d hasTime=%d hasUnix=%d — polling\n",
                      gps.sats, gps.hasTime ? 1 : 0, gps.hasUnixTime ? 1 : 0);
            lastWaitMsg = millis();
        }
        if (currentPhase >= 0) currentPhase = -1;
        gpsPoll();
        delay(50);
        return;
    }

    int phase = computePhaseFromUTC(timeNow);

    // Phase change detection
    if (phase != currentPhase) {
        // BUG FIX: Abort any TX still in progress from the previous phase.
        // SF12-255B takes ~8s; if the phase boundary falls during TX, the
        // radio is still mid-transmission. Force SET_STANDBY before
        // rfInitForPhase to avoid hardware-reset during active TX.
        abortTxIfActive();

        // V4: Add 500ms extra gap after SF12 phases for radio recovery
        if (currentPhase >= 0) {
            const Phase &prevP = *getPhaseEntry(currentPhase);
            if (prevP.sf == 12) {
                outPrintf("PHASE_GUARD 500 (SF12 recovery)\n");
                delay(500);
            } else {
                outPrintf("PHASE_GUARD 500\n");
            }
        }
        currentPhase = phase;
        // M6: seqInPhase is NOT reset here — it's a monotonic uint32 counter
        pktsSentInPhase = 0;  // reset per-phase packet counter for slot timing
        phaseStartMs = millis();

        const Phase &p = *getPhaseEntry(phase);
        rfInitForPhase(p);
        delay(50);
        gpsPoll();  // drain GPS UART after ~100ms of SPI radio init

        // O4: Emit CONFIG_START when switching configurations
        outPrintf("CONFIG_START,%s,%lu,%lu\n",
                  configId[0] ? configId : p.name,
                  (unsigned long)replicate,
                  (unsigned long)millis());

        char tbuf[16] = "NO_GPS";
        if (gps.hasTime) formatUTCTime(gps.timeSec, tbuf, sizeof(tbuf));
        // V4: include pktSize in phase start
        if (p.pktCount == 0) {
            outPrintf("PHASE_START %d %s %s SKIP pktSize=%d\n", phase, p.name, tbuf, p.pktSize);
        } else {
            outPrintf("PHASE_START %d %s %s pktSize=%d\n", phase, p.name, tbuf, p.pktSize);
        }
        // Serial.flush() now happens in outPrintf (BUG2 fix)
    }

    const Phase &p = *getPhaseEntry(currentPhase);

    // V4: SKIP phase (pktCount=0) — LF-LoRa-SF12 at >32B, air time impractical
    if (p.pktCount == 0) {
        gpsPoll();
        delay(10);
        return;
    }

    // ─── FIX GATE: TX must NOT transmit without GPS fix (Felix requirement) ──
    // The sweep loop keeps running (phase computation + radio reconfig above)
    // so TX stays phase-synced and is ready to transmit the moment fix returns.
    // Last known position is preserved in gps.lat/lon — parseNMEA only updates
    // those fields on a valid fix. When fix returns, position updates automatically.
    // Bench mode (laptop SET_TIME) is exempt — allows testing without GPS.
    // ─── GPS FIX GATE (ADR-018): TX NEVER transmits without satellite fix ───
    // This is UNCONDITIONAL — no laptop exemption. Per Felix's requirement:
    // "when we don't have a satellite fix, the TX board shouldn't transmit at all."
    // The sweep loop keeps running (phase computation + radio reconfig above)
    // so TX stays phase-synced and is ready to transmit the moment fix returns.
    // Last known position is preserved in gps.lat/lon — parseNMEA only updates
    // those fields on a valid fix. When fix returns, position updates automatically.
    if (!gps.fixValid) {
        static uint32_t lastNoFixMsg = 0;
        static bool hadFix = false;
        if (gps.fixValid) hadFix = true;
        if (millis() - lastNoFixMsg > 3000) {
            if (hadFix) {
                outPrintf("FIX_LOST sats=%d fix=0 — sweep continues, TX gated. Last pos preserved.\n",
                          gps.sats);
            } else {
                outPrintf("NO_FIX_WAIT sats=%d fix=0 — sweep continues, TX gated on fix\n",
                          gps.sats);
            }
            lastNoFixMsg = millis();
        }
        gpsPoll();
        delay(50);
        return;  // Don't transmit without fix — phase detection still runs next loop()
    }

    uint16_t pktSize = p.pktSize;
    uint8_t txBuf[256];

    // V4/PRBS-6: fill bytes 29 to pktSize-3 with PRBS-15 pattern seeded by seq
    // (start at 29 to cover bytes between FW hash end and CRC start)
    // When PRBS OFF: zero fill (for throughput testing without BER measurement)
    // Use pktsSentInPhase for PRBS seed so RX can correlate within each phase
    if (prbs_enabled && pktSize > PRBS_START + 2) {
        prbs15_fill(&txBuf[PRBS_START], pktSize - PRBS_START - 2, pktsSentInPhase);
    } else {
        memset(&txBuf[PRBS_START], 0, pktSize - PRBS_START - 2);
    }

    // Check if we still have time in this phase
    uint32_t elapsedInPhase = millis() - phaseStartMs;
    // Transition guard: 1000ms when next phase changes modulation or band
    uint32_t guardMs = 500;
    {
        int nextPh = currentPhase + 1;
        if (nextPh < numInterleavePhases) {
            if (interleavePhases[currentPhase].pktType != interleavePhases[nextPh].pktType ||
                interleavePhases[currentPhase].rfPath   != interleavePhases[nextPh].rfPath) {
                guardMs = 1000;
            }
        }
    }
    if (elapsedInPhase >= (uint32_t)p.slotMs - guardMs) {
        // Phase nearly over — enter guard band, wait for phase change
        outPrintf("PHASE_GUARD %lu\n", (unsigned long)guardMs);
        gpsPoll();
        delay(10);
        return;
    }

    // Check if we've sent all packets (per-phase counter)
    if (pktsSentInPhase >= p.pktCount) {
        // Sent all packets, wait for phase to end
        gpsPoll();
        delay(10);
        return;
    }

    // Build packet — MUST match RX layout in multi_radio_sweep_rx.cpp
    //   bytes 0-3:   sync header (0xA5 0x5A 0x42 0x24)
    //   bytes 4-7:   latE7 (int32 LE)
    //   bytes 8-11:  lonE7 (int32 LE)
    //   bytes 12-13: sats  (uint16 LE)
    //   byte  14:    fixQ  (uint8)
    //   bytes 15-18: utcSec (uint32 LE)
    //   byte  19:    phaseId (uint8)
    //   bytes 20-21: seq   (uint16 BE)
    //   bytes 22-28: fw_hash (7 ASCII chars — firmware self-identification)
    txBuf[0] = 0xA5;
    txBuf[1] = 0x5A;
    txBuf[2] = 0x42;
    txBuf[3] = 0x24;
    embedGPS(txBuf);
    txBuf[19] = (uint8_t)currentPhase;
    txBuf[20] = (uint8_t)(pktsSentInPhase >> 8);
    txBuf[21] = (uint8_t)(pktsSentInPhase & 0xFF);
    // Append 7-char firmware git hash so RX can verify TX build compatibility
    memcpy(&txBuf[22], FW_HASH_CHARS, 7);

    // ─── V4: App-layer CRC-16 over FULL payload (variable length) ─────
    // CRC-16 (CCITT 0x1021) over bytes 4 to pktSize-3 (everything between
    // sync header and CRC itself). For 32B: covers bytes 4-29 (26 bytes).
    // For 255B: covers bytes 4-252 (249 bytes). ~250μs on RP2040 — negligible.
    uint16_t crcLen = pktSize - 4 - 2;  // exclude sync (4) and CRC (2)
    uint16_t appCrc = crc16(&txBuf[4], crcLen);
    txBuf[pktSize - 2] = (uint8_t)(appCrc >> 8);
    txBuf[pktSize - 1] = (uint8_t)(appCrc & 0xFF);

    // TX
    rfClearIrq();
    rfClearTxFifo();
    rfWriteTxFifo(txBuf, pktSize);
    txInProgress = true;   // track TX for abortTxIfActive() phase-safety
    rfSetTx();

    // Wait for TX_DONE — poll DIO9 IRQ pin
    // For LoRa SF12, TX can take 1-2s. The UART ISR drains HW FIFO into the
    // 1024-byte ring buffer, but we also poll GPS periodically to prevent
    // overflow on very long transmissions. gpsPoll() returns instantly if
    // no data is available, so the tight spin loop is minimally impacted.
    uint32_t irqPinMask = 1UL << PIN_IRQ;
    uint32_t txStartMs = millis();
    bool irqFired = false;
    // V4 FIX: 16s timeout. Was 6s in V3, but LF-LoRa-SF12-32B takes ~13s
    // (410ms/byte × 32 + 10ms). The old timeout always expired mid-TX,
    // leaving the radio transmitting into the next phase's time slot.
    while ((millis() - txStartMs) < 16000) {
        if (sio_hw->gpio_in & irqPinMask) { irqFired = true; txInProgress = false; break; }
        // Drain GPS UART every ~65K iterations (~3ms at 125MHz)
        if ((millis() - txStartMs) % 3 == 0) gpsPoll();  // poll GPS ~every 3ms
    }

    // V4: Log TX timeout — indicates radio didn't complete TX_DONE
    if (!irqFired) {
        outPrintf("TX_TIMEOUT — TX_DONE not received after %lu ms (phase=%d)\n",
                  (unsigned long)(millis() - txStartMs), currentPhase);
    }

    // Output per-packet log — M3+M4+M5: 23-field harmonized PKT format
    // TX-side: rssi_dbm=0, snr_db=0 (TX doesn't receive), crc_ok=1 (valid TX)
    //          bit_err=0, bytes_bad=0 (no RX errors on TX side)
    // M5: All config fields from the phase config table (freq_hz, mod, sf, bw_khz, cr, power_dbm, pkt_size)
    uint32_t freqHz = (uint32_t)(p.freqMHz * 1e6f);
    const char* modStr = (p.pktType == PT_LORA) ? "LORA" : "FLRC";
    // Map bwCode to kHz: 0x0F=812, 0x05=250, 0x06=500, 0x0D=203.125, 0x0E=406.25
    uint16_t bwKhz = 0;
    if (p.bwCode == 0x0F)      bwKhz = 812;
    else if (p.bwCode == 0x05) bwKhz = 250;
    else if (p.bwCode == 0x06) bwKhz = 500;
    else if (p.bwCode == 0x0D) bwKhz = 203;
    else if (p.bwCode == 0x0E) bwKhz = 406;
    outPrintf("PKT,%s,%s,%lu,%lu,%lu,0,0,1,0,0,%lu,%s,%u,%u,%u,%d,%u,%d,%.5f,%.5f,%.1f,%u,%.1f\n",
              sessionId,
              configId[0] ? configId : p.name,
              (unsigned long)replicate,
              (unsigned long)seqInPhase,
              (unsigned long)millis(),
              (unsigned long)freqHz,
              modStr,
              p.sf,
              bwKhz,
              p.cr,
              (int)TX_POWER_DBM,
              pktSize,
              gps.fixValid ? 1 : 0,
              gps.fixValid ? gps.lat : 0.0f,
              gps.fixValid ? gps.lon : 0.0f,
              gps.fixValid ? gps.alt : 0.0f,
              gps.sats,
              gps.fixValid ? gps.hdop : 0.0f);

    // NeoPixel status — already handled in main heartbeat above.
    // Just toggle brightness slightly per TX for feedback.
    {
        if (gps.fixValid) {
            ledColor(0, seqInPhase & 1 ? 255 : 100, 0);  // Green pulse per packet
        } else {
            ledColor(seqInPhase & 1 ? 255 : 50, seqInPhase & 1 ? 200 : 30, 0);  // Yellow pulse
        }
    }

    // M6: seqInPhase is monotonic (never resets), pktsSentInPhase resets per phase
    seqInPhase++;
    pktsSentInPhase++;

    // Spread packets across slot (use per-phase counter for timing)
    uint32_t targetTime = (uint32_t)pktsSentInPhase * (uint32_t)p.slotMs / (uint32_t)p.pktCount;
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

    // outPrintf now flushes after every call (BUG2 fix — no more periodic flush needed)
}
