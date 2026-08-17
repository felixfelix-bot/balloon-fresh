# LR2021 LoRa Bandwidth Codes — Authoritative Table (BW-1)

**Status:** resolved 2026-08-17 (task `t_c91296d9`)
**Shared source of truth:** `firmware/rp2040/src/lr2021_bw_codes.h`
**Host parser:** `tools/lr2021_bw_codes.py` (reads the header at runtime)

## Ground truth

The vendored Semtech `lr20xx_driver` in the E80 bench repo is authoritative:

| File | Lines | What it defines |
|---|---|---|
| `~/repos/balloon-e80bench/firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_lora_types.h` | 93–111 | `lr20xx_radio_lora_bw_t` enum — the BW wire codes |
| `~/repos/balloon-e80bench/firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/src/lr20xx_radio_lora.c` | 185–195 | `SetModulationParams` packing: opcode `0x0220`, byte 2 = `(sf << 4) + bw`, byte 3 = `(cr << 4) + ppm` |
| same | 485–542 | `lr20xx_radio_lora_get_bw_in_hz()` — the Hz constants (also used for time-on-air math) |

## The authoritative table

Codes `0x00–0x07` are the **standard ladder**, `0x08–0x0F` the **alternate
ladder**. Hz values are the driver's `get_bw_in_hz()` constants.

| code | enum (lr20xx / lr2021) | driver Hz | datasheet nominal | bench relevance |
|------|------------------------|-----------|-------------------|-----------------|
| 0x00 | BW_7 | 7 812 | 7.8125 kHz | — |
| 0x01 | BW_15 | 15 625 | 15.625 kHz | — |
| 0x02 | BW_31 | 31 250 | 31.25 kHz | — |
| 0x03 | BW_62 | 62 500 | 62.5 kHz | — |
| **0x04** | BW_125 | 125 000 | 125 kHz | **LF LoRa (868 MHz)** |
| **0x05** | BW_250 | 250 000 | 250 kHz | **LF LoRa (868 MHz)** |
| 0x06 | BW_500 | 500 000 | 500 kHz | HF option |
| 0x07 | BW_1000 | 1 000 000 | 1000 kHz | HF option (verify vs datasheet before on-air use) |
| 0x08 | BW_10 | 10 417 | 10.417 kHz | — |
| 0x09 | BW_20 | 20 833 | 20.833 kHz | — |
| 0x0A | BW_41 | 41 667 | 41.67 kHz | — |
| 0x0B | BW_83 | 83 340 | 83.34 kHz | — |
| 0x0C | BW_101 | 101 563 | 101.5625 kHz | — |
| **0x0D** | BW_203 | 203 000 | 203.125 kHz | wide-BW ladder |
| **0x0E** | BW_406 | 406 000 | 406.25 kHz | wide-BW ladder |
| **0x0F** | BW_812 | 812 000 | 812.5 kHz | **HF LoRa (2.4 GHz)** |

Note the two "nominal" columns: the driver uses round Hz constants
(203 000 / 406 000 / 812 000) for airtime math, while datasheets quote
203.125 / 406.25 / 812.5 kHz. For anything that must match firmware
behaviour (airtime, timeout budgets) use the **driver Hz** column.

## Reconciliation — there was no real contradiction

* `firmware/rp2040/src/lora_868_tx.cpp` L63–69 maps 203/406/812 kHz →
  `0x0D/0x0E/0x0F`. **Correct** — these are the alternate/wide-BW ladder
  codes, and the file's comment values (203.13/406.25/812.5) are the
  datasheet nominals of exactly those codes.
* `firmware/rp2040/src/dual_radio_sweep_tx.cpp` L69 comment
  `0x05=250kHz`. **Correct** — standard-ladder code. Its mode table uses
  `0x05` for LF (868 MHz) LoRa and `0x0F` (812 kHz) for HF (2.4 GHz) LoRa,
  both consistent with the driver.

Each file showed a different *subset* of the same table (wide-BW codes vs
standard codes), which read as a contradiction. The full 16-entry table
above supersedes both partial views; the shared header encodes it once.

## Wire encoding (SetModulationParams, LoRa packet type)

```
opcode 0x02 0x20
byte2 = (sf << 4) | bw      # SF5..SF12 = 0x05..0x0C
byte3 = (cr << 4) | ppm     # CR 4/5..4/8 = 0x01..0x04
```

Examples: SF7/BW250 → `0x75`; SF12/BW125 → `0xC4`; SF5/BW812 → `0x5F`.

## Usage

**Firmware (FW-5a):**

```c
#include "lr2021_bw_codes.h"
uint8_t code = lr2021_bw_khz_to_code(125);   // MOD LORA <sf> 125
uint32_t hz  = lr2021_bw_code_to_hz(code);   // 125000
```

**Host scripts (HS-1b):**

```python
from lr2021_bw_codes import khz_to_code, code_to_hz
code = khz_to_code(812)      # 0x0F
hz   = code_to_hz(0x0F)      # 812000
python3 tools/lr2021_bw_codes.py   # pretty-print the whole table
```

## Tests

* C: `make -C firmware/rp2040/host-tests && ./host-tests/test_bw_codes`
  pins every row, the enum values, kHz/Hz round-trips, invalid inputs, and
  the wire-packing formula against the vendored-driver values.
* Python: `python3 -m pytest tools/test_lr2021_bw_codes.py -q` parses the
  header via the same parser HS-1b will use and pins it against the same
  ground truth — proving the one-source-of-truth contract end to end.

To re-verify the table against the vendored driver after a driver update:

```sh
grep -A17 'typedef enum' \
  ~/repos/balloon-e80bench/firmware/e80-stm32-bench/third_party/Radio/lr20xx_driver/inc/lr20xx_radio_lora_types.h
```
