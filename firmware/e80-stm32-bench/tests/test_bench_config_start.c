/**
 * @file    test_bench_config_start.c
 * @brief   Host unit tests: CONFIG_START transition marker format (E80-8/O4).
 *
 * Verifies that bench_pkt_config_start() produces the correct format:
 *   CONFIG_START,<config_id>,<replicate>,<ts_ms>
 *
 * This is the O4 transition marker emitted when the firmware receives a
 * CONFIG command, allowing the host capture tool to segment captures by
 * configuration window.
 */

#include "bench_pkt.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

#define CHECK(cond)                                                              \
    do                                                                           \
    {                                                                            \
        if (!(cond))                                                            \
        {                                                                        \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);               \
            failures++;                                                          \
        }                                                                        \
    } while (0)

static void test_config_start_basic(void)
{
    bench_pkt_ctx_t ctx = { .session_id = 1, .config_id = 42, .replicate = 3 };
    char buf[128];
    uint32_t ts_ms = 123456;

    int n = bench_pkt_config_start(buf, sizeof(buf), &ctx, ts_ms);
    CHECK(n > 0);
    CHECK(strncmp(buf, "CONFIG_START,", 13) == 0);

    /* Format: CONFIG_START,<config_id>,<replicate>,<ts_ms> */
    CHECK(strstr(buf, "CONFIG_START,42,3,123456") != NULL);

    printf("  basic:  %s\n", buf);
}

static void test_config_start_zero_values(void)
{
    bench_pkt_ctx_t ctx = { .session_id = 0, .config_id = 0, .replicate = 0 };
    char buf[128];
    uint32_t ts_ms = 0;

    int n = bench_pkt_config_start(buf, sizeof(buf), &ctx, ts_ms);
    CHECK(n > 0);
    CHECK(strcmp(buf, "CONFIG_START,0,0,0") == 0);

    printf("  zero:   %s\n", buf);
}

static void test_config_start_large_values(void)
{
    bench_pkt_ctx_t ctx = { .session_id = 999, .config_id = 4294967295UL,
                            .replicate = 4294967295UL };
    char buf[128];
    uint32_t ts_ms = 4294967295UL;

    int n = bench_pkt_config_start(buf, sizeof(buf), &ctx, ts_ms);
    CHECK(n > 0);
    CHECK(strstr(buf, "CONFIG_START,4294967295,4294967295,4294967295") != NULL);

    printf("  large:  %s\n", buf);
}

static void test_config_start_truncation_safe(void)
{
    bench_pkt_ctx_t ctx = { .session_id = 0, .config_id = 999, .replicate = 888 };
    char buf[8]; /* deliberately tiny */

    int n = bench_pkt_config_start(buf, sizeof(buf), &ctx, 123456);
    CHECK(n > 0);                          /* returns required length */
    CHECK(n > (int)sizeof(buf));          /* it was truncated */
    CHECK(buf[sizeof(buf) - 1] == '\0');  /* NUL-terminated */

    printf("  trunc:  returned %d (bufsz %zu)\n", n, sizeof(buf));
}

static void test_config_start_field_count(void)
{
    /* CONFIG_START line has 4 comma-separated fields:
     * CONFIG_START, <config_id>, <replicate>, <ts_ms> */
    bench_pkt_ctx_t ctx = { .session_id = 1, .config_id = 5, .replicate = 2 };
    char buf[128];

    bench_pkt_config_start(buf, sizeof(buf), &ctx, 9999);

    int commas = 0;
    for (const char* p = buf; *p; p++)
        if (*p == ',')
            commas++;
    CHECK(commas == 3); /* 3 commas = 4 fields */

    printf("  fields: %s (%d commas)\n", buf, commas);
}

int main(void)
{
    test_config_start_basic();
    test_config_start_zero_values();
    test_config_start_large_values();
    test_config_start_truncation_safe();
    test_config_start_field_count();

    if (failures == 0)
    {
        printf("test_bench_config_start: ALL PASS\n");
        return 0;
    }
    printf("test_bench_config_start: %d FAILURES\n", failures);
    return 1;
}