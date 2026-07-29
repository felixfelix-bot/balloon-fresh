# Balloon Fresh — Hardware Control Makefile
# Targets for ESP32-C3 BOOTSEL controller and RP2040 firmware management

BOOTSEL_DIR := firmware/esp32-bootsel-controller
RP2040_DIR := firmware/rp2040
PORT ?= /dev/ttyACM1

.DEFAULT_GOAL := help

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
	@echo "  BOOTSEL mode: $$RP2_BOOT boards | App mode: $$RP2_APP boards"

# ═══════════════════════════════════════════════════════════════════════
# Logic Analyzer Debugging Targets
# ═══════════════════════════════════════════════════════════════════════

RP2040_DIR := firmware/rp2040
CAPTURES_DIR := captures
# PlatformIO env names use rp2040- prefix (e.g. rp2040-raw-tx, rp2040-cont-tx)
# Users can pass the full env name or the short name.

.PHONY: flash capture capture-byte capture-batch capture-compare build \
	analyze list-captures setup help

## ─── flash ───────────────────────────────────────────────────────────
## Flash RP2040 via picotool (BOOTSEL mode required).
## Usage: make flash [ENV=rp2040-raw-tx]
flash: ## Flash RP2040 via picotool. Usage: make flash [ENV=rp2040-raw-tx]
	@if ! command -v picotool >/dev/null 2>&1; then \
		echo "ERROR: picotool not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@if [ -z "$(ENV)" ]; then ENV="rp2040-raw-tx"; fi; \
	UF2="$(RP2040_DIR)/.pio/build/$(ENV)/firmware.uf2"; \
	if [ ! -f "$$UF2" ]; then \
		echo "ERROR: Firmware not found at $$UF2"; \
		echo "Build first: make build ENV=$(ENV)"; \
		exit 1; \
	fi; \
	echo "Flashing $$UF2 to RP2040..."; \
	if ! picotool info >/dev/null 2>&1; then \
		echo "ERROR: No RP2040 in BOOTSEL mode detected."; \
		echo "Hold BOOTSEL button, plug in USB, then retry."; \
		echo "Check: picotool info"; \
		exit 1; \
	fi; \
	picotool load "$$UF2" && picotool reboot; \
	echo "Flash OK — RP2040 rebooting."

## ─── capture ──────────────────────────────────────────────────────────
## Capture SPI signals with sigrok-cli.
## Usage: make capture [DURATION=1] [OUTPUT=capture.sr]
capture: ## Capture SPI with sigrok-cli. Usage: make capture [DURATION=1] [OUTPUT=capture.sr]
	@if ! command -v sigrok-cli >/dev/null 2>&1; then \
		echo "ERROR: sigrok-cli not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@mkdir -p $(CAPTURES_DIR)
	@if [ -z "$(DURATION)" ]; then DURATION=1; fi; \
	if [ -z "$(OUTPUT)" ]; then OUTPUT="capture.sr"; fi; \
	SAMPLES=$$(echo "$(DURATION) * 24000000" | bc); \
	echo "Capturing $$DURATION seconds at 24 MHz → $$OUTPUT"; \
	echo "Channel mapping: D0=CS, D1=SCK, D2=MOSI, D3=MISO, D4=BUSY, D5=IRQ, D6=RST"; \
	sigrok-cli --driver=fx2lafw \
		--config samplerate=24mhz \
		--samples $$SAMPLES \
		--channels D0,D1,D2,D3,D4,D5,D6 \
		-o "$$OUTPUT"; \
	if [ $$? -eq 0 ]; then \
		echo "Capture saved to $$OUTPUT"; \
	else \
		echo "ERROR: Capture failed. Check logic analyzer USB connection."; \
		echo "Try: sigrok-cli --driver=fx2lafw --scan"; \
		exit 1; \
	fi

## ─── capture-byte ─────────────────────────────────────────────────────
## Build + flash raw_tx (per-byte), then capture.
capture-byte: ## Build+flash raw_tx, capture. Usage: make capture-byte [DURATION=1]
	$(MAKE) build ENV=rp2040-raw-tx
	$(MAKE) flash ENV=rp2040-raw-tx
	$(MAKE) capture DURATION=$(or $(DURATION),2) OUTPUT=$(CAPTURES_DIR)/byte-transfer.sr

