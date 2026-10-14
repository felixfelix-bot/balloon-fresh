#include "ringstore.h"

#include <cstring>

namespace balloon {

uint32_t ring_crc32(const uint8_t *data, size_t len) {
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

bool RingStore::load() {
  index_.clear();
  payloads_.clear();
  valid_end_ = 0;
  dropped_ = 0;

  size_t off = 0;
  const size_t total = dev_.size();
  std::vector<uint8_t> hdr(kHeader);

  while (off + kHeader <= total) {
    if (dev_.readAt(off, hdr.data(), kHeader) != kHeader) break;

    const uint16_t magic = static_cast<uint16_t>(hdr[0] | (hdr[1] << 8));
    const uint16_t len = static_cast<uint16_t>(hdr[2] | (hdr[3] << 8));
    const uint32_t crc = static_cast<uint32_t>(hdr[4]) |
                         (static_cast<uint32_t>(hdr[5]) << 8) |
                         (static_cast<uint32_t>(hdr[6]) << 16) |
                         (static_cast<uint32_t>(hdr[7]) << 24);

    if (magic != kMagic) { dropped_ = 1; break; }        // damage: stop here
    if (off + kHeader + len > total) { dropped_ = 1; break; }

    std::vector<uint8_t> pay(len);
    if (len > 0 && dev_.readAt(off + kHeader, pay.data(), len) != len) {
      dropped_ = 1;
      break;
    }
    if (ring_crc32(pay.data(), len) != crc) { dropped_ = 1; break; }

    Entry e;
    e.off = off;
    e.len = len;
    index_.push_back(e);
    payloads_.push_back(pay);
    off += kHeader + len;
    valid_end_ = off;
  }
  return true;
}

bool RingStore::append(const uint8_t *data, size_t len) {
  if (data == nullptr && len > 0) return false;
  if (len > 0xFFFF) return false;

  const size_t off = valid_end_;
  const size_t need = kHeader + len;
  if (off + need > dev_.size()) return false;  // no room: leave prefix intact

  std::vector<uint8_t> buf(need);
  buf[0] = static_cast<uint8_t>(kMagic & 0xFF);
  buf[1] = static_cast<uint8_t>((kMagic >> 8) & 0xFF);
  buf[2] = static_cast<uint8_t>(len & 0xFF);
  buf[3] = static_cast<uint8_t>((len >> 8) & 0xFF);
  const uint32_t crc = ring_crc32(data, len);
  buf[4] = static_cast<uint8_t>(crc & 0xFF);
  buf[5] = static_cast<uint8_t>((crc >> 8) & 0xFF);
  buf[6] = static_cast<uint8_t>((crc >> 16) & 0xFF);
  buf[7] = static_cast<uint8_t>((crc >> 24) & 0xFF);
  if (len > 0) std::memcpy(buf.data() + kHeader, data, len);

  const size_t wrote = dev_.writeAt(off, buf.data(), need);
  if (wrote != need) {
    // A cut inside the record: the medium now holds a partial record. Trim it
    // back so the next append starts from a known-good boundary. Earlier
    // records are untouched, which is guarantee G2.
    dev_.truncate(off);
    return false;
  }

  Entry e;
  e.off = off;
  e.len = len;
  index_.push_back(e);
  payloads_.push_back(std::vector<uint8_t>(data, data + len));
  valid_end_ = off + need;
  return true;
}

bool RingStore::record(size_t i, const uint8_t **out, size_t *out_len) const {
  if (i >= payloads_.size()) return false;
  *out = payloads_[i].empty() ? nullptr : payloads_[i].data();
  *out_len = payloads_[i].size();
  return true;
}

}  // namespace balloon
