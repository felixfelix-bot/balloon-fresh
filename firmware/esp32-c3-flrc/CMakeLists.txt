# CMakeLists.txt for ESP32-C3 FLRC raw SPI throughput test
# Standalone ESP-IDF project
# Build: source ~/esp/esp-idf/export.sh && idf.py build
# Flash: idf.py -p /dev/ttyACM1 flash

cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

# ─── Build flags (pass via idf.py -D<flag>=<value>) ──────────────────
# CONTINUOUS_TX=1   Enable infinite TX loop for LA benchmark
# TX_PKT_SIZE=<N>   Override TX payload size (default 255, for sweep)
option(CONTINUOUS_TX "Enable continuous (infinite) TX mode" OFF)
set(TX_PKT_SIZE "" CACHE STRING "TX payload size in bytes (default 255)")

project(esp32-c3-flrc)
