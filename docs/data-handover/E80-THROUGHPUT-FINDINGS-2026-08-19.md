# E80 STM32 FLRC Throughput Test Findings

**Date:** 2026-08-19  
**Hardware:** 2× Ebyte E80-900MBL-02 (STM32F103C8T6 + LR2021)  
**Connection:** Board-to-board, ~10cm apart  
**Frequency:** 869.85 MHz  
**TX Power:** +22 dBm (OUTDOOR mode, 2026 ETSI duty cycle)  
**Firmware:** e80_bench.bin v1.2, commit c31fb30 (ORE + HAL_Delay fix)

## 1. Firmware Fixes Applied (commit c31fb30)

### 1.1 ORE (Overrun Error) Clearing
**Problem:** SWD halt causes USART1 byte overrun. Once ORE bit sets in USART1 SR, 
all further RX is blocked — the ISR never fires, polling fallback never sees RXNE.

**Fix:** After reading DR, check SR for ORE. If set, read SR then DR to clear it.
Applied in both the RXNE interrupt handler AND the polling fallback path.

**File:** `firmware/e80-stm32-bench/src/console.c`

### 1.2 HAL_Delay Override
**Problem:** SWD halt poisons SysTick — HAL_GetTick() never increments. 
HAL_Delay() enters infinite busy-wait loop. Main loop never reached. 
PC stuck at 0x08000a64 (inside HAL_Delay) confirmed via SWD register dump.

**Fix:** Replaced HAL_Delay with `boot_delay_ms()` — NOP spin loop:
```c
void boot_delay_ms(uint32_t ms) {
    for (volatile uint32_t i = 0; i < ms * 8000; i++) { __NOP(); }
}
```
Does not depend on SysTick interrupts. Works after SWD halt.

**File:** `firmware/e80-stm32-bench/src/console.c`

### 1.3 Polling Fallback (Permanent)
Main loop drains USART1 DR directly if RXNE interrupt doesn't fire.
Makes firmware robust against NVIC corruption from any source.

## 2. SWD Poisoning Diagnosis (Key Learning)

**Symptom:** UART RX dead after SWD flash. TX works (boot banner visible). 
Physical RX path confirmed intact (0x5A sent via CH340, read back from USART1 DR).

**Root Cause Chain:**
1. OpenOCD `halt` disables CPU → SysTick stops → HAL_GetTick frozen
2. While CPU halted, CH340 sends bytes → USART1 overrun → ORE bit sets
3. ORE blocks RXNE interrupt → ISR never fires
4. On `reset run`, CPU restarts but:
   - HAL_Delay hangs (SysTick dead) → main loop never reached
   - ORE still set → RXNE still blocked → polling fallback also blocked

**Solution Sequence:**
1. Clear ORE in both ISR and polling path
2. Replace HAL_Delay with NOP spin loop
3. Physical power-cycle (unplug CH340 USB 3+ seconds) for clean NVIC state
4. After power-cycle, DO NOT use SWD — any SWD halt re-poisons NVIC

**Critical Rule:** After physical power-cycle, avoid SWD access entirely. 
SWD `reset` without `halt` is OK ( NVIC stays clean). SWD `halt` poisons NVIC.

## 3. Throughput Matrix Results

### Test Parameters
- Packets per test: N=200
- Inter-packet gap: 10ms (gap_us=10000)
- Modulation: FLRC (Fast Long Range Communication)
- Rates tested: 260, 650, 1300, 2600 kbps
- Payload sizes: 64, 128, 255 bytes

### Results Summary

| Rate (kbps) | Len (B) | TX Sent | RX Got | CRC Err | Throughput (kbps) | RSSI (dBm) | Status |
|:-----------:|:-------:|:-------:|:------:|:-------:|:-----------------:|:----------:|:------:|
| 260 | 64 | 200 | 0 | 0 | 0 | 0.0 | ❌ RX got 0 |
| 260 | 128 | 200 | 0 | 200 | 0 | 0.0 | ❌ All CRC errors |
| 260 | 255 | 200 | ? | ? | ? | ? | ⚠️ Stat parse failed |
| 650 | 64 | 200 | 0 | 0 | 0 | 0.0 | ❌ RX got 0 |
| 650 | 128 | 54 | 0 | 0 | 0 | 0.0 | ❌ TX cut short (IWDG) |
| 650 | 255 | 200 | 200 | 0 | 16 | -28.0 | ✅ PERFECT |
| 1300 | 64 | 200 | 200 | 0 | ~74 | -16.0 | ✅ PERFECT (manual test) |
| 1300 | 128 | 54 | 61 | 0 | 2 | -16.5 | ⚠️ Partial (IWDG cut TX) |
| 1300 | 255 | 30 | 0 | 0 | 0 | 0.0 | ❌ TX cut short (IWDG) |
| 2600 | 64 | 200 | 0 | 0 | 0 | 0.0 | ❌ RX got 0 |
| 2600 | 128 | 200 | 200 | 0 | 8 | -15.5 | ✅ PERFECT |
| 2600 | 255 | 200 | 0 | 0 | 0 | 0.0 | ❌ RX got 0 |

