#include "expframework.h"

#include <cstring>

namespace balloon {

static void copyName(char *dst, const char *src) {
  size_t i = 0;
  for (; src != nullptr && src[i] != '\0' && i + 1 < kNameLen; ++i) dst[i] = src[i];
  dst[i] = '\0';
}

int ExperimentFramework::find(const char *name) const {
  if (name == nullptr) return -1;
  for (size_t i = 0; i < n_; ++i) {
    if (std::strcmp(e_[i].name, name) == 0) return static_cast<int>(i);
  }
  return -1;
}

ExpResult ExperimentFramework::add(const char *name, ExpBody body, void *ctx) {
  if (name == nullptr) return ExpResult::Unknown;
  if (find(name) >= 0) return ExpResult::Duplicate;
  if (n_ >= kMaxExperiments) return ExpResult::TooMany;

  Entry &e = e_[n_];
  copyName(e.name, name);
  e.body = body;
  e.ctx = ctx;
  e.st = ExpStat{};
  e.st.enabled = false;
  ++n_;
  return ExpResult::Ok;
}

ExpResult ExperimentFramework::enable(const char *name) {
  const int i = find(name);
  if (i < 0) return ExpResult::Unknown;
  e_[i].st.enabled = true;
  return ExpResult::Ok;
}

ExpResult ExperimentFramework::disable(const char *name) {
  const int i = find(name);
  if (i < 0) return ExpResult::Unknown;
  e_[i].st.enabled = false;
  return ExpResult::Ok;
}

ExpResult ExperimentFramework::tick(const char *name) {
  const int i = find(name);
  if (i < 0) return ExpResult::Unknown;
  Entry &e = e_[i];

  // THE zero-cost rule: a disabled experiment is not run, and nothing about it
  // is touched. Return before any side effect whatsoever.
  if (!e.st.enabled) return ExpResult::Disabled;

  e.st.ran = true;
  ++e.st.ticks;
  if (e.body != nullptr) {
    e.st.last_value = e.body(e.ctx);
  }
  return ExpResult::Ok;
}

ExpResult ExperimentFramework::sample(const char *name, uint16_t &value) {
  const int i = find(name);
  if (i < 0) return ExpResult::Unknown;
  Entry &e = e_[i];

  if (!e.st.enabled) return ExpResult::Disabled;  // no slot consumed
  if (!e.st.ran) return ExpResult::Disabled;      // nothing to report yet
  if (slots_left_ == 0) return ExpResult::SlotFull;

  --slots_left_;
  ++e.st.samples;
  value = e.st.last_value;
  return ExpResult::Ok;
}

bool ExperimentFramework::stat(const char *name, ExpStat &out) const {
  const int i = find(name);
  if (i < 0) return false;
  out = e_[i].st;
  return true;
}

}  // namespace balloon
