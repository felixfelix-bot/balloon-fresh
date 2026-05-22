#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "fips_transport.h"
#include "mbedtls/sha256.h"
#include "uECC.h"

static uint8_t initiator_buf[256];
static size_t initiator_buf_len;
static uint8_t responder_buf[256];
static size_t responder_buf_len;

static uint8_t rand_state = 42;
static int fake_rng(uint8_t *dest, unsigned size) {
    for (unsigned i = 0; i < size; i++) {
        rand_state = (rand_state * 1103515245 + 12345) & 0xFF;
        dest[i] = rand_state;
    }
    return 1;
}

static int init_send(const uint8_t *data, size_t len) {
    memcpy(initiator_buf, data, len);
    initiator_buf_len = len;
    return 0;
}
static int init_recv(uint8_t *data, size_t max_len) {
    if (responder_buf_len > max_len) return -1;
    memcpy(data, responder_buf, responder_buf_len);
    return (int)responder_buf_len;
}
static int resp_send(const uint8_t *data, size_t len) {
    memcpy(responder_buf, data, len);
    responder_buf_len = len;
    return 0;
}
static int resp_recv(uint8_t *data, size_t max_len) {
    if (initiator_buf_len > max_len) return -1;
    memcpy(data, initiator_buf, initiator_buf_len);
    return (int)initiator_buf_len;
}

static int test_keygen(void) {
    uint8_t pub[64], priv[32];
    uECC_make_key(pub, priv, uECC_secp256k1());
    uint8_t pub2[64];
    uECC_compute_public_key(priv, pub2, uECC_secp256k1());
    return memcmp(pub, pub2, 64) == 0 ? 1 : 0;
}

static int test_compress_decompress(void) {
    uint8_t pub[64], priv[32];
    uECC_make_key(pub, priv, uECC_secp256k1());

    uint8_t compressed[33];
    uECC_compress(pub, compressed, uECC_secp256k1());

    uint8_t pub2[64];
    uECC_decompress(compressed, pub2, uECC_secp256k1());

    return memcmp(pub, pub2, 64) == 0 ? 1 : 0;
}

static int test_node_addr(void) {
    uint8_t pub[64], priv[32];
    uECC_make_key(pub, priv, uECC_secp256k1());

    uint8_t addr[16];
    fips_get_node_addr(pub, addr);

    uint8_t expected[32];
    mbedtls_sha256(pub, 64, expected, 0);
    return memcmp(addr, expected, 16) == 0 ? 1 : 0;
}

static int test_msg_sizes(void) {
    if (FIPS_MSG1_SIZE != 98) { printf("  MSG1=%d != 98\n", FIPS_MSG1_SIZE); return 0; }
    if (FIPS_MSG2_SIZE != 49) { printf("  MSG2=%d != 49\n", FIPS_MSG2_SIZE); return 0; }
    return 1;
}

static int test_handshake(void) {
    uint8_t init_priv[32], init_pub[64];
    uint8_t resp_priv[32], resp_pub[64];
    uECC_make_key(init_pub, init_priv, uECC_secp256k1());
    uECC_make_key(resp_pub, resp_priv, uECC_secp256k1());

    uint8_t resp_compressed[33];
    uECC_compress(resp_pub, resp_compressed, uECC_secp256k1());

    fips_session_t init_sess;
    fips_init(&init_sess, init_priv, resp_compressed);

    fips_session_t resp_sess;
    fips_init(&resp_sess, NULL, NULL);

    uint8_t msg1[256];
    size_t msg1_len;
    int r = fips_handshake_initiator_msg1(&init_sess, msg1, &msg1_len);
    if (r != 0) { printf("  msg1 gen failed: %d\n", r); return 0; }
    if (msg1_len != FIPS_MSG1_SIZE) { printf("  msg1 size: %zu != %d\n", msg1_len, FIPS_MSG1_SIZE); return 0; }

    uint8_t msg2[256];
    size_t msg2_len;
    r = fips_handshake_responder_process_msg1(&resp_sess, resp_priv, msg1, msg1_len, msg2, &msg2_len);
    if (r != 0) { printf("  msg1 process failed: %d\n", r); return 0; }
    if (msg2_len != FIPS_MSG2_SIZE) { printf("  msg2 size: %zu != %d\n", msg2_len, FIPS_MSG2_SIZE); return 0; }

    r = fips_handshake_initiator_process_msg2(&init_sess, msg2, msg2_len);
    if (r != 0) { printf("  msg2 process failed: %d\n", r); return 0; }

    if (init_sess.state != FIPS_STATE_ESTABLISHED) { printf("  init not established\n"); return 0; }
    if (resp_sess.state != FIPS_STATE_ESTABLISHED) { printf("  resp not established\n"); return 0; }

    return 1;
}

