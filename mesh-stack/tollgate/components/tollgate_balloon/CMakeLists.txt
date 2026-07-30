idf_component_register(SRCS "src/tollgate_balloon.c"
                            "src/tollgate_payment_proto.c"
                    INCLUDE_DIRS "include" ".."
                     REQUIRES tollgate_core nucula_lib json lwip esp_event mesh_service_mux)
