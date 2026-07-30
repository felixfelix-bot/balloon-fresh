/*
 * test_payment_proto.c — host unit tests for tollgate payment protocol
 * encode/decode functions (ADR-002).
 *
 * Tests the wire-level message format:
 *   [hdr(8 bytes, packed)] [payload(N bytes, JSON)]
 *
 * Covers:
 *   - tollgate_proto_encode (basic, empty, overflow)
 *   - tollgate_proto_decode (valid, short, bad version, truncated payload)
 *   - Round-trip encode → decode for all message types
 *   - tollgate_proto_build_info_json (normal + NULL mint)
 *   - Struct packing / size invariant
 */
#include "test_framework.h"
#include "tollgate_payment_proto.h"
#include "tollgate_balloon.h"

#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

/*
 * Verify every field of a decoded header against expected values.
 */
static void check_hdr_fields(const tollgate_msg_hdr_t *hdr,
                              uint8_t version, uint8_t type,
                              uint16_t seq, uint16_t payload_len,
                              uint16_t reserved)
{
    ASSERT_EQ_INT(version,     hdr->version,     "hdr.version");
    ASSERT_EQ_INT(type,        hdr->type,        "hdr.type");
    ASSERT_EQ_INT((int)seq,    (int)hdr->seq,    "hdr.seq");
    ASSERT_EQ_INT((int)payload_len, (int)hdr->payload_len, "hdr.payload_len");
    ASSERT_EQ_INT((int)reserved, (int)hdr->reserved, "hdr.reserved");
}

/* ------------------------------------------------------------------ */
/* 1. Struct packing                                                   */
/* ------------------------------------------------------------------ */

static void test_msg_hdr_packed_size(void)
{
    printf("\n--- test_msg_hdr_packed_size ---\n");

    /*
     * tollgate_msg_hdr_t layout (packed):
     *   version     uint8_t   1
     *   type        uint8_t   1
     *   seq         uint16_t  2
     *   payload_len uint16_t  2
     *   reserved    uint16_t  2
     *   -------------------------
     *   total                 8 bytes
     */
    ASSERT_EQ_INT(8, (int)sizeof(tollgate_msg_hdr_t),
                  "sizeof(tollgate_msg_hdr_t) == 8");

    /* Field offsets must be contiguous (no compiler-inserted padding) */
    tollgate_msg_hdr_t hdr;
    ASSERT_EQ_INT(0, (int)((uint8_t *)&hdr.version     - (uint8_t *)&hdr), "offset version == 0");
    ASSERT_EQ_INT(1, (int)((uint8_t *)&hdr.type        - (uint8_t *)&hdr), "offset type == 1");
    ASSERT_EQ_INT(2, (int)((uint8_t *)&hdr.seq         - (uint8_t *)&hdr), "offset seq == 2");
    ASSERT_EQ_INT(4, (int)((uint8_t *)&hdr.payload_len - (uint8_t *)&hdr), "offset payload_len == 4");
    ASSERT_EQ_INT(6, (int)((uint8_t *)&hdr.reserved    - (uint8_t *)&hdr), "offset reserved == 6");
}

/* ------------------------------------------------------------------ */
/* 2. Encode — basic                                                   */
/* ------------------------------------------------------------------ */

static void test_proto_encode_basic(void)
{
    printf("\n--- test_proto_encode_basic ---\n");

    const char *json = "{\"token\":\"cashuAxyz\"}";
    uint16_t json_len = (uint16_t)strlen(json);   /* 20 */
    uint8_t buf[256];

    int ret = tollgate_proto_encode(buf, sizeof(buf), TG_MSG_PAY, 42,
                                     json, json_len);

    /* Total = header(8) + payload(20) = 28 */
    ASSERT_EQ_INT((int)(sizeof(tollgate_msg_hdr_t) + json_len), ret,
                  "encode returns hdr+payload size");

    const tollgate_msg_hdr_t *hdr = (const tollgate_msg_hdr_t *)buf;
    check_hdr_fields(hdr, TOLLGATE_PROTO_VERSION, TG_MSG_PAY, 42, json_len, 0);

    /* Payload bytes must match the original JSON */
    ASSERT_MEM_EQ(json, buf + sizeof(tollgate_msg_hdr_t), json_len,
                  "payload bytes match input JSON");
}

