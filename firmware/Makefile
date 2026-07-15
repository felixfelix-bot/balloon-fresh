# firmware/Makefile — RP2040 + ESP32-C3 board management
#
# Targets:
#   bootsel-flash         — Flash BOOTSEL controller to ESP32 (ACM1 or ACM2)
#   bootsel               — Trigger RP2040 BOOTSEL via ESP32
#   rp2040-reset          — Reset RP2040 via ESP32 (normal boot)
#   rp2040-flash ENV=xxx  — Build + flash RP2040 firmware env via UF2
#   rp2040-build ENV=xxx  — Build RP2040 firmware env only
#   rp2040-monitor        — Open serial monitor on RP2040
#   esp32-flash PORT=xxx  — Flash ESP32 firmware (bootsel controller by default)
#   esp32-monitor PORT=xx — Open serial monitor on ESP32
#   uart-test             — Build + flash UART echo test to RP2040
#   devices               — List connected serial devices
#
# Usage:
#   make bootsel-flash PORT=/dev/ttyACM1
#   make bootsel                          # triggers RP2040 into BOOTSEL
#   make rp2040-flash ENV=rp2040-uart-test
#   make devices

PIO            := pio
RP2040_DIR     := rp2040
BOOTSEL_DIR    := esp32-c3-bootsel-controller
ESPTOOL        := python3 -m esptool

# Defaults — override on command line
PORT          ?= /dev/ttyACM1
ENV           ?= rp2040-uart-test
MONITOR_PORT  ?= /dev/ttyACM0
MONITOR_BAUD  ?= 115200

# ── Device discovery ────────────────────────────────────────────────
.PHONY: devices
devices:
	@echo "=== Connected serial devices ==="
	@for dev in /dev/ttyACM* /dev/ttyUSB*; do \
		[ -e "$$dev" ] || continue; \
		serial=$$(udevadm info -q property "$$dev" 2>/dev/null | grep ID_SERIAL_SHORT | cut -d= -f2); \
		model=$$(udevadm info -q property "$$dev" 2>/dev/null | grep ID_MODEL= | cut -d= -f2); \
		echo "  $$dev → $$model (serial=$$serial)"; \
	done
	@ls /dev/disk/by-label/RPI-RP2 2>/dev/null && echo "  RP2040 in BOOTSEL mode" || true

# ── ESP32 BOOTSEL controller ────────────────────────────────────────
.PHONY: bootsel-flash bootsel rp2040-reset esp32-monitor

bootsel-flash:
	@echo "Flashing BOOTSEL controller to $(PORT)..."
	cd $(BOOTSEL_DIR) && $(PIO) run -e esp32-c3-bootsel-controller 2>&1 | tail -3
	$(ESPTOOL) --port $(PORT) --chip esp32c3 --baud 921600 \
		write_flash 0x0 $(BOOTSEL_DIR)/.pio/build/esp32-c3-bootsel-controller/firmware.bin
	@echo "Done. Wait 3s for boot..."
	@sleep 3

bootsel:
	@echo "Triggering RP2040 BOOTSEL via $(PORT)..."
	@printf 'b' > $(PORT)
	@sleep 2
	@ls /dev/disk/by-label/RPI-RP2 2>/dev/null && echo "RP2040 in BOOTSEL ✓" || echo "ERROR: RP2040 not in BOOTSEL"

# 1200 baud BOOTSEL fallback — works when RP2040 USB CDC is alive
# Use for boards without working ESP32 BOOTSEL circuit
.PHONY: bootsel-1200
bootsel-1200:
	@echo "Triggering BOOTSEL via 1200 baud on $(PORT)..."
	@timeout 5 python3 -c "import serial; s=serial.Serial('$(PORT)', 1200, timeout=1); s.close()" 2>/dev/null
	@echo "Waiting for RPI-RP2 to appear..."
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if ls /dev/disk/by-label/RPI-RP2 >/dev/null 2>&1; then \
			echo "RP2040 in BOOTSEL ✓ (after $${i}s)"; exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "ERROR: 1200 baud failed — RPI-RP2 never appeared"; exit 1

rp2040-reset:
	@echo "Resetting RP2040 via $(PORT)..."
	@printf 'r' > $(PORT)
	@sleep 2

