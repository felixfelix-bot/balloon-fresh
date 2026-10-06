/**
 * @file    flrc_range_host_cmd.h
 * @brief   Pure console command parser for the host-driven range bench (FW-2).
 *
 * Port of E80 bench_cmd.{c,h} (tokenizer, bench_strcaseeq, parse_u32/i8,
 * overflow guards) adapted to plan §1 REV-2 grammar:
 *   - adds standalone LEN / N / GAP commands
 *   - drops BAND / FLASH / ARM TX and START kwargs (START is bare; the
 *     standalone commands carry burst config — REV-2 "standalone-arg grammar")
 *   - MOD FLRC takes <br_kbps> only (no dbm arg)
 *   - FREQ band check 863..870 MHz baked in (EU SRD LF hard clamp, §1)
 *   - POWER MODE OUTDOOR pin (==2026) validated at parse time
 *
 * ZERO Arduino includes: this TU compiles identically in the RP2040 firmware
 * and in the host unit tests (firmware/rp2040/host-tests/).
 *
 * Error model (§1): every failure is one of
 *   ARG           malformed structure / bad or missing argument
 *   RANGE         syntactically valid value out of allowed range
 *   BUSY          config change while a session is active    (dispatch, FW-6)
 *   INHIBITED     START without ROLE TX|RX set               (dispatch, FW-6)
 *   POWER-LOCKED  PA > 10 dBm without OUTDOOR unlock         (dispatch, FW-6)
 *   UNKNOWN       unrecognized command word
 * The parser itself only emits OK / ARG / RANGE / UNKNOWN; BUSY, INHIBITED
 * and POWER-LOCKED depend on runtime state and are produced by the FW-6
 * dispatch layer. The enum + err_str live here so the reply vocabulary is
 * defined exactly once.
 *
 * Port provenance: ~/repos/balloon-e80bench/firmware/e80-stm32-bench/src/bench_cmd.{c,h}
 */

#ifndef FLRC_RANGE_HOST_CMD_H
#define FLRC_RANGE_HOST_CMD_H

#include <stdint.h>
#include <stdbool.h>

#include "flrc_range_host_types.h" /* bench_mod_t */

