#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include "../include/frag.h"

static uint8_t payload[200];
static uint8_t frame_buf[300];
static uint8_t assembly[300];

static void fill_payload(uint8_t *buf, uint8_t len, uint8_t seed) {
    for (uint8_t i = 0; i < len; i++) buf[i] = (uint8_t)(seed + i);
}

static void test_crc16_empty(void) {
    assert(frag_crc16((const uint8_t *)"", 0) == 0xFFFF);
    printf("PASS\n");
}

static void test_crc16_deterministic(void) {
    uint8_t data[20];
    fill_payload(data, 20, 0);
    assert(frag_crc16(data, 20) == frag_crc16(data, 20));
    printf("PASS\n");
}

static void test_crc16_different_data(void) {
    uint8_t data1[20], data2[20];
    fill_payload(data1, 20, 0);
    fill_payload(data2, 20, 1);
    assert(frag_crc16(data1, 20) != frag_crc16(data2, 20));
    printf("PASS\n");
}

static void test_reassembler_init(void) {
    frag_reassembler_t ra;
    frag_reassembler_init(&ra, 42, 3, 50, assembly, sizeof(assembly));
    assert(ra.block_id == 42);
    assert(ra.original_count == 3);
    assert(ra.frag_size == 50);
    assert(ra.frags_received == 0);
    assert(ra.complete == false);
    assert(ra.assembly_buf == assembly);
    printf("PASS\n");
}

static void test_feed_short_frame(void) {
    frag_reassembler_t ra;
    frag_reassembler_init(&ra, 1, 2, 10, assembly, sizeof(assembly));
    uint8_t short_frame[5] = {0x01, 0x00, 0x00, 0x02, 0x00};
    assert(frag_reassembler_feed(&ra, short_frame, 5) == -1);
    printf("PASS\n");
}

static void test_feed_wrong_block_id(void) {
    frag_reassembler_t ra;
    frag_reassembler_init(&ra, 1, 2, 10, assembly, sizeof(assembly));
    uint8_t frame[FRAG_HEADER_SIZE + 10];
    frag_make_frame(99, 0, 2, payload, 10, frame, sizeof(frame));
    assert(frag_reassembler_feed(&ra, frame, FRAG_HEADER_SIZE + 10) == -2);
    printf("PASS\n");
}

static void test_feed_wrong_count(void) {
    frag_reassembler_t ra;
    frag_reassembler_init(&ra, 1, 2, 10, assembly, sizeof(assembly));
    uint8_t frame[FRAG_HEADER_SIZE + 10];
    frag_make_frame(1, 0, 5, payload, 10, frame, sizeof(frame));
    assert(frag_reassembler_feed(&ra, frame, FRAG_HEADER_SIZE + 10) == -3);
    printf("PASS\n");
}

static void test_feed_duplicate(void) {
    frag_reassembler_t ra;
    frag_reassembler_init(&ra, 1, 2, 10, assembly, sizeof(assembly));

    fill_payload(payload, 10, 0xAA);
    uint8_t frame[FRAG_HEADER_SIZE + 10];
    frag_make_frame(1, 0, 2, payload, 10, frame, sizeof(frame));

    assert(frag_reassembler_feed(&ra, frame, FRAG_HEADER_SIZE + 10) == 1);
    assert(frag_reassembler_feed(&ra, frame, FRAG_HEADER_SIZE + 10) == 1);
    assert(ra.frags_received == 1);
    assert(!ra.complete);
    printf("PASS\n");
}

static void test_feed_completion(void) {
    frag_reassembler_t ra;
    uint8_t data1[20], data2[20];
    fill_payload(data1, 20, 0x10);
    fill_payload(data2, 20, 0x20);
    frag_reassembler_init(&ra, 7, 2, 20, assembly, sizeof(assembly));

    uint8_t f1[FRAG_HEADER_SIZE + 20], f2[FRAG_HEADER_SIZE + 20];
    frag_make_frame(7, 0, 2, data1, 20, f1, sizeof(f1));
    frag_make_frame(7, 1, 2, data2, 20, f2, sizeof(f2));

    assert(frag_reassembler_feed(&ra, f1, FRAG_HEADER_SIZE + 20) == 1);
    assert(!ra.complete);
    assert(frag_reassembler_feed(&ra, f2, FRAG_HEADER_SIZE + 20) == 0);
    assert(ra.complete);
    assert(ra.frags_received == 2);
    assert(memcmp(assembly, data1, 20) == 0);
    assert(memcmp(assembly + 20, data2, 20) == 0);
    printf("PASS\n");
}

