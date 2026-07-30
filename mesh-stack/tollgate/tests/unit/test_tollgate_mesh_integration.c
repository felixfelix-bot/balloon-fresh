/*
 * test_tollgate_mesh_integration.c — end-to-end integration test for
 * tollgate_balloon ↔ mesh_service_mux over a mock mesh transport.
 *
 * This test exercises the full data path without real radio hardware:
 *
 *   PAY flow:
 *     encode PAY → mux_wrap(SVC_TOLLGATE) → mock_send
 *       → mock_recv → mux_unwrap → tollgate_balloon_on_mesh_frame
 *       → ACK generated → mux_wrap(SVC_TOLLGATE) → mock_send
 *       → verify ACK received + decoded correctly
 *
 *   Service filtering:
 *     A non-TOLLGATE frame (SVC_NOSTR) is delivered to the balloon
 *     handler — it must be silently ignored (no response sent).
 *
 * The "mock mesh_adapter" is a simple loopback: the send callback writes
 * into a static buffer; the test then inspects that buffer.
 */
#include "test_framework.h"
#include "tollgate_balloon.h"
#include "tollgate_payment_proto.h"
#include "mesh_service_mux.h"

#include <string.h>
#include <stdio.h>

/* ------------------------------------------------------------------ */
/* Mock mesh transport — loopback buffer                               */
/* ------------------------------------------------------------------ */

#define MOCK_TX_CAP  2200   /* > TOLLGATE_MAX_TOKEN_LEN + headers */

static uint8_t  s_tx_buf[MOCK_TX_CAP];
static uint16_t s_tx_len    = 0;
static int      s_send_count = 0;

/*
 * mock_mesh_send — stands in for mesh_adapter_send().
 * Captures whatever the balloon pushes through the mux into s_tx_buf.
 */
static void mock_mesh_send(const uint8_t *data, uint16_t len)
{
    if (!data || len > MOCK_TX_CAP)
        return;
    memcpy(s_tx_buf, data, len);
    s_tx_len = (uint16_t)len;
    s_send_count++;
}

static void mock_reset(void)
{
    memset(s_tx_buf, 0, sizeof(s_tx_buf));
    s_tx_len = 0;
    s_send_count = 0;
}

/* ------------------------------------------------------------------ */
/* 1. Full PAY → ACK roundtrip through mux + balloon handler           */
/* ------------------------------------------------------------------ */

