/* Golden PRBS + payload vectors — BENCH-CONSOLE-SPEC §4 (HARM-T5 RED phase).
 * Vendors MUST mirror prbs.c; these vectors are normative. */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "prbs.h"
#include "bench_payload.h"

static int fails = 0;
#define CHECK(cond, msg) do { if (!(cond)) { printf("FAIL: %s\n", msg); fails++; } } while (0)

int main(void)
{
    /* Spec golden table: seed folds the seq LSB — seq=0 and seq=1 share the
     * fill. First 8 PRBS fill bytes for any seq: DD D8 CC D2 AA EF FE 60. */
    static const uint8_t golden8[8] = {0xDD, 0xD8, 0xCC, 0xD2, 0xAA, 0xEF, 0xFE, 0x60};

    uint8_t buf[64];

    prbs15_fill(buf, 8, 0);   /* seq 0 */
    CHECK(memcmp(buf, golden8, 8) == 0, "prbs15_fill seq=0 first 8 bytes");

    prbs15_fill(buf, 8, 1);   /* seq 1 — identical fill (seed folds seq LSB) */
    CHECK(memcmp(buf, golden8, 8) == 0, "prbs15_fill seq=1 identical to seq=0");

    /* Determinism: same seq, same stream. */
    uint8_t a[32], b[32];
    prbs15_fill(a, 32, 7);
    prbs15_fill(b, 32, 7);
    CHECK(memcmp(a, b, 32) == 0, "prbs15_fill deterministic per seq");

    /* Length cap: fill never writes beyond n. */
    memset(b, 0xA5, sizeof(b));
    prbs15_fill(b, 4, 9);
    CHECK(b[4] == 0xA5, "prbs15_fill respects n");

    /* bench_payload_build: BE header + PRBS fill; seq round-trip. */
    uint8_t p[32];
    bench_payload_build(p, 32, 0);
    CHECK(p[0] == 0 && p[1] == 0 && p[2] == 0 && p[3] == 0, "payload seq=0 header");
    CHECK(memcmp(p + 4, golden8, 8) == 0, "payload seq=0 fill == golden8");
    bench_payload_build(p, 32, 1);
    CHECK(p[3] == 1, "payload seq=1 header LSB");
    CHECK(memcmp(p + 4, golden8, 8) == 0, "payload seq=1 fill == golden8");
    CHECK(bench_payload_seq(p) == 1, "payload_seq round-trip");

    /* Verify: clean payload → 0 errors; corrupted byte → bit errors counted. */
    uint16_t bad = 0xFFFF;
    CHECK(bench_payload_verify(p, 32, 1, &bad) == 0 && bad == 0, "verify clean payload");
    p[10] ^= 0x0F;
    uint16_t bit_err = bench_payload_verify(p, 32, 1, &bad);
    CHECK(bit_err == 4 && bad == 1, "verify corrupted byte (4 bit errors, 1 bad byte)");

    if (fails == 0) { printf("test_prbs: PASS\n"); return 0; }
    printf("test_prbs: %d FAILURES\n", fails);
    return 1;
}
