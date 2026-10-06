# Makefile for host unit tests — mesh-stack tollgate (ADR-024 migration)
# Adapted from tollgate-esp32/tests/unit/Makefile

REPO_ROOT := ../..
MAIN_DIR  := $(REPO_ROOT)/main

SECP256K1_SRC := $(REPO_ROOT)/components/secp256k1/libsecp256k1
SECP256K1_INC := $(SECP256K1_SRC)/include
SECP256K1_PRIV_INC := $(SECP256K1_SRC)/src
SECP256K1_CFG := $(REPO_ROOT)/components/secp256k1

TG_CORE_SRC := $(REPO_ROOT)/components/tollgate_core/src
TG_CORE_INC := $(REPO_ROOT)/components/tollgate_core/include

TG_BALLOON_SRC := $(REPO_ROOT)/components/tollgate_balloon/src
TG_BALLOON_INC := $(REPO_ROOT)/components/tollgate_balloon/include

TG_CLIENT_SRC := $(REPO_ROOT)/components/tollgate_client/src
TG_CLIENT_INC := $(REPO_ROOT)/components/tollgate_client/include

MUX_SRC := $(REPO_ROOT)/components/mesh_service_mux/src
MUX_INC := $(REPO_ROOT)/components/mesh_service_mux/include

CC := gcc
CFLAGS := -Wall -Wextra -Wno-unused-parameter -Wno-unused-function -Wno-sign-compare \
          -std=gnu17 -g -O0 \
          -DTEST_HOST \
          -DENABLE_MODULE_SCHNORRSIG=1 -DENABLE_MODULE_EXTRAKEYS=1 \
          -DENABLE_MODULE_ECDH=1 \
          -DECMULT_WINDOW_SIZE=8 -DECMULT_GEN_PREC_BITS=4 \
          -include stubs/esp_err.h \
          -I stubs \
          -I $(MAIN_DIR) \
          -I $(SECP256K1_INC) \
          -I $(SECP256K1_CFG) \
          -I /usr/include/cjson \
          -I $(TG_CORE_SRC) \
          -I $(TG_CORE_INC)

LDFLAGS := -lmbedcrypto -lcjson -lm

SECP256K1_OBJ := secp256k1.o precomputed_ecmult.o precomputed_ecmult_gen.o

# Stubs that most tollgate_core compilations need
TG_CORE_OBJS_CFLAGS := -include stubs/mint_health.h -include stubs/esp_netif.h \
                       -include stubs/esp_log.h -include stubs/esp_http_client.h \
                       -include stubs/esp_crt_bundle.h

# Available tollgate_core sources for the full-suite build
TG_CORE_FULL_SRCS := $(TG_CORE_SRC)/tollgate_core_cashu.c \
                     $(TG_CORE_SRC)/tollgate_core_session.c \
                     $(TG_CORE_SRC)/tollgate_core_firewall.c \
                     $(TG_CORE_SRC)/tollgate_core.c

# Tests we ship in this tree
TESTS := test_geohash test_identity test_nostr_event test_cashu test_session \
         test_firewall_sandbox test_beacon test_mint_health test_mint_health_core \
         test_portal test_payment_proto \
         test_mesh_service_mux test_tollgate_mesh_integration \
         test_tollgate_client

.PHONY: all test clean $(TESTS)

all: test

test: $(TESTS)
	@echo ""
	@echo "=== Running all unit tests ==="
	@failed=0; \
	passed=0; \
	for t in $(TESTS); do \
		echo ""; \
		echo "--- $$t ---"; \
		if ./$$t; then passed=$$((passed + 1)); else failed=$$((failed + 1)); fi; \
	done; \
	echo ""; \
	echo "=== $$passed passed, $$failed failed ==="; \
	if [ $$failed -eq 0 ]; then \
		echo "=== ALL UNIT TESTS PASSED ==="; \
	else \
		echo "=== $$failed test(s) FAILED ==="; \
		exit 1; \
	fi

$(SECP256K1_OBJ): %.o: $(SECP256K1_SRC)/src/%.c
	$(CC) $(CFLAGS) -I $(SECP256K1_PRIV_INC) -c $< -o $@

# --- Pure main/ tests ---

test_geohash: test_geohash.c $(MAIN_DIR)/geohash.c
	$(CC) $(CFLAGS) $^ -o $@ $(LDFLAGS)

test_identity: test_identity.c $(MAIN_DIR)/identity.c $(SECP256K1_OBJ)
	$(CC) $(CFLAGS) -I $(SECP256K1_PRIV_INC) $< $(MAIN_DIR)/identity.c $(SECP256K1_OBJ) -o $@ $(LDFLAGS)

