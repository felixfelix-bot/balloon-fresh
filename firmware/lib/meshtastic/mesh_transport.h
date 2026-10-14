// L4 (Meshtastic) - the transport layer that binds the codec, channel keys,
// AES-CTR sealing and the flooding policy to the FROZEN radio HAL.
//
// CONTRACT USED (firmware/lib/radio_core/radio_hal.h):
//   * acquire() before ANY configure()/send()/receive(); release() when done.
//     Meshtastic, LoRaWAN and MeshCore share ONE radio on the hub v9 board, so
//     acquire/release is not ceremony - it is what stops the stacks fighting
//     over SPI and the TCXO.
//   * read_config() is the read-back verification path and is exercised in the
//     tests rather than trusted.
//   * receive() returning Ok with 0 bytes means "nothing pending", which is NOT
//     an error and NOT an empty packet.
//
// WIRE FRAME produced by send():
//
//     +--------------------------+------------------------------------+
//     | 16-byte PacketHeader     | sealed payload                     |
//     | byte-compatible with     | AES-CTR(TLV frame) || LE32(crc32)  |
//     | Meshtastic               | OUR container, NOT theirs          |
//     +--------------------------+------------------------------------+
//
// So the HEADER half of this frame is Meshtastic-compatible and the payload half
// is not (it would be a protobuf `Data` message upstream). Do not describe this
// as a Meshtastic-compatible implementation; describe it as a Meshtastic-style
// layer reusing Meshtastic's header, key expansion, channel hash and hop policy.
#pragma once

#include "../radio_core/radio_hal.h"

#include "mesh_channel.h"
#include "mesh_crypto.h"
#include "mesh_flood.h"
#include "mesh_packet.h"

namespace balloon {
namespace meshtastic {

// kMaxPayloadLen lives in mesh_packet.h, next to the frame budget it derives
// from, so there is exactly one definition of it.

/// Channel identity: a name plus the stored PSK, before expansion.
///
/// The name is a plain char array rather than std::string because it also
/// participates in the channel hash and must be byte-stable.
struct ChannelConfig {
  char name[16] = {};
  uint8_t psk[32] = {};
  size_t psk_len = 0;
};

/// What the receiver decided to do with a frame. Returning a decision, rather
/// than a bool, is what makes the "why" testable: a filter that quietly drops
/// everything and a filter that works look identical from the outside
/// otherwise.
enum class RxAction : uint8_t {
  Deliver = 0,          // decoded, authenticated by the CRC trailer, for us
  FilterChannelHash,    // different channel hash: rejected BEFORE any AES work
  FilterDuplicate,      // (from,id) already seen inside the duplicate window
  FilterNotForUs,       // a unicast addressed to another node
  FilterBadFrame,       // header or sealed payload malformed
};

struct RxOutcome {
  RxAction action = RxAction::FilterBadFrame;
  bool deliver = false;
  bool rebroadcast = false;
  uint32_t rebroadcast_delay_ms = 0;
  MeshPacket packet;
};

/// The L4 transport. One instance owns the radio through the HAL for its
/// lifetime between begin() and end().
class MeshTransport {
 public:
  MeshTransport(radio::RadioHal *hal, const ChannelConfig &channel,
                const FloodPolicy &policy = FloodPolicy(),
                RandomSource *rng = nullptr);
  ~MeshTransport();

  MeshTransport(const MeshTransport &) = delete;
  MeshTransport &operator=(const MeshTransport &) = delete;

  // ---- lifecycle

  /// Acquire the radio, put it in continuous RX and configure LoRa.
  /// Idempotent: a second begin() while already acquired returns Ok.
  radio::Result begin(uint32_t timeout_ms);

  /// Release the radio. Safe to call when not acquired.
  radio::Result end();

  bool acquired() const;

  /// Try to take the radio WITHOUT changing our own state, to prove the HAL's
  /// Busy/Timeout paths are reachable from this layer. Useful in a preflight
  /// check: "is the radio healthy?" without disturbing the current owner.
  radio::Result probe_acquire(uint32_t timeout_ms);

  /// Configure the HAL for LoRa and read the config back. The read-back is not
  /// optional: a silent configure failure is exactly the failure that costs a
  /// flight, and the HAL exposes read_config() for this reason.
  radio::Result apply_radio_config(uint32_t frequency_hz, uint8_t sf, uint8_t cr,
                                   int8_t tx_power_dbm, uint32_t bandwidth_hz = 125000,
                                   uint16_t preamble_symbols = 16);

  // ---- channel identity

  /// The 8-bit channel hash that goes in the header and is used to filter
  /// inbound frames before decryption.
  uint8_t channel_hash() const;
  const CryptoKey &key() const;
  const char *channel_name() const;

  uint32_t node_num() const { return node_num_; }
  void set_node_num(uint32_t n) { node_num_ = n; }

  // ---- data path

  /// Encode, seal and transmit. Returns BadArgument for a payload over
  /// kMaxPayloadLen or a frame that would not fit 255 bytes; NotAcquired when
  /// the radio is not held. On any failure NOTHING is handed to the HAL.
  radio::Result send(const MeshPacket &p, uint32_t now_ms, uint32_t timeout_ms);

  /// Pull one frame off the radio, verify it, and decode it.
  ///   Ok + payload empty  -> nothing was pending
  ///   BadArgument         -> a frame arrived but was not accepted (wrong
  ///                          channel, wrong key, corrupt, malformed). The
  ///                          outcome is recorded so the caller can look up WHY
  ///                          with last_rx().
  radio::Result receive(MeshPacket *out, uint32_t timeout_ms);

  /// Decide what to do with a decoded packet, without touching the radio: this
  /// is the policy half of receive(), split out so it can be tested against a
  /// fake clock instead of a fake radio.
  RxOutcome classify(const MeshPacket &p, uint32_t now_ms);

  /// Outcome of the most recent receive(), for diagnostics.
  const RxOutcome &last_rx() const { return last_rx_; }

  /// Duplicate history, exposed for tests and for a status display.
  DuplicateSuppressor &duplicates() { return dup_; }

 private:
  radio::RadioHal *hal_;
  ChannelConfig channel_;
  CryptoKey key_;
  FloodPolicy policy_;
  RandomSource *rng_;
  bool own_rng_ = false;
  uint32_t node_num_ = 0x00000001u;
  bool acquired_ = false;
  DuplicateSuppressor dup_;
  RxOutcome last_rx_;
};

}  // namespace meshtastic
}  // namespace balloon
