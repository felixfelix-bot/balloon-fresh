#include "mesh_transport.h"

#include "mesh_tlv.h"

#include <cstring>

namespace balloon {
namespace meshtastic {

MeshTransport::MeshTransport(radio::RadioHal *hal, const ChannelConfig &channel,
                             const FloodPolicy &policy, RandomSource *rng)
    : hal_(hal), channel_(channel), policy_(policy), rng_(rng),
      dup_(policy.duplicate_window_ms) {
  if (rng_ == nullptr) {
    // Own a deterministic generator so a caller cannot forget one. A flight
    // node wants reproducible jitter for a test, but it must never be a null
    // dereference in production.
    rng_ = new XorshiftRandom(0x2545F491u);
    own_rng_ = true;
  }
  expand_psk(channel_.psk, channel_.psk_len, &key_);
}

MeshTransport::~MeshTransport() {
  if (own_rng_) {
    delete rng_;
    rng_ = nullptr;
  }
}

radio::Result MeshTransport::begin(uint32_t timeout_ms) {
  if (hal_ == nullptr) return radio::Result::BadArgument;
  if (acquired_) return radio::Result::Ok;  // idempotent
  const radio::Result r = hal_->acquire(timeout_ms);
  if (r != radio::Result::Ok) return r;
  acquired_ = true;
  return radio::Result::Ok;
}

radio::Result MeshTransport::end() {
  if (hal_ == nullptr) return radio::Result::BadArgument;
  if (!acquired_) return radio::Result::Ok;
  acquired_ = false;
  return hal_->release();
}

bool MeshTransport::acquired() const { return acquired_; }

radio::Result MeshTransport::probe_acquire(uint32_t timeout_ms) {
  if (hal_ == nullptr) return radio::Result::BadArgument;
  const radio::Result r = hal_->acquire(timeout_ms);
  if (r == radio::Result::Ok) {
    // We got it by accident (nobody else held it): give it straight back so the
    // probe has no side effect on ownership.
    const radio::Result rel = hal_->release();
    if (rel != radio::Result::Ok) return rel;
  }
  return r;
}

radio::Result MeshTransport::apply_radio_config(uint32_t frequency_hz, uint8_t sf,
                                                uint8_t cr, int8_t tx_power_dbm,
                                                uint32_t bandwidth_hz,
                                                uint16_t preamble_symbols) {
  if (hal_ == nullptr) return radio::Result::BadArgument;
  if (!acquired_) return radio::Result::NotAcquired;
  if (sf < 5 || sf > 12) return radio::Result::BadArgument;  // HAL contract: 5..12
  if (cr < 5 || cr > 8) return radio::Result::BadArgument;   // 5..8 => 4/5..4/8

  radio::Config cfg{};
  cfg.modulation = radio::Modulation::Lora;
  cfg.frequency_hz = frequency_hz;
  cfg.bandwidth_hz = bandwidth_hz;
  cfg.spreading_factor = sf;
  cfg.coding_rate = cr;
  cfg.tx_power_dbm = tx_power_dbm;
  cfg.preamble_symbols = preamble_symbols;
  cfg.crc_on = true;  // the LoRa PHY CRC; separate from our payload CRC

  const radio::Result r = hal_->configure(cfg);
  if (r != radio::Result::Ok) return r;

  radio::Config rb{};
  const radio::Result rr = hal_->read_config(&rb);
  if (rr != radio::Result::Ok) return rr;
  if (rb.frequency_hz != cfg.frequency_hz ||
      rb.spreading_factor != cfg.spreading_factor ||
      rb.coding_rate != cfg.coding_rate || rb.tx_power_dbm != cfg.tx_power_dbm ||
      rb.modulation != cfg.modulation) {
    // A configure() that reports Ok but does not stick is the failure mode the
    // frozen contract added read_config() for. Report it instead of flying on.
    return radio::Result::BusError;
  }

  const radio::Result rc = hal_->set_rx_continuous(true);
  if (rc != radio::Result::Ok) return rc;
  return radio::Result::Ok;
}

uint8_t MeshTransport::channel_hash() const {
  return balloon::meshtastic::channel_hash(channel_.name, key_);
}

const CryptoKey &MeshTransport::key() const { return key_; }

const char *MeshTransport::channel_name() const { return channel_.name; }

radio::Result MeshTransport::send(const MeshPacket &p, uint32_t /*now_ms*/,
                                  uint32_t /*timeout_ms*/) {
  if (hal_ == nullptr) return radio::Result::BadArgument;
  if (!acquired_) return radio::Result::NotAcquired;
  if (p.payload.size() > kMaxPayloadLen) return radio::Result::BadArgument;

  MeshPacket tx = p;
  // The header carries the channel HASH, not the channel index. Upstream does
  // the same substitution right before encryption ("Now that we are encrypting
  // the packet channel should be the hash").
  tx.channel = channel_hash();
  // The sender's address is the header's `from`; the nonce uses it, so it must
  // be settled before sealing.
  if (tx.from == 0) tx.from = node_num_;

  uint8_t plain[512];
  size_t plain_len = 0;
  if (tlv_encode(tx, plain, sizeof(plain), &plain_len) != EncodeStatus::Ok) {
    return radio::Result::BadArgument;
  }

  std::vector<uint8_t> sealed;
  if (seal_payload(key_, tx.id, tx.from, plain, plain_len, &sealed) !=
      SealStatus::Ok) {
    return radio::Result::BadArgument;
  }

  if (kHeaderLength + sealed.size() > kMaxLoraPayload) {
    return radio::Result::BadArgument;  // would not fit one LoRa frame
  }

  std::vector<uint8_t> frame(kHeaderLength + sealed.size());
  encode_header(tx, frame.data());
  std::memcpy(frame.data() + kHeaderLength, sealed.data(), sealed.size());

  return hal_->send(frame.data(), frame.size());
}

radio::Result MeshTransport::receive(MeshPacket *out, uint32_t timeout_ms) {
  if (!acquired_) return radio::Result::NotAcquired;
  if (hal_ == nullptr || out == nullptr) return radio::Result::BadArgument;

  uint8_t frame[kMaxLoraPayload + 1];
  size_t frame_len = 0;
  const radio::Result r = hal_->receive(frame, sizeof(frame), &frame_len, timeout_ms);
  if (r != radio::Result::Ok) return r;
  if (frame_len == 0) {
    // Ok + 0 means nothing pending: an empty result, NOT a failure.
    *out = MeshPacket();
    last_rx_ = RxOutcome();
    last_rx_.action = RxAction::Deliver;
    return radio::Result::Ok;
  }

  *out = MeshPacket();
  RxOutcome outcome;

  if (frame_len < kHeaderLength) {
    outcome.action = RxAction::FilterBadFrame;
    last_rx_ = outcome;
    return radio::Result::BadArgument;
  }

  MeshPacket hdr;
  if (decode_header(frame, frame_len, &hdr) != DecodeStatus::Ok) {
    outcome.action = RxAction::FilterBadFrame;
    last_rx_ = outcome;
    return radio::Result::BadArgument;
  }

  // The channel hash is checked BEFORE any AES work is attempted. That is the
  // entire purpose of the hash: a relay or a node on another channel must not
  // make us run a cipher for every frame in earshot.
  if (hdr.channel != channel_hash()) {
    outcome.action = RxAction::FilterChannelHash;
    outcome.packet = hdr;
    last_rx_ = outcome;
    return radio::Result::BadArgument;
  }

  const uint8_t *sealed = frame + kHeaderLength;
  const size_t sealed_len = frame_len - kHeaderLength;

  std::vector<uint8_t> plain;
  const SealStatus ss = open_payload(key_, hdr.id, hdr.from, sealed, sealed_len, &plain);
  if (ss != SealStatus::Ok) {
    // Wrong key, wrong nonce or corruption. The plaintext is NOT handed back.
    outcome.action = RxAction::FilterBadFrame;
    outcome.packet = hdr;
    last_rx_ = outcome;
    return radio::Result::BadArgument;
  }

  MeshPacket decoded;
  if (tlv_decode(plain.data(), plain.size(), &decoded) != DecodeStatus::Ok) {
    outcome.action = RxAction::FilterBadFrame;
    outcome.packet = hdr;
    last_rx_ = outcome;
    return radio::Result::BadArgument;
  }

  // Routing-visible fields come from the CLEARTEXT header, because those are the
  // ones a relay is allowed to rewrite (it stamps next_hop/relay_node and
  // decrements the hop fields). The sealed body carries the rest.
  decoded.channel = hdr.channel;
  decoded.next_hop = hdr.next_hop;
  decoded.relay_node = hdr.relay_node;

  outcome.packet = decoded;
  outcome = classify(decoded, 0);
  last_rx_ = outcome;
  *out = decoded;

  if (outcome.action == RxAction::FilterDuplicate) {
    // A duplicate is a normal event on a flooded mesh, and the caller asked for
    // one frame: report "nothing usable" rather than an error.
    *out = MeshPacket();
    return radio::Result::Ok;
  }
  return radio::Result::Ok;
}

RxOutcome MeshTransport::classify(const MeshPacket &p, uint32_t now_ms) {
  RxOutcome o;
  o.packet = p;

  const bool ours = (p.from == node_num_);

  if (p.channel != channel_hash()) {
    o.action = RxAction::FilterChannelHash;
    o.deliver = false;
    // Upstream relays frames it cannot read, and so do we: a relay on the
    // balloon's fallback path exists to carry OTHER people's traffic. Whether we
    // actually transmit is still bounded by the hop policy.
    o.rebroadcast = should_rebroadcast(p, ours);
    return o;
  }

  if (!ours && p.to != kBroadcastNode && p.to != node_num_) {
    // A unicast for somebody else: relay it, but never hand it to the
    // application - we cannot read it anyway, and pretending otherwise would be
    // the bug that matters.
    o.action = RxAction::FilterNotForUs;
    o.deliver = false;
    o.rebroadcast = should_rebroadcast(p, ours);
    return o;
  }

  if (!ours && !dup_.should_relay(p, now_ms)) {
    // We already have this (from,id): a redundant copy. If we had a rebroadcast
    // scheduled, hearing the neighbour's copy is what cancels it.
    dup_.cancel_pending(p, now_ms);
    o.action = RxAction::FilterDuplicate;
    o.deliver = false;
    o.rebroadcast = false;
    return o;
  }

  o.action = RxAction::Deliver;
  o.deliver = true;
  o.rebroadcast = should_rebroadcast(p, ours);
  if (o.rebroadcast) {
    int16_t snr = 0;
    if (hal_ != nullptr) {
      int8_t s = 0;
      if (hal_->get_snr_db(&s) == radio::Result::Ok) snr = s;
    }
    o.rebroadcast_delay_ms =
        rebroadcast_delay_ms(policy_, snr, /*is_router=*/false, rng_);
  }
  return o;
}

}  // namespace meshtastic
}  // namespace balloon
