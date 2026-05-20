# For more information about build system see
# https://docs.espressif.com/projects/esp-idf/en/latest/esp32c3/api-guides/build-system.html

cmake_minimum_required(VERSION 3.16)

set(EXTRA_COMPONENT_DIRS "components")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(balloon-tracker)
