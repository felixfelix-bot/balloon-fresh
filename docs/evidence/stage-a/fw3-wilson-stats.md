# FW-3: Wilson stats module + host tests — Evidence

## Task
Kanban `t_1e40230c` — FW-3: Wilson stats module + host tests

## Deliverables
- `firmware/rp2040/src/flrc_range_host_stats.h` — C++ port of E80 bench_stats.h
- `firmware/rp2040/src/flrc_range_host_stats.cpp` — verbatim integer port of E80 bench_stats.c
- `firmware/rp2040/host-tests/Makefile` — g++ pattern rule for host-side unit tests
- `firmware/rp2040/host-tests/test_stats.cpp` — ported E80 test vectors + FW-3 boundary cases

## Port provenance
- Source: `~/repos/balloon-e80bench/firmware/e80-stm32-bench/src/bench_stats.{c,h}`
- Tests:  `~/repos/balloon-e80bench/firmware/e80-stm32-bench/tests/test_bench_stats.c`
- Verbatim port: integer Wilson 95% CI, PER, isqrt, kbps, RSSI/SNR averages, min/max

## TDD process
1. RED: wrote test_stats.cpp + Makefile + header → build failed (no .cpp implementation)
2. GREEN: wrote flrc_range_host_stats.cpp (verbatim from E80) → all tests pass

## Test output
```
$ make -C firmware/rp2040/host-tests
g++ -std=c++17 -Wall -Wextra -Werror -O2 -g -I../src -o test_stats test_stats.cpp ../src/flrc_range_host_stats.cpp -lm

$ ./firmware/rp2040/host-tests/test_stats
test_stats: ALL PASS
```

## E80 cross-check
E80 original tests also pass (bit-exact match confirmed):
```
$ ./build-host/test_bench_stats
test_bench_stats: ALL PASS
```

## pytest suite
```
$ python3 -m pytest tools/test_range_bench_ctl.py -q
20 passed in 0.03s
```

## FW-3 boundary cases added
- S==N (100/100, 2/2, 10/10, 10000/10000): hi == exactly 1_000_000
- S=0, N=10: per=1_000_000 (complete loss)
- N=1, S=1: Wilson [~0.2076, 1.0]
- N=2, S=1: Wilson with ±200 tolerance (small-N integer rounding)
- N=10, S=5: Wilson
- N=10000, S=9900: Wilson
- N=10000, S=0: Wilson lo=0