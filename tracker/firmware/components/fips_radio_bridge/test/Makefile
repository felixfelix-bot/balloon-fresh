CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -g -pthread \
           -I../include \
           -I../../fips_transport/include \
           -I../../lr2021_transport/include \
           -I../../micro_ecc/include
LDFLAGS = -pthread -lmbedtls -lmbedcrypto -lmbedx509

# Shared sources for both test binaries
SHARED_SRCS = ../src/fips_radio_bridge.cpp \
       ../../fips_transport/fips_transport.cpp \
       ../../micro_ecc/uECC.c \
       ../../lr2021_transport/src/lr2021_spi.cpp \
       ../../lr2021_transport/src/lr2021_framing.cpp \
       ../../lr2021_transport/src/lr2021_transport.cpp

# Build both test binaries
build: test_fips_radio_bridge test_fips_fragmented

# Build + run all tests
test: build
	./test_fips_radio_bridge
	./test_fips_fragmented

# Phase 1: FIPS Noise IK handshake over LR2021
test_fips_radio_bridge: test_fips_radio_bridge.cpp $(SHARED_SRCS)
	$(CXX) $(CXXFLAGS) -o $@ test_fips_radio_bridge.cpp $(SHARED_SRCS) $(LDFLAGS)

# Phase 3: Encrypted multi-frame transport over LR2021
test_fips_fragmented: test_fips_fragmented.cpp $(SHARED_SRCS)
	$(CXX) $(CXXFLAGS) -o $@ test_fips_fragmented.cpp $(SHARED_SRCS) $(LDFLAGS)

clean:
	rm -f test_fips_radio_bridge test_fips_fragmented

.PHONY: build test clean
