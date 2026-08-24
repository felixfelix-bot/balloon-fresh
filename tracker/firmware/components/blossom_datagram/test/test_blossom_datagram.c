/*
 * test_blossom_datagram.c — Host-side tests for the blossom datagram adapter.
 *
 * Covers:
 *   1. Serialize/deserialize roundtrip (PUT with content_type + payload)
 *   2. PUT message creation + parse (no payload, content_type only)
 *   3. GET request -> RESPONSE cycle (load + send, end-to-end routing)
 *   4. SHA-256 integrity check (corrupted SHA detected)
 *   5. GET for missing blob produces ERROR
 *   6. Auth side-channel: PUT rejected without auth, accepted with
 *   7. Truncated / malformed messages rejected
 *   8. ERROR message routing to callback
 */
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include "blossom_datagram.h"

/* ── Mock backends ──────────────────────────────────────────────── */

/* Single-slot mock store. */
static uint8_t  g_stored_sha[BLOSSOM_SHA256_LEN];
static uint8_t  g_stored_data[512];
static size_t   g_stored_len;
static char     g_stored_ct[BLOSSOM_MAX_CONTENT_TYPE_LEN + 1];
static int      g_store_calls;

static blossom_dgram_result_t mock_store(
    const uint8_t *sha256,
    const uint8_t *data, size_t len,
    const char *content_type)
{
    memcpy(g_stored_sha, sha256, BLOSSOM_SHA256_LEN);
    if (len > sizeof(g_stored_data)) return BLOSSOM_DGRAM_ERR_TOO_LARGE;
    memcpy(g_stored_data, data, len);
    g_stored_len = len;
    g_stored_ct[0] = '\0';
    if (content_type) {
        strncpy(g_stored_ct, content_type, sizeof(g_stored_ct) - 1);
        g_stored_ct[sizeof(g_stored_ct) - 1] = '\0';
    }
    g_store_calls++;
    return BLOSSOM_DGRAM_OK;
}

static blossom_dgram_result_t mock_load(
    const uint8_t *sha256,
    uint8_t *out_data, size_t *inout_len,
    char *out_content_type, size_t ct_cap)
{
    if (g_stored_len == 0 ||
        memcmp(sha256, g_stored_sha, BLOSSOM_SHA256_LEN) != 0) {
        return BLOSSOM_DGRAM_ERR_NOT_FOUND;
    }
    if (*inout_len < g_stored_len) return BLOSSOM_DGRAM_ERR_TOO_LARGE;
    memcpy(out_data, g_stored_data, g_stored_len);
    *inout_len = g_stored_len;
    if (out_content_type && ct_cap > 0) {
        strncpy(out_content_type, g_stored_ct, ct_cap - 1);
        out_content_type[ct_cap - 1] = '\0';
    }
    return BLOSSOM_DGRAM_OK;
}

static int      g_auth_calls;
static bool     g_auth_should_pass;

static blossom_dgram_result_t mock_auth(
    const uint8_t *sha256,
    const uint8_t *event, size_t event_len)
{
    (void)sha256; (void)event; (void)event_len;
    g_auth_calls++;
    return g_auth_should_pass ? BLOSSOM_DGRAM_OK : BLOSSOM_DGRAM_ERR_AUTH;
}

/* Capture last sent buffer. */
static uint8_t  g_sent[1024];
static size_t   g_sent_len;
static int      g_send_calls;

static blossom_dgram_result_t mock_send(
    const uint8_t *data, size_t len)
{
    if (len > sizeof(g_sent)) return BLOSSOM_DGRAM_ERR_TOO_LARGE;
    memcpy(g_sent, data, len);
    g_sent_len = len;
    g_send_calls++;
    return BLOSSOM_DGRAM_OK;
}

static uint8_t  g_resp_sha[BLOSSOM_SHA256_LEN];
static uint8_t  g_resp_payload[512];
static size_t   g_resp_len;
static int      g_resp_calls;

