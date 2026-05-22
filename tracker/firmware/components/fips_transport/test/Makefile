CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -g \
           -I../include \
           -I../../micro_ecc/include \
           -I../../crypto/include \
           -I../../../main \
           -I../../pipeline/include \
           -I../../erasure/include \
           -I../../frag/include
LDFLAGS = -lmbedtls -lmbedcrypto -lmbedx509

SRCS = test_fips.cpp \
       ../fips_transport.cpp \
       ../../micro_ecc/uECC.c

INTEG_SRCS = test_fips_pipeline.cpp \
             ../fips_transport.cpp \
             ../../micro_ecc/uECC.c \
             ../../pipeline/pipeline.c \
             ../../erasure/erasure.c \
             ../../frag/frag.c

test: test_fips test_fips_pipeline
	./test_fips
	./test_fips_pipeline

test_fips: $(SRCS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

test_fips_pipeline: $(INTEG_SRCS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f test_fips test_fips_pipeline

.PHONY: test clean
