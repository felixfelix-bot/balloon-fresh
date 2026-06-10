#pragma once

#include <cstring>
#include <cstddef>

template<int MAX_ELEMENTS, int FP_RATE_PER_MILLION = 10000>
class StaticBloomFilter {
    static constexpr int BIT_COUNT = MAX_ELEMENTS * 10;
    static constexpr int BYTE_COUNT = (BIT_COUNT + 7) / 8;
    static constexpr int NUM_HASHES = 7;

    uint8_t bits[BYTE_COUNT];
    int count;

    static uint32_t fnv1a(const uint8_t* data, size_t len, uint32_t seed) {
        uint32_t h = seed;
        for (size_t i = 0; i < len; i++) {
            h ^= data[i];
            h *= 16777619u;
        }
        return h;
    }

public:
    StaticBloomFilter() : count(0) {
        clear();
    }

    void clear() {
        memset(bits, 0, sizeof(bits));
        count = 0;
    }

    void insert(uint8_t key) {
        for (int i = 0; i < NUM_HASHES; i++) {
            uint32_t h = fnv1a(&key, 1, 0x811C9DC5u + (uint32_t)i * 0x01000193u);
            int bit = (int)(h % (uint32_t)BIT_COUNT);
            bits[bit / 8] |= (uint8_t)(1 << (bit % 8));
        }
        count++;
    }

    bool contains(uint8_t key) const {
        for (int i = 0; i < NUM_HASHES; i++) {
            uint32_t h = fnv1a(&key, 1, 0x811C9DC5u + (uint32_t)i * 0x01000193u);
            int bit = (int)(h % (uint32_t)BIT_COUNT);
            if (!(bits[bit / 8] & (uint8_t)(1 << (bit % 8)))) {
                return false;
            }
        }
        return true;
    }

    int size() const { return count; }
};
