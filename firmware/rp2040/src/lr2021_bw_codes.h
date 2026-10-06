/**
 * @file    lr2021_bw_codes.h
 * @brief   BW-1: Authoritative LR2021 LoRa bandwidth code table — single
 *          source of truth shared by RP2040 firmware AND host scripts.
 *
 * Ground truth (vendored Semtech lr20xx_driver — read-only, do not edit):
 *   ~/repos/balloon-e80bench/firmware/e80-stm32-bench/third_party/Radio/
 *     lr20xx_driver/inc/lr20xx_radio_lora_types.h  L93-111 (BW enum codes)
 *     lr20xx_driver/src/lr20xx_radio_lora.c        L485-542 (get_bw_in_hz)
 *
 * SetModulationParams wire format (lr20xx_radio_lora.c L185-195):
 *   opcode 0x0220, cbuffer[2] = (sf << 4) + bw, cbuffer[3] = (cr << 4) + ppm
 *   (SF5..SF12 = 0x05..0x0C — SF equals its numeric value.)
 *
 * HOST SCRIPTS: tools/lr2021_bw_codes.py parses the LR2021_BW_TABLE X-macro
 * rows below at runtime. Keep the exact row format
 *     X(<khz_label>, <code>, <hz>UL)
 * and the BEGIN/END comment markers in sync with that parser. Do not edit
 * this table without re-diffing against the vendored driver files above.
 *
 * Reconciliation notes (see docs/bw-code-table.md):
 *   - lora_868_tx.cpp L63-69 (203/406/812 -> 0x0D/0x0E/0x0F): CORRECT subset.
 *   - dual_radio_sweep_tx.cpp L69 (0x05=250 kHz): CORRECT subset.
 *   - Codes 0x00-0x07 are the standard ladder (7.81k -> 1000k);
 *     codes 0x08-0x0F are the alternate ladder (10.42k -> 812k).
 *   - Hz values are the driver's get_bw_in_hz() constants (used for time-on-
 *     air math); datasheet nominals differ slightly for 203/406/812
 *     (203.125k/406.25k/812.5k).
 */

#ifndef LR2021_BW_CODES_H
#define LR2021_BW_CODES_H

#include <stdint.h>

/* Single-source table: (kHz label, wire code, driver Hz constant).
 * Ordered by code. khz_label is the label used on the bench console
 * (`MOD LORA <sf> <bw_khz>`) and matches the lr20xx enum suffixes. */
#define LR2021_BW_TABLE(X)                                                     \
    /* LR2021_BW_TABLE_BEGIN */                                                \
    X(7,    0x00,   7812UL)                                                    \
    X(15,   0x01,  15625UL)                                                    \
    X(31,   0x02,  31250UL)                                                    \
    X(62,   0x03,  62500UL)                                                    \
    X(125,  0x04, 125000UL)                                                    \
    X(250,  0x05, 250000UL)                                                    \
    X(500,  0x06, 500000UL)                                                    \
    X(1000, 0x07, 1000000UL)                                                   \
    X(10,   0x08,  10417UL)                                                    \
    X(20,   0x09,  20833UL)                                                    \
    X(41,   0x0A,  41667UL)                                                    \
    X(83,   0x0B,  83340UL)                                                    \
    X(101,  0x0C, 101563UL)                                                    \
    X(203,  0x0D, 203000UL)                                                    \
    X(406,  0x0E, 406000UL)                                                    \
    X(812,  0x0F, 812000UL)                                                    \
    /* LR2021_BW_TABLE_END */

/* LoRa bandwidth wire codes — values identical to lr20xx_radio_lora_bw_t. */
#define LR2021_BW_ENUM(name, code, hz) LR2021_LORA_BW_##name = code,
typedef enum
{
    LR2021_BW_TABLE(LR2021_BW_ENUM)
} lr2021_lora_bw_t;
#undef LR2021_BW_ENUM

/** Sentinel for "no such bandwidth". */
#define LR2021_BW_CODE_INVALID 0xFF

/** Number of table rows. */
#define LR2021_BW_COUNT 16U

/** Wire code -> driver Hz constant; 0 for unknown codes. */
static inline uint32_t lr2021_bw_code_to_hz(uint8_t code)
{
    switch (code)
    {
#define LR2021_BW_HZ_CASE(name, code_, hz) \
    case code_:                            \
        return hz;
        LR2021_BW_TABLE(LR2021_BW_HZ_CASE)
#undef LR2021_BW_HZ_CASE
    default:
        return 0U;
    }
}

/** Exact driver Hz constant -> wire code; LR2021_BW_CODE_INVALID if absent. */
static inline uint8_t lr2021_bw_hz_to_code(uint32_t hz)
{
    switch (hz)
    {
#define LR2021_BW_CODE_CASE(name, code_, hz) \
    case hz:                                 \
        return code_;
        LR2021_BW_TABLE(LR2021_BW_CODE_CASE)
#undef LR2021_BW_CODE_CASE
    default:
        return LR2021_BW_CODE_INVALID;
    }
}

/** Console kHz label (7,10,...,125,250,...,812,1000) -> wire code. */
static inline uint8_t lr2021_bw_khz_to_code(uint32_t khz)
{
    switch (khz)
    {
#define LR2021_BW_KHZ_CASE(name, code_, hz) \
    case name:                              \
        return code_;
        LR2021_BW_TABLE(LR2021_BW_KHZ_CASE)
#undef LR2021_BW_KHZ_CASE
    default:
        return LR2021_BW_CODE_INVALID;
    }
}

#endif /* LR2021_BW_CODES_H */
