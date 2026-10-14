// H1 - energy-budgeted duty scheduler. PURE LOGIC: no I/O, no timers, no radio.
// Decisions are returned as data so they are testable without hardware.
//
// Priorities, highest first: telemetry > cold-start logging > link stats.
// An experiment that is not enabled must consume ZERO slots and ZERO budget -
// that is asserted, not assumed (see the zero-cost test).
#pragma once

#include <cstddef>
#include <cstdint>

namespace balloon {

enum class TaskKind : uint8_t {
  Telemetry = 0,
  ColdStartLog = 1,
  LinkStats = 2,
};

struct TaskCost {
  TaskKind kind;
  uint16_t energy_units;  // abstract budget units, comparable to solar input
  uint16_t duration_ms;
};

// One decision: what to run in a slot, or nothing.
struct SlotDecision {
  bool run;
  TaskKind kind;
  uint16_t energy_units;
};

// Inputs for one scheduling step. `irradiance` is a 0..1000 normalised sun
// figure (0 = night); `buffer_charge_pct` is 0..100 of whatever buffer exists.
struct SchedulerInput {
  uint16_t irradiance;
  uint8_t buffer_charge_pct;
  bool cold_start_log_enabled;
  bool link_stats_enabled;
  bool cold_start_log_due;
  bool link_stats_due;
};

class Scheduler {
 public:
  // Budget available for this step, derived from sun + buffer.
  static uint16_t budgetFor(const SchedulerInput &in);

  // The decision. Telemetry wins whenever it fits; a lower-priority task runs
  // only if it is BOTH due/enabled AND its cost fits the remaining budget.
  static SlotDecision decide(const SchedulerInput &in);

  static constexpr uint16_t kTelemetryCost = 10;
  static constexpr uint16_t kColdStartCost = 6;
  static constexpr uint16_t kLinkStatsCost = 4;
};

}  // namespace balloon
