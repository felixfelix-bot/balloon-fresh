# main component — minimal app_main that exercises tollgate_balloon_init().
# Note: the legacy extracted .c files in main/ (config.c, identity.c,
# nostr_event.c, geohash.c, mint_health.c) are NOT registered here. This
# skeleton is intentionally minimal — it proves the components link. The
# balloon firmware project (mesh-stack/firmware/) will register its own
# app_main + source list when it integrates these components.
idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
    REQUIRES tollgate_balloon
)
