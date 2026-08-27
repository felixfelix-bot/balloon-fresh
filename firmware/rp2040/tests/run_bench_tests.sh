#!/bin/sh
# Host build + run of the RP2040BENCH console unit tests (HARM-T5).
#
# Compiles every test in tests/ against the vendored bench modules plus the
# console core (src/bench/) and runs each binary. Exit 0 iff all tests pass.
#
# Usage: sh tests/run_bench_tests.sh [from anywhere — paths are script-relative]
set -u

cd "$(dirname "$0")/.." || exit 1
BUILD=build/host-bench
mkdir -p "$BUILD"

CC=${CC:-gcc}
CFLAGS="-std=c11 -Wall -Wextra -O1 -Isrc/bench"

SRC="src/bench/bench_cmd.c \
     src/bench/bench_payload.c \
     src/bench/bench_pkt.c \
     src/bench/bench_stats.c \
     src/bench/buffer.c \
     src/bench/prbs.c \
     src/bench/rp2040_bench.c"

TESTS="test_crc16 test_prbs test_bench_pkt test_bench_stats test_rp2040_bench"

rc=0
for t in $TESTS; do
    if ! $CC $CFLAGS -o "$BUILD/$t" "tests/$t.c" $SRC 2> "$BUILD/$t.builderr"; then
        echo "$t: BUILD FAIL"
        cat "$BUILD/$t.builderr"
        rc=1
        continue
    fi
    if [ -s "$BUILD/$t.builderr" ]; then
        echo "$t: build warnings"
        cat "$BUILD/$t.builderr"
    fi
    "./$BUILD/$t" || rc=1
done

if [ "$rc" -eq 0 ]; then
    echo "bench tests: ALL PASS"
else
    echo "bench tests: FAILURES PRESENT"
fi
exit $rc