/* ------------------------------------------------------------------ */
/* 3. Encode — empty payload                                           */
/* ------------------------------------------------------------------ */

static void test_proto_encode_empty_payload(void)
{
    printf("\n--- test_proto_encode_empty_payload ---\n");

    uint8_t buf[64];

    int ret = tollgate_proto_encode(buf, sizeof(buf), TG_MSG_STATUS, 7,
                                     NULL, 0);

    /* With 0-length payload, total == header size */
    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), ret,
                  "empty payload → total == sizeof(hdr)");

    const tollgate_msg_hdr_t *hdr = (const tollgate_msg_hdr_t *)buf;
    check_hdr_fields(hdr, TOLLGATE_PROTO_VERSION, TG_MSG_STATUS, 7, 0, 0);
}

/* ------------------------------------------------------------------ */
/* 4. Encode — buffer overflow                                         */
/* ------------------------------------------------------------------ */

static void test_proto_encode_overflow(void)
{
    printf("\n--- test_proto_encode_overflow ---\n");

    const char *json = "{\"token\":\"cashuAxyz\"}";
    uint16_t json_len = (uint16_t)strlen(json);   /* 20 */
    uint8_t buf[10];                              /* too small (need 28) */

    int ret = tollgate_proto_encode(buf, sizeof(buf), TG_MSG_PAY, 1,
                                     json, json_len);
    ASSERT_EQ_INT(-1, ret, "overflow → returns -1");

    /* Exactly enough: buf_len == hdr + payload should succeed */
    uint8_t exact[8 + 21];
    ret = tollgate_proto_encode(exact, sizeof(exact), TG_MSG_PAY, 1,
                                 json, json_len);
    ASSERT_EQ_INT(29, ret, "exact-fit buffer succeeds");

    /* One byte too small must fail */
    ret = tollgate_proto_encode(exact, sizeof(exact) - 1, TG_MSG_PAY, 1,
                                 json, json_len);
    ASSERT_EQ_INT(-1, ret, "one byte short → returns -1");

    /* NULL buffer must fail */
    ret = tollgate_proto_encode(NULL, 256, TG_MSG_PAY, 1, json, json_len);
    ASSERT_EQ_INT(-1, ret, "NULL buffer → returns -1");
}

/* ------------------------------------------------------------------ */
/* 5. Decode — valid known-good byte sequence                          */
/* ------------------------------------------------------------------ */

static void test_proto_decode_valid(void)
{
    printf("\n--- test_proto_decode_valid ---\n");

    /*
     * Hand-crafted wire bytes (little-endian host):
     *   version=1, type=INFO(0x05), seq=100, payload_len=5, reserved=0
     *   payload = "hello"
     */
    static const uint8_t data[] = {
        0x01,               /* version  = 1            */
        0x05,               /* type     = TG_MSG_INFO  */
        0x64, 0x00,         /* seq      = 100  (LE)    */
        0x05, 0x00,         /* payload_len = 5 (LE)    */
        0x00, 0x00,         /* reserved = 0            */
        'h', 'e', 'l', 'l', 'o'
    };

    tollgate_msg_hdr_t hdr;
    const uint8_t *payload = NULL;

    int off = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);

    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), off,
                  "decode returns sizeof(hdr) offset");
    ASSERT(payload != NULL, "payload pointer is set");
    check_hdr_fields(&hdr, 1, TG_MSG_INFO, 100, 5, 0);

    /* Payload pointer must point just past the header */
    ASSERT(payload == data + sizeof(tollgate_msg_hdr_t),
           "payload pointer == data + sizeof(hdr)");
    ASSERT_MEM_EQ("hello", payload, 5, "payload content matches \"hello\"");

    /* payload_out may be NULL (caller doesn't want it) */
    int off2 = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, NULL);
    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), off2,
                  "decode works with NULL payload pointer");
}