**Earlier clean manual test (not from matrix):**
- FLRC 1300 kbps / 64B / N=200: TX 200/200, RX 200/200, CRC=0, RSSI=-16.0, elapsed=2.7s → **~74 kbps effective**

### Clean Data Points (200/200, 0 CRC)

| Rate (kbps) | Len (B) | RSSI (dBm) | TX Throughput (kbps) | Notes |
|:-----------:|:-------:|:----------:|:--------------------:|:-----:|
| 650 | 255 | -28.0 | 16 | Matrix v5 |
| 1300 | 64 | -16.0 | 74 | Manual test |
| 2600 | 128 | -15.5 | 8 | Matrix v5 |

## 4. Issues Identified

### 4.1 IWDG Watchdog Timer
- `ARM TX` starts IWDG with 2-4 second window
- If `START` command doesn't arrive within window, board resets
- Board loses all configured state (mod, freq, power, role)
- **Mitigation:** Send `ARM TX\rSTART ...` as single serial write (zero gap)
- **Better fix:** Increase IWDG window in firmware, or feed watchdog during wait

### 4.2 2600 kbps FLRC
- `MOD flrc 2600 10` returns ERR UNKNOWN or ERR ARG
- LR2021 firmware may not support 2600 kbps FLRC
- **But:** 2600/128 test got 200/200 in matrix v5 — suggests it DOES work sometimes
- Likely: 2600 kbps requires specific bandwidth/coding rate combination

### 4.3 RX=0 Cases (TX=200 but RX=0)
- Multiple rate/payload combos show TX sending 200 but RX receiving 0
- Possible causes:
  - RX board not armed before TX starts (timing race)
  - Watchdog reset on RX board during setup
  - Certain rate/payload combos not supported by LR2021 in RX mode
  - RX board on wrong ttyUSB port (ports swap on replug)

### 4.4 Port Mapping Instability
- CH340 USB devices map to different ttyUSB numbers on each replug
- Matrix scripts hardcode port assignments
- After replug, TX may be sending to wrong board
- **Fix:** Scan USB serial numbers before each test run

### 4.5 kbps Calculation
- RX-side kbps divides total bytes by elapsed_s (includes 25s wait)
- TX-side kbps more accurate (divides by actual TX time ~2.7s)
- Need to fix kbps calculation to use actual transmission time

## 5. Key Learnings

1. **SWD halt poisons STM32F1 NVIC** — SysTick dies, HAL_Delay hangs, ORE blocks RX. 
   Physical power-cycle is the ONLY clean recovery. Avoid SWD after power-cycle.

2. **ORE clearing is critical** — Without it, any byte overrun (from SWD halt, 
   baud mismatch, or slow polling) permanently blocks UART RX.

3. **Polling fallback should be permanent** — NVIC-based RX is fragile on STM32F1. 
   Main-loop polling of DR is more robust and costs zero extra RAM.

4. **IWDG + ARM TX race** — The watchdog starts at ARM TX, not at START. 
   Must send ARM+START back-to-back. Better: increase IWDG timeout or feed during wait.

5. **2600 kbps FLRC is marginal** — Not cleanly supported by firmware. 
   Focus throughput tests on 260/650/1300 kbps.

6. **CH340 port mapping is unstable** — Always scan USB serial numbers before tests.

7. **Physical path was never broken** — UART RX hardware path confirmed working 
   via 3 separate tests (0x5A, 0x49, 'I' all read from USART1 DR). Issue was 
   always NVIC/SysTick software state from SWD, not hardware.

## 6. Recommendations

