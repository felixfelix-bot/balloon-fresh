/**
 * @file    test_bench_safety.c
 * @brief   Host unit tests: TX-hang watchdog math (chip TX timeout, superloop
 *          backstop) and STM32 IWDG prescaler math.
 *
 * Reference values hand-derived from:
 *   - LoRa airtime: Semtech AN1200.24 symbol formula (CR4/5, explicit header,
 *     CRC16, 8-symbol preamble), worst of the LDRO on/off variants, ceiling
 *     integer math in quarter-symbols.
 *   - FLRC airtime: 32b preamble + 32b syncword + payload + 16b CRC, all
 *     CR3/4-coded (x4/3), at the configured bit rate.
 *   - Chip timeout: airtime_ms * 2 + 50 ms slack, clamped to [100, 60000] ms.
 *     60000 ms cap keeps the vendored driver's ms->RTC-step conversion
 *     (ms * 32768 / 1000, uint32) overflow-free and under the 24-bit
 *     SetTx timeout register (max 512 s).
 *   - Backstop: (2 * chip_timeout_ms + 50) * 1000 us, wraparound-safe compare.
 *   - IWDG: t = ceil((reload+1) * (4 << pr) * 1000 / lsi_hz).
 */

#include "bench_safety.h"

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

/* ---- LoRa airtime ---------------------------------------------------------- */

static void test_lora_airtime_exact(void)
{
    /* Bench worst case: SF12 / BW125 / 255 B.
     * num = 8*255 - 4*12 + 28 + 16 = 2036 bits; LDRO-on denom 4*(12-2)=40
     * -> ceil(2036/40)=51 code blocks * (1+4) = 255 + 8 = 263 symbols.
     * Quarter-symbols: 8*4 (preamble) + 17 (4.25 SFD) + 263*4 = 1101.
     * Tsym = 2^12 / 125 kHz = 32768 us -> 1101 * 32768 / 4 = 9,019,392 us.
     * (263 payload symbols cross-checks against SX126x calculators.) */
    CHECK(bench_safety_lora_airtime_us(12, 125000, 255) == 9019392U);

    /* SF7 / BW125 / 16 B: num = 144; LDRO-on denom 20 -> ceil(7.2)=8 *5 = 40
     * + 8 = 48 symbols; q = 32 + 17 + 192 = 241; Tsym = 1024 us
     * -> 241 * 1024 / 4 = 61,696 us. */
    CHECK(bench_safety_lora_airtime_us(7, 125000, 16) == 61696U);

    /* SF5 / BW500 / 6 B (smallest legal LoRa payload): num = 72;
     * LDRO-on denom 12 -> ceil(6)=6 *5 = 30 + 8 = 38 symbols;
     * q = 32 + 17 + 152 = 201; Tsym = 64 us -> 201*64/4 = 3,216 us. */
    CHECK(bench_safety_lora_airtime_us(5, 500000, 6) == 3216U);
}

static void test_lora_airtime_monotonic(void)
{
    uint32_t t;

    CHECK(bench_safety_lora_airtime_us(12, 125000, 255) >
          bench_safety_lora_airtime_us(7, 125000, 255));   /* SF up = slower */
    CHECK(bench_safety_lora_airtime_us(7, 125000, 255) >
          bench_safety_lora_airtime_us(7, 500000, 255));   /* BW up = faster */
    t = bench_safety_lora_airtime_us(9, 125000, 1);
    CHECK(bench_safety_lora_airtime_us(9, 125000, 255) > t); /* len up = slower */
}

/* ---- FLRC airtime ----------------------------------------------------------- */

static void test_flrc_airtime_exact(void)
{
    /* 650 kbps, 255 B: bits = 32+32+8*255+16 = 2120 -> coded ceil(2120*4/3)
     * = 2827 -> ceil(2827 * 1e6 / 650000) = 4350 us. */
    CHECK(bench_safety_flrc_airtime_us(650000, 255) == 4350U);

    /* 260 kbps, 511 B (slowest FLRC, max bench LEN): bits = 4168 -> coded 5558
     * -> ceil(5558 * 1e6 / 260000) = 21,377 us. */
    CHECK(bench_safety_flrc_airtime_us(260000, 511) == 21377U);

    /* 2.6 Mbps, 6 B: bits = 128 -> coded 171 -> 66 us. */
    CHECK(bench_safety_flrc_airtime_us(2600000, 6) == 66U);
}

/* ---- Chip TX timeout --------------------------------------------------------- */

static void test_tx_timeout_bounds(void)
{
    /* Fast configs clamp to the 100 ms floor. */
    CHECK(bench_safety_tx_timeout_ms(BENCH_MOD_LORA, 5, 500000, 0, 6) == 100U);
    CHECK(bench_safety_tx_timeout_ms(BENCH_MOD_FLRC, 0, 0, 2600000, 6) == 100U);

    /* SF7/BW125/16 B: airtime 61,696 us -> 62 ms -> 62*2+50 = 174 ms. */
    CHECK(bench_safety_tx_timeout_ms(BENCH_MOD_LORA, 7, 125000, 0, 16) == 174U);

    /* Bench worst case SF12/BW125/255 B: 9020 ms -> 18,090 ms. */
    CHECK(bench_safety_tx_timeout_ms(BENCH_MOD_LORA, 12, 125000, 0, 255) ==
          18090U);
}

