# Host-side unit tests for range_test.h — plain host g++, no ESP-IDF.
# One binary per test_*.cpp; `make test` builds and runs all, failing on any.
CXX ?= g++
CXXFLAGS ?= -Wall -Wextra -std=c++17 -I..

BINARIES := $(patsubst %.cpp,%,$(wildcard test_*.cpp))

.PHONY: all test clean
all: $(BINARIES)

test: $(BINARIES)
	@fail=0; \
	for bin in $(BINARIES); do \
	  echo "== $$bin"; \
	  ./$$bin || fail=1; \
	done; \
	exit $$fail

clean:
	rm -f $(BINARIES)

%: %.cpp
	$(CXX) $(CXXFLAGS) -o $@ $<
