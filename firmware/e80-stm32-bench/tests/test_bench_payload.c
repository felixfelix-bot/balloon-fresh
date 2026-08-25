/**
 * @file    test_bench_payload.c
 * @brief   Host unit tests: PRBS15 payload generation + verification.
 */

#include "bench_payload.h"
#include "prbs.h"

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

static void test_header(void)
{
    uint8_t buf[64];
    bench_payload_build(buf, 64, 0xDEADBEEFU);
    CHECK(bench_payload_seq(buf) == 0xDEADBEEFU);
}

static void test_roundtrip(void)
{
    uint8_t buf[511];
    for (uint32_t seq = 0; seq < 50; seq++)
    {
        bench_payload_build(buf, 511, seq);
        uint16_t bytes_bad = 0xFFFF;
        uint16_t bit_err = bench_payload_verify(buf, 511, seq, &bytes_bad);
        CHECK(bit_err == 0);
        CHECK(bytes_bad == 0);
        CHECK(bench_payload_seq(buf) == seq);
    }
}

static void test_lengths(void)
{
    uint8_t buf[511];
    /* every valid length from 4 (header only) to 511 */
    for (uint32_t len = BENCH_PAYLOAD_HDR_LEN; len <= 511; len++)
    {
        bench_payload_build(buf, len, len * 7);
        uint16_t bytes_bad = 0xFFFF;
        uint16_t bit_err = bench_payload_verify(buf, len, len * 7, &bytes_bad);
        CHECK(bit_err == 0);
        CHECK(bytes_bad == 0);
    }
}

static void test_corruption_detected(void)
{
    uint8_t buf[255];
    bench_payload_build(buf, 255, 42);
    uint16_t bytes_bad = 0;
    uint16_t bit_err = bench_payload_verify(buf, 255, 42, &bytes_bad);
    CHECK(bit_err == 0);

    /* Flip one bit in the body (after 4-byte header) */
    buf[100] ^= 0x01;
    bit_err = bench_payload_verify(buf, 255, 42, &bytes_bad);
    CHECK(bit_err == 1);
    CHECK(bytes_bad == 1);

    /* Restore and verify clean again */
    buf[100] ^= 0x01;
    bit_err = bench_payload_verify(buf, 255, 42, &bytes_bad);
    CHECK(bit_err == 0);

    /* Header corruption: seq low byte change means wrong seed -> body won't match.
     * Note: PRBS-15 seed is (uint16_t)(seq ^ 0x5A5A) | 1, so bit 0 of the
     * 16-bit state is forced to 1. Flipping bit 0 of seq produces the same
     * LFSR state, so we flip bit 1 instead to guarantee a different stream. */
    bench_payload_build(buf, 255, 42);
    buf[3] ^= 0x02;  /* flip bit 1 of seq -> different 15-bit LFSR state */
    uint32_t corrupted_seq = bench_payload_seq(buf);
    bit_err = bench_payload_verify(buf, 255, corrupted_seq, &bytes_bad);
    /* With corrupted seq used as seed, the body (generated from seq=42)
     * should not match the PRBS stream from the corrupted seq. */
    CHECK(bit_err > 0);
}

static void test_bit_errors_count(void)
{
    uint8_t buf[64];
    bench_payload_build(buf, 64, 7);

    /* Flip 3 bits in one body byte */
    buf[20] ^= 0x07;
    uint16_t bytes_bad = 0;
    uint16_t bit_err = bench_payload_verify(buf, 64, 7, &bytes_bad);
    CHECK(bit_err == 3);
    CHECK(bytes_bad == 1);
}

static void test_distinct_sequences(void)
{
    uint8_t a[32], b[32];
    bench_payload_build(a, 32, 1);
    bench_payload_build(b, 32, 2);
    /* Header bytes [0..3] differ (different seq) + body bytes [4..] differ */
    CHECK(memcmp(a, b, 32) != 0);
    /* but same seq reproduces identical bytes */
    bench_payload_build(b, 32, 1);
    CHECK(memcmp(a, b, 32) == 0);
}

static void test_min_length(void)
{
    /* Payload with only header (no body) should return 0 bit errors */
    uint8_t buf[4] = {0x00, 0x00, 0x00, 0x01};  /* seq=1 BE */
    uint16_t bytes_bad = 0xFFFF;
    uint16_t bit_err = bench_payload_verify(buf, 4, 1, &bytes_bad);
    CHECK(bit_err == 0);
    CHECK(bytes_bad == 0);
}

static void test_big_endian_header(void)
{
    /* Verify seq is stored big-endian: seq=0x12345678
     * buf[0]=0x12, buf[1]=0x34, buf[2]=0x56, buf[3]=0x78 */
    uint8_t buf[64];
    bench_payload_build(buf, 64, 0x12345678);
    CHECK(buf[0] == 0x12);
    CHECK(buf[1] == 0x34);
    CHECK(buf[2] == 0x56);
    CHECK(buf[3] == 0x78);
    CHECK(bench_payload_seq(buf) == 0x12345678);
}

int main(void)
{
    test_header();
    test_roundtrip();
    test_lengths();
    test_corruption_detected();
    test_bit_errors_count();
    test_distinct_sequences();
    test_min_length();
    test_big_endian_header();

    if (failures == 0)
    {
        printf("test_bench_payload: ALL PASS\n");
        return 0;
    }
    printf("test_bench_payload: %d FAILURES\n", failures);
    return 1;
}