/*
 * interlock.c — over-pressure / over-inflation safety interlock.
 * See interlock.h for the fail-safe contract.  Pure C, host-testable.
 */
#include "interlock.h"

#include <string.h>

/* ------------------------------------------------------------------ */
/* helpers                                                            */
/* ------------------------------------------------------------------ */

static bool il_is_latched(il_state_t s)
{
    return s == IL_TRIP_OVERPRESSURE ||
           s == IL_TRIP_SENSOR_FAULT ||
           s == IL_TRIP_TIMEOUT ||
           s == IL_TRIP_MANUAL;
}

static void il_latch(il_t *il, il_state_t s)
{
    il->state = s;          /* latched until an explicit il_reset() */
}

/* ------------------------------------------------------------------ */
/* public API                                                         */
/* ------------------------------------------------------------------ */

void il_init(il_t *il, const il_cfg_t *cfg)
{
    if (il == NULL) {
        return;
    }
    memset(il, 0, sizeof(*il));
    if (cfg != NULL) {
        il->cfg = *cfg;
    }
    il->state = IL_IDLE;    /* valve commanded CLOSED */
}

void il_arm(il_t *il)
{
    if (il == NULL) {
        return;
    }
    /* Only a clean, idle interlock may be armed.  A latched fault must be
     * explicitly reset first — arming must never silently clear a trip. */
    if (il->state == IL_IDLE) {
        il->state     = IL_ARMED;
        il->elapsed_s = 0.0;
    }
}

void il_tick(il_t *il, double dp_mbar, bool sensor_ok, double dt_s)
{
    if (il == NULL) {
        return;
    }

    /* Always record the evidence a reset decision needs. */
    il->dp_last        = dp_mbar;
    il->sensor_ok_last = sensor_ok;

    /* A latched fault stays latched; no fresh reading can clear it. */
    if (il_is_latched(il->state)) {
        return;
    }

    /* 1. Sensor fault -> fail closed.  Highest priority: an unreliable reading
     *    must never permit filling. */
    if (!sensor_ok) {
        il_latch(il, IL_TRIP_SENSOR_FAULT);
        return;
    }

    /* 2. Over-pressure -> hard cut-off. */
    if (dp_mbar > il->cfg.dp_cutoff_mbar) {
        il_latch(il, IL_TRIP_OVERPRESSURE);
        return;
    }

    /* 3. Fill-time ceiling -> redundant backstop against a stuck-open valve. */
    if (il->state == IL_ARMED) {
        il->elapsed_s += (dt_s > 0.0) ? dt_s : 0.0;
        if (il->elapsed_s > il->cfg.max_fill_s) {
            il_latch(il, IL_TRIP_TIMEOUT);
            return;
        }
    }

    /* Otherwise: stay in IDLE (closed) or ARMED (may open). */
}

void il_abort(il_t *il)
{
    if (il == NULL) {
        return;
    }
    il_latch(il, IL_TRIP_MANUAL);
}

bool il_reset(il_t *il, double dp_mbar, bool sensor_ok)
{
    if (il == NULL) {
        return false;
    }
    il->dp_last        = dp_mbar;
    il->sensor_ok_last = sensor_ok;

    if (!il_is_latched(il->state)) {
        return false;                       /* nothing to clear */
    }
    if (!sensor_ok) {
        return false;                       /* cannot certify a fault is gone */
    }
    if (dp_mbar >= il->cfg.dp_reset_mbar) {
        return false;                       /* still over the safe band */
    }

    il->state     = IL_IDLE;
    il->elapsed_s = 0.0;
    return true;
}

bool il_valve_energized(const il_t *il)
{
    /* THE fail-safe line: open IFF armed.  Every fault, idle, reset or
     * unknown state yields false == de-energized == closed. */
    return (il != NULL) && (il->state == IL_ARMED);
}

bool il_alarm(const il_t *il)
{
    return (il != NULL) && il_is_latched(il->state);
}

