#pragma once

#include <cstdint>

struct ClusterHead {
    uint8_t node_hash;
    int8_t best_snr;
    uint32_t last_heard;
    uint8_t member_count;
};

template<int MAX_CLUSTERS>
class ClusterHeadElector {
    ClusterHead heads_[MAX_CLUSTERS];
    int cluster_count_;

public:
    ClusterHeadElector() : cluster_count_(0) {
        clear();
    }

    void clear() {
        memset(heads_, 0, sizeof(heads_));
        cluster_count_ = 0;
    }

    int getClusterCount() const { return cluster_count_; }
    const ClusterHead& getHead(int idx) const { return heads_[idx]; }

    template<int MAX_NODES>
    void elect(const NodeTable<MAX_NODES>& nodes, const int* roots, int nodeCount,
               uint32_t now, float recencyW = 3.0f, float signalW = 2.0f, float stabilityW = 1.0f) {
        clear();

        bool seen[MAX_CLUSTERS * 4];
        memset(seen, 0, sizeof(seen));

        for (int i = 0; i < nodeCount; i++) {
            int root = roots[i];
            int slot = -1;
            for (int c = 0; c < cluster_count_; c++) {
                if (heads_[c].node_hash == (uint8_t)root) {
                    slot = c;
                    break;
                }
            }

            if (slot < 0) {
                if (cluster_count_ >= MAX_CLUSTERS) continue;
                slot = cluster_count_++;
                heads_[slot].node_hash = (uint8_t)root;
                heads_[slot].best_snr = -128;
                heads_[slot].last_heard = 0;
                heads_[slot].member_count = 0;
            }

            const auto& node = nodes.get(i);
            heads_[slot].member_count++;

            float score = recencyW / (float)(now - node.last_heard + 1)
                        + signalW * (float)(node.last_snr + 20)
                        + stabilityW * (float)node.uf_rank;

            float bestScore = recencyW / (float)(now - heads_[slot].last_heard + 1)
                            + signalW * (float)(heads_[slot].best_snr + 20)
                            + stabilityW * 0.0f;

            if (node.last_snr > heads_[slot].best_snr || heads_[slot].best_snr == -128) {
                heads_[slot].best_snr = node.last_snr;
                heads_[slot].last_heard = node.last_heard;
                heads_[slot].node_hash = (uint8_t)root;
            }
        }
    }
};
