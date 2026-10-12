/*
 * test_interlock.c — host unit test for the pre-stretch over-pressure interlock.
 *
 * Builds with plain gcc, no ESP-IDF, no hardware:
 *     make -C tools/balloon_pressure_test/test check
 *
 * What it proves (all in software — NO hardware test is claimed):
 *   - an over-pressure reading closes the fill valve and raises the alarm;
 *   - a sensor fault fails CLOSED (the fail-safe direction);
 *   - a fill-time overrun trips;
 *   - every trip latches and can only be cleared by an explicit, condition-aware reset;
 *   - the global invariant: the fill valve is energized for exactly one state,
 *     and no alarming state ever leaves it energized.
 */
#include "interlock.h"

#include <stdio.h>

static int g_fail = 0;
static int g_pass = 0;

#define EXPECT(cond, msg) do {                                    \
        if (cond) { g_pass++; }                                   \
        else { g_fail++; printf("  FAIL: %s\n", (msg)); }         \
    } while (0)

static il_cfg_t cfg(void)
{
    il_cfg_t c = { .dp_cutoff_mbar = 5.0, .dp_reset_mbar = 2.0, .max_fill_s = 3600.0 };
    return c;
}

static void test_nominal_fill(void)
{
    il_t il; il_cfg_t c = cfg();
    il_init(&il, &c);
    il_arm(&il);
    il_tick(&il, 1.0, true, 1.0);
    EXPECT(il.state == IL_ARMED,                        "armed after arm+tick");
    EXPECT(il_valve_energized(&il) == true,             "valve open while armed");
    EXPECT(il_alarm(&il) == false,                      "no alarm while healthy");
}

static void test_overpressure_cutoff(void)
{
    il_t il; il_cfg_t c = cfg();
    il_init(&il, &c);
    il_arm(&il);
    il_tick(&il, c.dp_cutoff_mbar + 0.5, true, 1.0);
    EXPECT(il.state == IL_TRIP_OVERPRESSURE,            "over-pressure trips");
    EXPECT(il_valve_energized(&il) == false,            "fill valve CLOSES on over-pressure");
    EXPECT(il_alarm(&il) == true,                       "alarm raised on over-pressure");
    /* latch: clearing the reading does not clear the trip */
    il_tick(&il, 0.0, true, 1.0);
    EXPECT(il.state == IL_TRIP_OVERPRESSURE,            "over-pressure trip latches");
    EXPECT(il_valve_energized(&il) == false,            "valve stays closed while latched");
}

static void test_sensor_fault_fails_closed(void)
{
    il_t il; il_cfg_t c = cfg();
    il_init(&il, &c);
    il_arm(&il);
    il_tick(&il, 1.0, false, 1.0);
    EXPECT(il.state == IL_TRIP_SENSOR_FAULT,            "sensor fault trips");
    EXPECT(il_valve_energized(&il) == false,            "valve fails CLOSED (fail-safe direction)");
    EXPECT(il_alarm(&il) == true,                       "alarm raised on sensor fault");
}

static void test_timeout(void)
{
    il_t il; il_cfg_t c = cfg();
    il_init(&il, &c);
    il_arm(&il);
    il_tick(&il, 1.0, true, c.max_fill_s + 1.0);
    EXPECT(il.state == IL_TRIP_TIMEOUT,                 "fill-time ceiling trips");
    EXPECT(il_valve_energized(&il) == false,            "valve closed on timeout");
}

static void test_reset_is_conditional(void)
{
    il_t il; il_cfg_t c = cfg();
    il_init(&il, &c);
    il_arm(&il);
    il_tick(&il, c.dp_cutoff_mbar + 0.5, true, 1.0);

    EXPECT(il_reset(&il, c.dp_reset_mbar + 0.5, true) == false,  "reset refused while dp high");
    EXPECT(il_reset(&il, c.dp_reset_mbar - 0.5, false) == false, "reset refused while sensor bad");
    EXPECT(il_reset(&il, c.dp_reset_mbar - 0.5, true) == true,   "reset accepted when healthy+low");
    EXPECT(il.state == IL_IDLE,                                 "state IDLE after reset");
    EXPECT(il_valve_energized(&il) == false,                    "reset does not auto-open valve");
    il_arm(&il);
    EXPECT(il_valve_energized(&il) == true,                     "re-arm opens valve again");
}

static void test_manual_abort_and_arming_latch(void)
{
    il_t il; il_cfg_t c = cfg();
    il_init(&il, &c);
    il_arm(&il);
    il_abort(&il);
    EXPECT(il.state == IL_TRIP_MANUAL,                  "manual abort trips");
    EXPECT(il_valve_energized(&il) == false,            "valve closed on manual abort");
    il_arm(&il);                                        /* must NOT clear a latch */
    EXPECT(il.state == IL_TRIP_MANUAL,                  "arming a latched interlock is a no-op");
}

static void test_global_invariant(void)
{
    il_cfg_t c = cfg();
    il_state_t s;
    for (s = IL_IDLE; s <= IL_TRIP_MANUAL; s++) {
        il_t probe; il_init(&probe, &c);
        probe.state = s;
        if (il_alarm(&probe)) {
            EXPECT(il_valve_energized(&probe) == false,
                   "INVARIANT: alarming state never leaves the valve energized");
        }
        EXPECT(il_valve_energized(&probe) == (s == IL_ARMED),
               "INVARIANT: valve energized for exactly the ARMED state");
    }
}

int main(void)
{
    test_nominal_fill();
    test_overpressure_cutoff();
    test_sensor_fault_fails_closed();
    test_timeout();
    test_reset_is_conditional();
    test_manual_abort_and_arming_latch();
    test_global_invariant();

    /* the module's own boot-time self-test must also pass */
    int self_fail = il_selftest();
    EXPECT(self_fail == 0, "il_selftest() returns 0 failures");

    printf("test_interlock: %d passed, %d failed\n", g_pass, g_fail);
    return (g_fail == 0) ? 0 : 1;
}
