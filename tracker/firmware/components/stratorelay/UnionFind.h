#pragma once

#include <cstdint>

template<int MAX_NODES>
class UnionFind {
    uint8_t parent_[MAX_NODES];
    uint8_t rank_[MAX_NODES];
    int n_;

public:
    void init(int n) {
        n_ = n;
        for (int i = 0; i < n_; i++) {
            parent_[i] = (uint8_t)i;
            rank_[i] = 0;
        }
    }

    int find(int x) {
        while (parent_[x] != (uint8_t)x) {
            parent_[x] = parent_[parent_[x]];
            x = parent_[x];
        }
        return x;
    }

    void unionSets(int a, int b) {
        int ra = find(a);
        int rb = find(b);
        if (ra == rb) return;
        if (rank_[ra] < rank_[rb]) {
            int tmp = ra; ra = rb; rb = tmp;
        }
        parent_[rb] = (uint8_t)ra;
        if (rank_[ra] == rank_[rb]) {
            rank_[ra]++;
        }
    }

    bool connected(int a, int b) {
        return find(a) == find(b);
    }

    int getRoot(int x) {
        return find(x);
    }
};
