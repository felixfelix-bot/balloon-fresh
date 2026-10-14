/**
 * @file    pram_patch.c
 * @brief   LR2021 PRAM (patch-RAM) upload — portable implementation.
 *          See pram_patch.h for the ExpressLRS provenance and semantics.
 */

#include <stddef.h>

#include "pram_patch.h"

#include "lr20xx_hal.h"
#include "lr20xx_regmem.h"

/* Diagnostic state (also the bench-visible evidence trail). */
static bool     patch_on = false;
static int      last_status = -1;
static int      last_verify_mismatch = -1;
static int32_t  last_verify_addr = -1;
static int32_t  last_verify_value = -1;
static uint32_t load_calls = 0;

/* Status-code offsets so a bench log says WHICH call failed. */
#define PRAM_ST_WRITE_BASE   1000
#define PRAM_ST_ENABLE_BASE  2000
#define PRAM_ST_VERIFY_BASE  3000

/* Weak default so a host test can link the radio path (radio_bench.c calls
 * pram_patch_apply) without dragging in the STM32 platform file: the strong
 * definition in src/pram_patch_platform.c (HAL_Delay) wins in the firmware,
 * and the tests that care about the settle time define their own. */
__attribute__((weak)) void pram_patch_platform_delay_ms(uint32_t ms)
{
    (void)ms;
}

uint32_t pram_patch_chunk_count(uint32_t total, uint32_t chunk)
{
    if (chunk == 0u)
        return 0u;
    return (total + chunk - 1u) / chunk;
}

uint32_t pram_patch_chunk_words(uint32_t idx, uint32_t total, uint32_t chunk)
{
    uint32_t start;
    uint32_t remaining;

    if (chunk == 0u)
        return 0u;
    start = idx * chunk;
    if (start >= total)
        return 0u;
    remaining = total - start;
    return (remaining > chunk) ? chunk : remaining;
}

uint32_t pram_patch_chunk_addr(uint32_t idx, uint32_t chunk)
{
    return PRAM_PATCH_BASE_ADDR + (idx * chunk * 4u);
}

uint32_t pram_patch_table_crc32(void)
{
    /* CRC32 (reflected 0xEDB88320), init/xorout 0xFFFFFFFF — matches
     * zlib.crc32() over the big-endian word bytes (see gen_pram_table.py). */
    uint32_t crc = 0xFFFFFFFFu;
    uint32_t i;
    uint8_t  b;

    for (i = 0u; i < PRAM_PATCH_WORDS; i++)
    {
        uint32_t w = pram_patch_table[i];
        for (b = 0u; b < 4u; b++)
        {
            uint8_t byte = (uint8_t)(w >> (24u - 8u * b));
            crc ^= byte;
            for (uint8_t k = 0u; k < 8u; k++)
            {
                if (crc & 1u)
                    crc = (crc >> 1) ^ 0xEDB88320u;
                else
                    crc >>= 1;
            }
        }
    }
    return crc ^ 0xFFFFFFFFu;
}

bool pram_patch_enabled(void)
{
    return patch_on;
}

void pram_patch_set_enabled(bool on)
{
    patch_on = on;
}

int pram_patch_last_status(void)
{
    return last_status;
}

int pram_patch_last_verify_mismatch(void)
{
    return last_verify_mismatch;
}

int32_t pram_patch_last_verify_addr(void)
{
    return last_verify_addr;
}

int32_t pram_patch_last_verify_value(void)
{
    return last_verify_value;
}

uint32_t pram_patch_load_count(void)
{
    return load_calls;
}

int pram_patch_load(void* ctx)
{
    uint32_t chunks = pram_patch_chunk_count(PRAM_PATCH_WORDS, PRAM_PATCH_CHUNK_WORDS);
    uint32_t i;

    load_calls++;
    /* Fresh attempt: clear the previous attempt's verdict. */
    last_status = -1;
    last_verify_mismatch = -1;
    last_verify_addr = -1;
    last_verify_value = -1;

    for (i = 0u; i < chunks; i++)
    {
        uint32_t       addr = pram_patch_chunk_addr(i, PRAM_PATCH_CHUNK_WORDS);
        uint32_t       n = pram_patch_chunk_words(i, PRAM_PATCH_WORDS, PRAM_PATCH_CHUNK_WORDS);
        const uint32_t* src = &pram_patch_table[i * PRAM_PATCH_CHUNK_WORDS];
        int            st;

        if (n == 0u)
            break;
        st = (int)lr20xx_regmem_write_regmem32(ctx, addr, src, (uint8_t)n);
        if (st != 0)
        {
            last_status = PRAM_ST_WRITE_BASE + st;
            return last_status;
        }
    }

    {
        /* PATCH_ENABLE_PRAM_OC (0x012D) with the single payload byte 0x00.
         * ExpressLRS issues this through its raw command path
         * (LR2021Patch.cpp:70 -> hal.WriteCommand(..., 10000)); the vendored
         * driver exposes the same two-stage HAL write, so the byte stream on
         * the wire is identical: 0x01 0x2D 0x00. */
        uint8_t cmd[3];
        int     st;

        cmd[0] = (uint8_t)(PRAM_PATCH_ENABLE_OC >> 8);
        cmd[1] = (uint8_t)(PRAM_PATCH_ENABLE_OC & 0xFFu);
        cmd[2] = 0x00u;

        st = (int)lr20xx_hal_write(ctx, cmd, (uint16_t)sizeof(cmd), NULL, 0u);
        if (st != 0)
        {
            last_status = PRAM_ST_ENABLE_BASE + st;
            return last_status;
        }
    }

    pram_patch_platform_delay_ms(PRAM_PATCH_SETTLE_MS);

    last_status = 0;
    return 0;
}

int pram_patch_verify(void* ctx)
{
    uint32_t chunks = pram_patch_chunk_count(PRAM_PATCH_WORDS, PRAM_PATCH_CHUNK_WORDS);
    uint32_t i;
    int      mismatches = 0;

    last_verify_mismatch = -1;
    last_verify_addr = -1;
    last_verify_value = -1;

    for (i = 0u; i < chunks; i++)
    {
        uint32_t  addr = pram_patch_chunk_addr(i, PRAM_PATCH_CHUNK_WORDS);
        uint32_t  n = pram_patch_chunk_words(i, PRAM_PATCH_WORDS, PRAM_PATCH_CHUNK_WORDS);
        uint32_t  rd[PRAM_PATCH_CHUNK_WORDS];
        uint32_t  k;
        int       st;

        if (n == 0u)
            break;
        for (k = 0u; k < n; k++)
            rd[k] = 0u;
        st = (int)lr20xx_regmem_read_regmem32(ctx, addr, rd, (uint8_t)n);
        if (st != 0)
        {
            last_status = PRAM_ST_VERIFY_BASE + st;
            return -1;
        }
        for (k = 0u; k < n; k++)
        {
            uint32_t expect = pram_patch_table[i * PRAM_PATCH_CHUNK_WORDS + k];
            if (rd[k] != expect)
            {
                if (mismatches == 0)
                {
                    last_verify_addr = (int32_t)(addr + 4u * k);
                    last_verify_value = (int32_t)rd[k];
                }
                mismatches++;
            }
        }
    }

    last_verify_mismatch = mismatches;
    return mismatches;
}

int pram_patch_apply(void* ctx)
{
    int st = pram_patch_load(ctx);

    if (st != 0)
        return st;
    (void)pram_patch_verify(ctx); /* advisory: never fails the load */
    return 0;
}
