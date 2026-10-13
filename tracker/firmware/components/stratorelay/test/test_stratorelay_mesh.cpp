// Host unit tests for the StratoRelayMesh decision core.
//
// Covers the five StratoRelayMesh items of section 11 in
// mesh-stack/research/routing/cluster-aware-bridge.md
//   - filter from cluster head (allowed)
//   - filter from non-head (dropped)
//   - bridge between clusters (forwarded)
//   - no self-bridge (packet from Cluster A not sent back to A)
//   - unknown node allowed (conservative default)
// expanded into 8 focused cases (the bridging and dropping rules each get a
// positive and a negative case).
//
// Build: g++ -std=c++17 -Wall -Wextra -Werror -I.. test_stratorelay_mesh.cpp
// (no .cpp sources: StratoRelayMesh is header-only and radio-free).

#include <cstdio>
#include <cstdint>

#include "StratoRelayMesh.h"

static int tests_passed = 0;
static int tests_failed = 0;

#define ASSERT(cond, msg) do { \
    if (!(cond)) { printf("FAIL: %s (line %d)\n", msg, __LINE__); tests_failed++; return; } \
} while(0)

#define PASS(name) do { printf("  PASS: %s\n", name); tests_passed++; } while(0)

static constexpr uint32_t T0 = 100000;  // RTC time used by every scenario

using Mesh = StratoRelayMesh<64, 8, 256>;

// FNV-style, collision-free membership check for the small target lists below.
static bool contains(const uint8_t* arr, int n, uint8_t v) {
    for (int i = 0; i < n; i++) {
        if (arr[i] == v) return true;
    }
    return false;
}

// Build one RF cluster: every member is joined to `hub` by bidirectional flood
// path observations (section 4.3) and `hub` carries the strongest signal, so
// it must win the section-6.1 election.
static void buildCluster(Mesh& m, const uint8_t* members, int n, uint8_t hub) {
    for (int i = 0; i < n; i++) {
        int8_t snr = (members[i] == hub) ? 12 : 2;
        m.observeAdvert(members[i], snr, T0);
    }
    for (int i = 0; i < n; i++) {
        if (members[i] == hub) continue;
        m.observeFloodForwardedBy(members[i], hub);  // hub heard the member
        m.observeFloodForwardedBy(hub, members[i]);  // member heard the hub
    }
    m.electHeads(T0);
}

// Cluster A: 0x10, 0x20 (head), 0x30
static const uint8_t CLUSTER_A[] = {0x10, 0x20, 0x30};
// Cluster B: 0x40, 0x50 (head), 0x60
static const uint8_t CLUSTER_B[] = {0x40, 0x50, 0x60};
// Cluster C: 0x70, 0x80 (head), 0x90
static const uint8_t CLUSTER_C[] = {0x70, 0x80, 0x90};

static const uint8_t HEAD_A = 0x20;
static const uint8_t HEAD_B = 0x50;
static const uint8_t HEAD_C = 0x80;
static const uint8_t UNKNOWN_NODE = 0xEE;

// 1. section 11: "filter from cluster head (allowed)"
static void test_filter_allows_cluster_head() {
    Mesh m;
    buildCluster(m, CLUSTER_A, 3, HEAD_A);

    ASSERT(m.nodeCount() == 3, "cluster A should track 3 nodes");
    ASSERT(m.clusterCount() == 1, "cluster A should form exactly 1 cluster");
    ASSERT(m.isClusterHead(HEAD_A), "0x20 has the best score and should be head");
    ASSERT(!m.isClusterHead(0x10), "0x10 is not the head");
    ASSERT(m.clusterOf(0x10) == m.clusterOf(HEAD_A), "0x10 must be in the head's cluster");
    ASSERT(!m.filterRecvFloodPacket(HEAD_A), "flood from the cluster head must be ALLOWED");
    PASS("filter from cluster head (allowed)");
}

// 2. section 11: "filter from non-head (dropped)"
static void test_filter_drops_non_head() {
    Mesh m;
    buildCluster(m, CLUSTER_A, 3, HEAD_A);

    // both non-heads are known and clustered with the head, so the drop is
    // because they are not the head, not because they are unknown
    ASSERT(m.clusterOf(0x10) != Mesh::UNKNOWN, "0x10 must be a known node");
    ASSERT(m.clusterOf(0x10) == m.clusterOf(HEAD_A), "0x10 is in the head's cluster");
    ASSERT(m.filterRecvFloodPacket(0x10), "flood from a non-head must be DROPPED");
    ASSERT(m.filterRecvFloodPacket(0x30), "flood from the other non-head must be DROPPED");
    ASSERT(!m.filterRecvFloodPacket(HEAD_A), "head flood stays allowed in the same cluster");
    PASS("filter from non-head (dropped)");
}

