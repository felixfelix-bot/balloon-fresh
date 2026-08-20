/**
 * @file    test_buffer.c
 * @brief   Host unit tests: TX payload buffer module (task BUF-T1, TDD RED).
 *
 * Covers (per docs/plans/tx-buffer-spec.md and the task matrix):
 *   - CRC-16/CCITT-FALSE golden vectors (shared with
 *     tools/test_crc16_golden.py - C and Python must agree)
 *   - BUF LOAD reject matrix gate (role==RX / burst / armed) + exact reply
 *     strings; precedence ROLE > BURST > ARMED; STOP does NOT clear armed
 *   - staging lifecycle: begin/feed/commit, CRC-fail clears len (rule 5:
 *     stale-partial forbidden), abort preserves the previously committed
 *     buffer (rule 3), clear, begin range guards
 *   - wrap chunk reads: N=64 (4096/64 exact, no straddle), N=65 and N=100
 *     (first straddling chunks), N=50 (spec correction: 4096/50=81.92, first
 *     wrap at chunk 81, offset 4050 - NOT N=50 half-arena), LEN>staged
 *   - PRBS fallback semantics: fallback iff buf_len()==0
 *
 * TDD: fails against the RED stubs in src/buffer.c. Task BUF-T2 implements
 * the module (GREEN).
 */

#include "buffer.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

#define CHECK(cond)                                                              \
    do                                                                           \
    {                                                                            \
        if (!(cond))                                                             \
        {                                                                        \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);               \
            failures++;                                                          \
        }                                                                        \
    } while (0)

/* Golden CRC constants — MUST match tools/test_crc16_golden.py exactly. */
#define GOLDEN_123456789 0x29B1u
#define GOLDEN_64_ZEROS 0xD6DAu
#define GOLDEN_4096_INC 0x0F69u
#define GOLDEN_ABCD 0xBFFAu

/* Non-periodic arena fill: differs when pos wraps by 4096 (period of a
 * byte function under +256 is invisible at wrap distance 4096; (i ^ i>>8)
 * has no such period), so a non-wrapping read is observably wrong. */
static uint8_t fill2(uint32_t pos)
{
    return (uint8_t)(pos ^ (pos >> 8));
}

/* Stage n bytes with a self-consistent CRC (the CRC algorithm itself is
 * pinned independently by the golden vectors above). */
static bool stage_bytes(const uint8_t* d, uint16_t n)
{
    if (!buf_load_begin(n))
        return false;
    for (uint16_t i = 0; i < n; i++)
        buf_load_byte(d[i]);
    return buf_load_commit(crc16_ccitt_false(d, n));
}

/* ---- CRC-16/CCITT-FALSE golden vectors ------------------------------------- */

static void test_crc16_golden(void)
{
    CHECK(crc16_ccitt_false((const uint8_t*)"123456789", 9) == GOLDEN_123456789);

    uint8_t zeros[64];
    memset(zeros, 0, sizeof(zeros));
    CHECK(crc16_ccitt_false(zeros, sizeof(zeros)) == GOLDEN_64_ZEROS);

    uint8_t inc[BUF_CAPACITY];
    for (uint32_t i = 0; i < BUF_CAPACITY; i++)
        inc[i] = (uint8_t)(i % 256);
    CHECK(crc16_ccitt_false(inc, BUF_CAPACITY) == GOLDEN_4096_INC);

    /* No data processed: the init register value comes through. */
    CHECK(crc16_ccitt_false(zeros, 0) == 0xFFFF);

    /* Used by the console framing tests (test_console_binary.c). */
    CHECK(crc16_ccitt_false((const uint8_t*)"ABCD", 4) == GOLDEN_ABCD);
}

/* ---- BUF LOAD gate (reject matrix) ------------------------------------------ */

static void test_gate_matrix(void)
{
    /* Fresh idle board, role NONE: LOAD allowed (only role==RX rejects). */
    CHECK(buf_load_gate(false, false, false) == BUF_LOAD_OK);

    /* role==RX: TX buffer is TX-side only. */
    CHECK(buf_load_gate(true, false, false) == BUF_LOAD_ERR_ROLE);

    /* TX burst in flight: STOP FIRST. */
    CHECK(buf_load_gate(false, true, false) == BUF_LOAD_ERR_BURST);

    /* TX armed — including the after-STOP cell: STOP does NOT clear armed;
     * only a ROLE change unlocks (spec decision). */
    CHECK(buf_load_gate(false, false, true) == BUF_LOAD_ERR_ARMED);

    /* Precedence on stacked rejects: ROLE > BURST > ARMED. */
    CHECK(buf_load_gate(true, true, true) == BUF_LOAD_ERR_ROLE);
    CHECK(buf_load_gate(false, true, true) == BUF_LOAD_ERR_BURST);
}

