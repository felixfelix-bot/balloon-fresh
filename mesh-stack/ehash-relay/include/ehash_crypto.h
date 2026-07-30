/**
 * @file ehash_crypto.h
 * @brief Per-session template encryption (D8).
 *
 * Generates a per-session AES-128 key on session start. For now, uses XOR
 * (AES-128 to be integrated later). The key gates template delivery:
 * miners with zero e-hash balance get no decryption key (D8).
 */

#ifndef EHASH_CRYPTO_H
#define EHASH_CRYPTO_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/** AES-128 key size (16 bytes). */
#define EHASH_CRYPTO_KEY_SIZE 16

/**
 * @brief Generate a per-session encryption key.
 *
 * Uses a simple PRNG seeded with the session timestamp + station ID.
 * On ESP-IDF, this should use esp_fill_random() — the host version uses
 * a deterministic PRNG for testability.
 *
 * @param key        Output buffer (16 bytes).
 * @param seed       Seed value (e.g. timestamp XOR station_id).
 */
void ehash_crypto_session_start(uint8_t key[EHASH_CRYPTO_KEY_SIZE], uint32_t seed);

/**
 * @brief XOR-encrypt/decrypt a buffer in place (symmetric).
 *
 * XOR is symmetric: encrypt and decrypt are the same operation.
 * The key is cycled for buffers longer than 16 bytes.
 *
 * NOTE: XOR is a placeholder. The real implementation will use AES-128
 * in CTR mode once the ESP-IDF mbedTLS component is integrated.
 *
 * @param data      Buffer to encrypt/decrypt (modified in place).
 * @param len       Buffer length.
 * @param key       16-byte key.
 */
void ehash_crypto_xor(uint8_t *data, size_t len, const uint8_t key[EHASH_CRYPTO_KEY_SIZE]);

/**
 * @brief Check whether two keys are equal.
 */
bool ehash_crypto_key_equal(const uint8_t *a, const uint8_t *b);

#ifdef __cplusplus
}
#endif

#endif /* EHASH_CRYPTO_H */
