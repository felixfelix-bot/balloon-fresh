# Host-side unit tests for pure modules (no Arduino includes).
# Pattern: each test_*.cpp links against the corresponding src/*.cpp pure TU.
#
# Usage:  make -C firmware/rp2040/host-tests
#
# Mirrors E80 make test-host (cmake+ctest) but simpler — g++ pattern rule.

CXX      ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -Werror -O2 -g
SRC_DIR   = ../src

# Header-only modules: test_X.cpp compiles alone (no src TU to link).

# --- test targets (add new test_*.cpp here) --------------------------------

TESTS = test_stats test_safety test_cmd test_bw_codes test_radio test_dispatch

# `all` is declared below; make it the default goal so a bare `make` builds
# every test (the first explicit rule would otherwise become the default).
.DEFAULT_GOAL := all

# Pattern: test_X links test_X.cpp + any needed src TUs
test_stats: test_stats.cpp $(SRC_DIR)/flrc_range_host_stats.cpp
	$(CXX) $(CXXFLAGS) -I$(SRC_DIR) -o $@ $^ -lm

test_safety: test_safety.cpp $(SRC_DIR)/flrc_range_host_safety.cpp
	$(CXX) $(CXXFLAGS) -I$(SRC_DIR) -o $@ $^ -lm

test_cmd: test_cmd.cpp $(SRC_DIR)/flrc_range_host_cmd.cpp
	$(CXX) $(CXXFLAGS) -I$(SRC_DIR) -o $@ $^

# BW-1: header-only shared table (lr2021_bw_codes.h) — no src TU to link.
test_bw_codes: test_bw_codes.cpp
	$(CXX) $(CXXFLAGS) -I$(SRC_DIR) -o $@ $^

# FW-5a: radio backend + band matrix. Links the safety TU too — the test
# asserts set_tx ticks derive from the FW-4 chip-timeout function.
test_radio: test_radio.cpp $(SRC_DIR)/flrc_range_host_radio.cpp $(SRC_DIR)/flrc_range_host_safety.cpp
	$(CXX) $(CXXFLAGS) -DBENCH_RADIO_HOST_TEST -I$(SRC_DIR) -o $@ $^

# FW-6: dispatch layer (state machine + plan + replies). Links the parser,
# safety (band/PA checks) and stats (embedded counters) pure TUs.
test_dispatch: test_dispatch.cpp $(SRC_DIR)/flrc_range_host_dispatch.cpp \
               $(SRC_DIR)/flrc_range_host_cmd.cpp \
               $(SRC_DIR)/flrc_range_host_safety.cpp \
               $(SRC_DIR)/flrc_range_host_stats.cpp
	$(CXX) $(CXXFLAGS) -I$(SRC_DIR) -o $@ $^

# --- catch-all ------------------------------------------------------------

.PHONY: all clean
all: $(TESTS)

clean:
	rm -f $(TESTS)