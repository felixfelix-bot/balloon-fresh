# Balloon Range Tests — Build/Flash/Test Infrastructure
# Per ADR-020: Reproducible build, flash, and test via Make targets
# Usage: make <target>

TX_SERIAL = 242D
RX_SERIAL = 8332
BUILD_DIR = .pio/build
TX_UF2 = $(BUILD_DIR)/rp2040-sweep-tx-v4/firmware.uf2
RX_UF2 = $(BUILD_DIR)/rp2040-sweep-rx-v4/firmware.uf2
TOOLS = tools

# ─── Build targets ───────────────────────────────────
.PHONY: build-tx build-rx build-both

build-tx:
	pio run -e rp2040-sweep-tx-v4

build-rx:
	pio run -e rp2040-sweep-rx-v4

build-both: build-tx build-rx

# ─── Flash targets (via BOOTSEL) ─────────────────────
.PHONY: flash-tx flash-rx flash-both

flash-tx: build-tx
	@echo "Flashing TX (serial $(TX_SERIAL))..."
	@$(TOOLS)/flash_board.sh $(TX_SERIAL) $(TX_UF2)

flash-rx: build-rx
	@echo "Flashing RX (serial $(RX_SERIAL))..."
	@$(TOOLS)/flash_board.sh $(RX_SERIAL) $(RX_UF2)

flash-both: flash-tx flash-rx
	@echo "Both boards flashed."

# ─── Test targets ────────────────────────────────────
.PHONY: test test-unit test-hw test-walk

test: test-unit

test-unit:
	pytest tests/ -m "not hw" -v

test-hw:
	pytest tests/ -m "hw" -v --timeout=300

test-walk:
	pytest tests/ -m "walk" -v --timeout=600

# ─── Capture targets ─────────────────────────────────
.PHONY: capture capture-stop

capture:
	@echo "Starting RX capture daemon..."
	@python3 $(TOOLS)/rx_capture.py --serial $(RX_SERIAL) --resync &

capture-stop:
	@pkill -f rx_capture.py || true
	@echo "Capture daemon stopped."

# ─── All-in-one ──────────────────────────────────────
.PHONY: walk-ready clean

walk-ready: build-both flash-both
	@echo "Boards flashed. Verify GPS lock before walking."

clean:
	pio run -t clean