#ifdef __cplusplus
extern "C" {
#endif

/* --- token limits (mirrors E80 bench_cmd.h) ------------------------------ */
#define RH_CMD_MAX_TOKENS 8
#define RH_CMD_ARG_MAX 24

/* --- range constants (plan §1; single source of truth for FW-6/HS) ------- */
#define RH_FREQ_MIN_HZ 863000000UL   /* EU SRD lower edge (LF hard clamp)   */
#define RH_FREQ_MAX_HZ 870000000UL   /* EU SRD upper edge                   */
#define RH_PA_MIN_DBM (-18)          /* PA floor                            */
#define RH_PA_MAX_DBM 22             /* PA ceiling                          */
#define RH_PA_UNLOCK_THRESHOLD_DBM 10 /* dbm > 10 needs OUTDOOR unlock (FW-6) */
#define RH_LEN_MIN 8UL               /* payload bytes (4B seq + payload)    */
#define RH_LEN_MAX 255UL             /* FLRC FIFO max                       */
#define RH_N_MIN 1UL                 /* packets per burst                   */
#define RH_N_MAX 1000000UL
#define RH_GAP_MIN_US 100UL          /* inter-packet gap                    */
#define RH_GAP_MAX_US 100000000UL
#define RH_POWER_PIN 2026UL          /* POWER MODE OUTDOOR magic pin        */

typedef enum
{
    RH_CMD_NONE = 0,
    RH_CMD_ID,             /* ID?                                  */
    RH_CMD_ROLE,           /* ROLE TX|RX|NONE                      */
    RH_CMD_MOD,            /* MOD FLRC <br_kbps> | LORA <sf> <bw>  */
    RH_CMD_FREQ,           /* FREQ <hz>                            */
    RH_CMD_PA,             /* PA <dbm>                             */
    RH_CMD_LEN,            /* LEN <bytes>                          */
    RH_CMD_N,              /* N <count>                            */
    RH_CMD_GAP,            /* GAP <us>                             */
    RH_CMD_POWER_OUTDOOR,  /* POWER MODE OUTDOOR <pin>             */
    RH_CMD_START,          /* START (bare — uses LEN/N/GAP state)  */
    RH_CMD_STOP,           /* STOP                                 */
    RH_CMD_STAT,           /* STAT?                                */
    RH_CMD_HELP,           /* HELP | ?                             */
} rh_cmd_id_t;

typedef enum
{
    RH_ROLE_NONE = 0,
    RH_ROLE_RX,
    RH_ROLE_TX,
} rh_role_t;

typedef enum
{
    RH_CMD_OK = 0,
    RH_CMD_E_ARG,           /* malformed structure / bad or missing arg */
    RH_CMD_E_RANGE,         /* value out of allowed range               */
    RH_CMD_E_BUSY,          /* session active (dispatch layer, FW-6)    */
    RH_CMD_E_INHIBITED,     /* TX inhibited (dispatch layer, FW-6)      */
    RH_CMD_E_POWER_LOCKED,  /* PA > 10 locked (dispatch layer, FW-6)    */
    RH_CMD_E_UNKNOWN,       /* unknown command word                     */
} rh_cmd_err_t;

typedef struct rh_cmd_s
{
    rh_cmd_id_t  id;
    rh_cmd_err_t err;

    rh_role_t   role;      /* ROLE                                  */
    bench_mod_t mod;       /* MOD                                   */

    uint8_t  sf;           /* MOD LORA: 5..12                       */
    uint32_t bw_hz;        /* MOD LORA: 125000/250000/500000        */
    uint32_t br_bps;       /* MOD FLRC: 260000..2600000             */
    int8_t   txpow_dbm;    /* PA: -18..+22                          */

    uint32_t freq_hz;      /* FREQ: 863000000..870000000            */
    uint32_t pin;          /* POWER MODE OUTDOOR: == 2026           */

    uint32_t len_bytes;    /* LEN: 8..255                           */
    uint32_t n_pkts;       /* N: 1..1000000                         */
    uint32_t gap_us;       /* GAP: 100..100000000                   */
} rh_cmd_t;

/**
 * @brief Parse one newline-stripped command line (case-insensitive).
 *
 * @param line NUL-terminated input (trailing \r\n tolerated).
 * @param out  Parsed command. On failure out->id==RH_CMD_NONE and the
 *             return value / out->err carry the error class.
 * @return RH_CMD_OK on success.
 */
rh_cmd_err_t rh_cmd_parse(const char* line, rh_cmd_t* out);

/** String form of an error class, for "ERR <reason>" replies. */
const char* rh_cmd_err_str(rh_cmd_err_t e);

/**
 * @brief True for commands that change radio configuration and therefore
 * require the full re-init sequence (rfSwitchBitrate) when applied while
 * IDLE, and ERR BUSY while a session is active (§1 re-init rule; FW-6).
 * MOD / FREQ / PA / LEN — not N / GAP (burst pacing, no radio re-apply).
 */
bool rh_cmd_is_config(rh_cmd_id_t id);

/**
 * @brief Split a line into space/tab-separated tokens (whitespace runs
 * collapsed, \r\n stripped). Exposed so tests can lock the plan §1 STAT?
 * example line tokens (FW-2 acceptance vector).
 *
 * @param tokens    caller-provided array of RH_CMD_ARG_MAX-char buffers.
 * @param max_tokens size of the array (use > RH_CMD_MAX_TOKENS for long
 *                protocol lines such as the STAT? reply).
 * @param ntok     number of tokens written.
 * @return RH_CMD_OK, or RH_CMD_E_ARG on too-many / too-long tokens.
 */
rh_cmd_err_t rh_cmd_tokenize(const char* line, char tokens[][RH_CMD_ARG_MAX],
                             int max_tokens, int* ntok);

/** Case-insensitive token compare (exposed for tests). */
int rh_strcaseeq(const char* a, const char* b);

/** Parse uint32 decimal; returns false on garbage/overflow. */
bool rh_parse_u32(const char* s, uint32_t* out);

/** Parse int8 (allows leading '-' or '+'); returns false on garbage. */
bool rh_parse_i8(const char* s, int8_t* out);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* FLRC_RANGE_HOST_CMD_H */
