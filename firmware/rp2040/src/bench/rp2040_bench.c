/**
 * @file    rp2040_bench.c
 * @brief   TDD RED STUB — RP2040BENCH console core (HARM-T5).
 *
 * Zero-logic compilable bodies so the host tests exercise REAL assertion
 * failures (not link errors) before the implementation lands. The GREEN
 * commit replaces every body; the seam contract (rp2040_bench.h) is frozen.
 *
 * RED policy (e80-bench-tdd-workflow): no stub returns a NULL string; every
 * entry point is present so the test binary links and each CHECK fails on
 * value mismatch only.
 */

#include "rp2040_bench.h"

#include <string.h>

void bench_rp2040_init(const bench_io_t* io, const char* fw_sha7)
{
    (void)io;
    (void)fw_sha7;
}

void bench_rp2040_feed_line(const char* line)
{
    (void)line;
}

void bench_rp2040_poll(void)
{
}

void bench_rp2040_rx_event(const uint8_t* payload, uint16_t len,
                           int16_t rssi_half_dbm, int8_t snr_qdb, bool crc_ok)
{
    (void)payload; (void)len; (void)rssi_half_dbm; (void)snr_qdb; (void)crc_ok;
}

bool bench_rp2040_selftest_golden(void)
{
    return false; /* RED: golden self-test fails */
}

const bench_cfg_t* bench_rp2040_cfg(void)
{
    static bench_cfg_t zero;
    memset(&zero, 0, sizeof zero);
    return &zero;
}

bool bench_rp2040_role_is_rx(void)
{
    return false;
}

uint16_t bench_rp2040_rx_len(void)
{
    return 0;
}

bool bench_rp2040_binary_active(void)
{
    return false;
}
