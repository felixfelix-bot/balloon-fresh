#!/bin/sh
# t_92c3910f — run the full dual-band sweep (868 MHz + 2.4 GHz, 113 configs).
set -e
cd /home/c03rad0r/repos/balloon-e80bench/firmware/e80-stm32-bench
exec python3 -u tools/e80_sweep_full.py
