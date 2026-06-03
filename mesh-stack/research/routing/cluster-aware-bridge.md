# Cluster-Aware Bridge: Algorithm Analysis + MeshCore Integration

**Date**: 2026-06-03
**Status**: Research complete, implementation pending
**Related**: ADR-013, `mesh-stack/research/routing/meshcore-study.md`

## TL;DR

A high-altitude balloon running MeshCore can prevent flood storms by subclassing `mesh::Mesh` and overriding four virtual methods. Clustering uses union-find on observed flood paths (~2.3 KB for 256 nodes). Membership testing uses per-cluster static bloom filters (~4 KB for 32 clusters). Total: ~6.5 KB static DRAM. Ground nodes remain completely stock.

## 1. The Problem

At 12 km altitude, a MeshCore repeater sees ground nodes across an ~800 km diameter. In a flood-routing mesh:

1. The balloon retransmits every flood packet it receives
2. Every ground node that hears the balloon processes the retransmit
3. Ground nodes in Cluster A (Berlin) and Cluster B (Munich) cannot hear each other directly
4. Without the balloon, their flood traffic stays local — no problem
5. With a dumb balloon repeater, Berlin's flood becomes Munich's flood and vice versa
6. Channel saturation follows

The balloon must act as a **bridge**, not a **repeater**.

## 2. MeshCore Virtual Hook Methods

MeshCore's `Mesh` class (`src/Mesh.h`) provides these overridable methods:

### 2.1 `filterRecvFloodPacket(Packet* packet)` — `Mesh.h:46`

```cpp
virtual bool filterRecvFloodPacket(Packet* packet) { return false; }
```

Returns `true` to drop a flood packet before processing. Default: allow all.

**Our use**: Return `true` for packets from non-cluster-head nodes. The cluster's local flood already handles delivery within the cluster — the balloon only needs to bridge between clusters.

### 2.2 `allowPacketForward(const Packet* packet)` — `Mesh.h:53`

```cpp
virtual bool allowPacketForward(const Packet* packet) { return false; }
```

Controls whether a packet is retransmitted. Default: `false` (transport not enabled). Repeater firmware overrides to `true`.

**Our use**: Return `true` only for inter-cluster bridging. Return `false` for intra-cluster packets (ground flood handles those).

### 2.3 `onAdvertRecv(...)` — `Mesh.h:80`

```cpp
virtual void onAdvertRecv(Packet* packet, const Identity& id, uint32_t timestamp,
                          const uint8_t* app_data, size_t app_data_len) { }
```

Called when a valid advertisement is received. Advert payload contains:
- `pub_key` (32 bytes) — node identity
- `timestamp` (4 bytes) — sender's RTC time
- `signature` (64 bytes) — Ed25519 signature
- `app_data` (up to 32 bytes) — optional: node type, name, GPS lat/lon

**Our use**: Extract sender identity hash, SNR from packet, and path forwarders. Populate NodeTable + UnionFind.

### 2.4 `routeRecvPacket(Packet* packet)` — `Mesh.cpp:routeRecvPacket()`

```cpp
DispatcherAction routeRecvPacket(Packet* packet);
```

Decides retransmit action for flood packets. Default: append own hash to path, schedule retransmit with priority = hop count.

**Our use**: Override to send via `sendZeroHop()` targeting specific cluster heads, or suppress retransmit for same-cluster packets.

## 3. Advert Data Format

MeshCore adverts carry optional application data parsed by `AdvertDataHelpers.h`:

```cpp
#define ADV_TYPE_NONE         0
#define ADV_TYPE_CHAT         1    // companion radio / chat node
#define ADV_TYPE_REPEATER     2    // repeater node
#define ADV_TYPE_ROOM         3    // chat room server
#define ADV_TYPE_SENSOR       4    // sensor node

#define ADV_LATLON_MASK       0x10  // has GPS coordinates
#define ADV_NAME_MASK         0x80  // has name string
```

**Key fields available for clustering**:
- Node type (repeater vs companion vs sensor)
- Node name (e.g., "STRATO-01", "Berlin-Repeater-3")
- GPS lat/lon (if `ADV_LATLON_MASK` set, only companion radios with GPS)
- `feat1`, `feat2` (16-bit unsigned, currently unused "FUTURE" fields)

