/**
 * @file    test_prbs.c
 * @brief   Host unit tests: PRBS15 fill + verify (TDD red phase).
 *
 * Tests the C3-compatible PRBS15 algorithm:
 *   - Polynomial x^15 + x^14 + 1 (Galois LFSR)
 *   - Seed: (uint16_t)(seed ^ 0x5A5A) | 1
 *   - MSB-first byte assembly
 *   - verify: regenerate + XOR + popcount
 */

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

/* ---- Expected values computed from the C3 reference algorithm ---- */

/* seed=1, first 8 bytes: 0xDD 0xD8 0xCC 0xD2 0xAA 0xEF 0xFE 0x60 */
static const uint8_t expected_seed1[8] = {
    0xDD, 0xD8, 0xCC, 0xD2, 0xAA, 0xEF, 0xFE, 0x60
};

/* seed=12345, first 16 bytes:
 * 0x7D 0x4B 0x0F 0xBA 0x21 0x9C 0xC5 0x4A
 * 0x9F 0xBF 0x41 0x83 0x85 0x09 0x1E 0x36 */
static const uint8_t expected_seed12345[16] = {
    0x7D, 0x4B, 0x0F, 0xBA, 0x21, 0x9C, 0xC5, 0x4A,
    0x9F, 0xBF, 0x41, 0x83, 0x85, 0x09, 0x1E, 0x36
};

/* ---- Test 1: fill generates known pattern ---- */

static void test_prbs15_fill_generates_known_pattern(void)
{
    uint8_t buf[8];
    memset(buf, 0, sizeof(buf));

    prbs15_fill(buf, 8, 1);

    for (int i = 0; i < 8; i++)
    {
        CHECK(buf[i] == expected_seed1[i]);
    }
}

/* ---- Test 2: verify detects bit errors ---- */

static void test_prbs15_verify_detects_bit_errors(void)
{
    uint8_t buf[64];

    /* Fill with correct PRBS15 stream */
    prbs15_fill(buf, 64, 42);

    /* Flip 1 bit */
    buf[10] ^= 0x10;  /* flip bit 4 in byte 10 */
    uint16_t bytes_bad = 0;
    uint16_t bit_err = prbs15_verify(buf, 64, 42, &bytes_bad);
    CHECK(bit_err == 1);
    CHECK(bytes_bad == 1);

    /* Restore and flip 3 bits in different bytes */
    prbs15_fill(buf, 64, 42);
    buf[5]  ^= 0x01;  /* flip 1 bit in byte 5 */
    buf[20] ^= 0x80; /* flip 1 bit in byte 20 */
    buf[50] ^= 0x40; /* flip 1 bit in byte 50 */
    bytes_bad = 0;
    bit_err = prbs15_verify(buf, 64, 42, &bytes_bad);
    CHECK(bit_err == 3);
    CHECK(bytes_bad == 3);
}

/* ---- Test 3: verify zero errors on correct data ---- */

static void test_prbs15_verify_zero_errors_on_correct_data(void)
{
    /* Test with lengths 8, 64, 255 */
    uint8_t buf[255];

    prbs15_fill(buf, 8, 7);
    uint16_t bytes_bad = 0;
    uint16_t bit_err = prbs15_verify(buf, 8, 7, &bytes_bad);
    CHECK(bit_err == 0);
    CHECK(bytes_bad == 0);

    prbs15_fill(buf, 64, 7);
    bytes_bad = 0;
    bit_err = prbs15_verify(buf, 64, 7, &bytes_bad);
    CHECK(bit_err == 0);
    CHECK(bytes_bad == 0);

    prbs15_fill(buf, 255, 7);
    bytes_bad = 0;
    bit_err = prbs15_verify(buf, 255, 7, &bytes_bad);
    CHECK(bit_err == 0);
    CHECK(bytes_bad == 0);
}

/* ---- Test 4: cross-compatibility with C3 hard-coded values ---- */

static void test_prbs15_cross_compat(void)
{
    uint8_t buf1[8];
    uint8_t buf2[16];

    /* seed=1 */
    prbs15_fill(buf1, 8, 1);
    CHECK(memcmp(buf1, expected_seed1, 8) == 0);

    /* seed=12345 */
    prbs15_fill(buf2, 16, 12345);
    CHECK(memcmp(buf2, expected_seed12345, 16) == 0);
}

/* ---- Test 5: different seeds produce different output ---- */

static void test_prbs15_seeded_differently_produces_different_output(void)
{
    uint8_t a[64], b[64];

    prbs15_fill(a, 64, 1);
    prbs15_fill(b, 64, 2);
    CHECK(memcmp(a, b, 64) != 0);

    /* Same seed reproduces identical stream */
    prbs15_fill(b, 64, 1);
    CHECK(memcmp(a, b, 64) == 0);
}

/* ---- Test 6: verify after 4-byte big-endian header format ---- */

static void test_prbs15_verify_after_header_format(void)
{
    uint8_t buf[128];
    uint32_t seq = 0x12345678;

    /* 4-byte big-endian header (C3 format) */
    buf[0] = (seq >> 24) & 0xFF;
    buf[1] = (seq >> 16) & 0xFF;
    buf[2] = (seq >> 8) & 0xFF;
    buf[3] = seq & 0xFF;

    /* PRBS15 fill after header, using seq as seed */
    prbs15_fill(buf + 4, 124, seq);

    /* Verify the PRBS portion */
    uint16_t bytes_bad = 0;
    uint16_t bit_err = prbs15_verify(buf + 4, 124, seq, &bytes_bad);
    CHECK(bit_err == 0);
    CHECK(bytes_bad == 0);

    /* Corrupt one PRBS byte and re-verify */
    buf[10] ^= 0x01;
    bytes_bad = 0;
    bit_err = prbs15_verify(buf + 4, 124, seq, &bytes_bad);
    CHECK(bit_err == 1);
    CHECK(bytes_bad == 1);
}

/* ---- Main ---- */

int main(void)
{
    test_prbs15_fill_generates_known_pattern();
    test_prbs15_verify_detects_bit_errors();
    test_prbs15_verify_zero_errors_on_correct_data();
    test_prbs15_cross_compat();
    test_prbs15_seeded_differently_produces_different_output();
    test_prbs15_verify_after_header_format();

    if (failures == 0)
    {
        printf("test_prbs: ALL PASS\n");
        return 0;
    }
    printf("test_prbs: %d FAILURES\n", failures);
    return 1;
}