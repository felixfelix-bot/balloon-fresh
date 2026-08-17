/**
 * @file    test_cmd.cpp
 * @brief   Host unit tests: console command parser (FW-2, plan §1 REV-2).
 *
 * Vectors ported from E80 tests/test_bench_cmd.c plus the REV-2 grammar
 * deltas (standalone LEN/N/GAP, bare START, FLRC without dbm, FREQ band
 * clamp, POWER pin baked) and the §1 STAT? example-line token lock.
 *
 * Pure TU: no Arduino includes — links only against flrc_range_host_cmd.cpp.
 */

#include "flrc_range_host_cmd.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

#define CHECK(cond)                                                               \
    do                                                                            \
    {                                                                             \
        if (!(cond))                                                              \
        {                                                                         \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);                \
            failures++;                                                           \
        }                                                                         \
    } while (0)

static rh_cmd_t parse(const char* line)
{
    rh_cmd_t c;
    memset(&c, 0, sizeof(c));
    rh_cmd_parse(line, &c);
    return c;
}

/* ---------------------------------------------------------------- basics */

static void test_basic_commands(void)
{
    rh_cmd_t c;

    c = parse("ID?");
    CHECK(c.id == RH_CMD_ID && c.err == RH_CMD_OK);

    c = parse("id?"); /* case-insensitive */
    CHECK(c.id == RH_CMD_ID && c.err == RH_CMD_OK);

    c = parse("STAT?");
    CHECK(c.id == RH_CMD_STAT && c.err == RH_CMD_OK);

    c = parse("stat?");
    CHECK(c.id == RH_CMD_STAT);

    c = parse("STOP");
    CHECK(c.id == RH_CMD_STOP && c.err == RH_CMD_OK);

    c = parse("stop\r\n"); /* trailing CRLF tolerated */
    CHECK(c.id == RH_CMD_STOP);

    c = parse("START"); /* REV-2: START is bare — no kwargs */
    CHECK(c.id == RH_CMD_START && c.err == RH_CMD_OK);

    c = parse("START N=1000 LEN=255 GAP=5000"); /* E80 kwargs REJECTED */
    CHECK(c.id == RH_CMD_NONE && c.err == RH_CMD_E_ARG);

    c = parse("HELP");
    CHECK(c.id == RH_CMD_HELP && c.err == RH_CMD_OK);

    c = parse("?");
    CHECK(c.id == RH_CMD_HELP); /* '?' is an alias */

    c = parse("");
    CHECK(c.err == RH_CMD_E_ARG); /* empty: no command word */

    c = parse("   \t  ");
    CHECK(c.err == RH_CMD_E_ARG); /* whitespace-only */

    c = parse("BOGUS 1 2");
    CHECK(c.err == RH_CMD_E_UNKNOWN);

    c = parse("STOP extra");
    CHECK(c.err == RH_CMD_E_ARG); /* STOP takes no args */
}

/* ------------------------------------------------------------------ ROLE */

static void test_role(void)
{
    rh_cmd_t c;

    c = parse("ROLE TX");
    CHECK(c.id == RH_CMD_ROLE && c.role == RH_ROLE_TX && c.err == RH_CMD_OK);

    c = parse("role rx");
    CHECK(c.id == RH_CMD_ROLE && c.role == RH_ROLE_RX);

    c = parse("Role None");
    CHECK(c.id == RH_CMD_ROLE && c.role == RH_ROLE_NONE);

    c = parse("ROLE BOGUS");
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("ROLE");
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("ROLE TX EXTRA");
    CHECK(c.err == RH_CMD_E_ARG);
}

/* ------------------------------------------------------------- MOD FLRC */

