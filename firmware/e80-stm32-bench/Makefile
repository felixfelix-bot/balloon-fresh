# E80 bench firmware - convenience makefile
#
#   make            - cross-compile the firmware (cmake + arm-none-eabi-gcc)
#   make test-host  - build & run the host unit tests with the PC's gcc
#   make clean      - remove build artifacts

CMAKE ?= cmake
BUILD := build-fw
TESTBUILD := build-host

# Firmware identity: sha7 of the repo HEAD, stamped into the binary and
# reported by ID? as fw=<sha7>. Queried at firmware-build time only.
FW_GIT_SHA := $(shell git rev-parse --short=7 HEAD 2>/dev/null || echo unknown)

.PHONY: all test-host clean firmware

all: firmware

firmware:
	$(CMAKE) -B $(BUILD) -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake \
		-DCMAKE_BUILD_TYPE=Release -DFW_GIT_SHA=$(FW_GIT_SHA) .
	$(CMAKE) --build $(BUILD)

test-host:
	$(CMAKE) -B $(TESTBUILD) tests
	$(CMAKE) --build $(TESTBUILD)
	cd $(TESTBUILD) && ctest --output-on-failure

clean:
	rm -rf $(BUILD) $(TESTBUILD)
