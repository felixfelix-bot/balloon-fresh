/*
 * tollgate_payment_proto.h — TollGate payment protocol for balloon tracker
 *
 * Self-contained encode/decode for TollGate PAY/ACK/NACK/INFO messages
 * over the relay pipeline. Wire-compatible with the tollgate component's
 * version (mesh-stack/tollgate/components/tollgate_balloon/).
 *
 * Wire format (ADR-002):
 *   [hdr(8 bytes, packed)] [payload(N bytes)]
 *
 * Header layout (little-endian, packed):
 *   offset 0  version      uint8_t   (1 = current)
 *   offset 1  type         uint8_t   (tollgate_msg_type_t)
 *   offset 2  seq          uint16_t
 *   offset 4  payload_len  uint16_t
 *   offset 6  reserved     uint16_t  (0, future use)
 *
 * In the relay pipeline, this message is preceded by a 1-byte relay
 * type tag (RELAY_TYPE_TOLLGATE_PAY or RELAY_TYPE_TOLLGATE_ACK).
 */

#ifndef TOLLGATE_PAYMENT_PROTO_H
#define TOLLGATE_PAYMENT_PROTO_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Protocol version */
#define TOLLGATE_PROTO_VERSION  1

/* Maximum Cashu token length (matches tollgate component) */
#define TOLLGATE_MAX_TOKEN_LEN  2048

/* Message types */
typedef enum {
    TG_MSG_PAY      = 0x01,  /* Client → Balloon: Cashu token payment */
    TG_MSG_ACK      = 0x02,  /* Balloon → Client: Payment accepted + session info */
    TG_MSG_NACK     = 0x03,  /* Balloon → Client: Payment rejected + reason */
    TG_MSG_STATUS   = 0x04,  /* Client → Balloon: Request status/pricing */
    TG_MSG_INFO     = 0x05,  /* Balloon → Client: Status response (price, mints) */
    TG_MSG_REVOKE   = 0x06,  /* Balloon → Client: Session revoked */
} tollgate_msg_type_t;

/* Packed 8-byte message header */
typedef struct {
    uint8_t  version;       /* Protocol version (TOLLGATE_PROTO_VERSION) */
    uint8_t  type;          /* tollgate_msg_type_t */
    uint16_t seq;           /* Sequence number for dedup */
    uint16_t payload_len;   /* Length of payload following header */
    uint16_t reserved;      /* Alignment / future use */
} __attribute__((packed)) tollgate_msg_hdr_t;

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

/*
 * Encode a message header + payload into a buffer.
 *
 * @param buf         Output buffer
 * @param buf_len      Output buffer capacity
 * @param type         Message type (TG_MSG_PAY, TG_MSG_ACK, etc.)
 * @param seq          Sequence number
 * @param payload      Payload data (may be NULL if payload_len == 0)
 * @param payload_len  Payload length in bytes
 * @return total bytes written (header + payload), or -1 on error
 */
int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
                           tollgate_msg_type_t type, uint16_t seq,
                           const char *payload, uint16_t payload_len);

/*
 * Decode a message header from raw bytes.
 *
 * @param data      Raw message bytes (header + payload)
 * @param len       Total byte count
 * @param hdr       Output: decoded header (caller-allocated)
 * @param payload   Output: pointer to payload within data (may be NULL)
 * @return sizeof(tollgate_msg_hdr_t) on success, or -1 on invalid header
 */
int tollgate_proto_decode(const uint8_t *data, uint16_t len,
                           tollgate_msg_hdr_t *hdr,
                           const uint8_t **payload);

#ifdef __cplusplus
}
#endif

#endif /* TOLLGATE_PAYMENT_PROTO_H */