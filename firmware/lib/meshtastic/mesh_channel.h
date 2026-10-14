// L4 (Meshtastic) - channel key expansion and the 8-bit channel hash.
//
// SOURCES (public, read during this task - see REPORT.md for URLs and SHAs):
//
// 1. docs/development/reference/encryption-technical.mdx (meshtastic/meshtastic):
//
//      "Channel messages are encrypted with AES-CTR under the channel's
//       pre-shared key (PSK). A 16-byte key selects AES-128 and a 32-byte key
//       selects AES-256. A key of length 0 disables encryption.
//
//       A single-byte PSK is shorthand. `0` means no encryption, `1` selects the
//       published default key, and `2` through `255` select the default key with
//       that value minus one added to its last byte. These are public keys, not
//       private ones. A secondary channel with no PSK uses the primary
//       channel's key.
//
//       ... The one-byte channel hash in the packet header is the XOR of the
//       channel name's bytes with the XOR of the key's bytes. When the stored
//       name is empty, the hash uses the modem preset's name."
//
// 2. docs/configuration/radio/channels.mdx:
//      "The encryption key used for private channels.
//       Hex byte `0x01` for the Primary `default` channel.
//       Must be either 0 bytes (no crypto), 16 bytes (AES128), or 32 bytes
//       (AES256)."
//
// 3. src/mesh/Channels.h (meshtastic/firmware) carries the published default
//    key, and src/mesh/Channels.cpp carries the expansion:
//
//      static const uint8_t defaultpsk[] = {
//          0xd4, 0xf1, 0xbb, 0x3a, 0x20, 0x29, 0x07, 0x59,
//          0xf0, 0xbc, 0xff, 0xab, 0xcf, 0x4e, 0x69, 0x01};
//
//      uint8_t pskIndex = k.bytes[0];
//      if (pskIndex == 0) k.length = 0;
//      else {
//        memcpy(k.bytes, defaultpsk, sizeof(defaultpsk));
//        k.length = sizeof(defaultpsk);
//        uint8_t *last = k.bytes + sizeof(defaultpsk) - 1;
//        *last = *last + pskIndex - 1;   // index 1 == no change vs defaultPSK
//      }
//
//      uint8_t xorHash(const uint8_t *p, size_t len) { ... code ^= p[i]; }
//      uint8_t h = xorHash(name, strlen(name));
//      h ^= xorHash(k.bytes, k.length);
//
//    The default key is SIXTEEN bytes, so a default channel uses AES-128, not
//    AES-256. The header comment in Channels.h says "16 bytes of random PSK ...
//    (AES128)" in so many words. This matters and is easy to get wrong.
#pragma once

#include <cstddef>
#include <cstdint>

namespace balloon {
namespace meshtastic {

/// The published default channel key, verbatim from src/mesh/Channels.h.
/// It is PUBLIC by design: every Meshtastic node powers up holding it, which is
/// why the default channel is not private. Do not treat this as a secret.
extern const uint8_t kDefaultPsk[16];
constexpr size_t kDefaultPskLen = 16;

/// A channel key: up to 32 bytes plus the EFFECTIVE length.
///
/// `length` is the field that matters and it is deliberately NOT the buffer
/// size: a 16-byte key means AES-128 while a 32-byte key means AES-256, and the
/// buffer is zero-padded in both cases. Conflating "how big is the buffer" with
/// "how big is the key" is the classic way to silently promote a default channel
/// from AES-128 to AES-256 and break interoperability.
struct CryptoKey {
  uint8_t bytes[32] = {};
  size_t length = 0;  // 0, 16 or 32 after expansion
};

enum class PskStatus : uint8_t {
  Ok = 0,
  Disabled,     // length 0 after expansion: upstream "encryption off"
  BadArgument,  // null pointer or an absurd input length
};

/// Expand a stored PSK into an effective key, following the documented rules.
///
/// Input to output:
///   1 byte, value 0    -> length 0  (encryption disabled)
///   1 byte, value 1    -> the 16-byte default key, length 16
///   1 byte, value 2..255 -> the 16-byte default key with
///                          bytes[15] += value - 1, length 16
///   16 bytes           -> copied, length 16
///   32 bytes           -> copied, length 32
///   2..15 bytes        -> zero-padded to length 16 (upstream: "User provided a
///                         too short AES128 key - padding")
///   17..31 bytes       -> zero-padded to length 32 (upstream equivalent)
///   other              -> BadArgument
///
/// The alias bump is on the LAST byte of the 16-byte key and wraps modulo 256;
/// upstream relies on uint8_t overflow, which this reproduces explicitly.
PskStatus expand_psk(const uint8_t *psk, size_t psk_len, CryptoKey *out);

/// The AES variant the key selects. Returns 0 when encryption is disabled.
int aes_bits_for(const CryptoKey &k);

/// The 8-bit channel hash used in the packet header to filter packets BEFORE
/// any decryption is attempted. XOR of the channel name bytes with the XOR of
/// the key bytes.
///
/// WEAKNESS, STATED: this is 8 bits and is not a MAC. It is a routing hint, so
/// two different keys collide one time in ~256 and a wrong-key packet can pass
/// the filter. The filter exists to avoid running AES for every packet, NOT to
/// authenticate anything. The integrity check belongs in the payload trailer
/// (see mesh_crypto.h).
uint8_t channel_hash(const char *name, const CryptoKey &k);

/// Convenience overload for a NUL-terminated C++ string. Identical semantics.
uint8_t channel_hash(const char *name, const CryptoKey &k, size_t name_len);

}  // namespace meshtastic
}  // namespace balloon
