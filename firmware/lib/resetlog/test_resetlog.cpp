// TDD entry point for S3. RED first: resetlog.cpp absent -> build failure.
#include "harness.h"
#include "resetlog.h"

#include <cstring>
#include <map>
#include <string>
#include <vector>

using namespace balloon;

// In-memory store with a switch for simulating a power cut mid-write.
class FakeKV : public KeyValueStore {
 public:
  int read(const char *key, uint8_t *out, size_t cap) override {
    auto it = m_.find(key);
    if (it == m_.end()) return -1;
    if (it->second.size() > cap) return -1;
    std::memcpy(out, it->second.data(), it->second.size());
    return static_cast<int>(it->second.size());
  }
  bool write(const char *key, const uint8_t *data, size_t len) override {
    if (cut_after_ >= 0) {
      // power cut: only the first `cut_after_` bytes reach the medium
      m_[key] = std::vector<uint8_t>(data, data + cut_after_);
      return false;
    }
    m_[key] = std::vector<uint8_t>(data, data + len);
    return true;
  }
  void cutAfter(int n) { cut_after_ = n; }
  void heal() { cut_after_ = -1; }
  void poison(const char *key) {
    auto it = m_.find(key);
    if (it != m_.end() && !it->second.empty()) it->second[0] ^= 0xFF;
  }

 private:
  std::map<std::string, std::vector<uint8_t>> m_;
  int cut_after_ = -1;
};

void run_tests() {
  CASE("fresh device: nothing yet");
  {
    FakeKV kv;
    ResetLog log(kv);
    uint32_t c = 0;
    uint8_t cause = 0;
    CHECK(!log.load(c, cause));
  }

  CASE("boot counter increments monotonically across reboots");
  {
    FakeKV kv;
    uint32_t c = 0;
    {
      ResetLog log(kv);
      CHECK(log.commit(kResetPowerOn, c));
      CHECK_EQ(c, 1u);
    }
    {  // simulated reboot: new object, same storage
      ResetLog log(kv);
      uint32_t lc = 0;
      uint8_t cause = 0;
      CHECK(log.load(lc, cause));
      CHECK_EQ(lc, 1u);
      CHECK_EQ(cause, kResetPowerOn);
      CHECK(log.commit(kResetBrownout, c));
      CHECK_EQ(c, 2u);
    }
    {
      ResetLog log(kv);
      uint32_t lc = 0;
      uint8_t cause = 0;
      CHECK(log.load(lc, cause));
      CHECK_EQ(lc, 2u);
      CHECK_EQ(cause, kResetBrownout);
    }
  }

  CASE("COUNTER-TEST: a torn write must NOT lose the counter");
  {
    FakeKV kv;
    uint32_t c = 0;
    ResetLog log(kv);
    CHECK(log.commit(kResetPowerOn, c));
    CHECK_EQ(c, 1u);

    // cut the NEXT write half-way through the slot
    kv.cutAfter(3);
    CHECK(!log.commit(kResetWatchdog, c));  // honestly reports failure
    CHECK_EQ(c, 1u);                        // counter not advanced, not lost

    // power cycle with the torn slot still on the medium
    kv.heal();
    ResetLog log2(kv);
    uint32_t lc = 0;
    uint8_t cause = 0;
    CHECK(log2.load(lc, cause));   // must still find the good slot
    CHECK_EQ(lc, 1u);
    CHECK_EQ(cause, kResetPowerOn);

    // and the counter can still move forward afterwards
    CHECK(log2.commit(kResetSoftware, c));
    CHECK_EQ(c, 2u);
  }

  CASE("COUNTER-TEST: corrupting a slot's bytes invalidates it");
  {
    FakeKV kv;
    uint32_t c = 0;
    ResetLog log(kv);
    CHECK(log.commit(kResetPowerOn, c));
    CHECK_EQ(c, 1u);
    // flip a payload byte in the stored slot -> CRC must reject it
    kv.poison("rl_a");
    ResetLog log2(kv);
    uint32_t lc = 0;
    uint8_t cause = 0;
    CHECK(!log2.load(lc, cause));  // no valid slot remains
  }
}

TEST_MAIN()