static void mock_on_response(
    const uint8_t *sha256,
    const uint8_t *payload, size_t payload_len)
{
    memcpy(g_resp_sha, sha256, BLOSSOM_SHA256_LEN);
    if (payload_len > sizeof(g_resp_payload)) payload_len = sizeof(g_resp_payload);
    memcpy(g_resp_payload, payload, payload_len);
    g_resp_len = payload_len;
    g_resp_calls++;
}

static uint8_t  g_err_sha[BLOSSOM_SHA256_LEN];
static uint8_t  g_err_reason[128];
static size_t   g_err_len;
static int      g_err_calls;

static void mock_on_error(
    const uint8_t *sha256,
    const uint8_t *reason, size_t reason_len)
{
    memcpy(g_err_sha, sha256, BLOSSOM_SHA256_LEN);
    if (reason_len > sizeof(g_err_reason)) reason_len = sizeof(g_err_reason);
    memcpy(g_err_reason, reason, reason_len);
    g_err_len = reason_len;
    g_err_calls++;
}

/* ── Helpers ────────────────────────────────────────────────────── */

static void reset_mocks(void)
{
    g_store_calls = 0;
    g_stored_len = 0;
    g_auth_calls = 0;
    g_auth_should_pass = true;
    g_send_calls = 0;
    g_sent_len = 0;
    g_resp_calls = 0;
    g_resp_len = 0;
    g_err_calls = 0;
    g_err_len = 0;
}

static void make_test_sha(uint8_t *out, uint8_t seed)
{
    for (int i = 0; i < BLOSSOM_SHA256_LEN; i++) {
        out[i] = (uint8_t)(seed + i);
    }
}

/* ── Tests ──────────────────────────────────────────────────────── */

static void test_serialize_deserialize_roundtrip(void)
{
    uint8_t sha[BLOSSOM_SHA256_LEN];
    make_test_sha(sha, 0x10);

    uint8_t payload[100];
    for (int i = 0; i < 100; i++) payload[i] = (uint8_t)(i * 3 + 1);

    uint8_t buf[256];
    int n = blossom_dgram_serialize_put(buf, sizeof(buf), sha,
                                        "image/png", payload, 100);
    assert(n > 0);
    assert((size_t)n == BLOSSOM_DGRAM_HEADER_LEN + 9 + 100);

    blossom_dgram_msg_t msg;
    blossom_dgram_result_t r = blossom_dgram_parse(buf, (size_t)n, &msg);
    assert(r == BLOSSOM_DGRAM_OK);
    assert(msg.type == BLOSSOM_MSG_PUT);
    assert(memcmp(msg.sha256, sha, BLOSSOM_SHA256_LEN) == 0);
    assert(msg.content_type_len == 9);
    assert(strncmp(msg.content_type, "image/png", 9) == 0);
    assert(msg.payload_len == 100);
    assert(memcmp(msg.payload, payload, 100) == 0);
    printf("PASS (PUT %d bytes, ct=\"image/png\", 100B payload)\n", n);
}

static void test_put_no_payload_with_content_type(void)
{
    uint8_t sha[BLOSSOM_SHA256_LEN];
    make_test_sha(sha, 0x20);

    uint8_t buf[64];
    int n = blossom_dgram_serialize_put(buf, sizeof(buf), sha,
                                        "text/plain", NULL, 0);
    assert(n > 0);
    assert((size_t)n == BLOSSOM_DGRAM_HEADER_LEN + 10);

    blossom_dgram_msg_t msg;
    blossom_dgram_result_t r = blossom_dgram_parse(buf, (size_t)n, &msg);
    assert(r == BLOSSOM_DGRAM_OK);
    assert(msg.type == BLOSSOM_MSG_PUT);
    assert(memcmp(msg.sha256, sha, BLOSSOM_SHA256_LEN) == 0);
    assert(msg.content_type_len == 10);
    assert(strncmp(msg.content_type, "text/plain", 10) == 0);
    assert(msg.payload_len == 0);
    printf("PASS (PUT with content_type, no payload)\n");
}

