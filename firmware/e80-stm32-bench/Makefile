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
#
# DIST parameter — auto-select per-stop config:
#   make tx DIST=50m       → configs/per-stop/stop-50m.json
#   make tx DIST=70km      → configs/per-stop/stop-70km.json
#   make tx DIST=100       → configs/per-stop/stop-100m.json (bare = meters)
#   make rx DIST=218m      → configs/per-stop/stop-218m.json
#   make range-dry-run DIST=436m   (preview without hardware)
#
# Valid DIST values: 50m, 100m, 218m, 436m, 872m, 1744m, 5km, 11km, 70km
# Bare numbers are meters: DIST=1744 → stop-1744m.json
# When DIST is not set, CONFIGS defaults to envelope-4cfg-max.json.

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
# Repo root is 2 levels up from e80-stm32-bench/
REPO_ROOT     := $(abspath $(TOOLDIR)/../..)
E80_DIR       := $(TOOLDIR)
CONFIGS_DIR   := $(REPO_ROOT)/configs

# Default config preset + band
CONFIGS       ?= $(CONFIGS_DIR)/envelope-4cfg-max.json

# DIST: distance for per-stop configs (50m, 100m, 218m, 436m, 872m, 1744m, 5km, 11km, 70km)
# Bare numbers are meters: DIST=100 → stop-100m.json
ifdef DIST
  # normalize: bare number → <n>m
  DIST_NORM := $(shell python3 -c "d='$(DIST)'; print(d if not d.isdigit() else d+'m')")
  DIST_FILE := $(CONFIGS_DIR)/per-stop/stop-$(DIST_NORM).json
  CONFIGS := $(DIST_FILE)
endif

BAND          ?= 868
FORMAT        ?= harmonized
TX_LOG        ?= tx-log.csv
RX_LOG        ?= rx-log.csv
OUT_DIR       ?= .
PRIME_DISCARD ?= 2

# --- Board selection (desk setup: both boards on ONE machine) ---
# Auto-detect fails with 2+ CH340 boards (or both targets grab the same port).
#   make rx DIST=50m PORT=/dev/ttyUSB0 PROBE=148757200D2D1425
#   make tx DIST=50m PORT=/dev/ttyUSB1 PROBE=203584200D2D0D42
# Find ports:  python3 tools/e80_detect.py   (lists port + probe per board)
PORT          ?=
PROBE         ?=
ifneq ($(PORT),)
E80_PORT_ARG  := --port $(PORT)
else
E80_PORT_ARG  :=
endif
ifneq ($(PROBE),)
E80_PROBE_ARG := --probe $(PROBE)
else
E80_PROBE_ARG :=
endif

# RX board SWD reset between configs. 20s covers real-world openocd+reopen.
# SWD_RESET_S=0 → --no-swd-reset (STOP-based; only safe from power-cycled board)
SWD_RESET_S   ?= 20
ifneq ($(SWD_RESET_S),0)
RX_SWD_ARG    := --swd-reset-s $(SWD_RESET_S)
else
RX_SWD_ARG    := --no-swd-reset
endif

# --- CVM config provider (dynamic config flow) ---
# CONFIGS names the config preset — a path to a .json file, or a bare preset
# name resolved in configs/. CONFIGS_JSON is the inline JSON of that same
# preset, produced by shelling out to python. It is passed to the CVM
# coordinator via --configs-json so the coordinator can run on a third machine
# (or the same machine) WITHOUT needing the config file present locally.
CONFIGS_JSON ?= $(shell $(PYTHON) -c "import json,os,sys; v='$(CONFIGS)'; p=v if v.endswith('.json') else os.path.join('$(CONFIGS_DIR)', v+'.json'); sys.stdout.write(json.dumps(json.load(open(p))))" 2>/dev/null || echo '')

# ── Deterministic T0 + SESSION_ID ──────────────────────────────────────
# Both machines independently compute the SAME T0 by rounding up to the
# next 5-minute epoch boundary. No communication needed between operators.
#
# Tolerance: both machines must run `make tx` / `make rx` within ~4 min
# of each other (NTP-synced clocks). The later starter still has ≥60s
# before T0 + t0_margin. The lateness guard catches violations.
#
# Override: make rx T0=<epoch> SESSION_ID=<id>  (explicit, for debugging)
BOUNDARY_S    := 300  # 5-minute round-up
T0            ?= $(shell python3 -c "import time; now=int(time.time()); boundary=$(BOUNDARY_S); t0=((now // boundary) + 1) * boundary; print(t0)")
SESSION_ID    ?= $(shell python3 -c "import time; t0=$(T0); print(time.strftime('%y%m%d%H%M', time.gmtime(t0)))")