static void test_make_frame_format(void) {
    uint8_t payload_in[10];
    fill_payload(payload_in, 10, 0x42);
    uint8_t out[FRAG_HEADER_SIZE + 10];
    uint16_t len = frag_make_frame(0x1234, 2, 4, payload_in, 10, out, sizeof(out));
    assert(len == FRAG_HEADER_SIZE + 10);

    frag_header_t hdr;
    memcpy(&hdr, out, FRAG_HEADER_SIZE);
    assert(hdr.block_id == 0x1234);
    assert(hdr.frag_index == 2);
    assert(hdr.original_count == 4);
    assert(memcmp(out + FRAG_HEADER_SIZE, payload_in, 10) == 0);
    printf("PASS\n");
}

static void test_make_frame_oversized(void) {
    uint8_t out[5];
    uint16_t len = frag_make_frame(1, 0, 1, payload, 10, out, 5);
    assert(len == 0);
    printf("PASS\n");
}

static void test_roundtrip_3_frags(void) {
    uint8_t orig[90];
    fill_payload(orig, 90, 0xCC);

    frag_reassembler_t ra;
    frag_reassembler_init(&ra, 42, 3, 30, assembly, sizeof(assembly));

    for (int i = 0; i < 3; i++) {
        uint8_t frame[FRAG_HEADER_SIZE + 30];
        uint16_t flen = frag_make_frame(42, i, 3, orig + i * 30, 30, frame, sizeof(frame));
        assert(flen > 0);
        int rc = frag_reassembler_feed(&ra, frame, flen);
        if (i < 2) assert(rc == 1);
        else assert(rc == 0);
    }

    assert(ra.complete);
    assert(memcmp(assembly, orig, 90) == 0);
    printf("PASS\n");
}

static void test_roundtrip_out_of_order(void) {
    uint8_t orig[60];
    fill_payload(orig, 60, 0xDD);

    frag_reassembler_t ra;
    frag_reassembler_init(&ra, 55, 2, 30, assembly, sizeof(assembly));

    uint8_t f0[FRAG_HEADER_SIZE + 30], f1[FRAG_HEADER_SIZE + 30];
    frag_make_frame(55, 0, 2, orig, 30, f0, sizeof(f0));
    frag_make_frame(55, 1, 2, orig + 30, 30, f1, sizeof(f1));

    assert(frag_reassembler_feed(&ra, f1, FRAG_HEADER_SIZE + 30) == 1);
    assert(!ra.complete);
    assert(frag_reassembler_feed(&ra, f0, FRAG_HEADER_SIZE + 30) == 0);
    assert(ra.complete);
    assert(memcmp(assembly, orig, 60) == 0);
    printf("PASS\n");
}

int main(void) {
    printf("\n=== Frag Tests ===\n\n");

    printf("TEST 1: CRC16 empty... ");
    test_crc16_empty();
    printf("TEST 2: CRC16 deterministic... ");
    test_crc16_deterministic();
    printf("TEST 3: CRC16 different data... ");
    test_crc16_different_data();
    printf("TEST 4: reassembler init... ");
    test_reassembler_init();
    printf("TEST 5: feed short frame... ");
    test_feed_short_frame();
    printf("TEST 6: feed wrong block_id... ");
    test_feed_wrong_block_id();
    printf("TEST 7: feed wrong count... ");
    test_feed_wrong_count();
    printf("TEST 8: feed duplicate... ");
    test_feed_duplicate();
    printf("TEST 9: feed completion... ");
    test_feed_completion();
    printf("TEST 10: make_frame format... ");
    test_make_frame_format();
    printf("TEST 11: make_frame oversized... ");
    test_make_frame_oversized();
    printf("TEST 12: roundtrip 3 frags... ");
    test_roundtrip_3_frags();
    printf("TEST 13: roundtrip out of order... ");
    test_roundtrip_out_of_order();

    printf("\n=== Results: 13/13 passed ===\n");
    return 0;
}