1. **Increase IWDG timeout** to 10+ seconds in firmware, or disable during bench testing
2. **Add RX warmup delay** — arm RX 500ms before arming TX
3. **Auto-detect ports** by USB serial number, not hardcoded ttyUSB numbers
4. **Fix kbps calculation** — use actual TX elapsed time, not total test time
5. **Test 260/650/1300 kbps only** — 2600 kbps is marginal
6. **Bump UART baud to 2 Mbps** — 115200 is insufficient for per-packet output at 
   high packet rates (M3 requirement from firmware harmonization plan)
7. **Commit all test scripts** to repo for reproducibility

## 7. Test Scripts

All scripts at `/home/c03rad0r/throughput_matrix*.py` (v1 through v5):
- v1: Initial, crashed with UnboundLocalError
- v2: Partial results, no reset between tests
- v3: Full reset + health check, still messy from IWDG
- v4: ARM TX + START as single write, partial improvement
- v5: Refined single-write approach, best results

SWD diagnostic scripts at `/home/c03rad0r/uart_*.py` — used for NVIC/DR debugging.

## 8. Firmware Build

- Flash: 19,500 B (29.7% of 64KB)
- RAM: 2,808 B (8.7% of 20KB)
- Build command: `make -C firmware/e80-stm32-bench/build-fw`
- Binary: `firmware/e80-stm32-bench/build-fw/e80_bench.bin`
- Commit: c31fb30 on `feat/e80-stm32-bench` branch

---

**Author:** Hermes Agent (manager profile)  
**Operator:** Felix (c03rad0r)  
**Session:** 2026-08-19, balloon-hermes Signal group
## 9. v6 Matrix Results (Final Run)

### Test v6 Parameters
- Same as above but: PA=10dBm (indoor, no outdoor unlock), GAP= key (not GAP_US=), no ARM RX (ROLE RX is sufficient), 4s wait per test

### v6 Results

| Rate (kbps) | Len (B) | TX Sent | RX Got | CRC Err | TX kbps | RSSI (dBm) | Status |
|:-----------:|:-------:|:-------:|:------:|:-------:|:-------:|:----------:|:------:|
| 260 | 64 | 200 | ? | ? | 31 | ? | RX stat parse fail |
| 260 | 128 | 200 | 0 | 200 | 54 | 0.0 | All CRC errors |
| 260 | 255 | 200 | 200 | 0 | 84 | -27.5 | PERFECT |
| 650 | 64 | 200 | 0 | 200 | 35 | 0.0 | All CRC errors |
| 650 | 128 | - | - | - | - | - | IWDG reset |
| 650 | 255 | 200 | 200 | 0 | 115 | -28.0 | PERFECT |
| 1300 | 64 | - | - | - | - | - | IWDG reset |
| 1300 | 128 | - | - | - | - | - | IWDG reset |
| 1300 | 255 | - | - | - | - | - | IWDG reset |

### Key Pattern Discovered
- 255B payloads consistently produce 200/200 with 0 CRC errors across rates
- 64B and 128B payloads at 260/650 kbps get 200 TX sent but RX sees 200 CRC errors
- This suggests a payload length / coding rate mismatch at shorter payloads
- IWDG kills the TX board after first test (watchdog stays active across ROLE changes)

### All Clean Data Points (5 total)

| Rate (kbps) | Len (B) | TX kbps | RSSI (dBm) | Source |
|:-----------:|:-------:|:-------:|:----------:|:------:|
| 260 | 255 | 84 | -27.5 | v6 |
| 650 | 255 | 115 | -28.0 | v6 |
| 1300 | 64 | 74 | -16.0 | manual |
| 2600 | 128 | 8 | -15.5 | v5 |

### Firmware Command Syntax (confirmed from source code)
- `MOD flrc <rate_kbps> <dbm>` — rate must be one of: 260, 325, 520, 650, 1040, 1300, 2080, 2600
- `FREQ <hz>` — frequency in Hz
- `PA <dbm>` — 0-10 indoor, 0-22 after POWER MODE OUTDOOR 2026
- `POWER MODE OUTDOOR 2026` — unlocks +22 dBm (pin=2026)
- `ROLE TX|RX|NONE` — RX is continuous, no ARM needed
- `ARM TX` — enables TX (starts IWDG 2-4s window)
- `START N=<pkts> LEN=<6-511> GAP=<us>` — key is GAP, not GAP_US
- `STAT?` — query statistics
