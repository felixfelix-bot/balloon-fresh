/**
 * @file    test_bench_pram.c
 * @brief   Host unit tests for the PRAM-patch port (RFA-1b).
 *
 * Host-compiles the REAL src/pram_patch.c + the generated table against the
 * REAL vendored lr20xx_regmem.c over a fake lr20xx HAL that models PRAM as a
 * 560-word memory. Pins:
 *
 *   - the table is byte-identical to ExpressLRS LR2021PRAM.h (CRC32 golden
 *     value produced independently by python3 zlib.crc32 —
 *     tools/gen_pram_table.py prints the same constant),
 *   - chunk math: 46 x 12 words + 1 x 8 words = 560, addresses 0x801000 + i*48,
 *   - the on-wire sequence: REGMEM32 (0x0104) writes carrying the exact table
 *     words big-endian, then PATCH_ENABLE_PRAM_OC (0x012D) with payload 0x00,
 *     then the settle delay,
 *   - failure propagation (write / enable status codes) and the advisory
 *     read-back verify (clean + corrupted model).
 */

#include "pram_patch.h"

#include "lr20xx_hal.h"
#include "lr20xx_regmem.h"

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

/* ---- fake lr20xx HAL: PRAM modelled as 560 words ------------------------- */

#define MODEL_BASE 0x801000u
#define CAP_MAX 64
#define CAP_HDR_MAX 8
#define CAP_DATA_MAX 48

static uint32_t model[PRAM_PATCH_WORDS];

static uint8_t  cap_hdr[CAP_MAX][CAP_HDR_MAX];
static uint8_t  cap_data[CAP_MAX][CAP_DATA_MAX];
static uint16_t cap_hdr_len[CAP_MAX];
static uint16_t cap_data_len[CAP_MAX];
static int      cap_n = 0;

static int      delay_calls = 0;
static uint32_t delay_ms_total = 0;

/* Fault injection. */
static int write_fail_after = -1;  /* fail the Nth hal_write (0-based) */
static int read_fail = 0;

static void cap_reset(void)
{
    cap_n = 0;
    delay_calls = 0;
    delay_ms_total = 0;
    write_fail_after = -1;
    read_fail = 0;
}

void pram_patch_platform_delay_ms(uint32_t ms)
{
    delay_calls++;
    delay_ms_total += ms;
}

/* Apply one captured REGMEM32 write to the PRAM model, so the fake behaves
 * like a device that actually stores what it is told (verify() then reads
 * back a truthful image rather than the recorder's echo). */
static void model_apply_one(const uint8_t* command, uint16_t command_length,
                            const uint8_t* data, uint16_t data_length)
{
    uint32_t addr;
    int      words;
    int      k;

    if (command_length != 5 || command[0] != 0x01 || command[1] != 0x04)
        return;
    addr = ((uint32_t)command[2] << 16) | ((uint32_t)command[3] << 8) | command[4];
    if (addr < MODEL_BASE)
        return;
    words = data_length / 4;
    for (k = 0; k < words; k++)
    {
        uint32_t w = ((uint32_t)data[4 * k + 0] << 24) | ((uint32_t)data[4 * k + 1] << 16) |
                     ((uint32_t)data[4 * k + 2] << 8) | ((uint32_t)data[4 * k + 3]);
        uint32_t idx = (addr - MODEL_BASE) / 4u + (uint32_t)k;
        if (idx < PRAM_PATCH_WORDS)
            model[idx] = w;
    }
}

lr20xx_hal_status_t lr20xx_hal_write(const void* context, const uint8_t* command,
                                    const uint16_t command_length,
                                    const uint8_t* data, const uint16_t data_length)
{
    (void)context;

    if (write_fail_after >= 0 && cap_n >= write_fail_after)
        return LR20XX_HAL_STATUS_ERROR;

    if (cap_n < CAP_MAX)
    {
        if (command_length <= CAP_HDR_MAX)
        {
            memcpy(cap_hdr[cap_n], command, command_length);
            cap_hdr_len[cap_n] = command_length;
        }
        if (data != NULL && data_length <= CAP_DATA_MAX)
        {
            memcpy(cap_data[cap_n], data, data_length);
            cap_data_len[cap_n] = data_length;
        }
    }
    cap_n++;
    model_apply_one(command, command_length, data, data_length);
    return LR20XX_HAL_STATUS_OK;
}

lr20xx_hal_status_t lr20xx_hal_read(const void* context, const uint8_t* command,
                                   const uint16_t command_length,
                                   uint8_t* data, const uint16_t data_length)
{
    uint32_t addr;
    uint16_t words;
    uint16_t i;

    (void)context;
    (void)command_length;

    if (read_fail)
        return LR20XX_HAL_STATUS_ERROR;

    /* reqmem read: [0]=0x01 [1]=0x06 [2..4]=addr [5]=len(words) */
    addr = ((uint32_t)command[2] << 16) | ((uint32_t)command[3] << 8) | command[4];
    words = command[5];
    if (data_length != (uint16_t)(words * 4u))
        return LR20XX_HAL_STATUS_ERROR;

    for (i = 0; i < words; i++)
    {
        uint32_t w = (addr >= MODEL_BASE && ((addr - MODEL_BASE) / 4u + i) < PRAM_PATCH_WORDS)
                         ? model[(addr - MODEL_BASE) / 4u + i]
                         : 0u;
        data[4 * i + 0] = (uint8_t)(w >> 24);
        data[4 * i + 1] = (uint8_t)(w >> 16);
        data[4 * i + 2] = (uint8_t)(w >> 8);
        data[4 * i + 3] = (uint8_t)(w);
    }
    return LR20XX_HAL_STATUS_OK;
}