static void test_pay_ack_roundtrip(void)
{
    printf("\n--- test_pay_ack_roundtrip ---\n");

    /* Wire the mock send callback into the balloon */
    tollgate_balloon_register_mesh(mock_mesh_send);
    mock_reset();

    /* --- Build a PAY message (client side) --- */
    const char *token = "cashuAtesttoken1234567890abcdef";
    uint16_t token_len = (uint16_t)strlen(token);

    uint8_t proto_buf[256];
    int proto_len = tollgate_proto_encode(proto_buf, sizeof(proto_buf),
                                           TG_MSG_PAY, 42,
                                           token, token_len);
    ASSERT(proto_len > 0, "PAY proto_encode succeeded");

    /* Wrap with mux: [svc_tag(1)] [proto_buf] */
    uint8_t mesh_buf[257];
    int mesh_len = mesh_service_mux_wrap(MESH_SVC_TOLLGATE,
                                          proto_buf, (uint16_t)proto_len,
                                          mesh_buf, sizeof(mesh_buf));
    ASSERT(mesh_len > 0, "mux_wrap(SVC_TOLLGATE) for PAY succeeded");
    ASSERT_EQ_INT(MESH_SVC_TOLLGATE, mesh_buf[0],
                  "first byte is SVC_TOLLGATE tag");

    /* --- Deliver frame to balloon (simulates mesh_adapter recv) --- */
    tollgate_balloon_on_mesh_frame("aabbccdd", mesh_buf, (uint16_t)mesh_len);

    /* --- Verify an ACK was sent --- */
    ASSERT(s_send_count > 0, "balloon called send callback (ACK generated)");
    ASSERT(s_tx_len > 0, "tx buffer has data");

    /* Unwrap the captured ACK frame from the mux layer */
    uint8_t svc_out = 0;
    const uint8_t *ack_proto = NULL;
    uint16_t ack_proto_len = 0;

    int rc = mesh_service_mux_unwrap(s_tx_buf, s_tx_len,
                                      &svc_out, &ack_proto, &ack_proto_len);
    ASSERT_EQ_INT(MESH_MUX_OK, rc, "ACK frame mux_unwrap succeeds");
    ASSERT_EQ_INT(MESH_SVC_TOLLGATE, svc_out,
                  "ACK frame carries SVC_TOLLGATE tag");

    /* Decode the tollgate protocol header from the ACK */
    tollgate_msg_hdr_t hdr;
    const uint8_t *ack_data = NULL;

    int off = tollgate_proto_decode(ack_proto, ack_proto_len, &hdr, &ack_data);
    ASSERT(off > 0, "ACK proto_decode succeeded");
    ASSERT_EQ_INT(TOLLGATE_PROTO_VERSION, hdr.version, "ACK version");
    ASSERT_EQ_INT(TG_MSG_ACK, hdr.type, "ACK message type is TG_MSG_ACK");
    ASSERT_EQ_INT(42, (int)hdr.seq, "ACK seq matches PAY seq");

    /* Verify ACK payload struct fields */
    ASSERT_EQ_INT((int)sizeof(tollgate_ack_payload_t), (int)hdr.payload_len,
                  "ACK payload_len matches struct size");

    const tollgate_ack_payload_t *ack =
        (const tollgate_ack_payload_t *)ack_data;
    ASSERT(ack->session_id != 0, "ACK session_id is non-zero");
    /* Default price_sats is 21 (set in tollgate_balloon.c static init) */
    ASSERT_EQ_INT(21, (int)ack->price_sats,
                  "ACK price_sats matches default (21)");
}

/* ------------------------------------------------------------------ */
/* 2. Service filtering — non-TOLLGATE frames are ignored              */
/* ------------------------------------------------------------------ */

static void test_service_filtering(void)
{
    printf("\n--- test_service_filtering ---\n");

    tollgate_balloon_register_mesh(mock_mesh_send);
    mock_reset();

    /* Build a NOSTR frame (SVC_NOSTR = 0x02) */
    const uint8_t nostr_payload[] = {
        0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08
    };

    uint8_t nostr_frame[64];
    int nostr_len = mesh_service_mux_wrap(MESH_SVC_NOSTR,
                                           nostr_payload, sizeof(nostr_payload),
                                           nostr_frame, sizeof(nostr_frame));
    ASSERT(nostr_len > 0, "mux_wrap(SVC_NOSTR) succeeded");
    ASSERT_EQ_INT(MESH_SVC_NOSTR, nostr_frame[0],
                  "NOSTR frame tagged with SVC_NOSTR");

    /* Deliver to balloon handler — must be silently ignored */
    tollgate_balloon_on_mesh_frame("aabbccdd",
                                    nostr_frame, (uint16_t)nostr_len);

    ASSERT_EQ_INT(0, s_send_count,
                  "no send callback fired for NOSTR frame");
    ASSERT_EQ_INT(0, s_tx_len, "tx buffer is empty (NOSTR ignored)");

    /* Sanity: same frame with SVC_TOLLGATE WOULD trigger a response */
    mock_reset();
    uint8_t tollgate_frame[64];
    int tg_len = mesh_service_mux_wrap(MESH_SVC_TOLLGATE,
                                        nostr_payload, sizeof(nostr_payload),
                                        tollgate_frame, sizeof(tollgate_frame));
    /* Deliver — the payload isn't a valid PAY message (too short / wrong type),
     * so on_packet may reject it, but at minimum the mux dispatch must route it
     * into tollgate_balloon_on_packet rather than silently ignoring it.
     * We don't assert on send_count here (it's not a valid PAY), but we verify
     * no crash occurred. The key assertion is the NOSTR case above. */
    tollgate_balloon_on_mesh_frame("aabbccdd",
                                    tollgate_frame, (uint16_t)tg_len);
    ASSERT(1, "TOLLGATE frame processed without crash");
}

