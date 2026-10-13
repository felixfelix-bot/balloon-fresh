/*
 * ser_io_host.cpp — host harness for the auto-BOOTSEL test firmware.
 *
 * Compiles the SAME bootsel_controller.cpp that is flashed to the ESP32-C3
 * against recording stubs, so the pin order, the timing, the command parser and
 * the heartbeat watchdog under test are literally the shipped object code — not
 * a re-implementation.
 *
 * It prints one line of machine-readable facts; tests/test_bootsel_controller.py
 * asserts on them. exit 0 = every internal property held, exit 1 = at least one
 * failed (the FAIL lines name which).
 *
 * Build/run (the pytest module does this automatically):
 *   g++ -std=c++17 -Wall -Wextra -O1 -I firmware/esp32-bootsel-controller/src \
 *       tests/src/ser_io_host.cpp firmware/esp32-bootsel-controller/src/bootsel_controller.cpp \
 *       -o /tmp/ser_io_host && /tmp/ser_io_host
 */
#include "bootsel_controller.h"

#include <stdio.h>
#include <string.h>
#include <string>

using std::string;

/* ---------------- recording platform hooks ---------------- */

static uint32_t g_t = 0;
static string   g_trace;      /* "t=<ms> RUN=<0|1>" / "t=<ms> GP0=<0|1>" */
static int      g_fail = 0;

void bootsel_platform_delay_ms(uint32_t ms) { g_t += ms; }

void bootsel_platform_write_run(bool high)
{
    char buf[48];
    snprintf(buf, sizeof buf, "t=%u RUN=%d;", (unsigned)g_t, high ? 1 : 0);
    g_trace += buf;
}

void bootsel_platform_write_bootsel(bool high)
{
    char buf[48];
    snprintf(buf, sizeof buf, "t=%u GP0=%d;", (unsigned)g_t, high ? 1 : 0);
    g_trace += buf;
}

void bootsel_platform_print(const char *text) { g_trace += text; }

static void prop(const char *name, bool ok)
{
    printf("PROP %s %s\n", name, ok ? "PASS" : "FAIL");
    if (!ok) g_fail++;
}

static void reset_trace(){ g_trace.clear(); g_t = 0; }

/* Index of the Nth occurrence of `needle` in the trace, or -1. */
static long nth(const string &hay, const char *needle, int n)
{
    size_t pos = string::npos;
    for (int i = 0; i < n; i++) {
        pos = hay.find(needle, pos == string::npos ? 0 : pos + 1);
        if (pos == string::npos) return -1;
    }
    return (long)pos;
}

