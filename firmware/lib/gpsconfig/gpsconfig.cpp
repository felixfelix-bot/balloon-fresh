#include "gpsconfig.h"

namespace balloon {

void ubxChecksum(const uint8_t *data, size_t len, uint8_t &ck_a, uint8_t &ck_b) {
  ck_a = 0;
  ck_b = 0;
  for (size_t i = 0; i < len; ++i) {
    ck_a = static_cast<uint8_t>(ck_a + data[i]);
    ck_b = static_cast<uint8_t>(ck_b + ck_a);
  }
}

size_t buildFrame(uint8_t cls, uint8_t id, const uint8_t *payload, size_t len,
                  uint8_t *out, size_t cap) {
  if (out == nullptr) return 0;
  if (len > ubx::kMaxPayload) return 0;
  const size_t need = 2 + 1 + 1 + 2 + len + 2;
  if (cap < need) return 0;

  size_t k = 0;
  out[k++] = ubx::kSync1;
  out[k++] = ubx::kSync2;
  out[k++] = cls;
  out[k++] = id;
  out[k++] = static_cast<uint8_t>(len & 0xFF);
  out[k++] = static_cast<uint8_t>((len >> 8) & 0xFF);
  for (size_t i = 0; i < len; ++i) out[k++] = payload[i];

  uint8_t a = 0, b = 0;
  ubxChecksum(out + 2, 4 + len, a, b);
  out[k++] = a;
  out[k++] = b;
  return k;
}

size_t buildSetU1(uint32_t key, uint8_t value, uint8_t *out, size_t cap) {
  // CFG-VALSET payload: version(0) layers(0=RAM) transaction(0) then key+value
  uint8_t p[6];
  p[0] = 0x00;
  p[1] = 0x00;
  p[2] = 0x00;
  p[3] = static_cast<uint8_t>(key & 0xFF);
  p[4] = static_cast<uint8_t>((key >> 8) & 0xFF);
  p[5] = static_cast<uint8_t>((key >> 16) & 0xFF);
  // we need 3 + 4 + 1 = 8 bytes
  uint8_t pl[8];
  pl[0] = 0x00;
  pl[1] = 0x00;
  pl[2] = 0x00;
  pl[3] = static_cast<uint8_t>(key & 0xFF);
  pl[4] = static_cast<uint8_t>((key >> 8) & 0xFF);
  pl[5] = static_cast<uint8_t>((key >> 16) & 0xFF);
  pl[6] = static_cast<uint8_t>((key >> 24) & 0xFF);
  pl[7] = value;
  (void)p;
  return buildFrame(ubx::kClassCfg, ubx::kIdValset, pl, sizeof pl, out, cap);
}

size_t buildSetU2(uint32_t key, uint16_t value, uint8_t *out, size_t cap) {
  uint8_t pl[9];
  pl[0] = 0x00;
  pl[1] = 0x00;
  pl[2] = 0x00;
  pl[3] = static_cast<uint8_t>(key & 0xFF);
  pl[4] = static_cast<uint8_t>((key >> 8) & 0xFF);
  pl[5] = static_cast<uint8_t>((key >> 16) & 0xFF);
  pl[6] = static_cast<uint8_t>((key >> 24) & 0xFF);
  pl[7] = static_cast<uint8_t>(value & 0xFF);
  pl[8] = static_cast<uint8_t>((value >> 8) & 0xFF);
  return buildFrame(ubx::kClassCfg, ubx::kIdValset, pl, sizeof pl, out, cap);
}

UbxResult parseFrame(const uint8_t *in, size_t len, FrameView &out) {
  if (in == nullptr || len < 8) return UbxResult::TooShort;
  if (in[0] != ubx::kSync1 || in[1] != ubx::kSync2) return UbxResult::BadSync;

  const size_t plen = static_cast<size_t>(in[4]) | (static_cast<size_t>(in[5]) << 8);
  const size_t need = 2 + 1 + 1 + 2 + plen + 2;
  if (len < need) return UbxResult::BadLength;

  uint8_t a = 0, b = 0;
  ubxChecksum(in + 2, 4 + plen, a, b);
  if (a != in[6 + plen] || b != in[7 + plen]) return UbxResult::BadChecksum;

  out.cls = in[2];
  out.id = in[3];
  out.payload = in + 6;
  out.len = plen;
  return UbxResult::Ok;
}

bool valgetFindU1(const uint8_t *payload, size_t len, uint32_t key, uint8_t &value) {
  if (payload == nullptr || len < 3) return false;
  size_t k = 2;  // skip version + layer
  while (k + 4 <= len) {
    const uint32_t got = static_cast<uint32_t>(payload[k]) |
                         (static_cast<uint32_t>(payload[k + 1]) << 8) |
                         (static_cast<uint32_t>(payload[k + 2]) << 16) |
                         (static_cast<uint32_t>(payload[k + 3]) << 24);
    k += 4;
    if (got == key) {
      if (k >= len) return false;
      value = payload[k];
      return true;
    }
    // unknown key: we cannot know its size, so stop rather than misparse
    return false;
  }
  return false;
}

}  // namespace balloon
