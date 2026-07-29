#ifndef TOLLGATE_PAYMENT_PROTO_H
#define TOLLGATE_PAYMENT_PROTO_H

#include "tollgate_balloon.h"
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/*
 * TollGate Payment Protocol — UDP message format (ADR-002)
 *
 * All messages use the tollgate_msg_hdr_t header (8 bytes, packed).
 * Payloads are JSON for v1 (matches existing tollgate_api format).
 *
 * Wire format:
 *   [hdr(8)] [payload(N, JSON)]
 *
 * Max total message size: TOLLGATE_MAX_TOKEN_LEN + sizeof(hdr) + 64
 */

/* PAY message payload (Client → Balloon) */
typedef struct {
    char token[TOLLGATE_MAX_TOKEN_LEN];  /* Cashu token string (cashuA...) */
} tollgate_pay_payload_t;

/* ACK message payload (Balloon → Client) */
typedef struct {
    uint32_t session_id;
    uint32_t expires_unix;     /* Session expiry timestamp */
    uint32_t quota_bytes;      /* Data quota (0 = unlimited time-based) */
    uint16_t price_sats;       /* Price that was charged */
} __attribute__((packed)) tollgate_ack_payload_t;

/* NACK message payload (Balloon → Client) */
typedef struct {
    int16_t error_code;        /* Negative errno-style code */
    char message[128];         /* Human-readable error */
} __attribute__((packed)) tollgate_nack_payload_t;

/* NACK error codes */
#define TG_ERR_INVALID_TOKEN    (-1)  /* Malformed Cashu token */
#define TG_ERR_SWAP_FAILED      (-2)  /* Mint rejected token */
#define TG_ERR_MINT_UNREACHABLE (-3)  /* Can't contact mint (offline) */
#define TG_ERR_ALREADY_PAID     (-4)  /* Session already active for this node */
#define TG_ERR_RATE_LIMITED     (-5)  /* Too many attempts */

/* INFO message payload (Balloon → Client, JSON) */
/* Example:
 * {
 *   "price_sats": 21,
 *   "step_ms": 60000,
 *   "mint_url": "https://mint.minibits.cash",
 *   "active_sessions": 3,
 *   "version": 1
 * }
 */

/*
 * Encode a message header + JSON payload into a buffer.
 * @return total bytes written, or -1 on error
 */
int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
                           tollgate_msg_type_t type, uint16_t seq,
                           const char *json_payload, uint16_t json_len);

/*
 * Decode a message header from raw bytes.
 * @return payload offset (always sizeof(hdr)), or -1 on invalid header
 * Sets *payload_len to payload length.
 */
int tollgate_proto_decode(const uint8_t *data, uint16_t len,
                           tollgate_msg_hdr_t *hdr,
                           const uint8_t **payload);

/*
 * Build INFO JSON response.
 * @return malloc'd string, caller must free.
 */
char *tollgate_proto_build_info_json(uint16_t price_sats,
                                      int32_t step_ms,
                                      const char *mint_url,
                                      int active_sessions);

#ifdef __cplusplus
}
#endif

#endif
