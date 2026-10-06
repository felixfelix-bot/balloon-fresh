# FW-2: Pure console parser module + host tests — Evidence

## Task
Kanban `t_f64ef023` — FW-2: pure console parser module + host tests (run #103)

## Deliverables
- `firmware/rp2040/src/flrc_range_host_cmd.h` — parser API: rh_cmd_t / rh_cmd_id_t / rh_cmd_err_t, range constants (single source of truth for FW-6/HS)
- `firmware/rp2040/src/flrc_range_host_cmd.cpp` — pure TU port of E80 bench_cmd.c, REV-2 grammar
- `firmware/rp2040/host-tests/test_cmd.cpp` — 13 test functions, E80 vectors + REV-2 deltas
- `firmware/rp2040/host-tests/Makefile` — test_cmd target
- `.gitignore` — test_cmd binary

## Port provenance
- Source: `~/repos/balloon-e80bench/firmware/e80-stm32-bench/src/bench_cmd.{c,h}`
- Tests:  `~/repos/balloon-e80bench/firmware/e80-stm32-bench/tests/test_bench_cmd.c`
- Ported verbatim: tokenizer (split_tokens), strcaseeq, parse_u32 (overflow guard),
  parse_i8, token limits (8 tokens × 24 chars), case-insensitive matching,
  CRLF tolerance.

## REV-2 grammar deltas vs E80 (each locked by a test vector)
| Delta | Vector |
|---|---|
| Standalone `LEN/N/GAP` cmds (not START kwargs) | `test_len_n_gap` |
| `START` bare — E80 kwargs now ERR ARG | `test_basic_commands` (`START N=1000...` → ARG) |
| `MOD FLRC <br>` — no dbm arg (moved to PA) | `test_mod_flrc` (`MOD FLRC 650 22` → ARG) |
| `FREQ` band 863–870 MHz baked in (EU SRD hard clamp) | `test_freq` (433 MHz / 2.4 GHz → RANGE) |
| `POWER MODE OUTDOOR <pin>`: pin==2026 checked at parse | `test_power` (9999 → ARG; E80 deferred) |
| Dropped: BAND OVERRIDE, FLASH, ARM TX (ROLE+START two-step) | — |
| `PA` −18..+22 range (E80 PA unchecked) | `test_pa` |

## Error-class layer split (§1)
Parser emits OK / ARG / RANGE / UNKNOWN. BUSY, INHIBITED, POWER-LOCKED need
runtime state → FW-6 dispatch. The enum + `rh_cmd_err_str` define the full
vocabulary here ("POWER-LOCKED" incl. hyphen) so replies have one source of
truth. Locked by `test_err_str`. Layer split locked by `PA 14` parsing OK.
`rh_cmd_is_config()` (MOD/FREQ/PA/LEN, not N/GAP) is the seam for the FW-6
re-init + ERR BUSY rules — locked by `test_is_config`.

## §1 STAT? example-line token lock
`test_stat_example_tokens` feeds the plan §1 example reply (joined to one
line, 21 tokens) through `rh_cmd_tokenize` and asserts every key=value token
positionally — the keys HS-2's parse_stat() must emit.

## TDD process
1. RED: header + test_cmd.cpp + STUB .cpp (compiles, returns garbage) →
   `test_cmd: 124 FAILURES` (exit 1), siblings green.
2. GREEN: full port (1 fix during GREEN: bare `MOD` indexed tokens[1] before
   the ntok guard — added ntok<2 check) → all pass.

## Test output
```
$ make -C firmware/rp2040/host-tests all
g++ -std=c++17 -Wall -Wextra -Werror -O2 -g -I../src -o test_stats ...
g++ -std=c++17 -Wall -Wextra -Werror -O2 -g -I../src -o test_safety ...
g++ -std=c++17 -Wall -Wextra -Werror -O2 -g -I../src -o test_cmd ...
$ ./test_stats && ./test_safety && ./test_cmd
test_stats: ALL PASS
test_safety: ALL PASS
test_cmd: ALL PASS
```

## Regression checks (gate 2)
- `pio run -e rp2040-range-host` → SUCCESS (15.5 s) — new TU compiles under
  arm-none-eabi via the `flrc_range_host*.cpp` src filter; no Arduino includes.
- `python3 -m pytest tools/test_range_bench_ctl.py -q` → 64 passed.
