/**
 * @file    bench_cmd.h
 * @brief   Portable text-protocol command parser for the E80 bench firmware.
 *
 * No dynamic allocation, no STM32 dependency: compiled into both the firmware
 * and the host unit tests.
 *
 * Protocol: newline-terminated ASCII lines, space-separated tokens,
 * case-insensitive commands. Replies are "OK [...]" / "ERR <reason>".
 */

#ifndef E80_BENCH_CMD_H
#define E80_BENCH_CMD_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define E80_CMD_MAX_TOKENS 8
#define E80_CMD_MAX_CHARS 96
#define E80_CMD_ARG_MAX 24

typedef enum bench_cmd_id_e
{
    BENCH_CMD_NONE = 0,
    BENCH_CMD_ID,            /* ID? */
    BENCH_CMD_ROLE,          /* ROLE TX|RX|NONE */
    BENCH_CMD_ARM_TX,        /* ARM TX (two-step TX enable, step 2) */
    BENCH_CMD_MOD,           /* MOD loRa <sf> <bw> | flrc <br_kbps> <dbm> */
    BENCH_CMD_FREQ,          /* FREQ <hz> */
    BENCH_CMD_BAND_OVERRIDE, /* BAND OVERRIDE <pin> */
    BENCH_CMD_POWER_OUTDOOR,/* POWER MODE OUTDOOR <pin> — lifts indoor +10 dBm cap to +22 */
    BENCH_CMD_PA,            /* PA <dbm> */
    BENCH_CMD_START,         /* START N=<pkts> LEN=<bytes> GAP=<us> */
    BENCH_CMD_STAT,          /* STAT? */
    BENCH_CMD_STOP,          /* STOP */
    BENCH_CMD_FLASH,         /* FLASH — jump to the STM32F1 ROM bootloader */
    BENCH_CMD_HELP,          /* HELP */
    BENCH_CMD_SESSION,       /* SESSION <id> — set session_id for PKT lines */
    BENCH_CMD_CONFIG,        /* CONFIG <id> <replicate> — set config_id/replicate */
    BENCH_CMD_PRBS9,         /* PRBS9 ON|OFF — chip-level PRBS9 TX test mode */
    BENCH_CMD_PRBS,          /* PRBS ON|OFF — toggle PRBS-15 RX verification */
    BENCH_CMD_BUF_CLEAR,     /* BUF CLEAR — drop the staged TX buffer (len=0) */
    BENCH_CMD_BUF_LOAD,      /* BUF LOAD <n> <crc16_hex> — binary payload receive */
    BENCH_CMD_BUF_STATUS,    /* BUF STATUS — staged len/crc report */
} bench_cmd_id_t;

typedef enum bench_role_e
{
    BENCH_ROLE_NONE = 0,
    BENCH_ROLE_RX,
    BENCH_ROLE_TX,
} bench_role_t;

typedef enum bench_mod_e
{
    BENCH_MOD_LORA = 0,
    BENCH_MOD_FLRC,
} bench_mod_t;

typedef enum bench_cmd_err_e
{
    BENCH_CMD_OK = 0,
    BENCH_CMD_E_SYNTAX,    /* malformed line */
    BENCH_CMD_E_ARG,       /* bad/missing argument */
    BENCH_CMD_E_RANGE,     /* value out of range */
    BENCH_CMD_E_UNKNOWN,   /* unknown command word */
} bench_cmd_err_t;

typedef struct bench_cmd_s
{
    bench_cmd_id_t id;
    bench_cmd_err_t err;

    bench_role_t role;   /* ROLE */
    bench_mod_t  mod;    /* MOD */

    uint8_t  sf;         /* MOD loRa: 5..12 */
    uint32_t bw_hz;      /* MOD loRa: 125000/250000/500000 */
    uint32_t br_bps;     /* MOD flrc: 260000..2600000 */
    int8_t   txpow_dbm;  /* MOD flrc / PA: dBm */

    uint32_t freq_hz;    /* FREQ */
    uint32_t pin;        /* BAND OVERRIDE */

    uint32_t n_pkts;     /* START */
    uint32_t len_bytes;
    uint32_t gap_us;
    bool     has_n, has_len, has_gap;

    uint32_t session_id;  /* SESSION <id> */
    uint32_t config_id;   /* CONFIG <id> <replicate> */
    uint32_t replicate;   /* CONFIG <id> <replicate> */
    bool     prbs9_enable; /* PRBS9 ON|OFF */
    bool     prbs_enable;  /* PRBS ON|OFF — enable PRBS-15 RX verification */

    uint32_t buf_load_n;   /* BUF LOAD <n>: payload byte count (1..4096) */
    uint16_t buf_load_crc; /* BUF LOAD <n> <crc16_hex>: expected CCITT-FALSE CRC */
} bench_cmd_t;

/**
 * @brief Parse one newline-stripped command line.
 *
 * @param line  NUL-terminated input (no trailing \r\n required; tolerated).
 * @param out   Parsed command; out->id==BENCH_CMD_NONE and out->err!=OK on failure.
 * @return bench_cmd_err_t BENCH_CMD_OK on success.
 */
bench_cmd_err_t bench_cmd_parse(const char* line, bench_cmd_t* out);

/** String form of a parse error (for "ERR <reason>"). */
const char* bench_cmd_err_str(bench_cmd_err_t e);

/** Case-insensitive token compare helper (exposed for tests). */
int bench_strcaseeq(const char* a, const char* b);

/** Parse uint32 decimal; returns false on garbage/overflow. */
bool bench_parse_u32(const char* s, uint32_t* out);

/** Parse int8 (allows leading '-'); returns false on garbage. */
bool bench_parse_i8(const char* s, int8_t* out);

/**
 * START per-modulation LEN caps (docs/rca-fix-plan-20260821.md BUG 1):
 * LoRa payloads are capped at 255 B (uint8_t pkt-param silicon limit in the
 * lr20xx driver), FLRC at 511 B.
 */
#define BENCH_START_LEN_MAX_LORA 255u
#define BENCH_START_LEN_MAX_FLRC 511u

/**
 * @brief Per-modulation START LEN gate — true iff LEN=<len> is legal for <mod>.
 *
 * FIX-T2 parity rule: BOTH the TX and the RX START branches must reject with
 * the same predicate, so both boards answer identically to an out-of-cap LEN.
 */
bool bench_start_len_ok(bench_mod_t mod, uint32_t len);

/**
 * @brief Exact ERR reason string for a per-mod LEN violation
 *        ("LEN (MAX 255 LORA / 511 FLRC)"). Single source for both branches.
 */
const char* bench_start_len_err_str(void);

#ifdef __cplusplus
}
#endif

#endif /* E80_BENCH_CMD_H */