# Ansible
ANSIBLE_PLAYBOOK := ansible-playbook
ANSIBLE_INVENTORY := $(REPO_ROOT)/ansible/range-inventory.ini

.PHONY: all test-host clean firmware flash
.PHONY: range-setup range-tx range-rx range-merge range-dry-run range-test-host
.PHONY: rx tx flash range-coord range-cvm-server range-adaptive range-cvm-test buf-smoke sweep-e80
.PHONY: boat-tx boat-rx

all: firmware

firmware:
	$(CMAKE) -B $(BUILD) -DCMAKE_TOOLCHAIN_FILE=cmake/arm-none-eabi.cmake \
		-DCMAKE_BUILD_TYPE=Release -DFW_GIT_SHA=$(FW_GIT_SHA) .
	$(CMAKE) --build $(BUILD)

# Firmware binary path (the build produces "e80_bench" without extension)
FW_ELF := $(BUILD)/e80_bench

flash: firmware ## Flash firmware to the connected board via SWD (auto-detect probe)
	@echo "=== Flashing E80 board via SWD ==="
	@command -v openocd >/dev/null 2>&1 || { \
		echo "ERROR: openocd not found. Install with:"; \
		echo "  sudo apt install openocd    # Debian/Ubuntu"; \
		echo "  brew install openocd         # macOS"; \
		exit 1; \
	}
	@# Acquire board lock if the lock script exists (T470 dev machine), else just flash
	@if [ -f "$(HOME)/repos/balloon-fresh/tools/balloon-board-lock.py" ]; then \
		BALLOON_TRACK=e80-bench python3 $(HOME)/repos/balloon-fresh/tools/balloon-board-lock.py acquire both --purpose "make flash" --timeout 60 >/dev/null 2>&1; \
		echo "  Board lock acquired."; \
	fi
	@export BALLOON_TRACK=e80-bench; \
	openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
		-c "adapter speed 1000; transport select swd; set CHIPNAME stm32f1x; reset_config none separate; program $(FW_ELF) verify reset exit" \
		2>&1 | tail -8
	@if [ -f "$(HOME)/repos/balloon-fresh/tools/balloon-board-lock.py" ]; then \
		BALLOON_TRACK=e80-bench python3 $(HOME)/repos/balloon-fresh/tools/balloon-board-lock.py release both >/dev/null 2>&1; \
	fi
	@echo "=== Verifying firmware ==="
	@$(PYTHON) $(TOOLDIR)/tools/e80_detect.py 2>&1 | grep -E "fw=|role:" || true
	@echo "=== Done. Board ready. ==="

test-host:
	$(CMAKE) -B $(TESTBUILD) tests
	$(CMAKE) --build $(TESTBUILD)
	cd $(TESTBUILD) && ctest --output-on-failure

clean:
	rm -rf $(BUILD) $(TESTBUILD)

# ============================================================
# SIMPLIFIED TARGETS: `make tx` and `make rx`
# ============================================================
# These are the recommended entry points for range testing.
# T0 and SESSION_ID are auto-computed deterministically (5-min boundary).
# Both operators just run the same target on their machine — no sharing needed.
#
# The T0 prints on startup so operators can verify they're in the same window.
# If clocks drift >5 min between machines, the lateness guard catches it.
#
# Timing parameters (defaults in tools/e80_bench_ctl.py):
#   t0_margin=30s  guard=5s  rx_lead=3s  settle=1s  swd_reset_s=2s
# These are safe for NTP-synced machines (drift <50ms). Guard times were
# reduced from (120/20/10/2/10)s — inter-stop overhead is now seconds, not
# tens of seconds. For offline machines, override: make range-tx GUARD=10 T0_MARGIN=60
# To pass custom timing, add --guard $(GUARD) etc. to the e80_ctl invocation.
# NOTE: total wall time is still dominated by LoRa-SF12 airtime (~90s for
# 10x 255B pkts), not by guard times — see `make range-dry-run`.

