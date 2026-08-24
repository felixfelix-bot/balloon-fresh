/*
 * blossom_datagram.h — Bridge between mesh datagram transport and
 * blossom blob storage.
 *
 * Wire format (compact binary, all fields in transmission order):
 *
 *   Byte  0       : message type  (1=PUT, 2=GET, 3=RESPONSE, 4=ERROR)
 *   Bytes 1..32   : SHA-256 (32 raw bytes; always present)
 *   Byte  33      : content_type_len (0..16; only meaningful for PUT,
 *                   0 for GET/RESPONSE/ERROR)
 *   Bytes 34..    : content_type string (content_type_len bytes, PUT only)
 *   Then         : payload bytes (PUT carries blob data; RESPONSE carries
 *                   blob data; ERROR carries a human-readable reason;
 *                   GET carries no payload)
 *
 * The adapter never blocks on the radio directly. It serializes a message
 * into a flat buffer and hands it to an injected `send` callback (which
 * the integrator wires to mesh_adapter_send). Likewise, when the mesh
 * stack delivers a reassembled frame, the integrator calls
 * blossom_datagram_handle_message() which parses and routes it:
 *
 *   PUT      -> store callback (after optional auth check)
 *   GET      -> load callback, then send a RESPONSE
 *   RESPONSE -> delivered to the response callback (if registered)
 *   ERROR    -> delivered to the error callback (if registered)
 *
 * Design note: storage / auth / load backends are injected as function
 * pointers so the component is unit-testable on host with mocks and
 * is not hard-coupled to the ESP-IDF blossom_storage/auth components
 * (which pull in LittleFS, esp_http_server, etc.). On the device the
 * integrator wraps the real blossom_storage_* and blossom_auth_*
 * functions into these callbacks.
 */
#pragma once

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ── Message types ──────────────────────────────────────────────── */

#define BLOSSOM_MSG_PUT       0x01
#define BLOSSOM_MSG_GET       0x02
#define BLOSSOM_MSG_RESPONSE  0x03
#define BLOSSOM_MSG_ERROR     0x04

/* ── Format constants ───────────────────────────────────────────── */

#define BLOSSOM_SHA256_LEN            32
#define BLOSSOM_MAX_CONTENT_TYPE_LEN  16
/* type(1) + sha256(32) + content_type_len(1) */
#define BLOSSOM_DGRAM_HEADER_LEN      34
/* Practical cap so a single serialized message fits a mesh fragment set. */
#define BLOSSOM_DGRAM_MAX_PAYLOAD     4096

/* ── Result codes ───────────────────────────────────────────────── */

typedef enum {
    BLOSSOM_DGRAM_OK                = 0,
    BLOSSOM_DGRAM_ERR_INVALID_PARAM = -1,
    BLOSSOM_DGRAM_ERR_TOO_LARGE     = -2,
    BLOSSOM_DGRAM_ERR_FORMAT        = -3,
    BLOSSOM_DGRAM_ERR_AUTH          = -4,
    BLOSSOM_DGRAM_ERR_NOT_FOUND     = -5,
    BLOSSOM_DGRAM_ERR_SEND_FAILED   = -6,
    BLOSSOM_DGRAM_ERR_SHA_MISMATCH  = -7,
    BLOSSOM_DGRAM_ERR_NO_BACKEND    = -8,
    BLOSSOM_DGRAM_ERR_TRUNCATED     = -9,
} blossom_dgram_result_t;

/* ── Parsed message ─────────────────────────────────────────────── */

/*
 * Fields below point INTO the buffer passed to blossom_dgram_parse();
 * the buffer must remain valid for the lifetime of this struct.
 */
typedef struct {
    uint8_t        type;                /* BLOSSOM_MSG_*                */
    uint8_t        sha256[BLOSSOM_SHA256_LEN];
    uint8_t        content_type_len;    /* 0..16                        */
    const char    *content_type;        /* points into buf, NOT NUL-term */
    const uint8_t *payload;             /* points into buf               */
    size_t         payload_len;
} blossom_dgram_msg_t;

/* ── Injected backend callbacks ─────────────────────────────────── */

/*
 * Store a blob. `sha256` is 32 raw bytes. `content_type` may be NULL.
 * Returns BLOSSOM_DGRAM_OK on success.
 */
typedef blossom_dgram_result_t (*blossom_dgram_store_fn)(
    const uint8_t *sha256,
    const uint8_t *data, size_t len,
    const char *content_type);

/*
 * Load a blob by 32-byte SHA-256. Caller provides out_data buffer of
 * capacity *inout_len; on success *inout_len is set to actual length.
 * out_content_type (capacity ct_cap) receives the MIME string if present.
 */
typedef blossom_dgram_result_t (*blossom_dgram_load_fn)(
    const uint8_t *sha256,
    uint8_t *out_data, size_t *inout_len,
    char *out_content_type, size_t ct_cap);

