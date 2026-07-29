idf_component_register(
    SRCS "src/fips_radio_bridge.cpp"
    INCLUDE_DIRS "include"
    REQUIRES fips_transport lr2021_transport
)
