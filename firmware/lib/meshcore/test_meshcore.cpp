// Top-level entry point for the meshcore module.
//
// ONE translation unit defines main(): firmware/lib's Makefile compiles every
// *.cpp in a module into a SINGLE executable, and harness.h keeps its check
// counters in static (per-TU) variables, so two TEST_MAIN translation units would
// each link -- with separate, silent counters. Everything therefore lives here.
//
// Running it with no arguments prints the simulated mesh as Graphviz DOT (stable,
// no timestamps, diffable). Running it with --check runs every scenario and
// verifies its digest -- that is the CLI seam used to host-test the mesh.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>

#include "harness.h"
#include "meshcodec.h"  // the compiled constants the template values must match
#include "meshcore.h"   // generated: the template-rendered constants
#include "meshsim.h"

using namespace balloon::mesh;
using namespace balloon::mesh::sim;

namespace {

void fill(uint8_t *p, size_t n, uint8_t base) {
  for (size_t i = 0; i < n; ++i) p[i] = (uint8_t)(base + i);
}

// Feed one frame to a node as if the radio had handed it over.
void deliver(Node &n, MeshType type, NodeId src, NodeId dst, uint16_t id,
             uint8_t hop, uint8_t fi, uint8_t fc, const uint8_t *pl,
             size_t pln) {
  Header h{};
  h.version = MESH_WIRE_VERSION;
  h.type = type;
  h.src = src;
  h.dst = dst;
  h.pkt_id = id;
  h.hop_limit = hop;
  h.frag_index = fi;
  h.frag_count = fc;
  h.payload_len = (uint8_t)pln;
  uint8_t frame[MESH_HEADER_SIZE + MESH_MAX_PAYLOAD];
  size_t w = 0;
  encode_header(h, frame, sizeof frame, &w);
  if (pln) std::memcpy(frame + MESH_HEADER_SIZE, pl, pln);
  n.fake()->push_incoming(frame, w, n.fake()->now_ms());
}

void advance(RadioHalFake &radio, Node &n, uint32_t ms) {
  radio.advance_ms(ms);
  n.flush();
}

// Build a frame by hand, bypassing encode_header when a forgery is wanted.
size_t raw_frame(uint8_t *out, MeshType type, NodeId src, NodeId dst, uint16_t id,
                 uint8_t hop, uint8_t fi, uint8_t fc, uint8_t plen,
                 const uint8_t *pl) {
  Header h{};
  h.version = MESH_WIRE_VERSION;
  h.type = type;
  h.src = src;
  h.dst = dst;
  h.pkt_id = id;
  h.hop_limit = hop;
  h.frag_index = fi;
  h.frag_count = fc;
  h.payload_len = plen;
  size_t w = 0;
  encode_header(h, out, MESH_HEADER_SIZE + MESH_MAX_PAYLOAD, &w);
  if (plen && pl) std::memcpy(out + MESH_HEADER_SIZE, pl, plen);
  return w;
}

}  // namespace

