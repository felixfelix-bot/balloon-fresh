/*
 * test_tollgate_payment_proto.c — host unit tests for tollgate payment
 * protocol encode/decode (ADR-002), tracker firmware standalone version.
 *
 * Tests the wire-level message format:
 *   [hdr(8 bytes, packed)] [payload(N bytes)]
 *
 * Build & run (host, no hardware):
 *   gcc -Wall -Wextra -O2 -I main \
 *       -o /tmp/test_tollgate_proto \
 *       main/test/test_tollgate_payment_proto.c \
 *       main/tollgate_payment_proto.c && /tmp/test_tollgate_proto
 *
 * Pass condition: all tests print PASS, exit code 0.
 */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "relay_types.h"          /* RELAY_PACKET_MAX_SIZE (relay frame budget) */
#include "tollgate_payment_proto.h"

/* ---- Minimal test framework (self-contained, no external dep) ---- */

static int g_pass = 0;
static int g_fail = 0;

#define ASSERT(cond, msg) do { \
    if (cond) { printf("  PASS: %s\n", msg); g_pass++; } \
    else { printf("  FAIL: %s (at %s:%d)\n", msg, __FILE__, __LINE__); g_fail++; } \
} while (0)

#define ASSERT_EQ_INT(exp, act, msg) do { \
    int _e = (exp), _a = (act); \
    if (_e == _a) { printf("  PASS: %s (got %d)\n", msg, _a); g_pass++; } \
    else { printf("  FAIL: %s (expected %d, got %d) at %s:%d\n", msg, _e, _a, __FILE__, __LINE__); g_fail++; } \
} while (0)

#define ASSERT_MEM_EQ(exp, act, len, msg) do { \
    const void *_e = (exp), *_a = (act); size_t _l = (len); \
    if (_e && _a && memcmp(_e, _a, _l) == 0) { printf("  PASS: %s (%zu bytes match)\n", msg, _l); g_pass++; } \
    else { printf("  FAIL: %s (%zu bytes mismatch) at %s:%d\n", msg, _l, __FILE__, __LINE__); g_fail++; } \
} while (0)

/* ---- Helpers ---- */

static void check_hdr_fields(const tollgate_msg_hdr_t *hdr,
                              uint8_t version, uint8_t type,
                              uint16_t seq, uint16_t payload_len,
                              uint16_t reserved)
{
    ASSERT_EQ_INT(version, hdr->version, "hdr.version");
    ASSERT_EQ_INT(type, hdr->type, "hdr.type");
    ASSERT_EQ_INT((int)seq, (int)hdr->seq, "hdr.seq");
    ASSERT_EQ_INT((int)payload_len, (int)hdr->payload_len, "hdr.payload_len");
    ASSERT_EQ_INT((int)reserved, (int)hdr->reserved, "hdr.reserved");
}

/* ---- Tests ---- */

/* 1. Struct packing — header must be exactly 8 bytes, no padding */
static void test_hdr_packed_size(void)
{
    printf("\n--- test_hdr_packed_size ---\n");
    ASSERT_EQ_INT(8, (int)sizeof(tollgate_msg_hdr_t),
                  "sizeof(tollgate_msg_hdr_t) == 8");

    tollgate_msg_hdr_t hdr;
    ASSERT_EQ_INT(0, (int)((uint8_t *)&hdr.version     - (uint8_t *)&hdr), "offset version == 0");
    ASSERT_EQ_INT(1, (int)((uint8_t *)&hdr.type        - (uint8_t *)&hdr), "offset type == 1");
    ASSERT_EQ_INT(2, (int)((uint8_t *)&hdr.seq         - (uint8_t *)&hdr), "offset seq == 2");
    ASSERT_EQ_INT(4, (int)((uint8_t *)&hdr.payload_len - (uint8_t *)&hdr), "offset payload_len == 4");
    ASSERT_EQ_INT(6, (int)((uint8_t *)&hdr.reserved    - (uint8_t *)&hdr), "offset reserved == 6");
}

