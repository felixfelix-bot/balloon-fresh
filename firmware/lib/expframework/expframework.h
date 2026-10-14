// H2 - experiment framework: enable/disable a named experiment from the ground,
// give it its own telemetry slot, and PROVE that a disabled experiment is
// zero-cost.
//
// "Zero cost" here is a checkable claim, not a slogan: when an experiment is
// disabled, tick() must neither call the experiment nor consume a telemetry
// slot nor advance any counter that would imply work happened.
#pragma once

#include <cstddef>
#include <cstdint>

namespace balloon {

constexpr size_t kMaxExperiments = 8;
constexpr size_t kNameLen = 16;

enum class ExpResult : uint8_t {
  Ok = 0,
  TooMany,      // registry full
  Duplicate,    // name already registered
  Unknown,      // name not registered
  Disabled,     // tick() refused because it is off
  SlotFull,     // no telemetry slot available for this experiment
};

struct ExpStat {
  bool enabled;
  bool ran;            // has tick() ever executed the body while enabled
  uint32_t ticks;      // times the body ran
  uint32_t samples;    // telemetry samples emitted
  uint16_t last_value; // whatever the experiment last produced
};

// The experiment body is injected, so this module has no hardware or timing
// dependency and is fully host-testable.
using ExpBody = uint16_t (*)(void *ctx);

class ExperimentFramework {
 public:
  ExpResult add(const char *name, ExpBody body, void *ctx);
  ExpResult enable(const char *name);
  ExpResult disable(const char *name);
  ExpResult tick(const char *name);

  // Emits one telemetry sample for `name` if it is enabled and has produced a
  // value. Returns SlotFull when the slot budget is exhausted.
  ExpResult sample(const char *name, uint16_t &value);

  bool stat(const char *name, ExpStat &out) const;
  size_t count() const { return n_; }
  size_t slotBudgetRemaining() const { return slots_left_; }

  void setSlotBudget(size_t n) { slots_left_ = n; }

 private:
  struct Entry {
    char name[kNameLen];
    ExpBody body;
    void *ctx;
    ExpStat st;
  };
  int find(const char *name) const;

  Entry e_[kMaxExperiments];
  size_t n_ = 0;
  size_t slots_left_ = 0;
};

}  // namespace balloon