/* ------------------------------------------------------------------ */
/* 6. Decode — too short (< header size)                               */
/* ------------------------------------------------------------------ */

static void test_proto_decode_short(void)
{
    printf("\n--- test_proto_decode_short ---\n");

    uint8_t data[7];   /* less than 8-byte header */
    memset(data, 0, sizeof(data));

    tollgate_msg_hdr_t hdr;
    const uint8_t *payload = NULL;

    int ret = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "len < sizeof(hdr) → returns -1");

    /* Zero-length input */
    ret = tollgate_proto_decode(data, 0, &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "len == 0 → returns -1");

    /* NULL data */
    ret = tollgate_proto_decode(NULL, 100, &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "NULL data → returns -1");
}

/* ------------------------------------------------------------------ */
/* 7. Decode — wrong protocol version                                  */
/* ------------------------------------------------------------------ */

static void test_proto_decode_bad_version(void)
{
    printf("\n--- test_proto_decode_bad_version ---\n");

    /* version = 2 (invalid, current is 1) */
    static const uint8_t data[] = {
        0x02,               /* version  = 2 (bad!)     */
        0x01,               /* type     = PAY          */
        0x00, 0x00,         /* seq      = 0            */
        0x00, 0x00,         /* payload_len = 0         */
        0x00, 0x00,         /* reserved = 0            */
    };

    tollgate_msg_hdr_t hdr;
    const uint8_t *payload = NULL;

    int ret = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "wrong version → returns -1");

    /* version = 0 should also fail */
    uint8_t data0[8];
    memset(data0, 0, sizeof(data0));
    data0[1] = TG_MSG_PAY;
    ret = tollgate_proto_decode(data0, sizeof(data0), &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "version 0 → returns -1");

    /* version = 255 should fail */
    data0[0] = 0xFF;
    ret = tollgate_proto_decode(data0, sizeof(data0), &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "version 255 → returns -1");
}

/* ------------------------------------------------------------------ */
/* 8. Decode — truncated payload                                       */
/* ------------------------------------------------------------------ */

static void test_proto_decode_truncated_payload(void)
{
    printf("\n--- test_proto_decode_truncated_payload ---\n");

    /*
     * Header claims payload_len = 100, but we only provide 50 bytes
     * after the header.  Total supplied = 8 + 50 = 58 bytes.
     */
    uint8_t data[8 + 50];
    memset(data, 0, sizeof(data));

    /* Manually set header: version=1, type=PAY, seq=1, payload_len=100 */
    tollgate_msg_hdr_t *raw = (tollgate_msg_hdr_t *)data;
    raw->version     = TOLLGATE_PROTO_VERSION;
    raw->type        = TG_MSG_PAY;
    raw->seq         = 1;
    raw->payload_len = 100;
    raw->reserved    = 0;

    tollgate_msg_hdr_t hdr;
    const uint8_t *payload = NULL;

    int ret = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);
    ASSERT_EQ_INT(-1, ret,
                  "payload_len > available bytes → returns -1");

    /* Exact-fit: payload_len == available → must succeed */
    raw->payload_len = 50;
    ret = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);
    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), ret,
                  "payload_len == available → succeeds");

    /* One byte short of exact → must fail */
    ret = tollgate_proto_decode(data, (uint16_t)sizeof(data) - 1, &hdr, &payload);
    ASSERT_EQ_INT(-1, ret,
                  "payload_len == avail but total 1 byte short → returns -1");
}

/* ------------------------------------------------------------------ */
/* 9. Round-trip: encode → decode for PAY / ACK / NACK / INFO          */
/* ------------------------------------------------------------------ */