static int test_encryption(void) {
    uint8_t init_priv[32], init_pub[64];
    uint8_t resp_priv[32], resp_pub[64];
    uECC_make_key(init_pub, init_priv, uECC_secp256k1());
    uECC_make_key(resp_pub, resp_priv, uECC_secp256k1());

    uint8_t resp_compressed[33];
    uECC_compress(resp_pub, resp_compressed, uECC_secp256k1());

    fips_session_t init_sess;
    fips_init(&init_sess, init_priv, resp_compressed);
    fips_session_t resp_sess;
    fips_init(&resp_sess, NULL, NULL);

    uint8_t msg1[256]; size_t msg1_len;
    fips_handshake_initiator_msg1(&init_sess, msg1, &msg1_len);
    uint8_t msg2[256]; size_t msg2_len;
    fips_handshake_responder_process_msg1(&resp_sess, resp_priv, msg1, msg1_len, msg2, &msg2_len);
    fips_handshake_initiator_process_msg2(&init_sess, msg2, msg2_len);

    const char *plaintext = "Hello from balloon!";
    size_t pt_len = strlen(plaintext);
    uint8_t encrypted[256];
    size_t enc_len;
    int r = fips_encrypt(&init_sess, (const uint8_t *)plaintext, pt_len, encrypted, &enc_len);
    if (r != 0) { printf("  encrypt failed: %d\n", r); return 0; }

    uint8_t decrypted[256];
    size_t dec_len;
    r = fips_decrypt(&resp_sess, encrypted, enc_len, decrypted, &dec_len);
    if (r != 0) { printf("  decrypt failed: %d\n", r); return 0; }
    if (dec_len != pt_len) { printf("  dec len mismatch: %zu != %zu\n", dec_len, pt_len); return 0; }
    if (memcmp(plaintext, decrypted, dec_len) != 0) { printf("  content mismatch\n"); return 0; }

    return 1;
}

static int test_bidirectional(void) {
    uint8_t init_priv[32], init_pub[64];
    uint8_t resp_priv[32], resp_pub[64];
    uECC_make_key(init_pub, init_priv, uECC_secp256k1());
    uECC_make_key(resp_pub, resp_priv, uECC_secp256k1());

    uint8_t resp_compressed[33];
    uECC_compress(resp_pub, resp_compressed, uECC_secp256k1());
    uint8_t init_compressed[33];
    uECC_compress(init_pub, init_compressed, uECC_secp256k1());

    fips_session_t init_sess;
    fips_init(&init_sess, init_priv, resp_compressed);
    fips_session_t resp_sess;
    fips_init(&resp_sess, resp_priv, init_compressed);

    uint8_t msg1[256]; size_t msg1_len;
    fips_handshake_initiator_msg1(&init_sess, msg1, &msg1_len);
    uint8_t msg2[256]; size_t msg2_len;
    fips_handshake_responder_process_msg1(&resp_sess, resp_priv, msg1, msg1_len, msg2, &msg2_len);
    fips_handshake_initiator_process_msg2(&init_sess, msg2, msg2_len);

    const char *msg_a = "Initiator to responder";
    const char *msg_b = "Responder to initiator";

    uint8_t enc_a[256], enc_b[256], dec_a[256], dec_b[256];
    size_t enc_a_len, enc_b_len, dec_a_len, dec_b_len;

    fips_encrypt(&init_sess, (const uint8_t *)msg_a, strlen(msg_a), enc_a, &enc_a_len);
    fips_decrypt(&resp_sess, enc_a, enc_a_len, dec_a, &dec_a_len);
    if (dec_a_len != strlen(msg_a) || memcmp(msg_a, dec_a, dec_a_len) != 0) {
        printf("  A->B failed\n"); return 0;
    }

    fips_encrypt(&resp_sess, (const uint8_t *)msg_b, strlen(msg_b), enc_b, &enc_b_len);
    fips_decrypt(&init_sess, enc_b, enc_b_len, dec_b, &dec_b_len);
    if (dec_b_len != strlen(msg_b) || memcmp(msg_b, dec_b, dec_b_len) != 0) {
        printf("  B->A failed\n"); return 0;
    }

    return 1;
}

