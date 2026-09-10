#pragma once

#include <cstdint>
#include <cstring>

#include "NodeTable.h"
#include "UnionFind.h"

// StratoRelayMesh - cluster-aware bridge DECISION CORE (host-testable).
//
// Design reference: mesh-stack/research/routing/cluster-aware-bridge.md
//   section 2   the four mesh::Mesh virtual hooks we mirror
//   section 4   clustering by union-find over observed flood paths
//   section 6   cluster-head election (scoring formula 6.1)
//   section 7   packet filtering / bridging policy
//
// The firmware-side mesh::Mesh subclass keeps only the radio, identity and
// packet glue and delegates every routing decision to this class. Nothing here
// touches a radio, crypto or MeshCore types, so the whole policy is exercised
// by plain host unit tests (test/test_stratorelay_mesh.cpp).
//
// Hook mapping (MeshCore name -> decision-core name):
//   filterRecvFloodPacket(Packet*) -> filterRecvFloodPacket(sender), true = DROP
//   allowPacketForward(Packet*)    -> allowPacketForward(sender),    true = BRIDGE
//   onAdvertRecv(...)              -> observeAdvert(hash, snr, ts)
//   routeRecvPacket(Packet*)       -> bridgeTargets(sender, out, n)
//
// Policy (section 7):
//   unknown sender              -> ALLOW  (conservative, section 7 step 2)
//   sender == cluster head      -> ALLOW  + BRIDGE
//   known sender, non-head      -> DROP   (ground flood covers intra-cluster)
//   bridge never targets the origin's own cluster (no self-bridge)

template<int MAX_NODES = 256, int MAX_CLUSTERS = 32, int MAX_EDGES = 512>
class StratoRelayMesh {
public:
    static constexpr int UNKNOWN = -1;
    // section 6.1: stability term saturates at 100 observed adverts
    static constexpr uint16_t ADVERT_CAP = 100;

    struct Edge {
        uint8_t a;
        uint8_t b;
    };

    struct HeadInfo {
        uint8_t hash;
        int cluster_root;
    };

private:
    NodeTable<MAX_NODES> nodes_;
    // Union-find is indexed by NodeTable slot, not by hash (section 4.2). Slots
    // are recycled when NodeTable evicts the oldest node, which is why any
    // eviction triggers rebuildClusters() below.
    UnionFind<MAX_NODES> clusters_;
    uint16_t adverts_[MAX_NODES];
    Edge edges_[MAX_EDGES];
    int edge_count_;
    HeadInfo heads_[MAX_CLUSTERS];
    int head_count_;
    float recency_w_;
    float signal_w_;
    float stability_w_;

    float scoreOf(int slot, uint32_t now) const {
        const typename NodeTable<MAX_NODES>::NodeRecord& n = nodes_.get(slot);
        uint32_t age = now - n.last_heard;
        float recency = recency_w_ / (float)(age + 1u);
        float signal = signal_w_ * (float)(n.last_snr + 20);
        float stability = stability_w_ * (float)adverts_[slot] / (float)ADVERT_CAP;
        return recency + signal + stability;
    }

    bool recordEdge(uint8_t a, uint8_t b) {
        if (a == b) return false;
        for (int i = 0; i < edge_count_; i++) {
            if ((edges_[i].a == a && edges_[i].b == b) ||
                (edges_[i].a == b && edges_[i].b == a)) {
                return false;
            }
        }
        if (edge_count_ >= MAX_EDGES) return false;
        edges_[edge_count_].a = a;
        edges_[edge_count_].b = b;
        edge_count_++;
        return true;
    }

    // Rebuild the union-find from the observed edge list, dropping edges whose
    // endpoint is no longer tracked. The edge list is the source of truth, so
    // this also erases union-find state left over by a recycled slot.
    void rebuildClusters() {
        int w = 0;
        for (int i = 0; i < edge_count_; i++) {
            if (nodes_.findByHash(edges_[i].a) >= 0 &&
                nodes_.findByHash(edges_[i].b) >= 0) {
                edges_[w++] = edges_[i];
            }
        }
        edge_count_ = w;

        clusters_.init(MAX_NODES);
        for (int i = 0; i < edge_count_; i++) {
            int a = nodes_.findByHash(edges_[i].a);
            int b = nodes_.findByHash(edges_[i].b);
            if (a >= 0 && b >= 0) clusters_.unionSets(a, b);
        }
    }

public:
    StratoRelayMesh(float recencyW = 3.0f, float signalW = 2.0f, float stabilityW = 1.0f)
        : edge_count_(0), head_count_(0),
          recency_w_(recencyW), signal_w_(signalW), stability_w_(stabilityW) {
        clear();
    }

    void clear() {
        nodes_.clear();
        clusters_.init(MAX_NODES);
        memset(adverts_, 0, sizeof(adverts_));
        memset(heads_, 0, sizeof(heads_));
        edge_count_ = 0;
        head_count_ = 0;
    }

    int nodeCount() const { return nodes_.getCount(); }
    int clusterCount() const { return head_count_; }
    int edgeCount() const { return edge_count_; }
    const HeadInfo& getHead(int idx) const { return heads_[idx]; }

