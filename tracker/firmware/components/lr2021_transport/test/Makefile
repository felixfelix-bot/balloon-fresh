CXX = g++
CXXFLAGS = -std=c++17 -Wall -Wextra -g -I../include
LDFLAGS =

# MockLr2021Radio + Lr2021Transport are host-compilable (EspIdfLr2021Radio is
# guarded by __has_include and excluded when ESP-IDF headers are absent).
SRCS = test_lr2021.cpp \
       ../src/lr2021_spi.cpp \
       ../src/lr2021_framing.cpp \
       ../src/lr2021_transport.cpp

test: test_lr2021
	./test_lr2021

test_lr2021: $(SRCS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f test_lr2021

.PHONY: test clean
