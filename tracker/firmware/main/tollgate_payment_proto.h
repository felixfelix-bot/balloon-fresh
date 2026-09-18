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

/*
 * Capacity constants
 * ------------------
 * TOLLGATE_MAX_TOKEN_LEN is the PROTOCOL capability and matches the mesh-stack
 * tollgate component
 * (mesh-stack/tollgate/components/tollgate_balloon/include/tollgate_balloon.h),
 * which carries a full 2048-byte token in a 2056-byte buffer
 * (tollgate_balloon.c: sizeof(tollgate_msg_hdr_t) + TOLLGATE_MAX_TOKEN_LEN).
 *
 * The tracker relay pipeline CANNOT carry that much: a relay frame is
 * RELAY_PACKET_MAX_SIZE (512 B, main/relay_types.h) and starts with a 1-byte
 * relay type tag, so the largest TollGate payload that can cross it is
 *
 *   TOLLGATE_MAX_PAYLOAD_RELAY = 512 - 1 (relay tag) - 8 (header) = 503 bytes
 *
 * Payloads over TOLLGATE_MAX_PAYLOAD_RELAY are rejected explicitly by
 * tollgate_proto_encode_relay() (TG_ENC_ERR_TOO_LONG) so a 2048-byte token
 * fails loudly instead of being silently dropped in the pipeline. Payloads
 * over TOLLGATE_MAX_TOKEN_LEN are refused by tollgate_proto_encode() itself,
 * whatever frame size it is handed.
 */
#define TOLLGATE_MAX_TOKEN_LEN      2048
#define TOLLGATE_MAX_PAYLOAD_RELAY  503   /* 512 - 1 relay tag - 8 header */

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
    uint16_t seq;           /* Sequence number — u16 echo token, see contract */
    uint16_t payload_len;   /* Length of payload following header */
    uint16_t reserved;      /* Alignment / future use */
} __attribute__((packed)) tollgate_msg_hdr_t;

/*
 * Sequence-number contract (v1)
 * -----------------------------
 * `seq` is a uint16_t on the wire and wraps modulo 2^16 (TOLLGATE_SEQ_MODULO).
 *
 *   - The producer increments its counter with tollgate_seq_next():
 *     65534 → 65535 → 0 → 1 ...
 *   - `seq` is an OPAQUE ECHO TOKEN: a responder copies the requester's seq
 *     into its ACK/NACK verbatim, and 0 is a legal, meaningful value that must
 *     never be conflated with "no sequence number" (test with `is not None` /
 *     a sentinel, not with truthiness).
 *   - Equality is EXACT 16-bit equality (tollgate_seq_equal()).
 *   - There is NO deduplication in v1: no receiver filters duplicates and no
 *     modular/sliding comparison window exists. A wrapped-forward pair such as
 *     65535 → 0 is NOT a match. Implementations that want dedup must first
 *     change this contract (and then handle the ambiguity a wrap introduces).
 */
#define TOLLGATE_SEQ_MODULO  (1u << 16)

/* Producer-side increment: wraps at 2^16 (65535 → 0). */
static inline uint16_t tollgate_seq_next(uint16_t seq)
{
    return (uint16_t)(seq + 1u);
}

/* Echo check: exact equality, no window, no dedup (see contract above). */
static inline int tollgate_seq_equal(uint16_t sent, uint16_t echoed)
{
    return sent == echoed;
}

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

/* Encode errors */
#define TG_ENC_ERR_TOO_LONG   (-2)  /* payload cannot fit the target frame */

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
 *         (NULL buffer, insufficient room, or payload_len >
 *         TOLLGATE_MAX_TOKEN_LEN — the protocol's hard cap)
 */
int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
                           tollgate_msg_type_t type, uint16_t seq,
                           const char *payload, uint16_t payload_len);

/*
 * Encode a message into the payload area of a relay frame.
 *
 * This is the entry point the tracker relay pipeline uses. `frame` is a relay
 * packet's data array and `frame[0]` is the 1-byte relay type tag
 * (RELAY_TYPE_TOLLGATE_PAY / _ACK — the caller sets it), so the message is
 * encoded at frame + 1 with capacity frame_len - 1 and the relay payload
 * budget (TOLLGATE_MAX_PAYLOAD_RELAY) is enforced here, in the encode path,
 * rather than only at the call site.
 *
 * @param frame        Relay packet data array (frame[0] = relay type tag)
 * @param frame_len    Capacity of that array (RELAY_PACKET_MAX_SIZE)
 * @param type         Message type
 * @param seq          Sequence number (u16 echo token)
 * @param payload      Payload data
 * @param payload_len  Payload length in bytes
 * @return header+payload bytes written at frame + 1 (so the frame length is
 *         the return value + 1), or -1 on invalid arguments, or
 *         TG_ENC_ERR_TOO_LONG when the payload exceeds
 *         TOLLGATE_MAX_PAYLOAD_RELAY or does not fit in frame_len.
 */
int tollgate_proto_encode_relay(uint8_t *frame, uint16_t frame_len,
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