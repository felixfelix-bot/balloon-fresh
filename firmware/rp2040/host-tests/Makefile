# Host-side unit tests for pure modules (no Arduino includes).
# Pattern: each test_*.cpp links against the corresponding src/*.cpp pure TU.
#
# Usage:  make -C firmware/rp2040/host-tests
#
# Mirrors E80 make test-host (cmake+ctest) but simpler — g++ pattern rule.

CXX      ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -Werror -O2 -g
SRC_DIR   = ../src

# --- test targets (add new test_*.cpp here) --------------------------------

TESTS = test_stats test_safety test_cmd

# Pattern: test_X links test_X.cpp + any needed src TUs
test_stats: test_stats.cpp $(SRC_DIR)/flrc_range_host_stats.cpp
	$(CXX) $(CXXFLAGS) -I$(SRC_DIR) -o $@ $^ -lm

test_safety: test_safety.cpp $(SRC_DIR)/flrc_range_host_safety.cpp
	$(CXX) $(CXXFLAGS) -I$(SRC_DIR) -o $@ $^ -lm

test_cmd: test_cmd.cpp $(SRC_DIR)/flrc_range_host_cmd.cpp
	$(CXX) $(CXXFLAGS) -I$(SRC_DIR) -o $@ $^

# --- catch-all ------------------------------------------------------------

.PHONY: all clean
all: $(TESTS)

clean:
	rm -f $(TESTS)