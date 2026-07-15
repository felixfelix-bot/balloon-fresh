# Balloon Fresh — Hardware Control Makefile
# Targets for ESP32-C3 BOOTSEL controller and RP2040 firmware management

BOOTSEL_DIR := firmware/esp32-bootsel-controller
RP2040_DIR := firmware/rp2040
PORT ?= /dev/ttyACM1

.PHONY: bootsel-build bootsel-flash bootsel-diag-flash bootsel-trigger bootsel-flash-rp2040 bootsel-clean

# Build auto-BOOTSEL firmware
bootsel-build:
	cd $(BOOTSEL_DIR) && pio run -e esp32c3

# Flash auto-BOOTSEL firmware to ESP32 (PORT=/dev/ttyACMx)
# After this, ESP32 will auto-trigger RP2040 BOOTSEL on every boot
bootsel-flash: bootsel-build
	python3 -m esptool --port $(PORT) --chip esp32c3 --baud 460800 \
		--before default_reset --after hard_reset \
		write_flash 0x0 $(BOOTSEL_DIR)/.pio/build/esp32c3/firmware.bin

# Flash diagnostic firmware (toggle GPIO pins for multimeter testing)
bootsel-diag-flash:
	cd $(BOOTSEL_DIR) && pio run -e esp32c3-diag
	python3 -m esptool --port $(PORT) --chip esp32c3 --baud 460800 \
		--before default_reset --after hard_reset \
		write_flash 0x0 $(BOOTSEL_DIR)/.pio/build/esp32c3-diag/firmware.bin

# Trigger BOOTSEL: flash bootsel firmware, wait for RPI-RP2, report status
bootsel-trigger: bootsel-flash
	@echo "Waiting for RP2040 BOOTSEL..."
	@sleep 5
	@if ls /dev/disk/by-label/RPI-RP2 >/dev/null 2>&1; then \
		echo "BOOTSEL OK — RPI-RP2 available"; \
	else \
		echo "BOOTSEL FAILED — check wiring"; \
		exit 1; \
	fi

# Full pipeline: trigger BOOTSEL → flash RP2040 UF2 → verify
# Usage: make bootsel-flash-rp2040 UF2=path/to/firmware.uf2
bootsel-flash-rp2040: bootsel-trigger
	@if [ -z "$(UF2)" ]; then echo "Usage: make bootsel-flash-rp2040 UF2=path.uf2"; exit 1; fi
	@MOUNT=$$(lsblk -o MOUNTPOINT -n /dev/disk/by-label/RPI-RP2 2>/dev/null); \
	if [ -z "$$MOUNT" ]; then \
		udisksctl mount -b /dev/disk/by-label/RPI-RP2 2>/dev/null; \
		MOUNT=$$(lsblk -o MOUNTPOINT -n /dev/disk/by-label/RPI-RP2 2>/dev/null); \
	fi; \
	cp "$(UF2)" "$$MOUNT/"; \
	sync; \
	echo "UF2 copied, RP2040 rebooting..."; \
	sleep 3

bootsel-clean:
	cd $(BOOTSEL_DIR) && pio run -t clean
