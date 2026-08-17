/**
 * @file    test_bw_codes.cpp
 * @brief   Host unit tests: BW-1 LR2021 LoRa bandwidth code table.
 *
 * Pins the shared single-source header (src/lr2021_bw_codes.h) against the
 * authoritative ground truth extracted from the vendored Semtech lr20xx_driver:
 *
 *   Provenance (do not edit — read-only ground truth):
 *   ~/repos/balloon-e80bench/firmware/e80-stm32-bench/third_party/Radio/
 *     lr20xx_driver/inc/lr20xx_radio_lora_types.h   L93-111  (enum wire codes)
 *     lr20xx_driver/src/lr20xx_radio_lora.c         L185-195 (SetModulationParams
 *                                                          packing: (sf<<4)+bw)
 *     lr20xx_driver/src/lr20xx_radio_lora.c         L485-542 (get_bw_in_hz)
 *
 * Reconciliation (BW-1): lora_868_tx.cpp L63-69 (203/406/812 -> 0x0D/0x0E/0x0F)
 * and dual_radio_sweep_tx.cpp L69 (0x05=250 kHz) are BOTH correct subsets of
 * this table — the apparent contradiction was only partial views of it.
 *
 * Run:  make -C firmware/rp2040/host-tests && ./host-tests/test_bw_codes
 */

#include "lr2021_bw_codes.h"

#include <stdio.h>
#include <stdint.h>

static int failures = 0;

#define CHECK(cond)                                                            \
    do                                                                         \
    {                                                                          \
        if (!(cond))                                                           \
        {                                                                      \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);             \
            failures++;                                                        \
        }                                                                      \
    } while (0)

/* ---- Ground truth: copied verbatim from vendored lr20xx_driver -------------
 * (enum code + get_bw_in_hz value, ordered by code 0x00..0x0F). */
typedef struct
{
    uint8_t  code;
    uint32_t hz;
    uint32_t khz_label;
} bw_row_t;

static const bw_row_t GROUND_TRUTH[16] = {
    {0x00, 7812UL, 7UL},     {0x01, 15625UL, 15UL},   {0x02, 31250UL, 31UL},
    {0x03, 62500UL, 62UL},   {0x04, 125000UL, 125UL}, {0x05, 250000UL, 250UL},
    {0x06, 500000UL, 500UL}, {0x07, 1000000UL, 1000UL},
    {0x08, 10417UL, 10UL},   {0x09, 20833UL, 20UL},   {0x0A, 41667UL, 41UL},
    {0x0B, 83340UL, 83UL},   {0x0C, 101563UL, 101UL},
    {0x0D, 203000UL, 203UL}, {0x0E, 406000UL, 406UL}, {0x0F, 812000UL, 812UL},
};

/* ---- Table completeness & exact values ------------------------------------ */

static void test_code_to_hz_exact(void)
{
    for (int i = 0; i < 16; i++)
    {
        uint32_t hz = lr2021_bw_code_to_hz(GROUND_TRUTH[i].code);
        if (hz != GROUND_TRUTH[i].hz)
        {
            printf("FAIL code 0x%02X: got %lu Hz, want %lu Hz\n",
                   GROUND_TRUTH[i].code, (unsigned long)hz,
                   (unsigned long)GROUND_TRUTH[i].hz);
            failures++;
        }
    }
}

static void test_invalid_codes(void)
{
    CHECK(lr2021_bw_code_to_hz(0x10) == 0U);
    CHECK(lr2021_bw_code_to_hz(0xFF) == 0U);
    CHECK(lr2021_bw_hz_to_code(0U) == LR2021_BW_CODE_INVALID);
    CHECK(lr2021_bw_hz_to_code(124000U) == LR2021_BW_CODE_INVALID); /* not a row */
    CHECK(lr2021_bw_hz_to_code(8000000U) == LR2021_BW_CODE_INVALID);
}

