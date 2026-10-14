// TDD entry point for H1. RED first: scheduler.cpp absent -> build failure.
#include "harness.h"
#include "scheduler.h"

using namespace balloon;

static SchedulerInput base() {
  SchedulerInput in{};
  in.irradiance = 1000;      // full sun
  in.buffer_charge_pct = 100;
  in.cold_start_log_enabled = false;
  in.link_stats_enabled = false;
  in.cold_start_log_due = false;
  in.link_stats_due = false;
  return in;
}

void run_tests() {
  CASE("night with empty buffer runs nothing");
  {
    SchedulerInput in = base();
    in.irradiance = 0;
    in.buffer_charge_pct = 0;
    SlotDecision d = Scheduler::decide(in);
    CHECK(!d.run);
    CHECK_EQ(d.energy_units, 0);
  }

  CASE("telemetry has priority over everything else");
  {
    SchedulerInput in = base();
    in.cold_start_log_enabled = true;
    in.cold_start_log_due = true;
    in.link_stats_enabled = true;
    in.link_stats_due = true;
    SlotDecision d = Scheduler::decide(in);
    CHECK(d.run);
    CHECK(d.kind == TaskKind::Telemetry);
  }

  CASE("budget is derived from sun and buffer, monotonically");
  {
    SchedulerInput dark = base();
    dark.irradiance = 0;
    dark.buffer_charge_pct = 0;
    SchedulerInput lit = base();
    CHECK(Scheduler::budgetFor(lit) > Scheduler::budgetFor(dark));
    CHECK_EQ(Scheduler::budgetFor(dark), 0);
  }

  CASE("ZERO-COST: a disabled experiment consumes zero slots");
  {
    SchedulerInput in = base();
    // starve the budget so only telemetry fits
    in.irradiance = 0;
    in.buffer_charge_pct = 30;  // -> 3 units, below every task

    // disabled + due: must still not run
    in.cold_start_log_enabled = false;
    in.cold_start_log_due = true;
    SlotDecision d1 = Scheduler::decide(in);
    CHECK(!d1.run);
    CHECK_EQ(d1.energy_units, 0);

    // exactly the same inputs, but now enabled -> the only difference is the flag
    in.cold_start_log_enabled = true;
    in.irradiance = 300;  // 6 units -> cold-start cost exactly fits
    SlotDecision d2 = Scheduler::decide(in);
    CHECK(d2.run);
    CHECK(d2.kind == TaskKind::ColdStartLog);

    // and with it disabled again, nothing runs at that same budget
    in.cold_start_log_enabled = false;
    SlotDecision d3 = Scheduler::decide(in);
    CHECK(!d3.run);
    CHECK_EQ(d3.energy_units, 0);
  }

  CASE("ZERO-COST: disabled link stats never runs, even when due and affordable");
  {
    SchedulerInput in = base();
    in.irradiance = 0;
    in.buffer_charge_pct = 100;  // 10 units, plenty
    in.link_stats_enabled = false;
    in.link_stats_due = true;
    in.cold_start_log_enabled = false;
    in.cold_start_log_due = false;
    // telemetry is always first at this budget, so it wins - and crucially link
    // stats is NOT what gets returned
    SlotDecision d = Scheduler::decide(in);
    CHECK(d.run);
    CHECK(d.kind == TaskKind::Telemetry);
  }

  CASE("COUNTER-TEST: the priority order is real - swapping it changes the answer");
  {
    // starve to exactly the link-stats cost so only a lower-priority task could
    // fit; telemetry must NOT run, which proves telemetry is gated by cost too
    SchedulerInput in = base();
    in.irradiance = 200;         // 4 units
    in.buffer_charge_pct = 0;
    in.link_stats_enabled = true;
    in.link_stats_due = true;
    SlotDecision d = Scheduler::decide(in);
    CHECK(d.run);
    CHECK(d.kind == TaskKind::LinkStats);  // telemetry did not fit, so it fell through
    CHECK_EQ(d.energy_units, Scheduler::kLinkStatsCost);
  }
}

TEST_MAIN()