/*
 * Verify a Nostr auth event authorizing a PUT of the blob identified by
 * `sha256`. `event` is the raw event bytes (JSON or canonical form,
 * backend-defined). Returns BLOSSOM_DGRAM_OK if authorized.
 * May be NULL to disable auth enforcement.
 */
typedef blossom_dgram_result_t (*blossom_dgram_auth_fn)(
    const uint8_t *sha256,
    const uint8_t *event, size_t event_len);

/*
 * Transmit a fully-serialized message buffer. Integrator typically wraps
 * mesh_adapter_send(). Returns BLOSSOM_DGRAM_OK on success.
 */
typedef blossom_dgram_result_t (*blossom_dgram_send_fn)(
    const uint8_t *data, size_t len);

/*
 * Delivered when a RESPONSE message is handled. May be NULL.
 */
typedef void (*blossom_dgram_response_cb)(
    const uint8_t *sha256,
    const uint8_t *payload, size_t payload_len);

/*
 * Delivered when an ERROR message is handled. `reason` points into the
 * message buffer. May be NULL.
 */
typedef void (*blossom_dgram_error_cb)(
    const uint8_t *sha256,
    const uint8_t *reason, size_t reason_len);

typedef struct {
    blossom_dgram_store_fn    store;     /* required for PUT handling   */
    blossom_dgram_load_fn     load;      /* required for GET handling   */
    blossom_dgram_auth_fn     auth;      /* optional; NULL = no auth    */
    blossom_dgram_send_fn     send;      /* required for sending        */
    blossom_dgram_response_cb on_response; /* optional                 */
    blossom_dgram_error_cb    on_error;    /* optional                 */
} blossom_dgram_config_t;

/* ── Lifecycle ──────────────────────────────────────────────────── */

/*
 * Initialize the adapter with the given backend callbacks. The config is
 * copied internally; the caller may discard it after this call.
 * Calling init again replaces the previous configuration.
 */
void blossom_datagram_init(const blossom_dgram_config_t *cfg);

/* ── Low-level serialization ────────────────────────────────────── */

/*
 * Serialize a PUT message into out_buf.
 * Returns total bytes written (>0) on success, or a negative
 * blossom_dgram_result_t on error.
 */
int blossom_dgram_serialize_put(
    uint8_t *out_buf, size_t out_cap,
    const uint8_t *sha256,                /* 32 bytes */
    const char *content_type,             /* may be NULL -> len 0 */
    const uint8_t *payload, size_t payload_len);

/*
 * Serialize a GET request (header only, no payload).
 */
int blossom_dgram_serialize_get(
    uint8_t *out_buf, size_t out_cap,
    const uint8_t *sha256);

/*
 * Serialize a RESPONSE carrying blob data.
 */
int blossom_dgram_serialize_response(
    uint8_t *out_buf, size_t out_cap,
    const uint8_t *sha256,
    const uint8_t *payload, size_t payload_len);

/*
 * Serialize an ERROR carrying a reason string.
 */
int blossom_dgram_serialize_error(
    uint8_t *out_buf, size_t out_cap,
    const uint8_t *sha256,
    const uint8_t *reason, size_t reason_len);

/*
 * Parse a wire-format buffer into msg. The msg's pointer fields alias buf.
 */
blossom_dgram_result_t blossom_dgram_parse(
    const uint8_t *buf, size_t buf_len,
    blossom_dgram_msg_t *msg);

/* ── High-level send helpers ────────────────────────────────────── */

/*
 * Serialize and transmit a PUT message via the configured send callback.
 */
blossom_dgram_result_t blossom_datagram_put_blob(
    const uint8_t *sha256,
    const char *content_type,
    const uint8_t *payload, size_t payload_len);

/*
 * Serialize and transmit a GET request via the configured send callback.
 */
blossom_dgram_result_t blossom_datagram_get_blob(
    const uint8_t *sha256);

/* ── Inbound routing ────────────────────────────────────────────── */

/*
 * Handle a received, already-reassembled message buffer. Routes by type:
 *   PUT      -> (optional auth) -> store
 *   GET      -> load -> send RESPONSE (or ERROR if not found)
 *   RESPONSE -> on_response callback
 *   ERROR    -> on_error callback
 */
blossom_dgram_result_t blossom_datagram_handle_message(
    const uint8_t *buf, size_t buf_len);

/* ── Auth-event side channel ────────────────────────────────────── */

/*
 * Provide a Nostr auth event authorizing the next PUT of the blob with
 * the given SHA-256. Per the wire protocol the auth event travels as a
 * SEPARATE message preceding the PUT; the integrator calls this when
 * that auth message arrives so the subsequent PUT can be validated.
 * Only one pending auth is held (most recent set wins). Pass event=NULL
 * to clear.
 */
blossom_dgram_result_t blossom_datagram_set_pending_auth(
    const uint8_t *sha256,
    const uint8_t *event, size_t event_len);

#ifdef __cplusplus
}
#endif
