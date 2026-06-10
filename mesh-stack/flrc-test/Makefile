# FLRC Throughput Benchmark Makefile
# NiceRF LR2021 + ESP32-C3 SuperMini

PORT1 ?= /dev/ttyACM2
PORT2 ?= /dev/ttyACM3

.PHONY: all setup build-all clean flash-tx flash-rx flash-tx-24 flash-rx-24 flash-lora-tx flash-lora-rx

all: build-all

setup:
	bash setup.sh

build-all:
	pio run -e flrc_tx -e flrc_rx -e flrc_tx_24 -e flrc_rx_24 -e lora_tx -e lora_rx

build-tx:
	pio run -e flrc_tx

build-rx:
	pio run -e flrc_rx

build-tx-24:
	pio run -e flrc_tx_24

build-rx-24:
	pio run -e flrc_rx_24

build-lora-tx:
	pio run -e lora_tx

build-lora-rx:
	pio run -e lora_rx

flash-tx: build-tx
	pio run -e flrc_tx -t upload --upload-port $(PORT1)

flash-rx: build-rx
	pio run -e flrc_rx -t upload --upload-port $(PORT2)

flash-tx-24: build-tx-24
	pio run -e flrc_tx_24 -t upload --upload-port $(PORT1)

flash-rx-24: build-rx-24
	pio run -e flrc_rx_24 -t upload --upload-port $(PORT2)

flash-lora-tx: build-lora-tx
	pio run -e lora_tx -t upload --upload-port $(PORT1)

flash-lora-rx: build-lora-rx
	pio run -e lora_rx -t upload --upload-port $(PORT2)

monitor1:
	pio device monitor -p $(PORT1) -b 115200

monitor2:
	pio device monitor -p $(PORT2) -b 115200

clean:
	pio run -t clean