tx: range-tx  ## TX mode: just run `make tx`. T0 + SESSION_ID auto-generated.

rx: range-rx  ## RX mode: just run `make rx`. T0 + SESSION_ID auto-generated.

# ============================================================
# BUF FLASH SMOKE (BUF-T3) — console-only, one board
# ============================================================
# 10x full-capacity (4 KB) binary BUF LOADs with CRC gate,
# then START with src=BUF, then BUF CLEAR -> START with src=PRBS.
# Console-only smoke: no radio probing, no second board needed.
#
#   make buf-smoke PORT=/dev/ttyUSB4
#
# PORT=  required — CH340 console port of the board under test.
# PROBE= optional — accepted for symmetry with make tx/rx but
#        IGNORED here (this smoke never touches the radio probe
#        port; find ports with `python3 tools/e80_detect.py`).
# LOADS=, SIZE= optional — override the 10x4096 defaults.

buf-smoke:
ifndef PORT
	@echo "usage: make buf-smoke PORT=<tty> [LOADS=n] [SIZE=n] [PROBE=<probe>]" >&2
	@echo "  PORT= is required (CH340 console of the board under test, e.g. /dev/ttyUSB4)" >&2
	@echo "  PROBE= is optional and ignored by this console-only smoke" >&2
	@echo "  Find ports: python3 tools/e80_detect.py" >&2
	@exit 1
endif
	@echo "BUF flash smoke: port=$(PORT) loads=$(if $(LOADS),$(LOADS),10) size=$(if $(SIZE),$(SIZE),4096)"
	$(PYTHON) $(TOOLDIR)/tools/buf_smoke_t3.py --port $(PORT) \
		$(if $(LOADS),--loads $(LOADS)) \
		$(if $(SIZE),--size $(SIZE))

# ============================================================
# SWEEP-E80 — desk E80<->E80 sweep via hardened root tool
# ============================================================
# Wraps the ROOT tools/e80_sweep.py (buf/t5b lineage: response
# validation + retries, IWDG-safe ARM/START sequencing, 23/24-field
# PKT parse, binary BUF loader). Full matrix: 14 configs, 50 pkts,
# 64B PRBS-15, 10ms gap — see the script docstring.
#
#   make sweep-e80 PORT=/dev/ttyUSB3
#   make sweep-e80 PORT=/dev/ttyUSB3 RX_PORT=/dev/ttyUSB4
#   make sweep-e80 PORT=/dev/ttyUSB3 CONFIGS="0 3 7"
#   make sweep-e80 PORT=/dev/ttyUSB3 DRY=1
#
# PORT=    required — TX board CH340 console port
# RX_PORT= optional — RX board console port (default: /dev/ttyUSB4)
# CONFIGS= optional — space-separated sweep indexes -> --only
# DRY=1    optional — plan only, no hardware touched
#
# CONFIGS has a file-level default (a range-test JSON preset) that must
# NOT leak into this target. The target-specific empty value disables it;
# a command-line CONFIGS= still wins over both (make rule).

sweep-e80: CONFIGS =
sweep-e80:
ifndef PORT
	@echo "usage: make sweep-e80 PORT=<tx-tty> [RX_PORT=<rx-tty>] [CONFIGS=\"0 1\"] [DRY=1]" >&2
	@echo "  PORT=    required (TX board CH340 console, e.g. /dev/ttyUSB3)" >&2
	@echo "  RX_PORT= optional (RX board console; default /dev/ttyUSB4)" >&2
	@echo "  CONFIGS= optional (space-separated sweep indexes, e.g. \"0 3 7\"; default: all 14)" >&2
	@echo "  DRY=1    optional (plan only, no hardware touched)" >&2
	@echo "  Find ports: python3 tools/e80_detect.py" >&2
	@exit 1
endif
	@echo "sweep-e80: tx=$(PORT) rx=$(if $(RX_PORT),$(RX_PORT),/dev/ttyUSB4 default) configs=[$(if $(CONFIGS),$(CONFIGS),all 14)]$(if $(DRY), [dry-run])"
	@$(PYTHON) $(REPO_ROOT)/tools/e80_sweep.py \
		--tx-port $(PORT) \
		$(if $(RX_PORT),--rx-port $(RX_PORT)) \
		$(if $(CONFIGS),--only "$(CONFIGS)") \
		$(if $(DRY),--dry-run)

