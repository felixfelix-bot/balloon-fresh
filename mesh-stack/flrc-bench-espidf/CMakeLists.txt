set(CMAKE_SYSTEM_NAME Generic)

set(CMAKE_C_COMPILER riscv32-esp-elf-gcc)
set(CMAKE_CXX_COMPILER riscv32-esp-g++)

cmake_minimum_required(VERSION 3.16)

# --- FW git hash injection ---
# Capture the short git SHA at configure time and expose it as FW_GIT_SHA
# to all compilation units via add_compile_definitions.
execute_process(
    COMMAND git rev-parse --short HEAD
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
    OUTPUT_VARIABLE FW_GIT_SHA
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
)
if(NOT FW_GIT_SHA)
    set(FW_GIT_SHA "unknown")
endif()
message(STATUS "FW_GIT_SHA = ${FW_GIT_SHA}")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(flrc-bench-espidf)

# Apply the definition after project() so the ESP-IDF toolchain is ready.
add_compile_definitions(FW_GIT_SHA="${FW_GIT_SHA}")
