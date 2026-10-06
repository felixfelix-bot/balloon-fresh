/**
 * @file    test_dispatch.cpp
 * @brief   Host unit tests: FW-6 dispatch layer — bench_apply_cmd decision
 *          table, STOP/stats retention semantics, ID?/HELP wiring, §1 reply
 *          formatting.
 *
 * Decision table is the binding kanban task list (t_561d8a41):
 *   - config cmd while IDLE   -> plan REINIT_FULL (state applied)
 *   - config cmd while ACTIVE -> ERR BUSY (state unchanged)
 *   - START before ROLE       -> ERR INHIBITED
 *   - PA > 10 without unlock  -> ERR POWER-LOCKED
 *   - FREQ out of EU band     -> ERR RANGE (parser + dispatch defense-in-depth)
 *   - MOD change              -> band-aware reinit flag set
 *   - STOP: abort -> standby, stats RETAINED until next START (START resets)
 *   - ID? / HELP wired through dispatch (format_id / help text)
 *
 * Pure TU: no Arduino includes — links dispatch + cmd + safety + stats TUs.
 */

#include "flrc_range_host_dispatch.h"

#include <stdio.h>
#include <string.h>

static int failures = 0;

#define CHECK(cond)                                                               \
    do                                                                            \
    {                                                                             \
        if (!(cond))                                                              \
        {                                                                         \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);                \
            failures++;                                                           \
        }                                                                         \
    } while (0)

/* Apply a parsed line through the dispatcher under test. */
static rh_plan_t apply(bench_state_t* st, const char* line)
{
    rh_cmd_t c;
    memset(&c, 0, sizeof(c));
    rh_cmd_parse(line, &c);
    return bench_apply_cmd(st, &c);
}

/* Role TX + START helper: put the state machine into an ACTIVE session. */
static void start_tx(bench_state_t* st)
{
    rh_plan_t p = apply(st, "ROLE TX");
    CHECK(p.err == RH_CMD_OK);
    p = apply(st, "START");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_START_BURST);
    CHECK(st->session == RH_SESSION_ACTIVE);
}

/* ------------------------------------------------------ boot state defaults */

static void test_state_defaults(void)
{
    bench_state_t st;
    bench_state_init(&st, "deadbeef");

    CHECK(st.session == RH_SESSION_IDLE);
    CHECK(st.role == RH_ROLE_NONE);
    CHECK(st.mod == BENCH_MOD_FLRC);
    CHECK(st.freq_hz == 869525000UL);      /* §1 STAT example boot config */
    CHECK(st.br_bps == 650000UL);
    CHECK(st.sf == 0 && st.bw_hz == 0);    /* LoRa unset at boot (FLRC) */
    CHECK(st.dbm == 10);
    CHECK(st.len_bytes == 51);
    CHECK(st.n_pkts == 1000);
    CHECK(st.gap_us == 5000);
    CHECK(st.outdoor_unlocked == false);
    CHECK(st.fw_hash != NULL && strcmp(st.fw_hash, "deadbeef") == 0);

    /* stats zeroed at init */
    CHECK(st.stats.rx_ok == 0 && st.stats.tx_done == 0 &&
          st.stats.tx_attempted == 0 && st.stats.rx_crc_err == 0);
    CHECK(st.stats.rssi_valid == false && st.stats.rx_seq_valid == false);
}

/* -------------------------------------------- config while IDLE -> reinit */

static void test_config_idle_reinit(void)
{
    bench_state_t st;
    bench_state_init(&st, "t");

    /* MOD FLRC change: reinit, band-aware (mod changed) */
    rh_plan_t p = apply(&st, "MOD FLRC 1300");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_REINIT_FULL);
    CHECK(p.band_aware == true);
    CHECK(st.mod == BENCH_MOD_FLRC && st.br_bps == 1300000UL);

    /* MOD LORA: reinit, band-aware (mod changed) */
    p = apply(&st, "MOD LORA 7 250");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_REINIT_FULL);
    CHECK(p.band_aware == true);
    CHECK(st.mod == BENCH_MOD_LORA && st.sf == 7 && st.bw_hz == 250000UL);

    /* back to FLRC for the remaining vectors */
    apply(&st, "MOD FLRC 650");

    /* FREQ change: reinit, band-aware (front-end calib depends on freq) */
    p = apply(&st, "FREQ 868000000");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_REINIT_FULL);
    CHECK(p.band_aware == true);
    CHECK(st.freq_hz == 868000000UL);

    /* PA change: reinit, NOT band-aware (band matrix bytes unchanged) */
    p = apply(&st, "PA 5");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_REINIT_FULL);
    CHECK(p.band_aware == false);
    CHECK(st.dbm == 5);

    /* LEN change: reinit (pkt params), not band-aware */
    p = apply(&st, "LEN 100");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_REINIT_FULL);
    CHECK(p.band_aware == false);
    CHECK(st.len_bytes == 100);

    /* No-op MOD (same mod, same args): reinit still emitted (idempotent
     * re-apply) but NOT flagged band-aware. */
    p = apply(&st, "MOD FLRC 650");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_REINIT_FULL);
    CHECK(p.band_aware == false);
}