static void test_gate_reply_strings(void)
{
    CHECK(strcmp(buf_load_gate_reply(BUF_LOAD_ERR_ROLE),
                 "ERR ROLE RX (TX BUFFER IS TX-SIDE ONLY)") == 0);
    CHECK(strcmp(buf_load_gate_reply(BUF_LOAD_ERR_BURST),
                 "ERR TX BURST ACTIVE (STOP FIRST)") == 0);
    CHECK(strcmp(buf_load_gate_reply(BUF_LOAD_ERR_ARMED),
                 "ERR TX ARMED (STOP DOES NOT CLEAR ARMED - ROLE CHANGE TO UNLOCK)") == 0);

    /* OK needs no canned line: the handler proceeds to the binary ack. */
    CHECK(buf_load_gate_reply(BUF_LOAD_OK) == NULL);
}

/* ---- Staging lifecycle ------------------------------------------------------- */

static void test_staging_lifecycle(void)
{
    uint8_t tmp[64];

    /* Fresh state: nothing staged -> PRBS fallback on TX (src=PRBS). */
    CHECK(buf_len() == 0);
    CHECK(buf_loading() == false);
    CHECK(buf_drops() == 0);

    /* begin: n within 1..4096 only. */
    CHECK(buf_load_begin(0) == false);
    CHECK(buf_loading() == false);
    CHECK(buf_load_begin(BUF_CAPACITY + 1) == false);
    CHECK(buf_loading() == false);

    /* Stage 64 zero bytes; nothing counts until commit. */
    CHECK(buf_load_begin(64) == true);
    CHECK(buf_loading() == true);
    CHECK(buf_len() == 0);
    for (int i = 0; i < 64; i++)
        buf_load_byte(0);
    CHECK(buf_load_commit(GOLDEN_64_ZEROS) == true);
    CHECK(buf_loading() == false);
    CHECK(buf_len() == 64);
    CHECK(buf_crc16() == GOLDEN_64_ZEROS);

    /* Staged content is readable (and buf_read returns n). */
    CHECK(buf_read(0, tmp, 16) == 16);
    for (int i = 0; i < 16; i++)
        CHECK(tmp[i] == 0);

    /* CLEAR drops the buffer. */
    buf_clear();
    CHECK(buf_len() == 0);
    CHECK(buf_crc16() == 0);

    /* CRC-fail clears len (rule 5: stale-partial forbidden) -> PRBS fallback. */
    CHECK(buf_load_begin(4) == true);
    buf_load_byte('A');
    buf_load_byte('B');
    buf_load_byte('C');
    buf_load_byte('D');
    CHECK(buf_load_commit(0xDEAD) == false);
    CHECK(buf_len() == 0);
    CHECK(buf_crc16() == 0);

    /* A failed load does not poison the next one. */
    const uint8_t abcd[4] = {'A', 'B', 'C', 'D'};
    CHECK(stage_bytes(abcd, 4) == true);
    CHECK(buf_len() == 4); /* staged -> TX uses src=BUF */
    CHECK(buf_read(0, tmp, 4) == 4);
    CHECK(memcmp(tmp, "ABCD", 4) == 0);

    /* Abort discards the partial load, keeps the committed buffer (rule 3). */
    CHECK(buf_load_begin(8) == true);
    buf_load_byte(0x11);
    buf_load_byte(0x22);
    buf_load_abort();
    CHECK(buf_loading() == false);
    CHECK(buf_len() == 4);
    CHECK(buf_read(0, tmp, 4) == 4);
    CHECK(memcmp(tmp, "ABCD", 4) == 0);

    /* Defensive: commit/feed with no load in progress are inert. */
    CHECK(buf_load_commit(GOLDEN_ABCD) == false);
    buf_load_byte(0x33);
    CHECK(buf_loading() == false);
    CHECK(buf_len() == 4);

    CHECK(buf_drops() == 0); /* clean flow never drops */
}

/* ---- Wrap chunk reads --------------------------------------------------------- */

