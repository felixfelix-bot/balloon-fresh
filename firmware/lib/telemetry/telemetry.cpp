#include "telemetry.h"

#include <cstring>

namespace balloon {

uint32_t crc32(const uint8_t *data, size_t len) {
  uint32_t crc = 0xFFFFFFFFu;
  for (size_t i = 0; i < len; ++i) {
    crc ^= data[i];
    for (int b = 0; b < 8; ++b) {
      const uint32_t mask = -(crc & 1u);
      crc = (crc >> 1) ^ (0xEDB88320u & mask);
    }
  }
  return crc ^ 0xFFFFFFFFu;
}

size_t encode(const TelemetryRecord &rec, uint8_t *out, size_t cap) {
  if (out == nullptr) return 0;
  const size_t need = encoded_size();
  if (cap < need) return 0;  // never write a partial record

  out[0] = TELEMETRY_VERSION;
  std::memcpy(out + 1, &rec, sizeof(TelemetryRecord));
  const uint32_t c = crc32(out, 1 + sizeof(TelemetryRecord));
  // little-endian CRC, written byte by byte so this is endian-independent
  out[1 + sizeof(TelemetryRecord) + 0] = static_cast<uint8_t>(c & 0xFF);
  out[1 + sizeof(TelemetryRecord) + 1] = static_cast<uint8_t>((c >> 8) & 0xFF);
  out[1 + sizeof(TelemetryRecord) + 2] = static_cast<uint8_t>((c >> 16) & 0xFF);
  out[1 + sizeof(TelemetryRecord) + 3] = static_cast<uint8_t>((c >> 24) & 0xFF);
  return need;
}

DecodeResult decode(const uint8_t *in, size_t len, TelemetryRecord &out) {
  if (in == nullptr) return DecodeResult::TooShort;
  const size_t need = encoded_size();
  if (len < need) return DecodeResult::TooShort;
  if (in[0] != TELEMETRY_VERSION) return DecodeResult::BadVersion;

  const uint32_t want = crc32(in, 1 + sizeof(TelemetryRecord));
  const size_t off = 1 + sizeof(TelemetryRecord);
  const uint32_t got = static_cast<uint32_t>(in[off]) |
                       (static_cast<uint32_t>(in[off + 1]) << 8) |
                       (static_cast<uint32_t>(in[off + 2]) << 16) |
                       (static_cast<uint32_t>(in[off + 3]) << 24);
  if (want != got) return DecodeResult::BadCrc;

  // only now is the payload trusted
  std::memcpy(&out, in + 1, sizeof(TelemetryRecord));
  return DecodeResult::Ok;
}

}  // namespace balloon
