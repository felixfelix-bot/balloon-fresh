# tollgate_core — balloon-relevant payment business logic only.
# Stripped from source: mining, stratum, market, dns, client modules.
# See EXTRACTION-LOG.md for details.
idf_component_register(
    SRCS "src/tollgate_core.c"
         "src/tollgate_core_cashu.c"
         "src/tollgate_core_firewall.c"
         "src/tollgate_core_session.c"
         "src/tollgate_core_beacon.c"
         "src/tollgate_core_portal.c"
         "src/tollgate_core_mint_health.c"
    INCLUDE_DIRS "include" "src"
    REQUIRES lwip json esp_http_client mbedtls log esp_netif
    PRIV_REQUIRES esp_wifi)
