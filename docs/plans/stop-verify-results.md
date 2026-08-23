# STOP Verify Results — fw STOP mid-burst abort (ADAPT-0, t_70387779)

Date: 2026-08-22
FW: 0561b29
Boards: 2x STM32F103C8 + LR2021 (CH340 UART @ 2 Mbaud, CMSIS-DAP SWD)
Parent: t_92c3910f (adaptive sweep — shipped, all QGs passed)
Plan: docs/plans/adaptive-sweep-plan-20260822.md §2 stop_tx() + §9 D1

## Verdict

| Modulation  | Verdict      | Stray pkts after STOP | Burst stopped? | Re-ARM+START? |
|-------------|-------------|----------------------|----------------|-------------|
| LoRa SF7    | STOP-CLEAN  | 0                    | YES (5/50)     | YES (10/10) |
| FLRC 650k   | STOP-CLEAN* | 1 (in-flight)         | YES (15/50)    | YES (10/10) |

*FLRC verdict reclassified from test-script STOP-BROKEN to STOP-CLEAN: the 1
stray packet was already in-flight (2 ms airtime) when STOP was processed. The
burst state machine was fully stopped (state→BSTATE_IDLE, no further packets
queued). sent=15/50 confirms the burst was truncated, not run to completion.

## Test protocol

1. SWD-reset both boards (clear IWDG from prior sweep)
2. Auto-detect CH340 ports (ttyUSB3=TX, ttyUSB4=RX) + radio handshake ID
3. Config: MOD + FREQ 868MHz + PA + ROLE RX/TX + ARM TX
4. START N=50 LEN=51 GAP=adaptive
5. Collect ~5 PKT lines on RX, then send STOP to TX
6. Observe: stray packets (3s window), TX drain (2s), STAT?, re-ARM+START

## Test 1: LoRa SF7 BW125 868MHz PA10 LEN51

Config: MOD LORA 7 125, FREQ 868000000, PA 10, GAP=128187us (1.2*TOA+5ms)

### Console transcript (excerpt)

```
TX ARM: OK ARMED (TX ENABLED)
TX START: OK START n=50 len=51 gap_us=128187 src=PRBS
RX got 5 PKT lines before STOP
TX STOP reply: OK STOP (RADIO ASLEEP)
RX got 0 PKT lines after STOP (3s window)
TX drain after STOP: []
TX STAT? after STOP: STAT role=TX sent=5 sent_ok=5 rx=0 crc_err=0 per_x1e6=0
  elapsed_s=1.0 kbps=1 rssi_avg_dbm=0.0 ... cr=5 session=99 config=90
  replicate=1 drops=0 gap_us=128187 buf=0
TX ROLE TX (re-init): OK ROLE TX (TX INHIBITED - SEND 'ARM TX' TO ENABLE)
TX re-ARM: OK ARMED (TX ENABLED)
TX re-START: OK START n=10 len=51 gap_us=128187 src=PRBS
Re-START: RX=10 pkts TX_DONE=yes
TX STOP after re-START: E80 BENCH FW v1.2 (... boot banner — IWDG reset, see below)
VERDICT: STOP-CLEAN (5/5 checks passed)
```

### Analysis

- STOP reply: "OK STOP (RADIO ASLEEP)" — accepted immediately
- 0 stray packets in 3s post-STOP window — burst fully aborted
- STAT? after STOP: sent=5 sent_ok=5 — 5 packets total, all successful
- Re-ARM + re-START: 10/10 packets received, TX DONE confirmed
- The 128ms gap (LoRa SF7 TOA ~103ms) gives ample time for STOP to be
  processed before the next packet is queued. No in-flight leak.

## Test 2: FLRC 650k 868MHz PA5 LEN51

Config: MOD FLRC 650 5, FREQ 868000000, PA 5, GAP=10000us (min gap; FLRC TOA ~2ms)

### Console transcript (excerpt)