## ─── capture-batch ───────────────────────────────────────────────────
## Build + flash cont_tx (batch/DMA), then capture.
capture-batch: ## Build+flash cont_tx, capture. Usage: make capture-batch [DURATION=1]
	$(MAKE) build ENV=rp2040-cont-tx
	$(MAKE) flash ENV=rp2040-cont-tx
	$(MAKE) capture DURATION=$(or $(DURATION),2) OUTPUT=$(CAPTURES_DIR)/batch-transfer.sr

## ─── capture-compare ─────────────────────────────────────────────────
## Capture both per-byte and batch for comparison.
capture-compare: ## Capture byte + batch transfers for comparison.
	$(MAKE) capture-byte DURATION=$(or $(DURATION),2)
	@echo "=== Now switch firmware to batch mode ==="
	$(MAKE) capture-batch DURATION=$(or $(DURATION),2)
	@echo ""
	@echo "=== Comparison captures ready ==="
	@ls -lh $(CAPTURES_DIR)/byte-transfer.sr $(CAPTURES_DIR)/batch-transfer.sr 2>/dev/null

## ─── build ───────────────────────────────────────────────────────────
## Build RP2040 firmware with PlatformIO.
## Usage: make build [ENV=rp2040-raw-tx]
build: ## Build firmware. Usage: make build [ENV=rp2040-raw-tx]
	@if ! command -v pio >/dev/null 2>&1; then \
		echo "ERROR: PlatformIO (pio) not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@if [ -z "$(ENV)" ]; then ENV="rp2040-raw-tx"; fi; \
	echo "Building firmware env: $(ENV)"; \
	cd $(RP2040_DIR) && pio run -e $(ENV)

## ─── analyze ──────────────────────────────────────────────────────────
## Open a capture file for analysis.
## Usage: make analyze FILE=captures/byte-transfer.sr
analyze: ## Open capture for analysis. Usage: make analyze FILE=captures/byte-transfer.sr
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make analyze FILE=captures/byte-transfer.sr"; \
		exit 1; \
	fi
	@if [ ! -f "$(FILE)" ]; then \
		echo "ERROR: File not found: $(FILE)"; \
		echo "List captures: make list-captures"; \
		exit 1; \
	fi
	@if command -v pulseview >/dev/null 2>&1; then \
		echo "Opening $(FILE) in PulseView..."; \
		pulseview "$(FILE)" & \
	else \
		echo "pulseview not installed. Install: sudo apt install pulseview"; \
		echo "Or use: make decode FILE=$(FILE)"; \
	fi

## ─── decode ───────────────────────────────────────────────────────────
## Decode SPI protocol from capture. Usage: make decode FILE=captures/foo.sr
decode: ## Decode SPI from capture. Usage: make decode FILE=captures/foo.sr
	@if [ -z "$(FILE)" ]; then echo "Usage: make decode FILE=captures/foo.sr"; exit 1; fi
	@echo "Decoding SPI from $(FILE)..."
	@sigrok-cli -i $(FILE) \
		--protocol-decoders spi:cs=D0:clk=D1:mosi=D2:miso=D3 \
		-P spi \
		-A spi 2>&1 | grep -v "^spi-1: [01]$$"

## ─── decode-hex ───────────────────────────────────────────────────────
## Show SPI hex dump. Usage: make decode-hex FILE=captures/foo.sr
decode-hex: ## SPI hex dump. Usage: make decode-hex FILE=captures/foo.sr
	@if [ -z "$(FILE)" ]; then echo "Usage: make decode-hex FILE=captures/foo.sr"; exit 1; fi
	@echo "SPI hex dump from $(FILE)..."
	@sigrok-cli -i $(FILE) \
		--protocol-decoders spi:cs=D0:clk=D1:mosi=D2:miso=D3 \
		-P spi \
		-B spi=mosi 2>&1 | xxd | head -100

