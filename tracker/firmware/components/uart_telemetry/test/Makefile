CC      ?= gcc
CFLAGS  ?= -std=c11 -Wall -Wextra -Werror -O2 -I../include

SRC = ../uart_telemetry.c
TESTS = test_uart_telemetry

build: $(TESTS)

test_uart_telemetry: test_uart_telemetry.c $(SRC)
	$(CC) $(CFLAGS) -o $@ test_uart_telemetry.c $(SRC)

test: build
	./test_uart_telemetry

clean:
	rm -f $(TESTS)

.PHONY: build test clean
