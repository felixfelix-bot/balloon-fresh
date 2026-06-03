# ADR 013: Cluster-Aware Stratorelay for MeshCore

## Status

Proposed

## Context

A balloon at 12 km altitude sees thousands of ground MeshCore nodes simultaneously across an ~800 km diameter footprint. Running the standard MeshCore repeater firmware would cause:

1. **Packet storms**: Every flood packet from every ground node gets rebroadcast to every other ground node via the balloon, multiplying traffic by the number of visible clusters.
2. **Channel saturation**: LoRa SF8/BW62.5 at 869.618 MHz has limited airtime. A dumb repeater seeing hundreds of nodes would exceed the 10% EU duty cycle.
3. **Hidden node problem**: Ground nodes in different cities cannot hear each other but can all hear the balloon, causing simultaneous transmissions that corrupt data.

The MeshCore community would benefit from stratospheric coverage (relay range from ~10 km ground-to-ground to ~700+ km via balloon) without their local networks degrading.

MeshCore's `Mesh` base class provides virtual hook methods that allow subclassing without modifying the core framework:
- `filterRecvFloodPacket()` — drop flood packets before processing
- `allowPacketForward()` — control which packets get retransmitted
- `onAdvertRecv()` — intercept node advertisements
- `routeRecvPacket()` — override retransmission behavior

Ground nodes must remain completely stock (standard MeshCore companion or repeater firmware). All intelligence lives on the balloon.

A secondary benefit: the balloon can broadcast its GPS position and telemetry via standard MeshCore adverts and chat messages, providing a backup tracking path independent of internet, WSPR, or LoRaWAN.

## Decision

Implement a `StratoRelayMesh` class extending MeshCore's `mesh::Mesh` with cluster-aware filtering:

1. **Passive cluster discovery**: Listen to ground node adverts and flood paths. Build clusters using union-find on observed forwarding relationships (if node A forwards node B's advert, they're in the same RF cluster).

2. **Cluster head election**: For each detected cluster, elect one node as the communication gateway based on SNR quality, advert recency, and stability.

3. **Cluster-aware filtering**: Only accept and re-bridge flood packets from cluster heads. Drop packets from non-head nodes (they're already handled by local ground flood).

4. **Per-cluster bloom filters**: Use static bloom filters for scalable membership testing (~4 KB for 32 clusters of 100 nodes each, 1% FP rate). Custom implementation (no external library) to avoid dynamic allocation.

5. **Zero-hop bridging**: Forward inter-cluster messages via `sendZeroHop()` — standard MeshCore packets that ground nodes process normally.

6. **Balloon telemetry**: Broadcast GPS position in adverts, send telemetry via chat messages, respond to on-demand queries.

### Memory Architecture

```
NodeTable:       256 nodes × 9 bytes = 2.3 KB (static array)
UnionFind:       embedded in NodeTable (parent + rank per node)
Bloom filters:   32 clusters × 125 bytes = 4.0 KB (static)
Cluster heads:   32 × 7 bytes = 224 bytes (static)
Total:           ~6.5 KB static DRAM
```

### MeshCore Extension Points

| Virtual Method | Override Purpose |
|---|---|
| `onAdvertRecv()` | Populate NodeTable + UnionFind from advert paths |
| `filterRecvFloodPacket()` | Drop packets from non-cluster-head nodes |
| `allowPacketForward()` | Enable bridging only between different clusters |
| `routeRecvPacket()` | Selective retransmission via zero-hop to cluster heads |

### Bloom Filter Decision

Evaluated three libraries:
- **ArashPartow/bloom** (`https://github.com/ArashPartow/bloom`): Uses `std::vector` (dynamic allocation). Header-only but violates MeshCore's "no dynamic allocation" principle.
- **jvirkki/libbloom** (`https://github.com/jvirkki/libbloom`): C library, uses `malloc/calloc`. Server-oriented, overkill for 100-element filters.
- **aappleby/smhasher** (`https://github.com/aappleby/smhasher`): Hash functions only, not a bloom filter.

**Decision**: Custom `StaticBloomFilter` template class (~60 lines). FNV-1a hashing with multiple seed passes. Fixed-size bit array. Zero heap allocation. Matches MeshCore coding principles.

### Build System Decision

- **Flight firmware**: ESP-IDF (single MCU, shares radio with tracker via FreeRTOS mutex)
- **Bench testing**: PlatformIO (`mesh-stack/meshcore-lr2021/`) for quick iteration
- **Upstream PRs**: Two separate tightly-scoped PRs to MeshCore: (1) LR2021 variant, (2) StratoRelayMesh example

### Single MCU Justification

ESP32-C3 current tracker usage: 4.4 KB BSS, 134 KB flash code. Free: 258 KB DRAM, 3,700 KB flash. MeshCore core + StratoRelay additions: ~32 KB DRAM, ~100 KB flash. Well within budget.

## Consequences

### Positive
- **No ground node changes**: Stock MeshCore firmware works as-is
- **Community value**: Stratospheric range for MeshCore community without breaking local networks
- **Free telemetry**: Balloon position visible on MeshCore map without internet
- **Incremental**: Basic repeater works first (Phase 2a), clustering added on top (Phase 2b)
- **Upstreamable**: StratoRelayMesh is a clean subclass, could become a MeshCore example

### Negative
- **Approximate clustering**: Bloom filter false positives cause over-filtering (safe — ground flood still delivers). Union-find from flood paths is heuristic, not exact topology.
- **Unknown node density**: Real-world ground node counts at stratospheric range are unmeasured. Design is parameterized but needs tuning after first flight data.
- **Advert GPS coverage varies**: Only companion radios with GPS include lat/lon in adverts. Dumb repeaters without GPS can't be geographically clustered. RF topology clustering (union-find on flood paths) is the primary mechanism.
- **RAM for node table**: 256-node table is 2.3 KB. If actual density exceeds this, LRU eviction drops oldest nodes. This may cause clusters to be re-evaluated frequently in dense areas.

### Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Too few nodes for meaningful clustering | Fallback to normal repeater mode if < STRATO_MIN_CLUSTER_SIZE nodes per cluster |
| Too many nodes (> 256) overwhelm NodeTable | LRU eviction + increase SNR threshold to only track strongest nodes |
| MeshCore upstream rejects PR | Stratorelay runs as external PlatformIO project, doesn't need to be in MeshCore core |
| Balloon advert triggers ground node flood echo | Set balloon advert interval to 60 min (configurable) vs default 5 min |
| Cluster head goes offline | Re-election at next REBUILD_INTERVAL (5 min), packets temporarily unfiltered |

## Reference Repositories

| Repo | URL | Purpose |
|---|---|---|
| MeshCore | `https://github.com/meshcore-dev/MeshCore` | Base framework, pinned to `companion-v1.15.0` |
| ArashPartow/bloom | `https://github.com/ArashPartow/bloom` | Evaluated and rejected (dynamic allocation) |
| jvirkki/libbloom | `https://github.com/jvirkki/libbloom` | Evaluated and rejected (malloc-based) |
| aappleby/smhasher | `https://github.com/aappleby/smhasher` | MurmurHash3 reference (not used, FNV-1a sufficient) |

## Related Decisions

- ADR-012: Mesh networking strategy (FIPS + MeshCore + TollGate + Nostr)
- ADR-009: V1 omnidirectional / V2 directional antenna strategy
- ADR-010: Adaptive TX power per TDMA slot