**For balloon telemetry**: We use `feat1` for altitude/10 (range 0–6553 km, resolution 10 m) and `feat2` for battery_mV/50 (range 0–3.275 V, resolution 50 mV).

## 4. RF Topology Clustering via Flood Paths

### 4.1 What the Balloon Observes

MeshCore flood packets carry a `path[]` array. Each relay appends its 1-byte identity hash:

```
Node A sends advert:  path = []             (zero-hop to balloon)
Node B forwards A:    path = [B_hash]        (B can hear A)
Node C forwards A:    path = [C_hash]        (C can hear A)
Node B forwards C:    path = [B_hash]        (B can hear C)
```

From these observations, the balloon infers:
- A, B, C can all hear each other (bidirectional forwarding)
- They form one RF cluster

### 4.2 Union-Find Algorithm

Union-find (disjoint sets) builds clusters incrementally from edge observations:

```
struct NodeRecord {
    uint8_t hash;        // identity hash (pub_key prefix byte)
    uint8_t uf_parent;   // union-find parent index
    uint8_t uf_rank;     // union-find rank
    int8_t  last_snr;    // SNR × 4 from last heard advert
    uint32_t last_heard; // our RTC timestamp
    bool is_cluster_head;
};

find(x):
    while (nodes[x].uf_parent != x):
        nodes[x].uf_parent = nodes[nodes[x].uf_parent].uf_parent  // path compression
        x = nodes[x].uf_parent
    return x

union(a, b):
    ra = find(a), rb = find(b)
    if ra == rb: return  // already same cluster
    if nodes[ra].uf_rank < nodes[rb].uf_rank: swap(ra, rb)
    nodes[rb].uf_parent = ra
    if nodes[ra].uf_rank == nodes[rb].uf_rank: nodes[ra].uf_rank++
```

**Complexity**: O(α(N)) per operation ≈ O(1). α is the inverse Ackermann function, never exceeds 4 for any practical N.

**Memory**: N × (1 + 1 + 1 + 1 + 4 + 1) = N × 9 bytes. For N=256: 2.3 KB.

### 4.3 Bidirectional Edge Detection

Observing A's advert forwarded by B means B can hear A. But does A hear B? We need **bidirectional** evidence to avoid false clustering of distant nodes.

**Method**: Only call `union(A, B)` when BOTH:
1. A's advert arrives forwarded by B (path contains B)
2. B's advert arrives forwarded by A (path contains A)

This ensures we only cluster nodes that are genuinely in mutual RF range.

**Relaxation**: If `STRATO_BIDIRECTIONAL_ONLY` is set to 0, we cluster on unidirectional evidence. This creates larger clusters (more aggressive) but risks merging distant nodes.

## 5. Bloom Filter Design

### 5.1 Why No External Library

Evaluated libraries:
- **ArashPartow/bloom** (`https://github.com/ArashPartow/bloom`): Header-only C++, uses `std::vector` for bit table and salt. Dynamic allocation violates MeshCore coding principles.
- **jvirkki/libbloom** (`https://github.com/jvirkki/libbloom`): C library, uses `malloc/calloc`. Designed for server-side (millions of elements).
- **aappleby/smhasher** (`https://github.com/aappleby/smhasher`): Only provides MurmurHash3. Would need custom bit array anyway.

### 5.2 Custom StaticBloomFilter

```cpp
template<int MAX_ELEMENTS, int FP_RATE_PER_MILLION = 10000>
class StaticBloomFilter {
    static constexpr int BIT_COUNT = MAX_ELEMENTS * 10;  // ~10 bits/element for 1% FP
    static constexpr int BYTE_COUNT = (BIT_COUNT + 7) / 8;
    static constexpr int NUM_HASHES = 7;

    uint8_t bits[BYTE_COUNT];
    int count;

    uint32_t fnv1a(const uint8_t* data, size_t len, uint32_t seed) {
        uint32_t h = seed;
        for (size_t i = 0; i < len; i++) {
            h ^= data[i];
            h *= 16777619;
        }
        return h;
    }

public:
    void clear() { memset(bits, 0, sizeof(bits)); count = 0; }

    void insert(uint8_t node_hash) {
        for (int i = 0; i < NUM_HASHES; i++) {
            uint32_t h = fnv1a(&node_hash, 1, 0x811C9DC5 + i * 0x01000193);
            int bit = h % BIT_COUNT;
            bits[bit / 8] |= (1 << (bit % 8));
        }
        count++;
    }

    bool contains(uint8_t node_hash) const {
        for (int i = 0; i < NUM_HASHES; i++) {
            uint32_t h = fnv1a(&node_hash, 1, 0x811C9DC5 + i * 0x01000193);
            int bit = h % BIT_COUNT;
            if (!(bits[bit / 8] & (1 << (bit % 8)))) return false;
        }
        return true;
    }

    int size() const { return count; }
};
```