static void test_mod_flrc(void)
{
    rh_cmd_t c;

    /* REV-2: MOD FLRC <br_kbps> — no dbm arg (E80 took two args) */
    c = parse("MOD FLRC 650");
    CHECK(c.id == RH_CMD_MOD && c.mod == BENCH_MOD_FLRC && c.err == RH_CMD_OK);
    CHECK(c.br_bps == 650000);

    /* all eight LR2021 FLRC rates map kbps -> bps */
    static const uint32_t khz[] = {260, 325, 520, 650, 1040, 1300, 2080, 2600};
    char line[32];
    for (unsigned i = 0; i < sizeof(khz) / sizeof(khz[0]); i++)
    {
        snprintf(line, sizeof(line), "MOD FLRC %u", (unsigned)khz[i]);
        c = parse(line);
        CHECK(c.id == RH_CMD_MOD && c.mod == BENCH_MOD_FLRC && c.err == RH_CMD_OK);
        CHECK(c.br_bps == khz[i] * 1000UL);
    }

    c = parse("mod flrc 666");
    CHECK(c.err == RH_CMD_E_RANGE); /* not a legal FLRC bitrate */

    c = parse("MOD flrc 650 22");
    CHECK(c.err == RH_CMD_E_ARG); /* extra arg: dbm moved to PA (REV-2) */

    c = parse("MOD gfsk 650");
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("MOD");
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("MOD FLRC");
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("MOD FLRC abc");
    CHECK(c.err == RH_CMD_E_ARG);
}

/* ------------------------------------------------------------- MOD LORA */

static void test_mod_lora(void)
{
    rh_cmd_t c;

    c = parse("MOD LORA 7 125");
    CHECK(c.id == RH_CMD_MOD && c.mod == BENCH_MOD_LORA && c.err == RH_CMD_OK);
    CHECK(c.sf == 7 && c.bw_hz == 125000);

    c = parse("MOD lora 12 500");
    CHECK(c.mod == BENCH_MOD_LORA && c.sf == 12 && c.bw_hz == 500000);

    c = parse("MOD LoRa 5 250");
    CHECK(c.mod == BENCH_MOD_LORA && c.sf == 5 && c.bw_hz == 250000);

    c = parse("MOD lora 4 125");
    CHECK(c.err == RH_CMD_E_RANGE); /* SF below 5 */

    c = parse("MOD lora 13 125");
    CHECK(c.err == RH_CMD_E_RANGE); /* SF above 12 */

    c = parse("MOD lora 7 137");
    CHECK(c.err == RH_CMD_E_RANGE); /* not a legal LoRa BW */

    c = parse("MOD lora 7 300");
    CHECK(c.err == RH_CMD_E_RANGE);

    c = parse("MOD lora x 125");
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("MOD lora 7");
    CHECK(c.err == RH_CMD_E_ARG); /* missing bw */
}

/* ------------------------------------------------------------------ FREQ */

static void test_freq(void)
{
    rh_cmd_t c;

    /* §1 example frequency */
    c = parse("FREQ 869525000");
    CHECK(c.id == RH_CMD_FREQ && c.freq_hz == 869525000UL && c.err == RH_CMD_OK);

    c = parse("freq 863000000"); /* band lower edge: OK */
    CHECK(c.id == RH_CMD_FREQ && c.freq_hz == RH_FREQ_MIN_HZ);

    c = parse("FREQ 870000000"); /* band upper edge: OK */
    CHECK(c.freq_hz == RH_FREQ_MAX_HZ);

    /* EU SRD hard clamp (§1): out-of-band is rejected, not clamped silently */
    c = parse("FREQ 862999999");
    CHECK(c.err == RH_CMD_E_RANGE);

    c = parse("FREQ 870000001");
    CHECK(c.err == RH_CMD_E_RANGE);

    c = parse("FREQ 433500000"); /* 433 band: out of clamped range */
    CHECK(c.err == RH_CMD_E_RANGE);

    c = parse("FREQ 2400000000"); /* 2.4 GHz (HW-B2 negative) */
    CHECK(c.err == RH_CMD_E_RANGE);

    c = parse("FREQ abc");
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("FREQ 99999999999"); /* > u32 */
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("FREQ");
    CHECK(c.err == RH_CMD_E_ARG);
}

/* -------------------------------------------------------------------- PA */

