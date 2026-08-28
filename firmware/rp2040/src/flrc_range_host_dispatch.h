/**
 * @file    flrc_range_host_dispatch.h
 * @brief   FW-6: command dispatch layer — bench state machine, decision
 *          table, and §1 reply formatting for the host-driven range bench.
 *
 * PURE TU: zero Arduino / RP2040 SDK includes (M1 fix — the dispatch layer
 * must be host-testable independently of the Arduino main). Links against
 * the FW-2 parser, FW-4 safety checks and FW-3 stats types only.
 *
 * Model:
 *
 *   bench_apply_cmd(state, cmd) -> plan
 *
 * The caller parses a line (rh_cmd_parse, FW-2), hands the cmd + the shared
 * bench_state_t to the dispatcher, and receives an rh_plan_t saying what the
 * executor (main / engines) must do. The dispatcher itself mutates ONLY
 * protocol state — radio SPI traffic, burst engines and timestamps are the
 * executor's job (FW-5a backend, FW-7/8 engines):
 *
 *   RH_PLAN_REINIT_FULL   run the band-aware re-init (bench_radio_reinit)
 *   RH_PLAN_START_BURST   begin the burst for st->role (engine hookup FW-7/8)
 *   RH_PLAN_STOP          abort the active burst -> standby
 *   RH_PLAN_NONE          nothing (queries, ROLE / N / GAP / POWER, errors)
 *
 * Decision table (binding — t_561d8a41; every row locked in test_dispatch):
 *
 *   command             | IDLE                      | ACTIVE
 *   --------------------+---------------------------+------------------
 *   MOD / FREQ / PA/LEN | REINIT_FULL (band-aware?) | ERR BUSY
 *   ROLE / N / GAP      | applied, NONE             | ERR BUSY
 *   POWER OUTDOOR       | unlock applied, NONE      | ERR BUSY
 *   START               | see below                 | ERR BUSY
 *   STOP                | OK, NONE (nothing to do)  | STOP, stats kept
 *   ID? / HELP / STAT?  | OK, NONE                  | OK, NONE
 *
 *   START rules: role==NONE -> ERR INHIBITED (two-step TX inhibit, §1);
 *                otherwise stats are RESET for the new session and the
 *                state machine goes ACTIVE.
 *   STOP rules:  abort -> standby; stats are RETAINED (readable via STAT?)
 *                until the next START wipes them.
 *   PA rules:    -18..22 dBm at parse; > 10 dBm additionally requires the
 *                POWER MODE OUTDOOR unlock -> else ERR POWER-LOCKED.
 *   FREQ rules:  863..870 MHz at parse; re-checked here against
 *                bench_safety_freq_in_eu_band() (defense in depth).
 *
 * band_aware flag: true when the applied change touches the modulation /
 * front-end block — a MOD parameter delta (FLRC<->LoRa or bitrate/SF/BW
 * change) or a FREQ change (CALIB_FRONT_END parameter). The executor must
 * then run the full band-aware re-init (REV-2 B1), never a partial
 * modulation-only patch. PA / LEN changes re-apply without band matrix
 * bytes (flag false).
 *
 * Documented FW-6 extensions of §1 (see docs/evidence/stage-a/
 * fw6-dispatch-decision-table.md): ROLE / N / GAP / POWER are BUSY while a
 * session is active (§1 lists no error for them; freezing everything but
 * queries keeps burst parameters deterministic), and STOP while IDLE is OK
 * with no action (§1 has STOP -> standby, session frozen).
 */

#ifndef FLRC_RANGE_HOST_DISPATCH_H
#define FLRC_RANGE_HOST_DISPATCH_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>

#include "flrc_range_host_types.h"  /* bench_mod_t   */
#include "flrc_range_host_cmd.h"    /* rh_cmd_t, rh_role_t, rh_cmd_err_t */
#include "flrc_range_host_stats.h"  /* bench_stats_t */

