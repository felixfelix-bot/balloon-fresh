# Makefile — Balloon RP2040 firmware build, flash, and test targets
# Usage:
#   make flash-all      # Build + flash BOTH boards (reproducible, same config)
#   make flash-tx       # Build + flash TX only
#   make flash-rx       # Build + flash RX only
#   make build-all      # Build both (no flash)
#   make monitor-tx     # Read TX serial output
#   make monitor-rx     # Read RX serial output
#   make test           # Run pytest suite (hardware tests)
#   make test-unit      # Run unit tests only (no hardware)
#   make walk-test      # Start robust walk capture on RX board
#   make clean          # Clean build artifacts

# Board serial numbers (by USB ID_SERIAL_SHORT)
TX_SERIAL = E663B035977F242D
RX_SERIAL = E663B035973B8332

# PlatformIO paths
PIO = pio
FW_DIR = firmware/rp2040
TX_ENV = rp2040-sweep-tx
RX_ENV = rp2040-sweep-rx

# Python
PYTHON = python3
TOOLS_DIR = tools

# Default target
.DEFAULT_GOAL := help

##@ Help
.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

##@ Board Detection
.PHONY: detect
detect: ## Detect board ports by serial number
	@echo "=== Detecting boards ==="
	@for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		sn=$$(udevadm info -q property -n "$$p" 2>/dev/null | grep ID_SERIAL_SHORT | cut -d= -f2); \
		if echo "$$sn" | grep -q "$(TX_SERIAL)"; then \
			echo "TX board: $$p (serial=$$sn)"; \
		elif echo "$$sn" | grep -q "$(RX_SERIAL)"; then \
			echo "RX board: $$p (serial=$$sn)"; \
		else \
			echo "Unknown:  $$p (serial=$$sn)"; \
		fi; \
	done

##@ Build
.PHONY: build-tx build-rx build-all
build-tx: ## Build TX firmware
	cd $(FW_DIR) && $(PIO) run -e $(TX_ENV)

build-rx: ## Build RX firmware
	cd $(FW_DIR) && $(PIO) run -e $(RX_ENV)

build-all: build-tx build-rx ## Build both TX and RX firmware

##@ Flash (builds first, then flashes)
.PHONY: flash-tx flash-rx flash-all
flash-tx: build-tx ## Flash TX board (auto-detect port)
	@TX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(TX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$TX_PORT" ]; then echo "ERROR: TX board not found"; exit 1; fi; \
	echo "Flashing TX at $$TX_PORT"; \
	cd $(FW_DIR) && $(PIO) run -e $(TX_ENV) -t upload --upload-port $$TX_PORT

flash-rx: build-rx ## Flash RX board (auto-detect port)
	@RX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(RX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$RX_PORT" ]; then echo "ERROR: RX board not found"; exit 1; fi; \
	echo "Flashing RX at $$RX_PORT"; \
	cd $(FW_DIR) && $(PIO) run -e $(RX_ENV) -t upload --upload-port $$RX_PORT

flash-all: flash-tx flash-rx ## Flash BOTH boards (ensures same firmware version)

##@ Monitor
.PHONY: monitor-tx monitor-rx
monitor-tx: ## Read TX serial output (10s)
	@TX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(TX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$TX_PORT" ]; then echo "ERROR: TX board not found"; exit 1; fi; \
	echo "Monitoring TX at $$TX_PORT (Ctrl+C to stop)"; \
	stty -F $$TX_PORT 115200 raw -echo; cat $$TX_PORT

monitor-rx: ## Read RX serial output (10s)
	@RX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(RX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$RX_PORT" ]; then echo "ERROR: RX board not found"; exit 1; fi; \
	echo "Monitoring RX at $$RX_PORT (Ctrl+C to stop)"; \
	stty -F $$RX_PORT 115200 raw -echo; cat $$RX_PORT

##@ Walk Test
.PHONY: walk-test
walk-test: ## Start robust walk capture on RX board (runs until Ctrl+C)
	$(PYTHON) $(TOOLS_DIR)/walk_capture.py

##@ Testing
.PHONY: test test-unit test-hardware
test: ## Run full pytest suite (includes hardware tests)
	$(PYTHON) -m pytest tests/ -v --tb=short

test-unit: ## Run unit tests only (no hardware required)
	$(PYTHON) -m pytest tests/ -v --tb=short -m "not hardware"

test-hardware: ## Run hardware integration tests only (requires boards connected)
	$(PYTHON) -m pytest tests/ -v --tb=short -m "hardware"

##@ Clean
.PHONY: clean
clean: ## Clean PlatformIO build artifacts
	cd $(FW_DIR) && $(PIO) run -t clean
	rm -rf .pytest_cache tests/__pycache__