static void test_pa(void)
{
    rh_cmd_t c;

    c = parse("PA 22");
    CHECK(c.id == RH_CMD_PA && c.txpow_dbm == 22 && c.err == RH_CMD_OK);

    c = parse("PA -18"); /* REV-2 floor */
    CHECK(c.id == RH_CMD_PA && c.txpow_dbm == -18);

    c = parse("PA 0");
    CHECK(c.txpow_dbm == 0);

    c = parse("PA -3");
    CHECK(c.txpow_dbm == -3);

    c = parse("PA +10"); /* explicit + tolerated */
    CHECK(c.txpow_dbm == 10);

    c = parse("PA 23");
    CHECK(c.err == RH_CMD_E_RANGE); /* above ceiling */

    c = parse("PA -19");
    CHECK(c.err == RH_CMD_E_RANGE); /* below floor */

    /* Layer split (§1): PA 11..22 is RANGE-valid but locked at dispatch.
     * The parser must accept it; FW-6 turns it into ERR POWER-LOCKED. */
    c = parse("PA 14");
    CHECK(c.id == RH_CMD_PA && c.err == RH_CMD_OK && c.txpow_dbm == 14);

    c = parse("PA");
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("PA abc");
    CHECK(c.err == RH_CMD_E_ARG);
}

/* ------------------------------------------------------- LEN / N / GAP */

static void test_len_n_gap(void)
{
    rh_cmd_t c;

    /* LEN 8..255 (§1 example uses len=51) */
    c = parse("LEN 51");
    CHECK(c.id == RH_CMD_LEN && c.len_bytes == 51 && c.err == RH_CMD_OK);

    c = parse("LEN 8");
    CHECK(c.len_bytes == 8);

    c = parse("LEN 255");
    CHECK(c.len_bytes == 255);

    c = parse("LEN 7");
    CHECK(c.err == RH_CMD_E_RANGE);

    c = parse("LEN 256");
    CHECK(c.err == RH_CMD_E_RANGE);

    c = parse("LEN 0");
    CHECK(c.err == RH_CMD_E_RANGE);

    c = parse("LEN 51 51");
    CHECK(c.err == RH_CMD_E_ARG);

    /* N 1..1000000 */
    c = parse("N 1000");
    CHECK(c.id == RH_CMD_N && c.n_pkts == 1000 && c.err == RH_CMD_OK);

    c = parse("N 1");
    CHECK(c.n_pkts == 1);

    c = parse("N 1000000");
    CHECK(c.n_pkts == 1000000UL);

    c = parse("N 0");
    CHECK(c.err == RH_CMD_E_RANGE);

    c = parse("N 1000001");
    CHECK(c.err == RH_CMD_E_RANGE);

    c = parse("N");
    CHECK(c.err == RH_CMD_E_ARG);

    /* GAP 100..100000000 us */
    c = parse("GAP 5000");
    CHECK(c.id == RH_CMD_GAP && c.gap_us == 5000 && c.err == RH_CMD_OK);

    c = parse("GAP 100");
    CHECK(c.gap_us == 100);

    c = parse("GAP 100000000");
    CHECK(c.gap_us == 100000000UL);

    c = parse("GAP 99");
    CHECK(c.err == RH_CMD_E_RANGE);

    c = parse("GAP 100000001");
    CHECK(c.err == RH_CMD_E_RANGE);

    c = parse("GAP 5000.5");
    CHECK(c.err == RH_CMD_E_ARG);
}

/* ----------------------------------------------------------------- POWER */

static void test_power(void)
{
    rh_cmd_t c;

    c = parse("POWER MODE OUTDOOR 2026");
    CHECK(c.id == RH_CMD_POWER_OUTDOOR && c.pin == 2026 && c.err == RH_CMD_OK);

    c = parse("power mode outdoor 2026"); /* case-insensitive */
    CHECK(c.id == RH_CMD_POWER_OUTDOOR && c.pin == 2026);

    /* §1: pin must be 2026 — wrong pin is ERR ARG at parse time
     * (unlike E80, which deferred the pin check to firmware). */
    c = parse("POWER MODE OUTDOOR 9999");
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("POWER MODE OUTDOOR 1234");
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("POWER MODE INDOOR 2026");
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("POWER MODE OUTDOOR");
    CHECK(c.err == RH_CMD_E_ARG);

    c = parse("POWER");
    CHECK(c.err == RH_CMD_E_ARG);
}