# ============================================================
# BOAT / MARITIME SWEEP — continuous loop, all 19 configs
# ============================================================
# For boat trips or moving platforms. Runs all configs from all
# distance presets (50m-70km) in a continuous loop until Ctrl-C.
# Log GPS separately on phone (GPX track) and stitch afterwards.
#
#   make boat-rx          # at base station (Cowork)
#   make boat-tx          # on boat / mobile side
#
# Both auto-compute same T0 (60s boundary for fast start).
# Uses configs/maritime-full-sweep.json (19 configs, ~4 min/cycle).

BOAT_CONFIGS  := $(CONFIGS_DIR)/maritime-full-sweep.json
BOAT_BOUNDARY := 300
BOAT_T0       := $(shell python3 -c "import time; now=int(time.time()); boundary=$(BOAT_BOUNDARY); t0=((now // boundary) + 1) * boundary; print(t0)")
BOAT_SESSION  := $(shell python3 -c "import time; t0=$(BOAT_T0); print(time.strftime('%y%m%d%H%M', time.gmtime(t0)))")
BOAT_TX_LOG   ?= boat-tx.csv
BOAT_RX_LOG   ?= boat-rx.csv
# SWD reset takes ~7-10s real-world (openocd + sleep + board reopen)
# but default swd_reset_s is only 2. Override to 12 for margin.
BOAT_SWD_RESET ?= 20

boat-tx: ## Boat TX mode: continuous loop of all 19 configs (868+2.4 GHz). Ctrl-C to stop.
	@echo "╔══════════════════════════════════════════════╗"
	@echo "║  E80 BOAT TX — continuous maritime sweep    ║"
	@echo "╠══════════════════════════════════════════════╣"
	@echo "║  T0:           $(BOAT_T0) (epoch)"
	@echo "║  SESSION_ID:   $(BOAT_SESSION)"
	@echo "║  Configs:      $(BOAT_CONFIGS)"
	@echo "║  Loop:         infinite (Ctrl-C to stop)"
	@echo "║  Cycle time:   ~5 min (19 configs)"
	@echo "╚══════════════════════════════════════════════╝"
	@python3 -c "import time; remaining=int($(BOAT_T0)-time.time()); print(f'T0 in {remaining}s ({remaining//60}m {remaining%60}s). RX operator should run: make boat-rx')"
	@python3 $(TOOLDIR)/tools/countdown.py $(BOAT_T0) 2>/dev/null || true
	@echo ""
	cd $(TOOLDIR) && $(E80_CTL) --mode tx \
		--t0 $(BOAT_T0) \
		--session-id $(BOAT_SESSION) \
		--configs "$(BOAT_CONFIGS)" \
		--tx-log "$(BOAT_TX_LOG)" \
		--prime-discard $(PRIME_DISCARD) \
		--format $(FORMAT) \
		--loop 0 \
		--skip-fw-check

boat-rx: ## Boat RX mode: continuous loop of all 19 configs (868+2.4 GHz). Ctrl-C to stop.
	@echo "╔══════════════════════════════════════════════╗"
	@echo "║  E80 BOAT RX — continuous maritime sweep    ║"
	@echo "╠══════════════════════════════════════════════╣"
	@echo "║  T0:           $(BOAT_T0) (epoch)"
	@echo "║  SESSION_ID:   $(BOAT_SESSION)"
	@echo "║  Configs:      $(BOAT_CONFIGS)"
	@echo "║  Loop:         infinite (Ctrl-C to stop)"
	@echo "║  SWD reset:    SKIPPED (--no-swd-reset)"
	@echo "║  Cycle time:   ~4 min (19 configs, no SWD reset)"
	@echo "╚══════════════════════════════════════════════╝"
	@python3 -c "import time; remaining=int($(BOAT_T0)-time.time()); print(f'T0 in {remaining}s ({remaining//60}m {remaining%60}s). TX operator should run: make boat-tx')"
	@python3 $(TOOLDIR)/tools/countdown.py $(BOAT_T0) 2>/dev/null || true
	@echo ""
	cd $(TOOLDIR) && $(E80_CTL) --mode rx \
		--t0 $(BOAT_T0) \
		--session-id $(BOAT_SESSION) \
		--configs "$(BOAT_CONFIGS)" \
		--rx-log "$(BOAT_RX_LOG)" \
		--prime-discard $(PRIME_DISCARD) \
		--format $(FORMAT) \
		--loop 0 \
		--no-swd-reset \
		--skip-fw-check