test_nostr_event: test_nostr_event.c $(MAIN_DIR)/nostr_event.c $(MAIN_DIR)/identity.c $(SECP256K1_OBJ)
	$(CC) $(CFLAGS) -I $(SECP256K1_PRIV_INC) $< $(MAIN_DIR)/nostr_event.c $(MAIN_DIR)/identity.c $(SECP256K1_OBJ) -o $@ $(LDFLAGS)

# --- tollgate_core tests (full src suite) ---

test_cashu: test_cashu.c $(TG_CORE_FULL_SRCS)
	$(CC) $(CFLAGS) $(TG_CORE_OBJS_CFLAGS) $^ -o $@ $(LDFLAGS)

test_session: test_session.c $(TG_CORE_FULL_SRCS)
	$(CC) $(CFLAGS) $(TG_CORE_OBJS_CFLAGS) $^ -o $@ $(LDFLAGS)

test_firewall_sandbox: test_firewall_sandbox.c $(TG_CORE_FULL_SRCS)
	$(CC) $(CFLAGS) -include stubs/dns_server.h $(TG_CORE_OBJS_CFLAGS) $^ -o $@ $(LDFLAGS)

# --- tollgate_core single-module tests ---

test_beacon: test_beacon.c $(TG_CORE_SRC)/tollgate_core_beacon.c
	$(CC) $(CFLAGS) $(TG_CORE_OBJS_CFLAGS) $^ -o $@ $(LDFLAGS)

# For test_mint_health we compile the real main/mint_health.c, so the real
# main/mint_health.h must be found BEFORE stubs/mint_health.h.  Reorder -I paths.
MINT_HEALTH_CFLAGS := -Wall -Wextra -Wno-unused-parameter -Wno-unused-function \
	-Wno-sign-compare -std=gnu17 -g -O0 -DTEST_HOST \
	-include stubs/esp_err.h \
	-I $(MAIN_DIR) -I stubs \
	-I $(SECP256K1_INC) -I $(SECP256K1_CFG) \
	-I /usr/include/cjson -I $(TG_CORE_SRC) -I $(TG_CORE_INC)

test_mint_health: test_mint_health.c $(MAIN_DIR)/mint_health.c $(TG_CORE_SRC)/tollgate_core_mint_health.c
	$(CC) $(MINT_HEALTH_CFLAGS) $^ -o $@ $(LDFLAGS)

test_mint_health_core: test_mint_health_core.c $(TG_CORE_SRC)/tollgate_core_mint_health.c
	$(CC) $(CFLAGS) $^ -o $@ $(LDFLAGS)

test_portal: test_portal.c $(TG_CORE_SRC)/tollgate_core_portal.c $(TG_CORE_SRC)/tollgate_core_session.c $(TG_CORE_SRC)/tollgate_core_firewall.c
	$(CC) $(CFLAGS) $(TG_CORE_OBJS_CFLAGS) $^ -o $@ $(LDFLAGS)

# --- tollgate_balloon payment protocol test ---

test_payment_proto: test_payment_proto.c $(TG_BALLOON_SRC)/tollgate_payment_proto.c
	$(CC) $(CFLAGS) -I $(TG_BALLOON_INC) $^ -o $@ $(LDFLAGS)

# --- tollgate_client state machine (client + payment proto) ---

test_tollgate_client: test_tollgate_client.c \
	$(TG_CLIENT_SRC)/tollgate_client.c \
	$(TG_BALLOON_SRC)/tollgate_payment_proto.c
	$(CC) $(CFLAGS) -I $(TG_CLIENT_INC) -I $(TG_BALLOON_INC) $^ -o $@ $(LDFLAGS)

# --- mesh_service_mux unit tests ---

test_mesh_service_mux: test_mesh_service_mux.c $(MUX_SRC)/mesh_service_mux.c
	$(CC) $(CFLAGS) -I $(MUX_INC) $^ -o $@ $(LDFLAGS)

# --- tollgate_balloon mesh integration (mux + balloon + mock transport) ---

test_tollgate_mesh_integration: test_tollgate_mesh_integration.c \
	$(TG_BALLOON_SRC)/tollgate_balloon.c \
	$(TG_BALLOON_SRC)/tollgate_payment_proto.c \
	$(MUX_SRC)/mesh_service_mux.c \
	stubs/nucula_wallet_stub.c
	$(CC) $(CFLAGS) -I $(TG_BALLOON_INC) -I $(MUX_INC) \
	-include stubs/esp_log.h $^ -o $@ $(LDFLAGS)

clean:
	rm -f $(TESTS) $(SECP256K1_OBJ)
