# firmware/Makefile — RP2040 + ESP32-C3 board management
#
# VERIFIED WORKING 2026-07-15. 1200 baud BOOTSEL trigger is the primary method.
#
# RP2040 targets:
#   make devices                      — List connected serial devices
#   make rp2040-flash ENV=xxx PORT=xx — Build + trigger BOOTSEL + mount + copy UF2 + reboot
#   make rp2040-build ENV=xxx         — Build RP2040 firmware env only
#   make rp2040-monitor PORT=/dev/xx  — Open serial monitor on RP2040
#   make bootsel PORT=/dev/ttyACMX    — Trigger RP2040 BOOTSEL via 1200 baud (reliable)
#
# FLRC test (auto-detect boards by serial number):
#   make flrc-rx-flash                — Flash RX firmware to board 8332
#   make flrc-tx-flash                — Flash TX firmware to board F242D
#   make flrc-flash-both              — Flash both boards sequentially
#   make flrc-test-setup BRIDGE_PORT=xx  — Flash both + UART bridge to ESP32
#
# ESP32 targets:
#   make bridge-flash PORT=/dev/ttyACMX   — Flash UART bridge (RP2040 UART → USB CDC)
#   make bridge-monitor PORT=/dev/ttyACMX — Monitor RP2040 output via ESP32 bridge
#   make esp-bootsel-flash PORT=xx        — Flash BOOTSEL controller to ESP32
#   make esp32-flash PORT=xx              — (legacy) Flash BOOTSEL diagnostic
#
# Usage:
#   make devices
#   make flrc-flash-both
#   make bridge-flash PORT=/dev/ttyACM1
#   make bridge-monitor PORT=/dev/ttyACM1
#
# Board IDs: RP2040 #1=8332 (E663B035973B8332), RP2040 #2=F242D (E663B035977F242D)

PIO            := pio
RP2040_DIR     := rp2040
BOOTSEL_DIR    := esp32-c3-bootsel-controller
ESPTOOL        := python3 -m esptool
SUDO_ASKPASS   := $(HOME)/.hermes/scripts/sudo-askpass.sh

# Defaults
PORT          ?= /dev/ttyACM0
ENV           ?= rp2040-uart-test
FLASH_MOUNT   := /tmp/rp2040-flash

# ── Device discovery ────────────────────────────────────────────────
.PHONY: devices
devices:
	@echo "=== Connected serial devices ==="
	@for dev in /dev/ttyACM* /dev/ttyUSB*; do \
		[ -e "$$dev" ] || continue; \
		serial=$$(udevadm info -q property "$$dev" 2>/dev/null | grep ID_SERIAL_SHORT | cut -d= -f2); \
		pid=$$(udevadm info -q property "$$dev" 2>/dev/null | grep ID_MODEL_ID | cut -d= -f2); \
		model=$$(udevadm info -q property "$$dev" 2>/dev/null | grep ID_MODEL= | cut -d= -f2); \
		echo "  $$dev → $$model (pid=$$pid serial=$$serial)"; \
	done
	@if ls /dev/disk/by-label/RPI-RP2 2>/dev/null; then \
		echo "  RP2040 in BOOTSEL mode ✓"; \
	else \
		echo "  (no RP2040 in BOOTSEL)"; \
	fi

# ── BOOTSEL trigger (1200 baud — reliable, no physical access needed) ──
.PHONY: bootsel
bootsel:
	@echo "Triggering BOOTSEL via 1200 baud on $(PORT)..."
	@timeout 5 python3 -c "import serial; s=serial.Serial('$(PORT)', 1200, timeout=1); s.close()" 2>/dev/null
	@echo "Waiting for RPI-RP2 drive..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if ls /dev/disk/by-label/RPI-RP2 >/dev/null 2>&1; then \
			echo "RP2040 in BOOTSEL ✓ (after $${i}s)"; exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "ERROR: RPI-RP2 never appeared. Is $(PORT) an RP2040 with earlephilhower core?"; exit 1

