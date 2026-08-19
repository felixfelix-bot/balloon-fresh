/**
 * @file    test_radio_bench_cfg.c
 * @brief   Host unit tests: radio_bench_cfg_t struct fields (E80-4).
 *
 * Verifies the cr (coding rate) field exists in radio_bench_cfg_t
 * so per-packet PKT output can include it.
 */

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

static void test_radio_config_has_cr_field(void)
{
    radio_bench_cfg_t cfg;
    memset(&cfg, 0, sizeof(cfg));

    /* LoRa CR: denominator form (5 = 4/5) */
    cfg.cr = 5;
    CHECK(cfg.cr == 5);

    /* FLRC CR: register code (1 = 3/4) */
    cfg.cr = 1;
    CHECK(cfg.cr == 1);

    /* Field is uint8_t */
    CHECK(sizeof(cfg.cr) == 1);
}

static void test_radio_config_other_fields_intact(void)
{
    radio_bench_cfg_t cfg;
    memset(&cfg, 0, sizeof(cfg));

    /* Verify all original fields still exist */
    cfg.mod = BENCH_MOD_LORA;
    cfg.sf = 8;
    cfg.bw_hz = 125000;
    cfg.br_bps = 650000;
    cfg.txpow_dbm = 10;
    cfg.freq_hz = 868000000UL;

    CHECK(cfg.mod == BENCH_MOD_LORA);
    CHECK(cfg.sf == 8);
    CHECK(cfg.bw_hz == 125000);
    CHECK(cfg.br_bps == 650000);
    CHECK(cfg.txpow_dbm == 10);
    CHECK(cfg.freq_hz == 868000000UL);
}

int main(void)
{
    test_radio_config_has_cr_field();
    test_radio_config_other_fields_intact();

    if (failures == 0)
    {
        printf("test_radio_bench_cfg: ALL PASS\n");
        return 0;
    }
    printf("test_radio_bench_cfg: %d FAILURE(S)\n", failures);
    return 1;
}