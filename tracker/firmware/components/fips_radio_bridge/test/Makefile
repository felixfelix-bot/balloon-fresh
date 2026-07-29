CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -g -pthread \
           -I../include \
           -I../../fips_transport/include \
           -I../../lr2021_transport/include \
           -I../../micro_ecc/include
LDFLAGS = -pthread -lmbedtls -lmbedcrypto -lmbedx509

SRCS = test_fips_radio_bridge.cpp \
       ../src/fips_radio_bridge.cpp \
       ../../fips_transport/fips_transport.cpp \
       ../../micro_ecc/uECC.c \
       ../../lr2021_transport/src/lr2021_spi.cpp \
       ../../lr2021_transport/src/lr2021_framing.cpp \
       ../../lr2021_transport/src/lr2021_transport.cpp

# Default: just build the test binary
build: test_fips_radio_bridge

# Build + run
test: build
	./test_fips_radio_bridge

test_fips_radio_bridge: $(SRCS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f test_fips_radio_bridge

.PHONY: build test clean
