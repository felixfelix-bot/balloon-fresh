# radio_adapter — bridges mesh_service_mux ↔ lr2021_transport.
#
# C++ component: provides concrete send/recv callbacks backed by the
# physical LR2021 FLRC radio, connecting the abstract mesh layer to
# the SPI transport.
#
# lr2021_transport and mesh_adapter live in tracker/firmware/components/
# (added via EXTRA_COMPONENT_DIRS in the project root CMakeLists.txt).
idf_component_register(
    SRCS "radio_adapter.cpp"
    INCLUDE_DIRS "."
    REQUIRES lr2021_transport mesh_adapter mesh_service_mux tollgate_balloon
)
