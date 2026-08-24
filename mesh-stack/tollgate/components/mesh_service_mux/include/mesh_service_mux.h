/*
 * mesh_service_mux.h — 1-byte service multiplexer for shared mesh transport.
 *
 * When multiple upper-layer services (TollGate, Nostr, Blossom) share a
 * single mesh_adapter datagram channel, each outgoing payload is prefixed
 * with a 1-byte service identifier so the receiver can demultiplex.
 *
 * Wire format:
 *
 *   Byte 0      : service ID  (MESH_SVC_*)
 *   Bytes 1..N  : service payload (opaque to the mux layer)
 *
 * The mux layer is deliberately stateless and allocation-free.  wrap()
 * copies into a caller-supplied buffer; unwrap() returns a pointer that
 * aliases the input buffer (zero-copy).
 *
 * Typical integration (mirrors blossom_datagram's dependency-injection
 * pattern):
 *
 *   Send path:  service_build_msg() → mux_wrap(SVC, buf, len, mesh_buf, cap)
 *                                          → mesh_adapter_send(mesh_buf, wrapped_len, …)
 *
 *   Recv path:  mesh_adapter_receive_frame() → mux_unwrap(frame, len, &svc, &p, &plen)
 *                                              → if (svc == SVC_TOLLGATE) tollgate_on_packet(p, plen);
 */
#ifndef MESH_SERVICE_MUX_H
#define MESH_SERVICE_MUX_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ── Service IDs ────────────────────────────────────────────────── */

#define MESH_SVC_TOLLGATE  0x01
#define MESH_SVC_NOSTR     0x02
#define MESH_SVC_BLOSSOM   0x03

/* ── Result codes ───────────────────────────────────────────────── */

#define MESH_MUX_OK             0
#define MESH_MUX_ERR_INVALID   -1   /* NULL argument or bad param   */
#define MESH_MUX_ERR_TOO_LARGE -2   /* output buffer too small      */
#define MESH_MUX_ERR_FORMAT    -3   /* truncated / malformed input  */

/* ── API ────────────────────────────────────────────────────────── */

/*
 * Prepend a 1-byte service ID to `in` (in_len bytes) and write the result
 * into `out` (capacity out_cap).
 *
 * Returns the total number of bytes written (1 + in_len) on success,
 * or a negative MESH_MUX_ERR_* code on error.
 */
int mesh_service_mux_wrap(uint8_t svc, const uint8_t *in, uint16_t in_len,
                           uint8_t *out, uint16_t out_cap);

/*
 * Parse a wrapped buffer.  On success *svc_out holds the service byte,
 * *payload points into `data` at offset 1, and *payload_len is len - 1.
 *
 * Any of svc_out / payload / payload_len may be NULL (caller doesn't care).
 *
 * Returns MESH_MUX_OK (0) on success, or a negative MESH_MUX_ERR_* code.
 */
int mesh_service_mux_unwrap(const uint8_t *data, uint16_t len,
                             uint8_t *svc_out,
                             const uint8_t **payload, uint16_t *payload_len);

#ifdef __cplusplus
}
#endif

#endif /* MESH_SERVICE_MUX_H */