void run_tests() {
  // =========================== single-node semantics ========================

  CASE("a Data frame addressed to us is delivered exactly once");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);

    uint8_t pl[4] = {1, 2, 3, 4};
    deliver(n, MeshType::Data, 1, 2, 0x0101, 4, 0, 1, pl, 4);
    n.flush();

    CHECK_EQ(n.stats().delivered, 1);
    CHECK_EQ(n.reassembly().completed(), 1);
    CHECK(n.reassembly().has_completed());
    std::vector<uint8_t> msg;
    NodeId src = 0;
    uint16_t id = 0;
    CHECK(n.reassembly().take(&msg, &src, &id));
    CHECK_EQ(src, 1);
    CHECK_EQ(id, 0x0101);
    CHECK_EQ(msg.size(), 4);
    CHECK_EQ(msg[0], 1);
    CHECK_EQ(msg[3], 4);
    CHECK_EQ(n.stats().forwarded, 0);
  }

  CASE("the same frame again is suppressed as a duplicate");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[4] = {1, 2, 3, 4};
    deliver(n, MeshType::Data, 1, 2, 0x0101, 4, 0, 1, pl, 4);
    n.flush();
    {
      std::vector<uint8_t> msg;   // consume the first delivery
      NodeId src = 0;
      uint16_t id = 0;
      CHECK(n.reassembly().take(&msg, &src, &id));
    }
    deliver(n, MeshType::Data, 1, 2, 0x0101, 4, 0, 1, pl, 4);
    n.flush();
    CHECK_EQ(n.stats().rx_duplicates, 1);
    CHECK_EQ(n.stats().delivered, 1);
    CHECK(!n.reassembly().has_completed());
  }

  CASE("a broadcast frame is delivered locally and re-broadcast with TTL-1");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    cfg.hop_limit = 4;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);

    uint8_t pl[2] = {9, 8};
    deliver(n, MeshType::Data, 1, MESH_BROADCAST, 0x0202, 4, 0, 1, pl, 2);
    n.flush();

    CHECK_EQ(n.stats().delivered, 1);
    CHECK_EQ(n.stats().forwarded, 1);
    CHECK_EQ(n.stats().rebroadcast, 1);
    uint8_t out[128];
    size_t len = 0;
    uint32_t t = 0;
    CHECK(radio.pop_transmitted(out, sizeof out, &len, &t));
    Header fh{};
    const uint8_t *fpl = nullptr;
    size_t fpln = 0;
    CHECK(decode_header(out, len, &fh, &fpl, &fpln) == CodecResult::Ok);
    CHECK_EQ(fh.hop_limit, 3);  // exactly one hop consumed
    CHECK_EQ(fh.pkt_id, 0x0202);
    CHECK_EQ(fh.src, 1);        // the origin is preserved, not rewritten
    CHECK_EQ(fh.dst, MESH_BROADCAST);
  }

  CASE("the duplicate of that broadcast is dropped, not re-flooded");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    cfg.hop_limit = 4;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[2] = {9, 8};
    deliver(n, MeshType::Data, 1, MESH_BROADCAST, 0x0202, 4, 0, 1, pl, 2);
    n.flush();
    deliver(n, MeshType::Data, 1, MESH_BROADCAST, 0x0202, 4, 0, 1, pl, 2);
    n.flush();
    CHECK_EQ(n.stats().forwarded, 1);
    CHECK_EQ(n.stats().rx_duplicates, 1);
  }

  CASE("hop_limit 1 delivers here and stops: one hop is one hop");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[1] = {5};
    deliver(n, MeshType::Data, 1, MESH_BROADCAST, 0x0303, 1, 0, 1, pl, 1);
    n.flush();
    CHECK_EQ(n.stats().delivered, 1);
    CHECK_EQ(n.stats().forwarded, 0);
    CHECK_EQ(n.stats().rebroadcast, 0);

    CASE("hop_limit 2 delivers here and forwards one hop further");
    MeshConfig cfg2;
    cfg2.node_id = 2;
    RadioHalFake radio2;
    radio2.configure(cfg2.to_radio());
    Node n2(cfg2, &radio2);
    deliver(n2, MeshType::Data, 1, MESH_BROADCAST, 0x0304, 2, 0, 1, pl, 1);
    n2.flush();
    CHECK_EQ(n2.stats().delivered, 1);
    CHECK_EQ(n2.stats().forwarded, 1);
  }

  CASE("our own flood heard back from a neighbour is dropped, not delivered");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[2] = {9, 8};
    deliver(n, MeshType::Data, 2, MESH_BROADCAST, 0x0404, 4, 0, 1, pl, 2);
    n.flush();
    CHECK_EQ(n.stats().drops_own, 1);
    CHECK_EQ(n.stats().delivered, 0);
    CHECK_EQ(n.stats().forwarded, 0);
    CHECK_EQ(n.stats().rx_duplicates, 0);
  }

  CASE("a unicast frame for an unreachable destination is dropped, not flooded");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    cfg.neighbor_count = 1;
    cfg.neighbors[0] = 1;
    cfg.hop_limit = 2;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[1] = {7};
    deliver(n, MeshType::Data, 1, 9, 0x0505, 2, 0, 1, pl, 1);
    n.flush();
    CHECK_EQ(n.stats().drops_no_route, 1);
    CHECK_EQ(n.stats().forwarded, 0);
  }

  CASE("a unicast frame whose destination IS our neighbour is forwarded");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    cfg.neighbor_count = 1;
    cfg.neighbors[0] = 9;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[1] = {7};
    deliver(n, MeshType::Data, 1, 9, 0x0606, 2, 0, 1, pl, 1);
    n.flush();
    CHECK_EQ(n.stats().forwarded, 1);
    CHECK_EQ(n.stats().delivered, 0);
  }

  CASE("an Ack is never itself acknowledged and never forwarded");
  {
    MeshConfig cfg;
    cfg.node_id = 1;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    Header rx{};
    rx.version = MESH_WIRE_VERSION;
    rx.type = MeshType::Ack;
    rx.src = 9;
    rx.dst = 1;
    rx.pkt_id = 0x0707;
    rx.hop_limit = 2;
    rx.frag_index = 0;
    rx.frag_count = 1;
    rx.payload_len = 0;
    CHECK(!n.ack(rx));
    CHECK(!n.has_work());
  }

  // =================== duplicate suppression is load-bearing ================

  CASE("dedup on: 5 identical frames -> exactly one delivery");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[1] = {1};
    for (int k = 0; k < 5; ++k)
      deliver(n, MeshType::Data, 1, 2, 0x0808, 4, 0, 1, pl, 1);
    n.flush();
    CHECK_EQ(n.stats().delivered, 1);
    CHECK_EQ(n.stats().rx_duplicates, 4);
  }

  CASE("dedup off: the SAME 5 frames storm through -- the check above is exactly "
       "what made the count 1");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    cfg.dedup_enabled = false;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[1] = {1};
    for (int k = 0; k < 5; ++k)
      deliver(n, MeshType::Data, 1, 2, 0x0808, 4, 0, 1, pl, 1);
    n.flush();
    CHECK_EQ(n.stats().delivered, 5);
    CHECK_EQ(n.stats().rx_duplicates, 0);
  }

  CASE("the seen-cache evicts and never grows without bound (counter-test)");
  {
    DupCache c(4);
    CHECK_EQ(c.capacity(), 4);
    for (int i = 0; i < 100; ++i) CHECK(!c.seen_or_add(1, (uint16_t)i, 0));
    CHECK_EQ(c.capacity(), 4);
    CHECK_EQ(c.size(), 4);
    CHECK(c.evictions() > 0);
    CHECK(c.seen_or_add(1, 99, 0));  // the newest is still recognised
    CHECK(!c.seen_or_add(1, 0, 0));  // the oldest was evicted
    c.set_capacity(2);
    CHECK_EQ(c.capacity(), 2);
    CHECK(c.size() <= 2);
  }

  // ============================== ACK reliability ===========================

  CASE("ACK: a missing ACK retransmits with backoff; an ACK then cancels it");
  {
    MeshConfig cfg;
    cfg.node_id = 1;
    cfg.hop_limit = 2;
    cfg.ack_timeout_ms = 100;
    cfg.backoff_multiplier = 2;
    cfg.max_attempts = 4;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);

    uint8_t pl[3] = {1, 2, 3};
    CHECK(n.send(9, pl, 3, 0x0909));
    n.flush();
    CHECK_EQ(n.stats().tx_attempts, 1);

    advance(radio, n, 100);
    CHECK(n.stats().tx_attempts >= 2);
    CHECK_EQ(n.stats().retransmits, n.stats().tx_attempts - 1);

    deliver(n, MeshType::Ack, 9, 1, 0x0909, 2, 0, 1, nullptr, 0);
    n.flush();
    CHECK_EQ(n.stats().ack_received, 1);
    const uint32_t settled = n.stats().tx_attempts;
    advance(radio, n, 5000);
    CHECK_EQ(n.stats().tx_attempts, settled);  // a settled datagram never retries
    CHECK_EQ(n.stats().failures, 0);
  }

  CASE("ACK: gives up after exactly max_attempts, never loops forever");
  {
    MeshConfig cfg;
    cfg.node_id = 1;
    cfg.hop_limit = 2;
    cfg.ack_timeout_ms = 10;
    cfg.backoff_multiplier = 4;
    cfg.max_attempts = 3;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);

    uint8_t pl[1] = {42};
    CHECK(n.send(9, pl, 1, 0x0A0A));
    n.flush();
    for (int i = 0; i < 12; ++i) advance(radio, n, 1000);
    CHECK_EQ(n.stats().tx_attempts, 3);
    CHECK_EQ(n.stats().retransmits, 2);
    CHECK_EQ(n.stats().failures, 1);
    CHECK(!n.has_work());
    CHECK_EQ(n.next_wake_ms(), MESH_NO_WAKE);
  }

  CASE("no ACK is armed for a broadcast");
  {
    MeshConfig cfg;
    cfg.node_id = 1;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[1] = {1};
    CHECK(n.send(MESH_BROADCAST, pl, 1, 0x0B0B));
    n.flush();
    for (int i = 0; i < 8; ++i) advance(radio, n, 1000);
    CHECK_EQ(n.stats().tx_attempts, 1);
    CHECK_EQ(n.stats().failures, 0);
    CHECK(!n.has_work());
  }

  CASE("no ACK is armed when ack_enabled is false");
  {
    MeshConfig cfg;
    cfg.node_id = 1;
    cfg.ack_enabled = false;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[1] = {1};
    CHECK(n.send(9, pl, 1, 0x0C0C));
    n.flush();
    for (int i = 0; i < 8; ++i) advance(radio, n, 1000);
    CHECK_EQ(n.stats().tx_attempts, 1);
    CHECK_EQ(n.stats().failures, 0);
  }

  // ============================ fragmentation ===============================

  CASE("fragmentation: a >MTU datagram splits and reassembles byte-exact");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);

    uint8_t big[100];
    fill(big, sizeof big, 0);
    for (uint8_t fi = 0; fi < 2; ++fi) {
      const size_t off = (size_t)fi * MESH_MAX_PAYLOAD;
      const size_t nb = (sizeof big - off > MESH_MAX_PAYLOAD) ? MESH_MAX_PAYLOAD
                                                              : sizeof big - off;
      deliver(n, MeshType::Data, 1, 2, 0x0D0D, 3, fi, 2, big + off, nb);
      n.flush();
      if (fi == 0) CHECK(!n.reassembly().has_completed());
    }
    CHECK_EQ(n.stats().delivered, 1);
    std::vector<uint8_t> msg;
    NodeId src = 0;
    uint16_t id = 0;
    CHECK(n.reassembly().take(&msg, &src, &id));
    CHECK_EQ(msg.size(), sizeof big);
    CHECK(std::memcmp(msg.data(), big, sizeof big) == 0);
  }

  CASE("a 512-byte datagram needs all 8 frames before it completes");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t big[MESH_MAX_DATAGRAM];
    fill(big, sizeof big, 0x11);
    const uint8_t fc = (uint8_t)(sizeof big / MESH_MAX_PAYLOAD);
    CHECK_EQ(fc, 8);
    for (uint8_t fi = 0; fi < fc; ++fi) {
      const size_t off = (size_t)fi * MESH_MAX_PAYLOAD;
      deliver(n, MeshType::Data, 1, 2, 0x0E0E, 3, fi, fc, big + off,
              MESH_MAX_PAYLOAD);
      n.flush();
      if (fi + 1 < fc) CHECK(!n.reassembly().has_completed());
    }
    CHECK(n.reassembly().has_completed());
    std::vector<uint8_t> msg;
    NodeId src = 0;
    uint16_t id = 0;
    CHECK(n.reassembly().take(&msg, &src, &id));
    CHECK_EQ(msg.size(), sizeof big);
    CHECK(std::memcmp(msg.data(), big, sizeof big) == 0);
  }

  CASE("a missing fragment can NEVER produce a message, and a duplicate cannot "
       "stand in for it (counter-test)");
  {
    Reassembly r(2);
    uint8_t a[MESH_MAX_PAYLOAD];
    uint8_t b[MESH_MAX_PAYLOAD];
    fill(a, sizeof a, 1);
    fill(b, sizeof b, 2);

    CHECK_EQ((int)r.offer(1, 0x1111, 0, 3, MESH_MAX_PAYLOAD, a, sizeof a),
             (int)Reassembly::Status::Accepted);
    CHECK_EQ((int)r.offer(1, 0x1111, 0, 3, MESH_MAX_PAYLOAD, a, sizeof a),
             (int)Reassembly::Status::Duplicate);
    CHECK(!r.has_completed());
    CHECK_EQ(r.completed(), 0);
    CHECK_EQ(r.corrupt_completions(), 0);

    CHECK_EQ((int)r.offer(1, 0x1111, 2, 3, MESH_MAX_PAYLOAD, b, sizeof b),
             (int)Reassembly::Status::Accepted);
    CHECK(!r.has_completed());
    CHECK_EQ(r.completed(), 0);

    CHECK_EQ((int)r.offer(1, 0x1111, 1, 3, MESH_MAX_PAYLOAD, b, sizeof b),
             (int)Reassembly::Status::Complete);
    CHECK(r.has_completed());
    std::vector<uint8_t> msg;
    NodeId src = 0;
    uint16_t id = 0;
    CHECK(r.take(&msg, &src, &id));
    CHECK_EQ(msg.size(), 3 * MESH_MAX_PAYLOAD);
    CHECK_EQ(msg[0], 1);
    CHECK_EQ(msg[MESH_MAX_PAYLOAD], 2);
    CHECK_EQ(msg[2 * MESH_MAX_PAYLOAD], 2);
    CHECK_EQ(r.corrupt_completions(), 0);
  }

  CASE("an inconsistent fragment is refused");
  {
    Reassembly r(2);
    uint8_t a[8];
    fill(a, 8, 1);
    CHECK_EQ((int)r.offer(1, 0x2222, 3, 3, 8, a, 8),
             (int)Reassembly::Status::BadFragment);  // index >= count
    CHECK_EQ((int)r.offer(1, 0x2222, 0, 0, 8, a, 8),
             (int)Reassembly::Status::BadFragment);  // count 0
    CHECK_EQ((int)r.offer(1, 0x2222, 0, 1, (uint8_t)(MESH_MAX_PAYLOAD + 1), a, 8),
             (int)Reassembly::Status::BadFragment);  // over-MTU
    CHECK_EQ((int)r.offer(1, 0x2222, 0, 2, 8, a, 4),
             (int)Reassembly::Status::BadFragment);  // len != payload_len
    CHECK(!r.has_completed());
    CHECK(r.rejected() >= 4);
    CHECK_EQ(r.corrupt_completions(), 0);
  }

  CASE("reassembly flow capacity is bounded (counter-test)");
  {
    Reassembly r(1);
    uint8_t a[4] = {1, 2, 3, 4};
    CHECK_EQ((int)r.offer(1, 0x0001, 0, 2, 4, a, 4),
             (int)Reassembly::Status::Accepted);
    CHECK_EQ((int)r.offer(2, 0x0002, 0, 2, 4, a, 4),
             (int)Reassembly::Status::TooManyFlows);
    CHECK_EQ(r.slots(), 1);
    CHECK_EQ((int)r.offer(1, 0x0001, 1, 2, 4, a, 4),
             (int)Reassembly::Status::Complete);
    CHECK_EQ((int)r.offer(2, 0x0002, 0, 2, 4, a, 4),
             (int)Reassembly::Status::Accepted);
  }

  // ============================ refusal paths ===============================

  CASE("a datagram larger than the fragmentable maximum is refused");
  {
    MeshConfig cfg;
    cfg.node_id = 1;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t big[MESH_MAX_DATAGRAM + 1];
    fill(big, sizeof big, 0);
    CHECK(!n.send(9, big, sizeof big, 0x0F0F));
    CHECK(!n.has_work());
  }

  CASE("a radio that would refuse the packet is not silently used");
  {
    MeshConfig cfg;
    cfg.node_id = 1;
    cfg.max_packet_bytes = MESH_HEADER_SIZE + 2;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[8] = {1, 2, 3, 4, 5, 6, 7, 8};
    CHECK(!n.send(9, pl, sizeof pl, 0x1010));
    CHECK(!n.has_work());
    CHECK_EQ(n.stats().tx_frames, 0);
  }

  CASE("a truncated frame is dropped and never reaches the reassembler");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[4] = {1, 2, 3, 4};
    uint8_t frame[MESH_HEADER_SIZE + MESH_MAX_PAYLOAD];
    const size_t w = raw_frame(frame, MeshType::Data, 1, 2, 0x1111, 4, 0, 1, 4, pl);
    radio.push_incoming(frame, w - 1, 0);  // one byte short: header claims 4
    n.flush();
    CHECK_EQ(n.stats().rx_frames, 1);
    CHECK_EQ(n.stats().drops_bad_frame, 1);
    CHECK_EQ(n.stats().delivered, 0);
    CHECK(!n.reassembly().has_completed());
  }

  CASE("an over-long frame is dropped, never partially parsed");
  {
    MeshConfig cfg;
    cfg.node_id = 2;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[4] = {1, 2, 3, 4};
    uint8_t frame[MESH_HEADER_SIZE + MESH_MAX_PAYLOAD + 4];
    const size_t w = raw_frame(frame, MeshType::Data, 1, 2, 0x1212, 4, 0, 1, 4, pl);
    radio.push_incoming(frame, w + 1, 0);  // one trailing byte
    n.flush();
    CHECK_EQ(n.stats().drops_bad_frame, 1);
    CHECK_EQ(n.stats().delivered, 0);
  }

  CASE("the default logger is silent for a whole session");
  {
    MeshConfig cfg;
    cfg.node_id = 1;
    RadioHalFake radio;
    radio.configure(cfg.to_radio());
    Node n(cfg, &radio);
    uint8_t pl[2] = {1, 2};
    n.send(MESH_BROADCAST, pl, 2, 0x1313);
    n.flush();
    CHECK(!n.has_work());
  }

  // ================== deterministic simulated multi-hop mesh ==============

  CASE("sim/line6: a flood reaches 5 hops away, exactly once per node");
  {
    SceneResult r = run_scene(line6());
    if (!r.ok) std::fprintf(stderr, "%s", r.digest.c_str());
    CHECK(r.ok);
  }

  CASE("sim/line8_tight: hop_limit 4 makes the delivery set EXACTLY nodes 2..5");
  {
    SceneResult r = run_scene(line8_tight());
    if (!r.ok) std::fprintf(stderr, "%s", r.digest.c_str());
    CHECK(r.ok);
  }

  CASE("sim/diamond: node 4 hears the flood from both arms, delivers once");
  {
    SceneResult r = run_scene(diamond());
    if (!r.ok) std::fprintf(stderr, "%s", r.digest.c_str());
    CHECK(r.ok);
  }

  CASE("sim/ring6: two paths the short way, exactly one delivery everywhere");
  {
    SceneResult r = run_scene(ring6());
    if (!r.ok) std::fprintf(stderr, "%s", r.digest.c_str());
    CHECK(r.ok);
  }

  CASE("sim/star: every modelled node is one hop away, one delivery each");
  {
    SceneResult r = run_scene(star());
    if (!r.ok) std::fprintf(stderr, "%s", r.digest.c_str());
    CHECK(r.ok);
  }

  CASE("sim/line4: flood, repeated flood, and two distinct floods stay bounded");
  {
    SceneResult r = run_scene(line4());
    if (!r.ok) std::fprintf(stderr, "%s", r.digest.c_str());
    CHECK(r.ok);
  }

  CASE("sim: 6x6 flood stress gives exactly one delivery per (packet, receiver)");
  {
    SceneResult r = run_stress(line6());
    if (!r.ok) std::fprintf(stderr, "%s", r.digest.c_str());
    CHECK(r.ok);
  }

  CASE("sim: the ACK rides two hops back to the sender, which never retransmits");
  {
    SceneResult r = run_ack_relay();
    if (!r.ok) std::fprintf(stderr, "%s", r.digest.c_str());
    CHECK(r.ok);
  }

  CASE("sim: no scenario ever produced a corrupt reassembly");
  {
    const std::vector<const Topology *> &tops = all_topologies();
    for (size_t k = 0; k < tops.size(); ++k) {
      SceneResult r = run_scene(*tops[k]);
      SceneResult s = run_stress(*tops[k]);
      CHECK(r.ok);
      CHECK(s.ok);
    }
  }

  CASE("sim: digests are reproducible run to run");
  {
    SceneResult a = run_scene(line6());
    SceneResult b = run_scene(line6());
    CHECK(a.digest == b.digest);
    CHECK(hexdigest(a.digest) == hexdigest(b.digest));
  }

  CASE("sim: with dedup OFF the SAME line6 stress is no longer 1 per receiver "
       "(counter-test at the swarm level)");
  {
    SceneResult with = run_stress(line6());
    SceneResult without = run_stress_no_dedup(line6());
    CHECK(with.ok);
    CHECK(!without.ok);  // the storm breaks the invariant...
    CHECK(without.total_deliveries > with.total_deliveries);  // ...loudly
  }

  // ===== one-source-of-truth: template values vs every compiled copy =========

  CASE("template_values.sh agrees with every compiled copy of each constant");
  {
    // The file is the third, independent copy. Parsing it here (rather than
    // trusting the generator) is what catches a change made in only one place.
    std::ifstream in("meshcore/template_values.sh");
    CHECK(in.is_open());
    std::string line;
    int parsed = 0;
    while (std::getline(in, line)) {
      if (line.empty() || line[0] == '#') continue;
      std::istringstream ls(line);
      std::string name;
      unsigned long long value = 0;
      if (!(ls >> name >> value)) continue;
      ++parsed;
      if (name == "MESH_WIRE_VERSION") {
        CHECK_EQ(value, (unsigned long long)MESH_WIRE_VERSION);
        CHECK_EQ(value, (unsigned long long)tpl::MESH_WIRE_VERSION);
      } else if (name == "MESH_HEADER_SIZE") {
        CHECK_EQ(value, (unsigned long long)MESH_HEADER_SIZE);
        CHECK_EQ(value, (unsigned long long)tpl::MESH_HEADER_SIZE);
      } else if (name == "MESH_MAX_PAYLOAD") {
        CHECK_EQ(value, (unsigned long long)MESH_MAX_PAYLOAD);
        CHECK_EQ(value, (unsigned long long)tpl::MESH_MAX_PAYLOAD);
      } else if (name == "MESH_MAX_DATAGRAM") {
        CHECK_EQ(value, (unsigned long long)MESH_MAX_DATAGRAM);
        CHECK_EQ(value, (unsigned long long)tpl::MESH_MAX_DATAGRAM);
      } else if (name == "MESH_MAX_FRAGS") {
        CHECK_EQ(value, (unsigned long long)MESH_MAX_FRAGS);
        CHECK_EQ(value, (unsigned long long)tpl::MESH_MAX_FRAGS);
      } else if (name == "MESH_MAX_NEIGHBORS") {
        CHECK_EQ(value, (unsigned long long)MESH_MAX_NEIGHBORS);
        CHECK_EQ(value, (unsigned long long)tpl::MESH_MAX_NEIGHBORS);
      } else if (name == "MESH_NO_WAKE") {
        CHECK_EQ(value, (unsigned long long)MESH_NO_WAKE);
        CHECK_EQ(value, (unsigned long long)tpl::MESH_NO_WAKE);
      } else if (name == "MESH_MAX_BACKOFF_MS") {
        CHECK_EQ(value, (unsigned long long)MESH_MAX_BACKOFF_MS);
        CHECK_EQ(value, (unsigned long long)tpl::MESH_MAX_BACKOFF_MS);
      } else if (name == "MESH_MAX_QUEUE") {
        CHECK_EQ(value, (unsigned long long)MESH_MAX_QUEUE);
        CHECK_EQ(value, (unsigned long long)tpl::MESH_MAX_QUEUE);
      } else if (name == "MESH_NODES") {
        CHECK_EQ(value, (unsigned long long)MESH_NODES);
        CHECK_EQ(value, (unsigned long long)tpl::MESH_NODES);
      } else {
        CHECK(false);  // a new constant with no compiled counterpart to check
      }
    }
    CHECK_EQ(parsed, 10);
    // The simulation's node count must fit a node's neighbour table.
    CHECK(MESH_NODES <= MESH_MAX_NEIGHBORS);
  }

  CASE("the generated header is in sync with template_values.sh");
  {
    const int rc = std::system(
        "python3 meshcore/scripts/gen_meshcore_header.py --check "
        "--values meshcore/template_values.sh --header meshcore/meshcore.h "
        "> build/template_check.txt 2>&1");
    if (rc != 0) {
      std::ifstream fail("build/template_check.txt");
      std::fprintf(stderr, "  generator said:\n");
      std::string l;
      while (std::getline(fail, l)) std::fprintf(stderr, "    %s\n", l.c_str());
    }
    CHECK_EQ(rc, 0);
  }

  CASE("counter-test: the generated-header check FAILS on a mutated constant");
  {
    // Mutate exactly one constant in a copy and confirm the check rejects it.
    // Without this, "the header is in sync" could pass because the check is a
    // no-op rather than because the files agree.
    const int mut = std::system(
        "sed 's/^MESH_HEADER_SIZE 10$/MESH_HEADER_SIZE 11/' "
        "meshcore/template_values.sh > build/template_values_mutated.sh");
    CHECK_EQ(mut, 0);
    const int rc = std::system(
        "python3 meshcore/scripts/gen_meshcore_header.py --check "
        "--values build/template_values_mutated.sh --header meshcore/meshcore.h "
        "> build/template_check_mutated.txt 2>&1");
    CHECK(rc != 0);  // drift must be detected, not waved through
    // (and the real header must still be reported as in sync)
    const int rc2 = std::system(
        "python3 meshcore/scripts/gen_meshcore_header.py --check "
        "--values meshcore/template_values.sh --header meshcore/meshcore.h "
        "> /dev/null 2>&1");
    CHECK_EQ(rc2, 0);
  }
}

#ifndef MESH_NO_MAIN
int main(int argc, char **argv) {
  if (argc > 1 && std::strcmp(argv[1], "--check") == 0) {
    std::string report;
    const bool ok = check_all(&report);
    std::printf("%s", report.c_str());
    return ok ? 0 : 1;
  }
  if (argc > 1 && std::strcmp(argv[1], "--dot") == 0) {
    std::printf("%s", dot_graph().c_str());
    return 0;
  }
  run_tests();
  if (g_fails == 0) {
    std::printf("  ok   %d checks passed\n", g_checks);
    return 0;
  }
  std::printf("  FAIL %d of %d checks failed\n", g_fails, g_checks);
  return 1;
}
#endif
