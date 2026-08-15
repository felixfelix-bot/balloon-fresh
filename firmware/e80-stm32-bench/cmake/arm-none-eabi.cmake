# CMake toolchain file for the E80 bench firmware (bare-metal Cortex-M3).
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(TOOLCHAIN_PREFIX arm-none-eabi)

find_program(ARM_GCC ${TOOLCHAIN_PREFIX}-gcc REQUIRED)
find_program(ARM_GCC_AR ${TOOLCHAIN_PREFIX}-gcc-ar)
if(NOT ARM_GCC_AR)
    set(ARM_GCC_AR ${TOOLCHAIN_PREFIX}-ar)
endif()

set(CMAKE_C_COMPILER ${ARM_GCC})
set(CMAKE_ASM_COMPILER ${ARM_GCC})
set(CMAKE_C_COMPILER_WORKS 1)
set(CMAKE_ASM_COMPILER_WORKS 1)

set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

set(ARM_FLAGS "-mcpu=cortex-m3 -mthumb")

set(CMAKE_C_FLAGS "${ARM_FLAGS} -std=gnu11 -Wall -Wextra -Wno-unused-parameter -ffunction-sections -fdata-sections -fno-common -fno-builtin" CACHE STRING "" FORCE)
set(CMAKE_ASM_FLAGS "${ARM_FLAGS} -x assembler-with-cpp" CACHE STRING "" FORCE)
set(CMAKE_EXE_LINKER_FLAGS "${ARM_FLAGS} -Wl,--gc-sections -Wl,-Map=${CMAKE_BINARY_DIR}/e80_bench.map -Wl,--print-memory-usage -Wl,--start-group -lc -lm -Wl,--end-group" CACHE STRING "" FORCE)

set(CMAKE_C_FLAGS_DEBUG "-Og -g3" CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS_RELEASE "-Os -g" CACHE STRING "" FORCE)

set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