#ifdef __cplusplus
extern "C" {
#endif

/* --- session -------------------------------------------------------------- */

typedef enum
{
    RH_SESSION_IDLE = 0,   /* standby, nothing running          */
    RH_SESSION_ACTIVE,     /* burst in progress (role TX or RX) */
} rh_session_t;

/* --- bench protocol state (owned by the dispatch layer) -------------------- */

typedef struct bench_state_s
{
    /* identity (ID? reply) */
    const char* fw_hash;      /* build id, injected at init (never freed) */

    /* session machine */
    rh_session_t session;
    rh_role_t    role;

    /* radio configuration (applied by REINIT_FULL / read at START) */
    bench_mod_t mod;
    uint32_t    freq_hz;      /* EU SRD 863..870 MHz              */
    uint32_t    br_bps;       /* FLRC: 260000..2600000            */
    uint8_t     sf;           /* LoRa: 5..12                      */
    uint32_t    bw_hz;        /* LoRa: 125000/250000/500000       */
    int8_t      dbm;          /* -18..+22 (cap policy below)      */
    uint32_t    len_bytes;    /* 8..255 payload                   */

    /* burst pacing (no radio re-apply) */
    uint32_t    n_pkts;       /* 1..1000000                       */
    uint32_t    gap_us;       /* inter-packet gap                 */

    /* safety unlock */
    bool        outdoor_unlocked; /* POWER MODE OUTDOOR 2026 (sticky) */

    /* session counters: RETAINED across STOP, RESET by START (§1). The
     * engines (FW-7/8) accumulate into these; t_start_us/t_stop_us are
     * theirs to stamp. */
    bench_stats_t stats;
} bench_state_t;

/* Boot defaults == the §1 STAT example config: FLRC 650 kbps @ 869.525 MHz,
 * 10 dBm (indoor cap), LEN 51 / N 1000 / GAP 5000. fw_hash is stored
 * verbatim (caller keeps it alive). */
void bench_state_init(bench_state_t* st, const char* fw_hash);

/* --- dispatch plan --------------------------------------------------------- */

typedef enum
{
    RH_PLAN_NONE = 0,
    RH_PLAN_REINIT_FULL,   /* re-apply radio config (band-aware if flag) */
    RH_PLAN_START_BURST,   /* engine: begin burst per st->role           */
    RH_PLAN_STOP,          /* engine: abort burst -> standby             */
} rh_plan_action_t;

typedef struct rh_plan_s
{
    rh_plan_action_t action;
    rh_cmd_err_t     err;        /* RH_CMD_OK or the §1 error class   */
    bool             band_aware;/* reinit must redo band/front-end
                                   matrix (MOD param or FREQ delta)  */
} rh_plan_t;

/**
 * @brief Apply one parsed command to the bench state and derive the plan.
 *
 * Pure protocol logic: no radio I/O, no clock reads, no engine calls.
 * On plan.err != RH_CMD_OK the state is guaranteed unchanged.
 */
rh_plan_t bench_apply_cmd(bench_state_t* st, const rh_cmd_t* cmd);

/* --- replies (§1) ----------------------------------------------------------- */

/* "ID range-host v1 fw=<hash> role=<NONE|RX|TX>" */
void bench_format_id(const bench_state_t* st, char* buf, size_t n);

/* Multi-line HELP text (command list + STOP-stats + PA-unlock notes — the
 * REV-2 "STOP semantics documented in HELP" minor). */
const char* bench_help_text(void);

/**
 * @brief Format the single-line reply for a command after dispatch.
 *
 * Covers ID? (via bench_format_id), HELP (full help text) and every
 * OK / ERR reply of the §1 grammar. Returns false when the command has no
 * FW-6 reply yet — STAT? (formatter lands with FW-9) — so the caller can
 * fall back.
 */
bool bench_format_reply(const bench_state_t* st, const rh_cmd_t* cmd,
                        const rh_plan_t* plan, char* buf, size_t n);

#ifdef __cplusplus
} /* extern "C" */
#endif

#endif /* FLRC_RANGE_HOST_DISPATCH_H */