static int test_roundtrip(void) {
    uint8_t init_priv[32], init_pub[64];
    uint8_t resp_priv[32], resp_pub[64];
    uECC_make_key(init_pub, init_priv, uECC_secp256k1());
    uECC_make_key(resp_pub, resp_priv, uECC_secp256k1());

    uint8_t resp_compressed[33];
    uECC_compress(resp_pub, resp_compressed, uECC_secp256k1());

    fips_session_t init_sess;
    fips_init(&init_sess, init_priv, resp_compressed);

    initiator_buf_len = 0;
    responder_buf_len = 0;

    fips_session_t resp_sess;
    fips_init(&resp_sess, NULL, NULL);

    fips_run_initiator(&init_sess, init_send, init_recv);

    fips_session_t resp_sess2;
    fips_init(&resp_sess2, NULL, NULL);
    int r = fips_run_responder(&resp_sess2, resp_priv, resp_send, resp_recv);
    if (r != 0) { printf("  responder failed: %d\n", r); return 0; }
    if (resp_sess2.state != FIPS_STATE_ESTABLISHED) { printf("  resp2 not established\n"); return 0; }

    return 1;
}

static int test_tamper_detection(void) {
    uint8_t init_priv[32], init_pub[64];
    uint8_t resp_priv[32], resp_pub[64];
    uECC_make_key(init_pub, init_priv, uECC_secp256k1());
    uECC_make_key(resp_pub, resp_priv, uECC_secp256k1());

    uint8_t resp_compressed[33];
    uECC_compress(resp_pub, resp_compressed, uECC_secp256k1());

    fips_session_t init_sess;
    fips_init(&init_sess, init_priv, resp_compressed);
    fips_session_t resp_sess;
    fips_init(&resp_sess, NULL, NULL);

    uint8_t msg1[256]; size_t msg1_len;
    fips_handshake_initiator_msg1(&init_sess, msg1, &msg1_len);

    msg1[10] ^= 0xFF;

    uint8_t msg2[256]; size_t msg2_len;
    int r = fips_handshake_responder_process_msg1(&resp_sess, resp_priv, msg1, msg1_len, msg2, &msg2_len);
    return (r != 0) ? 1 : 0;
}

static int test_multiple_messages(void) {
    uint8_t init_priv[32], init_pub[64];
    uint8_t resp_priv[32], resp_pub[64];
    uECC_make_key(init_pub, init_priv, uECC_secp256k1());
    uECC_make_key(resp_pub, resp_priv, uECC_secp256k1());

    uint8_t resp_compressed[33];
    uECC_compress(resp_pub, resp_compressed, uECC_secp256k1());

    fips_session_t init_sess;
    fips_init(&init_sess, init_priv, resp_compressed);
    fips_session_t resp_sess;
    fips_init(&resp_sess, NULL, NULL);

    uint8_t msg1[256]; size_t msg1_len;
    fips_handshake_initiator_msg1(&init_sess, msg1, &msg1_len);
    uint8_t msg2[256]; size_t msg2_len;
    fips_handshake_responder_process_msg1(&resp_sess, resp_priv, msg1, msg1_len, msg2, &msg2_len);
    fips_handshake_initiator_process_msg2(&init_sess, msg2, msg2_len);

    for (int i = 0; i < 10; i++) {
        uint8_t pt[32];
        memset(pt, i, sizeof(pt));

        uint8_t enc[256]; size_t enc_len;
        if (fips_encrypt(&init_sess, pt, sizeof(pt), enc, &enc_len) != 0) {
            printf("  encrypt %d failed\n", i); return 0;
        }

        uint8_t dec[256]; size_t dec_len;
        if (fips_decrypt(&resp_sess, enc, enc_len, dec, &dec_len) != 0) {
            printf("  decrypt %d failed\n", i); return 0;
        }
        if (dec_len != sizeof(pt) || memcmp(pt, dec, dec_len) != 0) {
            printf("  content mismatch %d\n", i); return 0;
        }
    }
    return 1;
}

static int test_state_guards(void) {
    fips_session_t sess;
    fips_init(&sess, NULL, NULL);

    uint8_t pt[16] = {0};
    uint8_t enc[256]; size_t enc_len;
    int r = fips_encrypt(&sess, pt, sizeof(pt), enc, &enc_len);
    if (r == 0) { printf("  encrypt should fail in IDLE\n"); return 0; }

    uint8_t dec[256]; size_t dec_len;
    r = fips_decrypt(&sess, pt, sizeof(pt), dec, &dec_len);
    if (r == 0) { printf("  decrypt should fail in IDLE\n"); return 0; }

    uint8_t init_priv[32], init_pub[64];
    uint8_t resp_priv[32], resp_pub[64];
    uECC_make_key(init_pub, init_priv, uECC_secp256k1());
    uECC_make_key(resp_pub, resp_priv, uECC_secp256k1());

    uint8_t resp_compressed[33];
    uECC_compress(resp_pub, resp_compressed, uECC_secp256k1());

    fips_session_t init_sess;
    fips_init(&init_sess, init_priv, resp_compressed);
    uint8_t msg1[256]; size_t msg1_len;
    fips_handshake_initiator_msg1(&init_sess, msg1, &msg1_len);

    if (init_sess.state != FIPS_STATE_WAIT_MSG2) { printf("  state should be WAIT_MSG2\n"); return 0; }
    r = fips_encrypt(&init_sess, pt, sizeof(pt), enc, &enc_len);
    if (r == 0) { printf("  encrypt should fail in WAIT_MSG2\n"); return 0; }

    return 1;
}

