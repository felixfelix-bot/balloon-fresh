// MeshCore-style mesh transport core — flood/TTL/dedup/ACK/fragmentation.
//
// The L1/L2 half of MeshCore that sits on top of the frozen radio HAL. It owns
// no hardware and performs no I/O beyond the injected HAL, so the whole protocol
// is host-testable. The radio arrives through the frozen contract:
//
//   @radio_hal ../radio_core/radio_hal.h -> radio::RadioHal (acquire/release,
//   configure/send/receive). We NEVER define make_radio_hal() and never link
//   radio_core.cpp: tests use RadioHalFake below, our own device model.
//
// Semantics (deliberately small, MeshCore-style):
//   * Flood: a Data/Hello frame addressed to MESH_BROADCAST is delivered locally
//     and re-broadcast, consuming one hop. A unicast frame is forwarded only if
//     its destination is a DIRECT neighbour -- multi-hop unicast would need a
//     route table, which this core does not have (multi-hop reach is the flood).
//   * Hop limit: hop_limit is decremented on every forward. hop_limit == 0 means
//     final: deliver (if addressed to us or broadcast) but never re-broadcast.
//   * Own-packet suppression: a frame whose src is our own id is our own flood
//     coming back to us, and is dropped -- we do not deliver our own broadcast.
//   * Duplicate suppression: a frame already seen from (src, pkt_id, frag_index)
//     is dropped. dedup_enabled == false turns that off on purpose, because the
//     only way to prove the check is load-bearing is to watch the mesh storm
//     without it. The seen-cache is a bounded ring, so memory is O(capacity).
//   * ACK: a unicast Data datagram arms a retransmit timer. A matching Ack
//     cancels it. Otherwise we retransmit at most (max_attempts - 1) times with
//     exponential backoff and then report a failure -- never an unbounded loop.
//   * Fragmentation: a datagram larger than app_mtu is split into
//     ceil(len / app_mtu) frames sharing one pkt_id. Reassembly is
//     PRESENCE-based: every fragment index must be present. Completing on an
//     arrival COUNT instead would let a duplicate stand in for a missing fragment
//     and yield a corrupt message, so Reassembly counts corrupt_completions()
//     and a test asserts it stays zero.
#pragma once

#include <cstddef>
#include <cstdint>
#include <vector>

#include "meshcodec.h"
#include "../radio_core/radio_hal.h"

namespace balloon {
namespace mesh {

using radio::Config;
using radio::Modulation;
using radio::RadioHal;
using radio::Result;

// Optional observer. Default is none, and the core never logs on its own, so a
// caller that passes a logger still sees zero calls unless it wants otherwise.
class LayerLogger {
 public:
  virtual ~LayerLogger() = default;
  virtual void log(const char *layer, const char *event, const char *detail) = 0;
};

// Largest neighbour table we hold. One radio, few peers, fixed memory.
constexpr size_t MESH_MAX_NEIGHBORS = 8;
// Sentinel from next_wake_ms(): this node needs no servicing at any future time.
constexpr uint32_t MESH_NO_WAKE = 0xFFFFFFFFu;
// Bound on the exponential backoff span so the deadline cannot overflow.
constexpr uint32_t MESH_MAX_BACKOFF_MS = 1u << 20;
// Bound on the internal TX queue; a full queue drops rather than growing.
constexpr size_t MESH_MAX_QUEUE = 256;

struct MeshConfig {
  MeshConfig()
      : node_id(1),
        neighbor_count(0),
        max_packet_bytes(MESH_HEADER_SIZE + MESH_MAX_PAYLOAD),
        app_mtu(MESH_MAX_PAYLOAD),
        tx_airtime_ms(5),
        hop_limit(4),
        ack_enabled(true),
        ack_timeout_ms(200),
        backoff_multiplier(2),
        max_attempts(4),
        dup_capacity(16),
        dedup_enabled(true),
        frag_capacity(4),
        modulation(Modulation::Lora),
        frequency_hz(869525000UL),
        bandwidth_hz(125000UL),
        spreading_factor(9),
        coding_rate(5),
        tx_power_dbm(14),
        preamble_symbols(8),
        crc_on(true) {
    for (size_t i = 0; i < MESH_MAX_NEIGHBORS; ++i) neighbors[i] = MESH_BROADCAST;
  }

  // Mesh-level knobs.
  NodeId node_id;
  NodeId neighbors[MESH_MAX_NEIGHBORS];  // direct-radio range, mesh-space only
  uint8_t neighbor_count;
  size_t max_packet_bytes;   // frames larger than this are refused by the radio
  size_t app_mtu;            // largest payload we offer to a single frame
  uint32_t tx_airtime_ms;    // host model of a blocking send() duration
  uint8_t hop_limit;         // default TTL stamped on our own frames
  bool ack_enabled;          // arm the retransmit timer for unicast Data
  uint32_t ack_timeout_ms;   // first retransmit delay
  uint32_t backoff_multiplier;
  uint8_t max_attempts;      // total transmit attempts, hard bound
  size_t dup_capacity;       // seen-cache size; must evict
  bool dedup_enabled;        // false deliberately produces a flood storm
  size_t frag_capacity;      // concurrent reassemblies

