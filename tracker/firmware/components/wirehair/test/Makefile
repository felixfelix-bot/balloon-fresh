CXX = g++
CXXFLAGS = -std=c++17 -O2 -mssse3 -Wall -I../include -I..
LDFLAGS =

SRCS = bench_wirehair.cpp \
       ../wirehair.cpp \
       ../WirehairCodec.cpp \
       ../WirehairTools.cpp \
       ../gf256.cpp

bench: bench_wirehair
	./bench_wirehair

bench_wirehair: $(SRCS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f bench_wirehair

.PHONY: bench clean