/* 2. Encode — basic PAY message with JSON payload */
static void test_encode_basic(void)
{
    printf("\n--- test_encode_basic ---\n");
    const char *json = "{\"token\":\"cashuAxyz\"}";
    uint16_t json_len = (uint16_t)strlen(json);
    uint8_t buf[256];

    int ret = tollgate_proto_encode(buf, sizeof(buf), TG_MSG_PAY, 42, json, json_len);

    /* Total = header(8) + payload(20) = 28 */
    ASSERT_EQ_INT((int)(sizeof(tollgate_msg_hdr_t) + json_len), ret,
                  "encode returns hdr+payload size");

    const tollgate_msg_hdr_t *hdr = (const tollgate_msg_hdr_t *)buf;
    check_hdr_fields(hdr, TOLLGATE_PROTO_VERSION, TG_MSG_PAY, 42, json_len, 0);

    ASSERT_MEM_EQ(json, buf + sizeof(tollgate_msg_hdr_t), json_len,
                  "payload bytes match input");
}

/* 3. Encode — empty payload */
static void test_encode_empty(void)
{
    printf("\n--- test_encode_empty ---\n");
    uint8_t buf[64];

    int ret = tollgate_proto_encode(buf, sizeof(buf), TG_MSG_STATUS, 7, NULL, 0);

    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), ret,
                  "empty payload → total == sizeof(hdr)");

    const tollgate_msg_hdr_t *hdr = (const tollgate_msg_hdr_t *)buf;
    check_hdr_fields(hdr, TOLLGATE_PROTO_VERSION, TG_MSG_STATUS, 7, 0, 0);
}

/* 4. Encode — buffer overflow protection */
static void test_encode_overflow(void)
{
    printf("\n--- test_encode_overflow ---\n");
    const char *json = "{\"token\":\"cashuAxyz\"}";
    uint16_t json_len = (uint16_t)strlen(json);
    uint8_t buf[10];  /* too small (need 28) */

    int ret = tollgate_proto_encode(buf, sizeof(buf), TG_MSG_PAY, 1, json, json_len);
    ASSERT_EQ_INT(-1, ret, "overflow → returns -1");

    /* Exactly enough: buf_len == hdr + payload should succeed */
    uint8_t exact[8 + 21];  /* hdr(8) + payload(21) = 29 */
    ret = tollgate_proto_encode(exact, sizeof(exact), TG_MSG_PAY, 1, json, json_len);
    ASSERT_EQ_INT(29, ret, "exact-fit buffer succeeds");

    /* One byte too small must fail */
    ret = tollgate_proto_encode(exact, sizeof(exact) - 1, TG_MSG_PAY, 1, json, json_len);
    ASSERT_EQ_INT(-1, ret, "one byte short → returns -1");

    /* NULL buffer must fail */
    ret = tollgate_proto_encode(NULL, 256, TG_MSG_PAY, 1, json, json_len);
    ASSERT_EQ_INT(-1, ret, "NULL buffer → returns -1");
}

/* 5. Decode — valid hand-crafted byte sequence */
static void test_decode_valid(void)
{
    printf("\n--- test_decode_valid ---\n");
    /* version=1, type=INFO(0x05), seq=100, payload_len=5, reserved=0, payload="hello" */
    static const uint8_t data[] = {
        0x01,
        0x05,
        0x64, 0x00,
        0x05, 0x00,
        0x00, 0x00,
        'h', 'e', 'l', 'l', 'o'
    };

    tollgate_msg_hdr_t hdr;
    const uint8_t *payload = NULL;

    int off = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);
    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), off,
                  "decode returns sizeof(hdr) offset");
    ASSERT(payload != NULL, "payload pointer is set");
    check_hdr_fields(&hdr, 1, TG_MSG_INFO, 100, 5, 0);

    ASSERT(payload == data + sizeof(tollgate_msg_hdr_t),
           "payload pointer == data + sizeof(hdr)");
    ASSERT_MEM_EQ("hello", payload, 5, "payload content matches \"hello\"");

    /* payload_out may be NULL */
    int off2 = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, NULL);
    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), off2,
                  "decode works with NULL payload pointer");
}

