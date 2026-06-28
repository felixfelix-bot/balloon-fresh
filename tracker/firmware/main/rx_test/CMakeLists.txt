# P1.2 ESP32 RX test firmware - top-level ESP-IDF project.
# RadioLib is pulled in automatically as a managed component via
# main/idf_component.yml (jgromes/RadioLib v7.6.0).
#
# Build / flash:
#   cd tracker/firmware/main/rx_test
#   idf.py build
#   idf.py -p /dev/ttyACM0 flash monitor
cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(rx_test)
