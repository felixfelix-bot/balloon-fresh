/**
 * @file    test_stats.cpp
 * @brief   Host unit tests: PER, Wilson 95% CI, kbps, isqrt, averages.
 *
 * Ported from E80 tests/test_bench_stats.c with added boundary cases per FW-3:
 *   - S==N => per=0, ci as computed (hi must be exactly 1_000_000)
 *   - S=0  => per=1_000_000 (complete loss)
 *   - Boundary N=1, 2, 10, 10000
 *
 * Wilson reference values cross-checked against the standard formula
 * (z = 1.96) with a host-side float oracle in the comments.
 *
 * Port provenance: ~/repos/balloon-e80bench/firmware/e80-stm32-bench/tests/test_bench_stats.c
 */

#include "flrc_range_host_stats.h"

#include <stdio.h>
#include <math.h>
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

/* ---- float oracle for Wilson cross-check (same as E80) ----------------- */
static void wilson_oracle(double S, double N, double* lo, double* hi)
{
    const double z = 1.96, z2 = z * z;
    double p = S / N;
    double center = (p + z2 / (2 * N)) / (1 + z2 / N);
    double half = (z / (1 + z2 / N)) * sqrt(p * (1 - p) / N + z2 / (4 * N * N));
    *lo = center - half;
    *hi = center + half;
}

/* ---- tests (ported from E80, with FW-3 additions marked) --------------- */

static void test_isqrt(void)
{
    CHECK(bench_isqrt64(0) == 0);
    CHECK(bench_isqrt64(1) == 1);
    CHECK(bench_isqrt64(3) == 1);
    CHECK(bench_isqrt64(4) == 2);
    CHECK(bench_isqrt64(999999) == 999);
    CHECK(bench_isqrt64(1000000) == 1000);
    CHECK(bench_isqrt64(0xFFFFFFFFFFFFFFFFULL) == 4294967295U);
    /* dense sweep vs libm */
    for (uint64_t x = 1; x < 100000; x += 7)
    {
        uint32_t r = bench_isqrt64(x);
        CHECK(r <= sqrt((double)x) && r + 1 > sqrt((double)x));
    }
}

static void test_per(void)
{
    bench_stats_t s;

    /* no sequenced packets -> 0 */
    bench_stats_reset(&s);
    CHECK(bench_stats_per_ppm(&s) == 0);

    /* seq 0..999 (expected 1000), 950 ok -> 5% loss = 50000 ppm */
    bench_stats_reset(&s);
    s.rx_seq_valid = true;
    s.rx_first_seq = 0;
    s.rx_last_seq = 999;
    s.rx_ok = 950;
    CHECK(bench_stats_per_ppm(&s) == 50000);

    /* all received -> 0 ppm  (FW-3: S==N => per=0) */
    s.rx_ok = 1000;
    CHECK(bench_stats_per_ppm(&s) == 0);

    /* none received but seq never advanced: expected == 1 -> 0 */
    bench_stats_reset(&s);
    s.rx_seq_valid = true;
    s.rx_first_seq = 42;
    s.rx_last_seq = 42;
    s.rx_ok = 1;
    CHECK(bench_stats_per_ppm(&s) == 0);

    /* gap: first 0, last 9, ok 5 -> 50% = 500000 ppm */
    bench_stats_reset(&s);
    s.rx_seq_valid = true;
    s.rx_first_seq = 0;
    s.rx_last_seq = 9;
    s.rx_ok = 5;
    CHECK(bench_stats_per_ppm(&s) == 500000);

    /* FW-3 addition: S=0 => per=1_000_000 (complete loss, 0 ok out of 10 expected) */
    bench_stats_reset(&s);
    s.rx_seq_valid = true;
    s.rx_first_seq = 0;
    s.rx_last_seq = 9;
    s.rx_ok = 0;
    CHECK(bench_stats_per_ppm(&s) == 1000000);
}

