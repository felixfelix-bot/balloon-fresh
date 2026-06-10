#pragma once

#include <cstdint>
#include <cstring>

template<int MAX_NODES>
class NodeTable {
public:
    struct NodeRecord {
        uint8_t hash;
        uint8_t uf_parent;
        uint8_t uf_rank;
        int8_t last_snr;
        uint32_t last_heard;
        bool active;
    };

private:
    NodeRecord nodes_[MAX_NODES];
    int count_;

    int findFreeSlot() {
        for (int i = 0; i < MAX_NODES; i++) {
            if (!nodes_[i].active) return i;
        }
        return -1;
    }

    int findOldest() {
        int idx = -1;
        uint32_t oldest = UINT32_MAX;
        for (int i = 0; i < MAX_NODES; i++) {
            if (nodes_[i].active && nodes_[i].last_heard < oldest) {
                oldest = nodes_[i].last_heard;
                idx = i;
            }
        }
        return idx;
    }

public:
    NodeTable() : count_(0) {
        clear();
    }

    void clear() {
        memset(nodes_, 0, sizeof(nodes_));
        count_ = 0;
    }

    int findByHash(uint8_t hash) const {
        for (int i = 0; i < MAX_NODES; i++) {
            if (nodes_[i].active && nodes_[i].hash == hash) return i;
        }
        return -1;
    }

    int insertOrUpdate(uint8_t hash, int8_t snr, uint32_t timestamp) {
        int idx = findByHash(hash);
        if (idx >= 0) {
            nodes_[idx].last_snr = snr;
            nodes_[idx].last_heard = timestamp;
            return idx;
        }

        idx = findFreeSlot();
        if (idx < 0) {
            idx = findOldest();
            if (idx < 0) return -1;
        } else {
            count_++;
        }

        nodes_[idx].hash = hash;
        nodes_[idx].uf_parent = (uint8_t)idx;
        nodes_[idx].uf_rank = 0;
        nodes_[idx].last_snr = snr;
        nodes_[idx].last_heard = timestamp;
        nodes_[idx].active = true;
        return idx;
    }

    void ageNodes(uint32_t now, uint32_t staleTimeout) {
        for (int i = 0; i < MAX_NODES; i++) {
            if (nodes_[i].active && (now - nodes_[i].last_heard) > staleTimeout) {
                nodes_[i].active = false;
                count_--;
            }
        }
    }

    int getCount() const { return count_; }
    const NodeRecord& get(int idx) const { return nodes_[idx]; }
    NodeRecord& get(int idx) { return nodes_[idx]; }
};
