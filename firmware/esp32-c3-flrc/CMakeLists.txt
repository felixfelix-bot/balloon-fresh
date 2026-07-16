# CMakeLists.txt for ESP32-C3 FLRC raw SPI throughput test
# Standalone ESP-IDF project
# Build: source ~/esp/esp-idf/export.sh && idf.py build
# Flash: idf.py -p /dev/ttyACM1 flash

cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

project(esp32-c3-flrc)