# ── Full RP2040 flash cycle: build → trigger → mount → copy → reboot ──
.PHONY: rp2040-flash
rp2040-flash: rp2040-build
	@UF2=$(RP2040_DIR)/.pio/build/$(ENV)/firmware.uf2; \
	[ -f "$$UF2" ] || { echo "ERROR: $$UF2 not found"; exit 1; }; \
	if ls /dev/disk/by-label/RPI-RP2 >/dev/null 2>&1; then \
		echo "RP2040 already in BOOTSEL"; \
	else \
		echo "Triggering BOOTSEL via 1200 baud on $(PORT)..."; \
		timeout 5 python3 -c "import serial; s=serial.Serial('$(PORT)', 1200, timeout=1); s.close()" 2>/dev/null; \
		for i in 1 2 3 4 5 6 7 8 9 10; do \
			if ls /dev/disk/by-label/RPI-RP2 >/dev/null 2>&1; then break; fi; \
			sleep 1; \
		done; \
		ls /dev/disk/by-label/RPI-RP2 >/dev/null 2>&1 || { echo "ERROR: BOOTSEL trigger failed"; exit 1; }; \
	fi; \
	echo "Mounting RPI-RP2..."; \
	mkdir -p $(FLASH_MOUNT) 2>/dev/null; \
	SUDO_ASKPASS=$(SUDO_ASKPASS) sudo -A umount $(FLASH_MOUNT) 2>/dev/null; \
	DEV=$$(readlink -f /dev/disk/by-label/RPI-RP2); \
	SUDO_ASKPASS=$(SUDO_ASKPASS) sudo -A mount -o uid=$$(id -u),gid=$$(id -g),flush $$DEV $(FLASH_MOUNT); \
	echo "Copying firmware.uf2..."; \
	cp "$$UF2" $(FLASH_MOUNT)/; sync; \
	echo "Flashed ✓ — RP2040 rebooting..."; \
	sleep 4

# ── Build only ──────────────────────────────────────────────────────
.PHONY: rp2040-build
rp2040-build:
	@echo "Building $(ENV)..."
	cd $(RP2040_DIR) && $(PIO) run -e $(ENV) 2>&1 | tail -5

# ── Serial monitor ──────────────────────────────────────────────────
.PHONY: rp2040-monitor
rp2040-monitor:
	@echo "Monitoring $(PORT) at 115200 baud..."
	@cd $(RP2040_DIR) && $(PIO) device monitor -p $(PORT) -b 115200

# ── ESP32 diagnostic firmware ───────────────────────────────────────
.PHONY: esp32-flash
esp32-flash:
	@echo "Flashing ESP32 BOOTSEL diagnostic to $(PORT)..."
	cd $(BOOTSEL_DIR) && $(PIO) run -e esp32-c3-bootsel-controller 2>&1 | tail -3
	$(ESPTOOL) --port $(PORT) --chip esp32c3 --baud 921600 \
		write_flash 0x0 $(BOOTSEL_DIR)/.pio/build/esp32-c3-bootsel-controller/firmware.bin
	@echo "Done. ESP32 runs diagnostic loop (triggers BOOTSEL periodically)."

# ── ESP32 UART Bridge ────────────────────────────────────────────────
BRIDGE_DIR := esp32-uart-bridge

# Flash UART bridge firmware to ESP32 (forwards RP2040 UART → USB CDC)
# Usage: make bridge-flash PORT=/dev/ttyACM1
.PHONY: bridge-flash bridge-build bridge-monitor
bridge-flash: bridge-build
	@echo "Flashing UART bridge to $(PORT)..."
	cd $(BRIDGE_DIR) && $(PIO) run -e esp32-uart-bridge -t upload --upload-port $(PORT) 2>&1 | tail -5
	@echo "Bridge flashed ✓ — ESP32 now forwards RP2040 UART to USB"

bridge-build:
	@echo "Building UART bridge..."
	cd $(BRIDGE_DIR) && $(PIO) run -e esp32-uart-bridge 2>&1 | tail -3

