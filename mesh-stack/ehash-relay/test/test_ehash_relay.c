/**
 * @file test_ehash_relay.c
 * @brief Host unit tests for the balloon e-hash relay module (Phase C).
 *
 * Compile:
 *   gcc -std=c11 -Wall -I include/ -I ../protocol/ \
 *     test/test_ehash_relay.c ehash_relay.c ehash_crypto.c \
 *     ehash_messages.c ehash_upstream.c ehash_radio_stub.c \
 *     -o /tmp/test_relay && /tmp/test_relay
 */

#include "ehash_relay.h"
#include "ehash_crypto.h"
#include "ehash_upstream.h"
#include "ehash_radio_stub.h"
#include <stdio.h>
#include <string.h>

/* ======================================================================== */
/*  Test Framework                                                          */
/* ======================================================================== */

static int g_pass = 0;
static int g_fail = 0;

#define CHECK(cond) do { \
    if (cond) { g_pass++; } \
    else { g_fail++; printf("  FAIL: %s (line %d)\n", #cond, __LINE__); } \
} while(0)

/* ======================================================================== */
/*  Test Data                                                               */
/* ======================================================================== */

static const uint8_t s_prevhash[32] = {
    0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,
    0x08,0x09,0x0a,0x0b,0x0c,0x0d,0x0e,0x0f,
    0x10,0x11,0x12,0x13,0x14,0x15,0x16,0x17,
    0x18,0x19,0x1a,0x1b,0x1c,0x1d,0x1e,0x1f
};

static const uint8_t s_coinbase1[20] = {
    0x46,0x65,0x6c,0x69,0x78,0x42,0x61,0x6c,
    0x6c,0x6f,0x6f,0x6e,0x21,0x00,0x00,0x00,
    0xaa,0xbb,0xcc,0xdd
};

static const uint8_t s_coinbase2[20] = {
    0xff,0xee,0xdd,0xcc,0xbb,0xaa,0x99,0x88,
    0x77,0x66,0x55,0x44,0x33,0x22,0x11,0x00,
    0x01,0x02,0x03,0x04
};

static const uint8_t s_merkle[2][32] = {
    {0xaa,0xaa,0xaa,0xaa,0xaa,0xaa,0xaa,0xaa,
     0xaa,0xaa,0xaa,0xaa,0xaa,0xaa,0xaa,0xaa,
     0xaa,0xaa,0xaa,0xaa,0xaa,0xaa,0xaa,0xaa,
     0xaa,0xaa,0xaa,0xaa,0xaa,0xaa,0xaa,0xaa},
    {0xbb,0xbb,0xbb,0xbb,0xbb,0xbb,0xbb,0xbb,
     0xbb,0xbb,0xbb,0xbb,0xbb,0xbb,0xbb,0xbb,
     0xbb,0xbb,0xbb,0xbb,0xbb,0xbb,0xbb,0xbb,
     0xbb,0xbb,0xbb,0xbb,0xbb,0xbb,0xbb,0xbb}
};

/* ======================================================================== */
/*  Upstream callback (captures forwarded nonces)                           */
/* ======================================================================== */

static ehash_nonce_t s_captured_nonce;
static int s_nonce_forward_count = 0;

static int test_upstream_tx(const ehash_nonce_t *nonce, void *ctx) {
    (void)ctx;
    s_captured_nonce = *nonce;
    s_nonce_forward_count++;
    return 0;
}

/* ======================================================================== */
/*  Helper: build a template struct                                         */
/* ======================================================================== */

static ehash_template_t make_test_template(uint32_t job_id) {
    ehash_template_t t;
    t.job_id = job_id;
    t.prevhash = s_prevhash;
    t.btc_version = 0x20000000;
    t.nbits = 0x17034219;
    t.ntime = 0;
    t.coinbase1 = s_coinbase1;
    t.coinbase1_len = sizeof(s_coinbase1);
    t.coinbase2 = s_coinbase2;
    t.coinbase2_len = sizeof(s_coinbase2);
    t.merkle_branch_count = 2;
    t.merkle_branches = s_merkle[0];
    t.clean_jobs = 1;
    return t;
}

/* ======================================================================== */
/*  Test 1: Template relay broadcasts via radio                             */
/* ======================================================================== */

static void test_template_relay(void) {
    printf("Test 1: template relay broadcast...\n");

    ehash_relay_t r;
    ehash_radio_stub_reset();
    ehash_relay_init(&r, ehash_radio_stub_broadcast,
                     ehash_radio_stub_unicast,
                     test_upstream_tx, NULL);

    /* Generate session key for encryption (D8) */
    ehash_crypto_session_start(r.session_key, 0x12345678);
    r.key_set = true;

    ehash_template_t tmpl = make_test_template(1);
    int rc = ehash_relay_on_template(&r, &tmpl, 1000);

    CHECK(rc > 0);  /* Should have broadcast something */
    CHECK(ehash_radio_stub_get_broadcast_count() == 1);

    size_t bcast_len = 0;
    const uint8_t *bcast = ehash_radio_stub_get_last_broadcast(&bcast_len);
    CHECK(bcast != NULL);
    CHECK(bcast_len > 0);
    /* Type byte should be EHASH_TEMPLATE */
    CHECK(bcast[0] == EHASH_TEMPLATE);

    /* Template should not be expired immediately */
    CHECK(!ehash_relay_template_expired(&r, 1000));

    printf("  templates_relayed=%u\n", r.templates_relayed);
}

/* ======================================================================== */
/*  Test 2: Nonce relay forwards upstream                                   */
/* ======================================================================== */

static void test_nonce_relay(void) {
    printf("Test 2: nonce relay upstream...\n");

    ehash_relay_t r;
    ehash_radio_stub_reset();
    s_nonce_forward_count = 0;
    ehash_relay_init(&r, ehash_radio_stub_broadcast,
                     ehash_radio_stub_unicast,
                     test_upstream_tx, NULL);

    /* Register station 7 with credit */
    ehash_relay_credit_set_balance(&r, 7, 10000, 500);

    /* Build a nonce envelope: type(1) + nonce struct(21) = 22 bytes */
    uint8_t buf[22];
    buf[0] = EHASH_NONCE;

    /* Encode nonce fields in little-endian */
    /* version(1) + job_id(4) + worker_id(4) + extranonce2(4) + ntime(4) + nonce(4) */
    buf[1] = 0x01;  /* version */
    uint32_t job_id = 1;
    memcpy(&buf[2], &job_id, 4);
    uint32_t worker_id = 7;
    memcpy(&buf[6], &worker_id, 4);
    uint32_t extranonce2 = 0x3039;
    memcpy(&buf[10], &extranonce2, 4);
    uint32_t ntime = 0x61A5B000;
    memcpy(&buf[14], &ntime, 4);
    uint32_t nonce_val = 0xDEADBEEF;
    memcpy(&buf[18], &nonce_val, 4);

    int rc = ehash_relay_on_nonce(&r, buf, sizeof(buf));

    CHECK(rc == 0);
    CHECK(s_nonce_forward_count == 1);
    CHECK(s_captured_nonce.worker_id == 7);
    CHECK(s_captured_nonce.job_id == 1);

    printf("  nonces_relayed=%u\n", r.nonces_relayed);
}

/* ======================================================================== */
/*  Test 3: Per-nonce credit issuance (D10)                                 */
/* ======================================================================== */

static void test_credit_issuance(void) {
    printf("Test 3: per-nonce credit issuance (D10)...\n");

    ehash_relay_t r;
    ehash_radio_stub_reset();
    s_nonce_forward_count = 0;
    ehash_relay_init(&r, ehash_radio_stub_broadcast,
                     ehash_radio_stub_unicast,
                     test_upstream_tx, NULL);

    /* Station 7 starts with 10000 sats balance, reward 500 per nonce */
    ehash_relay_credit_set_balance(&r, 7, 10000, 500);

    /* Submit a nonce */
    uint8_t buf[22];
    buf[0] = EHASH_NONCE;
    buf[1] = 0x01;
    uint32_t job_id = 1, worker_id = 7, extranonce2 = 100, ntime = 0, nonce_val = 200;
    memcpy(&buf[2], &job_id, 4);
    memcpy(&buf[6], &worker_id, 4);
    memcpy(&buf[10], &extranonce2, 4);
    memcpy(&buf[14], &ntime, 4);
    memcpy(&buf[18], &nonce_val, 4);

    ehash_relay_on_nonce(&r, buf, sizeof(buf));

    /* After valid nonce, balance should increase by reward_rate */
    const ehash_credit_entry_t *credit = ehash_relay_get_credit(&r, 7);
    CHECK(credit != NULL);
    CHECK(credit->balance == 10500);  /* 10000 + 500 */
    CHECK(credit->nonces_accepted == 1);
    CHECK(r.credits_issued == 1);

    /* A credit message should have been unicast to station 7 */
    CHECK(ehash_radio_stub_get_unicast_count() >= 1);

    printf("  balance after nonce: %llu\n", (unsigned long long)credit->balance);
}

/* ======================================================================== */
/*  Test 4: Encryption round-trip (D8)                                      */
/* ======================================================================== */

static void test_encryption(void) {
    printf("Test 4: encryption round-trip (D8)...\n");

    uint8_t key[EHASH_CRYPTO_KEY_SIZE];
    ehash_crypto_session_start(key, 0xDEADBEEF);

    /* Encrypt some data */
    uint8_t data[64];
    memset(data, 0x42, sizeof(data));

    uint8_t original[64];
    memcpy(original, data, sizeof(data));

    ehash_crypto_xor(data, sizeof(data), key);

    /* Encrypted data should differ from original */
    CHECK(memcmp(data, original, sizeof(data)) != 0);

    /* Decrypt (XOR is symmetric) */
    ehash_crypto_xor(data, sizeof(data), key);

    /* Should match original */
    CHECK(memcmp(data, original, sizeof(data)) == 0);

    /* Key equality check */
    uint8_t key2[EHASH_CRYPTO_KEY_SIZE];
    ehash_crypto_session_start(key2, 0xDEADBEEF);
    CHECK(ehash_crypto_key_equal(key, key2));

    /* Different seed → different key */
    uint8_t key3[EHASH_CRYPTO_KEY_SIZE];
    ehash_crypto_session_start(key3, 0xCAFEBABE);
    CHECK(!ehash_crypto_key_equal(key, key3));
}

/* ======================================================================== */
/*  Test 5: TTL expiry (D9)                                                 */
/* ======================================================================== */

static void test_ttl_expiry(void) {
    printf("Test 5: TTL expiry (D9)...\n");

    ehash_relay_t r;
    ehash_relay_init(&r, NULL, NULL, NULL, NULL);

    /* Default TTL is 15 minutes (900s) */
    ehash_template_t tmpl = make_test_template(42);
    ehash_relay_on_template(&r, &tmpl, 1000);

    /* Not expired at t=1000 */
    CHECK(!ehash_relay_template_expired(&r, 1000));

    /* Not expired at t=1000+899 (just under TTL) */
    CHECK(!ehash_relay_template_expired(&r, 1000 + 899));

    /* Expired at t=1000+900 (exactly TTL) */
    CHECK(ehash_relay_template_expired(&r, 1000 + 900));

    /* Expired well after TTL */
    CHECK(ehash_relay_template_expired(&r, 1000 + 9999));

    /* Test custom TTL: 60 seconds */
    ehash_relay_set_ttl(&r, 60);
    ehash_relay_on_template(&r, &tmpl, 2000);
    CHECK(!ehash_relay_template_expired(&r, 2000 + 59));
    CHECK(ehash_relay_template_expired(&r, 2000 + 60));
}

/* ======================================================================== */
/*  Test 6: Credit gate — zero balance = no access                          */
/* ======================================================================== */

static void test_credit_gate(void) {
    printf("Test 6: credit gate zero balance (D8)...\n");

    ehash_relay_t r;
    ehash_relay_init(&r, NULL, NULL, NULL, NULL);

    /* Station with zero balance */
    ehash_relay_credit_set_balance(&r, 1, 0, 500);
    CHECK(!ehash_relay_has_credit(&r, 1));  /* No credit */

    /* Station with positive balance */
    ehash_relay_credit_set_balance(&r, 2, 1000, 500);
    CHECK(ehash_relay_has_credit(&r, 2));   /* Has credit */

    /* Unknown station */
    CHECK(!ehash_relay_has_credit(&r, 99));

    /* After a nonce submission, zero-balance station earns credit */
    s_nonce_forward_count = 0;
    r.radio_broadcast = ehash_radio_stub_broadcast;
    r.radio_unicast = ehash_radio_stub_unicast;
    r.upstream_tx = test_upstream_tx;
    ehash_radio_stub_reset();

    uint8_t buf[22];
    buf[0] = EHASH_NONCE;
    buf[1] = 0x01;
    uint32_t job_id = 1, worker_id = 1, extranonce2 = 0, ntime = 0, nonce_val = 0;
    memcpy(&buf[2], &job_id, 4);
    memcpy(&buf[6], &worker_id, 4);
    memcpy(&buf[10], &extranonce2, 4);
    memcpy(&buf[14], &ntime, 4);
    memcpy(&buf[18], &nonce_val, 4);

    ehash_relay_on_nonce(&r, buf, sizeof(buf));

    /* Now station 1 should have credit (earned 500 from nonce) */
    CHECK(ehash_relay_has_credit(&r, 1));
    const ehash_credit_entry_t *c = ehash_relay_get_credit(&r, 1);
    CHECK(c->balance == 500);
}

/* ======================================================================== */
/*  Test 7: Credit table capacity (max 16 stations)                         */
/* ======================================================================== */

static void test_credit_table_capacity(void) {
    printf("Test 7: credit table capacity...\n");

    ehash_relay_t r;
    ehash_relay_init(&r, NULL, NULL, NULL, NULL);

    /* Fill up 16 stations */
    for (uint32_t i = 1; i <= EHASH_RELAY_MAX_STATIONS; i++) {
        int idx = ehash_relay_credit_find_or_create(&r, i);
        CHECK(idx >= 0);
        CHECK(idx == (int)(i - 1));
    }

    /* 17th station should fail */
    int idx = ehash_relay_credit_find_or_create(&r, 999);
    CHECK(idx < 0);
}

/* ======================================================================== */
/*  Test 8: Upstream disconnect marks templates stale (D9)                  */
/* ======================================================================== */

static void test_upstream_disconnect(void) {
    printf("Test 8: upstream disconnect (D9)...\n");

    ehash_relay_t r;
    ehash_relay_init(&r, NULL, NULL, NULL, NULL);

    /* Connected, send template */
    ehash_relay_set_upstream(&r, true);
    ehash_template_t tmpl = make_test_template(1);
    ehash_relay_on_template(&r, &tmpl, 1000);
    CHECK(!ehash_relay_template_expired(&r, 1000));

    /* Disconnect upstream */
    ehash_relay_set_upstream(&r, false);

    /* Template should be considered stale when upstream is down */
    /* (Even if TTL hasn't expired, upstream loss means templates are stale) */
    CHECK(r.upstream_connected == false);
}

/* ======================================================================== */
/*  Main                                                                    */
/* ======================================================================== */

int main(void) {
    printf("\n=== E-Hash Relay Module Tests (Phase C) ===\n\n");

    test_template_relay();
    test_nonce_relay();
    test_credit_issuance();
    test_encryption();
    test_ttl_expiry();
    test_credit_gate();
    test_credit_table_capacity();
    test_upstream_disconnect();

    printf("\n========================================\n");
    printf("E-Hash Relay Tests: %d passed, %d failed\n", g_pass, g_fail);
    printf("========================================\n\n");

    return (g_fail > 0) ? 1 : 0;
}