  // Physical-layer knobs, carried here so tests do not need the HAL mappings.
  Modulation modulation;
  uint32_t frequency_hz;
  uint32_t bandwidth_hz;
  uint8_t spreading_factor;
  uint8_t coding_rate;
  int8_t tx_power_dbm;
  uint16_t preamble_symbols;
  bool crc_on;

  // Build the frozen HAL's Config from the mesh-level knobs.
  radio::Config to_radio() const {
    radio::Config c;
    c.modulation = modulation;
    c.frequency_hz = frequency_hz;
    c.bandwidth_hz = bandwidth_hz;
    c.spreading_factor = spreading_factor;
    c.coding_rate = coding_rate;
    c.tx_power_dbm = tx_power_dbm;
    c.preamble_symbols = preamble_symbols;
    c.crc_on = crc_on;
    return c;
  }
};

// Bounded seen-frame cache over (src, pkt_id, frag_index) triples. Keyed on the
// fragment as well as the packet so a partly-received datagram's retransmitted
// fragment is accepted while a true repeat is discarded.
class DupCache {
 public:
  explicit DupCache(size_t capacity = 16);
  void set_capacity(size_t n);
  size_t capacity() const { return entries_.size(); }
  size_t size() const { return count_; }
  uint32_t evictions() const { return evictions_; }
  // Returns true if it had already been seen. Records it either way.
  bool seen_or_add(NodeId src, uint16_t pkt_id, uint8_t frag_index);

 private:
  struct Entry {
    bool used;
    NodeId src;
    uint16_t pkt_id;
    uint8_t frag_index;
  };
  std::vector<Entry> entries_;
  size_t head_;
  size_t count_;
  uint32_t evictions_;
};

// Presence-based fragment reassembly. Cannot complete without every index, and
// counts corrupt_completions() so a test can assert it stays zero.
class Reassembly {
 public:
  enum class Status : uint8_t {
    Accepted = 0,
    Duplicate,
    Complete,
    BadFragment,
    TooManyFlows,
  };

  explicit Reassembly(size_t capacity = 4) : capacity_(capacity), completed_(0),
                                            corrupt_(0), rejected_(0) {}

  void set_capacity(size_t n);
  size_t capacity() const { return capacity_; }
  size_t slots() const { return flows_.size(); }
  uint32_t completed() const { return completed_; }
  uint32_t corrupt_completions() const { return corrupt_; }
  uint32_t rejected() const { return rejected_; }

  Status offer(NodeId src, uint16_t pkt_id, uint8_t frag_index,
               uint8_t frag_count, uint8_t payload_len, const uint8_t *data,
               size_t len);

  bool has_completed() const { return !done_.empty(); }
  bool take(std::vector<uint8_t> *out, NodeId *src, uint16_t *pkt_id);

  struct FlowStat {
    NodeId src;
    uint16_t pkt_id;
    uint8_t frag_count;
    uint8_t received;
  };
  std::vector<FlowStat> flows() const;

 private:
  struct Flow {
    NodeId src;
    uint16_t pkt_id;
    uint8_t frag_count;
    std::vector<std::vector<uint8_t>> parts;
    std::vector<bool> present;
  };
  struct Done {
    std::vector<uint8_t> data;
    NodeId src;
    uint16_t pkt_id;
  };
  Flow *find(NodeId src, uint16_t pkt_id);
  Flow *open(NodeId src, uint16_t pkt_id, uint8_t frag_count);
  bool flow_complete(const Flow &f) const;
  void finish(Flow &f);

  size_t capacity_;
  std::vector<Flow> flows_;
  std::vector<Done> done_;
  uint32_t completed_;
  uint32_t corrupt_;
  uint32_t rejected_;
};

class RadioHalFake;

// A mesh node: the transport state machine. One unit of work per tick(); the
// caller decides when to run it (the simulated mesh advances virtual time and
// calls tick() when the node has work). Nothing blocks or sleeps.
class Node {
 public:
  enum class Op : uint8_t { Drop, Deliver, Forward, Ack };

  Node(const MeshConfig &cfg, RadioHal *radio, LayerLogger *logger = nullptr);
  ~Node();

  NodeId id() const { return cfg_.node_id; }
  const MeshConfig &config() const { return cfg_; }
  // The sim keeps the neighbour table in sync with the connectivity matrix.
  void set_neighbors(const NodeId *ids, size_t count);

  // Application side.
  bool send(NodeId dst, const uint8_t *data, size_t len, uint16_t pkt_id);
  bool ack(const Header &rx_header);   // app-level ACK of a delivered datagram

  // Transport side: exactly one unit of work. False when idle.
  bool tick();
  bool has_work() const;
  // Earliest virtual time this node needs servicing, or MESH_NO_WAKE.
  uint32_t next_wake_ms() const;
  // Host convenience: pump until idle. With no peers and no clock source this
  // can only drain what is already queued, because nothing advances time.
  void flush(uint32_t max_steps = 4096);