esp32-monitor:
	@echo "Monitoring $(PORT) at $(MONITOR_BAUD) baud..."
	@timeout 30 python3 -c "import serial,time; s=serial.Serial('$(PORT)',$(MONITOR_BAUD),timeout=1); [print(s.read(1024).decode('utf-8','replace'),end='') or time.sleep(0.1) for _ in iter(int,1)]" || true

# ── RP2040 firmware ─────────────────────────────────────────────────
.PHONY: rp2040-build rp2040-flash rp2040-monitor uart-test

rp2040-build:
	@echo "Building $(ENV)..."
	cd $(RP2040_DIR) && $(PIO) run -e $(ENV) 2>&1 | tail -5

rp2040-flash: rp2040-build
	@UF2=$(RP2040_DIR)/.pio/build/$(ENV)/firmware.uf2; \
	[ -f "$$UF2" ] || { echo "ERROR: $$UF2 not found. Build failed?"; exit 1; }; \
	if ls /dev/disk/by-label/RPI-RP2 2>/dev/null; then \
		echo "RP2040 already in BOOTSEL — flashing..."; \
	else \
		echo "Trying 1200 baud BOOTSEL on $(PORT)..."; \
		timeout 5 python3 -c "import serial; s=serial.Serial('$(PORT)', 1200, timeout=1); s.close()" 2>/dev/null; \
		for i in 1 2 3 4 5 6 7 8 9 10; do \
			if ls /dev/disk/by-label/RPI-RP2 >/dev/null 2>&1; then break; fi; \
			sleep 1; \
		done; \
		if ! ls /dev/disk/by-label/RPI-RP2 2>/dev/null; then \
			echo "1200 baud failed, trying ESP32 GPIO..."; \
			printf 'b' > $(PORT); sleep 3; \
		fi; \
		ls /dev/disk/by-label/RPI-RP2 2>/dev/null || { echo "ERROR: BOOTSEL trigger failed. Hold BOOTSEL + replug USB."; exit 1; }; \
	fi; \
	MOUNT=$$(lsblk -o MOUNTPOINT -n /dev/disk/by-label/RPI-RP2 2>/dev/null); \
	if [ -z "$$MOUNT" ]; then \
		DEV=$$(readlink -f /dev/disk/by-label/RPI-RP2); \
		MOUNT=$$(udisksctl mount -b $$DEV 2>/dev/null | sed 's/.*at //;s/\.//'); \
	fi; \
	if [ -z "$$MOUNT" ]; then \
		MOUNT=/tmp/rp2040-flash; \
		mkdir -p $$MOUNT 2>/dev/null; \
		SUDO_ASKPASS=$$HOME/.hermes/scripts/sudo-askpass.sh sudo -A mount -o uid=$$(id -u),gid=$$(id -g) $$(readlink -f /dev/disk/by-label/RPI-RP2) $$MOUNT 2>/dev/null; \
	fi; \
	if [ -z "$$MOUNT" ] || ! mountpoint -q $$MOUNT 2>/dev/null; then echo "ERROR: could not mount RPI-RP2"; exit 1; fi; \
	echo "Mount: $$MOUNT"; \
	cp "$$UF2" "$$MOUNT/"; sync; \
	echo "Flashed ✓. RP2040 rebooting..."; \
	sleep 3

rp2040-monitor:
	@echo "Monitoring $(MONITOR_PORT) at $(MONITOR_BAUD) baud..."
	@cd $(RP2040_DIR) && $(PIO) device monitor -p $(MONITOR_PORT) -b $(MONITOR_BAUD)

# ── Convenience: UART bridge test ───────────────────────────────────
.PHONY: uart-test
uart-test:
	$(MAKE) rp2040-flash ENV=rp2040-uart-test PORT=$(PORT)
	@echo "UART echo test flashed. Send text to RP2040 via serial monitor."

# ── Convenience: FLRC RX firmware ───────────────────────────────────
.PHONY: flrc-rx-flash
flrc-rx-flash:
	$(MAKE) rp2040-flash ENV=rp2040-flrc-rx PORT=$(PORT)

# ── Clean ───────────────────────────────────────────────────────────
.PHONY: clean
clean:
	cd $(RP2040_DIR) && $(PIO) run -t clean
	cd $(BOOTSEL_DIR) && $(PIO) run -t clean 2>/dev/null || true
