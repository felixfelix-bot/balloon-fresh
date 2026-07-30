# ESP-IDF project for BMP280 balloon pressure test rig
# Requires ESP-IDF v5.0+
cmake_minimum_required(VERSION 3.16)

set(EXTRA_COMPONENT_DIRS "")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

project(balloon_pressure_test)