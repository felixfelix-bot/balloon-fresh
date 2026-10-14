// TDD entry point for H2. RED first: expframework.cpp absent -> build failure.
#include "harness.h"
#include "expframework.h"

#include <cstring>

using namespace balloon;

static uint32_t g_calls = 0;
static uint16_t bodyA(void *) { ++g_calls; return 111; }
static uint16_t bodyB(void *) { ++g_calls; return 222; }

void run_tests() {
  CASE("registering and finding experiments");
  {
    ExperimentFramework fw;
    CHECK(fw.add("coldstart", bodyA, nullptr) == ExpResult::Ok);
    CHECK(fw.add("linkstats", bodyB, nullptr) == ExpResult::Ok);
    CHECK_EQ(fw.count(), 2u);
    CHECK(fw.add("coldstart", bodyA, nullptr) == ExpResult::Duplicate);
    CHECK(fw.enable("nope") == ExpResult::Unknown);
    CHECK(fw.tick("nope") == ExpResult::Unknown);
  }

  CASE("a disabled experiment is never run");
  {
    g_calls = 0;
    ExperimentFramework fw;
    fw.add("coldstart", bodyA, nullptr);   // registered but NOT enabled
    CHECK(fw.tick("coldstart") == ExpResult::Disabled);
    CHECK_EQ(g_calls, 0u);                 // the body was not called at all

    ExpStat st{};
    CHECK(fw.stat("coldstart", st));
    CHECK(!st.enabled);
    CHECK(!st.ran);                        // and it is not marked as having run
    CHECK_EQ(st.ticks, 0u);
  }

  CASE("enabling makes it run, and only then");
  {
    g_calls = 0;
    ExperimentFramework fw;
    fw.add("coldstart", bodyA, nullptr);
    CHECK(fw.enable("coldstart") == ExpResult::Ok);
    CHECK(fw.tick("coldstart") == ExpResult::Ok);
    CHECK_EQ(g_calls, 1u);
    CHECK(fw.tick("coldstart") == ExpResult::Ok);
    CHECK_EQ(g_calls, 2u);

    ExpStat st{};
    fw.stat("coldstart", st);
    CHECK(st.ran);
    CHECK_EQ(st.ticks, 2u);
    CHECK_EQ(st.last_value, 111);

    fw.disable("coldstart");
    CHECK(fw.tick("coldstart") == ExpResult::Disabled);
    CHECK_EQ(g_calls, 2u);                 // no further calls
    fw.stat("coldstart", st);
    CHECK_EQ(st.ticks, 2u);                // counters frozen
  }

  CASE("ZERO-COST: a disabled experiment consumes no telemetry slot");
  {
    ExperimentFramework fw;
    fw.add("coldstart", bodyA, nullptr);
    fw.setSlotBudget(1);
    CHECK_EQ(fw.slotBudgetRemaining(), 1u);

    uint16_t v = 0;
    // disabled -> refused, and crucially the slot budget is untouched
    CHECK(fw.sample("coldstart", v) == ExpResult::Disabled);
    CHECK_EQ(fw.slotBudgetRemaining(), 1u);

    // now enable + tick: it may take the one slot
    fw.enable("coldstart");
    fw.tick("coldstart");
    CHECK(fw.sample("coldstart", v) == ExpResult::Ok);
    CHECK_EQ(v, 111u);
    CHECK_EQ(fw.slotBudgetRemaining(), 0u);

    // and the budget is now genuinely exhausted
    CHECK(fw.sample("coldstart", v) == ExpResult::SlotFull);
  }

  CASE("ZERO-COST: two experiments, one disabled, share cleanly");
  {
    g_calls = 0;
    ExperimentFramework fw;
    fw.add("coldstart", bodyA, nullptr);
    fw.add("linkstats", bodyB, nullptr);
    fw.enable("linkstats");
    fw.setSlotBudget(2);

    CHECK(fw.tick("coldstart") == ExpResult::Disabled);  // off: no call
    CHECK(fw.tick("linkstats") == ExpResult::Ok);

    uint16_t v = 0;
    CHECK(fw.sample("coldstart", v) == ExpResult::Disabled);
    CHECK_EQ(fw.slotBudgetRemaining(), 2u);              // untouched by the off one
    CHECK(fw.sample("linkstats", v) == ExpResult::Ok);
    CHECK_EQ(v, 222u);
    CHECK_EQ(fw.slotBudgetRemaining(), 1u);              // only one slot used
    CHECK_EQ(g_calls, 1u);                               // exactly one body call
  }

  CASE("COUNTER-TEST: the enable flag is what gates work, not the body");
  {
    // If the gate were removed, the disabled case below would run and the call
    // count would rise. Same inputs twice, differing only in the enable flag.
    g_calls = 0;
    ExperimentFramework fw;
    fw.add("e", bodyA, nullptr);

    fw.tick("e");                    // disabled
    const uint32_t after_disabled = g_calls;

    fw.enable("e");
    fw.tick("e");                    // enabled
    CHECK_EQ(after_disabled, 0u);
    CHECK_EQ(g_calls, 1u);           // and the difference is exactly one call
  }

  CASE("registry limits are enforced, not silently ignored");
  {
    ExperimentFramework fw;
    char name[8];
    for (size_t i = 0; i < kMaxExperiments; ++i) {
      std::snprintf(name, sizeof name, "e%zu", i);
      CHECK(fw.add(name, bodyA, nullptr) == ExpResult::Ok);
    }
    CHECK(fw.add("one-too-many", bodyA, nullptr) == ExpResult::TooMany);
    CHECK_EQ(fw.count(), kMaxExperiments);
  }
}

TEST_MAIN()