/* ------------------------------------------ config while ACTIVE -> BUSY */

static void test_config_active_busy(void)
{
    bench_state_t st;
    bench_state_init(&st, "t");
    start_tx(&st);

    const char* cmds[] = {
        "MOD FLRC 1300", "MOD LORA 12 125", "FREQ 868000000",
        "PA 5",          "LEN 100",
    };
    for (unsigned i = 0; i < sizeof(cmds) / sizeof(cmds[0]); i++)
    {
        rh_plan_t p = apply(&st, cmds[i]);
        CHECK(p.err == RH_CMD_E_BUSY);
        CHECK(p.action == RH_PLAN_NONE);
        CHECK(p.band_aware == false);
    }

    /* state untouched by every rejected command */
    CHECK(st.mod == BENCH_MOD_FLRC && st.br_bps == 650000UL);
    CHECK(st.freq_hz == 869525000UL);
    CHECK(st.dbm == 10);
    CHECK(st.len_bytes == 51);
    CHECK(st.session == RH_SESSION_ACTIVE);
}

/* ----------------------------------------- START before ROLE -> INHIBITED */

static void test_start_without_role(void)
{
    bench_state_t st;
    bench_state_init(&st, "t");

    rh_plan_t p = apply(&st, "START");
    CHECK(p.err == RH_CMD_E_INHIBITED);
    CHECK(p.action == RH_PLAN_NONE);
    CHECK(st.session == RH_SESSION_IDLE); /* still standby */

    /* ROLE RX is equally required: role must be TX *or* RX */
    apply(&st, "ROLE RX");
    p = apply(&st, "START");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_START_BURST);
    CHECK(st.session == RH_SESSION_ACTIVE);
}

/* ROLE NONE after ROLE TX re-inhibits (two-step TX inhibit, §1) */
static void test_role_none_reinhibits(void)
{
    bench_state_t st;
    bench_state_init(&st, "t");

    rh_plan_t p = apply(&st, "ROLE TX");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_NONE);
    CHECK(st.role == RH_ROLE_TX);

    p = apply(&st, "ROLE NONE");
    CHECK(p.err == RH_CMD_OK && st.role == RH_ROLE_NONE);

    p = apply(&st, "START");
    CHECK(p.err == RH_CMD_E_INHIBITED);
}

/* -------------------------------- PA > 10 without unlock -> POWER-LOCKED */

static void test_pa_power_lock(void)
{
    bench_state_t st;
    bench_state_init(&st, "t");

    /* default boot PA is 10 dBm == indoor cap: at-cap is allowed */
    CHECK(st.dbm == 10 && st.outdoor_unlocked == false);

    rh_plan_t p = apply(&st, "PA 10");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_REINIT_FULL);

    /* above cap without unlock: locked, dbm unchanged */
    const int locked[] = { 11, 14, 22 };
    for (unsigned i = 0; i < sizeof(locked) / sizeof(locked[0]); i++)
    {
        char line[32];
        snprintf(line, sizeof(line), "PA %d", locked[i]);
        p = apply(&st, line);
        CHECK(p.err == RH_CMD_E_POWER_LOCKED);
        CHECK(p.action == RH_PLAN_NONE);
        CHECK(st.dbm == 10); /* rejected: state unchanged */
    }

    /* below-cap values stay fine */
    p = apply(&st, "PA -18");
    CHECK(p.err == RH_CMD_OK && st.dbm == -18);
    apply(&st, "PA 10");

    /* unlock via POWER MODE OUTDOOR 2026, then 14 dBm passes */
    p = apply(&st, "POWER MODE OUTDOOR 2026");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_NONE);
    CHECK(st.outdoor_unlocked == true);

    p = apply(&st, "PA 14");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_REINIT_FULL);
    CHECK(st.dbm == 14);

    /* protocol range still enforced above outdoor cap: 23 dBm -> RANGE */
    p = apply(&st, "PA 23");
    CHECK(p.err == RH_CMD_E_RANGE);
    CHECK(st.dbm == 14); /* unchanged */
}

