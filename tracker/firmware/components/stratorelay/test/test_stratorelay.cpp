#include <cassert>
#include <cstdio>
#include <cinttypes>

#include "StaticBloomFilter.h"
#include "UnionFind.h"
#include "NodeTable.h"
#include "ClusterHeadElector.h"

static int tests_passed = 0;
static int tests_failed = 0;

#define ASSERT(cond, msg) do { \
    if (!(cond)) { printf("FAIL: %s (line %d)\n", msg, __LINE__); tests_failed++; return; } \
} while(0)

#define PASS(name) do { printf("  PASS: %s\n", name); tests_passed++; } while(0)

void test_bloom_filter_insert_contains() {
    StaticBloomFilter<100> bf;
    bf.insert(42);
    bf.insert(99);
    bf.insert(0);
    ASSERT(bf.contains(42), "inserted key 42 not found");
    ASSERT(bf.contains(99), "inserted key 99 not found");
    ASSERT(bf.contains(0), "inserted key 0 not found");
    PASS("bloom insert+contains");
}

void test_bloom_filter_nonmembers() {
    StaticBloomFilter<100> bf;
    int false_positives = 0;
    for (int i = 0; i < 50; i++) bf.insert((uint8_t)i);
    for (int i = 50; i < 200; i++) {
        if (bf.contains((uint8_t)i)) false_positives++;
    }
    float fp_rate = (float)false_positives / 150.0f;
    ASSERT(fp_rate < 0.05f, "FP rate too high");
    PASS("bloom non-member rejection");
}

void test_bloom_filter_clear() {
    StaticBloomFilter<100> bf;
    bf.insert(42);
    ASSERT(bf.contains(42), "42 should exist before clear");
    bf.clear();
    ASSERT(!bf.contains(42), "42 should not exist after clear");
    ASSERT(bf.size() == 0, "size should be 0 after clear");
    PASS("bloom clear");
}

void test_union_find_basic() {
    UnionFind<10> uf;
    uf.init(5);
    ASSERT(!uf.connected(0, 1), "0 and 1 should not be connected");
    uf.unionSets(0, 1);
    ASSERT(uf.connected(0, 1), "0 and 1 should be connected after union");
    PASS("union-find basic");
}

void test_union_find_separate() {
    UnionFind<10> uf;
    uf.init(6);
    uf.unionSets(0, 1);
    uf.unionSets(2, 3);
    ASSERT(uf.connected(0, 1), "0-1 connected");
    ASSERT(uf.connected(2, 3), "2-3 connected");
    ASSERT(!uf.connected(0, 2), "0-2 not connected");
    ASSERT(!uf.connected(1, 3), "1-3 not connected");
    uf.unionSets(1, 2);
    ASSERT(uf.connected(0, 3), "0-3 connected after bridging");
    PASS("union-find separate components");
}

void test_union_find_path_compression() {
    UnionFind<20> uf;
    uf.init(10);
    for (int i = 1; i < 10; i++) uf.unionSets(i - 1, i);
    ASSERT(uf.connected(0, 9), "0-9 connected through chain");
    int root0 = uf.find(0);
    int root9 = uf.find(9);
    ASSERT(root0 == root9, "roots should match");
    PASS("union-find path compression");
}

void test_node_table_insert_find() {
    NodeTable<32> nt;
    int idx = nt.insertOrUpdate(42, 10, 1000);
    ASSERT(idx >= 0, "insert should return valid index");
    int found = nt.findByHash(42);
    ASSERT(found == idx, "findByHash should return same index");
    ASSERT(nt.getCount() == 1, "count should be 1");
    PASS("node table insert+find");
}

void test_node_table_update() {
    NodeTable<32> nt;
    int idx1 = nt.insertOrUpdate(42, 10, 1000);
    int idx2 = nt.insertOrUpdate(42, 15, 2000);
    ASSERT(idx1 == idx2, "update should return same index");
    ASSERT(nt.getCount() == 1, "count should still be 1");
    ASSERT(nt.get(idx1).last_snr == 15, "SNR should be updated");
    ASSERT(nt.get(idx1).last_heard == 2000, "timestamp should be updated");
    PASS("node table update");
}

void test_node_table_aging() {
    NodeTable<32> nt;
    nt.insertOrUpdate(1, 10, 1000);
    nt.insertOrUpdate(2, 10, 5000);
    nt.ageNodes(6000, 2000);
    ASSERT(nt.findByHash(1) < 0, "node 1 should be aged out");
    ASSERT(nt.findByHash(2) >= 0, "node 2 should still be alive");
    PASS("node table aging");
}

void test_node_table_overflow() {
    NodeTable<4> nt;
    nt.insertOrUpdate(1, 5, 100);
    nt.insertOrUpdate(2, 5, 200);
    nt.insertOrUpdate(3, 5, 300);
    nt.insertOrUpdate(4, 5, 400);
    ASSERT(nt.getCount() == 4, "table should be full");
    int idx = nt.insertOrUpdate(5, 10, 500);
    ASSERT(idx >= 0, "eviction should make room");
    ASSERT(nt.findByHash(5) >= 0, "new node should be findable");
    PASS("node table overflow eviction");
}

void test_cluster_head_elector() {
    NodeTable<32> nt;
    nt.insertOrUpdate(1, 10, 1000);
    nt.insertOrUpdate(2, 5, 1000);
    nt.insertOrUpdate(3, 15, 1000);

    int roots[32];
    for (int i = 0; i < 3; i++) roots[i] = i;

    ClusterHeadElector<8> elector;
    elector.elect(nt, roots, 3, 1000);
    ASSERT(elector.getClusterCount() >= 1, "should have at least 1 cluster");
    PASS("cluster head elector basic");
}

int main() {
    printf("=== StratoRelay Utility Tests ===\n\n");

    printf("StaticBloomFilter:\n");
    test_bloom_filter_insert_contains();
    test_bloom_filter_nonmembers();
    test_bloom_filter_clear();

    printf("\nUnionFind:\n");
    test_union_find_basic();
    test_union_find_separate();
    test_union_find_path_compression();

    printf("\nNodeTable:\n");
    test_node_table_insert_find();
    test_node_table_update();
    test_node_table_aging();
    test_node_table_overflow();

    printf("\nClusterHeadElector:\n");
    test_cluster_head_elector();

    printf("\n=== Results: %d passed, %d failed ===\n", tests_passed, tests_failed);
    return tests_failed > 0 ? 1 : 0;
}
