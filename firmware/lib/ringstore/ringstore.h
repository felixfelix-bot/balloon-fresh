// S2 - store-and-forward ring for flight data.
//
// Records are appended to a byte-addressable medium and self-describing:
//   [magic u16][len u16][crc32 u32][payload len]
// The CRC covers the payload, so a record interrupted by a power cut fails
// validation. load() accepts ONLY the contiguous valid prefix and stops at the
// first damaged record: it never skips a hole, because a hole means everything
// after it was written under conditions we cannot vouch for.
//
// Guarantees (each has a test and a counter-test):
//   G1 readback never yields a corrupt record
//   G2 a power cut during append never loses an earlier record
//   G3 the valid prefix never grows past what was actually committed
#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace balloon {

class BlockDevice {
 public:
  virtual ~BlockDevice() = default;
  virtual size_t size() = 0;
  virtual size_t readAt(size_t off, uint8_t *out, size_t n) = 0;
  // Writes at `off`. MAY be cut short by a power failure: returns the number of
  // bytes that actually reached the medium, which may be < n.
  virtual size_t writeAt(size_t off, const uint8_t *in, size_t n) = 0;
  virtual void truncate(size_t n) = 0;
};

class RingStore {
 public:
  static constexpr uint16_t kMagic = 0xB1A5;
  static constexpr size_t kHeader = 8;  // magic + len + crc

  explicit RingStore(BlockDevice &dev) : dev_(dev) {}

  // Scans the medium and indexes the contiguous valid prefix.
  bool load();

  // Appends one record. Returns false if the medium is full or the write was
  // interrupted; in both cases the valid prefix is left unchanged.
  bool append(const uint8_t *data, size_t len);

  size_t count() const { return index_.size(); }
  size_t validBytes() const { return valid_end_; }

  // 0-based. False if out of range. `out`/`out_len` point INTO the store's copy.
  bool record(size_t i, const uint8_t **out, size_t *out_len) const;

  // Total records that could not be read because they sat behind damage.
  size_t droppedBehindDamage() const { return dropped_; }

 private:
  struct Entry {
    size_t off;
    size_t len;
  };
  BlockDevice &dev_;
  std::vector<Entry> index_;
  std::vector<std::vector<uint8_t>> payloads_;
  size_t valid_end_ = 0;
  size_t dropped_ = 0;
};

uint32_t ring_crc32(const uint8_t *data, size_t len);

}  // namespace balloon
