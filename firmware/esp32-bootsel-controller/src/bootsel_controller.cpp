/*
 * bootsel_controller.cpp — pin sequence, command parser and heartbeat watchdog.
 *
 * Deliberately free of Arduino/IDF headers: it only calls the
 * bootsel_platform_*() hooks, which each target implements. That is what makes
 * the host suite (tests/test_bootsel_controller.py) able to run the *same*
 * command parser and sequence that is flashed to the board.
 */
#include "bootsel_controller.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#define ACK_MAX 96
static char s_ack[ACK_MAX];

/* Exact, case-insensitive command match: the whole line must be the word,
 * optionally followed by whitespace/CR/LF. Prefix matching is deliberately NOT
 * accepted: this interface can reset the RP2040 or park it in the bootloader,
 * so a stray line such as "bootselx" or "bootsel controller ready" must be an
 * error, not a hardware action. */
static bool token_eq(const char *line, const char *word)
{
    size_t i = 0;
    for (; word[i]; i++) {
        char c = line[i];
        if (c >= 'A' && c <= 'Z') c = (char)(c + 32);
        if (c != word[i]) return false;
    }
    for (; line[i]; i++) {
        char t = line[i];
        if (t != ' ' && t != '\t' && t != '\r' && t != '\n') return false;
    }
    return true;
}

static const char *skip_space(const char *p)
{
    while (*p == ' ' || *p == '\t') p++;
    return p;
}

static void ack(const char *fmt, ...) __attribute__((format(printf, 1, 2)));

static void ack(const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(s_ack, sizeof s_ack, fmt, ap);
    va_end(ap);
}

void bootsel_init(bootsel_state_t *s)
{
    memset(s, 0, sizeof *s);
    /* Idle HIGH first: the RP2040 must not be held in reset or in bootloader
     * mode while the ESP32 itself is still coming up. */
    bootsel_platform_write_run(true);
    bootsel_platform_write_bootsel(true);
    s->run_high = true;
    s->bootsel_high = true;
    s->watchdog_enabled = false;
    s->watchdog_ms = BOOTSEL_WD_DEFAULT_MS;
}

void bootsel_pulse_run(bootsel_state_t *s)
{
    bootsel_platform_write_run(false);
    s->run_high = false;
    bootsel_platform_delay_ms(BOOTSEL_DELAY_RUN_LOW_MS);
    bootsel_platform_write_run(true);
    s->run_high = true;
    s->run_pulses++;
    /* The RP2040 is restarting: it has to prove liveness again before the
     * watchdog is allowed to act, and the one-shot latch is re-armed. */
    s->have_rp_hb = false;
    s->wd_fired = false;
}

void bootsel_force_entry(bootsel_state_t *s)
{
    bootsel_platform_write_bootsel(false);          /* 1. GP0 LOW              */
    s->bootsel_high = false;
    bootsel_platform_delay_ms(BOOTSEL_DELAY_SETTLE_MS);   /* 2. settle         */
    bootsel_platform_write_run(false);              /* 3. RUN LOW (reset)      */
    s->run_high = false;
    bootsel_platform_delay_ms(BOOTSEL_DELAY_RUN_LOW_MS);  /* 4. min 1us, 100ms */
    bootsel_platform_write_run(true);               /* 5. RUN HIGH (release)   */
    s->run_high = true;
    bootsel_platform_delay_ms(BOOTSEL_DELAY_SAMPLE_MS);   /* 6. GP0 sampled    */
    bootsel_platform_write_bootsel(true);           /* 7. GP0 HIGH (pull-up)   */
    s->bootsel_high = true;
    s->bootsel_events++;
    s->run_pulses++;
    s->have_rp_hb = false;
    s->wd_fired = false;
}

void bootsel_note_rp_heartbeat(bootsel_state_t *s, uint32_t now_ms)
{
    s->last_rp_hb_ms = now_ms;
    s->have_rp_hb = true;
    s->wd_fired = false;   /* liveness proven -> the latch re-arms */
}

bool bootsel_watchdog_due(const bootsel_state_t *s, uint32_t now_ms)
{
    if (!s->watchdog_enabled || s->wd_fired) return false;
    if (!s->have_rp_hb) return false;   /* nothing observed yet: nothing to judge */
    return (uint32_t)(now_ms - s->last_rp_hb_ms) >= s->watchdog_ms;
}

bool bootsel_watchdog_tick(bootsel_state_t *s, uint32_t now_ms)
{
    if (!bootsel_watchdog_due(s, now_ms)) return false;
    bootsel_pulse_run(s);
    s->wd_fired = true;      /* exactly one recovery per silence episode */
    s->wd_triggers++;
    return true;
}

void bootsel_status_line(const bootsel_state_t *s, uint32_t now_ms,
                         char *out, size_t out_len)
{
    int n = snprintf(out, out_len,
                     "STAT run=%d bootsel=%d bootsel_events=%u run_pulses=%u "
                     "wd=%s wd_ms=%u wd_fires=%u",
                     s->run_high ? 1 : 0, s->bootsel_high ? 1 : 0,
                     (unsigned)s->bootsel_events, (unsigned)s->run_pulses,
                     s->watchdog_enabled ? "on" : "off",
                     (unsigned)s->watchdog_ms, (unsigned)s->wd_triggers);
    if (n > 0 && (size_t)n < out_len && s->have_rp_hb) {
        snprintf(out + n, out_len - (size_t)n, " since_hb_ms=%u",
                 (unsigned)(now_ms - s->last_rp_hb_ms));
    }
}

const char *bootsel_apply_line(bootsel_state_t *s, const char *line, uint32_t now_ms)
{
    line = skip_space(line ? line : "");
    char c = line[0];
    if (c == '\0' || c == '\r' || c == '\n') {
        s_ack[0] = '\0';
        return s_ack;
    }
    char lc = (c >= 'A' && c <= 'Z') ? (char)(c + 32) : c;

    /* A command is the whole line: the single letter, or its long alias. A line
     * that merely STARTS with one is rejected — see token_eq(). The long forms
     * are the words the existing host-side watcher
     * (firmware/esp32-c3-bootsel-controller/enhanced_board_watcher.sh) already
     * sends (RESET / BOOTSEL / STATUS), so that script keeps working. */
    if (token_eq(line, "r") || token_eq(line, "reset")) {
        bootsel_pulse_run(s);
        ack("OK r\n");
    } else if (token_eq(line, "b") || token_eq(line, "bootsel")) {
        bootsel_force_entry(s);
        ack("OK b\n");
    } else if (token_eq(line, "s") || token_eq(line, "status")) {
        char st[192];
        bootsel_status_line(s, now_ms, st, sizeof st);
        ack("%s\n", st);
    } else if (token_eq(line, "h") || token_eq(line, "hb")) {
        bootsel_note_rp_heartbeat(s, now_ms);
        ack("OK hb\n");
    } else if (lc == 'w') {
        const char *arg = skip_space(line + 1);
        if (arg[0] == '0' || token_eq(arg, "off")) {
            s->watchdog_enabled = false;
            ack("OK w=off wd_ms=%u\n", (unsigned)s->watchdog_ms);
        } else if (arg[0] == '1' || token_eq(arg, "on")) {
            s->watchdog_enabled = true;
            ack("OK w=on wd_ms=%u\n", (unsigned)s->watchdog_ms);
        } else {
            ack("ERR w needs on|off\n");
        }
    } else {
        ack("ERR unknown command\n");
    }
    return s_ack;
}
