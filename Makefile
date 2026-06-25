# Makefile for ESP32 Pico Balloon Tracker
#
# Targets:
#   build          - Build firmware with ESP-IDF
#   flash          - Flash firmware to XIAO ESP32C3
#   monitor        - Open serial monitor
#   clean          - Clean build artifacts
#   commit         - Stage all changes and commit
#   push           - Push to nostr via ngit
#   blog-list      - List all blog posts
#   blog-publish   - Publish a blog post to Nostr (NIP-23 kind 30023)
#   blog-upload    - Upload an image to Blossom
#   blog-all       - Upload images + publish blog post
#   pressure-test  - Flash balloon pressure test firmware
#   antenna-sim    - Run antenna simulation
#
# Usage:
#   make blog-publish POST=001-introduction
#   make blog-upload IMG=blog/images/wiring-diagram.png
#   make blog-all POST=001-introduction

# Config
RELAYS = wss://relay.orangesync.tech,wss://ngit.orangesync.tech,wss://relay.ngit.dev,wss://nos.lol,wss://relay.damus.io,wss://relay.nostr.band
BLOSSOM = https://blossom.orangesync.tech
BLOG_DIR = blog
NSEC = $(shell git config --local nostr.nsec 2>/dev/null)
NPUB = $(shell git config --local nostr.npub 2>/dev/null)
SERIAL_PORT ?= /dev/ttyACM0

