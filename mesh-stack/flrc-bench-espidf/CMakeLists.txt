set(CMAKE_SYSTEM_NAME Generic)

set(CMAKE_C_COMPILER riscv32-esp-elf-gcc)
set(CMAKE_CXX_COMPILER riscv32-esp-g++)

cmake_minimum_required(VERSION 3.16)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(flrc-bench-espidf)
