# CMakeLists.txt — C1 Radio Validation test app (standalone ESP-IDF project)
#
# Builds independently of the main tracker firmware.
# References the lr2021_transport component via EXTRA_COMPONENT_DIRS.
#
# Build:
#   source ~/esp/esp-idf/export.sh
#   cd tracker/firmware/radio_test
#   idf.py set-target esp32c3
#   idf.py build

cmake_minimum_required(VERSION 3.16)

# Pull lr2021_transport (and sibling components) from the tracker tree
set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../components")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

project(radio_test)