static void test_put_null_content_type(void)
{
    uint8_t sha[BLOSSOM_SHA256_LEN];
    make_test_sha(sha, 0x21);

    uint8_t payload[4] = {1, 2, 3, 4};
    uint8_t buf[64];
    int n = blossom_dgram_serialize_put(buf, sizeof(buf), sha,
                                        NULL, payload, 4);
    assert(n > 0);
    assert((size_t)n == BLOSSOM_DGRAM_HEADER_LEN + 4);

    blossom_dgram_msg_t msg;
    assert(blossom_dgram_parse(buf, (size_t)n, &msg) == BLOSSOM_DGRAM_OK);
    assert(msg.content_type_len == 0);
    assert(msg.content_type == NULL);
    assert(msg.payload_len == 4);
    printf("PASS (NULL content_type -> len 0)\n");
}

static void test_get_request_response_cycle(void)
{
    reset_mocks();

    /* Configure adapter with mock backends. */
    blossom_dgram_config_t cfg = {
        .store       = mock_store,
        .load        = mock_load,
        .auth        = NULL,
        .send        = mock_send,
        .on_response = mock_on_response,
        .on_error    = mock_on_error,
    };
    blossom_datagram_init(&cfg);

    uint8_t sha[BLOSSOM_SHA256_LEN];
    make_test_sha(sha, 0x30);

    /* Seed storage via a PUT (no auth configured -> direct store). */
    uint8_t blob[64];
    for (int i = 0; i < 64; i++) blob[i] = (uint8_t)(0xA0 + i);
    uint8_t putbuf[256];
    int pn = blossom_dgram_serialize_put(putbuf, sizeof(putbuf), sha,
                                         "application/octet-stream",
                                         blob, 64);
    assert(pn > 0);
    assert(blossom_datagram_handle_message(putbuf, (size_t)pn) == BLOSSOM_DGRAM_OK);
    assert(g_store_calls == 1);
    assert(g_stored_len == 64);
    assert(memcmp(g_stored_data, blob, 64) == 0);

    /* Now send a GET for the same blob. */
    g_send_calls = 0;
    uint8_t getbuf[64];
    int gn = blossom_dgram_serialize_get(getbuf, sizeof(getbuf), sha);
    assert(gn == BLOSSOM_DGRAM_HEADER_LEN);
    assert(blossom_datagram_handle_message(getbuf, (size_t)gn) == BLOSSOM_DGRAM_OK);

    /* GET handler should have loaded the blob and sent a RESPONSE. */
    assert(g_send_calls == 1);
    assert(g_sent_len == (size_t)BLOSSOM_DGRAM_HEADER_LEN + 64);

    /* The sent RESPONSE should parse correctly. */
    blossom_dgram_msg_t resp;
    assert(blossom_dgram_parse(g_sent, g_sent_len, &resp) == BLOSSOM_DGRAM_OK);
    assert(resp.type == BLOSSOM_MSG_RESPONSE);
    assert(memcmp(resp.sha256, sha, BLOSSOM_SHA256_LEN) == 0);
    assert(resp.payload_len == 64);
    assert(memcmp(resp.payload, blob, 64) == 0);

    /* Feed the RESPONSE back through handle_message -> on_response. */
    assert(blossom_datagram_handle_message(g_sent, g_sent_len) == BLOSSOM_DGRAM_OK);
    assert(g_resp_calls == 1);
    assert(memcmp(g_resp_sha, sha, BLOSSOM_SHA256_LEN) == 0);
    assert(g_resp_len == 64);
    assert(memcmp(g_resp_payload, blob, 64) == 0);

    printf("PASS (PUT->store, GET->load+send RESPONSE, RESPONSE->callback)\n");
}