# ============================================================
# DISTRIBUTED RANGE TEST TARGETS
# ============================================================

range-setup: ## Ansible: install openocd, pyserial, clone repo, verify boards (both machines)
	@echo "=== E80 Range Test Setup (Ansible) ==="
	$(ANSIBLE_PLAYBOOK) -i $(ANSIBLE_INVENTORY) $(REPO_ROOT)/ansible/range-setup.yml
	@echo "Setup complete. Run 'make range-dry-run' to verify."

range-tx: ## Distributed TX mode: auto-detect board, send bursts on T0 schedule
	@echo "╔══════════════════════════════════════════════╗"
	@echo "║  E80 TX MODE — waiting for T0               ║"
	@echo "╠══════════════════════════════════════════════╣"
	@echo "║  T0:           $(T0) (epoch)"
	@echo "║  SESSION_ID:   $(SESSION_ID)"
	@echo "║  Configs:      $(CONFIGS)"
ifdef DIST
	@if [ ! -f "$(DIST_FILE)" ]; then \
		echo "║  ERROR: DIST=$(DIST) → $(DIST_FILE) not found."; \
		echo "Valid DIST values: 50m, 100m, 218m, 436m, 872m, 1744m, 5km, 11km, 70km"; \
		exit 1; \
	fi
	@echo "║  DIST:         $(DIST) → stop-$(DIST_NORM).json"
endif
	@echo "║  Band:         $(BAND) MHz"
	@echo "║  Prime discard: $(PRIME_DISCARD)"
	@echo "║  Port:         $(if $(PORT),$(PORT),auto-detect)"
	@echo "║  Probe:        $(if $(PROBE),$(PROBE),auto-detect)"
	@echo "╚══════════════════════════════════════════════╝"
	@python3 -c "import time; remaining=int($(T0)-time.time()); print(f'T0 in {remaining}s ({remaining//60}m {remaining%60}s). RX operator should run: make rx')"
	@python3 $(TOOLDIR)/tools/countdown.py $(T0) 2>/dev/null || true
	@echo ""
	cd $(TOOLDIR) && $(E80_CTL) --mode tx \
		--t0 $(T0) \
		--session-id $(SESSION_ID) \
		--configs "$(CONFIGS)" \
		--tx-log "$(TX_LOG)" \
		--prime-discard $(PRIME_DISCARD) \
		--format $(FORMAT) \
		$(E80_PORT_ARG) $(E80_PROBE_ARG) \
		--skip-fw-check

range-rx: ## Distributed RX mode: auto-detect board, capture packets on T0 schedule
	@echo "╔══════════════════════════════════════════════╗"
	@echo "║  E80 RX MODE — waiting for T0               ║"
	@echo "╠══════════════════════════════════════════════╣"
	@echo "║  T0:           $(T0) (epoch)"
	@echo "║  SESSION_ID:   $(SESSION_ID)"
	@echo "║  Configs:      $(CONFIGS)"
ifdef DIST
	@if [ ! -f "$(DIST_FILE)" ]; then \
		echo "║  ERROR: DIST=$(DIST) → $(DIST_FILE) not found."; \
		echo "Valid DIST values: 50m, 100m, 218m, 436m, 872m, 1744m, 5km, 11km, 70km"; \
		exit 1; \
	fi
	@echo "║  DIST:         $(DIST) → stop-$(DIST_NORM).json"
endif
	@echo "║  Band:         $(BAND) MHz"
	@echo "║  Prime discard: $(PRIME_DISCARD)"
	@echo "║  Port:         $(if $(PORT),$(PORT),auto-detect)"
	@echo "║  Probe:        $(if $(PROBE),$(PROBE),auto-detect)"
	@echo "║  SWD reset:    $(if $(filter 0,$(SWD_RESET_S)),DISABLED,$(SWD_RESET_S)s between configs)"
	@echo "╚══════════════════════════════════════════════╝"
	@python3 -c "import time; remaining=int($(T0)-time.time()); print(f'T0 in {remaining}s ({remaining//60}m {remaining%60}s). TX operator should run: make tx')"
	@python3 $(TOOLDIR)/tools/countdown.py $(T0) 2>/dev/null || true
	@echo ""
	cd $(TOOLDIR) && $(E80_CTL) --mode rx \
		--t0 $(T0) \
		--session-id $(SESSION_ID) \
		--configs "$(CONFIGS)" \
		--rx-log "$(RX_LOG)" \
		--prime-discard $(PRIME_DISCARD) \
		--format $(FORMAT) \
		$(E80_PORT_ARG) $(E80_PROBE_ARG) \
		$(RX_SWD_ARG) \
		--skip-fw-check

