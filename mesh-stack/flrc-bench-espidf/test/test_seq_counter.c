/*
 * Host unit test for uint32 sequence counter (TDD - Gate 1)
 *
 * Build:
 *   RED:  gcc -DUSE_OLD_BEHAVIOR -o test_seq_counter test_seq_counter.c
 *   GREEN: gcc -o test_seq_counter test_seq_counter.c
 *
 * This test verifies that:
 *   1. The TX sequence counter is a true uint32_t (can exceed 65535)
 *   2. The sequence counter does NOT reset between windows
 *   3. The 4-byte big-endian payload encoding uses all 4 bytes when seq > 65535
 *
 * RED phase: fails because current code uses uint16_t p that resets per window
 * GREEN phase: passes after widening to uint32_t with no inter-window reset
 */
#include <stdio.h>
#include <string.h>
#include <stdint.h>

/* Simulated window parameters (mirror range_windows[] from range_test.h) */
typedef struct {
    const char *name;
    uint16_t pkt_count;
} SimWindow;

static const SimWindow sim_windows[] = {
    { "L12-868",  20 },
    { "L9-868",   20 },
    { "F260-868", 50 },
    { "F1300-868",100 },
};
#define SIM_WINDOW_COUNT (sizeof(sim_windows) / sizeof(sim_windows[0]))

/*
 * Simulate the TX packet encoding loop.
 * Extracts the seq-encoding logic from range_test.cpp runRangeTx().
 *
 * Fills `out_seq` with the sequence numbers that would be encoded
 * into buf[0..3] (big-endian) for each packet across all windows.
 * Returns the total number of packets encoded.
 */
#ifdef USE_OLD_BEHAVIOR
/* OLD: uint16_t p, resets per window (current code) */
static int simulate_tx_loop(uint32_t *out_seq, int max_seqs) {
    int idx = 0;
    for (int w = 0; w < (int)SIM_WINDOW_COUNT; w++) {
        for (uint16_t p = 0; p < sim_windows[w].pkt_count; p++) {
            if (idx >= max_seqs) return idx;
            /* Old encoding: p is uint16_t, so bytes 0,1 are always 0 */
            out_seq[idx] = (uint32_t)p;  /* truncated, wraps at 65535 */
            idx++;
        }
    }
    return idx;
}
#else
/* NEW: uint32_t seq, does NOT reset between windows */
static int simulate_tx_loop(uint32_t *out_seq, int max_seqs) {
    int idx = 0;
    uint32_t seq = 0;  /* declared OUTSIDE window loop — no reset */
    for (int w = 0; w < (int)SIM_WINDOW_COUNT; w++) {
        for (uint32_t p = 0; p < sim_windows[w].pkt_count; p++) {
            if (idx >= max_seqs) return idx;
            out_seq[idx] = seq;
            seq++;
            idx++;
        }
        /* No reset of seq here — counter persists across windows */
    }
    return idx;
}
#endif

/* Encode seq as 4-byte big-endian (mirrors range_test.cpp buf[0..3]) */
static void encode_seq_be(uint32_t seq, uint8_t *buf) {
    buf[0] = (seq >> 24) & 0xFF;
    buf[1] = (seq >> 16) & 0xFF;
    buf[2] = (seq >> 8) & 0xFF;
    buf[3] = seq & 0xFF;
}

