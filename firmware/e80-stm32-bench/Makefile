# E80 bench firmware - convenience makefile
#
#   make            - cross-compile the firmware (cmake + arm-none-eabi-gcc)
#   make test-host  - build & run the host unit tests with the PC's gcc
#   make clean      - remove build artifacts

CMAKE ?= cmake
BUILD := build-fw
TESTBUILD := build-host

.PHONY: all test-host clean firmware

all: firmware

firmware:
	$(CMAKE) -B $(BUILD) -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake -DCMAKE_BUILD_TYPE=Release .
	$(CMAKE) --build $(BUILD)

test-host:
	$(CMAKE) -B $(TESTBUILD) tests
	$(CMAKE) --build $(TESTBUILD)
	cd $(TESTBUILD) && ctest --output-on-failure

clean:
	rm -rf $(BUILD) $(TESTBUILD)