static void test_wrap_chunks(void)
{
    uint8_t out[300];

    /* First: the full-arena golden CRC staging (4096 x i%256 -> 0x0F69). */
    uint8_t inc[BUF_CAPACITY];
    for (uint32_t i = 0; i < BUF_CAPACITY; i++)
        inc[i] = (uint8_t)(i % 256);
    CHECK(buf_load_begin(BUF_CAPACITY) == true);
    for (uint32_t i = 0; i < BUF_CAPACITY; i++)
        buf_load_byte(inc[i]);
    CHECK(buf_load_commit(GOLDEN_4096_INC) == true);
    CHECK(buf_len() == BUF_CAPACITY);

    /* Re-stage with the non-periodic fill for observable wrap checks. */
    uint8_t f[BUF_CAPACITY];
    for (uint32_t i = 0; i < BUF_CAPACITY; i++)
        f[i] = fill2(i);
    CHECK(stage_bytes(f, BUF_CAPACITY) == true);
    CHECK(buf_len() == BUF_CAPACITY);

    /* --- N=64: 4096/64 = 64 exact — chunks never straddle the boundary --- */
    /* chunk 63: offset 4032, ends at 4095, no wrap */
    CHECK(buf_read(63u * 64u, out, 64) == 64);
    for (int i = 0; i < 64; i++)
        CHECK(out[i] == fill2(4032u + (uint32_t)i));
    /* chunk 64: offset 4096 -> wraps to arena[0] */
    CHECK(buf_read(64u * 64u, out, 64) == 64);
    for (int i = 0; i < 64; i++)
        CHECK(out[i] == fill2((uint32_t)i));
    /* chunk 65: offset 4160 -> arena[64] */
    CHECK(buf_read(65u * 64u, out, 64) == 64);
    for (int i = 0; i < 64; i++)
        CHECK(out[i] == fill2(64u + (uint32_t)i));
    /* chunk 0 sanity */
    CHECK(buf_read(0, out, 64) == 64);
    for (int i = 0; i < 64; i++)
        CHECK(out[i] == fill2((uint32_t)i));

    /* --- N=65: first straddling chunk is 63 (offset 63*65=4095) --- */
    CHECK(buf_read(63u * 65u, out, 65) == 65);
    CHECK(out[0] == fill2(4095)); /* last arena byte ... */
    for (int i = 1; i < 65; i++)
        CHECK(out[i] == fill2((uint32_t)(i - 1))); /* ... then wrapped */
    /* chunk 64: offset 4160 -> starts at arena[4160-4096=64] */
    CHECK(buf_read(64u * 65u, out, 65) == 65);
    for (int i = 0; i < 65; i++)
        CHECK(out[i] == fill2(64u + (uint32_t)i));

    /* --- N=100: first straddling chunk is 40 (offset 4000, wraps after 96) --- */
    CHECK(buf_read(40u * 100u, out, 100) == 100);
    for (int i = 0; i < 96; i++)
        CHECK(out[i] == fill2(4000u + (uint32_t)i));
    for (int i = 96; i < 100; i++)
        CHECK(out[i] == fill2((uint32_t)(i - 96)));

    /* --- N=50 spec correction: 4096/50 = 81.92 -> first wrap at chunk 81
     *      (offset 4050, 46 bytes then 4 wrapped), NOT a half-arena rule --- */
    CHECK(buf_read(81u * 50u, out, 50) == 50);
    for (int i = 0; i < 46; i++)
        CHECK(out[i] == fill2(4050u + (uint32_t)i));
    for (int i = 46; i < 50; i++)
        CHECK(out[i] == fill2((uint32_t)(i - 46)));

    CHECK(buf_drops() == 0);
}

/* ---- LEN may exceed the staged bytes (wrap arena) ----------------------------- */

static void test_len_exceeds_staged(void)
{
    uint8_t out[300];
    const uint8_t ten[10] = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'};

    buf_clear();
    CHECK(stage_bytes(ten, 10) == true);
    CHECK(buf_len() == 10);

    /* LEN=255 with only 10 staged: still 255 bytes out; prefix is the staged
     * data (rest is unstaged arena — content not pinned, wrap is). */
    CHECK(buf_read(0, out, 255) == 255);
    CHECK(memcmp(out, "0123456789", 10) == 0);

    /* PRBS fallback: only when len==0 (never mid-buffer). */
    CHECK(buf_len() != 0); /* src=BUF here */
    buf_clear();
    CHECK(buf_len() == 0); /* src=PRBS from here */
}

int main(void)
{
    test_crc16_golden();
    test_gate_matrix();
    test_gate_reply_strings();
    test_staging_lifecycle();
    test_wrap_chunks();
    test_len_exceeds_staged();

    if (failures == 0)
    {
        printf("test_buffer: ALL PASS\n");
        return 0;
    }
    printf("test_buffer: %d FAILURES\n", failures);
    return 1;
}
