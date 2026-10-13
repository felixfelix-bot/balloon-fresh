/**
 * @file    e28_range_console.c
 * @brief   E28-2G4M27S (SX1282) ranging console core — host-testable.
 *
 * Command set (case-insensitive, E80-bench style):
 *   ID?          -> E28-RANGE v1.0 fw=<hash>
 *   STAT?        -> role=<master|slave|idle> freq=<MHz> sf=<n> bw=<kHz>
 *                   pa=<dBm> addr=<0x…> last=<m|none> err=<code>
 *   RANGE        -> master: one ranging exchange, DIST=<m>m rssi=<dBm> | RANGE TIMEOUT
 *   RANGE-SLAVE  -> slave: respond to master's ranging requests
 *   RANGE?       -> DIST=<m>m (or DIST=none)
 *   FREQ <hz>    -> 2400–2500 MHz
 *   SF <n>       -> 5–12
 *   BW <khz>     -> 406.25 / 812.5 / 1625 (ranging-valid only)
 *   PA <dbm>     -> clamped to indoor cap (+10 dBm)
 *   ADDR <hex>   -> 32-bit ranging address (both ends must match)
 *   HELP / ?     -> list commands
 *
 * All radio access is behind e28_io_t so the same object code runs on the
 * ESP32-S3 (SX1282 RadioLib ops) and in the host unit tests (fake io).
 */

#include "e28_range_console.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <ctype.h>
#include <stdarg.h>
#include <errno.h>

/* ---- state --------------------------------------------------------------- */

typedef struct
{
    const e28_io_t* io;
    char fw_sha7[8];
    uint32_t freq_hz;
    uint8_t  sf;
    float    bw_khz;
    int8_t   pa_dbm;
    uint32_t addr;
    bool     has_result;
    float    last_m;
    int      last_err;
    bool     role_master;   /* true = last RANGE was master; false = slave */
    bool     role_set;      /* a ranging exchange has run */
} e28_state_t;

static e28_state_t g;

/* ---- helpers ------------------------------------------------------------- */

static void put(const char* s) { if(g.io && g.io->put) g.io->put(s); }

static void putf(const char* fmt, ...)
{
    char buf[128];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    put(buf);
}

/* Strict decimal parse: returns true iff the whole string is a valid
 * (optionally signed) integer with no trailing garbage. */
static bool parse_long(const char* s, long* out)
{
    if(!s || !*s) return false;
    char* end = NULL;
    errno = 0;
    long v = strtol(s, &end, 10);
    if(errno != 0 || end == s || *end != '\0') return false;
    *out = v;
    return true;
}

/* Strict unsigned parse (hex or decimal): returns true iff the whole string
 * is a valid non-negative integer with no trailing garbage. */
static bool parse_ulong(const char* s, unsigned long* out)
{
    if(!s || !*s) return false;
    char* end = NULL;
    errno = 0;
    unsigned long v = strtoul(s, &end, 0);   /* 0x prefix -> hex, else decimal */
    if(errno != 0 || end == s || *end != '\0') return false;
    *out = v;
    return true;
}

static void push_config(void)
{
    if(g.io && g.io->radioBegin) {
        g.last_err = g.io->radioBegin();
    }
}

static void trim(char* s)
{
    char* p = s;
    while(*p && isspace((unsigned char)*p)) p++;
    if(p != s) memmove(s, p, strlen(p) + 1);
    size_t n = strlen(s);
    while(n > 0 && isspace((unsigned char)s[n-1])) s[--n] = 0;
}

static void upper(char* s)
{
    for(char* p = s; *p; p++) *p = (char)toupper((unsigned char)*p);
}

/* ---- command handlers ---------------------------------------------------- */

static void cmd_id(void)
{
    putf("%s %s fw=%s\r\n", E28_RANGE_BOARD_NAME, E28_RANGE_FW_VERSION, g.fw_sha7);
}

static void cmd_stat(void)
{
    const char* role = "idle";
    if(g.role_set) role = g.role_master ? "master" : "slave";
    if(g.has_result) {
        putf("role=%s freq=%u sf=%u bw=%g pa=%d addr=0x%08X last=%.2f err=%d\r\n",
             role, g.freq_hz / 1000000u, g.sf, g.bw_khz, g.pa_dbm, g.addr,
             g.last_m, g.last_err);
    } else {
        putf("role=%s freq=%u sf=%u bw=%g pa=%d addr=0x%08X last=none err=%d\r\n",
             role, g.freq_hz / 1000000u, g.sf, g.bw_khz, g.pa_dbm, g.addr,
             g.last_err);
    }
}