static void test_wilson(void)
{
    uint32_t lo, hi;
    double flo, fhi;

    /* degenerate: 0 trials */
    bench_stats_wilson_ppm(0, 0, &lo, &hi);
    CHECK(lo == 0 && hi == 1000000);

    /* 0/100: success CI [0, ~0.0370] -> ppm [0, 37020] (oracle 37011) */
    bench_stats_wilson_ppm(0, 100, &lo, &hi);
    wilson_oracle(0, 100, &flo, &fhi);
    CHECK(lo == 0);
    CHECK((int64_t)hi >= (int64_t)(flo * 1e6) - 60 && (int64_t)hi <= (int64_t)(fhi * 1e6) + 60);

    /* 100/100: success CI [~0.9638, 1.0]  (FW-3: S==N => hi must be exactly 1_000_000) */
    bench_stats_wilson_ppm(100, 100, &lo, &hi);
    wilson_oracle(100, 100, &flo, &fhi);
    CHECK(hi == 1000000);
    CHECK(lo >= (uint32_t)(flo * 1e6) - 60 && lo <= (uint32_t)(flo * 1e6) + 60);

    /* 950/1000: success CI ~[0.9296, 0.9667] */
    bench_stats_wilson_ppm(950, 1000, &lo, &hi);
    wilson_oracle(950, 1000, &flo, &fhi);
    CHECK(lo >= (uint32_t)(flo * 1e6) - 60 && lo <= (uint32_t)(flo * 1e6) + 60);
    CHECK(hi >= (uint32_t)(fhi * 1e6) - 60 && hi <= (uint32_t)(fhi * 1e6) + 60);

    /* 500/1000: success CI ~[0.4691, 0.5309] */
    bench_stats_wilson_ppm(500, 1000, &lo, &hi);
    wilson_oracle(500, 1000, &flo, &fhi);
    CHECK(lo >= (uint32_t)(flo * 1e6) - 60 && lo <= (uint32_t)(flo * 1e6) + 60);
    CHECK(hi >= (uint32_t)(fhi * 1e6) - 60 && hi <= (uint32_t)(fhi * 1e6) + 60);

    /* monotone sanity: interval must contain the point estimate */
    bench_stats_wilson_ppm(7, 13, &lo, &hi);
    uint32_t phat = 7 * 1000000 / 13;
    CHECK(lo <= phat && phat <= hi);

    /* exact small case: 1/1 -> [0.2076, 1.0] */
    bench_stats_wilson_ppm(1, 1, &lo, &hi);
    wilson_oracle(1, 1, &flo, &fhi);
    CHECK(lo >= (uint32_t)(flo * 1e6) - 60 && lo <= (uint32_t)(flo * 1e6) + 60);
    CHECK(hi == 1000000);

    /* FW-3 boundary: N=2, S=2 => hi exactly 1_000_000, lo as computed */
    bench_stats_wilson_ppm(2, 2, &lo, &hi);
    wilson_oracle(2, 2, &flo, &fhi);
    CHECK(hi == 1000000);
    CHECK(lo >= (uint32_t)(flo * 1e6) - 60 && lo <= (uint32_t)(flo * 1e6) + 60);

    /* FW-3 boundary: N=2, S=1.
     * Small N has larger integer rounding error (~160 ppm vs oracle),
     * so use ±200 tolerance instead of the ±60 used for N>=100. */
    bench_stats_wilson_ppm(1, 2, &lo, &hi);
    wilson_oracle(1, 2, &flo, &fhi);
    CHECK(lo >= (uint32_t)(flo * 1e6) - 200 && lo <= (uint32_t)(flo * 1e6) + 200);
    CHECK(hi >= (uint32_t)(fhi * 1e6) - 200 && hi <= (uint32_t)(fhi * 1e6) + 200);

    /* FW-3 boundary: N=10, S=10 => hi exactly 1_000_000 */
    bench_stats_wilson_ppm(10, 10, &lo, &hi);
    wilson_oracle(10, 10, &flo, &fhi);
    CHECK(hi == 1000000);
    CHECK(lo >= (uint32_t)(flo * 1e6) - 200 && lo <= (uint32_t)(flo * 1e6) + 200);

    /* FW-3 boundary: N=10, S=5 */
    bench_stats_wilson_ppm(5, 10, &lo, &hi);
    wilson_oracle(5, 10, &flo, &fhi);
    CHECK(lo >= (uint32_t)(flo * 1e6) - 200 && lo <= (uint32_t)(flo * 1e6) + 200);
    CHECK(hi >= (uint32_t)(fhi * 1e6) - 200 && hi <= (uint32_t)(fhi * 1e6) + 200);

    /* FW-3 boundary: N=10000, S=10000 => hi exactly 1_000_000 */
    bench_stats_wilson_ppm(10000, 10000, &lo, &hi);
    wilson_oracle(10000, 10000, &flo, &fhi);
    CHECK(hi == 1000000);
    CHECK(lo >= (uint32_t)(flo * 1e6) - 60 && lo <= (uint32_t)(flo * 1e6) + 60);

    /* FW-3 boundary: N=10000, S=0 => lo=0, hi as computed */
    bench_stats_wilson_ppm(0, 10000, &lo, &hi);
    wilson_oracle(0, 10000, &flo, &fhi);
    CHECK(lo == 0);
    CHECK((int64_t)hi >= (int64_t)(flo * 1e6) - 60 && (int64_t)hi <= (int64_t)(fhi * 1e6) + 60);

    /* FW-3 boundary: N=10000, S=9900 */
    bench_stats_wilson_ppm(9900, 10000, &lo, &hi);
    wilson_oracle(9900, 10000, &flo, &fhi);
    CHECK(lo >= (uint32_t)(flo * 1e6) - 60 && lo <= (uint32_t)(flo * 1e6) + 60);
    CHECK(hi >= (uint32_t)(fhi * 1e6) - 60 && hi <= (uint32_t)(fhi * 1e6) + 60);
}