static void test_tx_timeout_never_overflows_driver_convert(void)
{
    /* The vendored driver computes ms * 32768 / 1000 in uint32 and writes 24
     * timeout bits: ms must stay <= 131071 (uint32) and <= 512000 (24-bit).
     * Sweep every legal bench config at max LEN and hold the 60 s cap. */
    static const uint32_t bw[3] = { 125000, 250000, 500000 };
    static const uint32_t br[8] = { 260000, 325000, 520000, 650000,
                                    1040000, 1300000, 2080000, 2600000 };
    for (int i = 0; i < 3; i++)
        for (uint8_t sf = 5; sf <= 12; sf++)
        {
            uint32_t ms = bench_safety_tx_timeout_ms(BENCH_MOD_LORA, sf, bw[i],
                                                     0, 255);
            CHECK(ms >= 100U && ms <= 60000U);
        }
    for (int i = 0; i < 7; i++)
    {
        uint32_t ms = bench_safety_tx_timeout_ms(BENCH_MOD_FLRC, 0, 0, br[i],
                                                 511);
        CHECK(ms >= 100U && ms <= 60000U);
    }
}

/* ---- Superloop backstop ------------------------------------------------------- */

static void test_backstop_window(void)
{
    CHECK(bench_safety_tx_backstop_us(100U) == 250000U);
    CHECK(bench_safety_tx_backstop_us(18086U) == 36222000U);
}

static void test_backstop_fired(void)
{
    /* Not fired just before the boundary, fired at/after it. */
    CHECK(!bench_safety_tx_backstop_fired(1000U, 1000U + 249999U, 100U));
    CHECK(bench_safety_tx_backstop_fired(1000U, 1000U + 250000U, 100U));

    /* A normal FLRC packet (chip timeout 100 ms floor) can never trip it. */
    CHECK(!bench_safety_tx_backstop_fired(0U, 80000U, 100U));

    /* micros() wraparound: t0 near 2^32, elapsed crosses zero. */
    uint32_t t0 = 0xFFFFF000U;
    CHECK(bench_safety_tx_backstop_fired(t0, t0 + 250000U, 100U));
    CHECK(!bench_safety_tx_backstop_fired(t0, t0 + 249999U, 100U));
}

/* ---- IWDG prescaler math ------------------------------------------------------ */

static void test_iwdg_timeout_ms(void)
{
    /* Minimum window: PR=0 (/4), reload=0 -> 1 code tick. */
    CHECK(bench_safety_iwdg_timeout_ms(0, 0, 40000) == 1U);

    /* Maximum: PR=6 (/256), reload=4095 -> ceil(4096*256*1000/40000) = 26215. */
    CHECK(bench_safety_iwdg_timeout_ms(6, 4095, 40000) == 26215U);

    /* Divider sanity: PR=1 is /8. */
    CHECK(bench_safety_iwdg_timeout_ms(1, 0, 40000) == 1U);       /* 0.1 ms -> 1 */
    CHECK(bench_safety_iwdg_timeout_ms(1, 3999, 40000) == 800U);  /* 4000*8/40000 */
}

static void test_iwdg_bench_window_2_to_4_s(void)
{
    /* The chosen bench config: PR=4 (/64), reload=1874.
     * F103 LSI is only specified 30-60 kHz (typ. 40 kHz): the window must
     * stay inside the task spec 2-4 s across that whole spread. */
    CHECK(BENCH_IWDG_PR_REG == 4U);
    CHECK(BENCH_IWDG_RELOAD == 1874U);

    CHECK(bench_safety_iwdg_timeout_ms(BENCH_IWDG_PR_REG, BENCH_IWDG_RELOAD,
                                       40000) == 3000U); /* nominal 3.000 s */
    CHECK(bench_safety_iwdg_timeout_ms(BENCH_IWDG_PR_REG, BENCH_IWDG_RELOAD,
                                       60000) == 2000U); /* fastest LSI */
    CHECK(bench_safety_iwdg_timeout_ms(BENCH_IWDG_PR_REG, BENCH_IWDG_RELOAD,
                                       30000) == 4000U); /* slowest LSI */
}

int main(void)
{
    test_lora_airtime_exact();
    test_lora_airtime_monotonic();
    test_flrc_airtime_exact();
    test_tx_timeout_bounds();
    test_tx_timeout_never_overflows_driver_convert();
    test_backstop_window();
    test_backstop_fired();
    test_iwdg_timeout_ms();
    test_iwdg_bench_window_2_to_4_s();

    if (failures == 0)
        printf("test_bench_safety: ALL PASS\n");
    else
        printf("test_bench_safety: %d FAILURE(S)\n", failures);
    return failures;
}
