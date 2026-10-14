#include "scheduler.h"

namespace balloon {

uint16_t Scheduler::budgetFor(const SchedulerInput &in) {
  // Sun contributes up to 20 units; buffer charge up to 10. Both must be clear
  // of zero for anything to run, which is what makes night a quiet period.
  const uint32_t from_sun = (static_cast<uint32_t>(in.irradiance) * 20u) / 1000u;
  const uint32_t from_buf = (static_cast<uint32_t>(in.buffer_charge_pct) * 10u) / 100u;
  return static_cast<uint16_t>(from_sun + from_buf);
}

SlotDecision Scheduler::decide(const SchedulerInput &in) {
  uint16_t budget = budgetFor(in);

  // 1. telemetry - always first, and it is the one task we would rather keep
  if (budget >= kTelemetryCost) {
    return SlotDecision{true, TaskKind::Telemetry, kTelemetryCost};
  }

  // 2. cold-start logging - only if enabled AND due
  if (in.cold_start_log_enabled && in.cold_start_log_due) {
    if (budget >= kColdStartCost) {
      return SlotDecision{true, TaskKind::ColdStartLog, kColdStartCost};
    }
  }

  // 3. link stats - only if enabled AND due
  if (in.link_stats_enabled && in.link_stats_due) {
    if (budget >= kLinkStatsCost) {
      return SlotDecision{true, TaskKind::LinkStats, kLinkStatsCost};
    }
  }

  return SlotDecision{false, TaskKind::Telemetry, 0};
}

}  // namespace balloon
