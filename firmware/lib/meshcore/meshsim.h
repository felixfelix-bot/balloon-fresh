// Deterministic simulated MeshCore mesh — model API.
//
// HONESTY: this is a MODEL, not field evidence. There is no radio here: frames
// are relayed through adjacency matrices on a virtual clock. It proves the mesh
// SEMANTICS (whole-flood duplicate suppression, hop-budget reach, exact delivery
// sets, ACK round trips), not RF behaviour, range, or airtime on real hardware.
//
// Scope: MESH_NODES nodes. Each simulated node's neighbour table is bounded by
// radio_core's MESH_MAX_NEIGHBORS, hence the static_assert: a denser modelled
// mesh would silently truncate adjacency, and a silent truncation is exactly the
// kind of lie a test must not tell.
//
// Timing model: a relayed frame arrives with zero per-hop latency, so one flood
// completes within a single virtual instant; virtual time is advanced only by an
// explicit advance_to(), which is what ACK timers observe. Charging per-hop
// airtime would drift each node's clock independently and make the "one virtual
// instant" flood impossible to reason about, so it is deliberately not modelled.
#pragma once

#include <cstdint>
#include <string>
#include <vector>

#include "mesh.h"

namespace balloon {
namespace mesh {
namespace sim {

constexpr size_t MESH_NODES = 8;
static_assert(MESH_NODES <= MESH_MAX_NEIGHBORS,
              "the model must not exceed the frozen neighbour table size");

// Adjacency plus the set of nodes that take part (0-based indices; a node's
// NodeId is index + 1).
struct Topology {
  const char *name;
  uint8_t adj[MESH_NODES][MESH_NODES];
  std::vector<size_t> scope;
  size_t origin;      // 0-based index of the node that floods
  uint8_t hop_limit;  // TTL used for that flood and for ACK-relay frames
};

const Topology &line6();        // 1--2--3--4--5--6
const Topology &line8_tight();  // 1..8 in a line, hop_limit 4 (must stop at 5)
const Topology &diamond();      // 4 is reachable two ways -> duplicate at node 4
const Topology &ring6();        // 1..6 in a ring -> two paths the short way
const Topology &star();         // 1 is a hub over 2/3/4, all mutually adjacent
const Topology &line4();        // 1--2--3--4 , used for ACK relay + repeats
const std::vector<const Topology *> &all_topologies();

class Sim {
 public:
  struct Msg {           // one completed (= fully reassembled) delivery
    NodeId node;         // receiver
    uint16_t pkt_id;
    NodeId src;
    std::vector<uint8_t> bytes;
  };

  // dedup=false builds a deliberately broken mesh: the only way to show that the
  // duplicate-suppression check is what bounds a flood is to watch it not bound.
  explicit Sim(const Topology &top, bool dedup = true);
  ~Sim();

  Node &node(size_t zero_based);
  RadioHalFake &radio(size_t zero_based);
  const Topology &top() const { return top_; }

  // Run the mesh until no frame is in flight and no node has work. A flood
  // completes inside one call because relay latency is zero by construction.
  void quiesce();
  // Move virtual time forward by setting every node's clock to `t`, then quiesce
  // -- this is what makes ACK timers fire.
  void advance_to(uint32_t t);
  uint32_t now(size_t zero_based) const;

  uint16_t bcast(size_t origin, uint16_t pkt_id, const uint8_t *pl, size_t len);
  uint16_t bcast_str(size_t origin, uint16_t pkt_id, const char *s);

  // Collect every completed delivery so far, in a deterministic order.
  void drain();

  // The exact-delivery-set assertion: `id` is delivered exactly once at each of
  // receiver_idx, with bytes == golden, and nowhere else.
  bool check_exactly(const std::vector<size_t> &receiver_idx, uint16_t id,
                     const std::vector<uint8_t> &golden);
  int delivered_count(NodeId node, uint16_t id) const;
  // Same, addressed by 0-based topology index. Preferred in tests: passing an
  // index where a NodeId is expected is a silent off-by-one that reads exactly
  // like a protocol bug (node 4 vs node 5 in a 4-node topology).
  int delivered_count_idx(size_t idx, uint16_t id) const {
    return delivered_count((NodeId)(idx + 1), id);
  }
  const std::vector<Msg> &msgs() const { return msgs_; }

  uint32_t total_forwarded() const;
  uint32_t total_duplicates() const;
  uint32_t total_reroutes() const;   // drops_no_route, summed
  uint32_t total_corrupt() const;    // reassemblies that must never exist
  uint32_t total_own_echo() const;   // our own flood heard back
  bool any_work() const;             // any node or link still doing something

  // Human-readable per-scenario digest, including the expected receiver set.
  std::string digest_of(uint16_t id, const std::vector<size_t> &expect) const;
  // The header the application must ACK if it wants to ACK what node idx got.
  Header last_rx_header(size_t idx) const { return nodes_[idx]->last_rx(); }

 private:
  struct LinkFrame {
    size_t from;
    uint32_t t;
    std::vector<uint8_t> bytes;
  };

  void set_adjacency();
  void tick_all();
  void collect(size_t i);
  void deliver_queued();

  Topology top_;
  Node *nodes_[MESH_NODES];
  RadioHalFake *radios_[MESH_NODES];
  std::vector<LinkFrame> link_;
  std::vector<Msg> msgs_;
};

// Nodes a flood from t.origin can reach when each forward costs one hop.
std::vector<size_t> reachable(const Topology &t);

struct SceneResult {
  SceneResult() : ok(false), total_deliveries(0) {}
  bool ok;
  int total_deliveries;  // every completed delivery the scenario observed
  std::string digest;
};

// One named scenario: flood(s) over a topology with its exact-delivery-set proof.
SceneResult run_scene(const Topology &top);
// Six consecutive floods, asserting one delivery per (packet, receiver)
// everywhere. `dedup=false` builds a deliberately broken mesh -- the counter-test
// at swarm level, where the same six floods are no longer bounded.
SceneResult run_stress(const Topology &top, bool dedup = true);
// Two-hop unicast 4->2 through 3, with the ACK riding back 2->3->4.
SceneResult run_ack_relay();
// The same line6 stress with duplicate suppression switched off. Its `ok` field
// is false by construction: it exists precisely to prove that the check the
// scenario above depends on is what bounds the flood.
SceneResult run_stress_no_dedup(const Topology &top);

// Stable 64-bit FNV-1a over a digest string, so a digest can be compared cheaply
// across processes without embedding the whole string in a report.
uint64_t hexdigest(const std::string &s);
// Graphviz DOT of every topology: stable, no timestamps, diffable.
std::string dot_graph();
// Run every scenario and verify its digest; fills *report with the real text.
bool check_all(std::string *report);
// Nodes a flood from t.origin reaches, derived from the topology alone.
std::vector<size_t> reachable(const Topology &t);

}  // namespace sim
}  // namespace mesh
}  // namespace balloon
