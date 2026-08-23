# E80 bench firmware - convenience makefile
#
#   make            - cross-compile the firmware (cmake + arm-none-eabi-gcc)
#   make test-host  - build & run the host unit tests with the PC's gcc
#   make clean      - remove build artifacts
#
#   make range-setup    - Ansible: install deps + clone repo on both machines
#   make range-tx       - Distributed TX mode (single command, auto-detect)
#   make range-rx       - Distributed RX mode (single command, auto-detect)
#   make range-merge    - Merge TX+RX logs, compute PER, generate report
#   make range-dry-run  - Print schedule without touching hardware
#   make range-test-host - Run pytest for distributed split logic

CMAKE ?= cmake
BUILD := build-fw
TESTBUILD := build-host

# Firmware identity: sha7 of the repo HEAD, stamped into the binary and
# reported by ID? as fw=<sha7>. Queried at firmware-build time only.
FW_GIT_SHA := $(shell git rev-parse --short=7 HEAD 2>/dev/null || echo unknown)

# Distributed range test configuration
PYTHON        ?= python3
TOOLDIR       := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
E80_CTL       := $(PYTHON) $(TOOLDIR)/tools/e80_bench_ctl.py
MERGE_SCRIPT  := $(PYTHON) $(TOOLDIR)/tools/merge_csvs.py
REPO_ROOT     := $(abspath $(dir $(TOOLDIR)))
CONFIGS_DIR   := $(REPO_ROOT)/configs

# Default config preset + band
CONFIGS       ?= $(CONFIGS_DIR)/outdoor-10.json
BAND          ?= 868
TX_LOG        ?= tx-log.csv
RX_LOG        ?= rx-log.csv
OUT_DIR       ?= .
T0            ?= $(shell date -d '+5 minutes' '+%Y-%m-%d %H:%M' 2>/dev/null || echo '')

# Ansible
ANSIBLE_PLAYBOOK := ansible-playbook
ANSIBLE_INVENTORY := $(REPO_ROOT)/ansible/range-inventory.ini

.PHONY: all test-host clean firmware
.PHONY: range-setup range-tx range-rx range-merge range-dry-run range-test-host

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

# ============================================================
# DISTRIBUTED RANGE TEST TARGETS
# ============================================================

range-setup: ## Ansible: install openocd, pyserial, clone repo, verify boards (both machines)
	@echo "=== E80 Range Test Setup (Ansible) ==="
	$(ANSIBLE_PLAYBOOK) -i $(ANSIBLE_INVENTORY) $(REPO_ROOT)/ansible/range-setup.yml
	@echo "Setup complete. Run 'make range-dry-run' to verify."

range-tx: ## Distributed TX mode: auto-detect board, send bursts on T0 schedule
	@if [ -z "$(T0)" ]; then echo "ERROR: T0 required. Example: make range-tx T0='2026-08-30 14:00'"; exit 1; fi
	@echo "=== E80 Distributed TX Mode ==="
	@echo "  T0:      $(T0)"
	@echo "  Configs: $(CONFIGS)"
	@echo "  Band:    $(BAND) MHz"
	@echo ""
	cd $(TOOLDIR) && $(E80_CTL) --mode tx \
		--t0 "$(T0)" \
		--configs "$(CONFIGS)" \
		--tx-log "$(TX_LOG)" \
		--skip-fw-check

range-rx: ## Distributed RX mode: auto-detect board, capture packets on T0 schedule
	@if [ -z "$(T0)" ]; then echo "ERROR: T0 required. Example: make range-rx T0='2026-08-30 14:00'"; exit 1; fi
	@echo "=== E80 Distributed RX Mode ==="
	@echo "  T0:      $(T0)"
	@echo "  Configs: $(CONFIGS)"
	@echo "  Band:    $(BAND) MHz"
	@echo ""
	cd $(TOOLDIR) && $(E80_CTL) --mode rx \
		--t0 "$(T0)" \
		--configs "$(CONFIGS)" \
		--rx-log "$(RX_LOG)" \
		--skip-fw-check

range-merge: ## Merge TX+RX logs, compute PER, generate report
	@echo "=== Merging TX+RX Logs ==="
	@echo "  TX: $(TX)"
	@echo "  RX: $(RX)"
	@echo ""
	$(MERGE_SCRIPT) --tx "$(TX)" --rx "$(RX)" --out-dir "$(OUT_DIR)"

range-dry-run: ## Print schedule from config preset without touching hardware
	@echo "=== E80 Range Test Dry Run ==="
	@echo "  Configs: $(CONFIGS)"
	@echo ""
	cd $(TOOLDIR) && $(E80_CTL) --mode tx \
		--dry-run \
		--t0 "$(T0)" \
		--configs "$(CONFIGS)"

range-test-host: ## Run pytest for distributed range test split logic
	@echo "=== Running distributed range test unit tests ==="
	cd $(TOOLDIR)/tools && $(PYTHON) -m pytest test_e80_range_split.py -v
