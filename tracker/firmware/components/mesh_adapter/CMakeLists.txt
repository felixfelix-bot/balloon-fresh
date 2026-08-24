idf_component_register(
    SRCS "mesh_adapter.c"
    INCLUDE_DIRS "include"
    REQUIRES pipeline
    PRIV_REQUIRES erasure frag
)
