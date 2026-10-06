/**
 * @file    flrc_range_host_safety.cpp
 * @brief   TX-hang watchdog math, EU-band check, PA-cap check (portable).
 *
 * Pure TU — no Arduino includes, no RP2040 SDK calls, compilable by host g++
 * for unit testing.  All functions are pure; integer math only, every
 * division rounds up (an upper bound that must never fire on a legal
 * packet, but must fire on a hang).
 *
 * Port provenance: ~/repos/balloon-e80bench/firmware/e80-stm32-bench/src/bench_safety.c
 * Changes vs E80: see flrc_range_host_safety.h header comment.
 */

#include "flrc_range_host_safety.h"

/* ---- helpers ---------------------------------------------------------------- */

static uint32_t ceil_div_u32(uint32_t num, uint32_t den)
{
    return (num + den - 1U) / den;
}

/* ---- Defense 1: LR2021 chip TX timeout ---------------------------------------- */

uint32_t bench_safety_lora_airtime_us(uint8_t sf, uint32_t bw_hz, uint16_t len)
{
    /* Bench LoRa modem config: CR4/5 (CR index 1), explicit header, CRC16 on,
     * 8-symbol preamble. AN1200.24 payload symbol count:
     *   n = 8 + ceil((8*PL - 4*SF + 28 + 16*CRC) / (4*(SF - 2*DE))) * (CR+4)
     * computed for both LDRO variants (DE=0/1), keeping the LONGER one. */
    const uint32_t num_bits = 8U * (uint32_t)len - 4U * (uint32_t)sf + 28U + 16U;
    uint32_t         n_symbols;

    if (num_bits == 0U)
    {
        n_symbols = 8U; /* preamble-only + 8 header symbols, no payload block */
    }
    else
    {
        uint32_t de0 = ceil_div_u32(num_bits, 4U * (uint32_t)sf);
        uint32_t de1 = ceil_div_u32(num_bits, 4U * ((uint32_t)sf - 2U));
        uint32_t blocks = (de0 > de1) ? de0 : de1; /* LDRO-worst */

        n_symbols = 8U + blocks * 5U; /* (CR index 1 + 4) coded symbols/block */
    }

    /* Total in quarter-symbols: preamble 8*4 + SFD 4.25*4 + payload N*4. */
    {
        uint32_t quarter_symbols = 8U * 4U + 17U + n_symbols * 4U;
        uint32_t tsym_us         = ceil_div_u32(((uint32_t)1U << sf) * 1000000U,
                                                bw_hz);

        return ceil_div_u32(quarter_symbols * tsym_us, 4U);
    }
}

uint32_t bench_safety_flrc_airtime_us(uint32_t br_bps, uint16_t len)
{
    /* Bench FLRC packet config: 32-bit preamble, 4-byte syncword, FIX_LEN
     * payload, CRC16 — all CR3/4-coded on air (x4/3).
     * 64-bit intermediate: worst legal case coded=5558 bits, 5558 * 1e6
     * overflows uint32. */
    uint32_t bits  = 32U + 32U + 8U * (uint32_t)len + 16U;
    uint64_t coded = (uint64_t)ceil_div_u32(bits * 4U, 3U);

    return (uint32_t)((coded * 1000000ULL + br_bps - 1U) / br_bps);
}

uint32_t bench_safety_tx_timeout_ms(bench_mod_t mod, uint8_t sf, uint32_t bw_hz,
                                    uint32_t br_bps, uint16_t len)
{
    uint32_t airtime_us;
    uint32_t ms;

    if (mod == BENCH_MOD_LORA)
        airtime_us = bench_safety_lora_airtime_us(sf, bw_hz, len);
    else
        airtime_us = bench_safety_flrc_airtime_us(br_bps, len);

    ms = ceil_div_u32(airtime_us, 1000U) * 2U + 50U;
    if (ms < 100U)
        ms = 100U;
    if (ms > 60000U)
        ms = 60000U;
    return ms;
}

/* ---- Defense 2: SDK watchdog budget ----------------------------------------- */

uint32_t bench_safety_wdt_budget_ms(uint32_t requested_ms)
{
    /* RP2040 SDK watchdog_enable caps at 8388 ms; we stay under at 8000.
     * This is a superloop-wedge catcher ONLY — fed between packets.
     * Long airtimes (SF12 ~9s) are covered by defense-1 (chip TX timeout). */
    if (requested_ms > BENCH_WDT_BUDGET_CAP_MS)
        return BENCH_WDT_BUDGET_CAP_MS;
    return requested_ms;
}

/* ---- Defense 3: superloop backstop --------------------------------------------- */

uint32_t bench_safety_tx_backstop_us(uint32_t tx_timeout_ms)
{
    return (tx_timeout_ms * 2U + 50U) * 1000U;
}

bool bench_safety_tx_backstop_fired(uint32_t t_tx_start_us, uint32_t now_us,
                                    uint32_t tx_timeout_ms)
{
    /* Unsigned subtraction handles the micros() wraparound at 2^32. */
    uint32_t elapsed_us = now_us - t_tx_start_us;
    return elapsed_us >= bench_safety_tx_backstop_us(tx_timeout_ms);
}

/* ---- EU SRD band check ----------------------------------------------------- */

bool bench_safety_freq_in_eu_band(uint32_t freq_hz)
{
    return freq_hz >= BENCH_EU_BAND_LO_HZ && freq_hz <= BENCH_EU_BAND_HI_HZ;
}

/* ---- PA power-cap check ---------------------------------------------------- */

bool bench_safety_pa_allowed(int8_t dbm, bool outdoor_unlocked)
{
    /* Protocol rejects < -18 with ERR RANGE; this function checks the
     * upper cap given the unlock state.  Very low dbm is always allowed. */
    int8_t cap = outdoor_unlocked ? BENCH_PA_OUTDOOR_CAP_DBM
                                  : BENCH_PA_INDOOR_CAP_DBM;
    return dbm <= cap;
}