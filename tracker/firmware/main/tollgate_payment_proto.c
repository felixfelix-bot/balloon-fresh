/*
 * tollgate_payment_proto.c — encode/decode for TollGate payment protocol
 *
 * Wire format (ADR-002):
 *   [hdr(8 bytes, packed)] [payload(N bytes)]
 *
 * Self-contained — no ESP-IDF dependencies. Host-testable with gcc.
 * Wire-compatible with mesh-stack/tollgate/components/tollgate_balloon/.
 *
 * The one tracker-specific dependency is relay_types.h, used only for the
 * compile-time check that TOLLGATE_MAX_PAYLOAD_RELAY still matches
 * RELAY_PACKET_MAX_SIZE (see tollgate_proto_encode_relay below).
 */

#include "tollgate_payment_proto.h"
#include "relay_types.h"
#include <string.h>

/* The documented relay payload budget must track the relay frame size. If a
 * future change resizes RELAY_PACKET_MAX_SIZE, this fails the build instead of
 * silently letting an over-long payload be truncated or dropped. */
_Static_assert(TOLLGATE_MAX_PAYLOAD_RELAY ==
                   (RELAY_PACKET_MAX_SIZE - 1 - (int)sizeof(tollgate_msg_hdr_t)),
               "TOLLGATE_MAX_PAYLOAD_RELAY drifted from RELAY_PACKET_MAX_SIZE");

int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
                           tollgate_msg_type_t type, uint16_t seq,
                           const char *payload, uint16_t payload_len)
{
    if (!buf || buf_len < (uint16_t)sizeof(tollgate_msg_hdr_t) + payload_len)
        return -1;

    /* Protocol-level hard cap: no caller may smuggle a larger token through,
     * however big its buffer is. */
    if (payload_len > TOLLGATE_MAX_TOKEN_LEN)
        return -1;

    tollgate_msg_hdr_t *hdr = (tollgate_msg_hdr_t *)buf;
    hdr->version     = TOLLGATE_PROTO_VERSION;
    hdr->type        = (uint8_t)type;
    hdr->seq         = seq;
    hdr->payload_len = payload_len;
    hdr->reserved    = 0;

    if (payload_len > 0 && payload) {
        memcpy(buf + sizeof(tollgate_msg_hdr_t), payload, payload_len);
    }

    return (int)(sizeof(tollgate_msg_hdr_t) + payload_len);
}

int tollgate_proto_encode_relay(uint8_t *frame, uint16_t frame_len,
                                 tollgate_msg_type_t type, uint16_t seq,
                                 const char *payload, uint16_t payload_len)
{
    /* frame[0] is the 1-byte relay type tag, so the message gets frame_len-1. */
    if (!frame || frame_len < (uint16_t)(1 + sizeof(tollgate_msg_hdr_t)))
        return -1;

    /* Explicit, early rejection of anything the relay cannot carry. A 2048-byte
     * token (TOLLGATE_MAX_TOKEN_LEN) always lands here: the tracker relay frame
     * holds at most TOLLGATE_MAX_PAYLOAD_RELAY (503) payload bytes. */
    if (payload_len > TOLLGATE_MAX_PAYLOAD_RELAY ||
        (uint32_t)payload_len + 1u + sizeof(tollgate_msg_hdr_t) > (uint32_t)frame_len)
        return TG_ENC_ERR_TOO_LONG;

    return tollgate_proto_encode(frame + 1, (uint16_t)(frame_len - 1),
                                  type, seq, payload, payload_len);
}

int tollgate_proto_decode(const uint8_t *data, uint16_t len,
                           tollgate_msg_hdr_t *hdr,
                           const uint8_t **payload)
{
    if (!data || len < (uint16_t)sizeof(tollgate_msg_hdr_t))
        return -1;

    memcpy(hdr, data, sizeof(tollgate_msg_hdr_t));

    /* Validate */
    if (hdr->version != TOLLGATE_PROTO_VERSION)
        return -1;
    if (hdr->payload_len > len - (uint16_t)sizeof(tollgate_msg_hdr_t))
        return -1;

    if (payload)
        *payload = data + sizeof(tollgate_msg_hdr_t);

    return (int)sizeof(tollgate_msg_hdr_t);
}
