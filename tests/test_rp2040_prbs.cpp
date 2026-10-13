// test_rp2040_prbs.cpp — Host-compiled PRBS-15 tests for RP2040 port
//
// Verifies that the RP2040 prbs15_fill()/prbs15_verify() match:
//   1. The Python reference known-vector (seed=1, 16 bytes)
//   2. Zero bit errors when fill/verify match
//   3. Exact bit-error counting for corrupted payloads
//   4. Deterministic output (same seed, same pattern)
//   5. Different seeds produce different patterns
//
// Compile + run: cd tests && g++ -std=c++17 -O0 -g -Wall -I../firmware/rp2040/src
//   test_rp2040_prbs.cpp ../firmware/rp2040/src/prbs.cpp -o /tmp/test_rp2040_prbs && /tmp/test_rp2040_prbs
//
// Or via pytest:
//   pytest tests/test_c_host.py::TestRp2040PRBS -v

#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cassert>
#include "prbs.h"

// Known output of prbs15_fill(16, seed=1) — matches test_prbs15_cross_platform.py
static const uint8_t KNOWN_SEED_1[16] = {
    0xDD, 0xD8, 0xCC, 0xD2, 0xAA, 0xEF, 0xFE, 0x60,
    0x05, 0x40, 0x1F, 0x80, 0x41, 0x01, 0x86, 0x05,
};

static void test_known_vector(void)
{
    printf("TEST 1: prbs15_fill(16, seed=1) matches known vector... ");
    uint8_t buf[16];
    prbs15_fill(buf, sizeof(buf), 1);
    assert(memcmp(buf, KNOWN_SEED_1, sizeof(KNOWN_SEED_1)) == 0);
    printf("PASS\n");
}

static void test_verify_clean(void)
{
    printf("TEST 2: prbs15_verify returns 0 errors for clean payload... ");
    uint8_t buf[32];
    prbs15_fill(buf, sizeof(buf), 42);
    uint16_t bytes_bad;
    uint16_t bit_err = prbs15_verify(buf, sizeof(buf), 42, &bytes_bad);
    assert(bit_err == 0);
    assert(bytes_bad == 0);
    printf("PASS\n");
}

static void test_verify_null_bytes_bad(void)
{
    printf("TEST 3: prbs15_verify handles null out_bytes_bad... ");
    uint8_t buf[16];
    prbs15_fill(buf, sizeof(buf), 7);
    uint16_t bit_err = prbs15_verify(buf, sizeof(buf), 7, nullptr);
    assert(bit_err == 0);
    printf("PASS\n");
}

static void test_verify_one_bit_error(void)
{
    printf("TEST 4: prbs15_verify counts 1 bit error / 1 byte bad... ");
    uint8_t buf[32];
    prbs15_fill(buf, sizeof(buf), 99);
    buf[10] ^= 0x40;  // flip one bit in byte 10
    uint16_t bytes_bad;
    uint16_t bit_err = prbs15_verify(buf, sizeof(buf), 99, &bytes_bad);
    assert(bit_err == 1);
    assert(bytes_bad == 1);
    printf("PASS\n");
}

static void test_verify_multiple_errors(void)
{
    printf("TEST 5: prbs15_verify counts multiple errors correctly... ");
    uint8_t buf[32];
    prbs15_fill(buf, sizeof(buf), 55);
    buf[5] ^= 0xFF;   // 8 bit errors in byte 5
    buf[12] ^= 0x01;  // 1 bit error in byte 12
    uint16_t bytes_bad;
    uint16_t bit_err = prbs15_verify(buf, sizeof(buf), 55, &bytes_bad);
    assert(bit_err == 9);   // 8 + 1
    assert(bytes_bad == 2);
    printf("PASS\n");
}

static void test_reproducible(void)
{
    printf("TEST 6: same seed produces identical output... ");
    uint8_t a[64], b[64];
    prbs15_fill(a, sizeof(a), 1234);
    prbs15_fill(b, sizeof(b), 1234);
    assert(memcmp(a, b, sizeof(a)) == 0);
    printf("PASS\n");
}

static void test_different_seeds(void)
{
    printf("TEST 7: different seeds produce different patterns... ");
    uint8_t a[64], b[64];
    prbs15_fill(a, sizeof(a), 1);
    prbs15_fill(b, sizeof(b), 2);
    assert(memcmp(a, b, sizeof(a)) != 0);
    printf("PASS\n");
}

static void test_fill_large(void)
{
    printf("TEST 8: prbs15_fill works for large buffer (1024 bytes)... ");
    uint8_t buf[1024];
    prbs15_fill(buf, sizeof(buf), 777);
    // Verify it doesn't crash, then verify it produces consistent results
    uint16_t bytes_bad;
    uint16_t bit_err = prbs15_verify(buf, sizeof(buf), 777, &bytes_bad);
    assert(bit_err == 0);
    assert(bytes_bad == 0);
    printf("PASS\n");
}

int main(void)
{
    printf("\n=== RP2040 PRBS-15 Tests ===\n\n");

    test_known_vector();
    test_verify_clean();
    test_verify_null_bytes_bad();
    test_verify_one_bit_error();
    test_verify_multiple_errors();
    test_reproducible();
    test_different_seeds();
    test_fill_large();

    printf("\n=== Results: 8/8 passed ===\n");
    return 0;
}