/* ---------------------------- FREQ out of EU band -> RANGE (two layers) */

static void test_freq_out_of_band(void)
{
    bench_state_t st;
    bench_state_init(&st, "t");

    /* Layer 1: parser rejects (950 MHz) — dispatch propagates the class */
    rh_plan_t p = apply(&st, "FREQ 950000000");
    CHECK(p.err == RH_CMD_E_RANGE);
    CHECK(p.action == RH_PLAN_NONE);
    CHECK(st.freq_hz == 869525000UL);

    /* Layer 2: defense-in-depth — a hand-built FREQ cmd that bypassed the
     * parser (uint32 wrap, direct struct use) is re-checked against
     * bench_safety_freq_in_eu_band and still rejected. */
    rh_cmd_t c;
    memset(&c, 0, sizeof(c));
    c.id = RH_CMD_FREQ;
    c.err = RH_CMD_OK;
    c.freq_hz = 915000000UL; /* US ISM: out of EU SRD */
    p = bench_apply_cmd(&st, &c);
    CHECK(p.err == RH_CMD_E_RANGE);
    CHECK(st.freq_hz == 869525000UL);

    /* band edges are inclusive */
    p = apply(&st, "FREQ 863000000");
    CHECK(p.err == RH_CMD_OK && st.freq_hz == 863000000UL);
    p = apply(&st, "FREQ 870000000");
    CHECK(p.err == RH_CMD_OK && st.freq_hz == 870000000UL);
}

/* ------------------- STOP semantics: stats retained until next START */

static void test_stop_retains_stats_start_resets(void)
{
    bench_state_t st;
    bench_state_init(&st, "t");

    /* fabricate a finished burst's counters directly (engines own the real
     * accumulation, FW-7/8) */
    st.stats.tx_attempted = 1000;
    st.stats.tx_done = 997;
    st.stats.rx_ok = 42;
    st.stats.rx_crc_err = 3;
    st.stats.rx_seq_valid = true;
    st.stats.rx_first_seq = 1;
    st.stats.rx_last_seq = 1000;
    st.stats.rssi_valid = true;
    st.stats.rssi_sum_half = -2000;
    st.stats.rssi_min = -120;
    st.stats.rssi_max = -80;

    /* START resets the stats for the new session */
    rh_plan_t p = apply(&st, "ROLE TX");
    CHECK(p.err == RH_CMD_OK);
    p = apply(&st, "START");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_START_BURST);
    CHECK(st.session == RH_SESSION_ACTIVE);
    CHECK(st.stats.tx_attempted == 0 && st.stats.tx_done == 0 &&
          st.stats.rx_ok == 0 && st.stats.rx_crc_err == 0);
    CHECK(st.stats.rx_seq_valid == false && st.stats.rssi_valid == false);
    CHECK(st.stats.rssi_min == 0 && st.stats.rssi_max == 0 &&
          st.stats.rssi_sum_half == 0);

    /* burst runs; counters accumulate again */
    st.stats.tx_attempted = 500;
    st.stats.tx_done = 500;
    st.stats.rx_ok = 250;

    /* STOP: abort -> standby, stats RETAINED (readable by STAT? after stop) */
    p = apply(&st, "STOP");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_STOP);
    CHECK(st.session == RH_SESSION_IDLE);
    CHECK(st.stats.tx_attempted == 500 && st.stats.tx_done == 500 &&
          st.stats.rx_ok == 250);

    /* STOP while IDLE: OK, nothing to abort, stats still retained */
    p = apply(&st, "STOP");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_NONE);
    CHECK(st.stats.rx_ok == 250);

    /* next START wipes them for the new session */
    p = apply(&st, "START");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_START_BURST);
    CHECK(st.stats.tx_attempted == 0 && st.stats.rx_ok == 0);
}

/* ------------------------------------------------- START while ACTIVE BUSY */

static void test_start_busy(void)
{
    bench_state_t st;
    bench_state_init(&st, "t");
    start_tx(&st);

    rh_plan_t p = apply(&st, "START");
    CHECK(p.err == RH_CMD_E_BUSY);
    CHECK(st.session == RH_SESSION_ACTIVE);
}

