/*
 * mesh_service_mux.c — 1-byte service multiplexer for shared mesh transport.
 *
 * See mesh_service_mux.h for wire format and integration notes.
 *
 * The implementation is deliberately minimal: wrap() copies the service
 * byte + payload into a flat buffer; unwrap() returns a pointer that
 * aliases the input.  No heap, no state, no locking.
 */
#include "mesh_service_mux.h"

#include <string.h>

/* ── Wrap ────────────────────────────────────────────────────────── */

int mesh_service_mux_wrap(uint8_t svc, const uint8_t *in, uint16_t in_len,
                           uint8_t *out, uint16_t out_cap)
{
    /* Validate arguments */
    if (!out)
        return MESH_MUX_ERR_INVALID;
    if (in_len > 0 && !in)
        return MESH_MUX_ERR_INVALID;

    /* Need 1 byte for the service tag + in_len payload bytes */
    uint16_t need = (uint16_t)(1u + in_len);
    if (need > out_cap)
        return MESH_MUX_ERR_TOO_LARGE;

    out[0] = svc;
    if (in_len > 0)
        memcpy(out + 1, in, in_len);

    return (int)need;
}

/* ── Unwrap ──────────────────────────────────────────────────────── */

int mesh_service_mux_unwrap(const uint8_t *data, uint16_t len,
                             uint8_t *svc_out,
                             const uint8_t **payload, uint16_t *payload_len)
{
    if (!data)
        return MESH_MUX_ERR_INVALID;

    /* Need at least the 1-byte service tag */
    if (len < 1)
        return MESH_MUX_ERR_FORMAT;

    if (svc_out)
        *svc_out = data[0];

    if (payload)
        *payload = data + 1;

    if (payload_len)
        *payload_len = (uint16_t)(len - 1);

    return MESH_MUX_OK;
}
