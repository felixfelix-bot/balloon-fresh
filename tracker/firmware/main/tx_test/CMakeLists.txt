# P1.1 — LR2021 TX test firmware (alternative main component).
#
# This is a self-contained main that exercises the LR2021 radio by transmitting
# numbered packets on command. It is NOT compiled by the default build — the
# parent main/CMakeLists.txt registers only ../app_main.cpp — so the two
# app_main() definitions never collide.
#
# To build this variant, point the build at this directory as the main
# component (e.g. swap these files into main/, or set MAIN/EXTRA_COMPONENT_DIRS
# accordingly). It reuses the proven ../EspHalC3.h HAL via INCLUDE_DIRS "..".

idf_component_register(
    SRCS "main.cpp"
    INCLUDE_DIRS "." ".."
    REQUIRES RadioLib esp_timer driver
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE
    RADIOLIB_DEBUG_BASIC=1
)
