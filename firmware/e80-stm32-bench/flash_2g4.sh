#!/bin/sh
# t_92c3910f — SWD flash both E80 bench boards with 2.4 GHz fw (0561b29).
# Method per task spec: openocd 'reset halt; resume' (NOT 'reset run').
set -e
cd "$(dirname "$0")"
for PS in 148757200D2D1425 203584200D2D0D42; do
  echo "=== probe $PS ==="
  /usr/bin/openocd -f interface/cmsis-dap.cfg -f target/stm32f1x.cfg \
    -c "transport select swd; adapter serial $PS; init; program build-fw/e80_bench.bin 0x08000000 verify; reset halt; resume; exit" 2>&1 | tail -12
done