## ─── analyze-timing ───────────────────────────────────────────────────
## Full SPI timing analysis (clock freq, gaps, throughput). Usage: make analyze-timing FILE=captures/foo.sr
analyze-timing: ## Full SPI timing analysis. Usage: make analyze-timing FILE=captures/foo.sr
	@if [ -z "$(FILE)" ]; then echo "Usage: make analyze-timing FILE=captures/foo.sr"; exit 1; fi
	@python3 scripts/analyze_spi.py "$(FILE)"

## ─── zip-capture ──────────────────────────────────────────────────────
## Compress capture for sharing. Usage: make zip-capture FILE=captures/foo.sr
zip-capture: ## Compress capture. Usage: make zip-capture FILE=captures/foo.sr
	@if [ -z "$(FILE)" ]; then echo "Usage: make zip-capture FILE=captures/foo.sr"; exit 1; fi
	@BASENAME=$$(basename $(FILE) .sr); \
	DIR=$$(dirname $(FILE)); \
	cd $$DIR && zip $$BASENAME.zip $$BASENAME.sr; \
	echo "Created: $$DIR/$$BASENAME.zip"

## ─── list-captures ───────────────────────────────────────────────────
## List all capture files with timestamps and sizes.
list-captures: ## List capture files in captures/ with timestamps and sizes.
	@echo "=== Capture Files ==="
	@if [ ! -d $(CAPTURES_DIR) ] || [ -z "$$(ls -A $(CAPTURES_DIR) 2>/dev/null)" ]; then \
		echo "No captures directory or no files found."; \
		echo "Run: make capture DURATION=2 OUTPUT=$(CAPTURES_DIR)/test.sr"; \
	else \
		ls -lh --time-style=long-iso $(CAPTURES_DIR)/*.sr 2>/dev/null || echo "No .sr files found."; \
		echo ""; \
		COUNT=$$(ls $(CAPTURES_DIR)/*.sr 2>/dev/null | wc -l); \
		TOTAL_SIZE=$$(du -sh $(CAPTURES_DIR) 2>/dev/null | cut -f1); \
		echo "Total: $$COUNT capture(s), $$TOTAL_SIZE"; \
	fi

## ─── install-framework ────────────────────────────────────────────────
## Install the earlephilhower Arduino core for RP2040 (needed for all builds).
## Run once if builds fail with "Arduino.h: No such file or directory".
## Also installs Max Gerhardt platform fork + sigrok firmware.
install-framework: ## Install earlephilhower core + platform fork + sigrok firmware.
	@echo "Installing Max Gerhardt's platform-raspberrypi fork (earlephilhower support)..."
	@pio platform install "https://github.com/maxgerhardt/platform-raspberrypi.git" 2>/dev/null || \
		echo "Platform already installed or installing..."
	@echo ""
	@echo "Installing earlephilhower Arduino-Pico framework..."
	@mkdir -p ~/./.platformio/packages
	@if [ -d ~/./.platformio/packages/framework-arduinopico ]; then \
		echo "framework-arduinopico already exists, skipping."; \
	else \
		echo "Cloning arduino-pico (earlephilhower core)..."; \
		git clone --recursive --depth 1 https://github.com/earlephilhower/arduino-pico.git ~/./.platformio/packages/framework-arduinopico; \
	fi
	@if [ -d ~/./.platformio/packages/tool-picotool-rp2040-earlephilhower ]; then \
		echo "tool-picotool-rp2040-earlephilhower already exists, skipping."; \
	else \
		echo "Cloning earlephilhower picotool..."; \
		git clone --depth 1 https://github.com/earlephilhower/picotool.git ~/./.platformio/packages/tool-picotool-rp2040-earlephilhower; \
	fi
	@echo ""
	@echo "Installing sigrok fx2lafw firmware (logic analyzer driver)..."
	@sudo apt install -y sigrok-firmware-fx2lafw 2>/dev/null || \
		echo "sigrok-firmware-fx2lafw not found in apt — may need manual install"
	@echo ""
	@echo "Done. Now rebuild:"
	@echo "  rm -rf $(RP2040_DIR)/.pio"
	@echo "  make build ENV=rp2040-raw-tx"

## Install udev rules for RP2040 + logic analyzer (requires sudo).
install-udev: ## Install USB permissions for RP2040 + logic analyzer.
	@echo "Installing udev rules for RP2040 + logic analyzer..."
	@sudo bash -c 'printf "%s\n" \
		"# RP2040 BOOTSEL mode" \
		"SUBSYSTEM==\"usb\", ATTRS{idVendor}==\"2e8a\", ATTRS{idProduct}==\"0003\", MODE=\"0666\"" \
		"# RP2040 app mode (CDC)" \
		"SUBSYSTEM==\"usb\", ATTRS{idVendor}==\"2e8a\", ATTRS{idProduct}==\"000a\", MODE=\"0666\"" \
		"# Logic analyzer (Saleae/fx2lafw)" \
		"SUBSYSTEM==\"usb\", ATTRS{idVendor}==\"0925\", ATTRS{idProduct}==\"3881\", MODE=\"0666\"" \
		"# Logic analyzer (generic fx2)" \
		"SUBSYSTEM==\"usb\", ATTRS{idVendor}==\"1d50\", ATTRS{idProduct}==\"6086\", MODE=\"0666\"" \
		> /etc/udev/rules.d/99-debug.rules'
	@sudo udevadm control --reload-rules && sudo udevadm trigger
	@echo "Done. Unplug and replug USB devices for rules to take effect."

## Force reinstall the earlephilhower framework (deletes existing, re-clones).
reinstall-framework: ## Force reinstall earlephilhower Arduino-Pico core.
	@echo "Removing existing earlephilhower packages..."
	@rm -rf ~/./.platformio/packages/framework-arduinopico
	@rm -rf ~/./.platformio/packages/tool-picotool-rp2040-earlephilhower
	@$(MAKE) install-framework

## ─── debug (one-command workflow) ─────────────────────────────────────
## Build firmware, auto-flash RP2040 (1200 baud BOOTSEL), start TX, capture SPI signals.
## Usage: make debug [ENV=rp2040-cont-tx] [DURATION=1] [OUTPUT=captures/debug.sr]
## Prerequisites: RP2040 connected via USB, logic analyzer connected.
debug: ## One-command: build + flash + start TX + capture.
	@echo "=== Balloon Speed Tests — One-Command Debug Workflow ==="
	@echo ""
	@echo "Step 1/4: Building firmware ($(or $(ENV),rp2040-cont-tx))..."
	@cd $(RP2040_DIR) && pio run -e $(or $(ENV),rp2040-cont-tx)
	@echo ""
	@echo "Step 2/4: Flashing RP2040..."
	@UF2=$$(find $(RP2040_DIR)/.pio/build/$(or $(ENV),rp2040-cont-tx) -name firmware.uf2 2>/dev/null | head -1); \
	if [ -z "$$UF2" ]; then \
		echo "ERROR: No firmware.uf2 found. Build may have failed."; exit 1; \
	fi; \
	if ! command -v picotool >/dev/null 2>&1; then \
		echo "ERROR: picotool not found. Install: sudo apt install picotool"; exit 1; \
	fi; \
	echo "Firmware: $$UF2"; \
	BOOTSEL_ALREADY=0; \
	if ls /dev/disk/by-label/RPI-RP2 >/dev/null 2>&1; then \
		echo "RP2040 already in BOOTSEL mode (RPI-RP2 disk found). Skipping 1200 baud."; \
		BOOTSEL_ALREADY=1; \
	else \
		echo "Scanning for RP2040 USB CDC port (PID 000a)..."; \
		PORT=""; \
		for p in /dev/ttyACM[0-9]; do \
			[ -e "$$p" ] || continue; \
			PID=$$(udevadm info -q property "$$p" 2>/dev/null | grep "ID_MODEL_ID=" | cut -d= -f2); \
			VID=$$(udevadm info -q property "$$p" 2>/dev/null | grep "ID_VENDOR_ID=" | cut -d= -f2); \
			SERIAL=$$(udevadm info -q property "$$p" 2>/dev/null | grep "ID_SERIAL_SHORT=" | cut -d= -f2); \
			echo "  $$p: VID=$$VID PID=$$PID serial=$$SERIAL"; \
			if [ "$$PID" = "000a" ] && [ "$$VID" = "2e8a" ]; then PORT="$$p"; fi; \
		done; \
		if [ -z "$$PORT" ]; then \
			echo "No RP2040 CDC port. Trying all ACM ports for 1200 baud..."; \
			for p in /dev/ttyACM[0-9]; do \
				[ -e "$$p" ] || continue; \
				VENDOR=$$(udevadm info -q property "$$p" 2>/dev/null | grep "ID_VENDOR=" | cut -d= -f2); \
				if echo "$$VENDOR" | grep -qi "raspberry\|pico\|2e8a"; then PORT="$$p"; fi; \
			done; \
		fi; \
		if [ -z "$$PORT" ]; then \
			echo "ERROR: No RP2040 found. Not in BOOTSEL, no CDC port."; \
			echo "Fix: hold white BOOTSEL button, unplug USB, plug back in while holding."; \
			exit 1; \
		fi; \
		echo "Triggering BOOTSEL on $$PORT via aggressive 1200 baud..."; \
		python3 -c "import serial,time; s=serial.Serial(); s.port='$$PORT'; s.baudrate=1200; s.dtr=False; s.rts=False; \
			try: s.open(); \
			except: pass; \
			try: s.close(); \
			except: pass; \
			time.sleep(0.5)" 2>/dev/null; \
		echo "Waiting for RPI-RP2 drive..."; \
		OK=""; \
		for i in $$(seq 1 10); do \
			if ls /dev/disk/by-label/RPI-RP2 >/dev/null 2>&1; then OK=1; break; fi; \
			sleep 1; \
		done; \
		if [ -z "$$OK" ]; then \
			echo "1200 baud failed. Trying stty fallback..."; \
			stty -F $$PORT 1200 2>/dev/null; sleep 3; \
			for i in $$(seq 1 10); do \
				if ls /dev/disk/by-label/RPI-RP2 >/dev/null 2>&1; then OK=1; break; fi; \
				sleep 1; \
			done; \
		fi; \
		if [ -z "$$OK" ]; then \
			echo "ERROR: Could not trigger BOOTSEL."; \
			echo "Hold the white BOOTSEL button, unplug USB, plug back in while holding."; \
			echo "Then re-run: make debug ENV=$(or $(ENV),rp2040-cont-tx)"; \
			exit 1; \
		fi; \
	fi; \
	RPIDEV=$$(ls /dev/disk/by-label/RPI-RP2 2>/dev/null | head -1); \
	RPIBLOCK=$$(readlink -f $$RPIDEV); \
	echo "RP2040 in BOOTSEL at $$RPIBLOCK"; \
	echo "Flashing via picotool..."; \
	picotool load "$$UF2" 2>&1 || { \
		echo "picotool load failed, trying UF2 copy..."; \
		FLASHDIR=/tmp/rp2040-flash; \
		umount $$FLASHDIR 2>/dev/null; \
		mkdir -p $$FLASHDIR; \
		sudo mount -o uid=$$(id -u),gid=$$(id -g) $$RPIBLOCK $$FLASHDIR || \
			sudo mount $$RPIBLOCK $$FLASHDIR; \
		cp "$$UF2" $$FLASHDIR/ && sync; \
		umount $$FLASHDIR 2>/dev/null; \
	}; \
	echo "Flashed. Waiting for reboot..."; \
	sleep 3; \
	picotool reboot 2>/dev/null || true
	@echo ""
	@echo "Step 3/4: Waiting for RP2040 serial port + starting TX..."
	@printf "Waiting for serial port"; \
	PORT=""; \
	for i in $$(seq 1 30); do \
		for p in /dev/ttyACM[0-9]; do \
			[ -e "$$p" ] || continue; \
			PID=$$(udevadm info -q property "$$p" 2>/dev/null | grep "ID_MODEL_ID=" | cut -d= -f2); \
			VID=$$(udevadm info -q property "$$p" 2>/dev/null | grep "ID_VENDOR_ID=" | cut -d= -f2); \
			if [ "$$PID" = "000a" ] && [ "$$VID" = "2e8a" ]; then PORT="$$p"; break; fi; \
		done; \
		if [ -n "$$PORT" ]; then break; fi; \
		printf "."; sleep 0.5; \
	done; \
	echo ""; \
	if [ -z "$$PORT" ]; then \
		echo "WARNING: No serial port found. TX may not have started."; \
		echo "Capture will proceed anyway (firmware may auto-start)."; \
	else \
		echo "Found $$PORT, sending RUN command..."; \
		sleep 2; \
		echo "RUN" | sudo tee $$PORT >/dev/null 2>&1 || \
			stty -F $$PORT 115200 raw -echo && echo "RUN" > $$PORT 2>/dev/null || \
			echo "WARNING: Could not send RUN. Firmware may need manual start."; \
		sleep 1; \
		echo "TX started."; \
	fi
	@echo ""
	@echo "Step 4/4: Capturing SPI signals ($(or $(DURATION),1)s)..."
	@echo "Settling 3s for LA USB re-enumeration..."
	@sleep 3
	@mkdir -p $(CAPTURES_DIR)
	@OUTPUT=$(or $(OUTPUT),$(CAPTURES_DIR)/debug.sr); \
	echo "Capturing to $$OUTPUT ..."; \
	echo "Channel mapping: D0=CS, D1=SCK, D2=MOSI, D3=MISO, D4=BUSY, D5=IRQ, D6=RST"; \
	sigrok-cli --driver fx2lafw --config samplerate=24mhz --samples $(or $(DURATION),1)000000 \
		--channels D0,D1,D2,D3,D4,D5,D6 -o $$OUTPUT 2>&1 || \
		{ echo "ERROR: sigrok-cli failed. Check logic analyzer is plugged in."; \
		echo "Try: sigrok-cli --list"; exit 1; }
	@echo ""
	@echo "=== Done! ==="
	@echo "Capture saved to: $(or $(OUTPUT),$(CAPTURES_DIR)/debug.sr)"
	@OUTPUT=$(or $(OUTPUT),$(CAPTURES_DIR)/debug.sr); \
	BASENAME=$$(basename $$OUTPUT .sr); \
	DIR=$$(cd $$(dirname $$OUTPUT) && pwd); \
	cd $$DIR && zip $$BASENAME.zip $$BASENAME.sr; \
	echo "Zip ready: $$DIR/$$BASENAME.zip"
	@echo "Analyze with: make analyze-timing FILE=$(or $(OUTPUT),$(CAPTURES_DIR)/debug.sr)"

## ─── setup ────────────────────────────────────────────────────────────
## Run the ansible playbook to install all dependencies.
setup: ## Install all deps via ansible playbook.
	@if ! command -v ansible-playbook >/dev/null 2>&1; then \
		echo "ERROR: ansible-playbook not found. Install with: pip install ansible"; \
		exit 1; \
	fi
	@echo "Installing deps via ansible (will ask for sudo password)..."
	@ansible-playbook ansible/setup-debug-env.yml -K --connection=local || \
		echo "" ; \
		echo "If ansible sudo prompt timed out, run directly:" ; \
	@echo "  ansible-playbook ansible/setup-debug-env.yml --ask-become-pass --connection=local"

## ─── sweep (payload size sweep — find throughput sweet spot) ──────────
## Runs 4 captures with different packet sizes: 32, 64, 128, 255 bytes.
## Auto-triggers BOOTSEL via 1200 baud between iterations. No manual button.
## Results in captures/sweep-*.sr
sweep: ## Payload size sweep. Fully automated — no manual BOOTSEL needed.
	@for SIZE in 32 64 128 255; do \
		echo ""; \
		echo "========================================"; \
		echo "SWEEP: $${SIZE}-byte packets"; \
		echo "========================================"; \
		$(MAKE) debug ENV=rp2040-sweep-$${SIZE} DURATION=1 OUTPUT=$(CAPTURES_DIR)/sweep-$${SIZE}.sr || \
			{ echo "SWEEP FAILED at $${SIZE}-byte step"; exit 1; }; \
		echo ""; \
		echo "Waiting 2s before next size..."; \
		sleep 2; \
	done
	@echo ""; echo "=== SWEEP COMPLETE ==="; echo "All captures in $(CAPTURES_DIR)/sweep-*.sr"

## ─── probe (diagnostic dump for remote debugging) ────────────────────
## Prints: USB devices, ACM port details, logic analyzer, picotool, RPI-RP2
probe: ## Dump all USB/serial/device info for remote debugging.
	@echo "═══ USB DEVICES ═══"
	@lsusb
	@echo ""
	@echo "═══ ACM PORTS ═══"
	@for dev in /dev/ttyACM[0-9]; do \
		[ -e "$$dev" ] || continue; \
		file "$$dev" 2>/dev/null | grep -q "character device" || { echo "$$dev: NOT a char device (REGULAR FILE — see Pitfall #15)"; continue; }; \
		echo "--- $$dev ---"; \
		udevadm info -q property "$$dev" 2>/dev/null | grep -E "ID_VENDOR|ID_MODEL|ID_SERIAL|ID_USB_ID|DEVPATH" || echo "  (no udev info)"; \
	done
	@echo ""
	@echo "═══ RPI-RP2 (BOOTSEL) ═══"
	@ls -la /dev/disk/by-label/RPI-RP2 2>/dev/null || echo "Not in BOOTSEL"
	@echo ""
	@echo "═══ PICOTOOL ═══"
	@which picotool >/dev/null 2>&1 && picotool info 2>&1 || echo "picotool: not found"
	@echo ""
	@echo "═══ SIGROK DEVICES ═══"
	@sigrok-cli --scan-drivers 2>&1 | head -5 || echo "sigrok-cli: not found"
	@echo ""
	@echo "═══ PYTHON PYSERIAL ═══"
	@python3 -c "import serial; print('pyserial OK, version:', serial.__version__)" 2>&1
	@echo ""
	@echo "═══ GIT BRANCH ═══"
	@git branch --show-current
	@git log --oneline -3

## ─── help ──────────────────────────────────────────────────────────────
help: ## Show this help message.
	@echo "Balloon Speed Tests — Logic Analyzer Debugging"
	@echo ""
	@echo "Setup:"
	@echo "  make setup             Install all deps via ansible playbook"
	@echo "  make install-framework Install earlephilhower Arduino core (fix Arduino.h errors)"
	@echo "  make install-udev      Install USB permissions for RP2040 + logic analyzer"
	@echo "  make reinstall-framework  Force reinstall earlephilhower core"
	@echo ""
	@echo "Firmware:"
	@echo "  make debug [ENV=rp2040-cont-tx] [DURATION=1]  One-command: build+flash+TX+capture"
	@echo "  make build [ENV=rp2040-raw-tx]   Build firmware (default: rp2040-raw-tx)"
	@echo "  make flash [ENV=rp2040-raw-tx]    Flash RP2040 via picotool (BOOTSEL required)"
	@echo ""
	@echo "Capture (logic analyzer):"
	@echo "  make capture [DURATION=1] [OUTPUT=capture.sr]  Capture SPI signals"
	@echo "  make capture-byte [DURATION=2]     Build+flash raw_tx, capture per-byte transfer"
	@echo "  make capture-batch [DURATION=2]    Build+flash cont_tx, capture batch/DMA transfer"
	@echo "  make capture-compare [DURATION=2]  Capture both byte+batch for comparison"
	@echo ""
	@echo "Analysis:"
	@echo "  make analyze FILE=captures/byte-transfer.sr  Open capture in pulseview or print sigrok hints"
	@echo "  make list-captures                 List all .sr files with sizes"
	@echo ""
	@echo "Help:"
	@echo "  make help                Show this message"
	@echo ""
	@echo "Available PlatformIO environments (common):"
	@echo "  rp2040-raw-tx    Per-byte SPI transfer"
	@echo "  rp2040-cont-tx    Batch/DMA continuous transfer"
	@echo "  rp2040-raw-tx-pipe   Pipelined transfer"
	@echo ""
	@echo "Channel mapping: CH1=CS, CH2=SCK, CH3=MOSI, CH4=MISO, CH5=BUSY, CH6=IRQ, CH7=RST"

# ═══════════════════════════════════════════════════════════════════════
# Range Test Targets (from master branch)
# ═══════════════════════════════════════════════════════════════════════

TX_SERIAL = E663B035977F242D
RX_SERIAL = E663B035973B8332
PYTHON = python3
TOOLS_DIR = tools

##@ Monitoring
.PHONY: monitor-tx monitor-rx
monitor-tx: ## Read TX serial output (Ctrl+C to stop)
	@TX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(TX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$TX_PORT" ]; then echo "ERROR: TX board not found. Run: make find-ports"; exit 1; fi; \
	echo "Monitoring TX at $$TX_PORT (Ctrl+C to stop)"; \
	stty -F $$TX_PORT 115200 raw -echo; cat $$TX_PORT

monitor-rx: ## Read RX serial output (Ctrl+C to stop)
	@RX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(RX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$RX_PORT" ]; then echo "ERROR: RX board not found. Run: make find-ports"; exit 1; fi; \
	echo "Monitoring RX at $$RX_PORT (Ctrl+C to stop)"; \
	stty -F $$RX_PORT 115200 raw -echo; cat $$RX_PORT

##@ Time Sync
.PHONY: sync-time sync-tx sync-rx
sync-tx: ## Sync TX board time from laptop clock
	@TX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(TX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$TX_PORT" ]; then echo "ERROR: TX board not found. Run: make find-ports"; exit 1; fi; \
	echo "Syncing TX at $$TX_PORT..."; \
	$(PYTHON) -c "import serial,time; s=serial.Serial('$$TX_PORT',115200); s.write(f'SET_TIME {int(time.time())}\n'.encode()); print('TX synced to', int(time.time())); s.close()"

sync-rx: ## Sync RX board time from laptop clock
	@RX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(RX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$RX_PORT" ]; then echo "ERROR: RX board not found. Run: make find-ports"; exit 1; fi; \
	echo "Syncing RX at $$RX_PORT..."; \
	$(PYTHON) -c "import serial,time; s=serial.Serial('$$RX_PORT',115200); s.write(f'SET_TIME {int(time.time())}\n'.encode()); print('RX synced to', int(time.time())); s.close()"

sync-time: sync-tx ## Alias for sync-tx

##@ Walk Test
.PHONY: walk-test
walk-test: ## Start robust walk capture on RX board (runs until Ctrl+C)
	@RX_PORT=$$(for p in /dev/ttyACM[0-9]; do \
		[ -e "$$p" ] || continue; \
		udevadm info -q property -n "$$p" 2>/dev/null | grep -q $(RX_SERIAL) && echo "$$p" && break; \
	done); \
	if [ -z "$$RX_PORT" ]; then echo "ERROR: RX board not found. Run: make find-ports"; exit 1; fi; \
	echo "Starting walk capture on RX at $$RX_PORT (Ctrl+C to stop)"; \
	$(PYTHON) $(TOOLS_DIR)/walk_capture.py 7200 $$RX_PORT

##@ Testing
.PHONY: test test-unit test-hardware
test: ## Run full pytest suite (includes hardware tests)
	$(PYTHON) -m pytest tests/ -v --tb=short

test-unit: ## Run unit tests only (no hardware required)
	$(PYTHON) -m pytest tests/test_phase_sync.py tests/test_rmc_parser.py tests/test_c_host.py -v --tb=short -m "not hardware"

test-hardware: ## Run hardware integration tests only (requires boards connected)
	$(PYTHON) -m pytest tests/ -v --tb=short -m "hardware"

##@ Clean
.PHONY: clean
clean: ## Clean PlatformIO build artifacts
	cd $(RP2040_DIR) && pio run -t clean
	rm -rf .pytest_cache tests/__pycache__

