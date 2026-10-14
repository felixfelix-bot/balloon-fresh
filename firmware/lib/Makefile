# Host tests for the flight-software libraries. g++ only; no PlatformIO.
#
# Modules AUTO-DISCOVER: any directory containing test_*.cpp is built and run.
# Adding a module therefore never edits this file -> parallel workers adding
# separate module directories cannot conflict on it.
CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O1 -Wall -Wextra -g
BUILD    ?= build

.PHONY: all test clean

all: test

test:
	@mkdir -p $(BUILD)
	@fail=0; found=0; \
	for d in $$(ls -d */ 2>/dev/null); do \
		m=$${d%/}; \
		ls $$m/test_*.cpp >/dev/null 2>&1 || continue; \
		found=1; \
		echo "== $$m =="; \
		if $(CXX) $(CXXFLAGS) -I. -I$$m -o $(BUILD)/$$m.test $$m/*.cpp; then \
			if ./$(BUILD)/$$m.test; then :; else fail=1; fi; \
		else fail=1; fi; \
	done; \
	if [ $$found -eq 0 ]; then echo "no module tests found"; exit 1; fi; \
	if [ $$fail -ne 0 ]; then echo "RESULT: FAILURES"; exit 1; fi; \
	echo "RESULT: all module tests green"

clean:
	rm -rf $(BUILD)