static void test_proto_roundtrip(void)
{
    printf("\n--- test_proto_roundtrip ---\n");

    struct {
        tollgate_msg_type_t type;
        uint16_t            seq;
        const char         *json;
    } cases[] = {
        { TG_MSG_PAY,  1234, "{\"token\":\"cashuA123\"}" },
        { TG_MSG_ACK,  5678, "{\"session_id\":42,\"expires\":999}" },
        { TG_MSG_NACK, 9012, "{\"error\":-2,\"msg\":\"swap failed\"}" },
        { TG_MSG_INFO, 3456, "{\"price_sats\":21,\"step_ms\":60000}" },
    };

    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        uint16_t json_len = (uint16_t)strlen(cases[i].json);
        uint8_t buf[512];

        int enc = tollgate_proto_encode(buf, sizeof(buf),
                                         cases[i].type, cases[i].seq,
                                         cases[i].json, json_len);
        ASSERT(enc > 0, "encode succeeded");

        tollgate_msg_hdr_t hdr;
        const uint8_t *payload = NULL;
        int dec = tollgate_proto_decode(buf, (uint16_t)enc, &hdr, &payload);
        ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), dec, "decode offset");

        check_hdr_fields(&hdr, TOLLGATE_PROTO_VERSION,
                         (uint8_t)cases[i].type, cases[i].seq,
                         json_len, 0);

        ASSERT(payload != NULL, "payload pointer set");
        ASSERT_MEM_EQ(cases[i].json, payload, json_len,
                      "round-trip payload matches");
    }
}

/* ------------------------------------------------------------------ */
/* 10. Build INFO JSON — normal values                                 */
/* ------------------------------------------------------------------ */

static void test_proto_build_info_json(void)
{
    printf("\n--- test_proto_build_info_json ---\n");

    char *json = tollgate_proto_build_info_json(21, 60000,
                                                  "https://mint.example.com", 3);
    ASSERT(json != NULL, "build_info_json returns non-NULL");

    ASSERT(strstr(json, "\"price_sats\":21") != NULL,        "price_sats field");
    ASSERT(strstr(json, "\"step_ms\":60000") != NULL,        "step_ms field");
    ASSERT(strstr(json, "\"mint_url\":\"https://mint.example.com\"") != NULL,
           "mint_url field");
    ASSERT(strstr(json, "\"active_sessions\":3") != NULL,    "active_sessions field");
    ASSERT(strstr(json, "\"version\":1") != NULL,            "version field");

    /* Sanity: valid JSON starts with { and ends with } */
    ASSERT(json[0] == '{', "JSON starts with '{'");
    ASSERT(json[strlen(json) - 1] == '}', "JSON ends with '}'");

    free(json);
}

/* ------------------------------------------------------------------ */
/* 11. Build INFO JSON — NULL mint_url                                 */
/* ------------------------------------------------------------------ */

static void test_proto_build_info_json_null_mint(void)
{
    printf("\n--- test_proto_build_info_json_null_mint ---\n");

    char *json = tollgate_proto_build_info_json(5, 30000, NULL, 0);
    ASSERT(json != NULL, "build_info_json(NULL mint) returns non-NULL");

    ASSERT(strstr(json, "\"price_sats\":5") != NULL,     "price_sats field");
    ASSERT(strstr(json, "\"step_ms\":30000") != NULL,    "step_ms field");
    /* NULL mint_url should produce an empty string */
    ASSERT(strstr(json, "\"mint_url\":\"\"") != NULL,    "mint_url is empty string");
    ASSERT(strstr(json, "\"active_sessions\":0") != NULL, "active_sessions is 0");

    free(json);
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("=== test_payment_proto ===\n");

    test_msg_hdr_packed_size();
    test_proto_encode_basic();
    test_proto_encode_empty_payload();
    test_proto_encode_overflow();
    test_proto_decode_valid();
    test_proto_decode_short();
    test_proto_decode_bad_version();
    test_proto_decode_truncated_payload();
    test_proto_roundtrip();
    test_proto_build_info_json();
    test_proto_build_info_json_null_mint();

    TEST_SUMMARY();
}
