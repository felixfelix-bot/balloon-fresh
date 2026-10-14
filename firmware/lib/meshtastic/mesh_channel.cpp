#include "mesh_channel.h"

#include <cstring>

namespace balloon {
namespace meshtastic {

const uint8_t kDefaultPsk[16] = {0xd4, 0xf1, 0xbb, 0x3a, 0x20, 0x29, 0x07, 0x59,
                                 0xf0, 0xbc, 0xff, 0xab, 0xcf, 0x4e, 0x69, 0x01};

namespace {

uint8_t xor_all(const uint8_t *p, size_t len) {
  uint8_t code = 0;
  for (size_t i = 0; i < len; ++i) code ^= p[i];
  return code;
}

}  // namespace

PskStatus expand_psk(const uint8_t *psk, size_t psk_len, CryptoKey *out) {
  if (out == nullptr) return PskStatus::BadArgument;
  if (psk == nullptr && psk_len != 0) return PskStatus::BadArgument;

  *out = CryptoKey();

  if (psk_len == 0) {
    out->length = 0;  // upstream: a secondary channel inherits the primary key;
                      // that policy lives in the caller, not in the key expander
    return PskStatus::Disabled;
  }

  if (psk_len == 1) {
    const uint8_t idx = psk[0];
    if (idx == 0) {
      out->length = 0;
      return PskStatus::Disabled;
    }
    std::memcpy(out->bytes, kDefaultPsk, kDefaultPskLen);
    out->length = kDefaultPskLen;
    // "index of 1 means no change vs defaultPSK"; 2..255 shift the last byte.
    // uint8_t arithmetic wraps, which is what upstream's `*last + pskIndex - 1`
    // does once the key material reaches 255.
    out->bytes[kDefaultPskLen - 1] =
        (uint8_t)(out->bytes[kDefaultPskLen - 1] + (uint8_t)(idx - 1));
    return PskStatus::Ok;
  }

  if (psk_len <= 16) {
    // Upstream: "User provided a too short AES128 key - padding"
    std::memcpy(out->bytes, psk, psk_len);
    out->length = 16;
    return PskStatus::Ok;
  }
  if (psk_len <= 32) {
    std::memcpy(out->bytes, psk, psk_len);
    out->length = (psk_len == 16) ? 16 : 32;
    return PskStatus::Ok;
  }
  return PskStatus::BadArgument;  // longer than AES-256 can use
}

int aes_bits_for(const CryptoKey &k) {
  if (k.length == 16) return 128;
  if (k.length == 32) return 256;
  return 0;  // disabled (or unexpanded)
}

uint8_t channel_hash(const char *name, const CryptoKey &k, size_t name_len) {
  if (name == nullptr) name = "";
  const uint8_t h_name = xor_all((const uint8_t *)name, name_len);
  const uint8_t h_key = xor_all(k.bytes, k.length);
  return (uint8_t)(h_name ^ h_key);
}

uint8_t channel_hash(const char *name, const CryptoKey &k) {
  return channel_hash(name, k, name == nullptr ? 0 : std::strlen(name));
}

}  // namespace meshtastic
}  // namespace balloon
