#include "mesh_tlv.h"

#include <cstring>

namespace balloon {
namespace meshtastic {
namespace {

// A writer whose record() is ATOMIC: it either writes a whole record or nothing
// at all. This matters because the obvious implementation (write the header,
// then write the value) leaves a half-written record in the buffer when the
// value does not fit, and a half-written record is worse than no record - it
// would go out on the air as a valid-looking prefix.
//
// The earlier version of this class had a real bug: the value-copy helper never
// advanced the write offset, so every record emitted its 3-byte header and no
// value. The test caught it (a 77-byte expected frame came out at 30 bytes and
// decoded as Truncated). It is written as one operation now so that class of bug
// cannot recur.
class Writer {
 public:
  Writer(uint8_t *buf, size_t cap) : buf_(buf), cap_(cap) {}

  bool record(FieldId id, FieldType type, const uint8_t *value, uint8_t len) {
    if (len > kTlvMaxValueLen) return false;
    if (n_ + 3 + (size_t)len > cap_) return false;  // all-or-nothing
    if (len > 0 && value == nullptr) return false;
    buf_[n_++] = (uint8_t)id;
    buf_[n_++] = (uint8_t)type;
    buf_[n_++] = len;
    if (len > 0) std::memcpy(buf_ + n_, value, len);
    n_ += len;
    return true;
  }

  size_t size() const { return n_; }

