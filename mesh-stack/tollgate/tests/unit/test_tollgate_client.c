/*
 * test_tollgate_client.c — host unit tests for TollGate client state machine
 *
 * Tests the client-side payment protocol state machine (ADR-002):
 *   - IDLE → QUERYING → IDLE (query/INFO flow)
 *   - IDLE → PAYING → ACTIVE (pay/ACK flow)
 *   - IDLE → PAYING → ERROR (pay/NACK flow)
 *   - ACTIVE → EXPIRED (session timeout via tick)
 *   - EXPIRED → PAYING (auto-renew via tick)
 *   - Retry logic (3 attempts → ERROR)
 *   - Wire format verification (STATUS and PAY messages)
 *   - Input validation + state guard checks
 *
 * Uses a mock transport that captures sent bytes into a global buffer,
 * and the tollgate_client_mock_now_ms test hook for time control.
 */

#include "test_framework.h"
#include "tollgate_client.h"
#include "tollgate_payment_proto.h"

#include <string.h>
#include <stdio.h>
#include <stdlib.h>

/* ------------------------------------------------------------------ */
/* Mock transport — send_fn writes to a global buffer                  */
/* ------------------------------------------------------------------ */

static uint8_t  g_send_buf[4096];
static uint16_t g_send_len  = 0;
static int      g_send_count = 0;

static void mock_send(const uint8_t *data, uint16_t len)
{
    if (len > sizeof(g_send_buf))
        len = sizeof(g_send_buf);
    memcpy(g_send_buf, data, len);
    g_send_len   = len;
    g_send_count++;
}

static void reset_send_buf(void)
{
    g_send_len   = 0;
    g_send_count = 0;
}

/* ------------------------------------------------------------------ */
/* State-change tracking                                               */
/* ------------------------------------------------------------------ */

static tollgate_client_state_t g_last_from = TG_CLIENT_IDLE;
static tollgate_client_state_t g_last_to   = TG_CLIENT_IDLE;
static int g_state_change_count = 0;

static void on_state_change_cb(tollgate_client_state_t from,
                                tollgate_client_state_t to)
{
    g_last_from = from;
    g_last_to   = to;
    g_state_change_count++;
}

/* ------------------------------------------------------------------ */
/* Packet builders (mirror the balloon side's wire format)             */
/* ------------------------------------------------------------------ */

/* Build an INFO packet (JSON payload, like what the balloon sends) */
static uint16_t build_info_packet(uint8_t *buf, uint16_t buf_len,
                                    uint16_t price_sats, int32_t step_ms)
{
    char *json = tollgate_proto_build_info_json(
        price_sats, step_ms, "https://mint.test", 0);
    if (!json)
        return 0;

    uint16_t json_len = (uint16_t)strlen(json);
    int len = tollgate_proto_encode(buf, buf_len, TG_MSG_INFO, 1,
                                     json, json_len);
    free(json);
    return (len > 0) ? (uint16_t)len : 0;
}

/* Build an ACK packet (binary payload struct) */
static uint16_t build_ack_packet(uint8_t *buf, uint16_t buf_len,
                                   uint32_t session_id,
                                   uint32_t expires_unix,
                                   uint16_t price_sats)
{
    tollgate_ack_payload_t ack;
    memset(&ack, 0, sizeof(ack));
    ack.session_id   = session_id;
    ack.expires_unix = expires_unix;
    ack.quota_bytes  = 0;
    ack.price_sats   = price_sats;

    int len = tollgate_proto_encode(buf, buf_len, TG_MSG_ACK, 1,
                                     (const char *)&ack, sizeof(ack));
    return (len > 0) ? (uint16_t)len : 0;
}

/* Build a NACK packet (binary payload struct) */
static uint16_t build_nack_packet(uint8_t *buf, uint16_t buf_len)
{
    tollgate_nack_payload_t nack;
    memset(&nack, 0, sizeof(nack));
    nack.error_code = TG_ERR_SWAP_FAILED;
    strncpy(nack.message, "swap failed", sizeof(nack.message) - 1);

    int len = tollgate_proto_encode(buf, buf_len, TG_MSG_NACK, 1,
                                     (const char *)&nack, sizeof(nack));
    return (len > 0) ? (uint16_t)len : 0;
}

