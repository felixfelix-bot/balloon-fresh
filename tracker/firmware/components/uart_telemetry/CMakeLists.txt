# ESP32-C3 <-> RP2040 UART telemetry protocol (card t_79ae3ee7).
#
# The portable core (uart_telemetry.c) has no target headers and is also the
# unit under test on the host (`test/Makefile`, run by host-tests.yml).
#
# The two target drivers are compiled only when their guard macro is defined by
# the consuming component; without it they are empty translation units, so a
# build that does not link the driver still gets the protocol core for free.
#   UART_TLM_C3_TARGET      -> uart_telemetry_c3.cpp     (ESP-IDF producer)
#   UART_TLM_RP2040_TARGET  -> uart_telemetry_rp2040.cpp (Pico/Arduino consumer)

idf_component_register(
    SRCS
        "uart_telemetry.c"
        "uart_telemetry_c3.cpp"
        "uart_telemetry_rp2040.cpp"
    INCLUDE_DIRS "include"
    REQUIRES
        driver esp_timer
    PRIV_REQUIRES
        gps bmp280 power_manager
)