static void cmd_range(void)
{
    if(!g.io || !g.io->radioRange) { put("ERR no radio\r\n"); return; }
    int st = g.io->radioRange(true, g.addr);
    g.last_err = st;
    g.role_set = true;
    g.role_master = true;
    if(st == 0) {
        g.last_m = g.io->radioRangingResult();
        g.has_result = true;
        putf("DIST=%.2fm\r\n", g.last_m);
    } else if(st == -901) {   /* RADIOLIB_ERR_RANGING_TIMEOUT */
        put("RANGE TIMEOUT\r\n");
    } else {
        putf("ERR range=%d\r\n", st);
    }
}

static void cmd_range_slave(void)
{
    if(!g.io || !g.io->radioRange) { put("ERR no radio\r\n"); return; }
    int st = g.io->radioRange(false, g.addr);
    g.last_err = st;
    g.role_set = true;
    g.role_master = false;
    if(st == 0) {
        put("SLAVE OK\r\n");
    } else {
        putf("ERR slave=%d\r\n", st);
    }
}

static void cmd_range_query(void)
{
    if(g.has_result) {
        putf("DIST=%.2fm\r\n", g.last_m);
    } else {
        put("DIST=none\r\n");
    }
}

static void cmd_freq(const char* arg)
{
    unsigned long hz;
    if(!parse_ulong(arg, &hz)) {
        put("ERR freq: expected integer Hz\r\n");
        return;
    }
    if(hz < E28_RANGE_FREQ_MIN_HZ || hz > E28_RANGE_FREQ_MAX_HZ) {
        put("ERR freq out of band (2400-2500 MHz)\r\n");
        return;
    }
    g.freq_hz = (uint32_t)hz;
    push_config();
}

static void cmd_sf(const char* arg)
{
    long sf;
    if(!parse_long(arg, &sf)) {
        put("ERR sf: expected integer\r\n");
        return;
    }
    if(sf < E28_RANGE_SF_MIN || sf > E28_RANGE_SF_MAX) {
        put("ERR sf out of range (5-12)\r\n");
        return;
    }
    g.sf = (uint8_t)sf;
    push_config();
}

static void cmd_bw(const char* arg)
{
    char buf[16];
    snprintf(buf, sizeof buf, "%s", arg);
    trim(buf);
    float bw = (float)atof(buf);
    if(bw != 812.5f) {
        put("ERR bw must be 812.5 kHz (ranging BW 812.5 kHz only)\r\n");
        return;
    }
    g.bw_khz = bw;
    push_config();
}

static void cmd_pa(const char* arg)
{
    long pa;
    if(!parse_long(arg, &pa)) {
        put("ERR pa: expected integer dBm\r\n");
        return;
    }
    if(pa > E28_RANGE_TXPOW_CAP_INDOOR_DBM) {
        putf("ERR PA capped to %d dBm\r\n", E28_RANGE_TXPOW_CAP_INDOOR_DBM);
        pa = E28_RANGE_TXPOW_CAP_INDOOR_DBM;
    }
    if(pa < E28_RANGE_PA_MIN_DBM) {
        putf("ERR pa below SX1282 floor (%d dBm)\r\n", E28_RANGE_PA_MIN_DBM);
        pa = E28_RANGE_PA_MIN_DBM;
    }
    g.pa_dbm = (int8_t)pa;
    push_config();
}

static void cmd_addr(const char* arg)
{
    unsigned long a;
    if(!parse_ulong(arg, &a)) {
        put("ERR addr: expected hex or decimal\r\n");
        return;
    }
    g.addr = (uint32_t)a;
    push_config();
}

static void cmd_help(void)
{
    put("ID?  STAT?  RANGE  RANGE-SLAVE  RANGE?  FREQ <hz>  SF <n>  "
        "BW <khz>  PA <dbm>  ADDR <hex>  HELP\r\n");
}

/* ---- parser -------------------------------------------------------------- */

void e28_range_init(const e28_io_t* io, const char* fw_sha7)
{
    memset(&g, 0, sizeof g);
    g.io = io;
    snprintf(g.fw_sha7, sizeof g.fw_sha7, "%s", fw_sha7 ? fw_sha7 : "0000000");
    g.freq_hz = 2440000000ul;
    g.sf = 7;
    g.bw_khz = E28_RANGE_BW_DEFAULT_KHZ;
    g.pa_dbm = E28_RANGE_TXPOW_CAP_INDOOR_DBM;
    g.addr = E28_RANGE_DEFAULT_ADDR;
    g.last_err = 0;
    /* push the power-on defaults to the radio so hardware is configured
     * even before the first console command (cold-review finding). */
    push_config();
}

