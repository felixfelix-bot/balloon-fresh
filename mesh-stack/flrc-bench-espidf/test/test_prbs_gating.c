/*
 * Host unit test for PRBS-15 mode gating (TDD - Gate 1)
 *
 * Build:
 *   RED:  gcc -DUSE_OLD_BEHAVIOR -I../main -o test_prbs_gating.test \
 *         test_prbs_gating.c ../main/prbs.c
 *   GREEN: gcc -I../main -o test_prbs_gating.test \
 *         test_prbs_gating.c ../main/prbs.c
 *
 * This test verifies:
 *   1. Throughput/fifo mode (prbs_enabled=false): prbs15_fill NOT called,
 *      payload is zero-padded; prbs15_verify returns 0 errors, 0 bad bytes
 *   2. Range/autonomous mode (prbs_enabled=true): prbs15_fill IS called,
 *      payload has PRBS content; prbs15_verify detects bit errors
 *   3. Toggle: setting prbs_enabled via ON/OFF changes behavior
 */

#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

#include "prbs.h"

/* ================================================================
 * Simulated gating logic (mirrors bench_main.cpp / range_test.cpp)
 * ================================================================ */

static bool prbs_enabled = false;   /* DEFAULT OFF for throughput/fifo modes */

static void set_prbs_enabled(bool on) {
    prbs_enabled = on;
}

/*
 * Simulated TX: fill a packet buffer similar to bench_main.cpp.
 * Sequence number goes in buf[0..3] big-endian.
 * If prbs_enabled, fill buf[4..len-1] with PRBS-15 seeded by seq.
 * If NOT enabled, zero the payload (no PRBS CPU cost).
 */
static void sim_tx_fill(uint8_t *buf, size_t len, uint32_t seq) {
    buf[0] = (seq >> 24) & 0xFF;
    buf[1] = (seq >> 16) & 0xFF;
    buf[2] = (seq >> 8) & 0xFF;
    buf[3] = seq & 0xFF;
#ifdef USE_OLD_BEHAVIOR
    /* OLD: always call prbs15_fill */
    if (len > 4) {
        prbs15_fill(buf + 4, len - 4, seq);
    }
#else
    /* NEW: gate on prbs_enabled */
    if (prbs_enabled && len > 4) {
        prbs15_fill(buf + 4, len - 4, seq);
    } else if (len > 4) {
        memset(buf + 4, 0, len - 4);
    }
#endif
}

/*
 * Simulated RX verify: check payload against PRBS-15.
 * If prbs_enabled, call prbs15_verify.
 * If NOT enabled, return (0, 0) — no CPU spent on PRBS verification.
 */
static void sim_rx_verify(const uint8_t *buf, size_t len, uint32_t seq,
                           uint16_t *out_bit_err, uint16_t *out_bytes_bad) {
#ifdef USE_OLD_BEHAVIOR
    /* OLD: always call prbs15_verify */
    *out_bit_err = prbs15_verify(buf + 4, len - 4, seq, out_bytes_bad);
#else
    /* NEW: gate on prbs_enabled */
    if (prbs_enabled && len > 4) {
        *out_bit_err = prbs15_verify(buf + 4, len - 4, seq, out_bytes_bad);
    } else {
        *out_bit_err = 0;
        if (out_bytes_bad) *out_bytes_bad = 0;
    }
#endif
}

/* ================================================================
 * Test helpers
 * ================================================================ */

static int failures = 0;
#define TEST(cond, msg) do { \
    if (!(cond)) { \
        fprintf(stderr, "FAIL: %s\n", msg); \
        failures++; \
    } else { \
        printf("PASS: %s\n", msg); \
    } \
} while(0)

/* Check all bytes in buf[offset..offset+len-1] are zero */
static int is_zeros(const uint8_t *buf, size_t offset, size_t n) {
    for (size_t i = 0; i < n; i++) {
        if (buf[offset + i] != 0) return 0;
    }
    return 1;
}

/* Check at least one byte in buf[offset..offset+len-1] is non-zero */
static int has_nonzero(const uint8_t *buf, size_t offset, size_t n) {
    for (size_t i = 0; i < n; i++) {
        if (buf[offset + i] != 0) return 1;
    }
    return 0;
}

/* ================================================================
 * Tests
 * ================================================================ */

