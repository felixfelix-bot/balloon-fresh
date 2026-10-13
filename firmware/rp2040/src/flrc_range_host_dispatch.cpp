/**
 * @file    flrc_range_host_dispatch.cpp
 * @brief   FW-6 implementation — see flrc_range_host_dispatch.h for the
 *          decision table and semantics. Pure TU: zero Arduino includes.
 *
 * Port provenance: ~/repos/balloon-e80bench/firmware/e80-stm32-bench/src/
 * bench.c apply path (config-store + BUSY/INHIBITED gating), restructured
 * into a plan-returning pure function so the whole decision table runs in
 * host unit tests (M1: dispatch independent of the Arduino main TU).
 */

#include "flrc_range_host_dispatch.h"
#include "flrc_range_host_safety.h"   /* band + PA cap policy (FW-4) */

#include <stdio.h>
#include <string.h>

/* --- helpers ---------------------------------------------------------------- */

static const char* role_str(rh_role_t r)
{
    switch (r)
    {
    case RH_ROLE_TX:  return "TX";
    case RH_ROLE_RX:  return "RX";
    default:          return "NONE";
    }
}

static rh_plan_t plan_err(rh_cmd_err_t e)
{
    rh_plan_t p;
    memset(&p, 0, sizeof(p));
    p.action = RH_PLAN_NONE;
    p.err    = e;
    p.band_aware = false;
    return p;
}

static rh_plan_t plan_ok(rh_plan_action_t a, bool band_aware)
{
    rh_plan_t p;
    memset(&p, 0, sizeof(p));
    p.action = a;
    p.err    = RH_CMD_OK;
    p.band_aware = band_aware;
    return p;
}

/* --- state ------------------------------------------------------------------ */

void bench_state_init(bench_state_t* st, const char* fw_hash)
{
    memset(st, 0, sizeof(*st));
    st->fw_hash = (fw_hash != NULL) ? fw_hash : "";
    st->session = RH_SESSION_IDLE;
    st->role    = RH_ROLE_NONE;
    st->mod     = BENCH_MOD_FLRC;
    st->br_bps  = 650000UL;      /* §1 STAT example boot config */
    st->freq_hz = 869525000UL;
    st->dbm     = 10;            /* indoor cap: legal without unlock */
    st->len_bytes = 51;
    st->n_pkts  = 1000;
    st->gap_us  = 5000;
    st->outdoor_unlocked = false;
    /* stats zeroed by memset */
}

/* --- dispatch ---------------------------------------------------------------- */