/* ------------------------------ ROLE / N / GAP while ACTIVE -> BUSY
 * (documented FW-6 extension: everything except queries freezes during a
 * session — see docs/evidence/stage-a/fw6-dispatch-decision-table.md) */

static void test_nonconfig_active_busy(void)
{
    bench_state_t st;
    bench_state_init(&st, "t");
    start_tx(&st);

    const char* cmds[] = { "ROLE RX", "ROLE NONE", "N 500", "GAP 1000",
                           "POWER MODE OUTDOOR 2026" };
    for (unsigned i = 0; i < sizeof(cmds) / sizeof(cmds[0]); i++)
    {
        rh_plan_t p = apply(&st, cmds[i]);
        CHECK(p.err == RH_CMD_E_BUSY);
        CHECK(p.action == RH_PLAN_NONE);
    }
    CHECK(st.role == RH_ROLE_TX);
    CHECK(st.n_pkts == 1000 && st.gap_us == 5000);

    /* while IDLE they apply normally, no radio action */
    apply(&st, "STOP");
    rh_plan_t p = apply(&st, "N 500");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_NONE);
    CHECK(st.n_pkts == 500);
    p = apply(&st, "GAP 1000");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_NONE);
    CHECK(st.gap_us == 1000);
    p = apply(&st, "ROLE RX");
    CHECK(p.err == RH_CMD_OK && st.role == RH_ROLE_RX);
}

/* ------------------------------------------- POWER pin errors propagate */

static void test_power_bad_pin(void)
{
    bench_state_t st;
    bench_state_init(&st, "t");

    rh_plan_t p = apply(&st, "POWER MODE OUTDOOR 9999");
    CHECK(p.err == RH_CMD_E_ARG);
    CHECK(st.outdoor_unlocked == false);
}

/* ------------------------------ parse errors / unknown propagate untouched */

static void test_parse_errors_propagate(void)
{
    bench_state_t st;
    bench_state_init(&st, "t");

    rh_plan_t p = apply(&st, "BOGUS 1 2");
    CHECK(p.err == RH_CMD_E_UNKNOWN && p.action == RH_PLAN_NONE);

    p = apply(&st, "ROLE");            /* ARG */
    CHECK(p.err == RH_CMD_E_ARG);
    p = apply(&st, "PA 99");           /* RANGE at parse */
    CHECK(p.err == RH_CMD_E_RANGE);
    p = apply(&st, "N 0");             /* RANGE at parse */
    CHECK(p.err == RH_CMD_E_RANGE);
    p = apply(&st, "LEN 4");           /* RANGE at parse */
    CHECK(p.err == RH_CMD_E_RANGE);

    CHECK(st.role == RH_ROLE_NONE && st.dbm == 10 && st.n_pkts == 1000 &&
          st.len_bytes == 51);
}

/* ------------------------------- queries are never BUSY (usable in flight) */

static void test_queries_while_active(void)
{
    bench_state_t st;
    bench_state_init(&st, "t");
    start_tx(&st);

    const char* cmds[] = { "ID?", "HELP", "?", "STAT?" };
    for (unsigned i = 0; i < sizeof(cmds) / sizeof(cmds[0]); i++)
    {
        rh_plan_t p = apply(&st, cmds[i]);
        CHECK(p.err == RH_CMD_OK);
        CHECK(p.action == RH_PLAN_NONE);
    }
}

/* ------------------------------------------------------- ID? / HELP wiring */

static void test_id_format(void)
{
    bench_state_t st;
    bench_state_init(&st, "cafe42");

    char buf[128];
    bench_format_id(&st, buf, sizeof(buf));
    CHECK(strcmp(buf, "ID range-host v1 fw=cafe42 role=NONE") == 0);

    apply(&st, "ROLE TX");
    bench_format_id(&st, buf, sizeof(buf));
    CHECK(strcmp(buf, "ID range-host v1 fw=cafe42 role=TX") == 0);

    apply(&st, "ROLE RX");
    bench_format_id(&st, buf, sizeof(buf));
    CHECK(strcmp(buf, "ID range-host v1 fw=cafe42 role=RX") == 0);
}

