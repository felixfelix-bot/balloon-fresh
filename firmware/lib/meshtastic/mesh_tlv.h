// L4 (Meshtastic) - a compact TLV codec for the packet structures L4 needs.
//
// IMPORTANT, READ FIRST: Meshtastic does NOT use TLV. The real firmware sends a
// fixed 16-byte PacketHeader (see mesh_packet.h) followed by a protobuf-encoded
// `Data` message for the payload, and carries position/telemetry as separate
// protobuf `PortNum` messages inside that payload.
//
// A protobuf implementation is out of scope for this library (and would be a
// third-party dependency in the flight build). So the payload and the optional
// position/telemetry structures are encoded with THIS codec, which is our own
// container, while the 16-byte header is byte-exact Meshtastic. That split is
// deliberate and it is the single most important honesty caveat in this module:
//
//   * header        -> byte-compatible with Meshtastic
//   * payload/pos/telemetry -> OUR TLV container, NOT Meshtastic-compatible
//
// A real interoperability attempt would need protobuf (or a hand-rolled
// protobuf-minimal writer for the handful of fields involved). See REPORT.md.
//
// Record format (3-byte record header + value):
//
//   +--------+--------+--------+------------------+
//   | id u8  | type   | len u8 | value[len]       |
//   +--------+--------+--------+------------------+
//
// All multi-byte integers inside a U32 value are little-endian, matching the
// header's byte order so the whole frame is consistently little-endian.
//
// RULES (the brief requires a STATED rule for every awkward case):
//   R1  An unknown field id or an unknown wire type is SKIPPED, not rejected:
//       the record header is parsed, the declared length is used to step over
//       the value, and decoding continues. Rationale: a newer sender must be
//       able to add fields without a forward-compatibility break - the same
//       spirit as protobuf's unknown-field handling.
//       EXCEPTION: if the declared length runs past the end of the buffer the
//       stream is desynchronised and the whole decode is rejected (Truncated).
//       Skipping is only safe when the length is actually inside the buffer.
//   R2  A declared value length greater than kTlvMaxValueLen is REJECTED
//       (Oversized). This is checked BEFORE availability, so an attacker cannot
//       use a huge declared length to make the decoder walk off the buffer.
//   R3  A record header or value that does not fit in the remaining bytes is
//       REJECTED (Truncated).
//   R4  Field id 0 is reserved and REJECTED (Malformed): encode never emits it,
//       so its presence means the stream is not ours.
//   R5  A repeated field id is REJECTED (Duplicate). Ambiguity about which copy
//       wins is a security smell in a filter path, so it is an error, not
//       last-wins.
//   R6  On encode, a value that cannot be represented in its field is REJECTED
//       (BadValue). The type/length must match the field's schema exactly.
//   R7  If the output buffer is too small the encode REJECTS (NoSpace) and
//       writes nothing: no partial frames ever reach the radio.
#pragma once

#include <cstddef>
#include <cstdint>

#include "mesh_packet.h"

namespace balloon {
namespace meshtastic {

/// Largest value any single field may carry. Chosen as a small power of two so
/// one by
///te of length is enough; the payload is the only field that needs room,
/// and kMaxPayloadLen (235) fits comfortably. Enforced by rule R2.
constexpr uint8_t kTlvMaxValueLen = 64;

/// Wire types. U32 is always 4 bytes, U8 is always 1 byte, Bytes is variable.
enum class FieldType : uint8_t {
  U8 = 1,
  U32 = 2,
  Bytes = 3,
};

/// Field ids. 0 is reserved and never emitted.
enum class FieldId : uint8_t {
  To = 1,
  From = 2,
  Id = 3,
  Flags = 4,
  Channel = 5,
  NextHop = 6,
  RelayNode = 7,
  Payload = 8,
  Position = 9,    // 12 bytes: lat_1e7, lon_1e7, alt_mm
  Telemetry = 10,  // 9 bytes: battery_mv, temp_cc, sats, uptime_s
};

enum class EncodeStatus : uint8_t {
  Ok = 0,
  NoSpace,    // R7
  BadValue,   // R6
};

/// Encode p into out. On success writes *out_len bytes and returns Ok; on any
/// failure writes nothing and leaves *out_len untouched.
///
/// NOTE: the own-payload limit is enforced here. A payload larger than
/// kMaxPayloadLen cannot be represented in a 255-byte LoRa frame, so it is
/// BadValue rather than a truncation.
EncodeStatus tlv_encode(const MeshPacket &p, uint8_t *out, size_t out_cap,
                       size_t *out_len);

/// Decode a frame. Fields absent from the stream keep their default value, so a
/// decode followed by an encode is byte-identical when every field was present.
DecodeStatus tlv_decode(const uint8_t *in, size_t len, MeshPacket *out);

/// Size of the largest frame this codec can produce for p. Useful for sizing a
/// TX buffer. Returns 0 for a packet the encoder would reject.
size_t tlv_worst_case_size(const MeshPacket &p);

}  // namespace meshtastic
}  // namespace balloon