static void test_enum_wire_codes(void)
{
    /* Enum values must equal the lr20xx_driver enum codes exactly. */
    CHECK(LR2021_LORA_BW_7 == 0x00);
    CHECK(LR2021_LORA_BW_15 == 0x01);
    CHECK(LR2021_LORA_BW_31 == 0x02);
    CHECK(LR2021_LORA_BW_62 == 0x03);
    CHECK(LR2021_LORA_BW_125 == 0x04);
    CHECK(LR2021_LORA_BW_250 == 0x05);
    CHECK(LR2021_LORA_BW_500 == 0x06);
    CHECK(LR2021_LORA_BW_1000 == 0x07);
    CHECK(LR2021_LORA_BW_10 == 0x08);
    CHECK(LR2021_LORA_BW_20 == 0x09);
    CHECK(LR2021_LORA_BW_41 == 0x0A);
    CHECK(LR2021_LORA_BW_83 == 0x0B);
    CHECK(LR2021_LORA_BW_101 == 0x0C);
    CHECK(LR2021_LORA_BW_203 == 0x0D);
    CHECK(LR2021_LORA_BW_406 == 0x0E);
    CHECK(LR2021_LORA_BW_812 == 0x0F);
    CHECK(LR2021_BW_CODE_INVALID == 0xFF);
}

/* ---- kHz label mapping (console protocol `MOD LORA <sf> <bw_khz>`) -------- */

static void test_khz_to_code_roundtrip(void)
{
    for (int i = 0; i < 16; i++)
    {
        uint8_t code = lr2021_bw_khz_to_code(GROUND_TRUTH[i].khz_label);
        if (code != GROUND_TRUTH[i].code)
        {
            printf("FAIL khz %lu: got code 0x%02X, want 0x%02X\n",
                   (unsigned long)GROUND_TRUTH[i].khz_label, code,
                   GROUND_TRUTH[i].code);
            failures++;
        }
    }
    CHECK(lr2021_bw_khz_to_code(0U) == LR2021_BW_CODE_INVALID);
    CHECK(lr2021_bw_khz_to_code(300U) == LR2021_BW_CODE_INVALID);
    CHECK(lr2021_bw_khz_to_code(600U) == LR2021_BW_CODE_INVALID);
}

static void test_hz_to_code_exact(void)
{
    /* Bench-critical rows: LF 125/250, HF 812, plus the wide-BW ladder. */
    CHECK(lr2021_bw_hz_to_code(125000U) == 0x04);
    CHECK(lr2021_bw_hz_to_code(250000U) == 0x05);
    CHECK(lr2021_bw_hz_to_code(500000U) == 0x06);
    CHECK(lr2021_bw_hz_to_code(203000U) == 0x0D);
    CHECK(lr2021_bw_hz_to_code(406000U) == 0x0E);
    CHECK(lr2021_bw_hz_to_code(812000U) == 0x0F);
}

/* ---- SetModulationParams wire packing (documented ground truth) -----------
 * lr20xx_radio_lora.c L187-191: opcode 0x0220, then
 *   cbuffer[2] = (sf << 4) + bw        (SF5..SF12 = 0x05..0x0C per driver enum)
 *   cbuffer[3] = (cr << 4) + ppm
 * This test pins the BW half-byte convention FW-5a will rely on. */

static void test_setmodparams_packing(void)
{
    CHECK(((7 << 4) | LR2021_LORA_BW_250) == 0x75);   /* SF7/BW250  */
    CHECK(((12 << 4) | LR2021_LORA_BW_125) == 0xC4);  /* SF12/BW125 */
    CHECK(((5 << 4) | LR2021_LORA_BW_812) == 0x5F);   /* SF5/BW812  */
}

int main(void)
{
    test_code_to_hz_exact();
    test_invalid_codes();
    test_enum_wire_codes();
    test_khz_to_code_roundtrip();
    test_hz_to_code_exact();
    test_setmodparams_packing();

    if (failures == 0)
    {
        printf("test_bw_codes: ALL PASS\n");
        return 0;
    }
    printf("test_bw_codes: %d FAILURES\n", failures);
    return 1;
}
