#include "mesh_packet.h"

#include <cstring>

namespace balloon {
namespace meshtastic {
namespace {

void put_le32(uint8_t *p, uint32_t v) {
  p[0] = (uint8_t)(v & 0xFF);
  p[1] = (uint8_t)((v >> 8) & 0xFF);
  p[2] = (uint8_t)((v >> 16) & 0xFF);
  p[3] = (uint8_t)((v >> 24) & 0xFF);
}

uint32_t get_le32(const uint8_t *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}

}  // namespace

void encode_header(const MeshPacket &p, uint8_t *out) {
  put_le32(out + 0, p.to);
  put_le32(out + 4, p.from);
  put_le32(out + 8, p.id);
  out[12] = p.flags;
  out[13] = p.channel;
  out[14] = p.next_hop;
  out[15] = p.relay_node;
}

DecodeStatus decode_header(const uint8_t *in, size_t len, MeshPacket *out) {
  if (in == nullptr || out == nullptr) return DecodeStatus::Malformed;
  if (len < kHeaderLength) return DecodeStatus::Truncated;
  out->to = get_le32(in + 0);
  out->from = get_le32(in + 4);
  out->id = get_le32(in + 8);
  out->flags = in[12];
  out->channel = in[13];
  out->next_hop = in[14];
  out->relay_node = in[15];
  return DecodeStatus::Ok;
}

}  // namespace meshtastic
}  // namespace balloon
