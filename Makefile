# Balloon Fresh — Hardware Control Makefile
# Targets for ESP32-C3 BOOTSEL controller and RP2040 firmware management

BOOTSEL_DIR := firmware/esp32-bootsel-controller
RP2040_DIR := firmware/rp2040
PORT ?= /dev/ttyACM1

.PHONY: bootsel-build bootsel-flash bootsel-diag-flash bootsel-trigger bootsel-flash-rp2040 bootsel-clean bootsel-1200 bootsel-1200-tx bootsel-1200-rx bootsel-1200-both identify-ports

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

# ─── 1200 Baud Touch Reboot (no ESP32 needed) ───────────────────────
# Opens serial port at 1200 baud → RP2040 auto-reboots into BOOTSEL.
# Works with earlephilhower Arduino core and stock RP2040 USB stack.
# Requires board in app mode (PID 000a) with USB CDC connection.
#
# Usage: make bootsel-1200 PORT=/dev/ttyACM0 UF2=path/to/firmware.uf2
bootsel-1200:
	@if [ -z "$(PORT)" ] || [ -z "$(UF2)" ]; then \
		echo "Usage: make bootsel-1200 PORT=/dev/ttyACMX UF2=path.uf2"; \
		echo ""; \
		echo "Identify ports first: make identify-ports"; \
		exit 1; \
	fi
	@echo "Triggering BOOTSEL on $(PORT)..."
	@stty -F $(PORT) 1200 raw -echo 2>/dev/null || true
	@sleep 2
	@DEV=$$(lsblk -lnpo NAME,MODEL | grep 'RP2' | head -1 | awk '{print $$1}'); \
	if [ -z "$$DEV" ]; then \
		echo "ERROR: No RP2 mass storage found. Board may already be in BOOTSEL."; \
		echo "Check: lsblk | grep RP2"; \
		exit 1; \
	fi; \
	PART="$${DEV}1"; \
	echo "Found RP2 at $$PART — flashing $(UF2)..."; \
	sudo mount $$PART /mnt 2>/dev/null || true; \
	sudo cp "$(UF2)" /mnt/ && sync && sudo umount /mnt; \
	echo "FLASH OK — board rebooting"
	@sleep 3

# Convenience: flash TX firmware to 8332 (auto-detect port by serial)
# Usage: make bootsel-1200-tx UF2=path/to/firmware.uf2
bootsel-1200-tx:
	@PORT=$$(for p in /dev/ttyACM*; do \
		udevadm info --query=property $$p 2>/dev/null | grep -q "E663B035973B8332" && echo $$p; \
	done); \
	if [ -z "$$PORT" ]; then echo "ERROR: 8332 not found. Run: make identify-ports"; exit 1; fi; \
	echo "8332 found at $$PORT"; \
	$(MAKE) bootsel-1200 PORT=$$PORT UF2=$(UF2)

# Convenience: flash RX firmware to F242D (auto-detect port by serial)
# Usage: make bootsel-1200-rx UF2=path/to/firmware.uf2
bootsel-1200-rx:
	@PORT=$$(for p in /dev/ttyACM*; do \
		udevadm info --query=property $$p 2>/dev/null | grep -q "E663B035977F242D" && echo $$p; \
	done); \
	if [ -z "$$PORT" ]; then echo "ERROR: F242D not found. Run: make identify-ports"; exit 1; fi; \
	echo "F242D found at $$PORT"; \
	$(MAKE) bootsel-1200 PORT=$$PORT UF2=$(UF2)

# Flash both boards simultaneously
# Usage: make bootsel-1200-both TXUF2=path/tx.uf2 RXUF2=path/rx.uf2
bootsel-1200-both:
	@if [ -z "$(TXUF2)" ] || [ -z "$(RXUF2)" ]; then \
		echo "Usage: make bootsel-1200-both TXUF2=tx.uf2 RXUF2=rx.uf2"; exit 1; \
	fi
	@TXP=$$(for p in /dev/ttyACM*; do udevadm info --query=property $$p 2>/dev/null | grep -q "8332" && echo $$p; done); \
	RXP=$$(for p in /dev/ttyACM*; do udevadm info --query=property $$p 2>/dev/null | grep -q "F242D" && echo $$p; done); \
	if [ -z "$$TXP" ] || [ -z "$$RXP" ]; then echo "ERROR: Can't find both boards. Run: make identify-ports"; exit 1; fi; \
	echo "Triggering both boards into BOOTSEL..."; \
	stty -F $$TXP 1200 raw -echo 2>/dev/null & \
	stty -F $$RXP 1200 raw -echo 2>/dev/null & \
	wait; \
	sleep 2; \
	DEVS=$$(lsblk -lnpo NAME,MODEL | grep 'RP2' | awk '{print $$1"1"}'); \
	if [ $$(echo "$$DEVS" | wc -w) -lt 2 ]; then echo "ERROR: Expected 2 RP2 drives, got: $$DEVS"; exit 1; fi; \
	D1=$$(echo "$$DEVS" | head -1); D2=$$(echo "$$DEVS" | tail -1); \
	echo "Flashing TX to $$D1, RX to $$D2..."; \
	sudo mount $$D1 /mnt && sudo cp "$(TXUF2)" /mnt/ && sync && sudo umount /mnt; \
	sudo mount $$D2 /mnt && sudo cp "$(RXUF2)" /mnt/ && sync && sudo umount /mnt; \
	echo "BOTH FLASHED — boards rebooting"; \
	sleep 3

# Identify all RP2040 and ESP32 boards by serial number
identify-ports:
	@echo "=== Board Port Assignments ==="
	@for port in /dev/ttyACM*; do \
		SERIAL=$$(udevadm info --query=property $$port 2>/dev/null | grep ID_SERIAL_SHORT | cut -d= -f2); \
		VENDOR=$$(udevadm info --query=property $$port 2>/dev/null | grep ID_VENDOR_ID | cut -d= -f2); \
		MODEL=$$(udevadm info --query=property $$port 2>/dev/null | grep ID_MODEL_ID | cut -d= -f2); \
		case "$$SERIAL" in \
			*8332*) LABEL="8332 (TX RP2040)";; \
			*F242D*) LABEL="F242D (RX RP2040)";; \
			*13:21:00*) LABEL="ESP32 (UART bridge / BOOTSEL ctrl)";; \
			*21:FB:18*) LABEL="ESP32 (BOOTSEL ctrl #2)";; \
			*) LABEL="Unknown";; \
		esac; \
		if [ "$$VENDOR" = "2e8a" ]; then TYPE="RP2040"; elif [ "$$VENDOR" = "303a" ]; then TYPE="ESP32"; else TYPE="?"; fi; \
		echo "  $$port: $$LABEL [$$TYPE, PID $$MODEL]"; \
	done
	@echo ""
	@RP2_BOOT=$$(lsusb 2>/dev/null | grep "2e8a:0003" | wc -l); \
	RP2_APP=$$(lsusb 2>/dev/null | grep "2e8a:000a" | wc -l); \
	echo "  BOOTSEL mode: $$RP2_BOOT boards | App mode: $$RP2_APP boards"