# Monitor the ESP32 bridge output (RP2040 serial via UART)
bridge-monitor:
	@echo "Monitoring bridge on $(PORT) at 115200... (Ctrl+C to stop)"
	@timeout 30 cat $(PORT) 2>/dev/null || \
		python3 -c "import serial,time; s=serial.Serial('$(PORT)',115200,timeout=1); [print(s.read(1024).decode(errors='replace'),end='',flush=True) for _ in iter(lambda: True, False)]" 2>/dev/null

# ── ESP32 BOOTSEL Controller ─────────────────────────────────────────
# Flash BOOTSEL controller to ESP32 (auto-triggers RP2040 BOOTSEL on boot)
# Usage: make esp-bootsel-flash PORT=/dev/ttyACM1
.PHONY: esp-bootsel-flash esp-bootsel-build
esp-bootsel-flash: esp-bootsel-build
	@echo "Flashing BOOTSEL controller to $(PORT)..."
	cd $(BOOTSEL_DIR) && $(PIO) run -e esp32-c3-bootsel-controller -t upload --upload-port $(PORT) 2>&1 | tail -5
	@echo "BOOTSEL controller flashed ✓"

esp-bootsel-build:
	cd $(BOOTSEL_DIR) && $(PIO) run -e esp32-c3-bootsel-controller 2>&1 | tail -3

# ── RP2040 FLRC convenience targets ─────────────────────────────────
# Auto-detect board by serial number: 8332=RX, F242D=TX
RP2040_8332 ?= $(shell for d in /dev/ttyACM*; do [ -e "$$d" ] || continue; \
	udevadm info -q property "$$d" 2>/dev/null | grep -q E663B035973B8332 && echo "$$d" && break; done)
RP2040_F242D ?= $(shell for d in /dev/ttyACM*; do [ -e "$$d" ] || continue; \
	udevadm info -q property "$$d" 2>/dev/null | grep -q E663B035977F242D && echo "$$d" && break; done)

.PHONY: flrc-rx-flash flrc-tx-flash flrc-flash-both
flrc-rx-flash:
	@if [ -z "$(RP2040_8332)" ]; then echo "ERROR: RP2040 8332 not found on USB"; exit 1; fi
	@echo "Flashing FLRC RX to 8332 ($(RP2040_8332))..."
	$(MAKE) rp2040-flash ENV=rp2040-flrc-rx PORT=$(RP2040_8332)

flrc-tx-flash:
	@if [ -z "$(RP2040_F242D)" ]; then echo "ERROR: RP2040 F242D not found on USB"; exit 1; fi
	@echo "Flashing FLRC TX to F242D ($(RP2040_F242D))..."
	$(MAKE) rp2040-flash ENV=rp2040-flrc-tx-raw PORT=$(RP2040_F242D)

# Flash both boards (RX to 8332, TX to F242D) — sequential
flrc-flash-both: flrc-rx-flash flrc-tx-flash

# ── Convenience targets ─────────────────────────────────────────────
.PHONY: uart-test
uart-test:
	$(MAKE) rp2040-flash ENV=rp2040-uart-test PORT=$(PORT)

# ── Full test setup: flash both + bridge ────────────────────────────
# Usage: make flrc-test-setup BRIDGE_PORT=/dev/ttyACM1
BRIDGE_PORT ?= /dev/ttyACM1
.PHONY: flrc-test-setup
flrc-test-setup: flrc-flash-both bridge-flash
	@echo ""
	@echo "=== FLRC TEST SETUP COMPLETE ==="
	@echo "RX board (8332): FLRC RX firmware ($(RP2040_8332))"
	@echo "TX board (F242D): FLRC TX firmware ($(RP2040_F242D))"
	@echo "Bridge ESP32:     UART bridge ($(BRIDGE_PORT))"
	@echo ""
	@echo "Monitor RX via bridge: make bridge-monitor PORT=$(BRIDGE_PORT)"

# ── Clean ───────────────────────────────────────────────────────────
.PHONY: clean
clean:
	cd $(RP2040_DIR) && $(PIO) run -t clean 2>/dev/null || true
	cd $(BOOTSEL_DIR) && $(PIO) run -t clean 2>/dev/null || true
	cd $(BRIDGE_DIR) && $(PIO) run -t clean 2>/dev/null || true
