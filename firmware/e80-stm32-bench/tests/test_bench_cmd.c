/**
 * @file    test_bench_cmd.c
 * @brief   Host unit tests: bench command parser (protocol surface + safety).
 */

#include "bench_cmd.h"
#include "radio_bench.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

#define CHECK(cond)                                                              \
    do                                                                           \
    {                                                                            \
        if (!(cond))                                                             \
        {                                                                        \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);               \
            failures++;                                                          \
        }                                                                        \
    } while (0)

static bench_cmd_t parse(const char* line)
{
    bench_cmd_t c;
    memset(&c, 0, sizeof(c));
    bench_cmd_parse(line, &c);
    return c;
}

static void test_basic_commands(void)
{
    bench_cmd_t c;

    c = parse("ID?");
    CHECK(c.id == BENCH_CMD_ID && c.err == BENCH_CMD_OK);

    c = parse("id?"); /* case-insensitive */
    CHECK(c.id == BENCH_CMD_ID);

    c = parse("STAT?");
    CHECK(c.id == BENCH_CMD_STAT);

    c = parse("STOP");
    CHECK(c.id == BENCH_CMD_STOP);

    c = parse("HELP");
    CHECK(c.id == BENCH_CMD_HELP);

    c = parse("");
    CHECK(c.err == BENCH_CMD_E_SYNTAX);

    c = parse("BOGUS 1 2");
    CHECK(c.err == BENCH_CMD_E_UNKNOWN);

    /* trailing CRLF tolerated */
    c = parse("STOP\r\n");
    CHECK(c.id == BENCH_CMD_STOP);
}

static void test_role(void)
{
    bench_cmd_t c;

    c = parse("ROLE TX");
    CHECK(c.id == BENCH_CMD_ROLE && c.role == BENCH_ROLE_TX);

    c = parse("role rx");
    CHECK(c.role == BENCH_ROLE_RX);

    c = parse("ROLE NONE");
    CHECK(c.role == BENCH_ROLE_NONE);

    c = parse("ROLE BOGUS");
    CHECK(c.err == BENCH_CMD_E_ARG);

    c = parse("ROLE");
    CHECK(c.err == BENCH_CMD_E_SYNTAX);

    c = parse("ARM TX");
    CHECK(c.id == BENCH_CMD_ARM_TX);

    c = parse("ARM RX");
    CHECK(c.err == BENCH_CMD_E_SYNTAX);
}

static void test_freq_band(void)
{
    bench_cmd_t c;

    c = parse("FREQ 915000000");
    CHECK(c.id == BENCH_CMD_FREQ && c.freq_hz == 915000000UL);

    c = parse("FREQ 433500000");
    CHECK(c.id == BENCH_CMD_FREQ && c.freq_hz == 433500000UL); /* in-band check is firmware-side */

    c = parse("FREQ abc");
    CHECK(c.err == BENCH_CMD_E_ARG);

    c = parse("FREQ 99999999999"); /* > u32 */
    CHECK(c.err == BENCH_CMD_E_ARG);

    c = parse("BAND OVERRIDE 2026");
    CHECK(c.id == BENCH_CMD_BAND_OVERRIDE && c.pin == 2026);

    c = parse("BAND OVERRIDE 1234");
    CHECK(c.id == BENCH_CMD_BAND_OVERRIDE && c.pin == 1234); /* pin check firmware-side */

    c = parse("BAND OVERRIDE");
    CHECK(c.err == BENCH_CMD_E_ARG);

    c = parse("POWER MODE OUTDOOR 2026");
    CHECK(c.id == BENCH_CMD_POWER_OUTDOOR && c.pin == 2026);

    c = parse("POWER MODE OUTDOOR 9999");
    CHECK(c.id == BENCH_CMD_POWER_OUTDOOR && c.pin == 9999); /* pin check firmware-side */

    c = parse("POWER MODE INDOOR 2026");
    CHECK(c.err == BENCH_CMD_E_SYNTAX);

    c = parse("POWER MODE OUTDOOR");
    CHECK(c.err == BENCH_CMD_E_SYNTAX);
}

static void test_mod(void)
{
    bench_cmd_t c;

    c = parse("MOD loRa 7 125");
    CHECK(c.id == BENCH_CMD_MOD && c.mod == BENCH_MOD_LORA);
    CHECK(c.sf == 7 && c.bw_hz == 125000);

    c = parse("MOD lora 12 500");
    CHECK(c.sf == 12 && c.bw_hz == 500000);

    c = parse("MOD lora 4 125");
    CHECK(c.err == BENCH_CMD_E_RANGE);

    c = parse("MOD lora 13 125");
    CHECK(c.err == BENCH_CMD_E_RANGE);

    c = parse("MOD lora 7 137");
    CHECK(c.err == BENCH_CMD_E_RANGE);

    c = parse("MOD flrc 650 22");
    CHECK(c.id == BENCH_CMD_MOD && c.mod == BENCH_MOD_FLRC);
    CHECK(c.br_bps == 650000 && c.txpow_dbm == 22);

    c = parse("MOD flrc 2600 0");
    CHECK(c.br_bps == 2600000 && c.txpow_dbm == 0);

    c = parse("MOD flrc 666 22");
    CHECK(c.err == BENCH_CMD_E_RANGE);

    c = parse("MOD flrc 650 23");
    CHECK(c.err == BENCH_CMD_E_RANGE);

    c = parse("MOD flrc 650 -5");
    CHECK(c.err == BENCH_CMD_E_RANGE);

    c = parse("MOD gfsk 650 22");
    CHECK(c.err == BENCH_CMD_E_ARG);
}

