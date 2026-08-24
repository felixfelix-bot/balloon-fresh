/*
 * test_mesh_service_mux.c — host unit tests for the 1-byte service mux.
 *
 * Tests (TDD — written before implementation):
 *   1. Wrap/unwrap roundtrip for all 3 service IDs (TOLLGATE, NOSTR, BLOSSOM)
 *   2. Wrap with empty payload (0-length)
 *   3. Wrap overflow — output buffer too small
 *   4. Unwrap with too-short input (0 bytes)
 *   5. Unwrap NULL data
 *   6. Wrap NULL args
 *   7. Payload pointer aliasing (zero-copy verification)
 *   8. Service byte preserved through roundtrip
 */
#include "test_framework.h"
#include "mesh_service_mux.h"

#include <string.h>
#include <stdio.h>

/* ------------------------------------------------------------------ */
/* 1. Roundtrip for all 3 service IDs                                  */
/* ------------------------------------------------------------------ */

static void test_roundtrip_all_services(void)
{
    printf("\n--- test_roundtrip_all_services ---\n");

    uint8_t services[] = { MESH_SVC_TOLLGATE, MESH_SVC_NOSTR, MESH_SVC_BLOSSOM };

    const uint8_t payload[] = { 0xDE, 0xAD, 0xBE, 0xEF, 0x42 };

    for (int i = 0; i < 3; i++) {
        uint8_t wrapped[64];
        int wlen = mesh_service_mux_wrap(services[i], payload, sizeof(payload),
                                          wrapped, sizeof(wrapped));

        ASSERT_EQ_INT((int)(1 + sizeof(payload)), wlen,
                      "wrap returns 1 + payload_len");

        ASSERT_EQ_INT(services[i], wrapped[0],
                      "first byte is service ID");

        /* Unwrap */
        uint8_t svc_out = 0;
        const uint8_t *pl = NULL;
        uint16_t plen = 0;
        int rc = mesh_service_mux_unwrap(wrapped, (uint16_t)wlen,
                                          &svc_out, &pl, &plen);

        ASSERT_EQ_INT(MESH_MUX_OK, rc, "unwrap succeeds");
        ASSERT_EQ_INT(services[i], svc_out, "service byte preserved");
        ASSERT_EQ_INT((int)sizeof(payload), (int)plen, "payload length correct");
        ASSERT_MEM_EQ(payload, pl, sizeof(payload), "payload bytes match");
    }
}

/* ------------------------------------------------------------------ */
/* 2. Wrap with empty payload                                          */
/* ------------------------------------------------------------------ */

static void test_wrap_empty_payload(void)
{
    printf("\n--- test_wrap_empty_payload ---\n");

    uint8_t wrapped[16];
    int wlen = mesh_service_mux_wrap(MESH_SVC_TOLLGATE, NULL, 0,
                                      wrapped, sizeof(wrapped));

    /* With 0-length payload, wrapped = just the service byte */
    ASSERT_EQ_INT(1, wlen, "empty payload → wrap returns 1");

    ASSERT_EQ_INT(MESH_SVC_TOLLGATE, wrapped[0],
                  "wrapped byte is service ID");

    /* Unwrap should give 0-length payload */
    uint8_t svc_out = 0;
    const uint8_t *pl = (const uint8_t *)0xDEAD;
    uint16_t plen = 999;
    int rc = mesh_service_mux_unwrap(wrapped, (uint16_t)wlen,
                                      &svc_out, &pl, &plen);

    ASSERT_EQ_INT(MESH_MUX_OK, rc, "unwrap of 1-byte frame succeeds");
    ASSERT_EQ_INT(MESH_SVC_TOLLGATE, svc_out, "service byte correct");
    ASSERT_EQ_INT(0, (int)plen, "payload length is 0");
}

/* ------------------------------------------------------------------ */
/* 3. Wrap overflow — output buffer too small                          */
/* ------------------------------------------------------------------ */

static void test_wrap_overflow(void)
{
    printf("\n--- test_wrap_overflow ---\n");

    const uint8_t payload[] = { 0x01, 0x02, 0x03, 0x04, 0x05 };

    /* Buffer of exactly 6 bytes should fit (1 svc + 5 payload) */
    uint8_t exact[6];
    int ret = mesh_service_mux_wrap(MESH_SVC_NOSTR, payload, sizeof(payload),
                                     exact, sizeof(exact));
    ASSERT_EQ_INT(6, ret, "exact-fit buffer succeeds");

    /* Buffer of 5 bytes is too small (need 6) */
    uint8_t too_small[5];
    ret = mesh_service_mux_wrap(MESH_SVC_NOSTR, payload, sizeof(payload),
                                 too_small, sizeof(too_small));
    ASSERT_EQ_INT(MESH_MUX_ERR_TOO_LARGE, ret,
                  "one byte short → MESH_MUX_ERR_TOO_LARGE");

    /* Buffer of 1 byte with non-empty payload should fail */
    uint8_t tiny[1];
    ret = mesh_service_mux_wrap(MESH_SVC_NOSTR, payload, sizeof(payload),
                                 tiny, sizeof(tiny));
    ASSERT_EQ_INT(MESH_MUX_ERR_TOO_LARGE, ret,
                  "1-byte buffer with 5-byte payload → TOO_LARGE");

    /* Buffer of 0 capacity with empty payload → too small for even svc byte */
    ret = mesh_service_mux_wrap(MESH_SVC_NOSTR, NULL, 0,
                                 tiny, 0);
    ASSERT_EQ_INT(MESH_MUX_ERR_TOO_LARGE, ret,
                  "0-capacity buffer → TOO_LARGE");
}

