MESHCORE_DIR := MeshCore
MESHCORE_REPO := https://github.com/meshcore-dev/MeshCore.git
MESHCORE_TAG := companion-v1.15.0
PORT ?= /dev/ttyACM0
BAUD := 115200

.PHONY: setup verify-toolchain build-all build-companion build-companion-ble \
        build-companion-wifi build-chat build-kiss build-repeater build-room \
        flash-companion flash-chat flash-kiss flash-repeater monitor \
        test-t1 clean dist-clean

setup: $(MESHCORE_DIR)
	pip install platformio 2>/dev/null || pip3 install platformio
	./patches/apply-patches.sh $(MESHCORE_DIR)
	@echo ""
	@echo "Setup complete. Run 'make verify-toolchain' to test the build."

$(MESHCORE_DIR):
	git clone --depth 1 --branch $(MESHCORE_TAG) $(MESHCORE_REPO) $(MESHCORE_DIR)
	./patches/apply-patches.sh $(MESHCORE_DIR)

verify-toolchain:
	cd $(MESHCORE_DIR) && pio run -e Xiao_C3_companion_radio_usb

build-companion:
	cd $(MESHCORE_DIR) && pio run -e LR2021_companion_radio_usb

build-companion-ble:
	cd $(MESHCORE_DIR) && pio run -e LR2021_companion_radio_ble

build-companion-wifi:
	cd $(MESHCORE_DIR) && pio run -e LR2021_companion_radio_wifi

build-chat:
	cd $(MESHCORE_DIR) && pio run -e LR2021_secure_chat

build-kiss:
	cd $(MESHCORE_DIR) && pio run -e LR2021_kiss_modem

build-repeater:
	cd $(MESHCORE_DIR) && pio run -e LR2021_repeater

build-room:
	cd $(MESHCORE_DIR) && pio run -e LR2021_room_server

build-all: build-companion build-companion-ble build-companion-wifi build-chat build-kiss build-repeater build-room

flash-companion: build-companion
	cd $(MESHCORE_DIR) && pio run --target upload -e LR2021_companion_radio_usb --upload-port $(PORT)

flash-chat: build-chat
	cd $(MESHCORE_DIR) && pio run --target upload -e LR2021_secure_chat --upload-port $(PORT)

flash-kiss: build-kiss
	cd $(MESHCORE_DIR) && pio run --target upload -e LR2021_kiss_modem --upload-port $(PORT)

flash-repeater: build-repeater
	cd $(MESHCORE_DIR) && pio run --target upload -e LR2021_repeater --upload-port $(PORT)

monitor:
	pio device monitor -p $(PORT) -b $(BAUD)

test-t1: build-all
	@echo "=== Tier 1: All LR2021 builds succeeded ==="
	@for f in companion_radio_usb companion_radio_ble companion_radio_wifi secure_chat kiss_modem repeater room_server; do \
		if [ -f $(MESHCORE_DIR)/.pio/build/*_LR2021_*/firmware.bin ]; then \
			echo "  OK: $$f"; \
		else \
			echo "  MISSING: $$f"; \
		fi; \
	done

clean:
	cd $(MESHCORE_DIR) && pio run --target clean

dist-clean:
	rm -rf $(MESHCORE_DIR)
