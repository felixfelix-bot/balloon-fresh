# ============================================================
# E80 Range Test — Operator Command Structure
# ============================================================
# One Makefile. One command per task. Auto-detects everything.
#
# QUICK START (operator with minimal Linux experience):
#
#   On the TX machine:       make tx-server
#   On the RX machine:       make rx-server
#   From the operator's PC:  make range-test TX_HOST=<tx-ip> RX_HOST=<rx-ip>
#
# Or if you don't know which board is which:
#   make range-test HOST_A=<ip> HOST_B=<ip>   [GPS=...] [SITE=...]
#
# See: make help  (for all targets)
# ============================================================

PYTHON        ?= python3
TOOLDIR       := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
E80_DETECT    := $(PYTHON) $(TOOLDIR)e80_detect.py
E80_SERVER    := $(PYTHON) $(TOOLDIR)e80_board_server.py
E80_RANGE     := $(PYTHON) $(TOOLDIR)e80_range_test.py
TCP_PORT      ?= 7780

# Default test parameters (override on command line: make range-test FREQ=915000000)
FREQ          ?= 868000000
DBM           ?= 10
SITE          ?= siteA
STOP          ?= S1
DIST_M        ?= 100
REPEAT        ?= 1
OPERATOR      ?= $(shell whoami 2>/dev/null || echo operator)
GPS_TX        ?= ?
GPS_RX        ?= ?
H_TX          ?= 1.5
H_RX          ?= 1.5
GROUND        ?= ?
WEATHER       ?= ?
CSV_DIR       ?= results
CSV           ?= $(CSV_DIR)/$(SITE)_$(STOP)_r$(REPEAT).csv

# Remote SSH support (for starting servers on DQ05 from T470)
DQ05_HOST     ?= dq05
DQ05_SSH      ?= ssh
DQ05_REPO     ?= ~/repos/balloon-e80bench

