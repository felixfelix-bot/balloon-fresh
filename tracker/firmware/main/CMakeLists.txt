set(COMPONENT_REQUIRES
    RadioLib esp_timer driver bmp280 power_manager telemetry
    antenna_switch sky66112 gps cli
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

if(CONFIG_ENABLE_MESHCORE)
    list(APPEND COMPONENT_REQUIRES meshcore)
    message(STATUS "MeshCore enabled, adding meshcore to REQUIRES")
endif()

idf_component_register(
    SRCS "app_main.cpp"
    INCLUDE_DIRS "."
    REQUIRES ${COMPONENT_REQUIRES}
    PRIV_REQUIRES meshcore
)

target_compile_definitions(${COMPONENT_LIB} PRIVATE
    RADIOLIB_DEBUG_SPI=1
    RADIOLIB_DEBUG_BASIC=1
)
