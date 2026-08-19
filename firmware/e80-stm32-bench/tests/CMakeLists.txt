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
add_bench_test(test_bench_payload ${SRC_DIR}/bench_payload.c)
add_bench_test(test_bench_seq ${SRC_DIR}/bench_payload.c)  # tests payload stamping
target_include_directories(test_bench_seq PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/stubs)
add_bench_test(test_bench_safety ${SRC_DIR}/bench_safety.c)
add_bench_test(test_bench_flash ${SRC_DIR}/bench_cmd.c ${SRC_DIR}/bench_safety.c)
add_bench_test(test_bench_config)
target_include_directories(test_bench_config PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/stubs)
add_bench_test(test_console)  # includes console.c directly via #include — needs HAL stubs
target_include_directories(test_console PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/stubs)

# Banner test: only needs the bench_banner.h header from SRC_DIR.
add_bench_test(test_bench_banner)
