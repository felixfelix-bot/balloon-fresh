#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

extern "C" {
#include "fips_transport.h"
#include "pipeline.h"
}

extern "C" {
#include "uECC.h"
}

#define MAX_FRAMES 128
static uint8_t g_frames[MAX_FRAMES][256];
static uint16_t g_frame_lens[MAX_FRAMES];
static int g_frame_count;

static void collect_frame(const uint8_t *frame, uint16_t len, void *user_data) {
    (void)user_data;
    assert(g_frame_count < MAX_FRAMES);
    memcpy(g_frames[g_frame_count], frame, len);
    g_frame_lens[g_frame_count] = len;
    g_frame_count++;
}

static void reset_frames(void) {
    g_frame_count = 0;
    memset(g_frames, 0, sizeof(g_frames));
    memset(g_frame_lens, 0, sizeof(g_frame_lens));
}

static void do_handshake(fips_session_t &init_sess, fips_session_t &resp_sess) {
    uint8_t init_priv[32], init_pub[64];
    uint8_t resp_priv[32], resp_pub[64];
    uECC_make_key(init_pub, init_priv, uECC_secp256k1());
    uECC_make_key(resp_pub, resp_priv, uECC_secp256k1());

    uint8_t resp_compressed[33];
    uECC_compress(resp_pub, resp_compressed, uECC_secp256k1());

    fips_init(&init_sess, init_priv, resp_compressed);
    fips_init(&resp_sess, NULL, NULL);

    uint8_t msg1[256]; size_t msg1_len;
    fips_handshake_initiator_msg1(&init_sess, msg1, &msg1_len);
    uint8_t msg2[256]; size_t msg2_len;
    fips_handshake_responder_process_msg1(&resp_sess, resp_priv, msg1, msg1_len, msg2, &msg2_len);
    fips_handshake_initiator_process_msg2(&init_sess, msg2, msg2_len);
}

static int run_full_stack(fips_session_t &init_sess, fips_session_t &resp_sess,
                          const uint8_t *plaintext, size_t pt_len,
                          uint8_t frag_size, uint8_t redundancy) {
    uint8_t ciphertext[512];
    size_t ct_len = 0;

    int r = fips_encrypt(&init_sess, plaintext, pt_len, ciphertext, &ct_len);
    if (r != 0) return -1;

    reset_frames();
    pipeline_rx_reset();
    pipeline_rx_set_data_len((uint16_t)ct_len);

    int n = pipeline_tx_encode_fragment(ciphertext, (uint16_t)ct_len, frag_size, redundancy, collect_frame, NULL);
    if (n <= 0) return -2;

    uint8_t reassembled[512];
    uint16_t reassembled_len = 0;
    int decoded = 0;
    for (int i = 0; i < n; i++) {
        r = pipeline_rx_feed_frame(g_frames[i], g_frame_lens[i], reassembled, &reassembled_len, sizeof(reassembled));
        if (r == 1) { decoded = 1; break; }
    }
    if (!decoded) return -3;
    if (reassembled_len != ct_len) return -4;
    if (memcmp(ciphertext, reassembled, ct_len) != 0) return -5;

    uint8_t decrypted[512];
    size_t dec_len = 0;
    r = fips_decrypt(&resp_sess, reassembled, reassembled_len, decrypted, &dec_len);
    if (r != 0) return -6;
    if (dec_len != pt_len) return -7;
    if (memcmp(plaintext, decrypted, pt_len) != 0) return -8;

    return n;
}

static int test_fips_pipeline_roundtrip(void) {
    fips_session_t init_sess, resp_sess;
    do_handshake(init_sess, resp_sess);

    uint8_t payload[150];
    for (int i = 0; i < 150; i++) payload[i] = i & 0xFF;

    int n = run_full_stack(init_sess, resp_sess, payload, sizeof(payload), 80, 1);
    if (n <= 0) { printf("  roundtrip failed: %d\n", n); return 0; }
    return 1;
}

static int test_small_payload_single_frame(void) {
    fips_session_t init_sess, resp_sess;
    do_handshake(init_sess, resp_sess);

    uint8_t payload[28];
    for (int i = 0; i < 28; i++) payload[i] = i;

    int n = run_full_stack(init_sess, resp_sess, payload, sizeof(payload), 80, 0);
    if (n <= 0) { printf("  small payload failed: %d\n", n); return 0; }
    return 1;
}

static int test_large_payload_with_redundancy(void) {
    fips_session_t init_sess, resp_sess;
    do_handshake(init_sess, resp_sess);

    uint8_t payload[190];
    for (int i = 0; i < 190; i++) payload[i] = i ^ 0xAA;

    int n = run_full_stack(init_sess, resp_sess, payload, sizeof(payload), 60, 3);
    if (n <= 0) { printf("  large payload failed: %d\n", n); return 0; }
    return 1;
}

static int test_bidirectional(void) {
    fips_session_t init_sess, resp_sess;
    do_handshake(init_sess, resp_sess);

    const char *msg1 = "Hello from balloon!";
    const char *msg2 = "Acknowledged, ground.";

    uint8_t ct1[256]; size_t ct1_len;
    fips_encrypt(&init_sess, (const uint8_t *)msg1, strlen(msg1), ct1, &ct1_len);

    uint8_t pt1[256]; size_t pt1_len;
    fips_decrypt(&resp_sess, ct1, ct1_len, pt1, &pt1_len);
    if (pt1_len != strlen(msg1) || memcmp(msg1, pt1, pt1_len) != 0) {
        printf("  msg1 content mismatch\n"); return 0;
    }

    reset_frames();
    pipeline_rx_reset();
    pipeline_rx_set_data_len((uint16_t)ct1_len);
    int n = pipeline_tx_encode_fragment(ct1, (uint16_t)ct1_len, 80, 0, collect_frame, NULL);
    if (n <= 0) { printf("  fragment msg1 failed\n"); return 0; }

    uint8_t reassembled[256]; uint16_t rlen = 0;
    int decoded = 0;
    for (int i = 0; i < n; i++) {
        int r = pipeline_rx_feed_frame(g_frames[i], g_frame_lens[i], reassembled, &rlen, sizeof(reassembled));
        if (r == 1) { decoded = 1; break; }
    }
    if (!decoded) { printf("  reassemble msg1 failed\n"); return 0; }

    uint8_t ct2[256]; size_t ct2_len;
    fips_encrypt(&resp_sess, (const uint8_t *)msg2, strlen(msg2), ct2, &ct2_len);

    uint8_t pt2[256]; size_t pt2_len;
    fips_decrypt(&init_sess, ct2, ct2_len, pt2, &pt2_len);
    if (pt2_len != strlen(msg2) || memcmp(msg2, pt2, pt2_len) != 0) {
        printf("  msg2 content mismatch\n"); return 0;
    }

    return 1;
}

#define RUN(name) printf("  %-35s", #name); if (test_##name()) printf("PASS\n"); else { printf("FAIL\n"); fail++; }

int main(void) {
    printf("\n=== FIPS+Pipeline Integration Tests ===\n\n");
    int fail = 0;

    printf("Integration tests:\n");
    RUN(fips_pipeline_roundtrip);
    RUN(small_payload_single_frame);
    RUN(large_payload_with_redundancy);
    RUN(bidirectional);

    int total = 4;
    printf("\n=== Results: %d/%d passed ===\n", total - fail, total);
    return fail > 0 ? 1 : 0;
}
