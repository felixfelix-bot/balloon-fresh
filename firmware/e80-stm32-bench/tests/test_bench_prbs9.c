/**
 * @file    test_bench_prbs9.c
 * @brief   Host unit tests: PRBS9 CONFIG command parser + tx_test_mode dispatch.
 *
 * Tests:
 *   1. "PRBS9 ON"  parses to BENCH_CMD_PRBS9, prbs9_enable=true
 *   2. "PRBS9 OFF" parses to BENCH_CMD_PRBS9, prbs9_enable=false
 *   3. Bad arg (e.g. "PRBS9 FOO") → parse error
 *   4. Missing arg ("PRBS9") → parse error
 *   5. radio_bench_set_tx_test_mode exists and is callable (link test)
 */

#include "bench_cmd.h"
#include "radio_bench.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

#define CHECK(cond)                                                              \
    do                                                                          \
    {                                                                           \
        if (!(cond))                                                            \
        {                                                                       \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);              \
            failures++;                                                         \
        }                                                                       \
    } while (0)

static bench_cmd_t parse(const char* line)
{
    bench_cmd_t c;
    memset(&c, 0, sizeof(c));
    bench_cmd_parse(line, &c);
    return c;
}

/* Test 1: "PRBS9 ON" → BENCH_CMD_PRBS9, prbs9_enable=true */
static void test_prbs9_on(void)
{
    bench_cmd_t c = parse("PRBS9 ON");
    CHECK(c.id == BENCH_CMD_PRBS9);
    CHECK(c.err == BENCH_CMD_OK);
    CHECK(c.prbs9_enable == true);
}

/* Test 2: "PRBS9 OFF" → BENCH_CMD_PRBS9, prbs9_enable=false */
static void test_prbs9_off(void)
{
    bench_cmd_t c = parse("PRBS9 OFF");
    CHECK(c.id == BENCH_CMD_PRBS9);
    CHECK(c.err == BENCH_CMD_OK);
    CHECK(c.prbs9_enable == false);
}

/* Test 3: case-insensitive */
static void test_prbs9_case_insensitive(void)
{
    bench_cmd_t c = parse("prbs9 on");
    CHECK(c.id == BENCH_CMD_PRBS9);
    CHECK(c.prbs9_enable == true);

    c = parse("Prbs9 Off");
    CHECK(c.id == BENCH_CMD_PRBS9);
    CHECK(c.prbs9_enable == false);
}

/* Test 4: bad argument */
static void test_prbs9_bad_arg(void)
{
    bench_cmd_t c = parse("PRBS9 FOO");
    CHECK(c.err != BENCH_CMD_OK);

    c = parse("PRBS9 1");
    CHECK(c.err != BENCH_CMD_OK);
}

/* Test 5: missing argument */
static void test_prbs9_missing_arg(void)
{
    bench_cmd_t c = parse("PRBS9");
    CHECK(c.err != BENCH_CMD_OK);
}

/* Test 6: too many tokens */
static void test_prbs9_extra_tokens(void)
{
    bench_cmd_t c = parse("PRBS9 ON NOW");
    CHECK(c.err != BENCH_CMD_OK);
}

/* Test 7: radio_bench_set_tx_test_mode symbol exists (link test) */
static void test_radio_bench_set_tx_test_mode_exists(void)
{
    /* If this compiles + links, the function exists. */
    CHECK(&radio_bench_set_tx_test_mode != NULL);
}

int main(void)
{
    test_prbs9_on();
    test_prbs9_off();
    test_prbs9_case_insensitive();
    test_prbs9_bad_arg();
    test_prbs9_missing_arg();
    test_prbs9_extra_tokens();
    test_radio_bench_set_tx_test_mode_exists();

    if (failures == 0)
    {
        printf("test_bench_prbs9: ALL PASS\n");
        return 0;
    }
    printf("test_bench_prbs9: %d FAILURES\n", failures);
    return 1;
}