/* 6. Decode — too short */
static void test_decode_short(void)
{
    printf("\n--- test_decode_short ---\n");
    uint8_t data[7];
    memset(data, 0, sizeof(data));

    tollgate_msg_hdr_t hdr;
    const uint8_t *payload = NULL;

    int ret = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "len < sizeof(hdr) → returns -1");

    ret = tollgate_proto_decode(data, 0, &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "len == 0 → returns -1");

    ret = tollgate_proto_decode(NULL, 100, &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "NULL data → returns -1");
}

/* 7. Decode — wrong protocol version */
static void test_decode_bad_version(void)
{
    printf("\n--- test_decode_bad_version ---\n");
    static const uint8_t data[] = {
        0x02, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
    };

    tollgate_msg_hdr_t hdr;
    const uint8_t *payload = NULL;

    int ret = tollgate_proto_decode(data, sizeof(data), &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "wrong version → returns -1");

    uint8_t data0[8];
    memset(data0, 0, sizeof(data0));
    data0[1] = TG_MSG_PAY;
    ret = tollgate_proto_decode(data0, sizeof(data0), &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "version 0 → returns -1");

    data0[0] = 0xFF;
    ret = tollgate_proto_decode(data0, sizeof(data0), &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "version 255 → returns -1");
}

/* 8. Decode — truncated payload */
static void test_decode_truncated(void)
{
    printf("\n--- test_decode_truncated ---\n");
    uint8_t data[8 + 50];
    memset(data, 0, sizeof(data));

    tollgate_msg_hdr_t *raw = (tollgate_msg_hdr_t *)data;
    raw->version     = TOLLGATE_PROTO_VERSION;
    raw->type        = TG_MSG_PAY;
    raw->seq         = 1;
    raw->payload_len = 100;  /* claims 100 but only 50 available */
    raw->reserved    = 0;

    tollgate_msg_hdr_t hdr;
    const uint8_t *payload = NULL;

    int ret = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);
    ASSERT_EQ_INT(-1, ret, "payload_len > available → returns -1");

    /* Exact-fit succeeds */
    raw->payload_len = 50;
    ret = tollgate_proto_decode(data, (uint16_t)sizeof(data), &hdr, &payload);
    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), ret,
                  "payload_len == available → succeeds");

    /* One byte short of exact → fail */
    ret = tollgate_proto_decode(data, (uint16_t)sizeof(data) - 1, &hdr, &payload);
    ASSERT_EQ_INT(-1, ret,
                  "total 1 byte short → returns -1");
}

/* 9. Round-trip: encode → decode for all message types */
static void test_roundtrip(void)
{
    printf("\n--- test_roundtrip ---\n");
    struct {
        tollgate_msg_type_t type;
        uint16_t seq;
        const char *payload;
    } cases[] = {
        { TG_MSG_PAY,  1234, "{\"token\":\"cashuA123\"}" },
        { TG_MSG_ACK,  5678, "{\"session_id\":42,\"expires\":999}" },
        { TG_MSG_NACK, 9012, "{\"error\":-2,\"msg\":\"swap failed\"}" },
        { TG_MSG_INFO, 3456, "{\"price_sats\":21,\"step_ms\":60000}" },
    };

    for (size_t i = 0; i < sizeof(cases) / sizeof(cases[0]); i++) {
        uint16_t plen = (uint16_t)strlen(cases[i].payload);
        uint8_t buf[512];

        int enc = tollgate_proto_encode(buf, sizeof(buf),
                                         cases[i].type, cases[i].seq,
                                         cases[i].payload, plen);
        ASSERT(enc > 0, "encode succeeded");

        tollgate_msg_hdr_t hdr;
        const uint8_t *payload = NULL;
        int dec = tollgate_proto_decode(buf, (uint16_t)enc, &hdr, &payload);
        ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), dec, "decode offset");

        check_hdr_fields(&hdr, TOLLGATE_PROTO_VERSION,
                         (uint8_t)cases[i].type, cases[i].seq, plen, 0);

        ASSERT(payload != NULL, "payload pointer set");
        ASSERT_MEM_EQ(cases[i].payload, payload, plen, "round-trip payload matches");
    }
}

