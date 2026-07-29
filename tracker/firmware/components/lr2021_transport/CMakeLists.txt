idf_component_register(
    SRCS
        "src/lr2021_spi.cpp"
        "src/lr2021_framing.cpp"
        "src/lr2021_transport.cpp"
    INCLUDE_DIRS "include"
    REQUIRES driver
)
