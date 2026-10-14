// L4 (Meshtastic) - AES-256/AES-128 block cipher + CTR mode, self-contained.
//
// WHY THIS EXISTS: the Meshtastic wire format encrypts channel payloads with
// AES-CTR (16-byte key => AES-128, 32-byte key => AES-256). The balloon-fresh
// firmware has no crypto library on the host-testable path, and adding one would
// put a third-party dependency inside the flight build. This is therefore a
// small, dependency-free implementation whose ONLY correctness authority is the
// published FIPS-197 test vectors and OpenSSL cross-checks (see test_mesh.cpp).
//
// The S-box is GENERATED from the GF(2^8) definition rather than typed in as a
// 256-entry table: a table copied by hand is unverifiable, a generator plus the
// FIPS-197 vectors is verifiable. FIPS-197 (Appendix C) fixes the round
// constants and the S-box and the key schedule, so this is a real AES and not an
// approximation of one.
//
// SCOPE: no padding oracle, no AEAD, no side-channel hardening. This is a
// constant-time-agnostic reference implementation for a hobby flight computer,
// NOT a hardened crypto library. Say so in any review that touches it.
#pragma once

#include <cstddef>
#include <cstdint>

namespace balloon {
namespace meshtastic {

/// Block size of AES: always 16 bytes.
constexpr size_t kAesBlockLen = 16;

/// Expanded key schedule.
struct AesKey {
  uint8_t round_key[240];  // 15 x 16 for AES-256, 11 x 16 valid for AES-128
  int rounds = 0;          // 10 for AES-128, 14 for AES-256
};

/// FIPS-197 S-box, generated at first use from the GF(2^8) definition.
const uint8_t *aes_sbox();

/// \return true when key_len is 16 or 32.
bool aes_set_key(AesKey *k, const uint8_t *key, size_t key_len);

/// Encrypt one 16-byte block. in and out may alias.
void aes_encrypt_block(const AesKey &k, const uint8_t *in, uint8_t *out);

/// Streaming CTR state.
struct AesCtr {
  AesKey key{};
  uint8_t counter[kAesBlockLen] = {};
  uint8_t keystream[kAesBlockLen] = {};
  uint8_t pos = kAesBlockLen;  // 16 == "keystream exhausted, refill on next byte"
};

// CTR counter width, in bytes, that the firmware increments (the low 32 bits of
// the counter block). This mirrors upstream `ctr->setCounterSize(4)`.
//
// UNVERIFIED BEHAVIOUR: for any message shorter than (2^32-1)*16 bytes the
// increment width cannot change the keystream, so this constant is not
// observable from a round-trip test. It is recorded because a reviewer will
// otherwise ask why 4.
constexpr uint8_t kCtrCounterBytes = 4;

/// \return false unless key_len is 16 or 32 and nonce is kAesBlockLen bytes.
bool aes_ctr_init(AesCtr *c, const uint8_t *key, size_t key_len,
                  const uint8_t *nonce);

/// XOR the keystream over buf in place. The same call both encrypts and
/// decrypts, which is the defining property of CTR mode.
void aes_ctr_xor(AesCtr *c, uint8_t *buf, size_t len);

}  // namespace meshtastic
}  // namespace balloon