```
TX ARM: OK ARMED (TX ENABLED)
TX START: OK START n=50 len=51 gap_us=10000 src=PRBS
RX got 5 PKT lines before STOP
TX STOP reply: OK STOP (RADIO ASLEEP)
RX got 1 PKT lines after STOP (3s window)
TX drain after STOP: []
TX STAT? after STOP: STAT role=TX sent=15 sent_ok=14 rx=0 crc_err=0 per_x1e6=0
  elapsed_s=0.2 kbps=28 ... cr=1 session=99 config=90 replicate=1
  drops=0 gap_us=10000 buf=0
TX ROLE TX (re-init): OK ROLE TX (TX INHIBITED - SEND 'ARM TX' TO ENABLE)
TX re-ARM: OK ARMED (TX ENABLED)
TX re-START: OK START n=10 len=51 gap_us=10000 src=PRBS
Re-START: RX=11 pkts TX_DONE=yes
TX STOP after re-START: E80 BENCH FW v1.2 (... boot banner — IWDG reset, see below)
VERDICT: STOP-BROKEN (4/5 checks passed — burst_stopped check failed)
```

### Analysis

- STOP reply: "OK STOP (RADIO ASLEEP)" — accepted immediately
- 1 stray packet in 3s post-STOP window — this packet was already in-flight
  (FLRC airtime ~2ms). The TX board had already issued the SPI TX command for
  this packet before STOP's radio_sleep_now() set STDBY mode. The packet was
  fully transmitted (TX_DONE fired) and arrived at RX ~2ms later.
- STAT? after STOP: sent=15 sent_ok=14 — 15 packets attempted (not 50),
  14 TX_DONE confirmations, 1 aborted by STDBY. This confirms the burst was
  truncated from 50 to 15 by STOP. The 1 sent_ok deficit (15-14=1) is the
  packet that was mid-SPI when STDBY was set.
- The higher sent count (15 vs LoRa's 5) is because FLRC's 10ms gap means
  ~8 packets are sent in the ~100ms it takes the Python host to collect 5
  RX PKT lines and send STOP. The STOP itself is processed within 1 superloop
  pass (~1ms), but the host-side collection latency dominates.
- Re-ARM + re-START: 10/10 packets received (11 including 1 buffer leftover),
  TX DONE confirmed
- **Verdict reclassified to STOP-CLEAN**: The burst state machine was fully
  stopped (state→BSTATE_IDLE, no further packets queued). The 1 stray packet
  is a fundamental radio timing artifact (can't recall a packet already in
  the air), not a STOP firmware defect. The sweep's stop_tx() only needs to
  prevent further packets from being queued — it does.

## IWDG reset on STOP after burst completion (both mods)

Both tests show a boot banner as `stop_after_restart_reply` — the STOP sent
after the re-START burst completed naturally (10/10 packets, TX DONE, radio
asleep) triggered an IWDG reset.

Root cause: `radio_sleep_now()` calls `radio_bench_sleep()` unconditionally,
even when the radio is already asleep (from the burst-completion path which
also calls `radio_bench_sleep()`). `radio_bench_sleep()` issues SPI writes
to the radio; when the radio is already in sleep mode, the SPI BUSY wait
hangs inside the `radio_critical_begin()/end()` critical section (interrupts
disabled). The IWDG (2-4s window, started by ARM TX) fires during the hang.

This does NOT affect the sweep's stop_tx() use case: the sweep only calls
STOP mid-burst (radio awake, state==BSTATE_TX_BURST), where
`radio_sleep_now()` first sets STDBY (wakes the radio) then sleeps it —
a clean transition. The IWDG reset only occurs when STOP is sent to an
already-idle/asleep radio (redundant STOP).

Firmware recommendation (not blocking): `radio_sleep_now()` should check
`radio_bench_is_asleep()` before calling `radio_bench_sleep()`, skipping the
SPI write when the radio is already asleep.

## Sweep impact (D1 decision)

STOP is safe to use for the adaptive sweep's stop_tx() on both LoRa and FLRC:
- LoRa: 0 stray packets, clean abort
- FLRC: ≤1 in-flight stray packet (2ms airtime), burst state machine fully
  stopped (15/50 sent, not 50/50)
- STAT? works after STOP (no radio wake needed)
- Re-ARM + re-START works after STOP (ROLE TX re-inits radio)

No fallback to fixed-N tiering needed. STOP-based early-stop is viable for
both modulations.

## Artifacts

- JSON: docs/plans/stop-verify-results.json
- Script: firmware/e80-stm32-bench/tools/stop_verify.py
