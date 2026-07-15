# firmware/Makefile — RP2040 + ESP32-C3 board management
#
# VERIFIED WORKING 2026-07-15. 1200 baud BOOTSEL trigger is the primary method.
#
# Targets:
#   bootsel PORT=/dev/ttyACMX    — Trigger RP2040 BOOTSEL via 1200 baud (reliable)
#   rp2040-flash ENV=xxx PORT=xx — Build + trigger BOOTSEL + mount + copy UF2 + reboot
#   rp2040-build ENV=xxx         — Build RP2040 firmware env only
#   rp2040-monitor PORT=/dev/xx  — Open serial monitor on RP2040
#   esp32-flash PORT=/dev/ttyXX  — Flash BOOTSEL diagnostic to ESP32
#   devices                      — List connected serial devices
#   clean                        — Clean build artifacts
#
# Usage:
#   make bootsel PORT=/dev/ttyACM0        # trigger BOOTSEL on RP2040 #1
#   make bootsel PORT=/dev/ttyACM2        # trigger BOOTSEL on RP2040 #2
#   make rp2040-flash ENV=rp2040-uart-test PORT=/dev/ttyACM0
#   make devices
#
# IMPORTANT: PORT must point to the RP2040's ACM port (not the ESP32).
# The 1200 baud method requires earlephilhower core firmware on the RP2040.
# It does NOT work with mbed core (USB CDC dead on mbed).
# Board IDs: RP2040 #1=ACM0 (E663B035973B8332), RP2040 #2=ACM2 (E663B035977F242D)

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

# ── Convenience targets ─────────────────────────────────────────────
.PHONY: uart-test flrc-rx-flash
uart-test:
	$(MAKE) rp2040-flash ENV=rp2040-uart-test PORT=$(PORT)

flrc-rx-flash:
	$(MAKE) rp2040-flash ENV=rp2040-flrc-rx PORT=$(PORT)

# ── Clean ───────────────────────────────────────────────────────────
.PHONY: clean
clean:
	cd $(RP2040_DIR) && $(PIO) run -t clean 2>/dev/null || true
	cd $(BOOTSEL_DIR) && $(PIO) run -t clean 2>/dev/null || true
