// Deterministic simulated mesh core — implementation of meshsim.h.
//
// HONESTY: a model, not field evidence. See meshsim.h.
#include "meshsim.h"

#include <algorithm>
#include <cstdio>
#include <cstring>

namespace balloon {
namespace mesh {
namespace sim {

namespace {

const uint32_t kNoTime = 0xFFFFFFFFu;
const uint32_t kHopLatencyMs = 0;  // relayed frames arrive within the same instant

std::string hexdump(const uint8_t *p, size_t n) {
  static const char *kHex = "0123456789abcdef";
  std::string s;
  for (size_t i = 0; i < n; ++i) {
    s.push_back(kHex[p[i] >> 4]);
    s.push_back(kHex[p[i] & 0xF]);
  }
  return s;
}

// Zero the matrix to avoid the tedious explicit braces per topology.
void make_adj(uint8_t out[MESH_NODES][MESH_NODES], const size_t (*edges)[2],
              size_t edge_count) {
  for (size_t i = 0; i < MESH_NODES; ++i)
    for (size_t j = 0; j < MESH_NODES; ++j) out[i][j] = 0;
  for (size_t e = 0; e < edge_count; ++e) {
    const size_t a = edges[e][0];
    const size_t b = edges[e][1];
    if (a < MESH_NODES && b < MESH_NODES) {
      out[a][b] = 1;
      out[b][a] = 1;
    }
  }
}

std::string join_nodes(const std::vector<size_t> &idx) {
  std::string s;
  for (size_t i = 0; i < idx.size(); ++i) {
    if (i) s += ",";
    s += std::to_string((int)(idx[i] + 1));
  }
  return s;
}

}  // namespace

static std::vector<size_t> range(size_t n) {
  std::vector<size_t> v;
  for (size_t i = 0; i < n; ++i) v.push_back(i);
  return v;
}

// Edges
static const size_t kLine6Edges[][2] = {{0, 1}, {1, 2}, {2, 3}, {3, 4}, {4, 5}};
static const size_t kLine8Edges[][2] = {{0, 1}, {1, 2}, {2, 3}, {3, 4},
                                        {4, 5}, {5, 6}, {6, 7}};
static const size_t kDiamondEdges[][2] = {{0, 1}, {0, 2}, {1, 3}, {2, 3}};
static const size_t kRing6Edges[][2] = {{0, 1}, {1, 2}, {2, 3},
                                        {3, 4}, {4, 5}, {5, 0}};
static const size_t kStarEdges[][2] = {{0, 1}, {0, 2}, {0, 3},
                                       {1, 2}, {1, 3}, {2, 3}};
static const size_t kLine4Edges[][2] = {{0, 1}, {1, 2}, {2, 3}};

// Six distinct tunnels on one chunk of ground; a node cannot reach another it
// does not hear, which is exactly what the mesh has to route around.
const Topology &line6() {
  static Topology t = [] {
    Topology x;
    x.name = "line6";
    make_adj(x.adj, kLine6Edges, sizeof(kLine6Edges) / sizeof(kLine6Edges[0]));
    x.scope = range(6);
    x.origin = 0;
    x.hop_limit = 6;
    return x;
  }();
  return t;
}

const Topology &line8_tight() {
  static Topology t = [] {
    Topology x;
    x.name = "line8_tight";
    make_adj(x.adj, kLine8Edges, sizeof(kLine8Edges) / sizeof(kLine8Edges[0]));
    x.scope = range(8);
    x.origin = 0;
    x.hop_limit = 4;  // must therefore stop at index 4 (node 5)
    return x;
  }();
  return t;
}

const Topology &diamond() {
  static Topology t = [] {
    Topology x;
    x.name = "diamond";
    make_adj(x.adj, kDiamondEdges,
             sizeof(kDiamondEdges) / sizeof(kDiamondEdges[0]));
    x.scope = range(4);
    x.origin = 0;
    x.hop_limit = 6;
    return x;
  }();
  return t;
}

const Topology &ring6() {
  static Topology t = [] {
    Topology x;
    x.name = "ring6";
    make_adj(x.adj, kRing6Edges, sizeof(kRing6Edges) / sizeof(kRing6Edges[0]));
    x.scope = range(6);
    x.origin = 0;
    x.hop_limit = 6;
    return x;
  }();
  return t;
}

const Topology &star() {
  static Topology t = [] {
    Topology x;
    x.name = "star";
    make_adj(x.adj, kStarEdges, sizeof(kStarEdges) / sizeof(kStarEdges[0]));
    x.scope = range(4);
    x.origin = 0;
    x.hop_limit = 6;
    return x;
  }();
  return t;
}

const Topology &line4() {
  static Topology t = [] {
    Topology x;
    x.name = "line4";
    make_adj(x.adj, kLine4Edges, sizeof(kLine4Edges) / sizeof(kLine4Edges[0]));
    x.scope = range(4);
    x.origin = 0;
    x.hop_limit = 6;
    return x;
  }();
  return t;
}

const std::vector<const Topology *> &all_topologies() {
  static std::vector<const Topology *> v = {&line6(),   &line8_tight(),
                                            &diamond(), &ring6(),
                                            &star(),    &line4()};
  return v;
}

// Nodes a flood from t.origin can reach when each forward costs one hop. The
// origin's frame reaches t.hop_limit hops, so every node at distance 1..hop_limit
// is a receiver and any node further out must hear nothing.
std::vector<size_t> reachable(const Topology &t) {
  std::vector<int> dist(MESH_NODES, -1);
  dist[t.origin] = 0;
  std::vector<size_t> q;
  q.push_back(t.origin);
  for (size_t head = 0; head < q.size(); ++head) {
    const size_t u = q[head];
    for (size_t v = 0; v < MESH_NODES; ++v) {
      if (!t.adj[u][v] || dist[v] != -1) continue;
      dist[v] = dist[u] + 1;
      q.push_back(v);
    }
  }
  // A frame is forwarded only while hop_limit >= 2, so the origin's TTL of N
  // reaches exactly N hops: the nodes at distance 1..N are all receivers, and
  // the ones just beyond must hear nothing.
  const int max_hops = (int)t.hop_limit;
  std::vector<size_t> out;
  for (size_t i = 0; i < MESH_NODES; ++i) {
    if (i == t.origin) continue;
    if (dist[i] > 0 && dist[i] <= max_hops &&
        std::find(t.scope.begin(), t.scope.end(), i) != t.scope.end())
      out.push_back(i);
  }
  return out;
}

// -------------------------------------------------------------------- Sim ---

Sim::Sim(const Topology &top, bool dedup) : top_(top) {
  for (size_t i = 0; i < MESH_NODES; ++i) {
    MeshConfig cfg;
    cfg.node_id = (NodeId)(i + 1);
    cfg.hop_limit = top.hop_limit;
    cfg.tx_airtime_ms = 0;    // host model: sending is instantaneous
    cfg.ack_timeout_ms = 80;  // advanced explicitly via advance_to()
    cfg.backoff_multiplier = 2;
    cfg.max_attempts = 3;
    cfg.dup_capacity = 256;
    cfg.dedup_enabled = dedup;
    cfg.frag_capacity = 4;
    radios_[i] = new RadioHalFake(0);
    radios_[i]->configure(cfg.to_radio());
    nodes_[i] = new Node(cfg, radios_[i]);
  }
  set_adjacency();
}

Sim::~Sim() {
  for (size_t i = 0; i < MESH_NODES; ++i) {
    delete nodes_[i];
    delete radios_[i];
  }
}

Node &Sim::node(size_t zero_based) { return *nodes_[zero_based]; }
RadioHalFake &Sim::radio(size_t zero_based) { return *radios_[zero_based]; }

uint32_t Sim::now(size_t zero_based) const {
  return radios_[zero_based]->now_ms();
}

void Sim::set_adjacency() {
  for (size_t i = 0; i < MESH_NODES; ++i) {
    NodeId ids[MESH_MAX_NEIGHBORS];
    size_t c = 0;
    const bool i_in_scope =
        std::find(top_.scope.begin(), top_.scope.end(), i) != top_.scope.end();
    for (size_t j = 0; j < MESH_NODES && c < MESH_MAX_NEIGHBORS; ++j) {
      if (i == j || !i_in_scope || !top_.adj[i][j]) continue;
      ids[c++] = (NodeId)(j + 1);
    }
    nodes_[i]->set_neighbors(ids, c);
  }
}

void Sim::tick_all() {
  uint8_t buf[MESH_HEADER_SIZE + MESH_MAX_PAYLOAD];
  for (size_t i = 0; i < MESH_NODES; ++i) {
    for (int s = 0; s < 64; ++s) {  // one unit of work at a time
      if (!nodes_[i]->tick()) break;
      collect(i);
    }
    // process anything this node received in the same instant
    collect(i);
    (void)buf;
  }
}

void Sim::collect(size_t i) {
  uint8_t buf[MESH_HEADER_SIZE + MESH_MAX_PAYLOAD];
  size_t len = 0;
  uint32_t td = 0;
  while (radios_[i]->pop_transmitted(buf, sizeof buf, &len, &td)) {
    LinkFrame f;
    f.from = i;
    f.t = td;
    f.bytes.assign(buf, buf + len);
    link_.push_back(f);
    if (link_.size() > 8192) return;  // safety valve; never reached in these tests
  }
}

void Sim::deliver_queued() {
  for (size_t k = 0; k < link_.size(); ++k) {
    const LinkFrame &f = link_[k];
    for (size_t j = 0; j < top_.scope.size(); ++j) {
      const size_t dst = top_.scope[j];
      if (dst == f.from) continue;          // a node does not hear itself
      if (!top_.adj[f.from][dst]) continue; // out of radio range
      radios_[dst]->push_incoming(f.bytes.data(), f.bytes.size(),
                                  f.t + kHopLatencyMs);
    }
  }
  link_.clear();
}

void Sim::quiesce() {
  // Repeat until the whole mesh is quiet: a node with a pending frame transmits
  // it, and every transmitted frame is handed to its neighbours, which may then
  // transmit in turn. Zero relay latency keeps a flood single-instant.
  //
  // Bounded: each pass either transmits something (which strictly decreases the
  // remaining flood work) or finds nothing to do. The generous cap only exists
  // so a bug in the suppression logic shows up as a timeout, not a hang.
  for (int rounds = 0; rounds < 200000; ++rounds) {
    tick_all();
    if (link_.empty() && !any_work()) return;
    deliver_queued();
  }
}

bool Sim::any_work() const {
  for (size_t i = 0; i < MESH_NODES; ++i)
    if (nodes_[i]->has_work() || radios_[i]->has_arrival()) return true;
  return false;
}

void Sim::advance_to(uint32_t t) {
  for (size_t i = 0; i < MESH_NODES; ++i) {
    const uint32_t n = radios_[i]->now_ms();
    if (n < t) radios_[i]->advance_ms(t - n);
  }
  quiesce();
}

uint16_t Sim::bcast(size_t origin, uint16_t pkt_id, const uint8_t *pl,
                    size_t len) {
  nodes_[origin]->send(MESH_BROADCAST, pl, len, pkt_id);
  quiesce();
  return pkt_id;
}

uint16_t Sim::bcast_str(size_t origin, uint16_t pkt_id, const char *s) {
  return bcast(origin, pkt_id, (const uint8_t *)s, std::strlen(s));
}

void Sim::drain() {
  // Accumulates across calls so a scenario can inspect everything that was
  // delivered. Scenarios are independent, but each Sim instance is used for more
  // than one flood, so counts are always keyed on the packet id under test.
  for (size_t i = 0; i < MESH_NODES; ++i) {
    std::vector<uint8_t> msg;
    NodeId src = 0;
    uint16_t id = 0;
    while (nodes_[i]->reassembly().take(&msg, &src, &id)) {
      Msg m;
      m.node = (NodeId)(i + 1);
      m.pkt_id = id;
      m.src = src;
      m.bytes = msg;
      msgs_.push_back(m);
    }
  }
}

int Sim::delivered_count(NodeId node, uint16_t id) const {
  int c = 0;
  for (size_t i = 0; i < msgs_.size(); ++i)
    if (msgs_[i].pkt_id == id && msgs_[i].node == node) ++c;
  return c;
}

bool Sim::check_exactly(const std::vector<size_t> &receiver_idx, uint16_t id,
                        const std::vector<uint8_t> &golden) {
  drain();
  int total = 0;
  for (size_t i = 0; i < msgs_.size(); ++i)
    if (msgs_[i].pkt_id == id) ++total;
  bool ok = true;
  if (total != (int)receiver_idx.size()) {
    std::fprintf(stderr,
                 "  [sim] pkt %u delivered %d time(s); expected exactly %zu\n",
                 (unsigned)id, total, receiver_idx.size());
    ok = false;
  }
  for (size_t k = 0; k < receiver_idx.size(); ++k) {
    const NodeId want = (NodeId)(receiver_idx[k] + 1);
    int hits = 0;
    for (size_t i = 0; i < msgs_.size(); ++i) {
      if (msgs_[i].pkt_id != id || msgs_[i].node != want) continue;
      ++hits;
      if (msgs_[i].bytes != golden) {
        std::fprintf(stderr, "  [sim] pkt %u at node %u: payload differs\n",
                     (unsigned)id, (unsigned)want);
        ok = false;
      }
    }
    if (hits != 1) {
      std::fprintf(stderr, "  [sim] pkt %u reached node %u %d time(s)\n",
                   (unsigned)id, (unsigned)want, hits);
      ok = false;
    }
  }
  return ok;
}

uint32_t Sim::total_forwarded() const {
  uint32_t s = 0;
  for (size_t i = 0; i < MESH_NODES; ++i) s += nodes_[i]->stats().forwarded;
  return s;
}
uint32_t Sim::total_duplicates() const {
  uint32_t s = 0;
  for (size_t i = 0; i < MESH_NODES; ++i) s += nodes_[i]->stats().rx_duplicates;
  return s;
}
uint32_t Sim::total_reroutes() const {
  uint32_t s = 0;
  for (size_t i = 0; i < MESH_NODES; ++i) s += nodes_[i]->stats().drops_no_route;
  return s;
}
uint32_t Sim::total_corrupt() const {
  uint32_t s = 0;
  for (size_t i = 0; i < MESH_NODES; ++i)
    s += nodes_[i]->reassembly().corrupt_completions();
  return s;
}
uint32_t Sim::total_own_echo() const {
  uint32_t s = 0;
  for (size_t i = 0; i < MESH_NODES; ++i) s += nodes_[i]->stats().drops_own;
  return s;
}

// -------------------------------------------------------------- scenarios ---

std::string Sim::digest_of(uint16_t id, const std::vector<size_t> &expect) const {
  std::string d = "pkt=" + std::to_string((unsigned)id) + " expect=" +
                  join_nodes(expect) + " got=";
  bool first = true;
  for (size_t i = 0; i < msgs_.size(); ++i) {
    if (msgs_[i].pkt_id != id) continue;
    if (!first) d += ";";
    first = false;
    d += std::to_string((int)msgs_[i].node) + ":" +
         hexdump(msgs_[i].bytes.data(), msgs_[i].bytes.size());
  }
  return d;
}

SceneResult run_scene(const Topology &top) {
  SceneResult r;
  r.ok = true;
  Sim sim(top);
  const std::string name = top.name;
  std::string dig;

  // The receiver set is DERIVED from the topology, not hand-written: the origin
  // plus one hop per forward means every node at distance 1..hop_limit receives.
  // Addressing receivers by name rather than index is deliberate -- see
  // delivered_count_idx().
  const std::vector<size_t> rx = reachable(top);
  std::vector<size_t> must_not;
  for (size_t i = 0; i < MESH_NODES; ++i) {
    if (i == top.origin) continue;
    if (std::find(rx.begin(), rx.end(), i) != rx.end()) continue;
    must_not.push_back(i);
  }

  auto do_flood = [&](uint16_t id, const char *s) -> bool {
    const std::vector<uint8_t> golden(s, s + std::strlen(s));
    sim.bcast_str(top.origin, id, s);
    bool ok = sim.check_exactly(rx, id, golden);
    for (size_t k = 0; k < must_not.size(); ++k)
      if (sim.delivered_count_idx(must_not[k], id) != 0) ok = false;
    dig += sim.digest_of(id, rx);
    dig += " must_not=" + join_nodes(must_not) + "\n";
    return ok;
  };

  if (name == "line6") {
    if (!do_flood(100, "LINE6")) r.ok = false;
  } else if (name == "line8_tight") {
    if (!do_flood(100, "TIGHT")) r.ok = false;
  } else if (name == "diamond") {
    if (!do_flood(200, "DIAMOND!")) r.ok = false;
  } else if (name == "ring6") {
    if (!do_flood(300, "RING6!!!")) r.ok = false;
  } else if (name == "star") {
    if (!do_flood(400, "STAR")) r.ok = false;
  } else if (name == "line4") {
    // the SAME packet id twice: still one delivery per receiver
    {
      const std::vector<uint8_t> golden = {'D', 'U', 'P', '!'};
      sim.bcast_str(top.origin, 500, "DUP!");
      sim.bcast_str(top.origin, 500, "DUP!");
      if (!sim.check_exactly(rx, 500, golden)) r.ok = false;
      for (size_t k = 0; k < must_not.size(); ++k)
        if (sim.delivered_count_idx(must_not[k], 500) != 0) r.ok = false;
      dig += sim.digest_of(500, rx) + " (flooded twice)\n";
    }
    // two distinct floods, both delivered in full
    if (!do_flood(600, "A600")) r.ok = false;
    if (!do_flood(601, "A601")) r.ok = false;
  }

  dig += "forwarded=" + std::to_string(sim.total_forwarded()) +
         " duplicates=" + std::to_string(sim.total_duplicates()) +
         " reroute=" + std::to_string(sim.total_reroutes()) +
         " own_echo=" + std::to_string(sim.total_own_echo()) +
         " corrupt=" + std::to_string(sim.total_corrupt()) + "\n";
  if (sim.total_corrupt() != 0) r.ok = false;
  // In a topology with more than one path to a node, the flood MUST have produced
  // duplicates for the suppression to have had anything to suppress. Requiring
  // this stops "exactly one delivery" from being satisfied vacuously by a mesh
  // that simply never delivered the repeat in the first place.
  if (name == "line6" || name == "diamond" || name == "ring6" ||
      name == "star") {
    if (sim.total_duplicates() == 0) r.ok = false;
  }
  sim.drain();
  r.total_deliveries = (int)sim.msgs().size();
  r.digest = dig;
  return r;
}


SceneResult run_stress(const Topology &top, bool dedup) {
  SceneResult r;
  r.ok = true;
  Sim sim(top, dedup);
  for (int k = 0; k < 6; ++k) {
    char s[16];
    std::snprintf(s, sizeof s, "PKT%02d", k);
    sim.bcast_str(top.origin, (uint16_t)(1000 + k), s);
  }
  sim.drain();
  const std::vector<size_t> rx = reachable(top);
  std::string dig;
  int per_receiver = 0;
  for (size_t idx = 0; idx < MESH_NODES; ++idx) {
    const bool is_rx = std::find(rx.begin(), rx.end(), idx) != rx.end();
    dig += "node" + std::to_string((int)(idx + 1)) + ":";
    for (int k = 0; k < 6; ++k) {
      // Counted by topology index, and only for the ids this exercise sent.
      const int c = sim.delivered_count_idx(idx, (uint16_t)(1000 + k));
      dig += " " + std::to_string(c);
      if (is_rx) {
        if (c != 1) r.ok = false;  // every reachable node, exactly once
      } else if (c != 0) {
        r.ok = false;              // everyone else must hear nothing
      }
      per_receiver += c;
    }
    dig += "\n";
  }
  if (sim.total_corrupt() != 0) r.ok = false;
  r.total_deliveries = per_receiver;
  dig += "deliveries_total=" + std::to_string(per_receiver) +
         " forwarded=" + std::to_string(sim.total_forwarded()) +
         " duplicates=" + std::to_string(sim.total_duplicates()) + "\n";
  r.digest = dig;
  return r;
}

SceneResult run_stress_no_dedup(const Topology &top) {
  // Its `ok` field is false by construction: the six floods are no longer
  // bounded to one delivery per receiver, which is exactly the point.
  return run_stress(top, false);
}

SceneResult run_ack_relay() {
  SceneResult r;
  r.ok = true;
  const Topology &top = line4();  // 1--2--3--4
  Sim sim(top);
  // Node 4 unicasts to node 2; node 2's app ACKs; the ACK must ride back through
  // node 3 to reach node 4 and cancel its retransmit timer.
  uint8_t pl[4] = {7, 7, 7, 7};
  if (!sim.node(3).send(2, pl, 4, 700)) r.ok = false;
  sim.quiesce();

  const uint32_t tx_after_hop = sim.node(3).stats().tx_attempts;
  if (tx_after_hop != 1) r.ok = false;
  if (sim.node(1).stats().ack_sent != 0) r.ok = false;  // it is only a relay

  // Node 2 received the datagram; let the app ACK it.
  sim.node(1).ack(sim.last_rx_header(1));
  sim.quiesce();

  if (sim.node(1).stats().ack_sent != 1) r.ok = false;
  if (sim.node(3).stats().ack_received != 1) r.ok = false;
  if (sim.node(3).stats().failures != 0) r.ok = false;

  // Advance well past every timer: an ACKed datagram must never retransmit.
  const uint32_t settled = sim.node(3).stats().tx_attempts;
  sim.advance_to(5000);
  if (sim.node(3).stats().tx_attempts != settled) r.ok = false;
  if (sim.node(3).stats().retransmits != 0) r.ok = false;

  std::string dig;
  // Read the receiver's own delivery counter: its reassembled message was taken
  // by the application to build the ACK, so it is no longer sitting in the
  // reassembler queue where delivered_count* would look for it.
  dig += "pkt=700 delivered=" +
         std::to_string(sim.node(1).stats().delivered) +
         " acks_sent=" + std::to_string(sim.node(1).stats().ack_sent) +
         " acks_received=" + std::to_string(sim.node(3).stats().ack_received) +
         " tx_attempts=" + std::to_string(sim.node(3).stats().tx_attempts) +
         " retransmits=" + std::to_string(sim.node(3).stats().retransmits) +
         " failures=" + std::to_string(sim.node(3).stats().failures) + "\n";
  r.total_deliveries = sim.delivered_count_idx(1, 700);
  r.digest = dig;
  return r;
}

// --------------------------------------------------------------- utilities --

uint64_t hexdigest(const std::string &s) {
  uint64_t h = 1469598103934665603ULL;  // FNV-1a 64
  for (size_t i = 0; i < s.size(); ++i) {
    h ^= (uint64_t)(unsigned char)s[i];
    h *= 1099511628211ULL;
  }
  return h;
}

std::string dot_graph() {
  std::string g = "graph mesh {\n  layout=neato;\n  overlap=false;\n";
  const std::vector<const Topology *> &tops = all_topologies();
  for (size_t k = 0; k < tops.size(); ++k) {
    const Topology &t = *tops[k];
    for (size_t i = 0; i < t.scope.size(); ++i) {
      const size_t n = t.scope[i];
      g += "  n" + std::to_string((int)(n + 1)) + " [label=\"" +
           std::to_string((int)(n + 1)) + "\\n" + t.name + "\"];\n";
    }
    for (size_t i = 0; i < MESH_NODES; ++i)
      for (size_t j = i + 1; j < MESH_NODES; ++j)
        if (t.adj[i][j])
          g += "  n" + std::to_string((int)(i + 1)) + " -- n" +
               std::to_string((int)(j + 1)) + " [label=\"" + t.name + "\"];\n";
  }
  g += "}\n";
  return g;
}

bool check_all(std::string *report) {
  std::string out;
  bool all = true;
  const std::vector<const Topology *> &tops = all_topologies();
  for (size_t k = 0; k < tops.size(); ++k) {
    SceneResult r = run_scene(*tops[k]);
    char line[128];
    std::snprintf(line, sizeof line, "== %-12s ok=%s digest=%016llx ==\n",
                  tops[k]->name, r.ok ? "yes" : "NO",
                  (unsigned long long)hexdigest(r.digest));
    out += line;
    out += r.digest;
    if (!r.ok) all = false;
  }
  for (size_t k = 0; k < tops.size(); ++k) {
    SceneResult r = run_stress(*tops[k]);
    char line[128];
    std::snprintf(line, sizeof line,
                  "== stress %-7s ok=%s digest=%016llx ==\n", tops[k]->name,
                  r.ok ? "yes" : "NO", (unsigned long long)hexdigest(r.digest));
    out += line;
    out += r.digest;
    if (!r.ok) all = false;
  }
  SceneResult a = run_ack_relay();
  out += "== ack_relay ok=";
  out += a.ok ? "yes" : "NO";
  out += " digest=" + std::to_string((unsigned long long)hexdigest(a.digest)) +
         " ==\n" + a.digest;
  if (!a.ok) all = false;
  out += "CHECK: ";
  out += all ? "OK" : "FAIL";
  out += "\n";
  if (report != nullptr) *report = out;
  return all;
}

}  // namespace sim
}  // namespace mesh
}  // namespace balloon