  // Driver-facing: process one already-received frame.
  Op on_rx(const uint8_t *frame, size_t len);

  // Header of the most recent frame actually addressed to us. An application
  // layer needs it to address its ACK back at the real sender.
  const Header &last_rx() const { return last_rx_; }

  RadioHalFake *fake() { return fake_; }
  const Reassembly &reassembly() const { return reasm_; }
  Reassembly &reassembly() { return reasm_; }
  const DupCache &dup_cache() const { return dup_; }

  struct Stats {
    uint32_t tx_frames, tx_attempts, rx_frames, rx_duplicates, forwarded,
        rebroadcast, delivered, ack_sent, ack_received, retransmits, failures,
        drops_no_route, drops_queue_full, drops_bad_frame, drops_own;
    Stats()
        : tx_frames(0), tx_attempts(0), rx_frames(0), rx_duplicates(0),
          forwarded(0), rebroadcast(0), delivered(0), ack_sent(0),
          ack_received(0), retransmits(0), failures(0), drops_no_route(0),
          drops_queue_full(0), drops_bad_frame(0), drops_own(0) {}
  };
  const Stats &stats() const { return st_; }

 private:
  struct Event {
    std::vector<uint8_t> frame;
  };
  struct Pending {  // an in-flight datagram awaiting an ACK
    uint16_t pkt_id;
    NodeId dst;
    uint8_t attempts;
    bool armed;
    uint32_t span_ms;  // current backoff span
    uint32_t due_ms;   // absolute virtual deadline
  };

  bool ensure_ready();
  bool pump_arrival();
  Op process_frame(const uint8_t *frame, size_t len);
  bool deliver_locally(const Header &h, const uint8_t *payload, size_t plen);
  void forward(const Header &h, const uint8_t *payload, size_t plen);
  bool start_tx(const uint8_t *frame, size_t len);
  bool is_neighbor(NodeId dst) const;
  bool model_ok() const;
  void arm_ack(uint16_t pkt_id, NodeId dst);
  void cancel_ack(uint16_t pkt_id);
  bool ack_due_now() const;
  void on_ack_timeout();

  MeshConfig cfg_;
  RadioHal *radio_;
  RadioHalFake *fake_;
  LayerLogger *logger_;
  DupCache dup_;
  Reassembly reasm_;
  std::vector<Event> queue_;
  std::vector<uint8_t> retransmit_;
  std::vector<Pending> pending_;
  Stats st_;
  Header last_rx_;
  bool acquired_;
  bool configured_;
};

// Our own fake HAL: a device model, not radio_core.cpp. Register-file style with
// a virtual clock, an output FIFO, and a per-node arrival queue. A queued frame
// is handed to the node exactly once, only once its virtual arrival time has been
// reached; frames do not overwrite each other.
class RadioHalFake : public RadioHal {
 public:
  explicit RadioHalFake(uint32_t tx_airtime_ms = 0);

  void set_tx_airtime_ms(uint32_t ms) { airtime_ = ms; }
  uint32_t now_ms() const { return now_; }
  void advance_ms(uint32_t ms) { now_ += ms; }

  // HAL contract.
  Result acquire(uint32_t timeout_ms) override;
  Result release() override;
  bool is_acquired() const override { return acquired_; }
  Result reset() override;
  Result configure(const Config &cfg) override;
  Result read_config(Config *out) const override;
  Result send(const uint8_t *data, size_t len) override;
  Result receive(uint8_t *out, size_t max_len, size_t *out_len,
                 uint32_t timeout_ms) override;
  Result set_rx_continuous(bool on) override;
  Result get_rssi_dbm(int16_t *out) const override;
  Result get_snr_db(int8_t *out) const override;

  // Model-side hooks.
  bool push_incoming(const uint8_t *frame, size_t len, uint32_t t_done);
  bool push_transmitted(const uint8_t *frame, size_t len);
  bool pop_transmitted(uint8_t *buf, size_t cap, size_t *len, uint32_t *t_done);
  bool has_arrival() const;
  uint32_t next_arrival_ms() const;
  size_t pending_arrivals() const { return arrivals_.size(); }
  size_t pending_tx() const { return tx_fifo_.size(); }
  bool tx_busy() const { return !tx_fifo_.empty(); }

  // Metadata of the last frame handed out by receive().
  uint8_t last_src() const { return last_src_; }
  uint16_t last_pkt_id() const { return last_pkt_id_; }
  uint8_t last_frag_index() const { return last_frag_index_; }

 private:
  struct Frame {
    std::vector<uint8_t> bytes;
    uint32_t t_done;
  };
  Config cfg_;
  bool acquired_;
  bool have_cfg_;
  bool rx_continuous_;
  uint32_t airtime_;
  uint32_t now_;
  std::vector<Frame> tx_fifo_;
  std::vector<Frame> arrivals_;
  uint8_t last_src_;
  uint16_t last_pkt_id_;
  uint8_t last_frag_index_;
};

}  // namespace mesh
}  // namespace balloon