lr20xx_hal_status_t lr20xx_hal_direct_read(const void* context, uint8_t* data,
                                          const uint16_t data_length)
{
    (void)context;
    memset(data, 0, data_length);
    return LR20XX_HAL_STATUS_OK;
}

lr20xx_hal_status_t lr20xx_hal_direct_read_fifo(const void* context, const uint8_t* command,
                                               const uint16_t command_length,
                                               uint8_t* data, const uint16_t data_length)
{
    (void)context;
    (void)command;
    (void)command_length;
    memset(data, 0, data_length);
    return LR20XX_HAL_STATUS_OK;
}

lr20xx_hal_status_t lr20xx_hal_reset(const void* context)
{
    (void)context;
    return LR20XX_HAL_STATUS_OK;
}

lr20xx_hal_status_t lr20xx_hal_wakeup(const void* context)
{
    (void)context;
    return LR20XX_HAL_STATUS_OK;
}

/* Apply every captured REGMEM32 write to the model so a load() leaves the
 * model equal to the table (the fake is a faithful device, not a recorder). */
static void model_apply_captured(void)
{
    int i;

    memset(model, 0, sizeof(model));
    for (i = 0; i < cap_n; i++)
    {
        uint32_t addr;
        int      words;
        int      k;

        if (cap_hdr_len[i] != 5 || cap_hdr[i][0] != 0x01 || cap_hdr[i][1] != 0x04)
            continue;
        addr = ((uint32_t)cap_hdr[i][2] << 16) | ((uint32_t)cap_hdr[i][3] << 8) | cap_hdr[i][4];
        if (addr < MODEL_BASE)
            continue;
        words = cap_data_len[i] / 4;
        for (k = 0; k < words; k++)
        {
            uint32_t w = ((uint32_t)cap_data[i][4 * k + 0] << 24) |
                         ((uint32_t)cap_data[i][4 * k + 1] << 16) |
                         ((uint32_t)cap_data[i][4 * k + 2] << 8) |
                         ((uint32_t)cap_data[i][4 * k + 3]);
            uint32_t idx = (addr - MODEL_BASE) / 4u + (uint32_t)k;
            if (idx < PRAM_PATCH_WORDS)
                model[idx] = w;
        }
    }
}

/* ---- 1. table provenance ------------------------------------------------- */

static void test_table_provenance(void)
{
    /* Golden CRC32 of the ELRS LR2021PRAM.h table (python3 zlib.crc32 over the
     * big-endian word bytes; tools/gen_pram_table.py prints the same value). */
    CHECK(PRAM_PATCH_WORDS == 560u);
    CHECK(pram_patch_table_crc32() == 0x44FCC3B2u);
    /* Boundary words straight out of LR2021PRAM.h. */
    CHECK(pram_patch_table[0] == 0x600db002u);
    CHECK(pram_patch_table[559] == 0xf9fffff9u);
    /* A middle word, so a truncated/reordered table cannot pass on the
     * boundaries alone. */
    CHECK(pram_patch_table[9] == 0x0ff82184u);
}

/* ---- 2. chunk math ------------------------------------------------------- */

static void test_chunk_math(void)
{
    uint32_t i;
    uint32_t total = 0u;

    CHECK(pram_patch_chunk_count(PRAM_PATCH_WORDS, PRAM_PATCH_CHUNK_WORDS) == 47u);
    CHECK(pram_patch_chunk_addr(0u, PRAM_PATCH_CHUNK_WORDS) == 0x801000u);
    CHECK(pram_patch_chunk_addr(1u, PRAM_PATCH_CHUNK_WORDS) == 0x801030u);
    CHECK(pram_patch_chunk_addr(46u, PRAM_PATCH_CHUNK_WORDS) == 0x8018A0u);
    CHECK(pram_patch_chunk_words(46u, PRAM_PATCH_WORDS, PRAM_PATCH_CHUNK_WORDS) == 8u);

    for (i = 0u; i < 47u; i++)
        total += pram_patch_chunk_words(i, PRAM_PATCH_WORDS, PRAM_PATCH_CHUNK_WORDS);
    CHECK(total == PRAM_PATCH_WORDS);

    /* Out-of-range / degenerate inputs. */
    CHECK(pram_patch_chunk_words(47u, PRAM_PATCH_WORDS, PRAM_PATCH_CHUNK_WORDS) == 0u);
    CHECK(pram_patch_chunk_count(0u, 12u) == 0u);
    CHECK(pram_patch_chunk_count(10u, 0u) == 0u);
}