static void test_sha_integrity_check(void)
{
    uint8_t sha[BLOSSOM_SHA256_LEN];
    make_test_sha(sha, 0x40);
    uint8_t payload[16] = {0};

    uint8_t buf[128];
    int n = blossom_dgram_serialize_put(buf, sizeof(buf), sha,
                                        NULL, payload, 16);
    assert(n > 0);

    /* Corrupt a byte in the SHA-256 field. */
    buf[5] ^= 0xFF;

    blossom_dgram_msg_t msg;
    blossom_dgram_result_t r = blossom_dgram_parse(buf, (size_t)n, &msg);
    assert(r == BLOSSOM_DGRAM_OK); /* parse still OK structurally */

    /* The parsed SHA must differ from the original. */
    uint8_t diff = 0;
    for (int i = 0; i < BLOSSOM_SHA256_LEN; i++) {
        if (msg.sha256[i] != sha[i]) { diff = 1; break; }
    }
    assert(diff == 1);
    printf("PASS (corrupted SHA detected by comparison)\n");
}

static void test_get_missing_blob_sends_error(void)
{
    reset_mocks();
    blossom_dgram_config_t cfg = {
        .store = mock_store, .load = mock_load, .auth = NULL,
        .send = mock_send, .on_response = NULL, .on_error = mock_on_error,
    };
    blossom_datagram_init(&cfg);

    uint8_t sha[BLOSSOM_SHA256_LEN];
    make_test_sha(sha, 0x50);

    uint8_t getbuf[64];
    int gn = blossom_dgram_serialize_get(getbuf, sizeof(getbuf), sha);
    assert(gn > 0);

    blossom_dgram_result_t r =
        blossom_datagram_handle_message(getbuf, (size_t)gn);
    assert(r == BLOSSOM_DGRAM_ERR_NOT_FOUND);
    /* An ERROR should have been transmitted. */
    assert(g_send_calls == 1);
    blossom_dgram_msg_t emsg;
    assert(blossom_dgram_parse(g_sent, g_sent_len, &emsg) == BLOSSOM_DGRAM_OK);
    assert(emsg.type == BLOSSOM_MSG_ERROR);
    assert(memcmp(emsg.sha256, sha, BLOSSOM_SHA256_LEN) == 0);
    assert(emsg.payload_len > 0);
    printf("PASS (GET missing -> ERROR sent)\n");
}

static void test_auth_side_channel(void)
{
    reset_mocks();
    g_auth_should_pass = true;

    blossom_dgram_config_t cfg = {
        .store = mock_store, .load = NULL, .auth = mock_auth,
        .send = mock_send, .on_response = NULL, .on_error = NULL,
    };
    blossom_datagram_init(&cfg);

    uint8_t sha[BLOSSOM_SHA256_LEN];
    make_test_sha(sha, 0x60);
    uint8_t payload[8] = {1, 2, 3, 4, 5, 6, 7, 8};

    uint8_t putbuf[128];
    int pn = blossom_dgram_serialize_put(putbuf, sizeof(putbuf), sha,
                                         NULL, payload, 8);
    assert(pn > 0);

    /* PUT without pending auth -> rejected. */
    blossom_dgram_result_t r =
        blossom_datagram_handle_message(putbuf, (size_t)pn);
    assert(r == BLOSSOM_DGRAM_ERR_AUTH);
    assert(g_store_calls == 0);
    assert(g_auth_calls == 0);

    /* Set pending auth for the right SHA. */
    uint8_t event[] = "{\"kind\":24242}";
    assert(blossom_datagram_set_pending_auth(sha, event, sizeof(event) - 1)
           == BLOSSOM_DGRAM_OK);

    /* PUT now passes auth and stores. */
    r = blossom_datagram_handle_message(putbuf, (size_t)pn);
    assert(r == BLOSSOM_DGRAM_OK);
    assert(g_auth_calls == 1);
    assert(g_store_calls == 1);

    /* Pending auth is consumed — second PUT without re-auth fails. */
    r = blossom_datagram_handle_message(putbuf, (size_t)pn);
    assert(r == BLOSSOM_DGRAM_ERR_AUTH);
    assert(g_auth_calls == 1);
    assert(g_store_calls == 1);

    printf("PASS (auth rejected without event, accepted with, one-shot)\n");
}