/* --------------------------------------------------------- token limits */

static void test_token_overflow(void)
{
    char longtok[64];
    memset(longtok, 'A', sizeof(longtok) - 1);
    longtok[sizeof(longtok) - 1] = '\0';
    rh_cmd_t c = parse(longtok);
    CHECK(c.err == RH_CMD_E_ARG); /* token longer than RH_CMD_ARG_MAX-1 */

    c = parse("A B C D E F G H I"); /* 9 tokens > RH_CMD_MAX_TOKENS */
    CHECK(c.err == RH_CMD_E_ARG);

    /* exactly at the limits is fine */
    c = parse("MOD LORA 12 500"); /* 4 tokens, longest 4 chars */
    CHECK(c.err == RH_CMD_OK);
}

/* -------------------------------------------------------- parse helpers */

static void test_parse_helpers(void)
{
    uint32_t u;
    int8_t i;

    CHECK(rh_parse_u32("0", &u) && u == 0);
    CHECK(rh_parse_u32("4294967295", &u) && u == 4294967295UL);
    CHECK(!rh_parse_u32("4294967296", &u));
    CHECK(!rh_parse_u32("12a", &u));
    CHECK(!rh_parse_u32("-1", &u));
    CHECK(!rh_parse_u32("", &u));
    CHECK(!rh_parse_u32(NULL, &u));

    CHECK(rh_parse_i8("-128", &i) && i == -128);
    CHECK(rh_parse_i8("127", &i) && i == 127);
    CHECK(rh_parse_i8("+5", &i) && i == 5);
    CHECK(!rh_parse_i8("128", &i));
    CHECK(!rh_parse_i8("--1", &i));
    CHECK(!rh_parse_i8(NULL, &i));

    CHECK(rh_strcaseeq("STAT", "stat") == 1);
    CHECK(rh_strcaseeq("stat?", "STAT?") == 1);
    CHECK(rh_strcaseeq("STOP", "STAT") == 0);
    CHECK(rh_strcaseeq("STA", "STAT") == 0);
}

/* -------------------------------------------------------- error strings */

static void test_err_str(void)
{
    /* §1 reply vocabulary, defined exactly once — including the three
     * dispatch-layer classes the parser itself never emits. */
    CHECK(strcmp(rh_cmd_err_str(RH_CMD_OK), "OK") == 0);
    CHECK(strcmp(rh_cmd_err_str(RH_CMD_E_ARG), "ARG") == 0);
    CHECK(strcmp(rh_cmd_err_str(RH_CMD_E_RANGE), "RANGE") == 0);
    CHECK(strcmp(rh_cmd_err_str(RH_CMD_E_BUSY), "BUSY") == 0);
    CHECK(strcmp(rh_cmd_err_str(RH_CMD_E_INHIBITED), "INHIBITED") == 0);
    CHECK(strcmp(rh_cmd_err_str(RH_CMD_E_POWER_LOCKED), "POWER-LOCKED") == 0);
    CHECK(strcmp(rh_cmd_err_str(RH_CMD_E_UNKNOWN), "UNKNOWN") == 0);
}

/* ---------------------------------------------------- config-set helper */

static void test_is_config(void)
{
    /* §1 re-init rule: MOD/FREQ/PA/LEN re-apply radio config;
     * N/GAP are burst pacing — no re-apply. */
    CHECK(rh_cmd_is_config(RH_CMD_MOD));
    CHECK(rh_cmd_is_config(RH_CMD_FREQ));
    CHECK(rh_cmd_is_config(RH_CMD_PA));
    CHECK(rh_cmd_is_config(RH_CMD_LEN));
    CHECK(!rh_cmd_is_config(RH_CMD_N));
    CHECK(!rh_cmd_is_config(RH_CMD_GAP));
    CHECK(!rh_cmd_is_config(RH_CMD_START));
    CHECK(!rh_cmd_is_config(RH_CMD_STOP));
    CHECK(!rh_cmd_is_config(RH_CMD_STAT));
    CHECK(!rh_cmd_is_config(RH_CMD_HELP));
    CHECK(!rh_cmd_is_config(RH_CMD_ID));
    CHECK(!rh_cmd_is_config(RH_CMD_ROLE));
    CHECK(!rh_cmd_is_config(RH_CMD_NONE));
}