static void test_tx_throughput_mode(void) {
    /* prbs_enabled = false (default for throughput/fifo) */
    uint8_t buf[50];
    memset(buf, 0xFF, sizeof(buf));  /* pre-fill with garbage */

    sim_tx_fill(buf, sizeof(buf), 42);

    /* Seq header OK? */
    TEST(buf[0] == 0 && buf[1] == 0 && buf[2] == 0 && buf[3] == 42,
         "TX throughput: seq header correct");

    /* Payload should be ZEROS (not PRBS) */
    TEST(is_zeros(buf, 4, sizeof(buf) - 4),
         "TX throughput: payload is zero (PRBS not called)");
}

static void test_tx_range_mode(void) {
    /* prbs_enabled = true (range/autonomous mode) */
    set_prbs_enabled(true);
    uint8_t buf[50];
    memset(buf, 0, sizeof(buf));

    sim_tx_fill(buf, sizeof(buf), 999);

    /* Payload should be non-zero (PRBS was filled) */
    TEST(has_nonzero(buf, 4, sizeof(buf) - 4),
         "TX range: payload has PRBS content (non-zero)");
}

static void test_rx_throughput_mode(void) {
    set_prbs_enabled(false);

    /* Build a corrupted buffer for verification */
    uint8_t buf[50];
    memset(buf, 0xFF, sizeof(buf));  /* garbage */
    buf[0] = 0; buf[1] = 0; buf[2] = 0; buf[3] = 7;  /* seq = 7 */

    uint16_t bit_err = 999;
    uint16_t bytes_bad = 999;
    sim_rx_verify(buf, sizeof(buf), 7, &bit_err, &bytes_bad);

    /* Should report zero errors (PRBS not verified) */
    TEST(bit_err == 0, "RX throughput: bit_err=0 (PRBS not verified)");
    TEST(bytes_bad == 0, "RX throughput: bytes_bad=0");
}

static void test_rx_range_mode(void) {
    uint8_t buf[50];

    /* Build a CLEAN PRBS payload with seq=1 */
    set_prbs_enabled(true);
    sim_tx_fill(buf, sizeof(buf), 1);

    /* Verify the clean payload — should see zero errors */
    uint16_t bit_err = 999;
    uint16_t bytes_bad = 999;
    sim_rx_verify(buf, sizeof(buf), 1, &bit_err, &bytes_bad);
    TEST(bit_err == 0, "RX range: clean PRBS payload has 0 bit errors");
    TEST(bytes_bad == 0, "RX range: clean PRBS payload has 0 bad bytes");

    /* Now corrupt one byte */
    buf[20] ^= 0xFF;  /* flip all bits in byte */
    bit_err = 999;
    bytes_bad = 999;
    sim_rx_verify(buf, sizeof(buf), 1, &bit_err, &bytes_bad);
    TEST(bit_err > 0, "RX range: corrupted byte detected (bit_err > 0)");
    TEST(bytes_bad == 1, "RX range: corrupted byte counted as 1 bad byte");
}

static void test_toggle(void) {
    /* Start with OFF */
    set_prbs_enabled(false);
    uint8_t buf[20];
    memset(buf, 0xFF, sizeof(buf));
    sim_tx_fill(buf, sizeof(buf), 0);
    int off_zeros = is_zeros(buf, 4, sizeof(buf) - 4);

    /* Toggle ON */
    set_prbs_enabled(true);
    memset(buf, 0, sizeof(buf));
    sim_tx_fill(buf, sizeof(buf), 0);
    int on_prbs = has_nonzero(buf, 4, sizeof(buf) - 4);

    /* Toggle OFF again */
    set_prbs_enabled(false);
    memset(buf, 0xFF, sizeof(buf));
    sim_tx_fill(buf, sizeof(buf), 0);
    int off_again = is_zeros(buf, 4, sizeof(buf) - 4);

    TEST(off_zeros && on_prbs && off_again,
         "Toggle: PRBS ON produces payload, OFF produces zeros (3-state consistent)");
}

int main(void) {
    printf("=== PRBS-15 Mode Gating Tests ===\n\n");
    printf("Default: prbs_enabled=%s\n\n",
#ifdef USE_OLD_BEHAVIOR
           "(always ON — OLD behavior)"
#else
           "false (NEW behavior)"
#endif
    );

    test_tx_throughput_mode();
    test_tx_range_mode();
    test_rx_throughput_mode();
    test_rx_range_mode();
    test_toggle();

    printf("\n");
    if (failures == 0) {
        printf("All tests PASSED\n");
        return 0;
    } else {
        printf("%d test(s) FAILED\n", failures);
        return 1;
    }
}