rh_plan_t bench_apply_cmd(bench_state_t* st, const rh_cmd_t* cmd)
{
    if (cmd == NULL || st == NULL)
        return plan_err(RH_CMD_E_ARG);

    /* Parse failures propagate; the state is untouched. */
    if (cmd->id == RH_CMD_NONE)
        return plan_err(cmd->err != RH_CMD_OK ? cmd->err : RH_CMD_E_ARG);

    switch (cmd->id)
    {
    /* ---- queries: always OK, never BUSY (usable mid-burst) ---- */
    case RH_CMD_ID:
    case RH_CMD_HELP:
    case RH_CMD_STAT:
        return plan_ok(RH_PLAN_NONE, false);

    /* ---- ROLE: applied while IDLE, frozen while ACTIVE ---- */
    case RH_CMD_ROLE:
        if (st->session == RH_SESSION_ACTIVE)
            return plan_err(RH_CMD_E_BUSY);
        st->role = cmd->role;
        return plan_ok(RH_PLAN_NONE, false);

    /* ---- POWER unlock: sticky flag, frozen while ACTIVE ---- */
    case RH_CMD_POWER_OUTDOOR:
        if (st->session == RH_SESSION_ACTIVE)
            return plan_err(RH_CMD_E_BUSY);
        st->outdoor_unlocked = true; /* parser guarantees pin == 2026 */
        return plan_ok(RH_PLAN_NONE, false);

    /* ---- config commands: REINIT_FULL while IDLE, BUSY while ACTIVE ---- */
    case RH_CMD_MOD:
    {
        if (st->session == RH_SESSION_ACTIVE)
            return plan_err(RH_CMD_E_BUSY);
        /* Parser guarantees the parameter ranges; detect any applied
         * delta to derive the band-aware flag. */
        bool changed = (st->mod != cmd->mod) ||
                       (cmd->mod == BENCH_MOD_FLRC &&
                        st->br_bps != cmd->br_bps) ||
                       (cmd->mod == BENCH_MOD_LORA &&
                        (st->sf != cmd->sf || st->bw_hz != cmd->bw_hz));
        st->mod    = cmd->mod;
        st->br_bps = cmd->br_bps;
        st->sf     = cmd->sf;
        st->bw_hz  = cmd->bw_hz;
        return plan_ok(RH_PLAN_REINIT_FULL, changed);
    }

    case RH_CMD_FREQ:
    {
        if (st->session == RH_SESSION_ACTIVE)
            return plan_err(RH_CMD_E_BUSY);
        /* Defense in depth: the parser already clamps to 863..870 MHz;
         * a hand-built cmd that skipped it is still caught here. */
        if (!bench_safety_freq_in_eu_band(cmd->freq_hz))
            return plan_err(RH_CMD_E_RANGE);
        bool changed = (st->freq_hz != cmd->freq_hz);
        st->freq_hz = cmd->freq_hz;
        return plan_ok(RH_PLAN_REINIT_FULL, changed);
    }

    case RH_CMD_PA:
    {
        if (st->session == RH_SESSION_ACTIVE)
            return plan_err(RH_CMD_E_BUSY);
        if (cmd->txpow_dbm < RH_PA_MIN_DBM || cmd->txpow_dbm > RH_PA_MAX_DBM)
            return plan_err(RH_CMD_E_RANGE);
        /* > 10 dBm needs the outdoor unlock (LF cap policy, FW-4). */
        if (!bench_safety_pa_allowed(cmd->txpow_dbm, st->outdoor_unlocked))
            return plan_err(RH_CMD_E_POWER_LOCKED);
        st->dbm = cmd->txpow_dbm;
        return plan_ok(RH_PLAN_REINIT_FULL, false);
    }

    case RH_CMD_LEN:
    {
        if (st->session == RH_SESSION_ACTIVE)
            return plan_err(RH_CMD_E_BUSY);
        if (cmd->len_bytes < RH_LEN_MIN || cmd->len_bytes > RH_LEN_MAX)
            return plan_err(RH_CMD_E_RANGE);
        st->len_bytes = cmd->len_bytes;
        return plan_ok(RH_PLAN_REINIT_FULL, false);
    }

    /* ---- burst pacing: applied while IDLE, frozen while ACTIVE ---- */
    case RH_CMD_N:
        if (st->session == RH_SESSION_ACTIVE)
            return plan_err(RH_CMD_E_BUSY);
        if (cmd->n_pkts < RH_N_MIN || cmd->n_pkts > RH_N_MAX)
            return plan_err(RH_CMD_E_RANGE);
        st->n_pkts = cmd->n_pkts;
        return plan_ok(RH_PLAN_NONE, false);

    case RH_CMD_GAP:
        if (st->session == RH_SESSION_ACTIVE)
            return plan_err(RH_CMD_E_BUSY);
        if (cmd->gap_us < RH_GAP_MIN_US || cmd->gap_us > RH_GAP_MAX_US)
            return plan_err(RH_CMD_E_RANGE);
        st->gap_us = cmd->gap_us;
        return plan_ok(RH_PLAN_NONE, false);

    /* ---- session control ---- */
    case RH_CMD_START:
        if (st->session == RH_SESSION_ACTIVE)
            return plan_err(RH_CMD_E_BUSY);
        if (st->role == RH_ROLE_NONE)
            return plan_err(RH_CMD_E_INHIBITED); /* two-step TX inhibit */
        /* New session: stats from any previous burst are wiped. Engines
         * (FW-7/8) stamp t_start_us / t_stop_us around the burst. */
        bench_stats_reset(&st->stats);
        st->session = RH_SESSION_ACTIVE;
        return plan_ok(RH_PLAN_START_BURST, false);

    case RH_CMD_STOP:
        if (st->session == RH_SESSION_ACTIVE)
        {
            st->session = RH_SESSION_IDLE; /* abort -> standby */
            /* stats deliberately RETAINED until the next START */
            return plan_ok(RH_PLAN_STOP, false);
        }
        /* STOP while standby: OK, nothing to abort, stats kept. */
        return plan_ok(RH_PLAN_NONE, false);

    default:
        return plan_err(RH_CMD_E_UNKNOWN);
    }
}

