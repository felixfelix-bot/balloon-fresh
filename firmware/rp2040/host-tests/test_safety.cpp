/**
 * @file    test_safety.cpp
 * @brief   Host unit tests: TX-hang watchdog math (chip TX timeout, superloop
 *          backstop), SDK watchdog budget, EU-band check, PA-cap check.
 *
 * Ported from E80 tests/test_bench_safety.c with RP2040-specific additions:
 *   - wdt_budget_ms: min(requested, 8000) — RP2040 SDK caps at 8388 ms
 *   - freq_in_eu_band: 863_000_000..870_000_000
 *   - pa_allowed: LF cap +10 dBm indoor, +22 dBm outdoor (unlocked)
 *
 * Key B3 test vector: SF12 BW125 LEN=255 airtime ~9s.
 *   wdt budget MUST be 8000 not 18092 (defense-1 chip timeout covers the
 *   packet; defense-2 wdt catches superloop wedge only).
 *
 * Port provenance: ~/repos/balloon-e80bench/firmware/e80-stm32-bench/tests/test_bench_safety.c
 */

#include "flrc_range_host_safety.h"

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

    /* Bench worst case SF12/BW125/255 B: airtime 9,019,392 us -> 9020 ms
     * -> 9020*2+50 = 18,090 ms (under 60s cap). */
    CHECK(bench_safety_tx_timeout_ms(BENCH_MOD_LORA, 12, 125000, 0, 255) ==
          18090U);
}

