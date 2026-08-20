/**
 * @file    buffer.h
 * @brief   TX payload buffer for the E80 bench firmware (docs/plans/tx-buffer-spec.md).
 *
 * Host stages an arbitrary TX payload (up to 4096 B) over the console:
 *   BUF LOAD <n> <crc16_hex>\r\n   -> 'OK BINARY <n>' ack, then exactly n raw
 *                                     bytes (no escape), then a final
 *                                     'OK BUF <n> <crc_ok>' / 'ERR CRC' reply.
 *   BUF CLEAR                      -> drop the staged buffer (len=0).
 *   BUF STATUS                     -> 'BUF len=<n> crc=<0x…>'.
 *
 * TX path: with a staged buffer (len>0), each burst packet is a contiguous
 * chunk of the 4096-byte arena, wrapping at the arena boundary (long-soak
 * capable); when len==0 the existing PRBS payload path is used unchanged.
 *
 * Decisions pinned here (spec, final):
 *   - CRC16 is CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection,
 *     no xorout); bitwise implementation (~40 B flash).
 *   - Binary payload may contain CR/LF/ESC/NUL — no escaping, length-delimited.
 *   - The command line's trailing CR/LF is consumed BEFORE counting payload
 *     bytes (off-by-2 guard).
 *   - Idle timeout 1.0 s during binary receive: abort, discard the partial
 *     payload; a previously COMMITTED buffer survives (only CRC-fail sets
 *     len=0 - stale-partial is forbidden; rule 3 vs rule 5).
 *   - Buffer survives STOP / ROLE change; cleared ONLY by BUF CLEAR, a new
 *     successful LOAD, or power cycle. CRC-failed LOAD also clears it.
 *   - Reject matrix for BUF LOAD (checked BEFORE any binary phase), in
 *     precedence order: role==RX, TX burst active, TX armed. NOTE: STOP does
 *     NOT clear tx_armed; a ROLE change does (unlock path).
 */

#ifndef E80_BUFFER_H
#define E80_BUFFER_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BUF_CAPACITY 4096u
#define BUF_IDLE_TIMEOUT_MS 1000u

/* ---- CRC-16/CCITT-FALSE ---------------------------------------------------- */

/** CRC16 over data[0..len-1] (poly 0x1021, init 0xFFFF, no reflect, no xor).
 *  Golden vectors (C + Python, tools/test_crc16_golden.py):
 *    "123456789"        -> 0x29B1
 *    64 zero bytes      -> 0xD6DA
 *    4096 bytes i%256   -> 0x0F69
 */
uint16_t crc16_ccitt_false(const uint8_t* data, uint32_t len);

/* ---- BUF LOAD gate (reject matrix, checked before the binary phase) -------- */

typedef enum
{
    BUF_LOAD_OK = 0,
    BUF_LOAD_ERR_ROLE,  /* role == RX: the TX buffer is TX-side only */
    BUF_LOAD_ERR_BURST, /* a TX burst is in flight */
    BUF_LOAD_ERR_ARMED, /* TX armed (STOP does NOT clear armed; ROLE change does) */
} buf_load_gate_t;

/** Pure decision: may a BUF LOAD start its binary phase right now?
 *  Precedence on multiple hits: ROLE > BURST > ARMED. */
buf_load_gate_t buf_load_gate(bool role_is_rx, bool burst_active, bool tx_armed);

/** Exact console reply line for a gate rejection (bench.c prints it as-is). */
const char* buf_load_gate_reply(buf_load_gate_t g);

/* ---- Staged buffer ---------------------------------------------------------- */

/** Drop the staged payload: len=0 (arena content becomes irrelevant). */
void buf_clear(void);

/** Staged payload length (0 = no buffer staged -> PRBS fallback on TX). */
uint16_t buf_len(void);

/** CRC16 over the staged payload (meaningful once buf_len() > 0). */
uint16_t buf_crc16(void);

/** Ring/binary-receive drop counter (diagnostic, surfaced in BUF STATUS). */
uint32_t buf_drops(void);

/* ---- Binary load staging (driven by the console binary phase) -------------- */

/** Arm staging for an n-byte binary receive. Rejects n==0 / n>BUF_CAPACITY. */
bool buf_load_begin(uint16_t n);

/** Append one received payload byte (ignored unless a load is in progress). */
void buf_load_byte(uint8_t b);

/** Finish the load: computes CRC16 over the staged bytes and compares with
 *  expected_crc. On match the buffer is committed (len=n). On MISMATCH the
 *  buffer is cleared (len=0 - stale-partial forbidden, spec rule 5). */
bool buf_load_commit(uint16_t expected_crc);

/** Abort an in-progress load: discard its partial bytes. A previously
 *  committed buffer (if any) survives untouched (spec rule 3). */
void buf_load_abort(void);

/** True while a binary load is being received. */
bool buf_loading(void);

/* ---- TX chunk reads (wrap at the arena boundary) ---------------------------- */

/** Copy n bytes starting at absolute stream position @p offset into out,
 *  wrapping modulo BUF_CAPACITY (packet k of size L reads offset k*L).
 *  Reads are over the full 4096-byte arena: LEN may exceed the staged length
 *  (unstaged arena bytes are whatever buf_clear left there). Returns n. */
uint16_t buf_read(uint32_t offset, uint8_t* out, uint16_t n);

#ifdef __cplusplus
}
#endif

#endif /* E80_BUFFER_H */
