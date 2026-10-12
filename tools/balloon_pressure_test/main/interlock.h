/*
 * interlock.h — over-pressure / over-inflation safety interlock (pure C, no ESP-IDF deps)
 *
 * DESIGN + STUB.  This module is the firmware side of the pre-stretch bench safety
 * interlock described in docs/PRESTRETCH-OVERPRESSURE-INTERLOCK.md.
 *
 * FAIL-SAFE INVARIANT (the whole point of this file):
 *   The FILL valve is NORMALLY CLOSED (energize-to-open).  The physical output is
 *   il_valve_energized(); it returns true ONLY while the interlock is in the ARMED
 *   state.  Every fault (over-pressure, sensor fault, fill-time timeout, manual
 *   abort) de-energizes the valve -> the fill path closes -> no further gas is added.
 *   A power loss, an MCU reset or a task hang therefore also closes the valve,
 *   because de-energized is the default and requires no firmware action.
 *
 * The logic is deliberately free of any hardware dependency so it can be unit-tested
 * on the host with plain gcc (tools/balloon_pressure_test/test/test_interlock.c).
 *
 * This file asserts NO hardware test was run.  Its thresholds are PLACEHOLDERS until
 * the bench session B1 of the design doc derives them.
 */
#ifndef BALLOON_INTERLOCK_H
#define BALLOON_INTERLOCK_H

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    IL_IDLE = 0,           /* disarmed; valve commanded CLOSED (safe)            */
    IL_ARMED,              /* filling permitted; valve may be energized (open)   */
    IL_TRIP_OVERPRESSURE,  /* latched: differential pressure ceiling exceeded    */
    IL_TRIP_SENSOR_FAULT,  /* latched: no valid pressure reading -> fail closed  */
    IL_TRIP_TIMEOUT,       /* latched: hard fill-time ceiling exceeded           */
    IL_TRIP_MANUAL,        /* latched: operator/commanded abort                  */
} il_state_t;

typedef struct {
    double dp_cutoff_mbar;  /* UNVALIDATED PLACEHOLDER ceil on (P_in - P_amb)     */
    double dp_reset_mbar;   /* dp must fall below this before a reset is allowed  */
    double max_fill_s;      /* hard fill-time ceiling (redundant backstop)        */
} il_cfg_t;

typedef struct {
    il_cfg_t   cfg;
    il_state_t state;
    double     elapsed_s;      /* seconds accumulated while ARMED                */
    double     dp_last;        /* last differential seen (for reset gating)      */
    bool       sensor_ok_last;
} il_t;

/* Lifecycle */
void il_init(il_t *il, const il_cfg_t *cfg);
void il_arm(il_t *il);                                     /* IDLE -> ARMED     */

/* One evaluation step.  Call every control-loop tick with the live values.
 *   dp_mbar   : P_internal - P_ambient   (mbar)
 *   sensor_ok : false if the reading is invalid/stale/out-of-range
 *   dt_s      : seconds since the previous tick                              */
void il_tick(il_t *il, double dp_mbar, bool sensor_ok, double dt_s);

/* Operator/commanded abort -> latched, fail closed. */
void il_abort(il_t *il);

/* Clear a latch.  Succeeds ONLY when the sensor is healthy AND dp has fallen
 * below cfg.dp_reset_mbar (i.e. the trip condition is actually gone).  Returns
 * true if the interlock returned to IDLE, false otherwise.                   */
bool il_reset(il_t *il, double dp_mbar, bool sensor_ok);

/* Physical valve output.  true == energized == OPEN (the ONLY state that opens).
 * Everything else, including every fault, returns false == CLOSED.           */
bool il_valve_energized(const il_t *il);

/* Alarm asserted whenever latched in any TRIP_* state. */
bool il_alarm(const il_t *il);

const char *il_state_name(il_state_t s);

/* Exercise every transition.  Returns the number of failed assertions (0 == PASS).
 * Used both by the host unit test and by a boot-time self-test in the rig. */
int il_selftest(void);

#endif /* BALLOON_INTERLOCK_H */
