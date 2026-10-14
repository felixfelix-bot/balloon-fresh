// L1 packet codec. Strict by construction: nothing is decoded unless the whole
// frame validates, so a mesh never forwards a partially-parsed header.
#include "meshcodec.h"

namespace balloon {
namespace mesh {
namespace {

inline uint16_t rd16(const uint8_t *p) {
  return (uint16_t)(p[0] | ((uint16_t)p[1] << 8));
}
inline void wr16(uint8_t *p, uint16_t v) {
  p[0] = (uint8_t)(v & 0xFF);
  p[1] = (uint8_t)((v >> 8) & 0xFF);
}

bool known_type(uint8_t t) {
  return t == (uint8_t)MeshType::Data || t == (uint8_t)MeshType::Ack ||
         t == (uint8_t)MeshType::Hello;
}

}  // namespace

bool header_is_valid(const Header &h) {
  if (h.version != MESH_WIRE_VERSION) return false;
  if (!known_type((uint8_t)h.type)) return false;
  if (h.src == MESH_BROADCAST) return false;  // a broadcast can never be a sender
  if (h.payload_len > MESH_MAX_PAYLOAD) return false;
  if (h.frag_count == 0 || h.frag_count > MESH_MAX_FRAGS) return false;
  if (h.frag_index >= h.frag_count) return false;
  return true;
}

size_t header_frame_size(const uint8_t *buf, size_t len) {
  if (buf == nullptr || len < MESH_HEADER_SIZE) return 0;
  if (buf[0] != MESH_WIRE_VERSION) return 0;
  if (!known_type(buf[1])) return 0;
  if (buf[2] == MESH_BROADCAST) return 0;
  if (buf[9] > MESH_MAX_PAYLOAD) return 0;
  if (buf[8] == 0 || buf[8] > MESH_MAX_FRAGS) return 0;
  if (buf[7] >= buf[8]) return 0;
  return MESH_HEADER_SIZE + (size_t)buf[9];
}

CodecResult decode_header(const uint8_t *buf, size_t size, Header *out,
                          const uint8_t **payload, size_t *payload_len) {
  if (out) *out = Header{};
  if (payload) *payload = nullptr;
  if (payload_len) *payload_len = 0;

  if (buf == nullptr || size < MESH_HEADER_SIZE) return CodecResult::BufferTooSmall;
  // Whole-frame checks in a fixed order so the reported reason is stable.
  if (buf[0] != MESH_WIRE_VERSION) return CodecResult::BadVersion;
  if (!known_type(buf[1])) return CodecResult::BadType;
  if (buf[2] == MESH_BROADCAST) return CodecResult::BadSource;
  if (buf[8] == 0 || buf[8] > MESH_MAX_FRAGS || buf[7] >= buf[8])
    return CodecResult::BadFrag;
  const size_t declared_payload = (size_t)buf[9];
  // An over-MTU declaration cannot be a frame we would ever have sent, and it
  // cannot be satisfied by any legal frame, so it is over-long rather than
  // truncated.
  if (declared_payload > MESH_MAX_PAYLOAD) return CodecResult::Overlong;
  const size_t frame = MESH_HEADER_SIZE + declared_payload;
  if (size < frame) return CodecResult::Truncated;   // header claims more bytes
  if (size > frame) return CodecResult::Overlong;    // trailing bytes

  // Everything validated: only now are fields and payload handed back.
  Header h{};
  h.version = buf[0];
  h.type = (MeshType)buf[1];
  h.src = buf[2];
  h.dst = buf[3];
  h.pkt_id = rd16(buf + 4);
  h.hop_limit = buf[6];
  h.frag_index = buf[7];
  h.frag_count = buf[8];
  h.payload_len = buf[9];
  if (!header_is_valid(h)) return CodecResult::BadFrag;  // belt and braces
  if (out) *out = h;
  if (payload) *payload = buf + MESH_HEADER_SIZE;
  if (payload_len) *payload_len = declared_payload;
  return CodecResult::Ok;
}

CodecResult encode_header(const Header &h, uint8_t *out, size_t cap,
                          size_t *written) {
  if (written) *written = 0;
  if (h.version != MESH_WIRE_VERSION) return CodecResult::BadVersion;
  if (!known_type((uint8_t)h.type)) return CodecResult::BadType;
  if (h.src == MESH_BROADCAST) return CodecResult::BadSource;
  if (h.frag_count == 0 || h.frag_count > MESH_MAX_FRAGS || h.frag_index >= h.frag_count)
    return CodecResult::BadFrag;
  if (h.payload_len > MESH_MAX_PAYLOAD) return CodecResult::Overlong;
  const size_t frame = MESH_HEADER_SIZE + (size_t)h.payload_len;
  if (out == nullptr || cap < frame) return CodecResult::BufferTooSmall;

  out[0] = h.version;
  out[1] = (uint8_t)h.type;
  out[2] = h.src;
  out[3] = h.dst;
  wr16(out + 4, h.pkt_id);
  out[6] = h.hop_limit;
  out[7] = h.frag_index;
  out[8] = h.frag_count;
  out[9] = h.payload_len;
  if (written) *written = frame;
  return CodecResult::Ok;
}

}  // namespace mesh
}  // namespace balloon