/* ================================================================== */
/* Tests                                                               */
/* ================================================================== */

/* 1. Init validation — NULL args rejected, valid init → IDLE */
static void test_init_validation(void)
{
    printf("\n--- test_init_validation ---\n");

    esp_err_t ret = tollgate_client_init(NULL, mock_send, NULL);
    ASSERT_EQ_INT(ESP_ERR_INVALID_ARG, ret, "NULL mint_url -> INVALID_ARG");

    ret = tollgate_client_init("https://mint.test", NULL, NULL);
    ASSERT_EQ_INT(ESP_ERR_INVALID_ARG, ret, "NULL send_fn -> INVALID_ARG");

    ret = tollgate_client_init("https://mint.test", mock_send, NULL);
    ASSERT_EQ_INT(ESP_OK, ret, "valid init -> ESP_OK");
    ASSERT_EQ_INT(TG_CLIENT_IDLE,
                  tollgate_client_get_session()->state,
                  "state starts IDLE");
}

/* 2. query → receive INFO → state=IDLE, price learned */
static void test_query_info(void)
{
    printf("\n--- test_query_info ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);
    reset_send_buf();

    esp_err_t ret = tollgate_client_query_price();
    ASSERT_EQ_INT(ESP_OK, ret, "query_price returns ESP_OK");

    const tollgate_client_session_t *s = tollgate_client_get_session();
    ASSERT_EQ_INT(TG_CLIENT_QUERYING, s->state,
                  "state is QUERYING after query");
    ASSERT(g_send_count == 1, "STATUS message was sent");

    /* Receive INFO response */
    uint8_t pkt[512];
    uint16_t pkt_len = build_info_packet(pkt, sizeof(pkt), 21, 60000);
    ASSERT(pkt_len > 0, "INFO packet built");

    ret = tollgate_client_on_packet(pkt, pkt_len);
    ASSERT_EQ_INT(ESP_OK, ret, "on_packet(INFO) returns ESP_OK");

    s = tollgate_client_get_session();
    ASSERT_EQ_INT(TG_CLIENT_IDLE, s->state, "state is IDLE after INFO");
    ASSERT_EQ_INT(21, s->price_sats, "price_sats learned from INFO");
    ASSERT_EQ_INT(60000, s->step_ms, "step_ms learned from INFO");
}

/* 3. pay → receive ACK → state=ACTIVE */
static void test_pay_ack(void)
{
    printf("\n--- test_pay_ack ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);
    reset_send_buf();

    esp_err_t ret = tollgate_client_pay(21);
    ASSERT_EQ_INT(ESP_OK, ret, "pay returns ESP_OK");

    const tollgate_client_session_t *s = tollgate_client_get_session();
    ASSERT_EQ_INT(TG_CLIENT_PAYING, s->state, "state is PAYING after pay");

    /* Receive ACK */
    uint8_t pkt[128];
    uint16_t pkt_len = build_ack_packet(pkt, sizeof(pkt), 42, 1000, 21);
    ASSERT(pkt_len > 0, "ACK packet built");

    ret = tollgate_client_on_packet(pkt, pkt_len);
    ASSERT_EQ_INT(ESP_OK, ret, "on_packet(ACK) returns ESP_OK");

    s = tollgate_client_get_session();
    ASSERT_EQ_INT(TG_CLIENT_ACTIVE, s->state, "state is ACTIVE after ACK");
    ASSERT_EQ_INT(42, (int)s->session_id, "session_id from ACK");
    ASSERT_EQ_INT(1000, (int)s->session_expires, "session_expires from ACK");
    ASSERT(tollgate_client_is_active(), "is_active() returns true");
}

/* 4. pay → receive NACK → state=ERROR */
static void test_pay_nack(void)
{
    printf("\n--- test_pay_nack ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);
    reset_send_buf();

    esp_err_t ret = tollgate_client_pay(21);
    ASSERT_EQ_INT(ESP_OK, ret, "pay returns ESP_OK");

    /* Receive NACK */
    uint8_t pkt[256];
    uint16_t pkt_len = build_nack_packet(pkt, sizeof(pkt));
    ASSERT(pkt_len > 0, "NACK packet built");

    ret = tollgate_client_on_packet(pkt, pkt_len);
    ASSERT_EQ_INT(ESP_OK, ret, "on_packet(NACK) returns ESP_OK");

    const tollgate_client_session_t *s = tollgate_client_get_session();
    ASSERT_EQ_INT(TG_CLIENT_ERROR, s->state, "state is ERROR after NACK");
    ASSERT(!tollgate_client_is_active(), "is_active() returns false");
}

/* 5. Session expiry: ACTIVE → EXPIRED via tick */
static void test_session_expiry(void)
{
    printf("\n--- test_session_expiry ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);
    reset_send_buf();

    /* Pay and receive ACK with expiry at Unix sec 100 */
    tollgate_client_pay(21);
    uint8_t pkt[128];
    uint16_t pkt_len = build_ack_packet(pkt, sizeof(pkt), 1, 100, 21);
    tollgate_client_on_packet(pkt, pkt_len);

    const tollgate_client_session_t *s = tollgate_client_get_session();
    ASSERT_EQ_INT(TG_CLIENT_ACTIVE, s->state, "state is ACTIVE after ACK");

    /* Before expiry: now = 50 sec → still ACTIVE */
    tollgate_client_mock_now_ms = 50 * 1000;
    tollgate_client_tick();
    ASSERT_EQ_INT(TG_CLIENT_ACTIVE, s->state, "still ACTIVE before expiry");

    /* After expiry: now = 200 sec → EXPIRED */
    tollgate_client_mock_now_ms = 200 * 1000;
    tollgate_client_tick();
    ASSERT_EQ_INT(TG_CLIENT_EXPIRED, s->state,
                  "state is EXPIRED after timeout");
}

/* 6. Retry logic: 3 attempts → ERROR */
static void test_retry_logic(void)
{
    printf("\n--- test_retry_logic ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);
    reset_send_buf();

    tollgate_client_pay(21);
    ASSERT_EQ_INT(0, tollgate_client_get_session()->retries,
                  "retries == 0 after initial pay");
    ASSERT_EQ_INT(1, g_send_count, "1 PAY sent (initial)");

    /* Tick 1: retry */
    tollgate_client_mock_now_ms = TG_CLIENT_RETRY_MS;
    tollgate_client_tick();
    ASSERT_EQ_INT(1, tollgate_client_get_session()->retries,
                  "retries == 1 after tick 1");
    ASSERT_EQ_INT(TG_CLIENT_PAYING,
                  tollgate_client_get_session()->state,
                  "still PAYING after tick 1");
    ASSERT_EQ_INT(2, g_send_count, "2 PAY sent (retry 1)");

    /* Tick 2: retry */
    tollgate_client_mock_now_ms = TG_CLIENT_RETRY_MS * 2;
    tollgate_client_tick();
    ASSERT_EQ_INT(2, tollgate_client_get_session()->retries,
                  "retries == 2 after tick 2");
    ASSERT_EQ_INT(TG_CLIENT_PAYING,
                  tollgate_client_get_session()->state,
                  "still PAYING after tick 2");
    ASSERT_EQ_INT(3, g_send_count, "3 PAY sent (retry 2)");

    /* Tick 3: ERROR */
    tollgate_client_mock_now_ms = TG_CLIENT_RETRY_MS * 3;
    tollgate_client_tick();
    ASSERT_EQ_INT(3, tollgate_client_get_session()->retries,
                  "retries == 3 after tick 3");
    ASSERT_EQ_INT(TG_CLIENT_ERROR,
                  tollgate_client_get_session()->state,
                  "state is ERROR after max retries");
}

/* 7. Tick in IDLE is a no-op */
static void test_tick_idle(void)
{
    printf("\n--- test_tick_idle ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);
    reset_send_buf();

    tollgate_client_mock_now_ms = 10000;
    tollgate_client_tick();

    ASSERT_EQ_INT(TG_CLIENT_IDLE,
                  tollgate_client_get_session()->state,
                  "still IDLE after tick");
    ASSERT_EQ_INT(0, g_send_count, "no messages sent in IDLE tick");
}

/* 8. PAY message wire format via mock buffer */
static void test_pay_wire_format(void)
{
    printf("\n--- test_pay_wire_format ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);
    reset_send_buf();

    tollgate_client_pay(21);

    ASSERT(g_send_len >= sizeof(tollgate_msg_hdr_t),
           "sent data >= header size");

    /* Decode the sent message */
    tollgate_msg_hdr_t hdr;
    const uint8_t *payload = NULL;
    int off = tollgate_proto_decode(g_send_buf, g_send_len, &hdr, &payload);
    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), off,
                  "decode offset == sizeof(hdr)");
    ASSERT_EQ_INT(TOLLGATE_PROTO_VERSION, hdr.version,
                  "header version == 1");
    ASSERT_EQ_INT(TG_MSG_PAY, hdr.type, "header type == TG_MSG_PAY");
    ASSERT(hdr.payload_len > 0, "payload_len > 0 (token present)");
    ASSERT(payload != NULL, "payload pointer is set");

    /* Verify payload starts with Cashu token prefix */
    ASSERT(hdr.payload_len >= 6, "payload long enough for cashuA prefix");
    ASSERT_MEM_EQ("cashuA", payload, 6,
                  "payload starts with cashuA prefix");
}

/* 9. STATUS message wire format (query_price sends STATUS) */
static void test_status_wire_format(void)
{
    printf("\n--- test_status_wire_format ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);
    reset_send_buf();

    tollgate_client_query_price();

    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), g_send_len,
                  "STATUS message is header-only (no payload)");

    tollgate_msg_hdr_t hdr;
    const uint8_t *payload = NULL;
    int off = tollgate_proto_decode(g_send_buf, g_send_len, &hdr, &payload);
    ASSERT_EQ_INT((int)sizeof(tollgate_msg_hdr_t), off, "decode STATUS");
    ASSERT_EQ_INT(TG_MSG_STATUS, hdr.type, "type == STATUS");
    ASSERT_EQ_INT(0, hdr.payload_len, "payload_len == 0");
}

/* 10. Auto-renew: EXPIRED → PAYING via tick */
static void test_auto_renew(void)
{
    printf("\n--- test_auto_renew ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);
    reset_send_buf();

    /* Get to EXPIRED state */
    tollgate_client_pay(21);
    uint8_t pkt[128];
    uint16_t pkt_len = build_ack_packet(pkt, sizeof(pkt), 1, 100, 21);
    tollgate_client_on_packet(pkt, pkt_len);

    /* Expire the session */
    tollgate_client_mock_now_ms = 200 * 1000;
    tollgate_client_tick();
    ASSERT_EQ_INT(TG_CLIENT_EXPIRED,
                  tollgate_client_get_session()->state,
                  "EXPIRED after session timeout");

    /* Next tick should auto-renew */
    reset_send_buf();
    tollgate_client_tick();
    ASSERT_EQ_INT(TG_CLIENT_PAYING,
                  tollgate_client_get_session()->state,
                  "PAYING after auto-renew");
    ASSERT(g_send_count > 0, "PAY message sent during auto-renew");
}

/* 11. State-change callback fires on transitions */
static void test_state_change_callback(void)
{
    printf("\n--- test_state_change_callback ---\n");
    g_state_change_count = 0;
    tollgate_client_init("https://mint.test", mock_send, on_state_change_cb);
    reset_send_buf();

    tollgate_client_query_price();
    ASSERT_EQ_INT(TG_CLIENT_IDLE, g_last_from,
                  "callback from = IDLE");
    ASSERT_EQ_INT(TG_CLIENT_QUERYING, g_last_to,
                  "callback to = QUERYING");
    ASSERT(g_state_change_count >= 1, "state-change callback fired");
}

/* 12. query_price rejects wrong state */
static void test_query_wrong_state(void)
{
    printf("\n--- test_query_wrong_state ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);
    reset_send_buf();

    tollgate_client_query_price();  /* IDLE → QUERYING */

    esp_err_t ret = tollgate_client_query_price();  /* QUERYING → reject */
    ASSERT_EQ_INT(ESP_ERR_INVALID_STATE, ret,
                  "query_price in QUERYING -> INVALID_STATE");
}

/* 13. pay rejects wrong state */
static void test_pay_wrong_state(void)
{
    printf("\n--- test_pay_wrong_state ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);
    reset_send_buf();

    tollgate_client_query_price();  /* IDLE → QUERYING */

    esp_err_t ret = tollgate_client_pay(21);  /* QUERYING → reject */
    ASSERT_EQ_INT(ESP_ERR_INVALID_STATE, ret,
                  "pay in QUERYING -> INVALID_STATE");
}

/* 14. on_packet rejects NULL / malformed input */
static void test_on_packet_validation(void)
{
    printf("\n--- test_on_packet_validation ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);

    esp_err_t ret = tollgate_client_on_packet(NULL, 10);
    ASSERT_EQ_INT(ESP_ERR_INVALID_ARG, ret,
                  "NULL data -> INVALID_ARG");

    uint8_t short_data[4];
    memset(short_data, 0, sizeof(short_data));
    ret = tollgate_client_on_packet(short_data, sizeof(short_data));
    ASSERT_EQ_INT(ESP_ERR_INVALID_ARG, ret,
                  "data shorter than header -> INVALID_ARG");

    /* Bad version */
    uint8_t bad_ver[8];
    memset(bad_ver, 0, sizeof(bad_ver));
    bad_ver[0] = 0xFF;  /* invalid version */
    ret = tollgate_client_on_packet(bad_ver, sizeof(bad_ver));
    ASSERT_EQ_INT(ESP_ERR_INVALID_ARG, ret,
                  "bad version -> INVALID_ARG");
}

/* 15. REVOKE packet: ACTIVE → EXPIRED */
static void test_revoke(void)
{
    printf("\n--- test_revoke ---\n");
    tollgate_client_init("https://mint.test", mock_send, NULL);
    reset_send_buf();

    /* Get to ACTIVE state */
    tollgate_client_pay(21);
    uint8_t ack[128];
    uint16_t ack_len = build_ack_packet(ack, sizeof(ack), 5, 99999, 21);
    tollgate_client_on_packet(ack, ack_len);
    ASSERT_EQ_INT(TG_CLIENT_ACTIVE,
                  tollgate_client_get_session()->state,
                  "ACTIVE before REVOKE");

    /* Build and send REVOKE (no payload) */
    uint8_t pkt[32];
    int len = tollgate_proto_encode(pkt, sizeof(pkt), TG_MSG_REVOKE, 1, NULL, 0);
    ASSERT(len > 0, "REVOKE packet built");

    esp_err_t ret = tollgate_client_on_packet(pkt, (uint16_t)len);
    ASSERT_EQ_INT(ESP_OK, ret, "on_packet(REVOKE) returns ESP_OK");
    ASSERT_EQ_INT(TG_CLIENT_EXPIRED,
                  tollgate_client_get_session()->state,
                  "state is EXPIRED after REVOKE");
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

int main(void)
{
    printf("=== test_tollgate_client ===\n");

    test_init_validation();
    test_query_info();
    test_pay_ack();
    test_pay_nack();
    test_session_expiry();
    test_retry_logic();
    test_tick_idle();
    test_pay_wire_format();
    test_status_wire_format();
    test_auto_renew();
    test_state_change_callback();
    test_query_wrong_state();
    test_pay_wrong_state();
    test_on_packet_validation();
    test_revoke();

    TEST_SUMMARY();
}