/* --- replies ----------------------------------------------------------------- */

void bench_format_id(const bench_state_t* st, char* buf, size_t n)
{
    snprintf(buf, n, "ID range-host v1 fw=%s role=%s",
             st->fw_hash ? st->fw_hash : "", role_str(st->role));
}

const char* bench_help_text(void)
{
    return
        "CMDS: ID? | ROLE TX|RX|NONE | MOD FLRC <br_kbps> | MOD LORA <sf> <bw_khz> "
        "| FREQ <hz 863000000-870000000> | PA <dbm -18..22> | LEN <8-255> "
        "| N <1-1000000> | GAP <us> | POWER MODE OUTDOOR 2026 | START | STOP "
        "| STAT? | HELP|?\n"
        "NOTES: config while session active = ERR BUSY; START needs ROLE "
        "TX|RX first; PA>10dBm needs POWER MODE OUTDOOR unlock; "
        "STOP aborts to standby and stats are RETAINED until next START "
        "(START resets them).";
}

bool bench_format_reply(const bench_state_t* st, const rh_cmd_t* cmd,
                        const rh_plan_t* plan, char* buf, size_t n)
{
    if (plan->err != RH_CMD_OK)
    {
        snprintf(buf, n, "ERR %s", rh_cmd_err_str(plan->err));
        return true;
    }

    switch (cmd->id)
    {
    case RH_CMD_ID:
        bench_format_id(st, buf, n);
        return true;

    case RH_CMD_HELP:
        snprintf(buf, n, "%s", bench_help_text());
        return true;

    case RH_CMD_ROLE:
        snprintf(buf, n, "OK ROLE %s", role_str(st->role));
        return true;

    case RH_CMD_MOD:
        if (st->mod == BENCH_MOD_LORA)
            snprintf(buf, n, "OK MOD LORA sf=%u bw_hz=%lu",
                     (unsigned)st->sf, (unsigned long)st->bw_hz);
        else
            snprintf(buf, n, "OK MOD FLRC br_hz=%lu",
                     (unsigned long)st->br_bps);
        return true;

    case RH_CMD_FREQ:
        snprintf(buf, n, "OK FREQ %lu", (unsigned long)st->freq_hz);
        return true;

    case RH_CMD_PA:
        snprintf(buf, n, "OK PA %d", (int)st->dbm);
        return true;

    case RH_CMD_LEN:
        snprintf(buf, n, "OK LEN %lu", (unsigned long)st->len_bytes);
        return true;

    case RH_CMD_N:
        snprintf(buf, n, "OK N %lu", (unsigned long)st->n_pkts);
        return true;

    case RH_CMD_GAP:
        snprintf(buf, n, "OK GAP %lu", (unsigned long)st->gap_us);
        return true;

    case RH_CMD_POWER_OUTDOOR:
        snprintf(buf, n, "OK POWER OUTDOOR");
        return true;

    case RH_CMD_START:
        if (st->role == RH_ROLE_TX)
            snprintf(buf, n, "OK START n=%lu len=%lu gap_us=%lu",
                     (unsigned long)st->n_pkts, (unsigned long)st->len_bytes,
                     (unsigned long)st->gap_us);
        else
            snprintf(buf, n, "OK START RX");
        return true;

    case RH_CMD_STOP:
        snprintf(buf, n, "OK STOP");
        return true;

    default:
        /* STAT? and anything else: no FW-6 single-line reply (FW-9). */
        return false;
    }
}