range-merge: ## Merge TX+RX logs, compute PER, generate report
	@echo "=== Merging TX+RX Logs ==="
	@echo "  TX: $(TX)"
	@echo "  RX: $(RX)"
	@echo ""
	$(MERGE_SCRIPT) --tx "$(TX)" --rx "$(RX)" --out-dir "$(OUT_DIR)"

range-coord: ## Print T0 + SESSION_ID for sharing between TX and RX operators
	@echo "============================================"
	@echo "  T0:         $(T0)"
	@echo "  SESSION_ID: $(SESSION_ID)"
	@echo "  Configs:    $(CONFIGS)"
	@echo "============================================"
	@echo "Share these values with the other operator:"
	@echo ""
	@echo "  On RX machine:  make range-rx T0=$(T0) SESSION_ID=$(SESSION_ID)"
	@echo "  On TX machine:  make range-tx T0=$(T0) SESSION_ID=$(SESSION_ID)"
	@echo ""
	@echo "Or just run 'make range-tx' on this machine (auto-generated)."
	@echo "Test starts in ~5 minutes. Both machines must sync clocks via NTP."

range-dry-run: ## Print schedule from config preset without touching hardware
	@echo "=== E80 Range Test Dry Run ==="
	@echo "  Configs: $(CONFIGS)"
ifdef DIST
	@if [ ! -f "$(DIST_FILE)" ]; then \
		echo "ERROR: DIST=$(DIST) → $(DIST_FILE) not found."; \
		echo "Valid DIST values: 50m, 100m, 218m, 436m, 872m, 1744m, 5km, 11km, 70km"; \
		echo "Bare numbers are meters: DIST=100 → stop-100m.json"; \
		exit 1; \
	fi
	@echo "  DIST:     $(DIST) → stop-$(DIST_NORM).json"
endif
	@echo ""
	cd $(TOOLDIR) && $(E80_CTL) --mode tx \
		--dry-run \
		--t0 "$(T0)" \
		--configs "$(CONFIGS)"

# ============================================================
# GPS STITCH + ZIP PACKAGING (manual range test on unknown machine)
# ============================================================
#
#   make range-stitch RX=rx-log.csv GPS=track.gpx [TX_GPS=lat,lon] [OUT=combined.csv]
#   make range-zip      RX=rx-log.csv [GPS=track.gpx] [SITE=fieldA] [OPERATOR=alice]
#
# Variables:
#   RX        — RX packet log CSV path (required)
#   GPS       — GPS track file (.gpx or .csv) (optional for zip, required for stitch)
#   TX_GPS    — TX reference point "lat,lon" for distance calc (optional, stitch only)
#   OUT       — output combined CSV path (optional, stitch only; default <rx>_gps.csv)
#   SITE      — short site label, used in zip filename (default: unknown)
#   OPERATOR  — operator name, written into metadata.txt (default: whoami)

GPS_STITCH  := $(PYTHON) $(TOOLDIR)/tools/gps_stitch.py
SITE        ?= unknown
OPERATOR    ?= $(shell whoami 2>/dev/null || echo operator)
RANGE_ZIP_TS := $(shell date -u '+%Y%m%dT%H%M%SZ')

.PHONY: range-stitch range-zip

