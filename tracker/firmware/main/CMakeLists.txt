set(COMPONENT_REQUIRES
    lr2021_transport esp_timer driver bmp280 power_manager telemetry
    antenna_switch sky66112 gps cli secp256k1
)

if(CONFIG_ENABLE_MESH)
    list(APPEND COMPONENT_REQUIRES pipeline erasure frag mesh_adapter)
endif()

if(CONFIG_ENABLE_TDMA)
    list(APPEND COMPONENT_REQUIRES tdma)
endif()

if(CONFIG_ENABLE_NOSTR_STORE)
    list(APPEND COMPONENT_REQUIRES nostr_store)
endif()

if(CONFIG_ENABLE_RELAY_MODE)
    list(APPEND COMPONENT_REQUIRES nostr_store secp256k1)
endif()

if(CONFIG_ENABLE_MESHCORE)
    list(APPEND COMPONENT_REQUIRES meshcore)
    message(STATUS "MeshCore enabled, adding meshcore to REQUIRES")
endif()

idf_component_register(
    SRCS "app_main.cpp" "radio_task.cpp" "app_task.cpp"
    INCLUDE_DIRS "."
    REQUIRES ${COMPONENT_REQUIRES}
    PRIV_REQUIRES meshcore mesh_adapter nostr_store secp256k1
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE
    LR2021_SPI_DEBUG=0
)
