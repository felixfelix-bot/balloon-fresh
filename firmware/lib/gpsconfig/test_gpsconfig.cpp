// TDD entry point for S4. RED first: gpsconfig.cpp absent -> build failure.
#include "harness.h"
#include "gpsconfig.h"

#include <cstring>

using namespace balloon;

void run_tests() {
  CASE("frame has correct sync, class, id and little-endian length");
  {
    uint8_t frame[64];
    const size_t n = buildSetU1(kKeyNavspgDynmodel, kDynAirborne1g, frame, sizeof frame);
    CHECK_EQ(n, 2 + 1 + 1 + 2 + 8 + 2);
    CHECK_EQ(frame[0], 0xB5);
    CHECK_EQ(frame[1], 0x62);
    CHECK_EQ(frame[2], 0x06);  // CFG
    CHECK_EQ(frame[3], 0x8A);  // VALSET
    CHECK_EQ(frame[4], 8);     // payload length low byte
    CHECK_EQ(frame[5], 0);
  }

  CASE("the dynamic-model key and value land where they must");
  {
    uint8_t frame[64];
    buildSetU1(kKeyNavspgDynmodel, kDynAirborne1g, frame, sizeof frame);
    // payload starts at 6: version, layers, transaction, then the key LE
    CHECK_EQ(frame[6], 0);
    CHECK_EQ(frame[7], 0);
    CHECK_EQ(frame[8], 0);
    CHECK_EQ(frame[9], 0x21);
    CHECK_EQ(frame[10], 0x00);
    CHECK_EQ(frame[11], 0x11);
    CHECK_EQ(frame[12], 0x20);
    CHECK_EQ(frame[13], kDynAirborne1g);
  }

  CASE("checksum is computed over class,id,len,payload");
  {
    uint8_t frame[64];
    const size_t n = buildSetU1(kKeyNavspgDynmodel, kDynAirborne1g, frame, sizeof frame);
    uint8_t a = 0, b = 0;
    ubxChecksum(frame + 2, n - 4, a, b);
    CHECK_EQ(frame[n - 2], a);
    CHECK_EQ(frame[n - 1], b);
  }

  CASE("a built frame parses back to the same class/id/payload");
  {
    uint8_t frame[64];
    const size_t n = buildSetU1(kKeyNavspgDynmodel, kDynAirborne1g, frame, sizeof frame);
    FrameView v{};
    CHECK(parseFrame(frame, n, v) == UbxResult::Ok);
    CHECK_EQ(v.cls, 0x06);
    CHECK_EQ(v.id, 0x8A);
    CHECK_EQ(v.len, 8u);
  }

  CASE("READ-BACK: a CFG-VALGET response yields the configured model");
  {
    // simulate the receiver's answer: version, layer, key, value
    uint8_t pl[6];
    pl[0] = 0x01;  // version
    pl[1] = 0x00;  // layer = RAM
    pl[2] = 0x21;
    pl[3] = 0x00;
    pl[4] = 0x11;
    pl[5] = 0x20;
    uint8_t frame[64];
    // append the value by building a 7-byte payload through buildFrame
    uint8_t full[7];
    std::memcpy(full, pl, 6);
    full[6] = kDynAirborne1g;
    const size_t n = buildFrame(0x06, 0x8B, full, sizeof full, frame, sizeof frame);
    CHECK(n > 0);

    FrameView v{};
    CHECK(parseFrame(frame, n, v) == UbxResult::Ok);
    uint8_t got = 0;
    CHECK(valgetFindU1(v.payload, v.len, kKeyNavspgDynmodel, got));
    CHECK_EQ(got, kDynAirborne1g);  // the setting stuck
  }

  CASE("COUNTER-TEST: a corrupted frame is rejected, so read-back cannot lie");
  {
    uint8_t frame[64];
    const size_t n = buildSetU1(kKeyNavspgDynmodel, kDynAirborne1g, frame, sizeof frame);
    frame[10] ^= 0x01;  // flip one payload byte
    FrameView v{};
    CHECK(parseFrame(frame, n, v) == UbxResult::BadChecksum);
  }

  CASE("COUNTER-TEST: a corrupted length is caught, not read past the buffer");
  {
    uint8_t frame[64];
    const size_t n = buildSetU1(kKeyNavspgDynmodel, kDynAirborne1g, frame, sizeof frame);
    frame[4] = 0xFF;  // claim a huge payload
    frame[5] = 0x00;
    FrameView v{};
    CHECK(parseFrame(frame, n, v) == UbxResult::BadLength);
  }

  CASE("COUNTER-TEST: wrong sync bytes are refused");
  {
    uint8_t frame[64];
    const size_t n = buildSetU1(kKeyNavspgDynmodel, kDynAirborne1g, frame, sizeof frame);
    frame[0] = 0x00;
    FrameView v{};
    CHECK(parseFrame(frame, n, v) == UbxResult::BadSync);
  }

  CASE("an undersized output buffer never yields a partial frame");
  {
    uint8_t tiny[4];
    CHECK_EQ(buildSetU1(kKeyNavspgDynmodel, kDynAirborne1g, tiny, sizeof tiny), 0u);
    CHECK_EQ(buildFrame(0x06, 0x8A, nullptr, 0, nullptr, 0), 0u);
  }

  CASE("U2 rate key round-trips little-endian");
  {
    uint8_t frame[64];
    const size_t n = buildSetU2(kKeyRateMeas, 1000, frame, sizeof frame);
    CHECK_EQ(n, 2 + 1 + 1 + 2 + 9 + 2);
    CHECK_EQ(frame[13], 0xE8);  // 1000 & 0xFF
    CHECK_EQ(frame[14], 0x03);  // 1000 >> 8
  }
}

TEST_MAIN()