range-stitch: ## Stitch RX packet log with GPS track by nearest timestamp
	@if [ -z "$(RX)" ]; then \
		echo "ERROR: RX=<file> required."; \
		echo "Usage: make range-stitch RX=rx-log.csv GPS=track.gpx [TX_GPS=52.0,4.0] [OUT=combined.csv]"; \
		exit 1; \
	fi
	@if [ -z "$(GPS)" ]; then \
		echo "ERROR: GPS=<file> required."; \
		echo "Usage: make range-stitch RX=rx-log.csv GPS=track.gpx [TX_GPS=52.0,4.0]"; \
		exit 1; \
	fi
	@if [ ! -f "$(RX)" ]; then echo "ERROR: RX file not found: $(RX)"; exit 1; fi
	@if [ ! -f "$(GPS)" ]; then echo "ERROR: GPS file not found: $(GPS)"; exit 1; fi
	@echo "=== Stitching RX log with GPS ==="
	@echo "  RX:       $(RX)"
	@echo "  GPS:      $(GPS)"
	@echo "  TX ref:   $(if $(TX_GPS),$(TX_GPS),(not provided — no distance column))"
	@echo "  Output:   $(if $(OUT),$(OUT),<rx>_gps.csv (auto))"
	@echo ""
	@$(GPS_STITCH) \
		--rx "$(RX)" \
		--gps "$(GPS)" \
		--t0-epoch $(T0) \
		$$( [ -n "$(TX_GPS)" ] && echo "--tx-gps $(TX_GPS)" ) \
		$$( [ -n "$(OUT)" ] && echo "--out $(OUT)" )

range-zip: ## Zip RX log + optional GPS + metadata.txt for sharing
	@if [ -z "$(RX)" ]; then \
		echo "ERROR: RX=<file> required."; \
		echo "Usage: make range-zip RX=rx-log.csv [GPS=track.gpx] [SITE=fieldA] [OPERATOR=alice]"; \
		exit 1; \
	fi
	@if [ ! -f "$(RX)" ]; then echo "ERROR: RX file not found: $(RX)"; exit 1; fi
	@if [ -n "$(GPS)" ] && [ ! -f "$(GPS)" ]; then \
		echo "ERROR: GPS file not found: $(GPS)"; exit 1; \
	fi
	@echo "=== Building range-test zip ==="
	@ZIP_NAME="$(RANGE_ZIP_TS)_$(SITE).zip"; \
	META="$$(mktemp metadata-XXXX.txt)"; \
	trap 'rm -f "$$META"' EXIT; \
	{ \
		echo "E80 Range Test — Session Metadata"; \
		echo "================================="; \
		echo "zipped_utc: $(RANGE_ZIP_TS)"; \
		echo "operator:   $(OPERATOR)"; \
		echo "site:       $(SITE)"; \
		echo "host:       $$(hostname 2>/dev/null || echo unknown)"; \
		echo "os:         $$(uname -srm 2>/dev/null || echo unknown)"; \
		echo "repo_sha:   $(FW_GIT_SHA)"; \
		echo "repo_branch:$$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"; \
		echo ""; \
		echo "Files"; \
		echo "-----"; \
		echo "rx_log:     $(RX) ($$(wc -l < $(RX) 2>/dev/null || echo ?) lines, $$(du -h $(RX) 2>/dev/null | cut -f1 || echo ?))"; \
		if [ -n "$(GPS)" ]; then \
			echo "gps_track:   $(GPS) ($$(wc -l < $(GPS) 2>/dev/null || echo ?) lines, $$(du -h $(GPS) 2>/dev/null | cut -f1 || echo ?))"; \
		else \
			echo "gps_track:   (none provided)"; \
		fi; \
		echo ""; \
		echo "RX log header (first data line + metadata comments)"; \
		echo "----------------------------------------------------"; \
		head -n 5 "$(RX)" 2>/dev/null | grep -E '^(#|PKT,|STAT,|session,)' || true; \
	} > "$$META"; \
	INCLUDE="$(RX) $$META"; \
	if [ -n "$(GPS)" ]; then INCLUDE="$$INCLUDE $(GPS)"; fi; \
	zip -j "$$ZIP_NAME" $$INCLUDE > /dev/null; \
	rm -f "$$META"; \
	FILESIZE=$$(du -h "$$ZIP_NAME" | cut -f1); \
	echo "Created: $$ZIP_NAME ($$FILESIZE)"; \
	echo "Contents:"; \
	unzip -l "$$ZIP_NAME" 2>/dev/null | grep -E '(\.csv|\.gpx|\.txt)' || true; \
	echo ""; \
	echo "Send $$ZIP_NAME to the TX operator via Signal / Slack / email."

range-test-host: ## Run pytest for distributed range test split logic
	@echo "=== Running distributed range test unit tests ==="
	cd $(TOOLDIR)/tools && $(PYTHON) -m pytest test_e80_range_split.py -v