/* ---- 3. wire sequence ---------------------------------------------------- */

static void test_load_wire_sequence(void)
{
    int writes_0x0104 = 0;
    int enable = 0;
    int i;

    cap_reset();
    memset(model, 0, sizeof(model));

    CHECK(pram_patch_load((void*)0x1234) == 0);
    CHECK(cap_n == 47 + 1); /* 46 full chunks + 1 short chunk + the enable cmd */

    for (i = 0; i < cap_n; i++)
    {
        if (cap_hdr_len[i] == 5 && cap_hdr[i][0] == 0x01 && cap_hdr[i][1] == 0x04)
        {
            uint32_t addr = ((uint32_t)cap_hdr[i][2] << 16) |
                            ((uint32_t)cap_hdr[i][3] << 8) | cap_hdr[i][4];
            CHECK(addr == pram_patch_chunk_addr((uint32_t)writes_0x0104, PRAM_PATCH_CHUNK_WORDS));
            CHECK(cap_data_len[i] == (uint16_t)(pram_patch_chunk_words(
                                         (uint32_t)writes_0x0104, PRAM_PATCH_WORDS,
                                         PRAM_PATCH_CHUNK_WORDS) *
                                     4u));
            writes_0x0104++;
        }
        else if (cap_hdr_len[i] == 3 && cap_hdr[i][0] == 0x01 && cap_hdr[i][1] == 0x2D)
        {
            CHECK(enable == 0); /* exactly once, last */
            CHECK(i == cap_n - 1);
            CHECK(cap_data_len[i] == 0u); /* payload byte rides in the header */
            enable = 1;
        }
    }
    CHECK(writes_0x0104 == 47);
    CHECK(enable == 1);
    CHECK(delay_calls == 1);
    CHECK(delay_ms_total == PRAM_PATCH_SETTLE_MS);
    CHECK(pram_patch_last_status() == 0);
    CHECK(pram_patch_load_count() == 1u);

    /* The image the device received equals the table, word for word. */
    model_apply_captured();
    CHECK(memcmp(model, pram_patch_table, sizeof(model)) == 0);
}

/* ---- 4. read-back verify ------------------------------------------------- */

static void test_verify_clean_and_corrupt(void)
{
    cap_reset();
    memset(model, 0, sizeof(model));
    CHECK(pram_patch_load((void*)0) == 0);
    model_apply_captured();

    CHECK(pram_patch_verify((void*)0) == 0);
    CHECK(pram_patch_last_verify_mismatch() == 0);
    CHECK(pram_patch_last_verify_addr() == -1);

    /* One word corrupted on the device side -> reported with address/value. */
    model[100] = pram_patch_table[100] ^ 0x1u;
    CHECK(pram_patch_verify((void*)0) == 1);
    CHECK(pram_patch_last_verify_mismatch() == 1);
    CHECK(pram_patch_last_verify_addr() == (int32_t)(0x801000u + 4u * 100u));
    CHECK(pram_patch_last_verify_value() == (int32_t)(pram_patch_table[100] ^ 0x1u));

    /* Read failure -> -1, no false "clean". */
    read_fail = 1;
    CHECK(pram_patch_verify((void*)0) == -1);
    CHECK(pram_patch_last_verify_mismatch() == -1);
}

/* ---- 5. apply + failure propagation ------------------------------------- */

static void test_apply_and_failures(void)
{
    cap_reset();
    memset(model, 0, sizeof(model));
    CHECK(pram_patch_apply((void*)0) == 0);
    model_apply_captured();
    CHECK(pram_patch_last_verify_mismatch() == 0);

    /* Write failure mid-image: reported, no enable command issued. */
    cap_reset();
    write_fail_after = 5;
    CHECK(pram_patch_load((void*)0) != 0);
    CHECK(pram_patch_last_status() >= 1000);
    CHECK(pram_patch_last_status() < 2000);
    CHECK(delay_calls == 0);

    /* Enable-command failure: distinguished from a write failure. */
    cap_reset();
    write_fail_after = 47;
    CHECK(pram_patch_load((void*)0) != 0);
    CHECK(pram_patch_last_status() >= 2000);
    CHECK(delay_calls == 0);

    cap_reset();
}

/* ---- 6. flag semantics --------------------------------------------------- */

static void test_flag(void)
{
    CHECK(pram_patch_enabled() == false); /* default: current (unpatched) path */
    pram_patch_set_enabled(true);
    CHECK(pram_patch_enabled() == true);
    pram_patch_set_enabled(false);
    CHECK(pram_patch_enabled() == false);
}

int main(void)
{
    test_table_provenance();
    test_chunk_math();
    test_load_wire_sequence();
    test_verify_clean_and_corrupt();
    test_apply_and_failures();
    test_flag();

    if (failures == 0)
    {
        printf("PASS test_bench_pram\n");
        return 0;
    }
    printf("%d FAILURE(S)\n", failures);
    return 1;
}
