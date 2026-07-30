/*
 * tollgate_payment_proto.c — UDP payment message encode/decode
 *
 * Implements ADR-002: TollGate payment over FIPS mesh UDP.
 * Message format: [hdr(8 bytes, packed)] [payload(N bytes, JSON)]
 */

#include "tollgate_payment_proto.h"
#include "tollgate_balloon.h"
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

int tollgate_proto_encode(uint8_t *buf, uint16_t buf_len,
                           tollgate_msg_type_t type, uint16_t seq,
                           const char *json_payload, uint16_t json_len)
{
    if (!buf || buf_len < sizeof(tollgate_msg_hdr_t) + json_len)
        return -1;

    tollgate_msg_hdr_t *hdr = (tollgate_msg_hdr_t *)buf;
    hdr->version    = TOLLGATE_PROTO_VERSION;
    hdr->type       = (uint8_t)type;
    hdr->seq        = seq;
    hdr->payload_len = json_len;
    hdr->reserved   = 0;

    if (json_len > 0 && json_payload) {
        memcpy(buf + sizeof(tollgate_msg_hdr_t), json_payload, json_len);
    }

    return (int)(sizeof(tollgate_msg_hdr_t) + json_len);
}

int tollgate_proto_decode(const uint8_t *data, uint16_t len,
                           tollgate_msg_hdr_t *hdr,
                           const uint8_t **payload)
{
    if (!data || len < sizeof(tollgate_msg_hdr_t))
        return -1;

    memcpy(hdr, data, sizeof(tollgate_msg_hdr_t));

    /* Validate */
    if (hdr->version != TOLLGATE_PROTO_VERSION)
        return -1;
    if (hdr->payload_len > len - sizeof(tollgate_msg_hdr_t))
        return -1;

    if (payload)
        *payload = data + sizeof(tollgate_msg_hdr_t);

    return (int)sizeof(tollgate_msg_hdr_t);
}

char *tollgate_proto_build_info_json(uint16_t price_sats,
                                      int32_t step_ms,
                                      const char *mint_url,
                                      int active_sessions)
{
    /* Max ~200 bytes for a typical info response */
    char *json = malloc(256);
    if (!json) return NULL;

    snprintf(json, 256,
             "{\"price_sats\":%u,\"step_ms\":%ld,\"mint_url\":\"%s\",\"active_sessions\":%d,\"version\":%d}",
             price_sats, (long)step_ms, mint_url ? mint_url : "", active_sessions, TOLLGATE_PROTO_VERSION);

    return json;
}