# ============================================================
# CONTEXTVM (NOSTR MCP) RANGE TEST TARGETS
# ============================================================
#
# Server key (board side):   CVM_SERVER_HEX=<64 hex chars>
#                           or CVM_SERVER_NSEC=nsec1...
# Client key (coordinator): CVM_CLIENT_HEX=<64 hex chars>
# Relay list override:      RELAYS=wss://relay.primal.net,wss://nostr.mom
#
# Typical two-machine deployment:
#   # TX machine (auto-detects serial port + SWD probe):
#   CVM_SERVER_HEX=<hex> make range-cvm-server ROLE=tx
#
#   # RX machine:
#   CVM_SERVER_HEX=<hex> make range-cvm-server ROLE=rx
#
#   # Coordinator (any third machine with Nostr relay reachability):
#   CVM_CLIENT_HEX=<hex> make range-adaptive TX_NPUB=npub1... RX_NPUB=npub1... \
#       CONFIGS=outdoor-10
#
# CVM config provider: the coordinator runs the adaptive sweep by pushing each
# config entry to both boards via the set_config MCP tool. The Makefile passes
# the whole config preset to the coordinator inline as JSON (--configs-json,
# from CONFIGS_JSON) so the coordinator need not have the config file locally.
# The board servers (range-cvm-server) can also load an initial config at
# startup via CONFIGS=name|path, applied through the same set_config tool.

range-cvm-server: ## Start CVM (Nostr MCP) board server — ROLE=tx|rx (auto-detects port). CONFIGS=name|path to load initially.
	@if [ -z "$$CVM_SERVER_HEX" ] && [ -z "$$CVM_SERVER_NSEC" ]; then \
		echo "ERROR: set CVM_SERVER_HEX or CVM_SERVER_NSEC env var"; \
		echo "  e.g. CVM_SERVER_HEX=<hex> make range-cvm-server ROLE=tx"; \
		exit 1; \
	fi
	@echo "=== E80 CVM Board Server (role=$(ROLE)) ==="
	@echo "  Initial config: $(CONFIGS)"
	cd $(TOOLDIR) && $(PYTHON) tools/cvm_board_server.py --role $(ROLE) \
		$$( [ -n "$$CVM_SERVER_HEX" ] && echo "--server-hex $$CVM_SERVER_HEX" ) \
		$$( [ -n "$$CVM_SERVER_NSEC" ] && echo "--nsec $$CVM_SERVER_NSEC" ) \
		$$( [ -n "$$RELAYS" ] && echo "--relays $$RELAYS" ) \
		$$( [ -n "$(CONFIGS)" ] && echo "--configs '$(CONFIGS)'" )

range-adaptive: ## Adaptive sweep via CVM — TX_NPUB=npub1... RX_NPUB=npub1... CONFIGS=outdoor-10 (config JSON passed inline)
	@if [ -z "$(TX_NPUB)" ] || [ -z "$(RX_NPUB)" ]; then \
		echo "ERROR: TX_NPUB and RX_NPUB are required. Example:"; \
		echo "  make range-adaptive TX_NPUB=npub1... RX_NPUB=npub1... CONFIGS=outdoor-10"; \
		exit 1; \
	fi
	@if [ -z "$$CVM_CLIENT_HEX" ]; then \
		echo "ERROR: set CVM_CLIENT_HEX env var (coordinator Nostr secret)"; \
		exit 1; \
	fi
	@echo "=== E80 CVM Adaptive Sweep ==="
	@echo "  TX:      $(TX_NPUB)"
	@echo "  RX:      $(RX_NPUB)"
	@echo "  Configs: $(CONFIGS)"
	@echo ""
	cd $(TOOLDIR) && $(PYTHON) tools/cvm_campaign.py \
		--tx-npub "$(TX_NPUB)" \
		--rx-npub "$(RX_NPUB)" \
		--configs-json '$(CONFIGS_JSON)' \
		--client-hex "$$CVM_CLIENT_HEX" \
		$$( [ -n "$$RELAYS" ] && echo "--relays $$RELAYS" )

range-cvm-test: ## Test CVM relay connectivity + latency — RELAYS=wss://relay.primal.net,wss://nostr.mom
	@echo "=== CVM Relay Connectivity Test ==="
	cd $(TOOLDIR) && $(PYTHON) tools/cvm_relay_test.py \
		$$( [ -n "$(RELAYS)" ] && echo "--relays $(RELAYS)" )