int main(void)
{
    bootsel_state_t s;

    /* ---- 1. init must leave the RP2040 running (both pads HIGH) ---------- */
    reset_trace();
    bootsel_init(&s);
    prop("init_drives_run_high",
         g_trace.find("RUN=1;") != string::npos &&
         g_trace.find("RUN=0;") == string::npos);
    prop("init_drives_gp0_high",
         g_trace.find("GP0=1;") != string::npos &&
         g_trace.find("GP0=0;") == string::npos);
    prop("init_no_bootsel_event", s.bootsel_events == 0);
    prop("init_watchdog_off_by_default", s.watchdog_enabled == false);

    /* ---- 2. force_entry: exact verified sequence, in order -------------- */
    reset_trace();
    bootsel_force_entry(&s);
    {
        /* expected: GP0 LOW at t=0; RUN LOW at t=50; RUN HIGH at t=150;
         *           GP0 HIGH at t=650 */
        const string expect = "t=0 GP0=0;t=50 RUN=0;t=150 RUN=1;t=650 GP0=1;";
        prop("bootsel_sequence_exact", g_trace == expect);
        long gp0_low  = nth(g_trace, "GP0=0;", 1);
        long run_low  = nth(g_trace, "RUN=0;", 1);
        long run_high = nth(g_trace, "RUN=1;", 1);
        long gp0_high = nth(g_trace, "GP0=1;", 1);   /* the only GP0 HIGH in this trace */
        prop("bootsel_gp0_low_before_run_low", gp0_low >= 0 && run_low > gp0_low);
        prop("bootsel_run_released_before_gp0_released", run_high > run_low && gp0_high > run_high);
        prop("bootsel_settle_is_50ms", g_trace.find("t=50 RUN=0;") != string::npos);
        prop("bootsel_hold_run_low_100ms", g_trace.find("t=150 RUN=1;") != string::npos);
        prop("bootsel_hold_gp0_low_500ms", g_trace.find("t=650 GP0=1;") != string::npos);
        prop("bootsel_event_counted", s.bootsel_events == 1);
        prop("bootsel_ends_idle_high", s.run_high && s.bootsel_high);
    }

    /* ---- 3. pulse_run: reset only, never touches GP0 -------------------- */
    reset_trace();
    {
        uint32_t before = s.run_pulses;
        bootsel_pulse_run(&s);
        prop("run_pulse_drives_run_low", g_trace.find("t=0 RUN=0;") != string::npos);
        prop("run_pulse_releases_100ms", g_trace.find("t=100 RUN=1;") != string::npos);
        prop("run_pulse_never_touches_gp0", g_trace.find("GP0=") == string::npos);
        prop("run_pulse_counted", s.run_pulses == before + 1);
        prop("run_pulse_clears_liveness", s.have_rp_hb == false);
    }

    /* ---- 4. command parser --------------------------------------------- */
    {
        bootsel_init(&s);
        const char *a;

        a = bootsel_apply_line(&s, "r\n", 0);
        prop("cmd_r_acks_ok", strcmp(a, "OK r\n") == 0);
        a = bootsel_apply_line(&s, "b", 0);
        prop("cmd_b_acks_ok", strcmp(a, "OK b\n") == 0);
        a = bootsel_apply_line(&s, "BL", 0);          /* not a command           */
        prop("cmd_unknown_is_error", strncmp(a, "ERR", 3) == 0);
        a = bootsel_apply_line(&s, "", 0);
        prop("cmd_empty_is_silent", a[0] == '\0');
        a = bootsel_apply_line(&s, "s", 1234);
        prop("cmd_s_prints_status", strncmp(a, "STAT ", 5) == 0);
        a = bootsel_apply_line(&s, "w on", 0);
        prop("cmd_w_on_acks", strstr(a, "w=on") != NULL && s.watchdog_enabled);
        a = bootsel_apply_line(&s, "w off", 0);
        prop("cmd_w_off_acks", strstr(a, "w=off") != NULL && !s.watchdog_enabled);
        a = bootsel_apply_line(&s, "w maybe", 0);
        prop("cmd_w_needs_arg", strncmp(a, "ERR", 3) == 0);
        a = bootsel_apply_line(&s, "h", 5000);
        prop("cmd_h_records_heartbeat", s.have_rp_hb && s.last_rp_hb_ms == 5000);
        /* leading whitespace and a lone CRLF are tolerated */
        a = bootsel_apply_line(&s, "  b\r\n", 0);
        prop("cmd_leading_space_ok", strcmp(a, "OK b\n") == 0);
        /* the long aliases the existing board watcher sends still work ... */
        a = bootsel_apply_line(&s, "RESET", 0);
        prop("cmd_long_reset_ok", strcmp(a, "OK r\n") == 0);
        a = bootsel_apply_line(&s, "BOOTSEL", 0);
        prop("cmd_long_bootsel_ok", strcmp(a, "OK b\n") == 0);
        a = bootsel_apply_line(&s, "STATUS", 0);
        prop("cmd_long_status_ok", strncmp(a, "STAT", 4) == 0);
        /* ... but a line that merely starts with a command is NOT a command:
         * these strings can reset the RP2040, so a parse must be exact. */
        {
            bootsel_state_t p;
            bootsel_init(&p);
            reset_trace();
            a = bootsel_apply_line(&p, "bootselx", 0);
            prop("cmd_prefix_is_rejected", strncmp(a, "ERR", 3) == 0);
            a = bootsel_apply_line(&p, "bootsel controller ready", 0);
            prop("cmd_sentence_is_rejected", strncmp(a, "ERR", 3) == 0);
            prop("cmd_rejected_lines_move_no_pins", g_trace.empty());
            prop("cmd_rejected_lines_count_nothing",
                 p.bootsel_events == 0 && p.run_pulses == 0);
        }
    }

    /* ---- 5. heartbeat watchdog ----------------------------------------- */
    {
        bootsel_init(&s);
        /* OFF by default: 60 s of silence must not move a pin. */
        reset_trace();
        s.last_rp_hb_ms = 0;
        s.have_rp_hb = true;
        prop("wd_off_is_inert", bootsel_watchdog_tick(&s, 60000) == false);
        prop("wd_off_no_pin_change", g_trace.empty());

        bootsel_apply_line(&s, "w on", 0);
        bootsel_apply_line(&s, "h", 0);
        prop("wd_not_due_before_threshold",
             bootsel_watchdog_due(&s, BOOTSEL_WD_DEFAULT_MS - 1) == false);
        prop("wd_due_at_threshold",
             bootsel_watchdog_due(&s, BOOTSEL_WD_DEFAULT_MS) == true);

        reset_trace();
        prop("wd_tick_fires", bootsel_watchdog_tick(&s, BOOTSEL_WD_DEFAULT_MS) == true);
        prop("wd_tick_resets_only_run", g_trace.find("RUN=0;") != string::npos);
        prop("wd_tick_never_enters_bootloader", g_trace.find("GP0=") == string::npos);
        prop("wd_tick_counted", s.wd_triggers == 1);
        prop("wd_latches_single_fire",
             bootsel_watchdog_tick(&s, BOOTSEL_WD_DEFAULT_MS + 60000) == false);
        /* liveness restored -> latch re-arms and the next silence fires again */
        bootsel_apply_line(&s, "h", BOOTSEL_WD_DEFAULT_MS + 1);
        prop("wd_rearms_after_heartbeat",
             bootsel_watchdog_tick(&s, BOOTSEL_WD_DEFAULT_MS + 1 + BOOTSEL_WD_DEFAULT_MS) == true);
        prop("wd_second_trigger_counted", s.wd_triggers == 2);
        /* a fresh controller that has never seen a heartbeat must stay quiet:
         * absence of evidence is not evidence of a hang. */
        bootsel_state_t fresh;
        bootsel_init(&fresh);
        bootsel_apply_line(&fresh, "w on", 0);
        reset_trace();
        prop("wd_no_heartbeat_ever_is_inert",
             bootsel_watchdog_tick(&fresh, 600000) == false);
        prop("wd_no_heartbeat_no_pin_change", g_trace.empty());
    }

    /* ---- 6. numeric contract for the host-side documentation ------------- */
    printf("FACT run_gpio=%u bootsel_gpio=%u settle_ms=%u run_low_ms=%u sample_ms=%u wd_default_ms=%u\n",
           (unsigned)BOOTSEL_GPIO_RUN, (unsigned)BOOTSEL_GPIO_BOOTSEL,
           (unsigned)BOOTSEL_DELAY_SETTLE_MS, (unsigned)BOOTSEL_DELAY_RUN_LOW_MS,
           (unsigned)BOOTSEL_DELAY_SAMPLE_MS, (unsigned)BOOTSEL_WD_DEFAULT_MS);

    printf("RESULT %s\n", g_fail == 0 ? "ALL_PROPERTIES_PASS" : "PROPERTIES_FAILED");
    return g_fail == 0 ? 0 : 1;
}
