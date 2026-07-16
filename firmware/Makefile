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
#   make esp-recover PORT=/dev/ttyACMX    — Full erase + reflash (fixes corrupted bootloader)
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

# Alias for discoverability
.PHONY: bootsel-1200
bootsel-1200: bootsel

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
BRIDGE_BUILD := $(BRIDGE_DIR)/.pio/build/esp32-uart-bridge

# Flash UART bridge firmware to ESP32 (forwards RP2040 UART → USB CDC)
# Uses esptool with bootloader + partitions + firmware (not just firmware.bin)
# Usage: make bridge-flash PORT=/dev/ttyACM1
.PHONY: bridge-flash bridge-build bridge-read bridge-send bridge-monitor
bridge-flash: bridge-build
	@echo "Flashing UART bridge to $(PORT)..."
	@FW=$$(pwd)/$(BRIDGE_BUILD)/firmware.bin; \
	BL=$$(pwd)/$(BRIDGE_BUILD)/bootloader.bin; \
	PT=$$(pwd)/$(BRIDGE_BUILD)/partitions.bin; \
	[ -f "$$FW" ] || { echo "ERROR: $$FW not found. Run make bridge-build"; exit 1; }; \
	echo "Erasing flash..."; \
	$(ESPTOOL) --port $(PORT) --chip esp32c3 erase_flash 2>&1 | tail -1; \
	echo "Flashing bootloader+partitions+firmware..."; \
	$(ESPTOOL) --port $(PORT) --chip esp32c3 --baud 921600 \
		write_flash 0x0 "$$BL" 0x8000 "$$PT" 0x10000 "$$FW" 2>&1 | tail -2; \
	echo "Bridge flashed ✓ — ESP32 now forwards RP2040 UART to USB"
	@sleep 2

bridge-build:
	@echo "Building UART bridge..."
	cd $(BRIDGE_DIR) && $(PIO) run -e esp32-uart-bridge 2>&1 | tail -3

# Read bridge output for N seconds (default 10)
# Usage: make bridge-read PORT=/dev/ttyACM1 SECS=15
bridge-read:
	@python3 scripts/bridge-serial.py read PORT=$(PORT) SECS=$(or $(SECS),10)

# Send command through bridge to RP2040
# Usage: make bridge-send PORT=/dev/ttyACM1 CMD=RUN
bridge-send:
	@python3 scripts/bridge-serial.py send PORT=$(PORT) CMD=$(CMD)

# Monitor bridge continuously (Ctrl+C to stop)
bridge-monitor:
	@python3 scripts/bridge-serial.py monitor PORT=$(PORT)

# Send RUN + listen for results (default 20s)
# Usage: make bridge-test PORT=/dev/ttyACM1 SECS=20
bridge-test:
	@python3 scripts/bridge-serial.py test PORT=$(PORT) SECS=$(or $(SECS),20)

# ── ESP32 recovery (corrupted flash — boot loop, SHA mismatch) ──────
# Usage: make esp-recover PORT=/dev/ttyACM1
# Full erase + rebuild + reflash. Fixes bootloader corruption from
# wrong-offset write_flash 0x0.
.PHONY: esp-recover
esp-recover:
	@if [ -z "$(PORT)" ]; then echo "Usage: make esp-recover PORT=/dev/ttyACMX"; exit 1; fi
	@echo "=== ESP32 RECOVERY on $(PORT) ==="
	@echo "1/3 Erasing flash..."
	@python3 -m esptool --port $(PORT) --chip esp32c3 erase_flash 2>&1 | tail -2
	@echo "2/3 Rebuilding bridge firmware..."
	@cd $(BRIDGE_DIR) && $(PIO) run -e esp32-uart-bridge 2>&1 | tail -3
	@echo "3/3 Flashing clean..."
	@cd $(BRIDGE_DIR) && $(PIO) run -e esp32-uart-bridge -t upload --upload-port $(PORT) 2>&1 | tail -3
	@echo "=== RECOVERY COMPLETE — ESP32 should boot clean ==="

# ── ESP32 BOOTSEL Controller ─────────────────────────────────────────
# Flash BOOTSEL controller to ESP32 (auto-triggers RP2040 BOOTSEL on boot)
# Usage: make esp-bootsel-flash PORT=/dev/ttyACM1
BOOTSEL_BUILD_DIR := $(BOOTSEL_DIR)/.pio/build/esp32c3

