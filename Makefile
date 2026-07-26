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
#   make find-ports     # Identify all connected boards
#   make sync-time      # Sync TX time from laptop clock
#   make bootsel-1200-tx  # Flash TX via UF2 (no PlatformIO needed, BOOTSEL mode)
#   make bootsel-1200-rx  # Flash RX via UF2 (no PlatformIO needed, BOOTSEL mode)
#   make clean          # Clean build artifacts

# Board serial numbers (by USB ID_SERIAL_SHORT)
# TX board: E663B035977F242D (ends in F242D)
# RX board: E663B035973B8332 (ends in 8332)
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
.PHONY: detect find-ports identify-ports
detect: find-ports ## Detect board ports by serial number

find-ports: ## Identify all connected boards
	@echo "=== Board Port Assignments ==="
	@for port in /dev/ttyACM[0-9]; do \
		[ -e "$$port" ] || continue; \
		sn=$$(udevadm info -q property -n "$$port" 2>/dev/null | grep ID_SERIAL_SHORT | cut -d= -f2); \
		vid=$$(udevadm info -q property -n "$$port" 2>/dev/null | grep ID_VENDOR_ID | cut -d= -f2); \
		pid=$$(udevadm info -q property -n "$$port" 2>/dev/null | grep ID_MODEL_ID | cut -d= -f2); \
		if echo "$$sn" | grep -q "$(TX_SERIAL)"; then \
			echo "  $$port: TX board (F242D) [RP2040, PID $$pid]"; \
		elif echo "$$sn" | grep -q "$(RX_SERIAL)"; then \
			echo "  $$port: RX board (8332) [RP2040, PID $$pid]"; \
		elif echo "$$vid" | grep -q "303a"; then \
			echo "  $$port: ESP32 [$$sn]"; \
		else \
			echo "  $$port: Unknown [$$sn, VID=$$vid PID=$$pid]"; \
		fi; \
	done
	@echo ""
	@RP2_BOOT=$$(lsusb 2>/dev/null | grep "2e8a:0003" | wc -l); \
	RP2_APP=$$(lsusb 2>/dev/null | grep "2e8a:000a" | wc -l); \
	echo "  BOOTSEL mode: $$RP2_BOOT boards | App mode: $$RP2_APP boards"

identify-ports: find-ports ## Alias for find-ports

##@ Build
.PHONY: build-tx build-rx build-all
build-tx: ## Build TX firmware
	cd $(FW_DIR) && $(PIO) run -e $(TX_ENV)

build-rx: ## Build RX firmware
	cd $(FW_DIR) && $(PIO) run -e $(RX_ENV)

build-all: build-tx build-rx ## Build both TX and RX firmware

