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

# ─── Flash targets (via pio upload, auto-detects port) ──
.PHONY: flash-tx flash-rx flash-both

flash-tx: build-tx
	@echo "Flashing TX (serial $(TX_SERIAL))..."
	@PORT=$$(python3 $(TOOLS)/port_util.py find --serial $(TX_SERIAL) 2>/dev/null | grep -o '/dev/.*'); \
	if [ -z "$$PORT" ]; then echo "ERROR: TX board not found"; exit 1; fi; \
	echo "Found TX at $$PORT"; \
	pio run -e rp2040-sweep-tx-v4 -t upload --upload-port $$PORT

flash-rx: build-rx
	@echo "Flashing RX (serial $(RX_SERIAL))..."
	@PORT=$$(python3 $(TOOLS)/port_util.py find --serial $(RX_SERIAL) 2>/dev/null | grep -o '/dev/.*'); \
	if [ -z "$$PORT" ]; then echo "ERROR: RX board not found"; exit 1; fi; \
	echo "Found RX at $$PORT"; \
	pio run -e rp2040-sweep-rx-v4 -t upload --upload-port $$PORT

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

# ─── Port detection ───────────────────────────────────
.PHONY: ports find-tx find-rx

ports:
	@python3 $(TOOLS)/port_util.py list

find-tx:
	@echo "TX board (serial $(TX_SERIAL)):"
	@python3 $(TOOLS)/port_util.py find --serial $(TX_SERIAL)

find-rx:
	@echo "RX board (serial $(RX_SERIAL)):"
	@python3 $(TOOLS)/port_util.py find --serial $(RX_SERIAL)

# ─── Monitor TX serial output ─────────────────────────
.PHONY: monitor-tx monitor-rx

monitor-tx:
	@echo "Monitoring TX (serial $(TX_SERIAL)) — Ctrl+C to stop"
	@python3 -c "import serial,time,sys; \
	port=$$(python3 $(TOOLS)/port_util.py find --serial $(TX_SERIAL) 2>/dev/null | grep -o '/dev/.*'); \
	[port] or (print('TX not found'), sys.exit(1)); \
	s=serial.Serial(port,115200,timeout=1); \
	[print(l.decode(errors='replace').strip()) for l in iter(s.readline,b'')]"

monitor-rx:
	@echo "Monitoring RX (serial $(RX_SERIAL)) — Ctrl+C to stop"
	@python3 -c "import serial,time,sys; \
	port=$$(python3 $(TOOLS)/port_util.py find --serial $(RX_SERIAL) 2>/dev/null | grep -o '/dev/.*'); \
	[port] or (print('RX not found'), sys.exit(1)); \
	s=serial.Serial(port,115200,timeout=1); \
	[print(l.decode(errors='replace').strip()) for l in iter(s.readline,b'')]"

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