static void test_auth_wrong_sha_rejected(void)
{
    reset_mocks();
    blossom_dgram_config_t cfg = {
        .store = mock_store, .load = NULL, .auth = mock_auth,
        .send = mock_send, .on_response = NULL, .on_error = NULL,
    };
    blossom_datagram_init(&cfg);

    uint8_t sha_a[BLOSSOM_SHA256_LEN];
    uint8_t sha_b[BLOSSOM_SHA256_LEN];
    make_test_sha(sha_a, 0x70);
    make_test_sha(sha_b, 0x71);

    uint8_t event[] = "auth";
    blossom_datagram_set_pending_auth(sha_a, event, sizeof(event) - 1);

    uint8_t putbuf[128];
    int pn = blossom_dgram_serialize_put(putbuf, sizeof(putbuf), sha_b,
                                         NULL, (const uint8_t *)"x", 1);
    assert(pn > 0);
    blossom_dgram_result_t r =
        blossom_datagram_handle_message(putbuf, (size_t)pn);
    assert(r == BLOSSOM_DGRAM_ERR_AUTH);
    assert(g_store_calls == 0);
    printf("PASS (auth for wrong SHA rejected)\n");
}

static void test_truncated_and_malformed(void)
{
    uint8_t sha[BLOSSOM_SHA256_LEN];
    make_test_sha(sha, 0x80);

    /* Too short to contain a header. */
    uint8_t tiny[10] = {BLOSSOM_MSG_GET};
    blossom_dgram_msg_t msg;
    assert(blossom_dgram_parse(tiny, sizeof(tiny), &msg)
           == BLOSSOM_DGRAM_ERR_TRUNCATED);

    /* Bad message type. */
    uint8_t buf[64];
    int n = blossom_dgram_serialize_get(buf, sizeof(buf), sha);
    assert(n > 0);
    buf[0] = 0x99;
    assert(blossom_dgram_parse(buf, (size_t)n, &msg)
           == BLOSSOM_DGRAM_ERR_FORMAT);

    /* content_type_len exceeds max. */
    buf[0] = BLOSSOM_MSG_PUT;
    buf[33] = (uint8_t)(BLOSSOM_MAX_CONTENT_TYPE_LEN + 1);
    assert(blossom_dgram_parse(buf, (size_t)n, &msg)
           == BLOSSOM_DGRAM_ERR_FORMAT);

    /* NULL / invalid params. */
    assert(blossom_dgram_parse(NULL, 10, &msg) == BLOSSOM_DGRAM_ERR_INVALID_PARAM);
    assert(blossom_dgram_serialize_put(NULL, 10, sha, NULL, NULL, 0)
           == BLOSSOM_DGRAM_ERR_INVALID_PARAM);

    printf("PASS (truncated, bad type, oversized ct_len, NULL params)\n");
}

static void test_error_routing(void)
{
    reset_mocks();
    blossom_dgram_config_t cfg = {
        .store = NULL, .load = NULL, .auth = NULL,
        .send = mock_send, .on_response = NULL, .on_error = mock_on_error,
    };
    blossom_datagram_init(&cfg);

    uint8_t sha[BLOSSOM_SHA256_LEN];
    make_test_sha(sha, 0x90);
    const uint8_t reason[] = "disk full";
    uint8_t buf[128];
    int n = blossom_dgram_serialize_error(buf, sizeof(buf), sha,
                                          reason, sizeof(reason) - 1);
    assert(n > 0);

    assert(blossom_datagram_handle_message(buf, (size_t)n) == BLOSSOM_DGRAM_OK);
    assert(g_err_calls == 1);
    assert(memcmp(g_err_sha, sha, BLOSSOM_SHA256_LEN) == 0);
    assert(g_err_len == sizeof(reason) - 1);
    assert(memcmp(g_err_reason, reason, g_err_len) == 0);
    printf("PASS (ERROR -> on_error callback)\n");
}