// 3. section 11: "unknown node allowed (conservative default)"
static void test_unknown_node_allowed() {
    Mesh m;
    buildCluster(m, CLUSTER_A, 3, HEAD_A);

    ASSERT(m.clusterOf(UNKNOWN_NODE) == Mesh::UNKNOWN, "untracked node has no cluster");
    ASSERT(!m.isClusterHead(UNKNOWN_NODE), "untracked node is not a head");
    ASSERT(!m.filterRecvFloodPacket(UNKNOWN_NODE), "unknown node must be ALLOWED (conservative)");
    ASSERT(m.nodeCount() == 3, "the decision must not insert the unknown node");
    PASS("unknown node allowed");
}

// 4. section 11: "bridge between clusters (forwarded)" - the head is forwardable
static void test_forward_enabled_for_cluster_head() {
    Mesh m;
    buildCluster(m, CLUSTER_A, 3, HEAD_A);

    ASSERT(m.allowPacketForward(HEAD_A), "cluster head packet must be forwardable (bridged)");
    ASSERT(!m.allowPacketForward(0x10), "non-head packet must not be forwardable");
    ASSERT(!m.filterRecvFloodPacket(HEAD_A), "head packet is both allowed and forwardable");
    PASS("forward enabled for cluster head");
}

// 5. section 11: "bridge between clusters (forwarded)" - the target is the peer head
static void test_bridge_between_clusters_forwarded() {
    Mesh m;
    buildCluster(m, CLUSTER_A, 3, HEAD_A);
    buildCluster(m, CLUSTER_B, 3, HEAD_B);

    ASSERT(m.clusterCount() == 2, "A and B must be two separate clusters");
    ASSERT(m.clusterOf(HEAD_A) != m.clusterOf(HEAD_B), "A and B must not share a cluster");

    uint8_t targets[8];
    int n = m.bridgeTargets(HEAD_A, targets, 8);
    ASSERT(n == 1, "bridging out of A should target exactly one cluster");
    ASSERT(targets[0] == HEAD_B, "the bridge target must be B's cluster head");
    ASSERT(m.clusterOf(targets[0]) == m.clusterOf(HEAD_B), "target belongs to cluster B");
    PASS("bridge between clusters (forwarded)");
}

// 6. section 11: "no self-bridge (packet from Cluster A not sent back to A)"
static void test_no_self_bridge_to_origin_cluster() {
    Mesh m;
    buildCluster(m, CLUSTER_A, 3, HEAD_A);
    buildCluster(m, CLUSTER_B, 3, HEAD_B);

    uint8_t targets[8];
    int n = m.bridgeTargets(HEAD_A, targets, 8);
    ASSERT(n > 0, "a head with a peer cluster must produce at least one target");

    int origin = m.clusterOf(HEAD_A);
    for (int i = 0; i < n; i++) {
        ASSERT(targets[i] != HEAD_A, "origin head must never be its own bridge target");
        ASSERT(m.clusterOf(targets[i]) != origin, "bridge target must not be in the origin cluster");
    }
    ASSERT(!contains(targets, n, (uint8_t)0x10), "A's members are not bridge targets");
    ASSERT(!contains(targets, n, (uint8_t)0x30), "A's members are not bridge targets");
    PASS("no self-bridge to origin cluster");
}

// 7. section 11: "no self-bridge" with more than two clusters
static void test_bridge_targets_exclude_origin() {
    Mesh m;
    buildCluster(m, CLUSTER_A, 3, HEAD_A);
    buildCluster(m, CLUSTER_B, 3, HEAD_B);
    buildCluster(m, CLUSTER_C, 3, HEAD_C);
    ASSERT(m.clusterCount() == 3, "three RF clusters expected");

    uint8_t targets[8];
    int n = m.bridgeTargets(HEAD_A, targets, 8);
    ASSERT(n == 2, "A should bridge to exactly the two other clusters");
    ASSERT(contains(targets, n, HEAD_B), "B's head must be a target");
    ASSERT(contains(targets, n, HEAD_C), "C's head must be a target");
    ASSERT(!contains(targets, n, HEAD_A), "A's own head must never be a target");

    int origin = m.clusterOf(HEAD_A);
    for (int i = 0; i < n; i++) {
        ASSERT(m.clusterOf(targets[i]) != origin, "no target may sit in the origin cluster");
    }
    PASS("bridge targets exclude origin cluster");
}