    // --- section 2.3 / 4.1: observation ------------------------------------
    // An advert was heard from `hash` with the given SNR at RTC time `ts`.
    int observeAdvert(uint8_t hash, int8_t snr, uint32_t timestamp) {
        int prev = nodes_.findByHash(hash);
        int count_before = nodes_.getCount();
        int slot = nodes_.insertOrUpdate(hash, snr, timestamp);
        if (slot < 0) return UNKNOWN;
        if (prev < 0) {
            adverts_[slot] = 0;
            if (nodes_.getCount() == count_before) {
                // The table was full: LRU eviction handed this hash a recycled
                // slot. Survivors may still point at that slot in the
                // union-find, so rebuild the clusters from the edge list (the
                // evicted node's edges drop out with their dead endpoint), then
                // re-elect so the heads table matches the new clustering and
                // there is no window with stale head identities.
                rebuildClusters();
                electHeads(timestamp);
            }
        }
        if (adverts_[slot] < ADVERT_CAP) adverts_[slot]++;
        return slot;
    }

    // `sender`'s flood was forwarded by `forwarder`, i.e. the two can hear each
    // other (section 4.1). Section 4.3 wants *bidirectional* evidence before
    // clustering, so callers record both directions; this method records one
    // direction and unions immediately. Returns true when the observation added
    // a new edge (false for a repeat or an unknown endpoint, or once
    // MAX_EDGES is reached - then the edge is dropped, which can only under-
    // cluster, never over-cluster).
    bool observeFloodForwardedBy(uint8_t sender, uint8_t forwarder) {
        if (sender == forwarder) return false;
        int a = nodes_.findByHash(sender);
        int b = nodes_.findByHash(forwarder);
        if (a < 0 || b < 0) return false;  // unknown nodes cannot cluster
        bool fresh = recordEdge(sender, forwarder);
        clusters_.unionSets(a, b);
        return fresh;
    }

    // --- section 5.3 / 6.2: periodic rebuild -------------------------------
    // Age stale nodes, rebuild union-find from the surviving edge list, then
    // re-elect cluster heads. Called from StratoRelayMesh::rebuild() in
    // firmware every STRATO_REBUILD_INTERVAL (default 5 min).
    void rebuild(uint32_t now, uint32_t stale_timeout) {
        nodes_.ageNodes(now, stale_timeout);
        rebuildClusters();
        electHeads(now);
    }

    // --- section 6.1: cluster-head election ---------------------------------
    // Within each cluster the highest-scoring live node becomes head. Ties are
    // broken by lowest identity hash so results are order-independent. Clusters
    // beyond MAX_CLUSTERS are not represented (section 9.2 budget: 32).
    void electHeads(uint32_t now) {
        int best_slot[MAX_CLUSTERS];
        float best_score[MAX_CLUSTERS];
        head_count_ = 0;

        for (int i = 0; i < MAX_NODES; i++) {
            if (!nodes_.get(i).active) continue;
            int root = clusters_.find(i);
            int c = -1;
            for (int j = 0; j < head_count_; j++) {
                if (heads_[j].cluster_root == root) {
                    c = j;
                    break;
                }
            }
            if (c < 0) {
                if (head_count_ >= MAX_CLUSTERS) continue;
                c = head_count_++;
                heads_[c].cluster_root = root;
                best_slot[c] = UNKNOWN;
                best_score[c] = 0.0f;
            }

            float score = scoreOf(i, now);
            if (best_slot[c] == UNKNOWN || score > best_score[c] ||
                (score == best_score[c] &&
                 nodes_.get(i).hash < nodes_.get(best_slot[c]).hash)) {
                best_slot[c] = i;
                best_score[c] = score;
            }
        }

        for (int c = 0; c < head_count_; c++) {
            heads_[c].hash = (best_slot[c] >= 0)
                                 ? nodes_.get(best_slot[c]).hash
                                 : (uint8_t)0;
        }
    }

    // --- section 7: decisions ----------------------------------------------
    // Union-find root of the cluster containing `hash`, UNKNOWN if not tracked.
    int clusterOf(uint8_t hash) {
        int slot = nodes_.findByHash(hash);
        if (slot < 0) return UNKNOWN;
        return clusters_.find(slot);
    }

    bool isClusterHead(uint8_t hash) {
        if (nodes_.findByHash(hash) < 0) return false;
        for (int c = 0; c < head_count_; c++) {
            if (heads_[c].hash == hash) return true;
        }
        return false;
    }

    // true = DROP the flood (section 7 step 6).
    bool filterRecvFloodPacket(uint8_t sender) {
        if (nodes_.findByHash(sender) < 0) return false;  // section 7 step 2
        return !isClusterHead(sender);
    }

    // true = retransmit/bridge the packet (section 7 step 5).
    bool allowPacketForward(uint8_t sender) { return isClusterHead(sender); }

    // Heads of every cluster except the origin's own. Returns the number
    // written to `out` (section 7 bridging + the "no self-bridge" guarantee).
    //
    // Only a cluster head's packet is ever bridged: a non-head's flood was
    // dropped by filterRecvFloodPacket(), so it has no bridge targets, and an
    // untracked sender is not a head either.
    //
    // The sender is by definition the head of its own cluster, so skipping the
    // origin cluster is exactly the section-11 "no self-bridge" rule: a packet
    // from Cluster A is never handed back to Cluster A.
    int bridgeTargets(uint8_t sender, uint8_t* out, int max_out) {
        if (out == nullptr || max_out <= 0) return 0;
        if (!isClusterHead(sender)) return 0;
        int origin_cluster = clusterOf(sender);
        int n = 0;
        for (int c = 0; c < head_count_ && n < max_out; c++) {
            if (heads_[c].cluster_root == origin_cluster) continue;
            out[n++] = heads_[c].hash;
        }
        return n;
    }
};
