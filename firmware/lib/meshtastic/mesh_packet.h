// L4 (Meshtastic) - the in-memory packet and the 16-byte wire header.
//
// The header layout is Meshtastic's, reproduced from public source:
//   meshtastic/firmware  src/mesh/RadioInterface.h
//     struct PacketHeader { NodeNum to, from; PacketId id; uint8_t flags;
//                           uint8_t channel; uint8_t next_hop; uint8_t relay_node; };
//     #define MESHTASTIC_HEADER_LENGTH 16
//     #define PACKET_FLAGS_HOP_LIMIT_MASK      0x07
//     #define PACKET_FLAGS_WANT_ACK_MASK       0x08
//     #define PACKET_FLAGS_VIA_MQTT_MASK       0x10
//     #define PACKET_FLAGS_HOP_START_MASK      0xE0
//     #define PACKET_FLAGS_HOP_START_SHIFT     5
//
// The three uint32 fields are stored little-endian on the wire (the firmware is
// little-endian on every supported MCU, so the struct IS the wire format there).
// That endianness assumption is stated rather than assumed: a big-endian host
// would need explicit byte-order handling, and this code makes the byte order
// explicit so it does not depend on the host.
#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

namespace balloon {
namespace meshtastic {

/// Wire header length. Upstream MESHTASTIC_HEADER_LENGTH.
constexpr size_t kHeaderLength = 16;

/// Largest raw LoRa frame, per Semtech's SX12xx datasheets (upstream
/// MAX_LORA_PAYLOAD_LEN). The header is carved out of this budget.
constexpr size_t kMaxLoraPayload = 255;

/// Largest application payload this layer accepts.
///
/// Derived, not guessed. A maximum-size packet must still fit one 255-byte LoRa
/// frame once the 16-byte header, the TLV record overhead and the 4-byte CRC
/// trailer are paid for.
///
/// Fixed-field TLV overhead (7 records, 3-byte header each, plus values):
///     7 * 3                     = 21
///   + 4+4+4 (To, From, Id)      = 12
///   + 1*4   (four u8 fields)    =  4
///                               = 37 bytes
/// Optional fields, which must ALSO fit so a position/telemetry packet is not
/// rejected at the last moment:
///     3 + 12 (Position)         = 15
///     3 +  9 (Telemetry)        = 12
///                               = 27 bytes
/// CRC-32 trailer                =  4 bytes
/// 16-byte header                = 16 bytes
/// Non-payload budget total      = 37 + 27 + 4 + 16 = 84 bytes
///
/// A payload of L bytes occupies 3*ceil(L/64) + L bytes of TLV (the payload is
/// split into records of at most kTlvMaxValueLen), so the constraint is
///     84 + 3*ceil(L/64) + L <= 255
/// whose largest solution is L = 162. 160 is used so the number is round and the
/// remaining margin is explicit. The suite asserts the invariant directly (a
/// kMaxPayloadLen packet must encode, seal and fit one LoRa frame), so this
/// constant cannot silently drift away from the encoder.
constexpr size_t kMaxPayloadLen = 160;

/// Broadcast address, upstream NODENUM_BROADCAST.
constexpr uint32_t kBroadcastNode = 0xFFFFFFFFu;

/// Hop fields live in three bits, so 7 is a hard ceiling.
/// docs/configuration/radio/lora.mdx: "Maximum number of hops. This can't be
/// greater than 7. Default is 3". Upstream mesh.proto: `uint32 hop_limit = 9;`
/// is the PROTOBUF default before it is packed into those bits.
constexpr uint8_t kMaxHopLimit = 7;
constexpr uint8_t kDefaultHopLimit = 3;

// Flag bit positions, upstream PacketHeader/doc.
constexpr uint8_t kFlagHopLimitMask = 0x07;
constexpr uint8_t kFlagWantAckMask = 0x08;
constexpr uint8_t kFlagViaMqttMask = 0x10;
constexpr uint8_t kFlagHopStartMask = 0xE0;
constexpr uint8_t kFlagHopStartShift = 5;

/// Optional position fix. Field names mirror mesh.proto Position.
///
/// UNVERIFIED: the integer scaling here (1e7 degrees, millimetres of altitude)
/// is OUR choice, not a verified wire-format detail. It is a compact local
/// representation; if this ever needs to interoperate with a real Meshtastic
/// node the scaling must be checked against mesh.proto's `sfixed32 latitude_i`.
struct GeoPosition {
  int32_t lat_1e7 = 0;  // degrees * 1e7
  int32_t lon_1e7 = 0;  // degrees * 1e7
  int32_t alt_mm = 0;   // metres * 1000
};

/// Optional telemetry fields. Names mirror meshtastic Telemetry/DeviceMetrics.
/// UNVERIFIED: this is a local selection of fields, not the full proto.
struct Telemetry {
  uint16_t battery_mv = 0;
  int16_t temp_cc = 0;  // degrees Celsius * 100
  uint8_t sats = 0;
  uint32_t uptime_s = 0;
};

/// A Meshtastic mesh packet, decoded.
struct MeshPacket {
  uint32_t to = kBroadcastNode;
  uint32_t from = 0;
  uint32_t id = 0;  // upstream: PacketId is uint32 on the wire

