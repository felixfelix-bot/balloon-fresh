idf_component_register(SRCS "app_main.cpp"
                       INCLUDE_DIRS "."
                       REQUIRES RadioLib esp_timer driver bmp280 power_manager telemetry antenna_switch sky66112)