static void test_start(void)
{
    bench_cmd_t c;

    c = parse("START N=1000 LEN=255 GAP=5000");
    CHECK(c.id == BENCH_CMD_START);
    CHECK(c.n_pkts == 1000 && c.len_bytes == 255 && c.gap_us == 5000);
    CHECK(c.has_n && c.has_len && c.has_gap);

    /* order independence */
    c = parse("START GAP=1000 LEN=64 N=5");
    CHECK(c.n_pkts == 5 && c.len_bytes == 64 && c.gap_us == 1000);

    /* defaults */
    c = parse("START");
    CHECK(c.n_pkts == 100 && c.len_bytes == 255 && c.gap_us == 5000);
    CHECK(!c.has_n && !c.has_len && !c.has_gap);

    /* ranges */
    c = parse("START LEN=5");
    CHECK(c.err == BENCH_CMD_E_RANGE); /* < 6 */

    c = parse("START LEN=512");
    CHECK(c.err == BENCH_CMD_E_RANGE); /* > 511 */

    c = parse("START N=0");
    CHECK(c.err == BENCH_CMD_E_RANGE);

    c = parse("START GAP=1");
    CHECK(c.err == BENCH_CMD_E_RANGE);

    c = parse("START N=abc");
    CHECK(c.err == BENCH_CMD_E_ARG);

    c = parse("START FOO=1");
    CHECK(c.err == BENCH_CMD_E_ARG);
}

static void test_pa(void)
{
    bench_cmd_t c;

    c = parse("PA 22");
    CHECK(c.id == BENCH_CMD_PA && c.txpow_dbm == 22);

    c = parse("PA 0");
    CHECK(c.txpow_dbm == 0);

    c = parse("PA -3");
    CHECK(c.txpow_dbm == -3);

    c = parse("PA");
    CHECK(c.err == BENCH_CMD_E_ARG);
}

static void test_token_overflow(void)
{
    char longtok[64];
    memset(longtok, 'A', sizeof(longtok) - 1);
    longtok[sizeof(longtok) - 1] = '\0';
    bench_cmd_t c = parse(longtok);
    CHECK(c.err == BENCH_CMD_E_SYNTAX);

    c = parse("A B C D E F G H I"); /* 9 tokens > 8 */
    CHECK(c.err == BENCH_CMD_E_SYNTAX);
}

static void test_parse_helpers(void)
{
    uint32_t u;
    int8_t i;

    CHECK(bench_parse_u32("0", &u) && u == 0);
    CHECK(bench_parse_u32("4294967295", &u) && u == 4294967295UL);
    CHECK(!bench_parse_u32("4294967296", &u));
    CHECK(!bench_parse_u32("12a", &u));
    CHECK(!bench_parse_u32("-1", &u));
    CHECK(!bench_parse_u32("", &u));

    CHECK(bench_parse_i8("-128", &i) && i == -128);
    CHECK(bench_parse_i8("127", &i) && i == 127);
    CHECK(!bench_parse_i8("128", &i));
    CHECK(!bench_parse_i8("--1", &i));
}

static void test_radio_config_has_cr_field(void)
{
    radio_bench_cfg_t cfg;
    memset(&cfg, 0, sizeof(cfg));
    cfg.cr = 5; /* LoRa 4/5 */
    CHECK(cfg.cr == 5);
    cfg.cr = 1; /* FLRC 3/4 */
    CHECK(cfg.cr == 1);
}

static void test_quiet(void)
{
    bench_cmd_t c;

    /* QUIET ON */
    c = parse("QUIET ON");
    CHECK(c.id == BENCH_CMD_QUIET && c.err == BENCH_CMD_OK);
    CHECK(c.quiet_enable == true);

    /* case-insensitive */
    c = parse("quiet on");
    CHECK(c.id == BENCH_CMD_QUIET && c.quiet_enable == true);

    /* QUIET OFF */
    c = parse("QUIET OFF");
    CHECK(c.id == BENCH_CMD_QUIET && c.err == BENCH_CMD_OK);
    CHECK(c.quiet_enable == false);

    /* case-insensitive OFF */
    c = parse("Quiet Off");
    CHECK(c.id == BENCH_CMD_QUIET && c.quiet_enable == false);

    /* QUIET with no argument -> syntax error */
    c = parse("QUIET");
    CHECK(c.err == BENCH_CMD_E_SYNTAX);

    /* QUIET with bad argument -> arg error */
    c = parse("QUIET YES");
    CHECK(c.err == BENCH_CMD_E_ARG);

    /* QUIET with too many tokens -> syntax error */
    c = parse("QUIET ON NOW");
    CHECK(c.err == BENCH_CMD_E_SYNTAX);
}

int main(void)
{
    test_basic_commands();
    test_role();
    test_freq_band();
    test_mod();
    test_start();
    test_pa();
    test_token_overflow();
    test_parse_helpers();
    test_radio_config_has_cr_field();
    test_quiet();

    if (failures == 0)
    {
        printf("test_bench_cmd: ALL PASS\n");
        return 0;
    }
    printf("test_bench_cmd: %d FAILURES\n", failures);
    return 1;
}