 private:
  uint8_t *buf_;
  size_t cap_;
  size_t n_ = 0;
};

uint32_t rd_le32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}

void wr_le32(uint8_t *p, uint32_t v) {
  p[0] = (uint8_t)(v & 0xFF);
  p[1] = (uint8_t)((v >> 8) & 0xFF);
  p[2] = (uint8_t)((v >> 16) & 0xFF);
  p[3] = (uint8_t)((v >> 24) & 0xFF);
}

void wr_le16(uint8_t *p, uint16_t v) {
  p[0] = (uint8_t)(v & 0xFF);
  p[1] = (uint8_t)((v >> 8) & 0xFF);
}

uint16_t rd_le16(const uint8_t *p) {
  return (uint16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

/// Storage for the twelve bytes of a Position value, so the writer does not
/// need a temporary vector.
struct PosBuf {
  uint8_t b[12];
};

bool known_id(uint8_t id) {
  return id >= (uint8_t)FieldId::To && id <= (uint8_t)FieldId::Telemetry;
}

}  // namespace

size_t tlv_worst_case_size(const MeshPacket &p) {
  if (p.payload.size() > kMaxPayloadLen) return 0;
  size_t n = 0;
  n += 3 + 4;  // To
  n += 3 + 4;  // From
  n += 3 + 4;  // Id
  n += 3 + 1;  // Flags
  n += 3 + 1;  // Channel
  n += 3 + 1;  // NextHop
  n += 3 + 1;  // RelayNode
  // The payload may need to be split: kTlvMaxValueLen is 64 and the payload can
  // be longer. See the encode loop; this counts the split records.
  n += ((p.payload.size() + kTlvMaxValueLen - 1) / kTlvMaxValueLen) * 3 +
       p.payload.size();
  if (p.has_position) n += 3 + 12;
  if (p.has_telemetry) n += 3 + 9;
  return n;
}

EncodeStatus tlv_encode(const MeshPacket &p, uint8_t *out, size_t out_cap,
                        size_t *out_len) {
  if (out == nullptr || out_len == nullptr) return EncodeStatus::BadValue;
  if (p.payload.size() > kMaxPayloadLen) return EncodeStatus::BadValue;

  const size_t need = tlv_worst_case_size(p);
  if (need == 0 || need > out_cap) return EncodeStatus::NoSpace;

  Writer w(out, out_cap);
  uint8_t tmp[16];

  wr_le32(tmp, p.to);
  if (!w.record(FieldId::To, FieldType::U32, tmp, 4)) return EncodeStatus::NoSpace;
  wr_le32(tmp, p.from);
  if (!w.record(FieldId::From, FieldType::U32, tmp, 4)) return EncodeStatus::NoSpace;
  wr_le32(tmp, p.id);
  if (!w.record(FieldId::Id, FieldType::U32, tmp, 4)) return EncodeStatus::NoSpace;
  if (!w.record(FieldId::Flags, FieldType::U8, &p.flags, 1)) return EncodeStatus::NoSpace;
  if (!w.record(FieldId::Channel, FieldType::U8, &p.channel, 1)) return EncodeStatus::NoSpace;
  if (!w.record(FieldId::NextHop, FieldType::U8, &p.next_hop, 1)) return EncodeStatus::NoSpace;
  if (!w.record(FieldId::RelayNode, FieldType::U8, &p.relay_node, 1)) return EncodeStatus::NoSpace;

  // The payload is split across as many Payload records as needed, because a
  // single record's length byte is capped at kTlvMaxValueLen. The decoder
  // CONCATENATES repeated Payload records - which is the one deliberate
  // exception to rule R5, and it is why R5 is only enforced for the fixed-size
  // fields. A payload of at most 64 bytes uses exactly one record, so the
  // common case has no ambiguity at all.
  size_t off = 0;
  while (off < p.payload.size()) {
    const uint16_t remain = (uint16_t)(p.payload.size() - off);
    const uint8_t chunk =
        (uint8_t)(remain > kTlvMaxValueLen ? kTlvMaxValueLen : remain);
    if (!w.record(FieldId::Payload, FieldType::Bytes, p.payload.data() + off, chunk)) {
      return EncodeStatus::NoSpace;
    }
    off += chunk;
  }

  if (p.has_position) {
    uint8_t pb[12];
    wr_le32(pb + 0, (uint32_t)p.position.lat_1e7);
    wr_le32(pb + 4, (uint32_t)p.position.lon_1e7);
    wr_le32(pb + 8, (uint32_t)p.position.alt_mm);
    if (!w.record(FieldId::Position, FieldType::Bytes, pb, 12)) return EncodeStatus::NoSpace;
  }

  if (p.has_telemetry) {
    uint8_t tb[9];
    wr_le16(tb + 0, p.telemetry.battery_mv);
    wr_le16(tb + 2, (uint16_t)p.telemetry.temp_cc);
    tb[4] = p.telemetry.sats;
    wr_le32(tb + 5, p.telemetry.uptime_s);
    if (!w.record(FieldId::Telemetry, FieldType::Bytes, tb, 9)) return EncodeStatus::NoSpace;
  }

  *out_len = w.size();
  return EncodeStatus::Ok;
}

DecodeStatus tlv_decode(const uint8_t *in, size_t len, MeshPacket *out) {
  if (in == nullptr || out == nullptr) return DecodeStatus::Malformed;

  *out = MeshPacket();
  bool seen[16] = {};
  size_t off = 0;

  while (off < len) {
    if (off + 3 > len) return DecodeStatus::Truncated;  // R3
    const uint8_t id = in[off];
    const uint8_t type = in[off + 1];
    const uint8_t vlen = in[off + 2];

    if (id == 0) return DecodeStatus::Malformed;              // R4
    if (vlen > kTlvMaxValueLen) return DecodeStatus::Oversized;  // R2
    if (off + 3 + vlen > len) return DecodeStatus::Truncated;  // R3

    const uint8_t *val = in + off + 3;
    off += 3 + vlen;

    // R1: an unknown id, or a known id carrying an unknown type, is skipped.
    const bool type_known = (type == (uint8_t)FieldType::U8 ||
                             type == (uint8_t)FieldType::U32 ||
                             type == (uint8_t)FieldType::Bytes);
    if (!known_id(id) || !type_known) continue;

    // A known field carrying the WRONG type is a schema violation, not a
    // forward-compatibility case: reject rather than silently skip, because
    // silently skipping a To field would turn into a broadcast.
    FieldType want_type;
    uint8_t want_len;
    switch ((FieldId)id) {
      case FieldId::To:
      case FieldId::From:
      case FieldId::Id:
        want_type = FieldType::U32; want_len = 4; break;
      case FieldId::Flags:
      case FieldId::Channel:
      case FieldId::NextHop:
      case FieldId::RelayNode:
        want_type = FieldType::U8; want_len = 1; break;
      case FieldId::Payload:
        want_type = FieldType::Bytes; want_len = 0; break;  // variable, split
      case FieldId::Position:
        want_type = FieldType::Bytes; want_len = 12; break;
      case FieldId::Telemetry:
        want_type = FieldType::Bytes; want_len = 9; break;
      default:
        continue;
    }
    if (type != (uint8_t)want_type) return DecodeStatus::Malformed;
    if (want_len != 0 && vlen != want_len) return DecodeStatus::Malformed;

    if ((FieldId)id != FieldId::Payload) {
      if (seen[id]) return DecodeStatus::Duplicate;  // R5
      seen[id] = true;
    }

    switch ((FieldId)id) {
      case FieldId::To: out->to = rd_le32(val); break;
      case FieldId::From: out->from = rd_le32(val); break;
      case FieldId::Id: out->id = rd_le32(val); break;
      case FieldId::Flags: out->flags = val[0]; break;
      case FieldId::Channel: out->channel = val[0]; break;
      case FieldId::NextHop: out->next_hop = val[0]; break;
      case FieldId::RelayNode: out->relay_node = val[0]; break;
      case FieldId::Payload:
        out->payload.insert(out->payload.end(), val, val + vlen);
        break;
      case FieldId::Position:
        out->has_position = true;
        out->position.lat_1e7 = (int32_t)rd_le32(val + 0);
        out->position.lon_1e7 = (int32_t)rd_le32(val + 4);
        out->position.alt_mm = (int32_t)rd_le32(val + 8);
        break;
      case FieldId::Telemetry:
        out->has_telemetry = true;
        out->telemetry.battery_mv = rd_le16(val + 0);
        out->telemetry.temp_cc = (int16_t)rd_le16(val + 2);
        out->telemetry.sats = val[4];
        out->telemetry.uptime_s = rd_le32(val + 5);
        break;
      default:
        break;
    }
  }

  // Mandatory core: without these the packet is not addressable and not
  // routable, so an incomplete stream is rejected rather than defaulted.
  if (!seen[(uint8_t)FieldId::To] || !seen[(uint8_t)FieldId::From] ||
      !seen[(uint8_t)FieldId::Id] || !seen[(uint8_t)FieldId::Flags] ||
      !seen[(uint8_t)FieldId::Channel]) {
    return DecodeStatus::Malformed;
  }
  return DecodeStatus::Ok;
}

}  // namespace meshtastic
}  // namespace balloon