static void test_high_level_send_helpers(void)
{
    reset_mocks();
    blossom_dgram_config_t cfg = {
        .store = NULL, .load = NULL, .auth = NULL,
        .send = mock_send, .on_response = NULL, .on_error = NULL,
    };
    blossom_datagram_init(&cfg);

    uint8_t sha[BLOSSOM_SHA256_LEN];
    make_test_sha(sha, 0xA0);
    uint8_t payload[10];
    for (int i = 0; i < 10; i++) payload[i] = (uint8_t)i;

    /* put_blob serializes + sends. */
    g_send_calls = 0;
    assert(blossom_datagram_put_blob(sha, "text/plain", payload, 10)
           == BLOSSOM_DGRAM_OK);
    assert(g_send_calls == 1);
    blossom_dgram_msg_t msg;
    assert(blossom_dgram_parse(g_sent, g_sent_len, &msg) == BLOSSOM_DGRAM_OK);
    assert(msg.type == BLOSSOM_MSG_PUT);
    assert(msg.payload_len == 10);
    assert(memcmp(msg.payload, payload, 10) == 0);

    /* get_blob serializes + sends a GET. */
    g_send_calls = 0;
    assert(blossom_datagram_get_blob(sha) == BLOSSOM_DGRAM_OK);
    assert(g_send_calls == 1);
    assert(g_sent_len == (size_t)BLOSSOM_DGRAM_HEADER_LEN);
    assert(blossom_dgram_parse(g_sent, g_sent_len, &msg) == BLOSSOM_DGRAM_OK);
    assert(msg.type == BLOSSOM_MSG_GET);
    assert(msg.payload_len == 0);

    /* No send backend -> INVALID_PARAM. */
    blossom_dgram_config_t nocfg = {0};
    blossom_datagram_init(&nocfg);
    assert(blossom_datagram_put_blob(sha, NULL, payload, 10)
           == BLOSSOM_DGRAM_ERR_INVALID_PARAM);
    assert(blossom_datagram_get_blob(sha)
           == BLOSSOM_DGRAM_ERR_INVALID_PARAM);

    printf("PASS (put_blob/get_blob serialize+send, missing send rejected)\n");
}

/* ── Main ───────────────────────────────────────────────────────── */

int main(void)
{
    printf("\n=== Blossom Datagram Adapter Tests ===\n\n");

    printf("TEST 1: serialize/deserialize roundtrip... ");
    test_serialize_deserialize_roundtrip();

    printf("TEST 2: PUT creation + parse (no payload)... ");
    test_put_no_payload_with_content_type();

    printf("TEST 2b: PUT with NULL content_type... ");
    test_put_null_content_type();

    printf("TEST 3: GET request -> RESPONSE cycle... ");
    test_get_request_response_cycle();

    printf("TEST 4: SHA integrity check... ");
    test_sha_integrity_check();

    printf("TEST 5: GET missing blob -> ERROR... ");
    test_get_missing_blob_sends_error();

    printf("TEST 6: auth side-channel... ");
    test_auth_side_channel();

    printf("TEST 6b: auth wrong SHA rejected... ");
    test_auth_wrong_sha_rejected();

    printf("TEST 7: truncated/malformed rejected... ");
    test_truncated_and_malformed();

    printf("TEST 8: ERROR routing... ");
    test_error_routing();

    printf("TEST 9: high-level send helpers... ");
    test_high_level_send_helpers();

    printf("\n=== Results: 11/11 passed ===\n");
    return 0;
}