static int test_max_payload_boundary(void) {
    uint8_t init_priv[32], init_pub[64];
    uint8_t resp_priv[32], resp_pub[64];
    uECC_make_key(init_pub, init_priv, uECC_secp256k1());
    uECC_make_key(resp_pub, resp_priv, uECC_secp256k1());

    uint8_t resp_compressed[33];
    uECC_compress(resp_pub, resp_compressed, uECC_secp256k1());

    fips_session_t init_sess;
    fips_init(&init_sess, init_priv, resp_compressed);
    fips_session_t resp_sess;
    fips_init(&resp_sess, NULL, NULL);

    uint8_t msg1[256]; size_t msg1_len;
    fips_handshake_initiator_msg1(&init_sess, msg1, &msg1_len);
    uint8_t msg2[256]; size_t msg2_len;
    fips_handshake_responder_process_msg1(&resp_sess, resp_priv, msg1, msg1_len, msg2, &msg2_len);
    fips_handshake_initiator_process_msg2(&init_sess, msg2, msg2_len);

    uint16_t max_pt = FIPS_MAX_PAYLOAD - FIPS_FMP_OVERHEAD;
    uint8_t pt_max[256];
    memset(pt_max, 0xAA, max_pt);
    uint8_t enc[512]; size_t enc_len;
    int r = fips_encrypt(&init_sess, pt_max, max_pt, enc, &enc_len);
    if (r != 0) { printf("  encrypt at max_pt=%u failed: %d\n", max_pt, r); return 0; }

    uint8_t pt_over[256];
    memset(pt_over, 0xBB, max_pt + 1);
    r = fips_encrypt(&init_sess, pt_over, max_pt + 1, enc, &enc_len);
    if (r == 0) { printf("  encrypt over max_pt should fail\n"); return 0; }

    return 1;
}

static int test_corrupt_ciphertext(void) {
    uint8_t init_priv[32], init_pub[64];
    uint8_t resp_priv[32], resp_pub[64];
    uECC_make_key(init_pub, init_priv, uECC_secp256k1());
    uECC_make_key(resp_pub, resp_priv, uECC_secp256k1());

    uint8_t resp_compressed[33];
    uECC_compress(resp_pub, resp_compressed, uECC_secp256k1());

    fips_session_t init_sess;
    fips_init(&init_sess, init_priv, resp_compressed);
    fips_session_t resp_sess;
    fips_init(&resp_sess, NULL, NULL);

    uint8_t msg1[256]; size_t msg1_len;
    fips_handshake_initiator_msg1(&init_sess, msg1, &msg1_len);
    uint8_t msg2[256]; size_t msg2_len;
    fips_handshake_responder_process_msg1(&resp_sess, resp_priv, msg1, msg1_len, msg2, &msg2_len);
    fips_handshake_initiator_process_msg2(&init_sess, msg2, msg2_len);

    const char *plaintext = "Test corruption detection";
    uint8_t enc[256]; size_t enc_len;
    fips_encrypt(&init_sess, (const uint8_t *)plaintext, strlen(plaintext), enc, &enc_len);

    enc[enc_len - 3] ^= 0xFF;

    uint8_t dec[256]; size_t dec_len;
    int r = fips_decrypt(&resp_sess, enc, enc_len, dec, &dec_len);
    if (r == 0) { printf("  decrypt should fail on corrupt ciphertext\n"); return 0; }

    return 1;
}

int main(void) {
    uECC_set_rng(fake_rng);
    int pass = 0, fail = 0;

    #define RUN(name) do { \
        printf("  %-35s", #name); \
        if (test_##name()) { printf("PASS\n"); pass++; } \
        else { printf("FAIL\n"); fail++; } \
    } while(0)

    printf("FIPS transport tests:\n");
    RUN(keygen);
    RUN(compress_decompress);
    RUN(node_addr);
    RUN(msg_sizes);
    RUN(handshake);
    RUN(encryption);
    RUN(bidirectional);
    RUN(roundtrip);
    RUN(tamper_detection);
    RUN(multiple_messages);
    RUN(state_guards);
    RUN(max_payload_boundary);
    RUN(corrupt_ciphertext);

    printf("\n%d/%d passed\n", pass, pass + fail);
    return fail > 0 ? 1 : 0;
}
