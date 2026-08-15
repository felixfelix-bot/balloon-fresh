/**
 * @file    test_bench_payload.c
 * @brief   Host unit tests: LFSR payload generation + verification.
 */

#include "bench_payload.h"

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

static void test_lfsr_deterministic(void)
{
    uint32_t a = 12345, b = 12345;
    for (int i = 0; i < 100; i++)
        CHECK(bench_lfsr_next(&a) == bench_lfsr_next(&b));
    CHECK(a == b);
}

static void test_lfsr_never_zero(void)
{
    uint32_t st = 1;
    for (int i = 0; i < 100000; i++)
    {
        bench_lfsr_next(&st);
        CHECK(st != 0);
    }
}

static void test_header(void)
{
    uint8_t buf[64];
    bench_payload_build(buf, 64, 0xDEADBEEFU);
    CHECK(bench_payload_seq(buf) == 0xDEADBEEFU);
    CHECK(bench_payload_len_field(buf) == 64);
}

static void test_roundtrip(void)
{
    uint8_t buf[511];
    for (uint32_t seq = 0; seq < 50; seq++)
    {
        bench_payload_build(buf, 511, seq);
        CHECK(bench_payload_verify(buf, 511));
        CHECK(bench_payload_seq(buf) == seq);
    }
}

static void test_lengths(void)
{
    uint8_t buf[511];
    /* every valid FLRC length */
    for (uint32_t len = 6; len <= 511; len++)
    {
        bench_payload_build(buf, len, len * 7);
        CHECK(bench_payload_verify(buf, len));
        CHECK(bench_payload_len_field(buf) == len);
    }
}

static void test_corruption_detected(void)
{
    uint8_t buf[255];
    bench_payload_build(buf, 255, 42);
    CHECK(bench_payload_verify(buf, 255));

    buf[100] ^= 0x01;
    CHECK(!bench_payload_verify(buf, 255));

    buf[100] ^= 0x01;
    CHECK(bench_payload_verify(buf, 255));

    /* header corruption: seq change must break verification */
    bench_payload_build(buf, 255, 42);
    buf[0] ^= 0xFF;
    CHECK(!bench_payload_verify(buf, 255));
}

static void test_distinct_sequences(void)
{
    uint8_t a[32], b[32];
    bench_payload_build(a, 32, 1);
    bench_payload_build(b, 32, 2);
    CHECK(memcmp(a + 6, b + 6, 32 - 6) != 0);
    /* but same seq reproduces identical bytes */
    bench_payload_build(b, 32, 1);
    CHECK(memcmp(a, b, 32) == 0);
}

int main(void)
{
    test_lfsr_deterministic();
    test_lfsr_never_zero();
    test_header();
    test_roundtrip();
    test_lengths();
    test_corruption_detected();
    test_distinct_sequences();

    if (failures == 0)
    {
        printf("test_bench_payload: ALL PASS\n");
        return 0;
    }
    printf("test_bench_payload: %d FAILURES\n", failures);
    return 1;
}