# Colors for terminal output
GREEN  := \033[32m
YELLOW := \033[33m
RED    := \033[31m
NC     := \033[0m
BOLD   := \033[1m

.DEFAULT_GOAL := help
.PHONY: help detect check-deps tx-server rx-server auto-server \
        range-test range-test-auto start-servers stop-servers \
        dry-run test-single clean

# ============================================================
# HELP
# ============================================================

help: ## Show this help
	@echo "$(BOLD)E80 Range Test — Operator Commands$(NC)"
	@echo ""
	@echo "$(BOLD)SETUP (one-time, on each machine):$(NC)"
	@echo "  $(GREEN)make check-deps$(NC)          Check openocd + pyserial + boards detected"
	@echo "  $(GREEN)make detect$(NC)              Auto-detect local board (role + port)"
	@echo ""
	@echo "$(BOLD)STARTING SERVERS (one per machine):$(NC)"
	@echo "  $(GREEN)make tx-server$(NC)            Start TX board server (auto-detects port)"
	@echo "  $(GREEN)make rx-server$(NC)            Start RX board server (auto-detects port)"
	@echo "  $(GREEN)make auto-server$(NC)          Start server, auto-detect role (TX or RX)"
	@echo "  $(GREEN)make rx-server-remote$(NC)     Start RX server on DQ05 via SSH"
	@echo ""
	@echo "$(BOLD)RUNNING TESTS (from operator's machine):$(NC)"
	@echo "  $(GREEN)make range-test TX_HOST=<ip> RX_HOST=<ip>$(NC)"
	@echo "                        Full campaign, auto-detects roles"
	@echo "  $(GREEN)make range-test-auto HOST_A=<ip> HOST_B=<ip>$(NC)"
	@echo "                        Don't know which board is which? Use this"
	@echo "  $(GREEN)make dry-run$(NC)              Print what would happen (no boards needed)"
	@echo ""
	@echo "$(BOLD)TEST PARAMS (override on command line):$(NC)"
	@echo "  FREQ=$(FREQ)  DBM=$(DBM)  SITE=$(SITE)  STOP=$(STOP)  DIST_M=$(DIST_M)"
	@echo "  GPS_TX=lat,lon  GPS_RX=lat,lon  OPERATOR=$(OPERATOR)"
	@echo "  H_TX=$(H_TX)  H_RX=$(H_RX)  GROUND=$(GROUND)  WEATHER=$(WEATHER)"
	@echo ""
	@echo "$(BOLD)ONE-COMMAND FULL TEST:$(NC)"
	@echo "  make range-test TX_HOST=192.168.1.10 RX_HOST=192.168.1.20 \\"
	@echo "    SITE=fieldA STOP=S3 DIST_M=200 GPS_TX=52.01,4.04 GPS_RX=52.02,4.01"

# ============================================================
# DEPENDENCY CHECK + DETECTION
# ============================================================

check-deps: ## Check openocd, pyserial, and detect boards
	@echo "$(BOLD)[1/3] Checking dependencies...$(NC)"
	@$(E80_DETECT) --check-deps || ( \
		echo "$(YELLOW)$(BOLD)⚠  Dependencies missing. Install:$(NC)" && \
		echo "  pip install pyserial" && \
		echo "  sudo apt install openocd   (or: make install-openocd)" && \
		exit 2 \
	)
	@echo ""
	@echo "$(BOLD)[2/3] Detecting local board...$(NC)"
	@$(E80_DETECT) || true
	@echo ""
	@echo "$(BOLD)[3/3] Done. If detection failed:$(NC)"
	@echo "  - No board found? Check USB cable (both CH340 + Pico probe must be plugged in)"
	@echo "  - Permission denied? Run: sudo usermod -aG dialout $$USER && newgrp dialout"

.PHONY: install-openocd
install-openocd: ## Install openocd (user-local, no sudo if possible)
	@if command -v apt-get >/dev/null 2>&1; then \
		echo "Installing openocd via apt..."; \
		sudo apt-get update -qq && sudo apt-get install -y -qq openocd; \
	else \
		echo "apt not found. Install openocd manually:"; \
		echo "  git clone https://git.code.sf.net/p/openocd/code openocd"; \
		echo "  cd openocd && ./bootstrap && ./configure --prefix=\$$HOME/.local && make -j\$$(nproc) && make install"; \
	fi

detect: ## Auto-detect local board role + port (standalone)
	@$(E80_DETECT) --json

# ============================================================
# BOARD SERVERS — one per machine
# ============================================================

# Auto-role-detect: server figures out if it's TX or RX
auto-server: ## Start board server, auto-detect role (TX or RX)
	@echo "$(BOLD)Starting auto-detecting board server on port $(TCP_PORT)...$(NC)"
	@echo "  (Press Ctrl+C to stop)"
	@exec $(E80_SERVER) --tcp-port $(TCP_PORT)

# Explicit role servers (assert role with --role flag)
tx-server: ## Start TX board server (auto-detects port, asserts TX role)
	@echo "$(BOLD)Starting TX board server on port $(TCP_PORT)...$(NC)"
	@echo "  (Press Ctrl+C to stop)"
	@exec $(E80_SERVER) --tcp-port $(TCP_PORT) --role TX

rx-server: ## Start RX board server (auto-detects port, asserts RX role)
	@echo "$(BOLD)Starting RX board server on port $(TCP_PORT)...$(NC)"
	@echo "  (Press Ctrl+C to stop)"
	@exec $(E80_SERVER) --tcp-port $(TCP_PORT) --role RX

# Start server in background (daemon mode)
auto-server-bg: ## Start board server in background
	@echo "$(BOLD)Starting board server (background) on port $(TCP_PORT)...$(NC)"
	@nohup $(E80_SERVER) --tcp-port $(TCP_PORT) --daemon > /tmp/e80-server.log 2>&1
	@sleep 1
	@cat /tmp/e80-server.log

# Start RX server on DQ05 via SSH
.PHONY: rx-server-remote
rx-server-remote: ## Start RX server on DQ05 via SSH
	@echo "$(BOLD)Starting RX server on $(DQ05_HOST) via SSH...$(NC)"
	@$(DQ05_SSH) $(DQ05_HOST) \
		"cd $(DQ05_REPO)/firmware/e80-stm32-bench/tools && $(PYTHON) e80_board_server.py --tcp-port $(TCP_PORT) --role RX" &

.PHONY: rx-server-remote-bg
rx-server-remote-bg: ## Start RX server on DQ05 via SSH (background)
	@echo "$(BOLD)Starting RX server on $(DQ05_HOST) (background)...$(NC)"
	@$(DQ05_SSH) $(DQ05_HOST) \
		"cd $(DQ05_REPO)/firmware/e80-stm32-bench/tools && nohup $(PYTHON) e80_board_server.py --tcp-port $(TCP_PORT) --role RX --daemon > /tmp/e80-server.log 2>&1"
	@sleep 2
	@$(DQ05_SSH) $(DQ05_HOST) "cat /tmp/e80-server.log"

.PHONY: stop-servers
stop-servers: ## Stop all board servers (local + remote)
	@echo "$(BOLD)Stopping board servers...$(NC)"
	@-pkill -f "e80_board_server.py" 2>/dev/null || true
	@-$(DQ05_SSH) $(DQ05_HOST) "pkill -f e80_board_server.py" 2>/dev/null || true
	@echo "  Done."

# ============================================================
# RANGE TEST — the main event
# ============================================================

range-test: ## Full range test campaign (connects to TX+RX servers)
	@echo "$(BOLD)=== E80 Range Test ===$(NC)"
	@echo "  Site: $(SITE)  Stop: $(STOP)  Distance: $(DIST_M)m  Repeat: $(REPEAT)"
	@echo "  Freq: $$(echo '$(FREQ)' | awk '{printf "%.1f MHz", $$1/1e6}')  Power: +$(DBM) dBm"
	@echo "  TX: $(TX_HOST)  RX: $(RX_HOST)  Operator: $(OPERATOR)"
	@echo "  GPS TX: $(GPS_TX)  GPS RX: $(GPS_RX)"
	@echo ""
	@mkdir -p $(CSV_DIR)
	@$(E80_RANGE) \
		--tx-host $(TX_HOST) --rx-host $(RX_HOST) \
		--tcp-tx $(TCP_PORT) --tcp-rx $(TCP_PORT) \
		--freq $(FREQ) --dbm $(DBM) \
		--csv "$(CSV)" \
		--site "$(SITE)" --stop "$(STOP)" --dist-m "$(DIST_M)" --repeat $(REPEAT) \
		--operator "$(OPERATOR)" \
		--gps-tx "$(GPS_TX)" --gps-rx "$(GPS_RX)" \
		--h-tx "$(H_TX)" --h-rx "$(H_RX)" \
		--ground "$(GROUND)" --weather "$(WEATHER)"

# Auto-role-detect: operator doesn't know which board is which
range-test-auto: ## Range test where client auto-detects which host is TX/RX
	@if [ -z "$(HOST_A)" ] || [ -z "$(HOST_B)" ]; then \
		echo "$(RED)Error: HOST_A and HOST_B required.$(NC)"; \
		echo "Usage: make range-test-auto HOST_A=<ip1> HOST_B=<ip2> [GPS=...]"; \
		exit 1; \
	fi
	@echo "$(BOLD)=== E80 Range Test (auto-role-detect) ===$(NC)"
	@echo "  Host A: $(HOST_A)  Host B: $(HOST_B)"
	@echo "  (Client will auto-detect which is TX and which is RX)"
	@echo ""
	@mkdir -p $(CSV_DIR)
	@$(E80_RANGE) \
		--host-a "$(HOST_A)" --host-b "$(HOST_B)" \
		--tcp-tx $(TCP_PORT) --tcp-rx $(TCP_PORT) \
		--freq $(FREQ) --dbm $(DBM) \
		--csv "$(CSV)" \
		--site "$(SITE)" --stop "$(STOP)" --dist-m "$(DIST_M)" --repeat $(REPEAT) \
		--operator "$(OPERATOR)" \
		--gps-tx "$(GPS_TX)" --gps-rx "$(GPS_RX)" \
		--h-tx "$(H_TX)" --h-rx "$(H_RX)" \
		--ground "$(GROUND)" --weather "$(WEATHER)"

# Dry run (no boards needed, shows what would happen)
dry-run: ## Print the test plan without needing boards
	@echo "$(BOLD)=== E80 Range Test — DRY RUN ===$(NC)"
	@echo "  Site: $(SITE)  Stop: $(STOP)  Distance: $(DIST_M)m  Repeat: $(REPEAT)"
	@echo "  Freq: $$(echo '$(FREQ)' | awk '{printf "%.1f MHz", $$1/1e6}')  Power: +$(DBM) dBm"
	@echo "  CSV: $(CSV)"
	@echo "  GPS TX: $(GPS_TX)  GPS RX: $(GPS_RX)"
	@echo ""
	@echo "Matrix cells (from e80_bench_ctl.py):"
	@$(PYTHON) -c "import sys; sys.path.insert(0,'$(TOOLDIR)'); sys.path.insert(0,'$(TOOLDIR)../../../tools'); from e80_bench_ctl import MATRIX_KEYS, MOD_DEFS; [print(f'  {k}: {MOD_DEFS[k][\"label\"]} gap={MOD_DEFS[k][\"gap_us\"]}us') for k in MATRIX_KEYS]"

# ============================================================
# ONE-COMMAND FULL TEST (start servers + run test)
# ============================================================

.PHONY: all-in-one
all-in-one: ## Start both servers (local + remote) and run test
	@echo "$(BOLD)=== E80 Full Automated Test ===$(NC)"
	@echo "Step 1: Check dependencies..."
	@$(E80_DETECT) --check-deps || (echo "$(RED)Dependencies missing!$(NC)" && exit 2)
	@echo ""
	@echo "Step 2: Starting RX server on $(DQ05_HOST)..."
	@$(DQ05_SSH) $(DQ05_HOST) "cd $(DQ05_REPO)/firmware/e80-stm32-bench/tools && nohup $(PYTHON) e80_board_server.py --tcp-port $(TCP_PORT) --role RX --daemon > /tmp/e80-server.log 2>&1" &
	@sleep 2
	@echo "Step 3: Starting local TX server..."
	@nohup $(E80_SERVER) --tcp-port $(TCP_PORT) --role TX --daemon > /tmp/e80-tx-server.log 2>&1 &
	@sleep 2
	@cat /tmp/e80-tx-server.log
	@echo ""
	@echo "Step 4: Running range test..."
	@$(MAKE) --no-print-directory range-test TX_HOST=localhost RX_HOST=$(DQ05_HOST)
	@echo ""
	@echo "Step 5: Stopping servers..."
	@$(MAKE) --no-print-directory stop-servers

# ============================================================
# SINGLE-BOARD BENCH (both boards on one machine — legacy)
# ============================================================

test-single: ## Single-shot bench test (both boards local, uses e80_bench_ctl.py)
	@echo "$(BOLD)=== E80 Single-shot Test (local) ===$(NC)"
	@$(PYTHON) -c "import sys; sys.path.insert(0,'$(TOOLDIR)'); from e80_detect import detect_dual_board; import json; r=detect_dual_board(); print(json.dumps(r,indent=2,default=str))" > /tmp/e80-detect.json
	@TX=$$(python3 -c "import json; r=json.load(open('/tmp/e80-detect.json')); print(r.get('tx',{}).get('port',''))") && \
	RX=$$(python3 -c "import json; r=json.load(open('/tmp/e80-detect.json')); print(r.get('rx',{}).get('port',''))") && \
	if [ -z "$$TX" ] || [ -z "$$RX" ]; then echo "$(RED)Could not detect both boards$(NC)"; exit 1; fi && \
	echo "TX=$$TX RX=$$RX" && \
	$(PYTHON) $(TOOLDIR)e80_bench_ctl.py --tx $$TX --rx $$RX \
		--freq $(FREQ) --n 1000 --length 255 --dbm $(DBM)

# ============================================================
# CLEANUP
# ============================================================

clean: ## Remove generated results (keeps CSVs)
	@echo "Removing temp files..."
	@rm -f /tmp/e80-*.log /tmp/e80-detect.json
	@echo "  Done. (CSV results in $(CSV_DIR)/ are preserved)"

show-results: ## Show latest results
	@if [ -f "$(CSV)" ]; then \
		echo "$(BOLD)=== Results: $(CSV) ===$(NC)"; \
		cat "$(CSV)"; \
	else \
		echo "No results found at $(CSV)"; \
		echo "Run: make range-test TX_HOST=... RX_HOST=..."; \
	fi
