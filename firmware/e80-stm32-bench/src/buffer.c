/**
 * @file    buffer.c
 * @brief   TX payload buffer for the E80 bench firmware (task BUF-T2, GREEN).
 *
 * Implements the contract pinned by buffer.h / tests/test_buffer.c (task
 * BUF-T1) per docs/plans/tx-buffer-spec.md:
 *   - bitwise CRC-16/CCITT-FALSE (golden vectors shared with Python)
 *   - BUF LOAD gate: reject matrix with ROLE > BURST > ARMED precedence
 *   - staging lifecycle: begin/byte/commit/abort; CRC-fail clears len
 *     (rule 5, stale-partial forbidden); abort keeps a committed buffer
 *     (rule 3); committed buffer survives STOP / ROLE change
 *   - wrap-at-arena-boundary chunk reads (packet k of size L: offset k*L)
 */

#include "buffer.h"

#include <stddef.h>

/* Committed staged payload, double-buffered so an in-flight load stages
 * into scratch and a previously committed buffer survives ABORT / timeout
 * byte-exact (spec rule 3; pinned by test_buffer.c:184). Commit success
 * swaps the active index — no copy. 2 x 4096 B static.
 * buf_clear() drops only len/crc: unstaged bytes stay readable when LEN
 * exceeds the staged length (spec: wrap arena). */
static uint8_t  arena[2][BUF_CAPACITY];
static uint8_t  arena_active; /* index of the committed buffer */
static uint16_t staged_len;
static uint16_t staged_crc;
static uint32_t drop_count;

/* In-progress binary load (driven by the console binary phase). */
static bool     load_active;
static uint16_t load_n;
static uint16_t load_got;

uint16_t crc16_ccitt_false(const uint8_t* data, uint32_t len)
{
    /* Bitwise: poly 0x1021, init 0xFFFF, MSB-first, no reflection, no xorout.
     * Golden vectors (shared with tools/test_crc16_golden.py):
     *   "123456789" -> 0x29B1   64 x 0x00 -> 0xD6DA   4096 x (i%256) -> 0x0F69 */
    uint16_t crc = 0xFFFF;
    for (uint32_t i = 0; i < len; i++)
    {
        crc ^= (uint16_t)((uint16_t)data[i] << 8);
        for (int bit = 0; bit < 8; bit++)
            crc = (crc & 0x8000u) ? (uint16_t)((uint16_t)(crc << 1) ^ 0x1021u)
                                  : (uint16_t)(crc << 1);
    }
    return crc;
}

buf_load_gate_t buf_load_gate(bool role_is_rx, bool burst_active, bool tx_armed)
{
    if (role_is_rx)
        return BUF_LOAD_ERR_ROLE;
    if (burst_active)
        return BUF_LOAD_ERR_BURST;
    if (tx_armed)
        return BUF_LOAD_ERR_ARMED;
    return BUF_LOAD_OK;
}

const char* buf_load_gate_reply(buf_load_gate_t g)
{
    switch (g)
    {
    case BUF_LOAD_ERR_ROLE:  return "ERR ROLE RX (TX BUFFER IS TX-SIDE ONLY)";
    case BUF_LOAD_ERR_BURST: return "ERR TX BURST ACTIVE (STOP FIRST)";
    case BUF_LOAD_ERR_ARMED: return "ERR TX ARMED (STOP DOES NOT CLEAR ARMED - ROLE CHANGE TO UNLOCK)";
    default:                 return NULL; /* BUF_LOAD_OK: handler proceeds to the ack */
    }
}

void buf_clear(void)
{
    staged_len = 0;
    staged_crc = 0;
    /* Defensive: a CLEAR while a load is in flight also drops the partial.
     * Unreachable via the console (line assembly is suspended during the
     * binary phase), harmless as a direct-call safeguard. */
    load_active = false;
}

uint16_t buf_len(void)       { return staged_len; }
uint16_t buf_crc16(void)     { return staged_crc; }
uint32_t buf_drops(void)     { return drop_count; }
void     buf_note_drop(void) { drop_count++; }

bool buf_load_begin(uint16_t n)
{
    if (n == 0 || n > BUF_CAPACITY)
        return false;
    load_n      = n;
    load_got    = 0;
    load_active = true;
    return true;
}

void buf_load_byte(uint8_t b)
{
    if (!load_active || load_got >= load_n)
        return; /* inert without a load; extras past n are dropped */
    arena[arena_active ^ 1u][load_got++] = b; /* scratch, not committed */
}

bool buf_load_commit(uint16_t expected_crc)
{
    if (!load_active)
        return false; /* defensive: no load in progress */
    load_active = false;

    if (load_got != load_n)
    {
        /* Short load cannot CRC-match by construction; rule 5 applies. */
        staged_len = 0;
        staged_crc = 0;
        return false;
    }

    uint16_t crc = crc16_ccitt_false(arena[arena_active ^ 1u], load_n);
    if (crc != expected_crc)
    {
        staged_len = 0; /* stale-partial forbidden (spec rule 5) */
        staged_crc = 0;
        return false;
    }
    arena_active ^= 1u; /* scratch becomes the committed buffer */
    staged_len = load_n;
    staged_crc = crc;
    return true;
}

void buf_load_abort(void)
{
    /* Rule 3: only the partial in-flight load is discarded; a previously
     * committed buffer (if any) survives untouched. */
    load_active = false;
}

bool buf_loading(void) { return load_active; }

uint16_t buf_read(uint32_t offset, uint8_t* out, uint16_t n)
{
    const uint8_t* a = arena[arena_active];
    uint32_t pos = offset % BUF_CAPACITY;
    for (uint16_t i = 0; i < n; i++)
    {
        out[i] = a[pos];
        pos = (pos + 1u) % BUF_CAPACITY; /* wrap at the arena boundary */
    }
    return n;
}