/* --------------------------------------------------- §1 STAT? line lock */

static void test_stat_example_tokens(void)
{
    /* Plan §1 STAT? example reply, joined into the single line the board
     * actually prints (keys chosen so the E80 parse_stat() port stays
     * ~verbatim — FW-2 acceptance vector locks the token surface).
     */
    static const char kStatLine[] =
        "STAT role=TX mod=FLRC br_hz=650000 freq_hz=869525000 dbm=10 len=51 "
        "n=1000 gap_us=5000 sent=1000 sent_ok=1000 rx=0 crc_err=0 per_x1e6=0 "
        "per_ci_x1e6=[0,3764] rssi_avg_dbm=-128.0 rssi_min_dbm=-128.0 "
        "snr_avg_db=0.0 kbps=641.2 elapsed_s=6.2 state=IDLE";

    char toks[32][RH_CMD_ARG_MAX];
    int ntok = 0;
    CHECK(rh_cmd_tokenize(kStatLine, toks, 32, &ntok) == RH_CMD_OK);

    CHECK(ntok == 21);
    if (ntok == 21)
    {
        CHECK(strcmp(toks[0], "STAT") == 0);
        CHECK(strcmp(toks[1], "role=TX") == 0);
        CHECK(strcmp(toks[2], "mod=FLRC") == 0);
        CHECK(strcmp(toks[3], "br_hz=650000") == 0);
        CHECK(strcmp(toks[4], "freq_hz=869525000") == 0);
        CHECK(strcmp(toks[5], "dbm=10") == 0);
        CHECK(strcmp(toks[6], "len=51") == 0);
        CHECK(strcmp(toks[7], "n=1000") == 0);
        CHECK(strcmp(toks[8], "gap_us=5000") == 0);
        CHECK(strcmp(toks[9], "sent=1000") == 0);
        CHECK(strcmp(toks[10], "sent_ok=1000") == 0);
        CHECK(strcmp(toks[11], "rx=0") == 0);
        CHECK(strcmp(toks[12], "crc_err=0") == 0);
        CHECK(strcmp(toks[13], "per_x1e6=0") == 0);
        CHECK(strcmp(toks[14], "per_ci_x1e6=[0,3764]") == 0);
        CHECK(strcmp(toks[15], "rssi_avg_dbm=-128.0") == 0);
        CHECK(strcmp(toks[16], "rssi_min_dbm=-128.0") == 0);
        CHECK(strcmp(toks[17], "snr_avg_db=0.0") == 0);
        CHECK(strcmp(toks[18], "kbps=641.2") == 0);
        CHECK(strcmp(toks[19], "elapsed_s=6.2") == 0);
        CHECK(strcmp(toks[20], "state=IDLE") == 0);
    }

    /* the reply word matches the STAT? command word case-insensitively */
    CHECK(rh_strcaseeq(toks[0], "stat") == 1);

    /* leading/trailing whitespace and CRLF tolerated */
    CHECK(rh_cmd_tokenize("  a b  c  ", toks, 32, &ntok) == RH_CMD_OK);
    CHECK(ntok == 3 && strcmp(toks[0], "a") == 0 && strcmp(toks[2], "c") == 0);
}

int main(void)
{
    test_basic_commands();
    test_role();
    test_mod_flrc();
    test_mod_lora();
    test_freq();
    test_pa();
    test_len_n_gap();
    test_power();
    test_token_overflow();
    test_parse_helpers();
    test_err_str();
    test_is_config();
    test_stat_example_tokens();

    if (failures == 0)
    {
        printf("test_cmd: ALL PASS\n");
        return 0;
    }
    printf("test_cmd: %d FAILURES\n", failures);
    return 1;
}
