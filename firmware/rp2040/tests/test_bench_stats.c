/* bench_stats unit tests — Wilson CI, PER, kbps, RSSI folding (RED phase). */
#include <stdio.h>
#include <stdint.h>
#include "bench_stats.h"

static int fails = 0;
#define CHECK(cond, msg) do { if (!(cond)) { printf("FAIL: %s\n", msg); fails++; } } while (0)

int main(void)
{
    /* PER: 2 sequenced packets 0..9, 8 received -> lost 2 of 10 = 200000 ppm. */
    bench_stats_t s;
    bench_stats_reset(&s);
    s.rx_first_seq = 0; s.rx_last_seq = 9; s.rx_seq_valid = true; s.rx_ok = 8;
    CHECK(bench_stats_per_ppm(&s) == 200000UL, "per_ppm 8/10 received = 200000 ppm");

    /* No sequence -> 0. */
    bench_stats_reset(&s);
    s.rx_ok = 5;
    CHECK(bench_stats_per_ppm(&s) == 0UL, "per_ppm without valid seq = 0");

    /* Perfect run: per 0. */
    bench_stats_reset(&s);
    s.rx_first_seq = 0; s.rx_last_seq = 4; s.rx_seq_valid = true; s.rx_ok = 5;
    CHECK(bench_stats_per_ppm(&s) == 0UL, "per_ppm perfect run = 0");

    /* Wilson 95% on 100/100 successes: lower bound ~96.4% -> lo_ppm > 955000. */
    uint32_t lo = 0, hi = 0;
    bench_stats_wilson_ppm(100, 100, &lo, &hi);
    CHECK(hi == 1000000UL, "wilson 100/100 upper = 1e6");
    CHECK(lo > 950000UL, "wilson 100/100 lower > 95%");

    /* Wilson on 0 trials -> full-interval no-data answer [0, 1e6]
     * (vendored bench_stats.c: trials==0 -> lo=0, hi=1000000). */
    bench_stats_wilson_ppm(0, 0, &lo, &hi);
    CHECK(lo == 0UL && hi == 1000000UL, "wilson 0/0 = 0..1e6 (no data)");

    /* kbps: 1250 bytes over 1e6 us = 10 kbit/s. */
    CHECK(bench_stats_kbps(1250, 1000000ULL) == 10UL, "kbps 1250B/1s = 10");

    /* RSSI folding: min/max/avg in half-dBm units. note_rssi() only seeds
     * min/max (its first sample early-returns); the core folds the sum
     * itself (E80 bench.c:991), so mirror that here. */
    bench_stats_reset(&s);
    bench_stats_note_rssi(&s, -120);
    bench_stats_note_rssi(&s, -100);
    bench_stats_note_rssi(&s, -110);
    s.rssi_sum_half = -120 + -100 + -110;
    s.rx_ok = 3;
    CHECK(bench_stats_rssi_min_half_dbm(&s) == -120, "rssi min");
    CHECK(bench_stats_rssi_max_half_dbm(&s) == -100, "rssi max");
    CHECK(bench_stats_rssi_avg_half_dbm(&s) == -110, "rssi avg");

    /* Elapsed with wrap. */
    CHECK(bench_stats_elapsed_us(0xFFFFFFF0UL, 0x10UL) == 32UL, "elapsed across 2^32 wrap");

    if (fails == 0) { printf("test_bench_stats: PASS\n"); return 0; }
    printf("test_bench_stats: %d FAILURES\n", fails);
    return 1;
}
