if(CONFIG_ENABLE_MESH_RADIO)
    # ── Mesh radio test app: minimal deps, no RadioLib ──
    set(MAIN_SRCS "mesh_radio_main.c")
    set(COMPONENT_REQUIRES esp_timer driver lr2021_radio mesh_adapter pipeline erasure frag)
    message(STATUS "Mesh radio app enabled: building mesh_radio_main.c (not app_main.cpp)")
else()
    # ── Default tracker app ──
    set(MAIN_SRCS "app_main.cpp")
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
endif()

idf_component_register(
    SRCS ${MAIN_SRCS}
    INCLUDE_DIRS "."
    REQUIRES ${COMPONENT_REQUIRES}
    PRIV_REQUIRES meshcore
)

if(NOT CONFIG_ENABLE_MESH_RADIO)
target_compile_definitions(${COMPONENT_LIB} PRIVATE
    RADIOLIB_DEBUG_SPI=1
    RADIOLIB_DEBUG_BASIC=1
)
endif()
