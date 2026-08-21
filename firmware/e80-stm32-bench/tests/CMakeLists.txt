cmake_minimum_required(VERSION 3.16)
project(e80_bench_host_tests C)

enable_testing()

# Host (PC gcc) unit tests for the portable bench logic.
# The portable sources have zero STM32 dependencies by design.

set(SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../src)

# Host HAL stubs directory — any test that includes main.h needs these.
set(STUBS_DIR ${CMAKE_CURRENT_SOURCE_DIR}/stubs)

function(add_bench_test name)
    add_executable(${name} ${name}.c ${ARGN})
    target_include_directories(${name} PRIVATE ${SRC_DIR} ${STUBS_DIR})
    add_test(NAME ${name} COMMAND ${name})
endfunction()

add_bench_test(test_bench_stats ${SRC_DIR}/bench_stats.c)
target_link_libraries(test_bench_stats m)
add_bench_test(test_bench_cmd ${SRC_DIR}/bench_cmd.c)
# radio_bench.h pulls in lr20xx driver headers — provide those include dirs.
target_include_directories(test_bench_cmd PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/Radio/lr20xx_driver/inc
    ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/Radio/radio_hal)
add_bench_test(test_bench_payload ${SRC_DIR}/bench_payload.c ${SRC_DIR}/prbs.c)
add_bench_test(test_bench_seq ${SRC_DIR}/bench_payload.c ${SRC_DIR}/prbs.c)  # tests payload stamping
target_include_directories(test_bench_seq PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/stubs)
add_bench_test(test_bench_safety ${SRC_DIR}/bench_safety.c)
add_bench_test(test_bench_flash ${SRC_DIR}/bench_cmd.c ${SRC_DIR}/bench_safety.c)
add_bench_test(test_bench_config)
target_include_directories(test_bench_config PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/stubs)
add_bench_test(test_console ${SRC_DIR}/buffer.c)  # includes console.c directly via #include — needs HAL stubs; buffer.c since BUF-T2 (console binary phase calls buf_*)
target_include_directories(test_console PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/stubs)

add_bench_test(test_bench_pkt ${SRC_DIR}/bench_pkt.c)

# CONFIG_START transition marker test (E80-8/O4): portable, no STM32 deps.
add_bench_test(test_bench_config_start ${SRC_DIR}/bench_pkt.c)

# Radio bench cfg test (FIX-T3): host-compiles the REAL src/radio_bench.c
# against the REAL vendored lr20xx_driver sources; the test file provides a
# fake capturing lr20xx HAL. Pins the exact FLRC SetPacketParams bytes.
set(LR20XX_DRIVER_SRC ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/Radio/lr20xx_driver/src)
add_bench_test(test_radio_bench_cfg
    ${SRC_DIR}/radio_bench.c
    ${LR20XX_DRIVER_SRC}/lr20xx_radio_flrc.c
    ${LR20XX_DRIVER_SRC}/lr20xx_radio_common.c
    ${LR20XX_DRIVER_SRC}/lr20xx_radio_lora.c
    ${LR20XX_DRIVER_SRC}/lr20xx_radio_fifo.c
    ${LR20XX_DRIVER_SRC}/lr20xx_system.c
    ${LR20XX_DRIVER_SRC}/lr20xx_regmem.c
    ${LR20XX_DRIVER_SRC}/lr20xx_workarounds.c)
target_include_directories(test_radio_bench_cfg PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/Radio/lr20xx_driver/inc
    ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/Radio/radio_hal)

# Banner test: only needs the bench_banner.h header from SRC_DIR.
add_bench_test(test_bench_banner)

# PRBS15 fill/verify tests (TDD).
add_bench_test(test_prbs ${SRC_DIR}/prbs.c)

# PRBS-15 wiring tests: TX fill, RX verify, CRC-failed, CONFIG PRBS ON/OFF.
add_bench_test(test_prbs_wiring ${SRC_DIR}/bench_payload.c ${SRC_DIR}/prbs.c ${SRC_DIR}/bench_cmd.c ${SRC_DIR}/bench_pkt.c)
target_include_directories(test_prbs_wiring PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/Radio/lr20xx_driver/inc
    ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/Radio/radio_hal)

# PRBS9 hardware TX test mode command tests (TDD).
add_bench_test(test_bench_prbs9 ${SRC_DIR}/bench_cmd.c)
target_include_directories(test_bench_prbs9 PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/Radio/lr20xx_driver/inc
    ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/Radio/radio_hal)

# ---- TX payload buffer (task BUF-T1, TDD): parser surface + buffer module ----
add_bench_test(test_buf_cmd ${SRC_DIR}/bench_cmd.c)
target_include_directories(test_buf_cmd PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/Radio/lr20xx_driver/inc
    ${CMAKE_CURRENT_SOURCE_DIR}/../third_party/Radio/radio_hal)

add_bench_test(test_buffer ${SRC_DIR}/buffer.c)

# Console binary receive framing: real console.c over an injected UART
# (stubs/host_uart.h: RX byte injection + TX transcript capture).
add_bench_test(test_console_binary ${SRC_DIR}/buffer.c)
target_include_directories(test_console_binary PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/stubs)

# Golden CRC vectors shared C <-> Python (tx-buffer-spec): the Python side
# must agree with tests/test_buffer.c bit-for-bit.
find_program(HOST_PYTHON3 NAMES python3)
if(HOST_PYTHON3)
    add_test(NAME test_crc16_golden_python
             COMMAND ${HOST_PYTHON3} ${CMAKE_CURRENT_SOURCE_DIR}/../tools/test_crc16_golden.py)
    # Sweep tool: START-reply fail-fast validation + LEN caps (task FIX-T1).
    add_test(NAME test_e80_sweep_full_python
             COMMAND ${HOST_PYTHON3} ${CMAKE_CURRENT_SOURCE_DIR}/../tools/test_e80_sweep_full.py)
endif()