**Sizing for our use case**:
- 100 elements per cluster at 1% FP: 125 bytes per filter
- 32 clusters: 4,000 bytes total
- 1% FP means the balloon over-filters ~1 in 100 packets from non-cluster nodes
- Over-filtering is safe: ground flood still delivers the dropped packet locally

### 5.3 Filter Aging and Rebuild

Bloom filters are append-only — they saturate over time. Our design rebuilds all filters every `STRATO_REBUILD_INTERVAL` (default 5 minutes):

1. Age out stale nodes from NodeTable (not heard for `STRATO_STALE_TIMEOUT`)
2. Rebuild union-find with remaining nodes
3. Clear all bloom filters
4. Re-insert living nodes into their cluster's bloom filter
5. Re-elect cluster heads

This prevents saturation and adapts to changing topology as the balloon drifts.

## 6. Cluster Head Election

### 6.1 Scoring Formula

```
score = recency_weight / (now - last_heard + 1)
      + signal_weight × (snr + 20)       // normalize: -20 to +20 → 0 to 40
      + stability_weight × min(total_adverts_seen, 100) / 100
```

Default weights: `recency=3.0`, `signal=2.0`, `stability=1.0`

### 6.2 Election Trigger

Re-election happens at every `REBUILD_INTERVAL`. If the current cluster head has gone stale (not heard for `STALE_TIMEOUT / 2`), immediate re-election for that cluster.

### 6.3 Cluster Head Data

```cpp
struct ClusterHead {
    uint8_t node_hash;
    int8_t  best_snr;
    uint32_t last_heard;
    uint8_t member_count;
};
// 7 bytes × 32 clusters = 224 bytes
```

## 7. Packet Filtering Logic

```
INCOMING FLOOD PACKET from sender S:
  1. Find S in NodeTable
  2. If S not found (unknown node):
     → ALLOW (conservative: don't filter unknowns)
  3. Find S's cluster_id via union-find
  4. Look up cluster head for that cluster
  5. If S == cluster head:
     → filterRecvFloodPacket() returns false (ALLOW)
     → allowPacketForward() returns true (BRIDGE to other clusters)
  6. If S != cluster head:
     → filterRecvFloodPacket() returns true (DROP)
     → Ground flood already delivers within cluster

BRIDGING PACKET from Cluster A to Cluster B:
  1. Create packet copy with cleaned path (remove balloon's hash)
  2. sendZeroHop(copy)
  3. All ground nodes hear it (balloon is at altitude)
  4. Nodes in Cluster B process it (new information)
  5. Nodes in Cluster A dedup it (already have via local flood)
```

## 8. Balloon Telemetry over MeshCore

### 8.1 Advert-Based Tracking

The balloon broadcasts adverts every 5 minutes with GPS position:

```cpp
AdvertDataBuilder builder(ADV_TYPE_REPEATER, "STRATO-01", gps_lat, gps_lon);
builder.setFeat1(altitude_m / 10);       // 16-bit altitude
builder.setFeat2(battery_mv / 50);       // 16-bit battery
```

Any MeshCore user in range sees "STRATO-01" on their map with live coordinates. Range: ~700+ km at altitude on Sub-GHz.

### 8.2 Chat-Based Telemetry

Every 15 minutes, the balloon sends a telemetry string via encrypted chat:

```
"ALT:12345 BAT:3200 SOL:180 TMP:-45 GPS:52.5N,13.4E SAT:8 UP:12h30m"
```

