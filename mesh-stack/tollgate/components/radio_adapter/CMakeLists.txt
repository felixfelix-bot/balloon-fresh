# radio_adapter component — bridges mesh_service_mux → lr2021_transport
#
# Enables tollgate mesh packets over LR2021 FLRC radio.

idf_component_register(
    SRCS "src/radio_adapter.cpp"
    INCLUDE_DIRS "include"
    REQUIRES mesh_service_mux
    PRIV_REQUIRES lr2021_transport tollgate_balloon
)