static void test_help_text(void)
{
    const char* h = bench_help_text();
    /* every §1 command word present */
    CHECK(strstr(h, "ID?") != NULL);
    CHECK(strstr(h, "ROLE") != NULL);
    CHECK(strstr(h, "MOD") != NULL);
    CHECK(strstr(h, "FREQ") != NULL);
    CHECK(strstr(h, "PA") != NULL);
    CHECK(strstr(h, "LEN") != NULL);
    CHECK(strstr(h, "N ") != NULL);
    CHECK(strstr(h, "GAP") != NULL);
    CHECK(strstr(h, "POWER") != NULL);
    CHECK(strstr(h, "START") != NULL);
    CHECK(strstr(h, "STOP") != NULL);
    CHECK(strstr(h, "STAT?") != NULL);
    CHECK(strstr(h, "HELP") != NULL);
    /* REV-2 minor: STOP stats semantics documented in HELP */
    CHECK(strstr(h, "RETAINED") != NULL);
    /* PA unlock hint present */
    CHECK(strstr(h, "OUTDOOR") != NULL);
}

/* ---------------------------------------------------- §1 reply formatting */

static void test_reply_formats(void)
{
    bench_state_t st;
    bench_state_init(&st, "h7");
    char buf[512];

    struct
    {
        const char* line;
        const char* want;
    } v[] = {
        { "ROLE TX",             "OK ROLE TX" },
        { "ROLE RX",             "OK ROLE RX" },
        { "ROLE NONE",           "OK ROLE NONE" },
        { "MOD FLRC 650",        "OK MOD FLRC br_hz=650000" },
        { "MOD LORA 7 250",      "OK MOD LORA sf=7 bw_hz=250000" },
        { "FREQ 868000000",      "OK FREQ 868000000" },
        { "PA 5",                "OK PA 5" },
        { "PA -18",              "OK PA -18" },
        { "LEN 100",             "OK LEN 100" },
        { "N 500",               "OK N 500" },
        { "GAP 1000",            "OK GAP 1000" },
        { "POWER MODE OUTDOOR 2026", "OK POWER OUTDOOR" },
        { "STOP",                "OK STOP" },
    };

    for (unsigned i = 0; i < sizeof(v) / sizeof(v[0]); i++)
    {
        rh_cmd_t c;
        memset(&c, 0, sizeof(c));
        rh_cmd_parse(v[i].line, &c);
        rh_plan_t p = bench_apply_cmd(&st, &c);
        CHECK(p.err == RH_CMD_OK);
        bool ok = bench_format_reply(&st, &c, &p, buf, sizeof(buf));
        CHECK(ok);
        if (strcmp(buf, v[i].want) != 0)
            printf("  reply mismatch for '%s': got '%s' want '%s'\n",
                   v[i].line, buf, v[i].want);
        CHECK(strcmp(buf, v[i].want) == 0);
    }

    /* START reply carries the burst plan (TX), or is bare for RX */
    apply(&st, "ROLE TX");
    apply(&st, "N 50");
    apply(&st, "LEN 100");
    apply(&st, "GAP 1000");
    rh_cmd_t c;
    memset(&c, 0, sizeof(c));
    rh_cmd_parse("START", &c);
    rh_plan_t p = bench_apply_cmd(&st, &c);
    CHECK(p.action == RH_PLAN_START_BURST);
    bool ok = bench_format_reply(&st, &c, &p, buf, sizeof(buf));
    CHECK(ok && strcmp(buf, "OK START n=50 len=100 gap_us=1000") == 0);

    /* errors format as ERR <class> (§1 vocabulary) */
    bench_state_t fresh;
    bench_state_init(&fresh, "h7");
    rh_cmd_t bad;
    memset(&bad, 0, sizeof(bad));

    rh_cmd_parse("START", &bad);
    p = bench_apply_cmd(&fresh, &bad); /* no role -> INHIBITED */
    ok = bench_format_reply(&fresh, &bad, &p, buf, sizeof(buf));
    CHECK(ok && strcmp(buf, "ERR INHIBITED") == 0);

    rh_cmd_parse("PA 14", &bad);
    p = bench_apply_cmd(&fresh, &bad); /* locked */
    ok = bench_format_reply(&fresh, &bad, &p, buf, sizeof(buf));
    CHECK(ok && strcmp(buf, "ERR POWER-LOCKED") == 0);

    rh_cmd_parse("FREQ 950000000", &bad);
    p = bench_apply_cmd(&fresh, &bad); /* RANGE */
    ok = bench_format_reply(&fresh, &bad, &p, buf, sizeof(buf));
    CHECK(ok && strcmp(buf, "ERR RANGE") == 0);

    rh_cmd_parse("BOGUS", &bad);
    p = bench_apply_cmd(&fresh, &bad); /* UNKNOWN */
    ok = bench_format_reply(&fresh, &bad, &p, buf, sizeof(buf));
    CHECK(ok && strcmp(buf, "ERR UNKNOWN") == 0);

    rh_cmd_parse("ROLE", &bad);
    p = bench_apply_cmd(&fresh, &bad); /* ARG */
    ok = bench_format_reply(&fresh, &bad, &p, buf, sizeof(buf));
    CHECK(ok && strcmp(buf, "ERR ARG") == 0);

    /* ID? reply == format_id; HELP reply == help text (multi-line) */
    rh_cmd_parse("ID?", &bad);
    p = bench_apply_cmd(&fresh, &bad);
    ok = bench_format_reply(&fresh, &bad, &p, buf, sizeof(buf));
    CHECK(ok && strcmp(buf, "ID range-host v1 fw=h7 role=NONE") == 0);

    rh_cmd_parse("HELP", &bad);
    p = bench_apply_cmd(&fresh, &bad);
    ok = bench_format_reply(&fresh, &bad, &p, buf, sizeof(buf));
    CHECK(ok && strcmp(buf, bench_help_text()) == 0);

    /* STAT? has no FW-6 reply yet (FW-9 formatter) — formatter says no */
    rh_cmd_parse("STAT?", &bad);
    p = bench_apply_cmd(&fresh, &bad);
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_NONE);
    ok = bench_format_reply(&fresh, &bad, &p, buf, sizeof(buf));
    CHECK(!ok);
}

