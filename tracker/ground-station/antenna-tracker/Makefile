SHELL := /bin/bash

.PHONY: setup build flash monitor clean

setup:
	@echo "Loading environments..."
	@source $$HOME/esp/esp-idf/export.sh && \
	 source $$HOME/export-esp.sh && \
	 echo "Environment ready"

build:
	@source $$HOME/esp/esp-idf/export.sh && \
	 source $$HOME/export-esp.sh && \
	 cd antenna-firmware && \
	 cargo build

flash:
	@source $$HOME/esp/esp-idf/export.sh && \
	 source $$HOME/export-esp.sh && \
	 cd antenna-firmware && \
	 cargo run

monitor:
	@source $$HOME/esp/esp-idf/export.sh && \
	 source $$HOME/export-esp.sh && \
	 cd antenna-firmware && \
	 cargo monitor

clean:
	cd antenna-firmware && cargo clean
