cmake_minimum_required(VERSION 3.16)
project(e80_bench_host_tests C)

enable_testing()

# Host (PC gcc) unit tests for the portable bench logic.
# The portable sources have zero STM32 dependencies by design.

set(SRC_DIR ${CMAKE_CURRENT_SOURCE_DIR}/../src)

function(add_bench_test name)
    add_executable(${name} ${name}.c ${ARGN})
    target_include_directories(${name} PRIVATE ${SRC_DIR})
    add_test(NAME ${name} COMMAND ${name})
endfunction()

add_bench_test(test_bench_stats ${SRC_DIR}/bench_stats.c)
target_link_libraries(test_bench_stats m)
add_bench_test(test_bench_cmd ${SRC_DIR}/bench_cmd.c)
add_bench_test(test_bench_payload ${SRC_DIR}/bench_payload.c)