# ── ESP32 full recovery (fixes corrupted flash / WDT reset loop) ─────
# Does: erase → flash bootloader(0x0) + partitions(0x8000) + firmware(0x10000)
# Use when ESP32 is stuck in WDT reset loop after bad flash.
# Usage: make esp32-recover PORT=/dev/ttyACM1 FW_DIR=esp32-uart-bridge FW_ENV=esp32-uart-bridge
#        make esp32-recover PORT=/dev/ttyACM1 FW_DIR=esp32-c3-bootsel-controller FW_ENV=esp32c3
.PHONY: esp32-recover
esp32-recover:
	@if [ -z "$(FW_DIR)" ] || [ -z "$(FW_ENV)" ]; then \
		echo "ERROR: FW_DIR and FW_ENV required"; \
		echo "Usage: make esp32-recover PORT=/dev/ttyACM1 FW_DIR=esp32-uart-bridge FW_ENV=esp32-uart-bridge"; \
		echo "       make esp32-recover PORT=/dev/ttyACM1 FW_DIR=esp32-c3-bootsel-controller FW_ENV=esp32c3"; \
		exit 1; \
	fi
	@BUILD=$(FW_DIR)/.pio/build/$(FW_ENV); \
	FW=$$(pwd)/$$BUILD/firmware.bin; \
	BL=$$(pwd)/$$BUILD/bootloader.bin; \
	PT=$$(pwd)/$$BUILD/partitions.bin; \
	if [ ! -f "$$FW" ]; then echo "Building $(FW_ENV)..."; cd $(FW_DIR) && $(PIO) run -e $(FW_ENV) 2>&1 | tail -3; cd ..; fi; \
	[ -f "$$FW" ] || { echo "ERROR: $$FW not found"; exit 1; }; \
	[ -f "$$BL" ] || { echo "ERROR: $$BL not found"; exit 1; }; \
	[ -f "$$PT" ] || { echo "ERROR: $$PT not found"; exit 1; }; \
	echo "=== RECOVER $(PORT) ==="; \
	echo "Erasing flash..."; \
	$(ESPTOOL) --port $(PORT) --chip esp32c3 erase_flash 2>&1 | tail -1; \
	echo "Flashing bootloader(0x0) + partitions(0x8000) + firmware(0x10000)..."; \
	$(ESPTOOL) --port $(PORT) --chip esp32c3 --baud 921600 \
		write_flash 0x0 "$$BL" 0x8000 "$$PT" 0x10000 "$$FW" 2>&1 | tail -2; \
	echo "Recovery done ✓"; \
	sleep 3; \
	echo "Verifying..."; \
	timeout 5 python3 -c "import serial,time; s=serial.Serial('$(PORT)',115200,timeout=1); time.sleep(2); d=s.read(4096); print('Output: %s' % d.decode(errors='replace').strip()[:200])" 2>&1 || echo "(no output yet — may need reset)"
.PHONY: esp-bootsel-flash esp-bootsel-build
esp-bootsel-flash: esp-bootsel-build
	@echo "Flashing BOOTSEL controller to $(PORT)..."
	@FW=$$(pwd)/$(BOOTSEL_DIR)/.pio/build/esp32c3/firmware.bin; \
	[ -f "$$FW" ] || { echo "ERROR: $$FW not found"; exit 1; }; \
	$(ESPTOOL) --port $(PORT) --chip esp32c3 --baud 921600 \
		write_flash 0x0 "$$FW" 2>&1 | tail -2
	@echo "BOOTSEL controller flashed ✓"

esp-bootsel-build:
	cd $(BOOTSEL_DIR) && $(PIO) run -e esp32c3 2>&1 | tail -3

# Flash BOOTSEL oneshot controller (single trigger, then idle)
# Usage: make esp-bootsel-oneshot-flash PORT=/dev/ttyACM1
.PHONY: esp-bootsel-oneshot-flash esp-bootsel-oneshot-build
esp-bootsel-oneshot-flash: esp-bootsel-oneshot-build
	@echo "Flashing BOOTSEL oneshot to $(PORT)..."
	@FW=$$(pwd)/$(BOOTSEL_DIR)/.pio/build/esp32-bootsel-oneshot/firmware.bin; \
	[ -f "$$FW" ] || { echo "ERROR: $$FW not found"; exit 1; }; \
	$(ESPTOOL) --port $(PORT) --chip esp32c3 --baud 921600 \
		write_flash 0x0 "$$FW" 2>&1 | tail -2
	@echo "BOOTSEL oneshot flashed ✓"

esp-bootsel-oneshot-build:
	cd $(BOOTSEL_DIR) && $(PIO) run -e esp32-bootsel-oneshot 2>&1 | tail -3

# Convenience: recover + flash specific firmware
# make recover-bridge PORT=/dev/ttyACM1   — recover + flash UART bridge
# make recover-bootsel PORT=/dev/ttyACM1   — recover + flash BOOTSEL controller
.PHONY: recover-bridge recover-bootsel
recover-bridge:
	$(MAKE) esp32-recover PORT=$(PORT) FW_DIR=esp32-uart-bridge FW_ENV=esp32-uart-bridge

recover-bootsel:
	$(MAKE) esp32-recover PORT=$(PORT) FW_DIR=esp32-c3-bootsel-controller FW_ENV=esp32c3

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
.PHONY: flrc-test-setup flrc-run
flrc-test-setup: flrc-flash-both bridge-flash
	@echo ""
	@echo "=== FLRC TEST SETUP COMPLETE ==="
	@echo "RX board (8332): FLRC RX firmware ($(RP2040_8332))"
	@echo "TX board (F242D): FLRC TX firmware ($(RP2040_F242D))"
	@echo "Bridge ESP32:     UART bridge ($(BRIDGE_PORT))"
	@echo ""
	@echo "Monitor RX via bridge: make bridge-monitor PORT=$(BRIDGE_PORT)"
	@echo "Send RUN to RX:       make bridge-send PORT=$(BRIDGE_PORT) CMD=RUN"

# Full automated test: flash both + bridge, send RUN, listen for results
# Usage: make flrc-run BRIDGE_PORT=/dev/ttyACM1
flrc-run: flrc-test-setup
	@echo "Waiting for boards to boot..."
	@sleep 5
	@echo "Sending RUN + listening for results (20s)..."
	@python3 scripts/bridge-serial.py test PORT=$(BRIDGE_PORT) SECS=20

# ── Clean ───────────────────────────────────────────────────────────
.PHONY: clean
clean:
	cd $(RP2040_DIR) && $(PIO) run -t clean 2>/dev/null || true
	cd $(BOOTSEL_DIR) && $(PIO) run -t clean 2>/dev/null || true
	cd $(BRIDGE_DIR) && $(PIO) run -t clean 2>/dev/null || true