static void test_kbps(void)
{
    /* 255 B x 1000 pkts over 10 s -> 204 kbit/s */
    CHECK(bench_stats_kbps(255000ULL, 10000000ULL) == 204);
    /* 255 B over 3.1 ms -> 255*8000/3100 = 658 kbit/s */
    CHECK(bench_stats_kbps(255ULL, 3100ULL) == 658);
    CHECK(bench_stats_kbps(0, 1000) == 0);
    CHECK(bench_stats_kbps(1000, 0) == 0);
    /* large values must not overflow u32: 1 GB in 1 s = 8e6 kbps */
    CHECK(bench_stats_kbps(1000000000ULL, 1000000ULL) == 8000000U);
}

static void test_elapsed_wrap(void)
{
    /* plain */
    CHECK(bench_stats_elapsed_us(1000, 1100) == 100);
    /* 32-bit wrap: start near max */
    CHECK(bench_stats_elapsed_us(0xFFFFFFF0UL, 0x00000050UL) == 0x60);
}

static void test_averages(void)
{
    bench_stats_t s;
    bench_stats_reset(&s);
    CHECK(bench_stats_rssi_avg_half_dbm(&s) == 0);
    CHECK(bench_stats_snr_avg_cdb(&s) == 0);

    s.rx_ok = 3;
    s.rssi_sum_half = -270; /* -45.0 dBm avg */
    s.snr_sum_qdb = 40;     /* 10 qdb avg = 2.5 dB -> 250 cdB */
    CHECK(bench_stats_rssi_avg_half_dbm(&s) == -90);
    CHECK(bench_stats_snr_avg_cdb(&s) == 333); /* 40*25/3 = 333 */

    /* negative SNR */
    bench_stats_reset(&s);
    s.rx_ok = 2;
    s.snr_sum_qdb = -30; /* -15 qdb avg = -3.75 dB -> -375 cdB */
    CHECK(bench_stats_snr_avg_cdb(&s) == -375);
}

static void test_rssi_minmax(void)
{
    bench_stats_t s;

    /* no packet noted -> getters return 0 (same convention as rssi_avg) */
    bench_stats_reset(&s);
    CHECK(bench_stats_rssi_min_half_dbm(&s) == 0);
    CHECK(bench_stats_rssi_max_half_dbm(&s) == 0);

    /* first packet initializes BOTH trackers (no zero-sentinel bug: a
     * first packet weaker than 0 dBm must not leave max stuck at 0) */
    bench_stats_reset(&s);
    bench_stats_note_rssi(&s, -90); /* -45.0 dBm */
    CHECK(bench_stats_rssi_min_half_dbm(&s) == -90);
    CHECK(bench_stats_rssi_max_half_dbm(&s) == -90);

    /* monotonic updates: new max, new min, in-range sample changes nothing */
    bench_stats_note_rssi(&s, -61);  /* -30.5 dBm -> new max */
    bench_stats_note_rssi(&s, -120); /* -60.0 dBm -> new min */
    bench_stats_note_rssi(&s, -100); /* inside [min,max] -> no change */
    CHECK(bench_stats_rssi_min_half_dbm(&s) == -120);
    CHECK(bench_stats_rssi_max_half_dbm(&s) == -61);

    /* boundary values pass through unclamped: half-dBm -256..+254
     * == -128.0..+127.0 dBm (printable int8 dBm range) */
    bench_stats_reset(&s);
    bench_stats_note_rssi(&s, -256);
    bench_stats_note_rssi(&s, 254);
    CHECK(bench_stats_rssi_min_half_dbm(&s) == -256);
    CHECK(bench_stats_rssi_max_half_dbm(&s) == 254);

    /* out-of-range samples clamp at the getters, not the trackers */
    bench_stats_reset(&s);
    bench_stats_note_rssi(&s, 260);  /* +130.0 dBm: impossible, clamp */
    bench_stats_note_rssi(&s, -400); /* -200.0 dBm: impossible, clamp */
    CHECK(bench_stats_rssi_min_half_dbm(&s) == -256);
    CHECK(bench_stats_rssi_max_half_dbm(&s) == 254);

    /* reset clears validity again */
    bench_stats_reset(&s);
    CHECK(bench_stats_rssi_min_half_dbm(&s) == 0);
    CHECK(bench_stats_rssi_max_half_dbm(&s) == 0);
}

int main(void)
{
    test_isqrt();
    test_per();
    test_wilson();
    test_kbps();
    test_elapsed_wrap();
    test_averages();
    test_rssi_minmax();

    if (failures == 0)
    {
        printf("test_stats: ALL PASS\n");
        return 0;
    }
    printf("test_stats: %d FAILURES\n", failures);
    return 1;
}