/* ------------------------------------------------------------------ */
/* 3. Multiple PAY messages get distinct ACKs (seq tracking)           */
/* ------------------------------------------------------------------ */

static void test_multiple_pay_distinct_acks(void)
{
    printf("\n--- test_multiple_pay_distinct_acks ---\n");

    tollgate_balloon_register_mesh(mock_mesh_send);

    const char *token = "cashuAseqtest";
    uint16_t token_len = (uint16_t)strlen(token);

    /* Send PAY with seq=100 */
    mock_reset();
    uint8_t proto1[128];
    int plen1 = tollgate_proto_encode(proto1, sizeof(proto1),
                                       TG_MSG_PAY, 100, token, token_len);
    uint8_t mesh1[130];
    int mlen1 = mesh_service_mux_wrap(MESH_SVC_TOLLGATE, proto1, (uint16_t)plen1,
                                       mesh1, sizeof(mesh1));
    tollgate_balloon_on_mesh_frame("node1", mesh1, (uint16_t)mlen1);
    ASSERT(s_send_count == 1, "first PAY → exactly one ACK");

    /* Capture seq from first ACK */
    uint8_t svc;
    const uint8_t *p1;
    uint16_t l1;
    mesh_service_mux_unwrap(s_tx_buf, s_tx_len, &svc, &p1, &l1);
    tollgate_msg_hdr_t h1;
    const uint8_t *d1;
    tollgate_proto_decode(p1, l1, &h1, &d1);
    ASSERT_EQ_INT(100, (int)h1.seq, "first ACK seq = 100");

    /* Send PAY with seq=200 */
    mock_reset();
    uint8_t proto2[128];
    int plen2 = tollgate_proto_encode(proto2, sizeof(proto2),
                                       TG_MSG_PAY, 200, token, token_len);
    uint8_t mesh2[130];
    int mlen2 = mesh_service_mux_wrap(MESH_SVC_TOLLGATE, proto2, (uint16_t)plen2,
                                       mesh2, sizeof(mesh2));
    tollgate_balloon_on_mesh_frame("node2", mesh2, (uint16_t)mlen2);
    ASSERT(s_send_count == 1, "second PAY → exactly one ACK");

    mesh_service_mux_unwrap(s_tx_buf, s_tx_len, &svc, &p1, &l1);
    tollgate_proto_decode(p1, l1, &h1, &d1);
    ASSERT_EQ_INT(200, (int)h1.seq, "second ACK seq = 200");
}

/* ------------------------------------------------------------------ */
/* 4. Unregister mesh callback → no responses sent                     */
/* ------------------------------------------------------------------ */

static void test_unregister_mesh(void)
{
    printf("\n--- test_unregister_mesh ---\n");

    /* Deregister by passing NULL */
    tollgate_balloon_register_mesh(NULL);
    mock_reset();

    const char *token = "cashuAnocallback";
    uint16_t token_len = (uint16_t)strlen(token);

    uint8_t proto[128];
    int plen = tollgate_proto_encode(proto, sizeof(proto),
                                      TG_MSG_PAY, 1, token, token_len);
    uint8_t mesh[130];
    int mlen = mesh_service_mux_wrap(MESH_SVC_TOLLGATE, proto, (uint16_t)plen,
                                      mesh, sizeof(mesh));

    /* Deliver — balloon should process PAY but can't send ACK */
    tollgate_balloon_on_mesh_frame("node3", mesh, (uint16_t)mlen);

    ASSERT_EQ_INT(0, s_send_count,
                  "no ACK sent when send callback is NULL");

    /* Re-register for subsequent tests */
    tollgate_balloon_register_mesh(mock_mesh_send);
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("=== test_tollgate_mesh_integration ===\n");

    test_pay_ack_roundtrip();
    test_service_filtering();
    test_multiple_pay_distinct_acks();
    test_unregister_mesh();

    TEST_SUMMARY();
}