~60 bytes, fits in one MeshCore packet (184-byte max payload).

### 8.3 On-Demand Queries

Ground users can send `PAYLOAD_TYPE_REQ` to the balloon requesting detailed telemetry. The balloon responds with a binary payload:

```
altitude(4) + voltage(2) + solar_ma(2) + temp(2) +
gps_lat(4) + gps_lon(4) + satellites(1) + uptime(4) = 23 bytes
```

## 9. Integration with Existing Tracker

### 9.1 Single MCU Architecture

Both tracker and MeshCore run on the same ESP32-C3:

```
┌─────────────────────────────────────────────────┐
│  FreeRTOS                                        │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ Tracker Task │  │ Mesh Task                │ │
│  │ GPS + TX     │  │ StratoRelayMesh.loop()   │ │
│  │ telemetry    │  │ + cluster building        │ │
│  └──────┬───────┘  └────────────┬─────────────┘ │
│         │                       │                │
│         └───────┬───────────────┘                │
│                 │ mutex                          │
│         ┌───────┴───────┐                        │
│         │ RadioLib HAL  │                        │
│         │ (LR2021 SPI)  │                        │
│         └───────────────┘                        │
└─────────────────────────────────────────────────┘
```

### 9.2 RAM Budget (ESP32-C3, 400 KB total, 321 KB DRAM)

| Component | DRAM (BSS/static) | Notes |
|---|---|---|
| ESP-IDF system | ~80 KB | FreeRTOS, heap, stack |
| Tracker (existing) | ~4.4 KB | Current `idf.py size` measurement |
| MeshCore core | ~15 KB | Packet pool, dedup, identity |
| rweather/Crypto | ~8 KB | Ed25519, AES-128, SHA-256 tables |
| StratoRelay layer | ~6.5 KB | NodeTable + Bloom + ClusterHeads |
| **Total static** | **~114 KB** | |
| **Free heap** | **~207 KB** | For Wirehair encode/decode (temporary) |

Flash: tracker uses ~188 KB, mesh adds ~100 KB = 288 KB of 4 MB. Abundant.

## 10. Measurement Data Needed Before Tuning

Before Phase 2b implementation, we need real-world data from Phase 2a (basic repeater flight):

| Measurement | How | Why |
|---|---|---|
| Unique node count | Log identity hashes from adverts | Set `MAX_NODES` |
| Advert frequency | Timestamp deltas between same-node adverts | Set `REBUILD_INTERVAL` |
| Flood path depth | Parse `path[]` from flood packets | Validate union-find approach |
| SNR distribution | Log SNR per advert | Tune cluster head scoring |
| Packet collision rate | Dedup table stats | Determine filtering aggressiveness |
| Geographic spread | GPS from companion radio adverts | Validate cluster geography |

## 11. Unit Test Checklist

- [ ] UnionFind: basic union/find (two nodes become same cluster)
- [ ] UnionFind: path compression (deep chains compress)
- [ ] UnionFind: separate components (unrelated nodes stay separate)
- [ ] UnionFind: rank balancing (prevents tall trees)
- [ ] NodeTable: insert + find by hash
- [ ] NodeTable: aging (stale nodes removed after timeout)
- [ ] NodeTable: overflow (LRU eviction when MAX_NODES exceeded)
- [ ] NodeTable: update existing node (new SNR replaces old)
- [ ] StaticBloomFilter: insert + contains (members found)
- [ ] StaticBloomFilter: non-members rejected
- [ ] StaticBloomFilter: FP rate measurement (target < 1%)
- [ ] StaticBloomFilter: clear + rebuild (clean state after rebuild)
- [ ] ClusterHeadElector: basic election (highest score wins)
- [ ] ClusterHeadElector: stale fallback (head ages out, next-best elected)
- [ ] ClusterHeadElector: score ordering (recency > signal > stability)
- [ ] StratoRelayMesh: filter from cluster head (allowed)
- [ ] StratoRelayMesh: filter from non-head (dropped)
- [ ] StratoRelayMesh: bridge between clusters (forwarded)
- [ ] StratoRelayMesh: no self-bridge (packet from Cluster A not sent back to A)
- [ ] StratoRelayMesh: unknown node allowed (conservative default)
