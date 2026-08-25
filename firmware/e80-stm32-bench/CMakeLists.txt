cmake_minimum_required(VERSION 3.16)

project(e80_bench C ASM)

find_program(ARM_SIZE_UTIL arm-none-eabi-size REQUIRED)
find_program(ARM_OBJCOPY arm-none-eabi-objcopy REQUIRED)

# E80 bench firmware: STM32F103C8T6 host + LR2021 radio (vendored third_party).
set(TP ${CMAKE_CURRENT_SOURCE_DIR}/third_party)

add_executable(e80_bench
    # CMSIS device
    ${TP}/Drivers/CMSIS/Device/ST/STM32F1xx/Source/Templates/gcc/startup_stm32f103xb.s
    ${TP}/Drivers/CMSIS/Device/ST/STM32F1xx/Source/Templates/system_stm32f1xx.c
    # STM32 HAL - minimal module set (64K flash budget)
    ${TP}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal.c
    ${TP}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_cortex.c
    ${TP}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_rcc.c
    ${TP}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_rcc_ex.c
    ${TP}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_gpio.c
    ${TP}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_gpio_ex.c
    ${TP}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_spi.c
    ${TP}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_uart.c
    ${TP}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_dma.c
    ${TP}/Drivers/STM32F1xx_HAL_Driver/Src/stm32f1xx_hal_iwdg.c
    # LR2021 driver - only the engines the bench uses
    ${TP}/Radio/lr20xx_driver/src/lr20xx_system.c
    ${TP}/Radio/lr20xx_driver/src/lr20xx_regmem.c
    ${TP}/Radio/lr20xx_driver/src/lr20xx_radio_common.c
    ${TP}/Radio/lr20xx_driver/src/lr20xx_radio_lora.c
    ${TP}/Radio/lr20xx_driver/src/lr20xx_radio_flrc.c
    ${TP}/Radio/lr20xx_driver/src/lr20xx_radio_fifo.c
    ${TP}/Radio/lr20xx_driver/src/lr20xx_workarounds.c
    ${TP}/Radio/radio_hal/lr20xx_hal.c
    # Bench application
    src/bench.c
    src/stm32f1xx_it.c
    src/console.c
    src/buffer.c
    src/bench_cmd.c
    src/bench_stats.c
    src/bench_payload.c
    src/prbs.c
    src/bench_pkt.c
    src/bench_safety.c
    src/radio_bench.c
)

target_include_directories(e80_bench PRIVATE
    src
    ${TP}/Drivers/CMSIS/Include
    ${TP}/Drivers/CMSIS/Device/ST/STM32F1xx/Include
    ${TP}/Drivers/STM32F1xx_HAL_Driver/Inc
    ${TP}/Radio/lr20xx_driver/inc
    ${TP}/Radio/radio_hal
)

target_compile_definitions(e80_bench PRIVATE
    STM32F103xB
    USE_HAL_DRIVER
)

# Firmware identity (ID? fw=<sha7>). Preferred value comes from the
# convenience Makefile (-DFW_GIT_SHA=<sha7>); when configuring with bare
# CMake, query git here, and fall back to "unknown" outside a repo.
if(NOT DEFINED FW_GIT_SHA)
    execute_process(
        COMMAND git -C ${CMAKE_CURRENT_SOURCE_DIR} rev-parse --short=7 HEAD
        OUTPUT_VARIABLE FW_GIT_SHA
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
    if(NOT FW_GIT_SHA)
        set(FW_GIT_SHA "unknown")
    endif()
endif()
message(STATUS "FW_GIT_SHA=${FW_GIT_SHA}")
target_compile_definitions(e80_bench PRIVATE FW_GIT_SHA=${FW_GIT_SHA})

target_link_options(e80_bench PRIVATE
    -Wl,--gc-sections
    -Wl,-Map=${CMAKE_BINARY_DIR}/e80_bench.map
    -Wl,--print-memory-usage
    --specs=nano.specs
    --specs=nosys.specs
    -T${CMAKE_CURRENT_SOURCE_DIR}/ld/stm32f103c8.ld
)

# Generate .hex/.bin and print a size report vs the 64K/20K budget
add_custom_command(TARGET e80_bench POST_BUILD
    COMMAND ${ARM_SIZE_UTIL} $<TARGET_FILE:e80_bench>
    COMMAND ${ARM_OBJCOPY} -O ihex   $<TARGET_FILE:e80_bench> ${CMAKE_BINARY_DIR}/e80_bench.hex
    COMMAND ${ARM_OBJCOPY} -O binary $<TARGET_FILE:e80_bench> ${CMAKE_BINARY_DIR}/e80_bench.bin
    BYPRODUCTS ${CMAKE_BINARY_DIR}/e80_bench.hex ${CMAKE_BINARY_DIR}/e80_bench.bin
    COMMENT "size report + hex/bin generation"
)