/* ------------------------------------------------ full operator flow smoke */

static void test_operator_flow(void)
{
    bench_state_t st;
    bench_state_init(&st, "flow");
    rh_plan_t p;

    /* configure a FLRC burst from boot defaults */
    p = apply(&st, "ROLE TX");          CHECK(p.err == RH_CMD_OK);
    p = apply(&st, "MOD FLRC 1300");    CHECK(p.action == RH_PLAN_REINIT_FULL);
    p = apply(&st, "FREQ 868000000");   CHECK(p.action == RH_PLAN_REINIT_FULL);
    p = apply(&st, "PA 5");             CHECK(p.action == RH_PLAN_REINIT_FULL);
    p = apply(&st, "LEN 100");          CHECK(p.action == RH_PLAN_REINIT_FULL);
    p = apply(&st, "N 50");             CHECK(p.action == RH_PLAN_NONE);
    p = apply(&st, "GAP 1000");         CHECK(p.action == RH_PLAN_NONE);

    CHECK(st.mod == BENCH_MOD_FLRC && st.br_bps == 1300000UL);
    CHECK(st.freq_hz == 868000000UL && st.dbm == 5 && st.len_bytes == 100);

    /* locked PA rejected pre-burst, unlock, raise, run, stop */
    p = apply(&st, "PA 14");
    CHECK(p.err == RH_CMD_E_POWER_LOCKED);
    p = apply(&st, "POWER MODE OUTDOOR 2026");
    CHECK(p.err == RH_CMD_OK);
    p = apply(&st, "PA 14");
    CHECK(p.err == RH_CMD_OK && st.dbm == 14);

    p = apply(&st, "START");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_START_BURST);
    CHECK(st.session == RH_SESSION_ACTIVE);

    /* mid-flight: queries fine, mutations BUSY */
    p = apply(&st, "STAT?");            CHECK(p.err == RH_CMD_OK);
    p = apply(&st, "FREQ 869525000");   CHECK(p.err == RH_CMD_E_BUSY);
    p = apply(&st, "STOP");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_STOP);
    CHECK(st.session == RH_SESSION_IDLE);

    /* config immediately re-writable after STOP (IDLE) */
    p = apply(&st, "MOD LORA 9 125");
    CHECK(p.err == RH_CMD_OK && p.action == RH_PLAN_REINIT_FULL);
    CHECK(p.band_aware == true && st.mod == BENCH_MOD_LORA);
}

int main(void)
{
    test_state_defaults();
    test_config_idle_reinit();
    test_config_active_busy();
    test_start_without_role();
    test_role_none_reinhibits();
    test_pa_power_lock();
    test_freq_out_of_band();
    test_stop_retains_stats_start_resets();
    test_start_busy();
    test_nonconfig_active_busy();
    test_power_bad_pin();
    test_parse_errors_propagate();
    test_queries_while_active();
    test_id_format();
    test_help_text();
    test_reply_formats();
    test_operator_flow();

    if (failures == 0)
    {
        printf("test_dispatch: ALL PASS\n");
        return 0;
    }
    printf("test_dispatch: %d FAILURE(S)\n", failures);
    return 1;
}