/* ------------------------------------------------------------------ */
/* 4. Unwrap with too-short input (0 bytes)                            */
/* ------------------------------------------------------------------ */

static void test_unwrap_short_input(void)
{
    printf("\n--- test_unwrap_short_input ---\n");

    uint8_t svc_out = 0;
    const uint8_t *pl = NULL;
    uint16_t plen = 0;

    /* 0-length input */
    uint8_t dummy = 0x42;
    int rc = mesh_service_mux_unwrap(&dummy, 0, &svc_out, &pl, &plen);
    ASSERT_EQ_INT(MESH_MUX_ERR_FORMAT, rc,
                  "0-length input → MESH_MUX_ERR_FORMAT");

    /* 1-byte input: valid (just the service byte, empty payload) */
    uint8_t one[1] = { MESH_SVC_BLOSSOM };
    rc = mesh_service_mux_unwrap(one, 1, &svc_out, &pl, &plen);
    ASSERT_EQ_INT(MESH_MUX_OK, rc, "1-byte input succeeds");
    ASSERT_EQ_INT(MESH_SVC_BLOSSOM, svc_out, "service byte correct");
    ASSERT_EQ_INT(0, (int)plen, "payload length is 0");
}

/* ------------------------------------------------------------------ */
/* 5 & 6. NULL argument handling                                       */
/* ------------------------------------------------------------------ */

static void test_null_args(void)
{
    printf("\n--- test_null_args ---\n");

    const uint8_t payload[] = { 0xAA, 0xBB };
    uint8_t buf[16];

    /* Wrap with NULL output buffer */
    int ret = mesh_service_mux_wrap(MESH_SVC_TOLLGATE, payload, 2, NULL, 16);
    ASSERT_EQ_INT(MESH_MUX_ERR_INVALID, ret,
                  "wrap NULL out → MESH_MUX_ERR_INVALID");

    /* Wrap with NULL input but non-zero length */
    ret = mesh_service_mux_wrap(MESH_SVC_TOLLGATE, NULL, 5, buf, sizeof(buf));
    ASSERT_EQ_INT(MESH_MUX_ERR_INVALID, ret,
                  "wrap NULL in with len>0 → MESH_MUX_ERR_INVALID");

    /* Unwrap with NULL data */
    uint8_t svc;
    const uint8_t *pl;
    uint16_t plen;
    ret = mesh_service_mux_unwrap(NULL, 10, &svc, &pl, &plen);
    ASSERT_EQ_INT(MESH_MUX_ERR_INVALID, ret,
                  "unwrap NULL data → MESH_MUX_ERR_INVALID");

    /* Wrap with valid args but NULL in + 0 len should succeed */
    ret = mesh_service_mux_wrap(MESH_SVC_TOLLGATE, NULL, 0, buf, sizeof(buf));
    ASSERT_EQ_INT(1, ret, "wrap NULL in + 0 len → succeeds (empty payload)");
}

/* ------------------------------------------------------------------ */
/* 7. Zero-copy verification — payload pointer aliases input           */
/* ------------------------------------------------------------------ */

static void test_zero_copy_aliasing(void)
{
    printf("\n--- test_zero_copy_aliasing ---\n");

    uint8_t frame[] = { MESH_SVC_NOSTR, 0x10, 0x20, 0x30 };

    uint8_t svc;
    const uint8_t *pl;
    uint16_t plen;

    int rc = mesh_service_mux_unwrap(frame, sizeof(frame), &svc, &pl, &plen);
    ASSERT_EQ_INT(MESH_MUX_OK, rc, "unwrap succeeds");

    /* Payload pointer must point to frame + 1 (alias, not copy) */
    ASSERT(pl == frame + 1, "payload pointer aliases frame + 1");
    ASSERT_EQ_INT(3, (int)plen, "payload length is 3");

    /* Verify content through the alias */
    ASSERT_EQ_INT(0x10, pl[0], "payload[0] via alias");
    ASSERT_EQ_INT(0x20, pl[1], "payload[1] via alias");
    ASSERT_EQ_INT(0x30, pl[2], "payload[2] via alias");
}

/* ------------------------------------------------------------------ */
/* 8. Optional NULL output params in unwrap                            */
/* ------------------------------------------------------------------ */

static void test_unwrap_optional_nulls(void)
{
    printf("\n--- test_unwrap_optional_nulls ---\n");

    uint8_t frame[] = { MESH_SVC_BLOSSOM, 0xFF };

    /* Caller may pass NULL for svc_out */
    const uint8_t *pl;
    uint16_t plen;
    int rc = mesh_service_mux_unwrap(frame, sizeof(frame), NULL, &pl, &plen);
    ASSERT_EQ_INT(MESH_MUX_OK, rc, "unwrap with NULL svc_out succeeds");
    ASSERT_EQ_INT(1, (int)plen, "payload length correct");

    /* Caller may pass NULL for payload */
    uint8_t svc;
    rc = mesh_service_mux_unwrap(frame, sizeof(frame), &svc, NULL, NULL);
    ASSERT_EQ_INT(MESH_MUX_OK, rc, "unwrap with NULL payload/plen succeeds");
    ASSERT_EQ_INT(MESH_SVC_BLOSSOM, svc, "service byte correct");
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("=== test_mesh_service_mux ===\n");

    test_roundtrip_all_services();
    test_wrap_empty_payload();
    test_wrap_overflow();
    test_unwrap_short_input();
    test_null_args();
    test_zero_copy_aliasing();
    test_unwrap_optional_nulls();

    TEST_SUMMARY();
}
