// MeshCore-style transport core implementation.
//
// The HAL is consumed through ../radio_core/radio_hal.h only. RadioHalFake below
// is this module's own device model, and make_radio_hal is deliberately never
// defined: a test that accidentally linked radio_core would fail at link time
// rather than silently constructing a real device.
#include "mesh.h"

#include <cstring>

namespace balloon {
namespace mesh {
namespace {

// Compose a frame from a header plus payload into `out`. Returns 0 on refusal.
size_t build_frame(const Header &h, const uint8_t *payload, uint8_t *out,
                   size_t cap) {
  size_t w = 0;
  if (encode_header(h, out, cap, &w) != CodecResult::Ok) return 0;
  if (h.payload_len != 0) {
    if (payload == nullptr) return 0;
    std::memcpy(out + MESH_HEADER_SIZE, payload, h.payload_len);
  }
  return w;
}

}  // namespace

// ---------------------------------------------------------------- DupCache --

DupCache::DupCache(size_t capacity) : head_(0), count_(0), evictions_(0) {
  for (size_t i = 0; i < capacity; ++i) {
    Entry e;
    e.used = false;
    e.src = 0;
    e.pkt_id = 0;
    e.frag_index = 0;
    entries_.push_back(e);
  }
}

void DupCache::set_capacity(size_t n) {
  entries_.clear();
  for (size_t i = 0; i < n; ++i) {
    Entry e;
    e.used = false;
    e.src = 0;
    e.pkt_id = 0;
    e.frag_index = 0;
    entries_.push_back(e);
  }
  head_ = 0;
  count_ = 0;
}

bool DupCache::seen_or_add(NodeId src, uint16_t pkt_id, uint8_t frag_index) {
  for (size_t i = 0; i < entries_.size(); ++i) {
    const Entry &e = entries_[i];
    if (e.used && e.src == src && e.pkt_id == pkt_id && e.frag_index == frag_index)
      return true;
  }
  if (entries_.empty()) return false;  // nowhere to record it, so nothing to dedup
  if (entries_[head_].used) ++evictions_;  // this write evicts the oldest entry
  Entry &slot = entries_[head_];
  slot.used = true;
  slot.src = src;
  slot.pkt_id = pkt_id;
  slot.frag_index = frag_index;
  head_ = (head_ + 1) % entries_.size();
  if (count_ < entries_.size()) ++count_;
  return false;
}

// ------------------------------------------------------------- Reassembly --

void Reassembly::set_capacity(size_t n) {
  capacity_ = n;
  flows_.clear();
}

Reassembly::Flow *Reassembly::find(NodeId src, uint16_t pkt_id) {
  for (size_t i = 0; i < flows_.size(); ++i)
    if (flows_[i].src == src && flows_[i].pkt_id == pkt_id) return &flows_[i];
  return nullptr;
}

Reassembly::Flow *Reassembly::open(NodeId src, uint16_t pkt_id,
                                   uint8_t frag_count) {
  if (flows_.size() >= capacity_) return nullptr;
  Flow f;
  f.src = src;
  f.pkt_id = pkt_id;
  f.frag_count = frag_count;
  f.parts.resize(frag_count);
  f.present.assign(frag_count, false);
  flows_.push_back(f);
  return &flows_.back();
}

bool Reassembly::flow_complete(const Flow &f) const {
  if (f.parts.size() != (size_t)f.frag_count) return false;
  for (size_t i = 0; i < f.present.size(); ++i)
    if (!f.present[i]) return false;  // presence of every index, not a count
  return true;
}

void Reassembly::finish(Flow &f) {
  Done d;
  d.src = f.src;
  d.pkt_id = f.pkt_id;
  size_t total = 0;
  for (size_t i = 0; i < f.parts.size(); ++i) total += f.parts[i].size();
  d.data.reserve(total);
  for (size_t i = 0; i < f.parts.size(); ++i)
    d.data.insert(d.data.end(), f.parts[i].begin(), f.parts[i].end());
  done_.push_back(d);
  ++completed_;
  for (size_t i = 0; i < flows_.size(); ++i) {  // free the flow's slot
    if (&flows_[i] == &f) {
      flows_.erase(flows_.begin() + (long)i);
      break;
    }
  }
}

Reassembly::Status Reassembly::offer(NodeId src, uint16_t pkt_id,
                                    uint8_t frag_index, uint8_t frag_count,
                                    uint8_t payload_len, const uint8_t *data,
                                    size_t len) {
  if (frag_count == 0 || frag_count > MESH_MAX_FRAGS ||
      frag_index >= frag_count || payload_len > MESH_MAX_PAYLOAD ||
      len != (size_t)payload_len || (payload_len > 0 && data == nullptr)) {
    ++rejected_;
    return Status::BadFragment;
  }

  Flow *f = find(src, pkt_id);
  if (f != nullptr && f->frag_count != frag_count) {
    // Same packet id claiming a different shape: refuse rather than mix
    // fragments of two different datagrams into one output buffer.
    ++rejected_;
    return Status::BadFragment;
  }
  if (f == nullptr) {
    f = open(src, pkt_id, frag_count);
    if (f == nullptr) {
      ++rejected_;
      return Status::TooManyFlows;
    }
  }
  if (f->present[frag_index]) return Status::Duplicate;

  f->parts[frag_index].assign(data, data + len);
  f->present[frag_index] = true;
  if (flow_complete(*f)) {
    finish(*f);
    return Status::Complete;
  }
  return Status::Accepted;
}

bool Reassembly::take(std::vector<uint8_t> *out, NodeId *src, uint16_t *pkt_id) {
  if (done_.empty()) return false;
  const Done &d = done_.front();
  if (out) *out = d.data;
  if (src) *src = d.src;
  if (pkt_id) *pkt_id = d.pkt_id;
  done_.erase(done_.begin());
  return true;
}

std::vector<Reassembly::FlowStat> Reassembly::flows() const {
  std::vector<FlowStat> out;
  for (size_t i = 0; i < flows_.size(); ++i) {
    FlowStat s;
    s.src = flows_[i].src;
    s.pkt_id = flows_[i].pkt_id;
    s.frag_count = flows_[i].frag_count;
    uint8_t got = 0;
    for (size_t j = 0; j < flows_[i].present.size(); ++j)
      if (flows_[i].present[j]) ++got;
    s.received = got;
    out.push_back(s);
  }
  return out;
}

// -------------------------------------------------------------------- Node --

Node::Node(const MeshConfig &cfg, RadioHal *radio, LayerLogger *logger)
    : cfg_(cfg),
      radio_(radio),
      fake_(static_cast<RadioHalFake *>(radio)),
      logger_(logger),
      dup_(cfg.dup_capacity),
      reasm_(cfg.frag_capacity),
      acquired_(false),
      configured_(false) {}

Node::~Node() = default;

void Node::set_neighbors(const NodeId *ids, size_t count) {
  if (count > MESH_MAX_NEIGHBORS) count = MESH_MAX_NEIGHBORS;
  cfg_.neighbor_count = (uint8_t)count;
  for (size_t i = 0; i < MESH_MAX_NEIGHBORS; ++i)
    cfg_.neighbors[i] = (i < count) ? ids[i] : MESH_BROADCAST;
}

bool Node::is_neighbor(NodeId dst) const {
  for (size_t i = 0; i < cfg_.neighbor_count; ++i)
    if (cfg_.neighbors[i] == dst) return true;
  return false;
}

bool Node::model_ok() const {
  if (cfg_.modulation == Modulation::Lora)
    return cfg_.frequency_hz > 0 && cfg_.spreading_factor >= 5 &&
           cfg_.spreading_factor <= 12 && cfg_.coding_rate >= 5 &&
           cfg_.coding_rate <= 8;
  if (cfg_.modulation == Modulation::Flrc) return cfg_.bandwidth_hz > 0;
  return cfg_.coding_rate >= 5 && cfg_.coding_rate <= 8;  // Fsk
}

bool Node::ensure_ready() {
  if (radio_ == nullptr) return false;
  if (!acquired_) {
    if (radio_->acquire(50) != Result::Ok) return false;
    acquired_ = true;
  }
  if (!configured_) {
    if (radio_->configure(cfg_.to_radio()) != Result::Ok) return false;
    configured_ = true;
  }
  return true;
}

bool Node::send(NodeId dst, const uint8_t *data, size_t len, uint16_t pkt_id) {
  if (!ensure_ready()) return false;
  if (data == nullptr || len == 0) return false;
  if (len > MESH_MAX_DATAGRAM) return false;   // beyond what we can fragment
  if (cfg_.app_mtu == 0 || cfg_.app_mtu > MESH_MAX_PAYLOAD) return false;
  if (!model_ok()) return false;
  const size_t count = (len + cfg_.app_mtu - 1) / cfg_.app_mtu;
  if (count > MESH_MAX_FRAGS) return false;

  for (size_t fi = 0; fi < count; ++fi) {
    const size_t off = fi * cfg_.app_mtu;
    const size_t n = (len - off > cfg_.app_mtu) ? cfg_.app_mtu : len - off;
    Header h;
    h.version = MESH_WIRE_VERSION;
    h.type = MeshType::Data;
    h.src = cfg_.node_id;
    h.dst = dst;
    h.pkt_id = pkt_id;
    h.hop_limit = cfg_.hop_limit;
    h.frag_index = (uint8_t)fi;
    h.frag_count = (uint8_t)count;
    h.payload_len = (uint8_t)n;
    uint8_t frame[MESH_HEADER_SIZE + MESH_MAX_PAYLOAD];
    const size_t w = build_frame(h, data + off, frame, sizeof frame);
    if (w == 0 || !start_tx(frame, w)) return false;
  }

  // The retransmit path is single-fragment by design; a larger unicast datagram
  // rides the flood and has no ACK.
  retransmit_.assign(data, data + len);
  if (cfg_.ack_enabled && dst != MESH_BROADCAST && count == 1)
    arm_ack(pkt_id, dst);
  return true;
}

bool Node::ack(const Header &rx_header) {
  if (rx_header.src == MESH_BROADCAST) return false;
  if (rx_header.type == MeshType::Ack) return false;  // never ACK an ACK
  Header h;
  h.version = MESH_WIRE_VERSION;
  h.type = MeshType::Ack;
  h.src = cfg_.node_id;
  h.dst = rx_header.src;
  h.pkt_id = rx_header.pkt_id;
  h.hop_limit = cfg_.hop_limit;
  h.frag_index = 0;
  h.frag_count = 1;
  h.payload_len = 0;
  uint8_t frame[MESH_HEADER_SIZE];
  const size_t w = build_frame(h, nullptr, frame, sizeof frame);
  if (w == 0) return false;
  if (queue_.size() >= MESH_MAX_QUEUE) return false;
  Event e;
  e.frame.assign(frame, frame + w);
  queue_.push_back(e);
  ++st_.ack_sent;
  return true;
}

bool Node::start_tx(const uint8_t *frame, size_t len) {
  if (len > cfg_.max_packet_bytes) return false;  // the radio would refuse it
  if (queue_.size() >= MESH_MAX_QUEUE) {
    ++st_.drops_queue_full;
    return false;
  }
  Event e;
  e.frame.assign(frame, frame + len);
  queue_.push_back(e);
  ++st_.tx_frames;
  return true;
}

bool Node::deliver_locally(const Header &h, const uint8_t *payload, size_t plen) {
  if (h.type == MeshType::Ack) {
    ++st_.ack_received;
    cancel_ack(h.pkt_id);
    return true;
  }
  const Reassembly::Status s = reasm_.offer(h.src, h.pkt_id, h.frag_index,
                                            h.frag_count, h.payload_len, payload,
                                            plen);
  if (s == Reassembly::Status::Complete) {
    ++st_.delivered;
    return true;
  }
  return s == Reassembly::Status::Accepted;
}

void Node::forward(const Header &h, const uint8_t *payload, size_t plen) {
  (void)plen;     // build_frame copies h.payload_len bytes
  Header f = h;
  --f.hop_limit;  // consume one hop on every forward
  uint8_t frame[MESH_HEADER_SIZE + MESH_MAX_PAYLOAD];
  const size_t w = build_frame(f, payload, frame, sizeof frame);
  if (w == 0) return;
  if (queue_.size() >= MESH_MAX_QUEUE) {
    ++st_.drops_queue_full;
    return;
  }
  Event e;
  e.frame.assign(frame, frame + w);
  queue_.push_back(e);
}

Node::Op Node::process_frame(const uint8_t *frame, size_t len) {
  ++st_.rx_frames;
  Header h;
  const uint8_t *payload = nullptr;
  size_t plen = 0;
  if (decode_header(frame, len, &h, &payload, &plen) != CodecResult::Ok) {
    ++st_.drops_bad_frame;  // nothing is ever partially parsed into the mesh
    return Op::Drop;
  }

  // Our own flood arriving back at us from a neighbour is not a message for us.
  if (h.src == cfg_.node_id) {
    ++st_.drops_own;
    return Op::Drop;
  }

  if (cfg_.dedup_enabled && dup_.seen_or_add(h.src, h.pkt_id, h.frag_index)) {
    ++st_.rx_duplicates;
    return Op::Drop;
  }

  const bool for_us = (h.dst == cfg_.node_id) || (h.dst == MESH_BROADCAST);
  bool acted = false;
  if (for_us) {
    last_rx_ = h;
    acted = deliver_locally(h, payload, plen);
    if (h.type == MeshType::Ack) return Op::Ack;
    if (!acted && h.dst == cfg_.node_id) return Op::Drop;
  }
  (void)acted;

  // Rebroadcast only when a hop still remains AFTER this one (hop_limit >= 2),
  // so hop_limit N means "reaches N hops" rather than N+1. Never rebroadcast a
  // frame whose final destination is us.
  if (h.hop_limit >= 2 && !(h.dst == cfg_.node_id)) {
    const bool unicast = (h.dst != MESH_BROADCAST);
    if (h.type == MeshType::Ack) {
      // An ACK is never flooded. It may only be relayed ONE hop towards a direct
      // neighbour -- which is what lets a two-hop unicast be acknowledged
      // without turning the ACK into a mesh-wide storm.
      if (unicast && is_neighbor(h.dst)) {
        forward(h, payload, plen);
        ++st_.forwarded;
        ++st_.rebroadcast;
        return Op::Forward;
      }
      return Op::Drop;
    }
    if (!unicast || is_neighbor(h.dst)) {  // broadcast, or a reachable unicast
      forward(h, payload, plen);
      ++st_.forwarded;
      ++st_.rebroadcast;
      return Op::Forward;
    }
    // Unicast to a node outside direct radio range, with no route table: drop
    // rather than blindly flooding the whole mesh with it.
    ++st_.drops_no_route;
    return Op::Drop;
  }
  return for_us ? Op::Deliver : Op::Drop;
}

Node::Op Node::on_rx(const uint8_t *frame, size_t len) {
  if (frame == nullptr || len == 0) {
    ++st_.drops_bad_frame;
    return Op::Drop;
  }
  return process_frame(frame, len);
}

bool Node::pump_arrival() {
  if (fake_ == nullptr) return false;
  // A receive-only node has still never touched the radio, and the HAL refuses
  // every operation on an un-acquired device -- so acquire/configure here too.
  if (!ensure_ready()) return false;
  uint8_t buf[MESH_HEADER_SIZE + MESH_MAX_PAYLOAD];
  size_t len = 0;
  if (fake_->receive(buf, sizeof buf, &len, 0) != Result::Ok || len == 0)
    return false;
  on_rx(buf, len);
  return true;
}

// -------------------------------------------------------------------- ACK --

void Node::arm_ack(uint16_t pkt_id, NodeId dst) {
  Pending p;
  p.pkt_id = pkt_id;
  p.dst = dst;
  p.attempts = 1;  // the initial send is attempt 1
  p.armed = true;
  p.span_ms = cfg_.ack_timeout_ms;
  p.due_ms = (fake_ != nullptr) ? fake_->now_ms() + cfg_.ack_timeout_ms : 1;
  pending_.push_back(p);
}

void Node::cancel_ack(uint16_t pkt_id) {
  for (size_t i = 0; i < pending_.size(); ++i)
    if (pending_[i].armed && pending_[i].pkt_id == pkt_id) pending_[i].armed = false;
}

bool Node::ack_due_now() const {
  if (fake_ == nullptr) return false;
  for (size_t i = 0; i < pending_.size(); ++i) {
    const Pending &p = pending_[i];
    if (p.armed && p.due_ms != 0 && fake_->now_ms() >= p.due_ms) return true;
  }
  return false;
}

void Node::on_ack_timeout() {
  if (fake_ == nullptr) return;
  for (size_t i = 0; i < pending_.size(); ++i) {
    Pending &p = pending_[i];
    if (!p.armed || fake_->now_ms() < p.due_ms) continue;
    if (p.attempts >= cfg_.max_attempts) {
      p.armed = false;
      ++st_.failures;  // bounded give-up: no unbounded retry loop exists here
      continue;
    }
    if (retransmit_.empty()) {
      p.armed = false;
      ++st_.failures;
      continue;
    }
    Header h;
    h.version = MESH_WIRE_VERSION;
    h.type = MeshType::Data;
    h.src = cfg_.node_id;
    h.dst = p.dst;
    h.pkt_id = p.pkt_id;
    h.hop_limit = cfg_.hop_limit;
    h.frag_index = 0;
    h.frag_count = 1;
    h.payload_len = (uint8_t)retransmit_.size();
    uint8_t frame[MESH_HEADER_SIZE + MESH_MAX_PAYLOAD];
    const size_t w = build_frame(h, retransmit_.data(), frame, sizeof frame);
    if (w != 0 && start_tx(frame, w)) ++st_.retransmits;
    ++p.attempts;
    uint32_t span = p.span_ms;
    if (cfg_.backoff_multiplier > 1 &&
        span <= MESH_MAX_BACKOFF_MS / cfg_.backoff_multiplier)
      span *= cfg_.backoff_multiplier;
    else if (span < MESH_MAX_BACKOFF_MS)
      span = MESH_MAX_BACKOFF_MS;
    p.span_ms = span;
    p.due_ms = fake_->now_ms() + span;
    return;
  }
}

// ------------------------------------------------------------------- Tick --

bool Node::has_work() const {
  if (!queue_.empty()) return true;
  if (ack_due_now()) return true;
  return fake_ != nullptr && fake_->has_arrival();
}

uint32_t Node::next_wake_ms() const {
  if (fake_ == nullptr) return MESH_NO_WAKE;
  if (!queue_.empty()) return fake_->now_ms();
  uint32_t best = fake_->has_arrival() ? fake_->now_ms() : MESH_NO_WAKE;
  for (size_t i = 0; i < pending_.size(); ++i) {
    const Pending &p = pending_[i];
    if (p.armed && p.due_ms != 0 && p.due_ms < best) best = p.due_ms;
  }
  return best;
}

bool Node::tick() {
  if (!queue_.empty()) {
    Event e = queue_.front();
    queue_.erase(queue_.begin());
    if (fake_ != nullptr) {
      if (fake_->send(e.frame.data(), e.frame.size()) != Result::Ok) return true;
      if (cfg_.tx_airtime_ms != 0) fake_->advance_ms(cfg_.tx_airtime_ms);
    }
    ++st_.tx_attempts;
    return true;
  }
  if (ack_due_now()) {
    on_ack_timeout();
    return true;
  }
  return pump_arrival();  // nothing else to do: service the receiver
}

void Node::flush(uint32_t max_steps) {
  for (uint32_t i = 0; i < max_steps; ++i) {
    if (!has_work()) break;
    tick();
  }
}

// ------------------------------------------------------------------- Radio --

RadioHalFake::RadioHalFake(uint32_t tx_airtime_ms)
    : acquired_(false),
      have_cfg_(false),
      rx_continuous_(false),
      airtime_(tx_airtime_ms),
      now_(0),
      last_src_(0),
      last_pkt_id_(0),
      last_frag_index_(0) {
  cfg_.modulation = Modulation::Lora;
  cfg_.frequency_hz = 0;
  cfg_.bandwidth_hz = 0;
  cfg_.spreading_factor = 0;
  cfg_.coding_rate = 0;
  cfg_.tx_power_dbm = 0;
  cfg_.preamble_symbols = 0;
  cfg_.crc_on = false;
}

Result RadioHalFake::acquire(uint32_t) {
  if (acquired_) return Result::Busy;
  acquired_ = true;
  return Result::Ok;
}

Result RadioHalFake::release() {
  if (!acquired_) return Result::NotAcquired;
  acquired_ = false;
  return Result::Ok;
}

Result RadioHalFake::reset() {
  if (!acquired_) return Result::NotAcquired;
  have_cfg_ = false;
  tx_fifo_.clear();
  return Result::Ok;
}

Result RadioHalFake::configure(const Config &cfg) {
  if (!acquired_) return Result::NotAcquired;
  cfg_ = cfg;
  have_cfg_ = true;
  return Result::Ok;
}

Result RadioHalFake::read_config(Config *out) const {
  if (!have_cfg_ || out == nullptr) return Result::BadArgument;
  *out = cfg_;
  return Result::Ok;
}

Result RadioHalFake::send(const uint8_t *data, size_t len) {
  if (!acquired_) return Result::NotAcquired;
  if (!have_cfg_) return Result::BadArgument;
  if (data == nullptr || len == 0) return Result::BadArgument;
  if (len > MESH_HEADER_SIZE + MESH_MAX_PAYLOAD) return Result::BadArgument;
  Frame f;
  f.bytes.assign(data, data + len);
  f.t_done = now_ + airtime_;  // the frame is on the air until airtime elapses
  tx_fifo_.push_back(f);
  return Result::Ok;
}

bool RadioHalFake::pop_transmitted(uint8_t *buf, size_t cap, size_t *len,
                                   uint32_t *t_done) {
  for (size_t i = 0; i < tx_fifo_.size(); ++i) {
    if (tx_fifo_[i].t_done > now_) continue;
    const Frame &f = tx_fifo_[i];
    if (f.bytes.size() > cap) return false;
    std::memcpy(buf, f.bytes.data(), f.bytes.size());
    if (len) *len = f.bytes.size();
    if (t_done) *t_done = f.t_done;
    tx_fifo_.erase(tx_fifo_.begin() + (long)i);
    return true;
  }
  return false;
}

bool RadioHalFake::push_incoming(const uint8_t *frame, size_t len,
                                 uint32_t t_done) {
  if (frame == nullptr || len == 0) return false;
  Frame f;
  f.bytes.assign(frame, frame + len);
  f.t_done = t_done;
  arrivals_.push_back(f);
  return true;
}

bool RadioHalFake::has_arrival() const {
  for (size_t i = 0; i < arrivals_.size(); ++i)
    if (arrivals_[i].t_done <= now_) return true;
  return false;
}

uint32_t RadioHalFake::next_arrival_ms() const {
  uint32_t best = MESH_NO_WAKE;
  for (size_t i = 0; i < arrivals_.size(); ++i)
    if (arrivals_[i].t_done < best) best = arrivals_[i].t_done;
  return best;
}

Result RadioHalFake::receive(uint8_t *out, size_t max_len, size_t *out_len,
                             uint32_t timeout_ms) {
  if (!acquired_) return Result::NotAcquired;
  if (out_len) *out_len = 0;
  // The host model never blocks: a frame that has not arrived is simply not
  // ready, which the caller observes as Ok + 0 bytes.
  (void)timeout_ms;
  for (size_t i = 0; i < arrivals_.size(); ++i) {
    if (arrivals_[i].t_done > now_) continue;
    const Frame &f = arrivals_[i];
    if (f.bytes.size() > max_len) return Result::BadArgument;
    if (out != nullptr) std::memcpy(out, f.bytes.data(), f.bytes.size());
    if (out_len) *out_len = f.bytes.size();
    Header h;
    const uint8_t *pl = nullptr;
    size_t pln = 0;
    if (decode_header(f.bytes.data(), f.bytes.size(), &h, &pl, &pln) ==
        CodecResult::Ok) {
      last_src_ = h.src;
      last_pkt_id_ = h.pkt_id;
      last_frag_index_ = h.frag_index;
    }
    arrivals_.erase(arrivals_.begin() + (long)i);
    return Result::Ok;
  }
  return Result::Ok;  // Ok with 0 bytes: nothing pending
}

Result RadioHalFake::set_rx_continuous(bool on) {
  if (!acquired_) return Result::NotAcquired;
  rx_continuous_ = on;
  return Result::Ok;
}

Result RadioHalFake::get_rssi_dbm(int16_t *out) const {
  if (!acquired_) return Result::NotAcquired;
  if (out == nullptr) return Result::BadArgument;
  *out = -110;  // model value only; no radio was consulted
  return Result::Ok;
}

Result RadioHalFake::get_snr_db(int8_t *out) const {
  if (!acquired_) return Result::NotAcquired;
  if (out == nullptr) return Result::BadArgument;
  *out = 6;
  return Result::Ok;
}

}  // namespace mesh
}  // namespace balloon