##@ Flash via PlatformIO (builds first, then flashes)
.PHONY: flash-tx flash-rx flash-all
flash-tx: build-tx ## Flash TX board (auto-detect port by serial)
	@TX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(TX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$TX_PORT" ]; then echo "ERROR: TX board not found. Run: make find-ports"; exit 1; fi; \
	echo "Flashing TX at $$TX_PORT"; \
	cd $(FW_DIR) && $(PIO) run -e $(TX_ENV) -t upload --upload-port $$TX_PORT

flash-rx: build-rx ## Flash RX board (auto-detect port by serial)
	@RX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(RX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$RX_PORT" ]; then echo "ERROR: RX board not found. Run: make find-ports"; exit 1; fi; \
	echo "Flashing RX at $$RX_PORT"; \
	cd $(FW_DIR) && $(PIO) run -e $(RX_ENV) -t upload --upload-port $$RX_PORT

flash-all: flash-tx flash-rx ## Flash BOTH boards (ensures same firmware version)

##@ Flash via BOOTSEL (UF2 copy — no PlatformIO needed, works on any laptop)
.PHONY: bootsel-1200 bootsel-1200-tx bootsel-1200-rx
bootsel-1200: ## Flash via 1200-baud touch. Usage: make bootsel-1200 PORT=/dev/ttyACMX UF2=path.uf2
	@if [ -z "$(PORT)" ] || [ -z "$(UF2)" ]; then \
		echo "Usage: make bootsel-1200 PORT=/dev/ttyACMX UF2=path.uf2"; \
		echo ""; \
		echo "Identify ports first: make find-ports"; \
		exit 1; \
	fi
	@echo "Triggering BOOTSEL on $(PORT)..."
	@python3 -c "import serial; s=serial.Serial('$(PORT)',1200); s.close()" 2>/dev/null || \
		stty -F $(PORT) 1200 raw -echo 2>/dev/null || true
	@sleep 2
	@DEV=$$(lsblk -lnpo NAME,MODEL 2>/dev/null | grep 'RP2' | head -1 | awk '{print $$1}'); \
	if [ -z "$$DEV" ]; then \
		echo "ERROR: No RP2 mass storage found. Board may already be in BOOTSEL."; \
		echo "Check: lsblk | grep RP2"; \
		exit 1; \
	fi; \
	PART="$${DEV}1"; \
	echo "Found RP2 at $$PART — flashing $(UF2)..."; \
	sudo mount $$PART /mnt 2>/dev/null || true; \
	sudo cp "$(UF2)" /mnt/ && sync && sudo umount /mnt; \
	echo "FLASH OK — board rebooting"
	@sleep 3

bootsel-1200-tx: ## Flash TX via UF2. Usage: make bootsel-1200-tx UF2=path/to/tx.uf2
	@PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q "$(TX_SERIAL)" && echo "$$p" && break; \
	done); \
	if [ -z "$$PORT" ]; then echo "ERROR: TX board (F242D) not found. Run: make find-ports"; exit 1; fi; \
	echo "TX (F242D) found at $$PORT"; \
	$(MAKE) bootsel-1200 PORT=$$PORT UF2=$(UF2)

bootsel-1200-rx: ## Flash RX via UF2. Usage: make bootsel-1200-rx UF2=path/to/rx.uf2
	@PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q "$(RX_SERIAL)" && echo "$$p" && break; \
	done); \
	if [ -z "$$PORT" ]; then echo "ERROR: RX board (8332) not found. Run: make find-ports"; exit 1; fi; \
	echo "RX (8332) found at $$PORT"; \
	$(MAKE) bootsel-1200 PORT=$$PORT UF2=$(UF2)

##@ Monitor
.PHONY: monitor-tx monitor-rx
monitor-tx: ## Read TX serial output (Ctrl+C to stop)
	@TX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(TX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$TX_PORT" ]; then echo "ERROR: TX board not found. Run: make find-ports"; exit 1; fi; \
	echo "Monitoring TX at $$TX_PORT (Ctrl+C to stop)"; \
	stty -F $$TX_PORT 115200 raw -echo; cat $$TX_PORT

monitor-rx: ## Read RX serial output (Ctrl+C to stop)
	@RX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(RX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$RX_PORT" ]; then echo "ERROR: RX board not found. Run: make find-ports"; exit 1; fi; \
	echo "Monitoring RX at $$RX_PORT (Ctrl+C to stop)"; \
	stty -F $$RX_PORT 115200 raw -echo; cat $$RX_PORT

##@ Time Sync
.PHONY: sync-time sync-tx sync-rx
sync-tx: ## Sync TX board time from laptop clock
	@TX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(TX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$TX_PORT" ]; then echo "ERROR: TX board not found. Run: make find-ports"; exit 1; fi; \
	echo "Syncing TX at $$TX_PORT..."; \
	$(PYTHON) -c "import serial,time; s=serial.Serial('$$TX_PORT',115200); s.write(f'SET_TIME {int(time.time())}\n'.encode()); print('TX synced to', int(time.time())); s.close()"

sync-rx: ## Sync RX board time from laptop clock
	@RX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(RX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$RX_PORT" ]; then echo "ERROR: RX board not found. Run: make find-ports"; exit 1; fi; \
	echo "Syncing RX at $$RX_PORT..."; \
	$(PYTHON) -c "import serial,time; s=serial.Serial('$$RX_PORT',115200); s.write(f'SET_TIME {int(time.time())}\n'.encode()); print('RX synced to', int(time.time())); s.close()"

sync-time: sync-tx ## Alias for sync-tx

##@ Walk Test
.PHONY: walk-test
walk-test: ## Start robust walk capture on RX board (runs until Ctrl+C)
	@RX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(RX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$RX_PORT" ]; then echo "ERROR: RX board not found. Run: make find-ports"; exit 1; fi; \
	echo "Starting walk capture on RX at $$RX_PORT (Ctrl+C to stop)"; \
	$(PYTHON) $(TOOLS_DIR)/walk_capture.py 7200 $$RX_PORT

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