/* 10. ACK payload struct — packed size and field offsets */
static void test_ack_payload_struct(void)
{
    printf("\n--- test_ack_payload_struct ---\n");
    /* session_id(4) + expires_unix(4) + quota_bytes(4) + price_sats(2) = 14 bytes packed */
    ASSERT_EQ_INT(14, (int)sizeof(tollgate_ack_payload_t),
                  "sizeof(tollgate_ack_payload_t) == 14 (packed)");

    tollgate_ack_payload_t ack;
    memset(&ack, 0, sizeof(ack));
    ack.session_id   = 0xDEADBEEF;
    ack.expires_unix = 1700000000;
    ack.quota_bytes  = 0;
    ack.price_sats   = 21;

    /* Encode the ACK payload as the message payload and verify round-trip via memcpy */
    uint8_t buf[256];
    int ret = tollgate_proto_encode(buf, sizeof(buf), TG_MSG_ACK, 99,
                                     (const char *)&ack, sizeof(ack));
    ASSERT(ret > 0, "encode ACK with payload struct");

    tollgate_msg_hdr_t hdr;
    const uint8_t *payload = NULL;
    int dec = tollgate_proto_decode(buf, (uint16_t)ret, &hdr, &payload);
    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), dec, "decode ACK");

    /* Reinterpret payload as ACK struct */
    const tollgate_ack_payload_t *ack2 = (const tollgate_ack_payload_t *)payload;
    ASSERT_EQ_INT(0xDEADBEEF, (int)ack2->session_id, "ACK session_id round-trip");
    ASSERT_EQ_INT(21, (int)ack2->price_sats, "ACK price_sats round-trip");
}

/* 11. Sequence contract — u16 wrap (65535 → 0) and exact echo equality */
static void test_seq_contract(void)
{
    printf("\n--- test_seq_contract ---\n");

    ASSERT_EQ_INT(65536, (int)TOLLGATE_SEQ_MODULO, "seq modulo == 2^16");
    ASSERT_EQ_INT(1, (int)tollgate_seq_next(0), "tollgate_seq_next(0) == 1");
    ASSERT_EQ_INT(65535, (int)tollgate_seq_next(65534), "tollgate_seq_next(65534) == 65535");
    ASSERT_EQ_INT(0, (int)tollgate_seq_next(65535), "tollgate_seq_next(65535) wraps to 0");
    ASSERT_EQ_INT(1, (int)tollgate_seq_next(0), "counter keeps running after the wrap");

    ASSERT(tollgate_seq_equal(0, 0), "tollgate_seq_equal(0,0) == true");
    ASSERT(tollgate_seq_equal(65535, 65535), "tollgate_seq_equal(65535,65535) == true");
    ASSERT(!tollgate_seq_equal(0, 65535),
           "seq is an opaque echo token: 0 != 65535 (no modular comparison window)");
    ASSERT(!tollgate_seq_equal(65535, 0),
           "wrapped-forward case is NOT a match by design (no dedup in v1)");
    ASSERT(!tollgate_seq_equal(1, 2), "tollgate_seq_equal(1,2) == false");
}

