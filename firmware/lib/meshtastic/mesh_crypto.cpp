#include "mesh_crypto.h"

#include "mesh_aes.h"

#include <cstring>

namespace balloon {
namespace meshtastic {
namespace {

void put_le32(uint8_t *p, uint32_t v) {
  p[0] = (uint8_t)(v & 0xFF);
  p[1] = (uint8_t)((v >> 8) & 0xFF);
  p[2] = (uint8_t)((v >> 16) & 0xFF);
  p[3] = (uint8_t)((v >> 24) & 0xFF);
}

uint32_t get_le32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}

}  // namespace

uint32_t crc32_ieee(const uint8_t *data, size_t len) {
  uint32_t crc = 0xFFFFFFFFu;
  for (size_t i = 0; i < len; ++i) {
    crc ^= data[i];
    for (int b = 0; b < 8; ++b) {
      const uint32_t mask = (uint32_t)(-(int32_t)(crc & 1u));
      crc = (crc >> 1) ^ (0xEDB88320u & mask);
    }
  }
  return crc ^ 0xFFFFFFFFu;
}

void build_nonce(uint32_t packet_id, uint32_t from_node, uint8_t *out16) {
  std::memset(out16, 0, 16);
  // bytes 0-7: packet id as a 64-bit little-endian value. The packet id is
  // 32-bit on the wire, so the high half is zero.
  put_le32(out16 + 0, packet_id);
  put_le32(out16 + 4, 0);
  // bytes 8-11: sender node number, little-endian.
  put_le32(out16 + 8, from_node);
  // bytes 12-15: block counter, starts at 0 and is incremented by the CTR
  // implementation.
}

SealStatus seal_payload(const CryptoKey &key, uint32_t packet_id,
                        uint32_t from_node, const uint8_t *plain,
                        size_t plain_len, std::vector<uint8_t> *out) {
  if (out == nullptr) return SealStatus::BadArgument;
  if (plain == nullptr && plain_len != 0) return SealStatus::BadArgument;
  out->clear();

  if (key.length == 0) {
    // No encryption: upstream's 0-length PSK. Passthrough, no trailer.
    out->assign(plain, plain + plain_len);
    return SealStatus::Ok;
  }

  uint8_t nonce[16];
  build_nonce(packet_id, from_node, nonce);

  AesCtr ctr;
  if (!aes_ctr_init(&ctr, key.bytes, key.length, nonce)) {
    return SealStatus::BadArgument;
  }

  out->resize(plain_len + kSealTrailerLen);
  if (plain_len > 0) std::memcpy(out->data(), plain, plain_len);
  aes_ctr_xor(&ctr, out->data(), plain_len);
  put_le32(out->data() + plain_len, crc32_ieee(plain, plain_len));
  return SealStatus::Ok;
}

SealStatus open_payload(const CryptoKey &key, uint32_t packet_id,
                        uint32_t from_node, const uint8_t *sealed,
                        size_t sealed_len, std::vector<uint8_t> *out) {
  if (out == nullptr) return SealStatus::BadArgument;
  if (sealed == nullptr && sealed_len != 0) return SealStatus::BadArgument;
  out->clear();

  if (key.length == 0) {
    out->assign(sealed, sealed + sealed_len);
    return SealStatus::Ok;
  }

  if (sealed_len < kSealTrailerLen) return SealStatus::TooShort;
  const size_t plain_len = sealed_len - kSealTrailerLen;

  uint8_t nonce[16];
  build_nonce(packet_id, from_node, nonce);

  AesCtr ctr;
  if (!aes_ctr_init(&ctr, key.bytes, key.length, nonce)) {
    return SealStatus::BadArgument;
  }

  std::vector<uint8_t> plain(sealed, sealed + plain_len);
  aes_ctr_xor(&ctr, plain.data(), plain_len);

  const uint32_t want = get_le32(sealed + plain_len);
  const uint32_t got = crc32_ieee(plain.data(), plain_len);
  if (want != got) {
    // Deliberately do not hand back the garbage: a caller must not be able to
    // use it by accident.
    return SealStatus::IntegrityFailure;
  }

  *out = plain;
  return SealStatus::Ok;
}

}  // namespace meshtastic
}  // namespace balloon