# Derived
RELAY_ARGS = $(foreach r,$(subst $(comma), ,$(RELAYS)),wss://$(r))
NSEC_ARG = $(if $(NSEC),--sec $(NSEC),)

# Phony targets
.PHONY: build flash monitor clean commit push \
        blog-list blog-publish blog-upload blog-all \
        pressure-test antenna-sim help

# Default
help:
	@echo "ESP32 Pico Balloon Tracker - Makefile"
	@echo ""
	@echo "Firmware:"
	@echo "  make build            Build firmware (ESP-IDF)"
	@echo "  make flash            Flash to XIAO ESP32C3"
	@echo "  make monitor          Serial monitor"
	@echo "  make clean            Clean build"
	@echo ""
	@echo "Git / Nostr:"
	@echo "  make commit           Stage + commit all changes"
	@echo "  make push             Push to nostr via ngit"
	@echo ""
	@echo "Blog (NIP-23 long-form):"
	@echo "  make blog-list                    List all blog posts"
	@echo "  make blog-publish POST=<slug>     Publish a blog post"
	@echo "  make blog-upload IMG=<path>       Upload image to Blossom"
	@echo "  make blog-all POST=<slug>         Upload images + publish"
	@echo ""
	@echo "Tools:"
	@echo "  make pressure-test     Flash pressure test firmware"
	@echo "  make antenna-sim       Run antenna simulation"

# =============================================================================
# Firmware
# =============================================================================

build:
	source ~/esp/esp-idf/export.sh 2>/dev/null; \
	cd firmware && idf.py build

flash: build
	source ~/esp/esp-idf/export.sh 2>/dev/null; \
	cd firmware && idf.py -p $(SERIAL_PORT) flash

monitor:
	source ~/esp/esp-idf/export.sh 2>/dev/null; \
	cd firmware && idf.py -p $(SERIAL_PORT) monitor

clean:
	rm -rf firmware/build

# =============================================================================
# Git / Nostr
# =============================================================================

commit:
	@git add -A
	@git diff --cached --quiet && echo "Nothing to commit" || \
		git commit -m "update $(shell date +%Y-%m-%d)"

push:
	git push origin master

# =============================================================================
# Blog - NIP-23 Long-Form Content (kind 30023)
# =============================================================================

BLOG_POST = $(BLOG_DIR)/$(POST).md

blog-list:
	@echo "=== Blog Posts ==="
	@ls -1 $(BLOG_DIR)/*.md 2>/dev/null | while read f; do \
		slug=$$(basename "$$f" .md); \
		title=$$(head -1 "$$f" | sed 's/^# *//'); \
		echo "  $$slug  $$title"; \
	done || echo "  (no posts yet)"
	@echo ""
	@echo "=== Uploaded Images ==="
	@ls -1 $(BLOG_DIR)/images/*.url 2>/dev/null | while read f; do \
		echo "  $$(basename $$f .url): $$(cat $$f)"; \
	done || echo "  (no images yet)"

# Upload a single image to Blossom
# make blog-upload IMG=blog/images/photo.png
blog-upload:
	@if [ -z "$(IMG)" ]; then echo "Usage: make blog-upload IMG=blog/images/photo.png"; exit 1; fi
	@if [ ! -f "$(IMG)" ]; then echo "File not found: $(IMG)"; exit 1; fi
	@echo "Uploading $(IMG) to $(BLOSSOM)..."
	@sha=$$(nak blossom upload -s $(BLOSSOM) $(NSEC_ARG) "$(IMG)" 2>/dev/null | grep -oP 'sha256=\K[a-f0-9]+' | head -1); \
	if [ -z "$$sha" ]; then \
		echo "ERROR: Upload failed"; exit 1; \
	fi; \
	url="$(BLOSSOM)/$$sha"; \
	basename="$$(basename $(IMG))"; \
	echo "$$url" > "$(BLOG_DIR)/images/$${basename%.*}.url"; \
	echo "Uploaded: $$url"; \
	echo "URL saved to: $(BLOG_DIR)/images/$${basename%.*}.url"

# Upload all images referenced in a blog post that haven't been uploaded yet
blog-upload-all:
	@if [ -z "$(POST)" ]; then echo "Usage: make blog-upload-all POST=001-introduction"; exit 1; fi
	@echo "Scanning $(BLOG_POST) for images..."
	@grep -oP '!\[.*?\]\((?!http)(.*?)\)' $(BLOG_POST) | grep -oP '\((.*?)\)' | tr -d '()' | while read img; do \
		if [ ! -f "$$img" ]; then \
			echo "SKIP: $$img not found"; \
			continue; \
		fi; \
		urlfile="$$(dirname $$img)/$$(basename $$img .png).url"; \
		urlfile2="$$(dirname $$img)/$$(basename $$img .jpg).url"; \
		if [ -f "$$urlfile" ] || [ -f "$$urlfile2" ]; then \
			echo "SKIP: $$img already uploaded"; \
			continue; \
		fi; \
		$(MAKE) blog-upload IMG="$$img"; \
	done

# Publish a blog post as NIP-23 (kind 30023)
# make blog-publish POST=001-introduction
blog-publish:
	@if [ -z "$(POST)" ]; then echo "Usage: make blog-publish POST=001-introduction"; exit 1; fi
	@if [ ! -f "$(BLOG_POST)" ]; then echo "Post not found: $(BLOG_POST)"; exit 1; fi
	@echo "Publishing $(POST)..."
	@title=$$(head -1 $(BLOG_POST) | sed 's/^# *//'); \
	echo "Title: $$title"; \
	summary=$$(grep -m1 '^>' $(BLOG_POST) | sed 's/^> *//' || echo "$$title"); \
	published=$$(grep -m1 '^date:' $(BLOG_POST) | sed 's/^date: *//' || date -u +%Y-%m-%dT%H:%M:%SZ); \
	echo "Publishing to relays..."; \
	nak event -k 30023 \
		$(NSEC_ARG) \
		-d "$(POST)" \
		-t "title=$$title" \
		-t "summary=$$summary" \
		-t "published_at=$$(date -d "$$published" +%s 2>/dev/null || date +%s)" \
		-t "t=balloon" \
		-t "t=pico-balloon" \
		-t "t=lora" \
		-t "t=esp32" \
		-t "t=lr2021" \
		-t "t=ham-radio" \
		-t "t=aerospace" \
		-c "@$(BLOG_POST)" \
		$(RELAY_ARGS) 2>&1; \
	echo "Published!"

# Upload all images + publish post
blog-all:
	@if [ -z "$(POST)" ]; then echo "Usage: make blog-all POST=001-introduction"; exit 1; fi
	$(MAKE) blog-upload-all POST=$(POST)
	$(MAKE) blog-publish POST=$(POST)

# =============================================================================
# Tools
# =============================================================================

pressure-test:
	@echo "Flashing pressure test firmware..."
	@if [ ! -d "tools/balloon_pressure_test" ]; then \
		echo "Pressure test firmware not yet created. Run: make setup-tools"; \
		exit 1; \
	fi
	source ~/esp/esp-idf/export.sh 2>/dev/null; \
	cd tools/balloon_pressure_test && idf.py -p $(SERIAL_PORT) flash monitor

antenna-sim:
	python3 hardware/simulation/antenna_sim.py

setup-tools:
	chmod +x tools/setup_env.sh
	bash tools/setup_env.sh

# =============================================================================
# RP2040 Coprocessor (Board B / ADR-015)
# =============================================================================

RP2040_DIR = firmware/rp2040
RP2040_TX_PORT ?= /dev/ttyUSB0
RP2040_RX_PORT ?= /dev/ttyACM0

.PHONY: rp2040-build rp2040-flash rp2040-monitor rp2040-test rp2040-clean rp2040-sim

rp2040-build:
	@echo "Building RP2040 coprocessor firmware..."
	cd $(RP2040_DIR) && pio run -e rp2040

rp2040-flash: rp2040-build
	@echo "Flashing RP2040 (hold BOOT while connecting USB)..."
	cd $(RP2040_DIR) && pio run -e rp2040 -t upload

rp2040-monitor:
	cd $(RP2040_DIR) && pio device monitor -p $(RP2040_RX_PORT) -b 115200

rp2040-test:
	@echo "Running hardware speed test (TX=$(RP2040_TX_PORT) RX=$(RP2040_RX_PORT))..."
	pytest tests/src/test_rp2040_speed.py -v -m hardware \
		--tx-port $(RP2040_TX_PORT) --rx-port $(RP2040_RX_PORT)

rp2040-sim:
	@echo "Running simulation tests (no hardware)..."
	pytest tests/src/test_rp2040_speed.py -v -k "simulate or sim or parsing or breakdown or dominant or loss or target or esp32"

rp2040-clean:
	rm -rf $(RP2040_DIR)/.pio
