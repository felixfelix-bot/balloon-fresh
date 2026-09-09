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
    char buf[32];
    snprintf(buf, sizeof buf, "%s", arg);
    trim(buf);
    unsigned long hz = strtoul(buf, NULL, 10);
    if(hz < E28_RANGE_FREQ_MIN_HZ || hz > E28_RANGE_FREQ_MAX_HZ) {
        put("ERR freq out of band (2400-2500 MHz)\r\n");
        return;
    }
    g.freq_hz = (uint32_t)hz;
    push_config();
}

static void cmd_sf(const char* arg)
{
    char buf[16];
    snprintf(buf, sizeof buf, "%s", arg);
    trim(buf);
    long sf = strtol(buf, NULL, 10);
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
    if(bw != 406.25f && bw != 812.5f && bw != 1625.0f) {
        put("ERR bw must be 406.25/812.5/1625 kHz (ranging-valid)\r\n");
        return;
    }
    g.bw_khz = bw;
    push_config();
}

static void cmd_pa(const char* arg)
{
    char buf[16];
    snprintf(buf, sizeof buf, "%s", arg);
    trim(buf);
    long pa = strtol(buf, NULL, 10);
    if(pa > E28_RANGE_TXPOW_CAP_INDOOR_DBM) {
        putf("ERR PA capped to %d dBm\r\n", E28_RANGE_TXPOW_CAP_INDOOR_DBM);
        pa = E28_RANGE_TXPOW_CAP_INDOOR_DBM;
    }
    g.pa_dbm = (int8_t)pa;
    push_config();
}

static void cmd_addr(const char* arg)
{
    char buf[32];
    snprintf(buf, sizeof buf, "%s", arg);
    trim(buf);
    unsigned long a = strtoul(buf, NULL, 16);
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
}

void e28_range_feed_line(const char* line)
{
    char buf[128];
    snprintf(buf, sizeof buf, "%s", line ? line : "");
    trim(buf);
    if(buf[0] == 0) return;

    /* split command + arg */
    char cmd[32];
    const char* arg = "";
    char* sp = strchr(buf, ' ');
    if(sp) {
        *sp = 0;
        arg = sp + 1;
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
