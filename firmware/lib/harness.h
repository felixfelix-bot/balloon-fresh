// Minimal host test harness — no PlatformIO, no Unity, no dependencies.
// Usage:
//   #include "harness.h"
//   void run_tests() { CASE("round trip"); CHECK(1 == 1); }
//   TEST_MAIN()
#pragma once

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

static int g_checks = 0;
static int g_fails = 0;
static const char *g_case = "(no case)";

#define CASE(name) \
  do { g_case = (name); } while (0)

#define CHECK(cond)                                                          \
  do {                                                                       \
    ++g_checks;                                                              \
    if (!(cond)) {                                                           \
      ++g_fails;                                                             \
      std::fprintf(stderr, "  FAIL %s:%d [%s]  %s\n", __FILE__, __LINE__,     \
                   g_case, #cond);                                           \
    }                                                                        \
  } while (0)

#define CHECK_EQ(a, b)                                                       \
  do {                                                                       \
    long long _a = (long long)(a), _b = (long long)(b);                       \
    ++g_checks;                                                              \
    if (_a != _b) {                                                          \
      ++g_fails;                                                             \
      std::fprintf(stderr, "  FAIL %s:%d [%s]  %s = %lld, expected %s = %lld\n",\
                   __FILE__, __LINE__, g_case, #a, _a, #b, _b);               \
    }                                                                        \
  } while (0)

#define CHECK_NEAR(a, b, eps)                                                \
  do {                                                                       \
    double _a = (double)(a), _b = (double)(b);                                \
    ++g_checks;                                                              \
    if (std::fabs(_a - _b) > (eps)) {                                        \
      ++g_fails;                                                             \
      std::fprintf(stderr,                                                   \
                   "  FAIL %s:%d [%s]  %s = %.6g, expected %s = %.6g\n",      \
                   __FILE__, __LINE__, g_case, #a, _a, #b, _b);               \
    }                                                                        \
  } while (0)

#define CHECK_STREQ(a, b)                                                    \
  do {                                                                       \
    ++g_checks;                                                              \
    if (std::strcmp((a), (b)) != 0) {                                         \
      ++g_fails;                                                             \
      std::fprintf(stderr, "  FAIL %s:%d [%s]  \"%s\" != \"%s\"\n", __FILE__,  \
                   __LINE__, g_case, (a), (b));                               \
    }                                                                        \
  } while (0)

#define TEST_MAIN()                                                          \
  extern void run_tests();                                                   \
  int main() {                                                               \
    run_tests();                                                             \
    if (g_fails == 0) {                                                      \
      std::printf("  ok   %d checks passed\n", g_checks);                     \
      return 0;                                                              \
    }                                                                        \
    std::printf("  FAIL %d of %d checks failed\n", g_fails, g_checks);        \
    return 1;                                                                \
  }
