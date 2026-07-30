idf_component_register(
    SRCS
        "src/lr2021_spi.cpp"
        "src/lr2021_framing.cpp"
        "src/lr2021_transport.cpp"
        "src/esp_idf_lr2021_radio.cpp"
    INCLUDE_DIRS "include"
    REQUIRES driver esp_timer
)
