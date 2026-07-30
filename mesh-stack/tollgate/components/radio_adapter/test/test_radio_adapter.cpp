/*
 * test_radio_adapter.cpp — host unit test for radio_adapter service mux bridging.
 *
 * Tests the mesh_service_mux wrap/unwrap logic that radio_adapter uses,
 * without needing real LR2021 hardware. Verifies:
 *   1. Send path: payload → mux_wrap → correct service byte + payload
 *   2. Recv path: mux-wrapped frame → unwrap → correct payload extracted
 *   3. Service routing: TOLLGATE/NOSTR/BLOSSOM dispatched correctly
 *
 * Build: cd mesh-stack/tollgate/tests/unit && make
 * Run:   ./test_radio_adapter
 */

#include "mesh_service_mux.h"
#include <stdio.h>
#include <string.h>
#include <assert.h>

static int tests_run = 0;
static int tests_pass = 0;

#define TEST(name) \
    tests_run++; \
    printf("  test: %s ... ", name);

#define PASS() \
    tests_pass++; \
    printf("PASS\n");

#define FAIL(msg) \
    printf("FAIL: %s\n", msg); \
    return;

static void test_wrap_tollgate(void) {
    TEST("wrap TOLLGATE service");
    uint8_t payload[] = {0xDE, 0xAD, 0xBE, 0xEF};
    uint8_t out[32];
    int len = mesh_service_mux_wrap(MESH_SVC_TOLLGATE, payload, 4, out, sizeof(out));
    if (len != 5) { FAIL("expected 5 bytes, got different"); return; }
    if (out[0] != MESH_SVC_TOLLGATE) { FAIL("service byte mismatch"); return; }
    if (memcmp(out + 1, payload, 4) != 0) { FAIL("payload mismatch"); return; }
    PASS();
}

static void test_wrap_nostr(void) {
    TEST("wrap NOSTR service");
    uint8_t payload[] = "hello nostr";
    uint8_t out[32];
    int len = mesh_service_mux_wrap(MESH_SVC_NOSTR, payload, 11, out, sizeof(out));
    if (len != 12) { FAIL("expected 12 bytes"); return; }
    if (out[0] != MESH_SVC_NOSTR) { FAIL("service byte mismatch"); return; }
    PASS();
}

static void test_wrap_blossom(void) {
    TEST("wrap BLOSSOM service");
    uint8_t payload[] = {0x01, 0x02};
    uint8_t out[32];
    int len = mesh_service_mux_wrap(MESH_SVC_BLOSSOM, payload, 2, out, sizeof(out));
    if (len != 3) { FAIL("expected 3 bytes"); return; }
    if (out[0] != MESH_SVC_BLOSSOM) { FAIL("service byte mismatch"); return; }
    PASS();
}

static void test_wrap_overflow(void) {
    TEST("wrap overflow detection");
    uint8_t payload[] = {0x01, 0x02, 0x03, 0x04};
    uint8_t out[3];  // too small for 1 + 4
    int len = mesh_service_mux_wrap(MESH_SVC_TOLLGATE, payload, 4, out, sizeof(out));
    if (len != MESH_MUX_ERR_TOO_LARGE) { FAIL("expected TOO_LARGE error"); return; }
    PASS();
}

static void test_unwrap_tollgate(void) {
    TEST("unwrap TOLLGATE service");
    uint8_t frame[] = {MESH_SVC_TOLLGATE, 0xAA, 0xBB, 0xCC};
    uint8_t svc = 0;
    const uint8_t *payload = nullptr;
    uint16_t plen = 0;
    int rc = mesh_service_mux_unwrap(frame, 4, &svc, &payload, &plen);
    if (rc != MESH_MUX_OK) { FAIL("unwrap failed"); return; }
    if (svc != MESH_SVC_TOLLGATE) { FAIL("wrong service"); return; }
    if (plen != 3) { FAIL("wrong payload len"); return; }
    if (payload[0] != 0xAA) { FAIL("wrong payload"); return; }
    PASS();
}

static void test_unwrap_routing(void) {
    TEST("service routing dispatch");
    // Simulate three frames for three services
    uint8_t tg_frame[] = {MESH_SVC_TOLLGATE, 0x01};
    uint8_t ns_frame[] = {MESH_SVC_NOSTR, 0x02};
    uint8_t bl_frame[] = {MESH_SVC_BLOSSOM, 0x03};

    uint8_t svc;
    const uint8_t *p;
    uint16_t plen;

    mesh_service_mux_unwrap(tg_frame, 2, &svc, &p, &plen);
    if (svc != MESH_SVC_TOLLGATE) { FAIL("TOLLGATE route failed"); return; }

    mesh_service_mux_unwrap(ns_frame, 2, &svc, &p, &plen);
    if (svc != MESH_SVC_NOSTR) { FAIL("NOSTR route failed"); return; }

    mesh_service_mux_unwrap(bl_frame, 2, &svc, &p, &plen);
    if (svc != MESH_SVC_BLOSSOM) { FAIL("BLOSSOM route failed"); return; }

    PASS();
}

static void test_roundtrip(void) {
    TEST("wrap → unwrap roundtrip");
    uint8_t original[] = {0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77};
    uint8_t wire[32];
    int wlen = mesh_service_mux_wrap(MESH_SVC_TOLLGATE, original, 8, wire, sizeof(wire));
    if (wlen < 0) { FAIL("wrap failed"); return; }

    uint8_t svc;
    const uint8_t *payload;
    uint16_t plen;
    int rc = mesh_service_mux_unwrap(wire, (uint16_t)wlen, &svc, &payload, &plen);
    if (rc != MESH_MUX_OK) { FAIL("unwrap failed"); return; }
    if (svc != MESH_SVC_TOLLGATE) { FAIL("service mismatch"); return; }
    if (plen != 8) { FAIL("payload length mismatch"); return; }
    if (memcmp(payload, original, 8) != 0) { FAIL("payload content mismatch"); return; }
    PASS();
}

static void test_unwrap_truncated(void) {
    TEST("unwrap truncated frame (0 bytes)");
    int rc = mesh_service_mux_unwrap((const uint8_t *)"", 0, nullptr, nullptr, nullptr);
    if (rc != MESH_MUX_ERR_FORMAT) { FAIL("expected FORMAT error"); return; }
    PASS();
}

int main(void) {
    printf("=== radio_adapter service mux tests ===\n");

    test_wrap_tollgate();
    test_wrap_nostr();
    test_wrap_blossom();
    test_wrap_overflow();
    test_unwrap_tollgate();
    test_unwrap_routing();
    test_roundtrip();
    test_unwrap_truncated();

    printf("\n%d/%d tests passed\n", tests_pass, tests_run);
    return tests_pass == tests_run ? 0 : 1;
}
