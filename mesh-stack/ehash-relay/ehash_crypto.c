/**
 * @file ehash_crypto.c
 * @brief Per-session template encryption (D8).
 *
 * XOR cipher for now (placeholder for AES-128 CTR mode). The relay
 * generates a per-session key and encrypts template payloads before
 * broadcast. Miners receive the decryption key only after paying
 * e-hash (balance > 0). No payment = no key = no decryption (D8).
 *
 * On ESP-IDF: replace ehash_crypto_session_start() to call
 * esp_fill_random() from esp_system.h.
 */

#include "ehash_crypto.h"
#include <string.h>

/* ========================================================================
 *  Per-session key generation
 * ======================================================================== */

/*
 * Simple xorshift32 PRNG — deterministic for host tests, good enough for
 * XOR-key generation. On target, esp_fill_random() should be used.
 */
static uint32_t xorshift32(uint32_t *state) {
    uint32_t x = *state;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    *state = x;
    return x;
}

void ehash_crypto_session_start(uint8_t key[EHASH_CRYPTO_KEY_SIZE], uint32_t seed) {
    /* Avoid all-zero seed (degenerate PRNG state). */
    uint32_t state = seed ? seed : 0xDEADBEEF;

    for (int i = 0; i < EHASH_CRYPTO_KEY_SIZE; i += 4) {
        uint32_t v = xorshift32(&state);
        key[i]     = (uint8_t)(v);
        key[i + 1] = (uint8_t)(v >> 8);
        key[i + 2] = (uint8_t)(v >> 16);
        key[i + 3] = (uint8_t)(v >> 24);
    }

    /* Ensure key is never all-zero (would make XOR a no-op). */
    bool all_zero = true;
    for (int i = 0; i < EHASH_CRYPTO_KEY_SIZE; i++) {
        if (key[i] != 0) { all_zero = false; break; }
    }
    if (all_zero) {
        key[0] = 0x01;
    }
}

/* ========================================================================
 *  XOR encrypt/decrypt (symmetric)
 * ======================================================================== */

void ehash_crypto_xor(uint8_t *data, size_t len, const uint8_t key[EHASH_CRYPTO_KEY_SIZE]) {
    for (size_t i = 0; i < len; i++) {
        data[i] ^= key[i % EHASH_CRYPTO_KEY_SIZE];
    }
}

/* ========================================================================
 *  Key comparison
 * ======================================================================== */

bool ehash_crypto_key_equal(const uint8_t *a, const uint8_t *b) {
    return memcmp(a, b, EHASH_CRYPTO_KEY_SIZE) == 0;
}
