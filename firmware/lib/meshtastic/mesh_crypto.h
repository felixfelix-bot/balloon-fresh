// L4 (Meshtastic) - payload sealing: AES-CTR + nonce construction.
//
// NONCE, from public sources:
//
//   docs/development/reference/encryption-technical.mdx:
//     "The 16-byte nonce is the packet ID as a 64-bit value in bytes 0-7, the
//      sender's node number in bytes 8-11, and the block counter in bytes
//      12-15."
//     "AES-CTR adds no bytes and has no integrity check."
//
//   src/mesh/CryptoEngine.cpp (meshtastic/firmware):
//     void CryptoEngine::initNonce(uint32_t fromNode, uint64_t packetId,
//                                  uint32_t extraNonce) {
//       memset(nonce, 0, sizeof(nonce));
//       memcpy(nonce, &packetId, sizeof(uint64_t));
//       memcpy(nonce + sizeof(uint64_t), &fromNode, sizeof(uint32_t));
//       ...
//     }
//   and the CTR call is `ctr->setIV(_nonce, 16); ctr->setCounterSize(4);`
//
// So the counter block is:
//
//   bytes 0-7   : packet id, LITTLE-ENDIAN (memcpy of a uint64_t on a
//                 little-endian MCU - the firmware is LE on every supported
//                 target; this implementation writes it explicitly)
//   bytes 8-11  : sender node number, LITTLE-ENDIAN
//   bytes 12-15 : block counter, starting at 0
//
// UNVERIFIED DETAIL: the documentation says "the block counter in bytes 12-15"
// without saying how many of those bytes actually count. Upstream configures the
// counter size as 4 bytes, which matches "bytes 12-15" exactly, so the two
// sources agree and this implementation increments the low 4 bytes
// (kCtrCounterBytes = 4 in mesh_aes.h). Nothing observable in a round-trip test
// depends on it for frames shorter than ~64 GiB, so it cannot be proven here;
// it is recorded as verified-by-two-sources rather than proven.
//
// THE INTEGRITY GAP, WHICH IS THE IMPORTANT PART:
//
//   Upstream AES-CTR has NO integrity check and NO authentication, by design.
//   The docs say so outright ("no integrity check"). Plain CTR is malleable: a
//   flipped ciphertext bit flips exactly the same plaintext bit, and a wrong key
//   produces garbage that the receiver CANNOT detect. Meshtastic accepts that
//   trade because the channel key is shared, so any holder could forge a MAC
//   anyway, and it saves 12 bytes per frame on a link where every byte is
//   airtime.
//
//   This library is going on a balloon, where a relay must not forward garbage
//   and must not act on a garbled command. It therefore TRAILS the ciphertext
//   with a 4-byte CRC32 of the PLAINTEXT. This is an ADDITION to the wire
//   format, not part of Meshtastic's, and it costs 4 bytes per frame:
//
//       sealed payload = AES-CTR(plaintext) || LE32(crc32(plaintext))
//
//   A CRC is NOT a MAC: it detects accidents and wrong keys, and it does not
//   stop a deliberate forger who holds the channel key (they can recompute the
//   CRC). It stops the realistic failure here - the wrong channel key, a
//   truncated frame, and a corrupted one - all of which are detected rather than
//   silently accepted, which is what the brief requires of this layer.
#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "mesh_channel.h"

namespace balloon {
namespace meshtastic {

/// Bytes appended after the ciphertext: our CRC32 trailer.
constexpr size_t kSealTrailerLen = 4;

enum class SealStatus : uint8_t {
  Ok = 0,
  IntegrityFailure,  // CRC mismatch: wrong key, wrong nonce, or corruption
  TooShort,          // container smaller than the trailer
  BadArgument,
};

/// Build the 16-byte counter block described above.
void build_nonce(uint32_t packet_id, uint32_t from_node, uint8_t *out16);

/// Encrypt plain into a sealed container. A key with length 0 is a passthrough
/// (upstream: 0-length PSK disables encryption) and adds NO trailer, because a
/// trailer would be meaningless without a key to check it against - and because
/// matching upstream's "0 bytes added" behaviour is more useful than inventing a
/// trailer for the unencrypted case.
SealStatus seal_payload(const CryptoKey &key, uint32_t packet_id,
                        uint32_t from_node, const uint8_t *plain,
                        size_t plain_len, std::vector<uint8_t> *out);

/// Decrypt and verify. Returns IntegrityFailure - and does NOT write plaintext -
/// when the trailer does not match, so a caller can never accidentally act on
/// garbage.
SealStatus open_payload(const CryptoKey &key, uint32_t packet_id,
                        uint32_t from_node, const uint8_t *sealed,
                        size_t sealed_len, std::vector<uint8_t> *out);

/// CRC32 (IEEE 802.3, reflected, init 0xFFFFFFFF, final xor 0xFFFFFFFF).
/// Same polynomial the repo's telemetry module already uses, so a reviewer can
/// cross-check the two implementations against each other.
uint32_t crc32_ieee(const uint8_t *data, size_t len);

}  // namespace meshtastic
}  // namespace balloon
