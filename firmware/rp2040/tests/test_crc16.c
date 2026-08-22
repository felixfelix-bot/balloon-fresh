/* Golden CRC-16/CCITT-FALSE vectors — BENCH-CONSOLE-SPEC §5 (HARM-T5 RED).
 * Shared with tools/test_crc16_golden.py; MUST pass on-target before the
 * board is called protocol-compliant. */
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include "buffer.h"

static int fails = 0;
#define CHECK(cond, msg) do { if (!(cond)) { printf("FAIL: %s\n", msg); fails++; } } while (0)

int main(void)
{
    /* "123456789" -> 0x29B1 */
    CHECK(crc16_ccitt_false((const uint8_t*)"123456789", 9) == 0x29B1, "\"123456789\" -> 0x29B1");

    /* 64 x 0x00 -> 0xD6DA */
    uint8_t z[64];
    memset(z, 0, sizeof(z));
    CHECK(crc16_ccitt_false(z, 64) == 0xD6DA, "64 x 0x00 -> 0xD6DA");

    /* 4096 x (i % 256) -> 0x0F69 */
    static uint8_t big[4096];
    for (uint32_t i = 0; i < 4096; i++) big[i] = (uint8_t)(i % 256);
    CHECK(crc16_ccitt_false(big, 4096) == 0x0F69, "4096 x (i%256) -> 0x0F69");

    /* Spec §4 pcrc16 golden: 32-byte payload (seq header + 28 fill). */
    uint8_t p[32];
    extern void bench_payload_build(uint8_t*, uint32_t, uint32_t);
    bench_payload_build(p, 32, 0);
    CHECK(crc16_ccitt_false(p, 32) == 0x997E, "32B payload seq=0 -> pcrc16 0x997E");
    bench_payload_build(p, 32, 1);
    CHECK(crc16_ccitt_false(p, 32) == 0x6998, "32B payload seq=1 -> pcrc16 0x6998");

    if (fails == 0) { printf("test_crc16: PASS\n"); return 0; }
    printf("test_crc16: %d FAILURES\n", fails);
    return 1;
}