const char *il_state_name(il_state_t s)
{
    switch (s) {
    case IL_IDLE:              return "IDLE";
    case IL_ARMED:             return "ARMED";
    case IL_TRIP_OVERPRESSURE: return "TRIP_OVERPRESSURE";
    case IL_TRIP_SENSOR_FAULT: return "TRIP_SENSOR_FAULT";
    case IL_TRIP_TIMEOUT:      return "TRIP_TIMEOUT";
    case IL_TRIP_MANUAL:       return "TRIP_MANUAL";
    default:                   return "UNKNOWN";
    }
}

/* ------------------------------------------------------------------ */
/* self-test                                                          */
/* ------------------------------------------------------------------ */

int il_selftest(void)
{
    int fails = 0;
    il_cfg_t cfg = {
        .dp_cutoff_mbar = 5.0,      /* PLACEHOLDER (see design doc bench B1) */
        .dp_reset_mbar  = 2.0,
        .max_fill_s     = 3600.0,
    };
    il_t il;

#define CHECK(cond) do { if (!(cond)) { fails++; } } while (0)

    /* 1. nominal fill: armed, valve open, no alarm */
    il_init(&il, &cfg);
    il_arm(&il);
    il_tick(&il, 1.0, true, 1.0);
    CHECK(il.state == IL_ARMED);
    CHECK(il_valve_energized(&il) == true);
    CHECK(il_alarm(&il) == false);

    /* 2. over-pressure -> hard cut-off + alarm, valve fails CLOSED and latches */
    il_tick(&il, cfg.dp_cutoff_mbar + 0.1, true, 1.0);
    CHECK(il.state == IL_TRIP_OVERPRESSURE);
    CHECK(il_valve_energized(&il) == false);
    CHECK(il_alarm(&il) == true);
    il_tick(&il, 0.0, true, 1.0);          /* condition gone... */
    CHECK(il.state == IL_TRIP_OVERPRESSURE); /* ...but the latch holds */
    CHECK(il_valve_energized(&il) == false);

    /* 3. reset is refused while dp is still above the safe band ... */
    CHECK(il_reset(&il, cfg.dp_reset_mbar + 0.5, true) == false);
    CHECK(il.state == IL_TRIP_OVERPRESSURE);
    /* ... refused while the sensor is unhealthy ... */
    CHECK(il_reset(&il, cfg.dp_reset_mbar - 0.5, false) == false);
    /* ... and accepted once healthy + below the band */
    CHECK(il_reset(&il, cfg.dp_reset_mbar - 0.5, true) == true);
    CHECK(il.state == IL_IDLE);
    CHECK(il_valve_energized(&il) == false);   /* reset does NOT auto-open */
    CHECK(il_alarm(&il) == false);

    /* 4. re-arm after a clean reset works */
    il_arm(&il);
    CHECK(il.state == IL_ARMED);
    CHECK(il_valve_energized(&il) == true);

    /* 5. sensor fault -> fail closed, latched */
    il_tick(&il, 1.0, false, 1.0);
    CHECK(il.state == IL_TRIP_SENSOR_FAULT);
    CHECK(il_valve_energized(&il) == false);
    CHECK(il_alarm(&il) == true);

    /* 6. fill-time ceiling trips */
    il_reset(&il, 0.0, true);
    il_arm(&il);
    il_tick(&il, 1.0, true, cfg.max_fill_s + 1.0);
    CHECK(il.state == IL_TRIP_TIMEOUT);
    CHECK(il_valve_energized(&il) == false);

    /* 7. manual abort trips */
    il_reset(&il, 0.0, true);
    il_arm(&il);
    il_abort(&il);
    CHECK(il.state == IL_TRIP_MANUAL);
    CHECK(il_valve_energized(&il) == false);

    /* 8. arming a latched interlock is a no-op (never clears a trip) */
    il_arm(&il);
    CHECK(il.state == IL_TRIP_MANUAL);

    /* 9. global invariant over every state: alarm implies valve closed, and the
     *    valve is energized for exactly one state. */
    {
        il_state_t s;
        for (s = IL_IDLE; s <= IL_TRIP_MANUAL; s++) {
            il_t probe; il_init(&probe, &cfg);
            probe.state = s;
            if (il_alarm(&probe)) {
                CHECK(il_valve_energized(&probe) == false);
            }
            CHECK(il_valve_energized(&probe) == (s == IL_ARMED));
        }
    }

#undef CHECK
    return fails;
}
