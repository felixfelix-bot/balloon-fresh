// MeshCore-style transport core — L1 packet framing (packet header codec).
//
// @radio_hal: RadioHal::send()/receive() carry exactly ONE of these frames as
// their byte string; the header is the first thing a peer's stack decodes. This
// header is what a radio driver frames onto the air. It is the frozen
// radio_core/radio_hal.h contract that decides where the bytes go:
//   #include "../radio_core/radio_hal.h"   ->  radio::RadioHal, radio::Result
//
// Pure logic: no radio, no state, no I/O -- so it is exhaustively host-testable.
//
// Wire format (little-endian, one byte per field):
//   [0]      version       MESH_WIRE_VERSION
//   [1]      type          MeshType
//   [2]      src           source node id (never MESH_BROADCAST)
//   [3]      dst           destination node id (MESH_BROADCAST = flood)
//   [4..5]   pkt_id        u16 LE
//   [6]      hop_limit     rebroadcasts still permitted (0 = this node is final)
//   [7]      frag_index    0-based fragment index
//   [8]      frag_count    1 = unfragmented
//   [9]      payload_len   payload bytes that follow
//   [10..]   payload
//
// STRICTNESS CONTRACT: a frame whose buffer is shorter than the header, whose
// header claims more payload than the buffer holds (truncated), or that carries
// trailing bytes beyond what the header declares (over-long), is REJECTED as a
// whole. No field is ever handed back from a frame that failed validation --
// partial parsing is how a mesh forwards garbage.
#pragma once

#include <cstddef>
#include <cstdint>

namespace balloon {
namespace mesh {

// Bump on ANY framing change: peers with mismatched versions must reject the
// frame rather than reinterpret its bytes.
constexpr uint8_t MESH_WIRE_VERSION = 1;

// Size of the header with a zero-length payload. A well-formed frame is exactly
// MESH_HEADER_SIZE + header.payload_len bytes -- no more, no less.
constexpr size_t MESH_HEADER_SIZE = 10;

// Payload a single frame may carry (the frame MTU minus framing).
constexpr size_t MESH_MAX_PAYLOAD = 64;
// Largest application datagram we are willing to fragment across frames.
constexpr size_t MESH_MAX_DATAGRAM = 512;
// Largest fragment count we accept, so reassembly memory is bounded.
constexpr uint8_t MESH_MAX_FRAGS = 64;

// One byte of node id: hub v9 has one radio and far fewer than 256 peers.
using NodeId = uint8_t;
// Destination that means "every node in the mesh" (flood).
constexpr NodeId MESH_BROADCAST = 0xFF;

enum class MeshType : uint8_t {
  Data = 0,   // application payload (possibly fragmented)
  Ack = 1,    // end-to-end acknowledgement, never forwarded
  Hello = 2,  // neighbour beacon, flooded but no ACK
};

struct Header {
  uint8_t version;
  MeshType type;
  NodeId src;
  NodeId dst;
  uint16_t pkt_id;
  uint8_t hop_limit;
  uint8_t frag_index;
  uint8_t frag_count;
  uint8_t payload_len;
};

enum class CodecResult : uint8_t {
  Ok = 0,
  BufferTooSmall,  // buffer shorter than MESH_HEADER_SIZE
  Truncated,       // header declares more payload than the buffer holds
  Overlong,        // trailing bytes past the declared frame, or payload_len > MTU
  BadVersion,      // version byte is not MESH_WIRE_VERSION
  BadType,         // type byte is not a known MeshType
  BadFrag,         // frag_count 0, > MESH_MAX_FRAGS, or frag_index >= frag_count
  BadSource,       // src is MESH_BROADCAST, which can never be a sender
};

// Exact frame size (MESH_HEADER_SIZE + payload_len) of a well-formed header, or
// 0 if this buffer is not a valid header. Nothing is reported for a rejected
// frame -- not even a partially decoded length.
size_t header_frame_size(const uint8_t *buf, size_t len);

// Strict decode. On Ok: *out is filled, *payload points at buf + MESH_HEADER_SIZE
// (inside the caller's buffer) and *payload_len is header.payload_len. `size`
// MUST be the exact frame size: a truncated or over-long `size` is rejected.
CodecResult decode_header(const uint8_t *buf, size_t size, Header *out,
                          const uint8_t **payload, size_t *payload_len);

// Encode. Returns Ok and sets *written (== MESH_HEADER_SIZE + h.payload_len) only
// for a valid header that fits in `cap`; otherwise changes nothing and returns a
// CodecResult explaining the refusal.
CodecResult encode_header(const Header &h, uint8_t *out, size_t cap,
                          size_t *written);

// True if h is internally consistent (version, type, frag fields, MTU bounds).
bool header_is_valid(const Header &h);

}  // namespace mesh
}  // namespace balloon