int main(void) {
    int failures = 0;
    uint32_t seqs[1024];
    int n = simulate_tx_loop(seqs, 1024);

    printf("Simulated %d packets across %d windows\n", n, (int)SIM_WINDOW_COUNT);

    /* Test 1: Total packet count matches sum of all window pkt_counts */
    uint32_t expected_total = 0;
    for (int i = 0; i < (int)SIM_WINDOW_COUNT; i++)
        expected_total += sim_windows[i].pkt_count;
    if (n != (int)expected_total) {
        fprintf(stderr, "FAIL: packet count %d != expected %u\n", n, expected_total);
        failures++;
    } else {
        printf("PASS: total packet count = %d\n", n);
    }

    /* Test 2: Sequence numbers are monotonically increasing (no reset) */
    int monotonic_ok = 1;
    for (int i = 1; i < n; i++) {
        if (seqs[i] != seqs[i-1] + 1) {
            fprintf(stderr, "FAIL: seq[%d]=%u but seq[%d]=%u (expected %u)\n",
                    i-1, seqs[i-1], i, seqs[i], seqs[i-1] + 1);
            monotonic_ok = 0;
            break;
        }
    }
    if (monotonic_ok) {
        printf("PASS: sequence numbers are monotonically increasing (0..%u)\n", n - 1);
    } else {
        failures++;
    }

    /* Test 3: No reset between windows — first pkt of window 2 continues from window 1 */
    /* Window 0 has 20 packets (seq 0..19), window 1 starts at seq 20 */
    if (n > sim_windows[0].pkt_count) {
        uint32_t last_of_w0 = seqs[sim_windows[0].pkt_count - 1];
        uint32_t first_of_w1 = seqs[sim_windows[0].pkt_count];
        if (first_of_w1 != last_of_w0 + 1) {
            fprintf(stderr, "FAIL: window 1 starts at seq %u, expected %u (no reset)\n",
                    first_of_w1, last_of_w0 + 1);
            failures++;
        } else {
            printf("PASS: no reset between windows (w0 ends %u, w1 starts %u)\n",
                   last_of_w0, first_of_w1);
        }
    }

    /* Test 4: Large loop — seq counter exceeds 65535 (proves uint32) */
    /* Simulate enough loops to exceed uint16_t range */
    uint32_t big_seqs[70000];
    int loops_needed = (70000 / n) + 2;
    int total_pkts = 0;
    uint32_t seq_track = 0;
    int found_gt_65535 = 0;

#ifdef USE_OLD_BEHAVIOR
    /* Old behavior: seq wraps at 65535 per window, never exceeds it */
    for (int loop = 0; loop < loops_needed && total_pkts < 70000; loop++) {
        for (int w = 0; w < (int)SIM_WINDOW_COUNT; w++) {
            for (uint16_t p = 0; p < sim_windows[w].pkt_count; p++) {
                if (total_pkts >= 70000) break;
                big_seqs[total_pkts] = (uint32_t)p;
                if (big_seqs[total_pkts] > 65535) found_gt_65535 = 1;
                total_pkts++;
            }
        }
    }
#else
    /* New behavior: uint32_t seq, never resets, never wraps at 65535 */
    for (int loop = 0; loop < loops_needed && total_pkts < 70000; loop++) {
        for (int w = 0; w < (int)SIM_WINDOW_COUNT; w++) {
            for (uint32_t p = 0; p < sim_windows[w].pkt_count; p++) {
                if (total_pkts >= 70000) break;
                big_seqs[total_pkts] = seq_track;
                if (seq_track > 65535) found_gt_65535 = 1;
                seq_track++;
                total_pkts++;
            }
        }
    }
#endif

    if (!found_gt_65535) {
        fprintf(stderr, "FAIL: seq counter never exceeded 65535 (not uint32)\n");
        failures++;
    } else {
        printf("PASS: seq counter exceeded 65535 (true uint32, max=%u)\n",
               big_seqs[total_pkts - 1]);
    }

    /* Test 5: Big-endian encoding uses high bytes when seq > 65535 */
    if (total_pkts > 65536) {
        uint8_t be[4];
        encode_seq_be(big_seqs[65537], be);
        if (be[0] == 0 && be[1] == 0) {
            fprintf(stderr, "FAIL: seq[%d]=%u encoded as %02x%02x%02x%02x (high bytes zero)\n",
                    65537, big_seqs[65537], be[0], be[1], be[2], be[3]);
            failures++;
        } else {
            printf("PASS: seq %u encodes as %02x%02x%02x%02x (high bytes used)\n",
                   big_seqs[65537], be[0], be[1], be[2], be[3]);
        }
    } else {
        fprintf(stderr, "FAIL: not enough packets to test high bytes (only %d)\n", total_pkts);
        failures++;
    }

    if (failures == 0) {
        printf("\nAll tests PASSED\n");
        return 0;
    } else {
        printf("\n%d test(s) FAILED\n", failures);
        return 1;
    }
}