# cmake/pico-sdk build for the RP2040 coprocessor firmware (SPEED-P6).
#
# Canonical pico-sdk build of the PIO+DMA gapless RX engine. PlatformIO
# (platformio.ini) remains the build for the full mbed-Arduino firmware
# (radio.cpp + main.cpp); this CMake target is the framework-agnostic path
# that assembles the .pio with pioasm and links the driver against pico-sdk.
#
#   cd firmware/rp2040
#   mkdir build && cd build
#   cmake -DPICO_SDK_PATH=<path-to-pico-sdk> ..
#   make -j$(nproc)
#   # -> pio_rx_smoketest.uf2
#
# pico_generate_pio_header() runs pioasm on src/pio_lr2021_rx.pio to emit
# pio_lr2021_rx.pio.h. A pre-generated copy is committed in src/ for builds
# that cannot run pioasm (the mbed Arduino core); its encodings are identical
# and were verified against pico-sdk's own pio_instructions.h encoder.

cmake_minimum_required(VERSION 3.13)

# Pull in the pico-sdk boilerplate. Define PICO_SDK_PATH either as an env var,
# a -D flag, or via pico-sdk's import() mechanism.
include(pico_sdk_import.cmake OPTIONAL)

project(pio_rx_smoketest C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(pio_rx_smoketest
    src/pico_sdk_main.cpp
    src/pio_lr2021_rx.cpp
)

# Assemble the PIO program -> pio_lr2021_rx.pio.h (pioasm, bundled by the SDK).
pico_generate_pio_header(pio_rx_smoketest
    ${CMAKE_CURRENT_LIST_DIR}/src/pio_lr2021_rx.pio)

target_include_directories(pio_rx_smoketest PRIVATE src)

target_link_libraries(pio_rx_smoketest
    pico_stdlib
    hardware_pio
    hardware_dma
    hardware_irq
    hardware_gpio
)

pico_enable_stdio_usb(pio_rx_smoketest 1)
pico_add_extra_outputs(pio_rx_smoketest)   # .uf2 / .elf / .map / .dis
