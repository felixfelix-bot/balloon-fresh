/**
 * @file    prbs.c
 * @brief   PRBS15 fill + verify — STUB for TDD red phase.
 *
 * This stub makes the test compile but all functions return zero/garbage
 * so the tests FAIL.  The real implementation is added in the green phase.
 */

#include "prbs.h"

void prbs15_fill(uint8_t *buf, size_t len, uint32_t seed)
{
    (void)seed;
    for (size_t i = 0; i < len; i++)
        buf[i] = 0;
}

uint16_t prbs15_verify(const uint8_t *buf, size_t len, uint32_t seed, uint16_t *out_bytes_bad)
{
    (void)buf;
    (void)len;
    (void)seed;
    if (out_bytes_bad) *out_bytes_bad = 0;
    return 0;
}