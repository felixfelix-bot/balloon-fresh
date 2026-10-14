// S4 - UBX configuration for high-altitude flight, plus read-back verification.
//
// WHY THIS EXISTS: a u-blox receiver ships assuming a pedestrian/stationary
// platform. At 10-14 km with a 1-3 m/s vertical rate that filter is wrong, and
// its vertical solution degrades badly. The fix is CFG-VALSET with
// CFG-NAVSPG-DYNMODEL = airborne<1g. Setting the airborne dynamic model is also
// what switches the receiver from the ground CoCom limit to the airborne one.
//
// This module is PURE: it builds and parses UBX frames. The serial link is a
// thin injected interface elsewhere, so framing and checksums are host-testable.
#pragma once

#include <cstddef>
#include <cstdint>

namespace balloon {

namespace ubx {
constexpr uint8_t kSync1 = 0xB5;
constexpr uint8_t kSync2 = 0x62;
constexpr uint8_t kClassCfg = 0x06;
constexpr uint8_t kIdValset = 0x8A;
constexpr uint8_t kIdValget = 0x8B;
constexpr size_t kMaxPayload = 128;
}  // namespace ubx

// u-blox configuration keys (32-bit).
constexpr uint32_t kKeyNavspgDynmodel = 0x20110021;  // U1
constexpr uint32_t kKeyRateMeas = 0x30210001;        // U2, ms

// CFG-NAVSPG-DYNMODEL values.
enum DynModel : uint8_t {
  kDynPortable = 0,
  kDynStationary = 2,
  kDynPedestrian = 3,
  kDynAutomotive = 4,
  kDynSea = 5,
  kDynAirborne1g = 6,  // <- what a pico balloon needs
  kDynAirborne2g = 7,
  kDynAirborne4g = 8,
};

// UBX checksum: CK_A/CK_B over class,id,len,payload (8-bit wraparound).
void ubxChecksum(const uint8_t *data, size_t len, uint8_t &ck_a, uint8_t &ck_b);

// Builds a complete frame into `out`. Returns bytes written, or 0 on overflow.
size_t buildFrame(uint8_t cls, uint8_t id, const uint8_t *payload, size_t len,
                  uint8_t *out, size_t cap);

// Convenience: CFG-VALSET setting one U1 key.
size_t buildSetU1(uint32_t key, uint8_t value, uint8_t *out, size_t cap);
// Convenience: CFG-VALSET setting one U2 key.
size_t buildSetU2(uint32_t key, uint16_t value, uint8_t *out, size_t cap);

struct FrameView {
  uint8_t cls;
  uint8_t id;
  const uint8_t *payload;
  size_t len;
};

enum class UbxResult { Ok = 0, TooShort, BadSync, BadLength, BadChecksum };

UbxResult parseFrame(const uint8_t *in, size_t len, FrameView &out);

// Reads a U1 value for `key` out of a CFG-VALGET response payload.
// Payload layout: version(1) layer(1) then repeated [key(4) value(n)].
bool valgetFindU1(const uint8_t *payload, size_t len, uint32_t key, uint8_t &value);

}  // namespace balloon
