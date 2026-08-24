# mesh-stack/ehash-relay/CMakeLists.txt
#
# ESP-IDF component for the balloon-side e-hash relay module (Phase C).
# Builds as part of the tracker/mesh firmware when included in the
# project's components/ directory or referenced via EXTRA_COMPONENT_DIRS.
#
# Host unit tests compile separately with gcc (see test/README or
# the project Makefile/test script).

idf_component_register(
    SRCS
        "ehash_relay.c"
        "ehash_crypto.c"
        "ehash_upstream.c"
        "ehash_radio_stub.c"
    INCLUDE_DIRS
        "include"
        # Protocol header with packed structs is in mesh-stack/protocol/
        # Adjust this path relative to where the component is placed.
        "../protocol"
)
