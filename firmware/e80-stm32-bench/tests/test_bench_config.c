/**
 * @file    test_bench_config.c
 * @brief   Host unit tests: compile-time configuration constants.
 *
 * These tests pin the exact values of E80_BENCH_* defines as shipped in
 * main.h.  Any accidental change to a config constant is caught here.
 */

#include "main.h"

#include <stdio.h>

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

/* ---- Console baud rate ----------------------------------------------------- */

static void test_baud_default(void)
{
    /* E80-2: Bumped from 115200 to 2,000,000 baud.  CH340 supports 2 Mbps,
     * STM32F103 USART1 supports up to 4.5 Mbps, and the IRQ-driven RX ring
     * buffer handles the higher data rate without overrun. */
    CHECK(E80_BENCH_BAUD_DEFAULT == 2000000U);
}

/* ---- Compile-time safety caps ---------------------------------------------- */

static void test_tx_inhibited(void)
{
    CHECK(E80_BENCH_BOOT_TX_INHIBITED == 1);
}

static void test_freq_default(void)
{
    CHECK(E80_BENCH_FREQ_DEFAULT_HZ == 868000000UL);
}

static void test_freq_band_clamps(void)
{
    CHECK(E80_BENCH_BAND_MIN_HZ == 863000000UL);
    CHECK(E80_BENCH_BAND_MAX_HZ == 870000000UL);
    CHECK(E80_BENCH_OVERRIDE_PIN == 2026);
    CHECK(E80_BENCH_OVERRIDE_MIN_HZ == 410000000UL);
    CHECK(E80_BENCH_OVERRIDE_MAX_HZ == 2483500000UL);
    CHECK(E80_BENCH_BAND_2G4_MIN_HZ == 2400000000UL);
    CHECK(E80_BENCH_BAND_2G4_MAX_HZ == 2483500000UL);
}

static void test_txpower_caps(void)
{
    CHECK(E80_BENCH_TXPOW_CAP_INDOOR_DBM == 10);
    CHECK(E80_BENCH_TXPOW_MAX_DBM == 22);
}

static void test_max_payload(void)
{
    CHECK(E80_BENCH_MAX_PAYLOAD == 512);
}

int main(void)
{
    test_baud_default();
    test_tx_inhibited();
    test_freq_default();
    test_freq_band_clamps();
    test_txpower_caps();
    test_max_payload();

    if (failures == 0)
    {
        printf("test_bench_config: ALL PASS\n");
        return 0;
    }
    printf("test_bench_config: %d FAILURE(S)\n", failures);
    return 1;
}