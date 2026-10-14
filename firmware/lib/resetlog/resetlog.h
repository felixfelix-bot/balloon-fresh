// S3 - persisted reset cause + monotonic boot counter.
// Torn-write tolerant: two slots written alternately, each self-checksummed, so
// a power cut in the middle of a write can never lose the counter value.
#pragma once

#include <cstddef>
#include <cstdint>

namespace balloon {

// Injectable storage. On device this is NVS/littlefs; on the host, memory.
class KeyValueStore {
 public:
  virtual ~KeyValueStore() = default;
  // Bytes read, or -1 if the key is absent.
  virtual int read(const char *key, uint8_t *out, size_t cap) = 0;
  // True on success. MAY be interrupted by a power cut part-way through.
  virtual bool write(const char *key, const uint8_t *data, size_t len) = 0;
};

// Our own mirror of esp_reset_reason() so the host tests need no ESP-IDF.
enum ResetCause : uint8_t {
  kResetUnknown  = 0,
  kResetPowerOn  = 1,
  kResetBrownout = 2,  // the cold-start failure mode we care about
  kResetWatchdog = 3,
  kResetSoftware = 4,
};

class ResetLog {
 public:
  explicit ResetLog(KeyValueStore &kv) : kv_(kv) {}

  // Best valid slot wins. False when no slot is valid (fresh device).
  bool load(uint32_t &boot_count, uint8_t &cause);

  // Increments the counter, records `cause`, writes the OTHER slot than the one
  // just loaded, and reads it back. `new_count` is the value now persisted.
  bool commit(uint8_t cause, uint32_t &new_count);

  // Value from the last successful load()/commit(), for convenience.
  uint32_t boot_count() const { return count_; }

 private:
  struct __attribute__((packed)) Slot {
    uint32_t seq;
    uint8_t cause;
    uint32_t crc;  // over seq+cause
  };

  bool readSlot(const char *key, Slot &out);
  KeyValueStore &kv_;
  uint32_t count_ = 0;
  bool have_ = false;
  char last_key_[2] = {0, 0};  // which slot was written last
};

}  // namespace balloon