/* 12. Relay payload budget — the 2048-byte token cannot cross the relay frame */
static void test_relay_payload_budget(void)
{
    printf("\n--- test_relay_payload_budget ---\n");

    /* TOLLGATE_MAX_PAYLOAD_RELAY = RELAY_PACKET_MAX_SIZE - 1 type tag - 8 hdr */
    ASSERT_EQ_INT(RELAY_PACKET_MAX_SIZE - 1 - (int)sizeof(tollgate_msg_hdr_t),
                  (int)TOLLGATE_MAX_PAYLOAD_RELAY,
                  "TOLLGATE_MAX_PAYLOAD_RELAY matches the relay frame budget");
    ASSERT_EQ_INT(503, (int)TOLLGATE_MAX_PAYLOAD_RELAY, "relay budget == 503 bytes");
    ASSERT(TOLLGATE_MAX_TOKEN_LEN > TOLLGATE_MAX_PAYLOAD_RELAY,
           "TOLLGATE_MAX_TOKEN_LEN (2048, mesh-stack capability) exceeds the tracker relay budget");

    uint8_t frame[RELAY_PACKET_MAX_SIZE];
    static char payload[TOLLGATE_MAX_TOKEN_LEN];
    memset(payload, 'a', sizeof(payload));

    /* Exactly at the relay budget: succeeds, frame is exactly full */
    int ret = tollgate_proto_encode_relay(frame, sizeof(frame), TG_MSG_PAY, 1,
                                           payload, TOLLGATE_MAX_PAYLOAD_RELAY);
    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t) + TOLLGATE_MAX_PAYLOAD_RELAY, ret,
                  "encode at the budget succeeds");

    tollgate_msg_hdr_t hdr;
    const uint8_t *pl = NULL;
    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t),
                  tollgate_proto_decode(frame + 1, (uint16_t)ret, &hdr, &pl),
                  "budget-sized message decodes");
    ASSERT_EQ_INT(TOLLGATE_MAX_PAYLOAD_RELAY, (int)hdr.payload_len,
                  "decoded payload_len == TOLLGATE_MAX_PAYLOAD_RELAY");

    /* One byte over the budget: rejected explicitly, not truncated */
    ret = tollgate_proto_encode_relay(frame, sizeof(frame), TG_MSG_PAY, 1,
                                       payload, TOLLGATE_MAX_PAYLOAD_RELAY + 1);
    ASSERT_EQ_INT(TG_ENC_ERR_TOO_LONG, ret, "budget+1 → TG_ENC_ERR_TOO_LONG");

    /* The full 2048-byte token the constant advertises has no home on the relay */
    ret = tollgate_proto_encode_relay(frame, sizeof(frame), TG_MSG_PAY, 1,
                                       payload, TOLLGATE_MAX_TOKEN_LEN);
    ASSERT_EQ_INT(TG_ENC_ERR_TOO_LONG, ret,
                  "2048-byte token → TG_ENC_ERR_TOO_LONG (explicit, not silent)");

    /* A frame smaller than the declared budget still reports the same error */
    uint8_t small_frame[64];
    ret = tollgate_proto_encode_relay(small_frame, sizeof(small_frame), TG_MSG_PAY, 1,
                                       payload, 100);
    ASSERT_EQ_INT(TG_ENC_ERR_TOO_LONG, ret,
                  "payload larger than the supplied frame → TG_ENC_ERR_TOO_LONG");

    /* Invalid arguments */
    ret = tollgate_proto_encode_relay(NULL, sizeof(frame), TG_MSG_PAY, 1, payload, 8);
    ASSERT_EQ_INT(-1, ret, "NULL frame → -1");
    ret = tollgate_proto_encode_relay(frame, (uint16_t)sizeof(tollgate_msg_hdr_t),
                                       TG_MSG_PAY, 1, payload, 8);
    ASSERT_EQ_INT(-1, ret, "frame too small for tag + header → -1");

    /* Protocol-level hard cap: > TOLLGATE_MAX_TOKEN_LEN is refused even with room */
    uint8_t big_frame[TOLLGATE_MAX_TOKEN_LEN + 64];
    ret = tollgate_proto_encode(big_frame, (uint16_t)sizeof(big_frame), TG_MSG_PAY, 1,
                                 payload, TOLLGATE_MAX_TOKEN_LEN);
    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t) + TOLLGATE_MAX_TOKEN_LEN, ret,
                  "protocol cap allows exactly TOLLGATE_MAX_TOKEN_LEN");
    ret = tollgate_proto_encode(big_frame, (uint16_t)sizeof(big_frame), TG_MSG_PAY, 1,
                                 payload, (uint16_t)(TOLLGATE_MAX_TOKEN_LEN + 1));
    ASSERT_EQ_INT(-1, ret, "protocol cap rejects > TOLLGATE_MAX_TOKEN_LEN");
}

/* ---- Main ---- */

int main(void)
{
    printf("=== test_tollgate_payment_proto (tracker standalone) ===");

    test_hdr_packed_size();
    test_encode_basic();
    test_encode_empty();
    test_encode_overflow();
    test_decode_valid();
    test_decode_short();
    test_decode_bad_version();
    test_decode_truncated();
    test_roundtrip();
    test_ack_payload_struct();
    test_seq_contract();
    test_relay_payload_budget();

    printf("\n=== Results: %d passed, %d failed ===\n", g_pass, g_fail);
    return g_fail > 0 ? 1 : 0;
}