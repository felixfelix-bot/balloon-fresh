/**
 * @file    pram_patch.h
 * @brief   LR2021 PRAM (patch-RAM) upload — port of ExpressLRS LoadPatchRAM.
 *
 * ExpressLRS uploads a 560-word patch image unconditionally in
 * LR2021Driver::Begin() (LR2021.cpp:112 -> LR2021Patch.cpp:42-71):
 *
 *   - 560 x uint32 words from src/lib/LR2021Driver/LR2021PRAM.h
 *   - written to PRAM base 0x801000 with the REGMEM32 write opcode (0x0104)
 *     in 12-word chunks (12 words + 5-byte header = 53 B, inside the 64 B
 *     SPI frame the radio can take)
 *   - then LR2021_PATCH_ENABLE_PRAM_OC (0x012D) with a single payload byte
 *     0x00, followed by a 10 ms settle
 *
 * Our bench firmware never did this (RFA-1 audit, docs/RFA1-ELRS-LR2021-DIFF-
 * 2026-10-12.md Q5). This module ports it behind a runtime flag so ONE binary
 * can run both experiment arms (patch off = current behaviour, patch on = the
 * ExpressLRS sequence).
 *
 * The portable half (chunk math, table CRC, flag, load/verify sequencing)
 * has zero STM32 dependencies and is host-tested; the platform delay is the
 * only external symbol (src/pram_patch_platform.c in the firmware, a stub in
 * the host tests).
 */

#ifndef E80_PRAM_PATCH_H
#define E80_PRAM_PATCH_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Words in the PRAM image (LR2021PRAM.h: pram_lr2021[560]). */
#define PRAM_PATCH_WORDS 560u

/** Words per REGMEM32 write (ExpressLRS: 12 words + 5 B header <= 64 B). */
#define PRAM_PATCH_CHUNK_WORDS 12u

/** PRAM base address (LR2021Patch.cpp:9). */
#define PRAM_PATCH_BASE_ADDR 0x801000u

/** LR2021_PATCH_ENABLE_PRAM_OC (LR2021_Regs.h:93). */
#define PRAM_PATCH_ENABLE_OC 0x012Du

/** Settle time after the enable command (ExpressLRS: 10 ms). */
#define PRAM_PATCH_SETTLE_MS 10u

/** The patch image itself (src/pram_patch_table.c, generated). */
extern const uint32_t pram_patch_table[PRAM_PATCH_WORDS];

/** Platform delay hook (HAL_Delay in the firmware; test stub on the host). */
void pram_patch_platform_delay_ms(uint32_t ms);

/* ---- portable helpers (host-tested) ------------------------------------ */

/** Number of chunks needed to write <total> words at <chunk> words per call. */
uint32_t pram_patch_chunk_count(uint32_t total, uint32_t chunk);

/** Words in chunk <idx> (the final chunk may be short; 0 when out of range). */
uint32_t pram_patch_chunk_words(uint32_t idx, uint32_t total, uint32_t chunk);

/** PRAM address of chunk <idx> = base + idx * chunk * 4. */
uint32_t pram_patch_chunk_addr(uint32_t idx, uint32_t chunk);

/** CRC32 (IEEE 802.3: reflected, init 0xFFFFFFFF, xorout 0xFFFFFFFF) over the
 *  table, words serialised big-endian — the same bytes the SPI frame carries.
 *  Used as the build/provenance attestation printed in ID? and by the host
 *  unit test (golden value from the ELRS header: see tools/gen_pram_table.py). */
uint32_t pram_patch_table_crc32(void);

/* ---- runtime state ------------------------------------------------------ */

/** Patch flag (PATCH ON|OFF). Applies at the next chip bring-up. */
bool pram_patch_enabled(void);
void pram_patch_set_enabled(bool on);

/** 0 = last load clean, >0 = status code of the failing call, -1 = never run. */
int pram_patch_last_status(void);

/** Mismatched words in the last read-back verify (-1: never run / read error). */
int pram_patch_last_verify_mismatch(void);

/** Address of the first mismatching word in the last verify (-1 when none). */
int32_t pram_patch_last_verify_addr(void);

/** Value read back at that address (-1 when none). */
int32_t pram_patch_last_verify_value(void);

/** Number of load attempts (liveness: proves the bring-up path ran). */
uint32_t pram_patch_load_count(void);

/* ---- device-side transfers --------------------------------------------- */

/**
 * @brief Upload the PRAM image and enable the overlay.
 *
 * Write opcode 0x0104 chunk-by-chunk, then 0x012D with payload 0x00 and a
 * PRAM_PATCH_SETTLE_MS delay. Records diagnostics for the getters above.
 * @param ctx lr20xx driver context.
 * @return 0 on success, non-zero (offset status code) on the first failure.
 */
int pram_patch_load(void* ctx);

/**
 * @brief Read the PRAM image back and count mismatches (advisory evidence).
 *
 * @return mismatch count (0 = byte-identical), or -1 when a read call failed.
 */
int pram_patch_verify(void* ctx);

/**
 * @brief load() + verify(): what the bring-up path calls when the flag is on.
 * @return 0 when the load succeeded (verify is reported, not fatal).
 */
int pram_patch_apply(void* ctx);

#ifdef __cplusplus
}
#endif

#endif /* E80_PRAM_PATCH_H */