  uint8_t flags = 0;
  uint8_t channel = 0;    // wire value is the 8-bit CHANNEL HASH, not an index
  uint8_t next_hop = 0;
  uint8_t relay_node = 0;

  // hop_limit and hop_start both live inside `flags`. Encapsulating them behind
  // accessors is the whole point: the 3-bit packing bug is easy to write and
  // hard to see, and this is a flight computer where a hop-limit bug quietly
  // turns into a broadcast storm.
  uint8_t hop_limit() const {
    return (uint8_t)(flags & kFlagHopLimitMask);
  }
  void set_hop_limit(uint8_t v) {
    if (v > kMaxHopLimit) v = kMaxHopLimit;  // clamp, never spill into want_ack
    flags = (uint8_t)((flags & ~kFlagHopLimitMask) | (v & kFlagHopLimitMask));
  }
  uint8_t hop_start() const {
    return (uint8_t)((flags & kFlagHopStartMask) >> kFlagHopStartShift);
  }
  void set_hop_start(uint8_t v) {
    if (v > kMaxHopLimit) v = kMaxHopLimit;
    flags = (uint8_t)((flags & ~kFlagHopStartMask) |
                      ((v << kFlagHopStartShift) & kFlagHopStartMask));
  }
  bool want_ack() const { return (flags & kFlagWantAckMask) != 0; }
  void set_want_ack(bool v) {
    flags = (uint8_t)(v ? (flags | kFlagWantAckMask)
                        : (flags & (uint8_t)~kFlagWantAckMask));
  }
  bool via_mqtt() const { return (flags & kFlagViaMqttMask) != 0; }
  void set_via_mqtt(bool v) {
    flags = (uint8_t)(v ? (flags | kFlagViaMqttMask)
                        : (flags & (uint8_t)~kFlagViaMqttMask));
  }

  std::vector<uint8_t> payload;

  bool has_position = false;
  GeoPosition position;
  bool has_telemetry = false;
  Telemetry telemetry;
};

/// Serialise header[0..16) of the packet. Exactly kHeaderLength bytes.
///
/// UNVERIFIED: upstream does NOT encrypt this header - only the payload that
/// follows it, which is why `channel` (the hash) and the hop fields are visible
/// to every relay. That is reproduced here on purpose.
void encode_header(const MeshPacket &p, uint8_t *out);

/// Decode a header from at least kHeaderLength bytes.
enum class DecodeStatus : uint8_t {
  Ok = 0,
  Truncated,
  Malformed,
  Oversized,
  Duplicate,
  NoSpace,
  BadValue,
};

DecodeStatus decode_header(const uint8_t *in, size_t len, MeshPacket *out);

}  // namespace meshtastic
}  // namespace balloon
