#include "resetlog.h"

#include <cstring>

namespace balloon {

static uint32_t slotCrc(const uint8_t *d, size_t n) {
  uint32_t crc = 0xFFFFFFFFu;
  for (size_t i = 0; i < n; ++i) {
    crc ^= d[i];
    for (int b = 0; b < 8; ++b) {
      const uint32_t mask = -(crc & 1u);
      crc = (crc >> 1) ^ (0xEDB88320u & mask);
    }
  }
  return crc ^ 0xFFFFFFFFu;
}

static const char *kSlotKey[2] = {"rl_a", "rl_b"};

bool ResetLog::readSlot(const char *key, Slot &out) {
  uint8_t buf[sizeof(Slot)];
  const int n = kv_.read(key, buf, sizeof buf);
  if (n != static_cast<int>(sizeof(Slot))) return false;

  Slot s;
  std::memcpy(&s, buf, sizeof s);
  // recompute over the on-disk bytes so a torn slot cannot validate
  const uint32_t want = slotCrc(buf, sizeof(uint32_t) + sizeof(uint8_t));
  if (want != s.crc) return false;
  out = s;
  return true;
}

bool ResetLog::load(uint32_t &boot_count, uint8_t &cause) {
  Slot best;
  bool found = false;
  const char *best_key = nullptr;

  for (int i = 0; i < 2; ++i) {
    Slot s;
    if (!readSlot(kSlotKey[i], s)) continue;
    if (!found || s.seq > best.seq) {
      best = s;
      found = true;
      best_key = kSlotKey[i];
    }
  }
  if (!found) return false;

  count_ = best.seq;
  have_ = true;
  last_key_[0] = best_key[0];
  last_key_[1] = best_key[1];
  boot_count = count_;
  cause = best.cause;
  return true;
}

bool ResetLog::commit(uint8_t cause, uint32_t &new_count) {
  // Write the slot we did NOT just read from, so a cut cannot destroy the
  // only copy of the current count.
  const bool last_was_a = (last_key_[0] == 'r' && last_key_[1] == 'l');
  const char *target = have_ && last_was_a ? "rl_b" : "rl_a";
  if (!have_) target = "rl_a";

  Slot s;
  s.seq = have_ ? count_ + 1 : 1;
  s.cause = cause;

  uint8_t raw[sizeof(Slot)];
  std::memcpy(raw, &s, sizeof(Slot));
  s.crc = slotCrc(raw, sizeof(uint32_t) + sizeof(uint8_t));
  std::memcpy(raw, &s, sizeof(Slot));

  // A cut inside this write may corrupt `target`; the other slot still holds
  // the previous count, so the counter can never go backwards or be lost.
  kv_.write(target, raw, sizeof raw);

  // Read back from storage: only a verified slot may advance the counter.
  Slot verify;
  if (!readSlot(target, verify)) {
    // torn write - keep the value we already had; do not claim success
    new_count = count_;
    return false;
  }
  count_ = verify.seq;
  have_ = true;
  last_key_[0] = target[0];
  last_key_[1] = target[1];
  new_count = count_;
  return true;
}

}  // namespace balloon
