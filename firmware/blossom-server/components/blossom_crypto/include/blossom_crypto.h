#ifndef BLOSSOM_CRYPTO_H
#define BLOSSOM_CRYPTO_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* Schnorr (BIP-340) signature verification over secp256k1.
 *
 * Returns true if sig (64 bytes) is a valid Schnorr signature for
 * pubkey (32 bytes, x-only) over message msg (32 bytes). */
bool verify_schnorr_sig(const uint8_t pubkey[32],
                        const uint8_t msg[32],
                        const uint8_t sig[64]);

/* Verify that the SHA-256 of the canonical event serialization
 * (NIP-01: [0, pubkey, created_at, kind, tags, content]) matches
 * expected_id (32 bytes).
 *
 * `event_json` is the raw JSON event string. The function parses it,
 * re-serializes the canonical array, hashes it, and compares to expected_id. */
bool verify_event_id(const char *event_json, size_t event_len,
                     const uint8_t expected_id[32]);

/* Convenience: fully validate a Nostr event from its JSON string.
 * Checks that the `id` field matches the computed event hash AND that
 * the `sig` field is a valid Schnorr signature over that id.
 *
 * Returns true only if both checks pass. */
bool blossom_verify_event(const char *event_json, size_t event_len);

/* Hex helpers (ported from wisp_relay relay_types.c). */
int relay_hex_to_bytes(const char *hex, size_t hex_len, uint8_t *out, size_t out_len);
void relay_bytes_to_hex(const uint8_t *bytes, size_t len, char *hex);

#endif /* BLOSSOM_CRYPTO_H */
