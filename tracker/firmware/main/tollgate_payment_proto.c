/*
 * tollgate_payment_proto.c — encode/decode for TollGate payment protocol
 *
 * Wire format (ADR-002):
 *   [hdr(8 bytes, packed)] [payload(N bytes)]
 *
 * Self-contained — no ESP-IDF dependencies. Host-testable with gcc.
 * Wire-compatible with mesh-stack/tollgate/components/tollgate_balloon/.
 */

#include "tollgate_payment_proto.h"
#include <string.h>

int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
                           tollgate_msg_type_t type, uint16_t seq,
                           const char *payload, uint16_t payload_len)
{
    if (!buf || buf_len < (uint16_t)sizeof(tollgate_msg_hdr_t) + payload_len)
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