// 8. section 11: "filter from non-head (dropped)" - bridging corollary
static void test_non_head_not_bridged() {
    Mesh m;
    buildCluster(m, CLUSTER_A, 3, HEAD_A);
    buildCluster(m, CLUSTER_B, 3, HEAD_B);

    uint8_t targets[8];
    ASSERT(!m.allowPacketForward(0x10), "a non-head is not forwardable");
    ASSERT(m.bridgeTargets(0x10, targets, 8) == 0, "a dropped non-head packet has no bridge targets");
    ASSERT(m.bridgeTargets(UNKNOWN_NODE, targets, 8) == 0, "an untracked sender has no bridge targets");
    ASSERT(m.bridgeTargets(HEAD_A, targets, 8) == 1, "the head still bridges in the same state");
    PASS("non-head not bridged");
}

// Regression guard for the decision core added with this card: when NodeTable
// evicts the oldest node (LRU overflow) its slot is recycled, and the new
// owner must not inherit the evicted node's union-find membership.
static void test_recycled_slot_keeps_own_cluster() {
    // MAX_NODES is deliberately tiny to force eviction; MAX_CLUSTERS must be
    // at least 3 so the three post-eviction singletons are all representable
    // (with a smaller cap the count assertion below would only measure the
    // cluster cap, not the recycling behaviour).
    StratoRelayMesh<3, 3, 8> small;

    small.observeAdvert(0x11, 12, T0 + 50);   // cluster head candidate
    small.observeAdvert(0x22, 5, T0);         // oldest -> evicted first
    small.observeAdvert(0x33, 5, T0 + 100);
    small.observeFloodForwardedBy(0x22, 0x11);
    small.observeFloodForwardedBy(0x11, 0x22);
    small.electHeads(T0 + 100);

    ASSERT(small.nodeCount() == 3, "table should be full");
    ASSERT(small.clusterOf(0x11) == small.clusterOf(0x22), "0x11 and 0x22 share a cluster");
    ASSERT(small.clusterCount() == 2, "0x11/0x22 plus 0x33 make two clusters");

    // Table full: 0x44 evicts 0x22 (oldest) and reuses 0x22's slot. 0x11 still
    // points at that slot in the union-find, so without the rebuild-on-eviction
    // path 0x44 would be welded into 0x11's cluster.
    int slot = small.observeAdvert(0x44, 7, T0 + 200);
    ASSERT(slot >= 0, "eviction must free a slot");
    ASSERT(small.nodeCount() == 3, "table stays full after eviction");
    ASSERT(small.clusterOf(0x22) == Mesh::UNKNOWN, "evicted node is no longer tracked");
    ASSERT(small.clusterOf(0x44) != small.clusterOf(0x11),
           "recycled slot must not inherit the evicted node's cluster");
    ASSERT(small.clusterOf(0x44) != Mesh::UNKNOWN, "the new node is its own cluster");
    // Heads are re-elected as soon as the topology changes, so the new node is
    // immediately head of its own singleton cluster (no stale-head window).
    ASSERT(small.clusterCount() == 3, "eviction splits the pair into singletons");
    ASSERT(small.isClusterHead(0x44), "the new node heads its own cluster");
    PASS("recycled slot keeps its own cluster");
}

int main() {
    printf("=== StratoRelayMesh Tests ===\n\n");

    printf("Section 11 checklist:\n");
    test_filter_allows_cluster_head();
    test_filter_drops_non_head();
    test_unknown_node_allowed();
    test_forward_enabled_for_cluster_head();
    test_bridge_between_clusters_forwarded();
    test_no_self_bridge_to_origin_cluster();
    test_bridge_targets_exclude_origin();
    test_non_head_not_bridged();
    int s11_passed = tests_passed;
    int s11_failed = tests_failed;

    printf("\nRegression (slot recycling in the decision core):\n");
    test_recycled_slot_keeps_own_cluster();

    int total = tests_passed + tests_failed;
    // The card's contract is the 8 section-11 cases; the regression case is
    // reported separately so both counts stay verifiable.
    printf("\n=== StratoRelayMesh Tests: %d/%d passed (section 11: %d/%d) ===\n",
           tests_passed, total, s11_passed, s11_passed + s11_failed);
    return tests_failed > 0 ? 1 : 0;
}