/* ---- chip version decode (SX128x reg 0x01F0) ----------------------------- */

/** Try one (offset, stride) alignment of the raw capture. The version field is
 *  ASCII, NUL-padded; a non-printable byte therefore ends the name. Returns
 *  true and fills tmp[17] when the alignment carries the "SX1" signature. */
static bool ver_try_alignment(const uint8_t* raw, uint8_t off, uint8_t stride, char* tmp)
{
    uint8_t n = 0;
    while(n < 16) {
        uint8_t idx = (uint8_t)(off + stride * n);
        if(idx >= 17) break;
        uint8_t b = raw[idx];
        if(b < 32 || b >= 127) break;
        tmp[n] = (char)b;
        n++;
    }
    tmp[n] = 0;
    return (n >= 3) && (strncmp(tmp, "SX1", 3) == 0);
}

void e28_decode_chip_version(const uint8_t raw[17], char out[17])
{
    if(!out) return;
    out[0] = 0;
    if(!raw) return;

    /* Four plausible layouts of a 17-byte capture:
     *   (0,1) no status byte, straight data
     *   (1,1) one leading status byte, then straight data
     *   (1,2) status byte before each data byte
     *   (2,2) as above, offset by one */
    static const uint8_t offsets[4] = { 0, 1, 1, 2 };
    static const uint8_t strides[4] = { 1, 1, 2, 2 };

    for(uint8_t c = 0; c < 4; c++) {
        char tmp[17];
        if(ver_try_alignment(raw, offsets[c], strides[c], tmp)) {
            memcpy(out, tmp, strlen(tmp) + 1);
            return;
        }
    }

    /* No signature anywhere: an empty string is the honest answer (a dead bus
     * reads all 0x00/0xFF, a SX126x reads a non-SX128x name). Callers show the
     * raw hex alongside this so the failure is diagnosable. */
}

bool e28_chip_supports_ranging(const char* version)
{
    if(!version) return false;
    return (strncmp(version, "SX1280", 6) == 0) || (strncmp(version, "SX1282", 6) == 0);
}

void e28_range_feed_line(const char* line)
{
    char buf[128];
    snprintf(buf, sizeof buf, "%s", line ? line : "");
    trim(buf);
    if(buf[0] == 0) return;

    /* split command + arg on any whitespace (space or tab) */
    char cmd[32];
    const char* arg = "";
    char* sp = buf;
    while(*sp && !isspace((unsigned char)*sp)) sp++;
    if(*sp) {
        *sp = 0;
        arg = sp + 1;
        trim((char*)arg);
    }
    /* bounded copy: commands are short; truncation is safe (unknown cmd) */
    size_t clen = strlen(buf);
    if(clen >= sizeof cmd) clen = sizeof cmd - 1;
    memcpy(cmd, buf, clen);
    cmd[clen] = 0;
    upper(cmd);

    if(strcmp(cmd, "ID?") == 0)            cmd_id();
    else if(strcmp(cmd, "STAT?") == 0)      cmd_stat();
    else if(strcmp(cmd, "RANGE") == 0)      cmd_range();
    else if(strcmp(cmd, "RANGE-SLAVE") == 0) cmd_range_slave();
    else if(strcmp(cmd, "RANGE?") == 0)     cmd_range_query();
    else if(strcmp(cmd, "FREQ") == 0)       cmd_freq(arg);
    else if(strcmp(cmd, "SF") == 0)         cmd_sf(arg);
    else if(strcmp(cmd, "BW") == 0)         cmd_bw(arg);
    else if(strcmp(cmd, "PA") == 0)         cmd_pa(arg);
    else if(strcmp(cmd, "ADDR") == 0)       cmd_addr(arg);
    else if(strcmp(cmd, "HELP") == 0 || strcmp(cmd, "?") == 0) cmd_help();
    else put("ERR unknown command\r\n");
}

/* ---- introspection ------------------------------------------------------- */

uint32_t e28_range_freq_hz(void) { return g.freq_hz; }
uint8_t  e28_range_sf(void)      { return g.sf; }
float    e28_range_bw_khz(void)  { return g.bw_khz; }
int8_t   e28_range_pa_dbm(void)  { return g.pa_dbm; }
uint32_t e28_range_addr(void)     { return g.addr; }
bool     e28_range_has_result(void) { return g.has_result; }
float    e28_range_last_m(void)   { return g.last_m; }
