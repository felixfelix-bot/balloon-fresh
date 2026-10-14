// TDD entry point for S2. RED first: ringstore.cpp absent -> build failure.
// The torture test kills the write at EVERY offset of a record and asserts the
// two guarantees that matter for flight data.
#include "harness.h"
#include "ringstore.h"

#include <cstring>
#include <string>
#include <vector>

using namespace balloon;

// Byte medium that can simulate a power cut after N bytes of a write.
class FakeDev : public BlockDevice {
 public:
  explicit FakeDev(size_t cap) : mem_(cap, 0xFF) {}  // 0xFF = erased flash

  size_t size() override { return mem_.size(); }
  size_t readAt(size_t off, uint8_t *out, size_t n) override {
    if (off >= mem_.size()) return 0;
    const size_t k = std::min(n, mem_.size() - off);
    std::memcpy(out, mem_.data() + off, k);
    return k;
  }
  size_t writeAt(size_t off, const uint8_t *in, size_t n) override {
    if (off >= mem_.size()) return 0;
    size_t k = std::min(n, mem_.size() - off);
    if (cut_after_ >= 0 && static_cast<size_t>(cut_after_) < k) k = cut_after_;
    std::memcpy(mem_.data() + off, in, k);
    return k;
  }
  void truncate(size_t n) override {
    if (n < mem_.size()) std::fill(mem_.begin() + n, mem_.end(), 0xFF);
  }
  void cutAfter(int n) { cut_after_ = n; }
  void heal() { cut_after_ = -1; }
  void corrupt(size_t off) { mem_[off] ^= 0xFF; }

 private:
  std::vector<uint8_t> mem_;
  int cut_after_ = -1;
};

static std::vector<uint8_t> bytes(const char *s) {
  return std::vector<uint8_t>(s, s + std::strlen(s));
}

void run_tests() {
  CASE("append + reload round trip preserves order and content");
  {
    FakeDev dev(1024);
    RingStore rs(dev);
    rs.load();
    CHECK_EQ(rs.count(), 0u);

    auto a = bytes("first");
    auto b = bytes("second");
    auto c = bytes("third");
    CHECK(rs.append(a.data(), a.size()));
    CHECK(rs.append(b.data(), b.size()));
    CHECK(rs.append(c.data(), c.size()));
    CHECK_EQ(rs.count(), 3u);

    // simulate a reboot: fresh object over the same medium
    RingStore rs2(dev);
    rs2.load();
    CHECK_EQ(rs2.count(), 3u);
    const uint8_t *p = nullptr;
    size_t n = 0;
    CHECK(rs2.record(0, &p, &n));
    CHECK_EQ(n, a.size());
    CHECK(std::memcmp(p, a.data(), n) == 0);
    CHECK(rs2.record(2, &p, &n));
    CHECK(std::memcmp(p, c.data(), n) == 0);
  }

  CASE("record() out of range is refused");
  {
    FakeDev dev(256);
    RingStore rs(dev);
    rs.load();
    const uint8_t *p = nullptr;
    size_t n = 0;
    CHECK(!rs.record(0, &p, &n));
  }

  CASE("TORTURE: power cut at EVERY offset of a write loses no earlier record");
  {
    const char *rec1 = "RECORD-ONE-PAYLOAD";
    const char *rec2 = "RECORD-TWO-PAYLOAD-LONGER";

    for (int cut = 0; cut <= static_cast<int>(std::strlen(rec2) + RingStore::kHeader); ++cut) {
      FakeDev dev(512);
      RingStore rs(dev);
      rs.load();

      auto a = bytes(rec1);
      CHECK(rs.append(a.data(), a.size()));

      // cut the second write at `cut` bytes
      dev.cutAfter(cut);
      auto b = bytes(rec2);
      const bool ok = rs.append(b.data(), b.size());
      dev.heal();

      // G2: record 1 must survive in every single case
      RingStore after(dev);
      after.load();
      const uint8_t *p = nullptr;
      size_t n = 0;
      CHECK(after.count() >= 1u);
      if (after.count() >= 1u) {
        CHECK(after.record(0, &p, &n));
        CHECK_EQ(n, a.size());
        // G1: what we get back is exactly what we wrote, never garbage
        CHECK(std::memcmp(p, a.data(), n) == 0);
      }
      // if the whole record reached the medium it must be reported as present
      if (ok) {
        CHECK_EQ(after.count(), 2u);
      }
    }
  }

  CASE("COUNTER-TEST: a corrupted payload is never returned as valid");
  {
    FakeDev dev(512);
    RingStore rs(dev);
    rs.load();
    auto a = bytes("payload-alpha");
    CHECK(rs.append(a.data(), a.size()));
    dev.corrupt(RingStore::kHeader + 3);  // flip a byte inside the payload

    RingStore after(dev);
    after.load();
    CHECK_EQ(after.count(), 0u);          // rejected, not returned torn
    CHECK(after.droppedBehindDamage() > 0u);
  }

  CASE("COUNTER-TEST: a corrupted header length cannot cause an over-read");
  {
    FakeDev dev(512);
    RingStore rs(dev);
    rs.load();
    auto a = bytes("abc");
    CHECK(rs.append(a.data(), a.size()));
    dev.corrupt(2);  // mangle the length low byte -> absurd len

    RingStore after(dev);
    after.load();
    CHECK_EQ(after.count(), 0u);
  }

  CASE("full medium is refused without damaging the existing prefix");
  {
    FakeDev dev(RingStore::kHeader + 4 + 2);  // room for exactly one 4-byte rec
    RingStore rs(dev);
    rs.load();
    auto a = bytes("aaaa");
    CHECK(rs.append(a.data(), a.size()));
    auto b = bytes("bbbb");
    CHECK(!rs.append(b.data(), b.size()));   // no room
    CHECK_EQ(rs.count(), 1u);                // prefix intact
    const uint8_t *p = nullptr;
    size_t n = 0;
    CHECK(rs.record(0, &p, &n));
    CHECK(std::memcmp(p, a.data(), n) == 0);
  }
}

TEST_MAIN()