static void test_tx_timeout_never_overflows_driver_convert(void)
{
    /* Sweep every legal bench config at max LEN and hold the 60 s cap. */
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

/* ---- RP2040 SDK watchdog budget (B3 fix) -------------------------------------- */
/* Defense-2: SDK watchdog_enable(ms) caps at 8388 ms internally; we stay
 * under at 8000 ms. This is a superloop-wedge catcher ONLY — the chip
 * TX timeout (defense-1) covers long packets like SF12 BW125 LEN=255
 * (airtime ~9s). The wdt budget is min(requested, 8000). */

static void test_wdt_budget_basic(void)
{
    /* Requested under cap -> passes through. */
    CHECK(bench_safety_wdt_budget_ms(1000U) == 1000U);
    CHECK(bench_safety_wdt_budget_ms(5000U) == 5000U);
    CHECK(bench_safety_wdt_budget_ms(8000U) == 8000U);

    /* Requested over cap -> clamped to 8000. */
    CHECK(bench_safety_wdt_budget_ms(8001U) == 8000U);
    CHECK(bench_safety_wdt_budget_ms(10000U) == 8000U);
    CHECK(bench_safety_wdt_budget_ms(60000U) == 8000U);
}

static void test_wdt_budget_sf12_vector(void)
{
    /* B3 binding vector: SF12 BW125 LEN=255 airtime ~9s.
     * Chip TX timeout = 18,090 ms (covers the packet — defense-1).
     * WDT budget = min(18090, 8000) = 8000 (NOT 18092).
     * The superloop feeds the wdt between packets; if the superloop
     * wedges, the wdt fires at 8s regardless of airtime. */
    uint32_t airtime_us = bench_safety_lora_airtime_us(12, 125000, 255);
    CHECK(airtime_us == 9019392U); /* ~9.02 s */

    uint32_t chip_to = bench_safety_tx_timeout_ms(BENCH_MOD_LORA, 12, 125000,
                                                   0, 255);
    CHECK(chip_to == 18090U); /* covers the packet */

    /* If someone naively passed chip_to as wdt budget, it would be 18090.
     * The wdt_budget function MUST clamp to 8000. */
    CHECK(bench_safety_wdt_budget_ms(chip_to) == 8000U);
    CHECK(bench_safety_wdt_budget_ms(chip_to) != chip_to);
}

static void test_wdt_budget_zero(void)
{
    /* Edge: requested 0 -> 0 (no watchdog). */
    CHECK(bench_safety_wdt_budget_ms(0U) == 0U);
}

/* ---- EU band check ----------------------------------------------------------- */

static void test_freq_in_eu_band(void)
{
    /* Lower edge inclusive. */
    CHECK(bench_safety_freq_in_eu_band(863000000U) == true);
    /* Upper edge inclusive. */
    CHECK(bench_safety_freq_in_eu_band(870000000U) == true);
    /* Mid-band. */
    CHECK(bench_safety_freq_in_eu_band(868000000U) == true);
    CHECK(bench_safety_freq_in_eu_band(869525000U) == true);

    /* Below band. */
    CHECK(bench_safety_freq_in_eu_band(862999999U) == false);
    CHECK(bench_safety_freq_in_eu_band(433000000U) == false);
    CHECK(bench_safety_freq_in_eu_band(0U) == false);

    /* Above band. */
    CHECK(bench_safety_freq_in_eu_band(870000001U) == false);
    CHECK(bench_safety_freq_in_eu_band(2400000000U) == false);
}

/* ---- PA allowed check -------------------------------------------------------- */
/* LF path cap: +10 dBm indoor (default), +22 dBm outdoor-unlocked.
 * The unlock requires prior `POWER MODE OUTDOOR <pin>` (pin==2026). */

static void test_pa_allowed_indoor(void)
{
    /* Indoor (unlocked=false): -18..+10 dBm allowed. */
    CHECK(bench_safety_pa_allowed(-18, false) == true);
    CHECK(bench_safety_pa_allowed(0, false) == true);
    CHECK(bench_safety_pa_allowed(10, false) == true);

    /* Indoor: >10 dBm rejected. */
    CHECK(bench_safety_pa_allowed(11, false) == false);
    CHECK(bench_safety_pa_allowed(22, false) == false);
    CHECK(bench_safety_pa_allowed(30, false) == false);
}

static void test_pa_allowed_outdoor(void)
{
    /* Outdoor unlocked: -18..+22 dBm allowed. */
    CHECK(bench_safety_pa_allowed(-18, true) == true);
    CHECK(bench_safety_pa_allowed(0, true) == true);
    CHECK(bench_safety_pa_allowed(10, true) == true);
    CHECK(bench_safety_pa_allowed(22, true) == true);

    /* Outdoor: >22 dBm rejected. */
    CHECK(bench_safety_pa_allowed(23, true) == false);
    CHECK(bench_safety_pa_allowed(30, true) == false);
}

static void test_pa_allowed_boundary(void)
{
    /* Exactly at the caps. */
    CHECK(bench_safety_pa_allowed(10, false) == true);  /* indoor cap */
    CHECK(bench_safety_pa_allowed(22, true) == true);   /* outdoor cap */

    /* One above the caps. */
    CHECK(bench_safety_pa_allowed(11, false) == false);
    CHECK(bench_safety_pa_allowed(23, true) == false);

    /* Very negative dBm always allowed (within reason). */
    CHECK(bench_safety_pa_allowed(-50, false) == true);
    CHECK(bench_safety_pa_allowed(-50, true) == true);
}

/* ---- Integration: SF12 packet safety stack ----------------------------------- */

static void test_sf12_full_safety_stack(void)
{
    /* The B3 binding scenario: SF12 BW125 LEN=255.
     * Defense-1: chip TX timeout = 18,090 ms (covers ~9s airtime + margin).
     * Defense-2: wdt budget = 8,000 ms (superloop wedge catcher, fed between pkts).
     * Backstop: (2 * 18090 + 50) * 1000 = 36,230,000 us. */
    uint32_t chip_to = bench_safety_tx_timeout_ms(BENCH_MOD_LORA, 12, 125000,
                                                   0, 255);
    CHECK(chip_to == 18090U);

    uint32_t wdt = bench_safety_wdt_budget_ms(chip_to);
    CHECK(wdt == 8000U);

    uint32_t backstop = bench_safety_tx_backstop_us(chip_to);
    CHECK(backstop == 36230000U);

    /* The backstop MUST be longer than the chip timeout (defense-2 fires
     * only if defense-1 failed AND the superloop is wedged). */
    CHECK(backstop > chip_to * 1000U);

    /* The wdt MUST be shorter than the chip timeout (it's the aggressive
     * superloop catcher, not the packet-covering timeout). */
    CHECK(wdt < chip_to);
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
    test_wdt_budget_basic();
    test_wdt_budget_sf12_vector();
    test_wdt_budget_zero();
    test_freq_in_eu_band();
    test_pa_allowed_indoor();
    test_pa_allowed_outdoor();
    test_pa_allowed_boundary();
    test_sf12_full_safety_stack();

    if (failures == 0)
    {
        printf("test_safety: ALL PASS\n");
        return 0;
    }
    printf("test_safety: %d FAILURES\n", failures);
    return 1;
}