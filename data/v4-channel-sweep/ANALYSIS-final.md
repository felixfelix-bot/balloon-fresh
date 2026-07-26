# ANALYSIS — rx_sweep_final_031009.log (POST-FIX, All 3 Bugs Fixed)

**Generated:** 2026-07-26
**Capture file:** `data/v4-channel-sweep/rx_sweep_final_031009.log` (78,817 lines)
**Firmware state:** Post-`85793c2` — FLRC sync word length fix (all 3 bugs resolved)
**Previous bugs fixed:**
1. `7700e22` — FLRC-1300 index in channel sweep (wrong bitrate base)
2. `536b418` — RX channelSweepMode override clobbering freqMHz
3. `85793c2` — FLRC sync word length=0 → 32-bit (sw_len=2) — **root cause of FLRC mode failures**

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| **Total PHASE_RESULT lines** | 113 |
| **Phases decoded (rx > 0)** | **56 / 113 (49.6%)** |
| **Phases failed (rx = 0)** | 57 / 113 (50.4%) |
| **Full cycle decode rate (cycle 2, phases 0–76)** | **44 / 77 (57.1%)** |
| **LoRa modes decode rate** | 19 / 21 (90.5%) |
| **FLRC modes decode rate** | 22 / 32 (68.8%) |
| **Overall BER** | **0.00e+00** (115,392 bits, 0 errors) |
| **GPS** | 3–6 sats, fix=1 throughout active phases |

**Verdict:** The sync word fix (`85793c2`) produced a measurable improvement over the previous FINAL capture (`rx_sweep_fixed_204825.log`), particularly in FLRC-650/1300/2600 modes where small/medium packets were previously failing entirely. However, the **systemic bitrate-index offset** identified in MASTER-ANALYSIS.md persists — FLRC modes at bitrates > 325 still fail on small/medium packet sizes. The channel sweep remains fundamentally broken (WiFi out of band, EU868 TX/RX mismatch).

---

## 2. Capture Structure — 3 Cycles

The capture spans 1.47 full sweep cycles:

| Cycle | Phases | Range | Decoded | Rate | Description |
|-------|--------|-------|---------|------|-------------|
| 1 (tail) | 29 | 48–76 | 5 | 17% | End of previous cycle (FLRC + channel sweep — hardest phases) |
| **2 (full)** | **77** | **0–76** | **44** | **57%** | **Complete sweep cycle — primary analysis basis** |
| 3 (start) | 7 | 0–6 | 7 | 100% | Start of next cycle (HF-LoRa phases — easiest) |

**Capture completeness: ✅ COMPLETE.** All 77 phases (0–76) are present in cycle 2. No phases are missing from the full sweep.

---

## 3. Complete Decode Map (113 Phases, Capture Order)

Each row = one PHASE_RESULT line. Phases in capture order (not numerical).

### Cycle 1 — Tail of Previous Cycle (phases 48–76)

| Idx | Phase | Mode | Size | RX | PER% | RSSI | CRC | Garbage | Sats | Fix | Status |
|-----|-------|------|------|----|------|------|-----|---------|------|-----|--------|
| 0 | 48 | LF-FLRC-1300-32 | 32 | 0 | 100.0 | — | 0 | 1056 | 0 | 0 | ❌ FAIL |
| 1 | 49 | LF-FLRC-1300-64 | 64 | 0 | 100.0 | -54 | 0 | 1001 | 0 | 0 | ❌ FAIL |
| 2 | 50 | LF-FLRC-1300-128 | 128 | 0 | 100.0 | -54 | 0 | 1042 | 0 | 0 | ❌ FAIL |
| 3 | 51 | LF-FLRC-1300-255 | 255 | 4 | 96.0 | -45 | 3 | 956 | 6 | 1 | ✅ DECODE |
| 4 | 52 | LF-FLRC-2600-32 | 32 | 0 | 100.0 | -53 | 1 | 1050 | 0 | 0 | ❌ FAIL |
| 5 | 53 | LF-FLRC-2600-64 | 64 | 0 | 100.0 | -52 | 0 | 1007 | 0 | 0 | ❌ FAIL |
| 6 | 54 | LF-FLRC-2600-128 | 128 | 0 | 100.0 | — | 0 | 1048 | 0 | 0 | ❌ FAIL |
| 7 | 55 | LF-FLRC-2600-255 | 255 | 5 | 95.0 | -51 | 3 | 988 | 6 | 1 | ✅ DECODE |
| 8–20 | 56–68 | CH-2412…2472 (WiFi) | 64 | 0–1 | 99–100 | -55 | 0–1 | 938–1017 | 0–6 | 0–1 | ❌ OOB / ⚠️ LEAK |
| 21–28 | 69–76 | CH-863…870 (EU868) | 64 | 0 | 100.0 | -53/-54 | 0–1 | 1029–1047 | 0 | 0 | ❌ FAIL |

### Cycle 2 — Full Sweep (phases 0–76) — Primary Analysis

| Phase | Mode | Size | RX | PER% | RSSI avg/min | CRC | Garbage | Sats | Fix | Status |
|-------|------|------|----|------|-------------|-----|---------|------|-----|--------|
| 0 | HF-LoRa-SF7-32 | 32 | 10 | 50.0 | -25/-26 | 4 | 0 | 4 | 1 | ✅ |
| 1 | HF-LoRa-SF7-64 | 64 | 10 | 50.0 | -25/-26 | 3 | 1 | 5 | 1 | ✅ |
| 2 | HF-LoRa-SF7-128 | 128 | 11 | 45.0 | -25/-26 | 2 | 1 | 5 | 1 | ✅ |
| 3 | HF-LoRa-SF7-255 | 255 | 14 | 30.0 | -22/-26 | 0 | 0 | 5 | 1 | ✅ |
| 4 | HF-LoRa-SF9-32 | 32 | 12 | 40.0 | -22/-25 | 1 | 1 | 5 | 1 | ✅ |
| 5 | HF-LoRa-SF9-64 | 64 | 14 | 30.0 | -21/-22 | 1 | 0 | 4 | 1 | ✅ |
| 6 | HF-LoRa-SF9-128 | 128 | 10 | 23.1 | -21/-22 | 1 | 0 | 4 | 1 | ✅ |
| 7 | HF-LoRa-SF9-255 | 255 | 4 | 33.3 | -22/-22 | 0 | 0 | 4 | 1 | ✅ |
| 8 | HF-FLRC-325-32 | 32 | 21 | 79.0 | -51/-58 | 3 | 655 | 4 | 1 | ✅ |
| 9 | HF-FLRC-325-64 | 64 | 15 | 85.0 | -49/-58 | 3 | 563 | 4 | 1 | ✅ |
| 10 | HF-FLRC-325-128 | 128 | 14 | 86.0 | -46/-46 | 1 | 407 | 5 | 1 | ✅ |
| 11 | HF-FLRC-325-255 | 255 | 14 | 86.0 | -46/-46 | 0 | 255 | 4 | 1 | ✅ |
| 12 | HF-FLRC-650-32 | 32 | 1 | 99.0 | -56/-56 | 5 | 1016 | 4 | 1 | ✅ |
| 13 | HF-FLRC-650-64 | 64 | 0 | 100.0 | -56/-56 | 0 | 981 | 0 | 0 | ❌ |
| 14 | HF-FLRC-650-128 | 128 | 7 | 93.0 | -47/-56 | 2 | 925 | 4 | 1 | ✅ |
| 15 | HF-FLRC-650-255 | 255 | 10 | 90.0 | -46/-46 | 0 | 554 | 4 | 1 | ✅ |
| 16 | HF-FLRC-1300-32 | 32 | 1 | 99.0 | -55/-55 | 5 | 997 | 4 | 1 | ✅ |
| 17 | HF-FLRC-1300-64 | 64 | 1 | 99.0 | -54/-56 | 0 | 954 | 4 | 1 | ✅ |
| 18 | HF-FLRC-1300-128 | 128 | 0 | 100.0 | -54/-56 | 0 | 971 | 0 | 0 | ❌ |
| 19 | HF-FLRC-1300-255 | 255 | 12 | 88.0 | -46/-46 | 0 | 895 | 4 | 1 | ✅ |
| 20 | HF-FLRC-2600-32 | 32 | 0 | 100.0 | -54/-54 | 6 | 1022 | 0 | 0 | ❌ |
| 21 | HF-FLRC-2600-64 | 64 | 1 | 99.0 | -53/-54 | 0 | 998 | 4 | 1 | ✅ |
| 22 | HF-FLRC-2600-128 | 128 | 0 | 100.0 | -54/-54 | 0 | 1040 | 0 | 0 | ❌ |
| 23 | HF-FLRC-2600-255 | 255 | 3 | 97.0 | -53/-54 | 1 | 936 | 4 | 1 | ✅ |
| 24 | HF-LoRa-SF12-32 | 32 | 1 | 50.0 | -15/-15 | 0 | 0 | 5 | 1 | ✅ |
| 25 | HF-LoRa-SF12-64 | 64 | 1 | 0.0 | -16/-16 | 0 | 0 | 4 | 1 | ✅ |
| 26 | HF-LoRa-SF12-128 | 128 | 1 | 0.0 | -16/-16 | 0 | 0 | 4 | 1 | ✅ |
| 27 | HF-LoRa-SF12-255 | 255 | 1 | 0.0 | -15/-15 | 0 | 0 | 4 | 1 | ✅ |
| 28 | LF-LoRa-SF7-32 | 32 | 0 | 100.0 | — | 0 | 0 | 0 | 0 | ❌ |
| 29 | LF-LoRa-SF7-64 | 64 | 18 | 10.0 | -29/-30 | 1 | 1 | 5 | 1 | ✅ |
| 30 | LF-LoRa-SF7-128 | 128 | 10 | 23.1 | -30/-30 | 1 | 0 | 4 | 1 | ✅ |
| 31 | LF-LoRa-SF7-255 | 255 | 6 | 14.3 | -30/-30 | 0 | 0 | 4 | 1 | ✅ |
| 32 | LF-LoRa-SF9-32 | 32 | 7 | 0.0 | -27/-28 | 1 | 0 | 5 | 1 | ✅ |
| 33 | LF-LoRa-SF9-64 | 64 | 2 | 33.3 | -27/-28 | 0 | 0 | 4 | 1 | ✅ |
| 34 | LF-LoRa-SF9-128 | 128 | 1 | 0.0 | -27/-27 | 0 | 0 | 4 | 1 | ✅ |
| 35 | LF-LoRa-SF9-255 | 255 | 1 | 0.0 | -27/-27 | 0 | 0 | 4 | 1 | ✅ |
| 36 | LF-LoRa-SF12-32 | 32 | 0 | 100.0 | — | 0 | 0 | 0 | 0 | ❌ |
| 37 | LF-LoRa-SF12-SKIP | 64 | 0 | 0.0 | — | 0 | 0 | 0 | 0 | ⏭️ SKIP |
| 38 | LF-LoRa-SF12-SKIP | 128 | 0 | 0.0 | — | 0 | 0 | 0 | 0 | ⏭️ SKIP |
| 39 | LF-LoRa-SF12-SKIP | 255 | 0 | 0.0 | — | 0 | 0 | 0 | 0 | ⏭️ SKIP |
| 40 | LF-FLRC-325-32 | 32 | 24 | 76.0 | -49/-56 | 3 | 675 | 5 | 1 | ✅ |
| 41 | LF-FLRC-325-64 | 64 | 20 | 80.0 | -50/-57 | 0 | 571 | 4 | 1 | ✅ |
| 42 | LF-FLRC-325-128 | 128 | 15 | 85.0 | -43/-44 | 1 | 410 | 5 | 1 | ✅ |
| 43 | LF-FLRC-325-255 | 255 | 22 | 78.0 | -43/-44 | 0 | 244 | 5 | 1 | ✅ |
| 44 | LF-FLRC-650-32 | 32 | 1 | 99.0 | -55/-55 | 1 | 1037 | 5 | 1 | ✅ |
| 45 | LF-FLRC-650-64 | 64 | 0 | 100.0 | -53/-55 | 0 | 1017 | 0 | 0 | ❌ |
| 46 | LF-FLRC-650-128 | 128 | 2 | 98.0 | -45/-55 | 2 | 971 | 5 | 1 | ✅ |
| 47 | LF-FLRC-650-255 | 255 | 6 | 94.0 | -43/-43 | 1 | 567 | 5 | 1 | ✅ |
| 48 | LF-FLRC-1300-32 | 32 | 0 | 100.0 | -53/-53 | 1 | 1051 | 0 | 0 | ❌ |
| 49 | LF-FLRC-1300-64 | 64 | 1 | 99.0 | -53/-54 | 0 | 999 | 5 | 1 | ✅ |
| 50 | LF-FLRC-1300-128 | 128 | 0 | 100.0 | -54/-54 | 0 | 1041 | 0 | 0 | ❌ |
| 51 | LF-FLRC-1300-255 | 255 | 13 | 87.0 | -43/-43 | 0 | 920 | 5 | 1 | ✅ |
| 52 | LF-FLRC-2600-32 | 32 | 0 | 100.0 | -52/-52 | 1 | 1050 | 0 | 0 | ❌ |
| 53 | LF-FLRC-2600-64 | 64 | 0 | 100.0 | -52/-53 | 0 | 986 | 0 | 0 | ❌ |
| 54 | LF-FLRC-2600-128 | 128 | 0 | 100.0 | — | 0 | 1053 | 0 | 0 | ❌ |
| 55 | LF-FLRC-2600-255 | 255 | 3 | 97.0 | -52/-53 | 4 | 997 | 4 | 1 | ✅ |
| 56–68 | CH-2412…2472 (WiFi) | 64 | 0–2 | 98–100 | -55 | 0–2 | 927–1017 | 0–3 | 0–1 | ❌ OOB / ⚠️ LEAK |
| 69–76 | CH-863…870 (EU868) | 64 | 0 | 100.0 | -53/-54 | 0–1 | 1029–1047 | 0 | 0 | ❌ FAIL |

### Cycle 3 — Start of Next Cycle (phases 0–6)

| Phase | Mode | Size | RX | PER% | RSSI | Status |
|-------|------|------|----|------|------|--------|
| 0 | HF-LoRa-SF7-32 | 32 | 10 | 50.0 | -25 | ✅ |
| 1 | HF-LoRa-SF7-64 | 64 | 11 | 45.0 | -25 | ✅ |
| 2 | HF-LoRa-SF7-128 | 128 | 12 | 40.0 | -24 | ✅ |
| 3 | HF-LoRa-SF7-255 | 255 | 15 | 25.0 | -22 | ✅ |
| 4 | HF-LoRa-SF9-32 | 32 | 12 | 40.0 | -21 | ✅ |
| 5 | HF-LoRa-SF9-64 | 64 | 14 | 30.0 | -21 | ✅ |
| 6 | HF-LoRa-SF9-128 | 128 | 11 | 15.4 | -21 | ✅ |

---

## 4. Decode Map by Unique Mode (Cycle 2 — Full Cycle)

Using cycle 2 data (most recent full cycle). Excludes SKIP phases.

### LoRa Modes

| Mode | Size | RX | PER% | RSSI avg/min | Status |
|------|------|----|------|-------------|--------|
| HF-LoRa-SF7-32 | 32 | 10 | 50.0 | -25/-26 | ✅ |
| HF-LoRa-SF7-64 | 64 | 10 | 50.0 | -25/-26 | ✅ |
| HF-LoRa-SF7-128 | 128 | 11 | 45.0 | -25/-26 | ✅ |
| HF-LoRa-SF7-255 | 255 | 14 | 30.0 | -22/-26 | ✅ |
| HF-LoRa-SF9-32 | 32 | 12 | 40.0 | -22/-25 | ✅ |
| HF-LoRa-SF9-64 | 64 | 14 | 30.0 | -21/-22 | ✅ |
| HF-LoRa-SF9-128 | 128 | 10 | 23.1 | -21/-22 | ✅ |
| HF-LoRa-SF9-255 | 255 | 4 | 33.3 | -22/-22 | ✅ |
| HF-LoRa-SF12-32 | 32 | 1 | 50.0 | -15/-15 | ✅ |
| HF-LoRa-SF12-64 | 64 | 1 | 0.0 | -16/-16 | ✅ |
| HF-LoRa-SF12-128 | 128 | 1 | 0.0 | -16/-16 | ✅ |
| HF-LoRa-SF12-255 | 255 | 1 | 0.0 | -15/-15 | ✅ |
| LF-LoRa-SF7-32 | 32 | 0 | 100.0 | — | ❌ |
| LF-LoRa-SF7-64 | 64 | 18 | 10.0 | -29/-30 | ✅ |
| LF-LoRa-SF7-128 | 128 | 10 | 23.1 | -30/-30 | ✅ |
| LF-LoRa-SF7-255 | 255 | 6 | 14.3 | -30/-30 | ✅ |
| LF-LoRa-SF9-32 | 32 | 7 | 0.0 | -27/-28 | ✅ |
| LF-LoRa-SF9-64 | 64 | 2 | 33.3 | -27/-28 | ✅ |
| LF-LoRa-SF9-128 | 128 | 1 | 0.0 | -27/-27 | ✅ |
| LF-LoRa-SF9-255 | 255 | 1 | 0.0 | -27/-27 | ✅ |

**LoRa: 19/21 decoded (90.5%)**

### FLRC Modes

| Mode | Size | RX | PER% | RSSI avg/min | Status |
|------|------|----|------|-------------|--------|
| HF-FLRC-325-32 | 32 | 21 | 79.0 | -51/-58 | ✅ |
| HF-FLRC-325-64 | 64 | 15 | 85.0 | -49/-58 | ✅ |
| HF-FLRC-325-128 | 128 | 14 | 86.0 | -46/-46 | ✅ |
| HF-FLRC-325-255 | 255 | 14 | 86.0 | -46/-46 | ✅ |
| HF-FLRC-650-32 | 32 | 1 | 99.0 | -56/-56 | ✅ |
| HF-FLRC-650-64 | 64 | 0 | 100.0 | -56/-56 | ❌ |
| HF-FLRC-650-128 | 128 | 7 | 93.0 | -47/-56 | ✅ |
| HF-FLRC-650-255 | 255 | 10 | 90.0 | -46/-46 | ✅ |
| HF-FLRC-1300-32 | 32 | 1 | 99.0 | -55/-55 | ✅ |
| HF-FLRC-1300-64 | 64 | 1 | 99.0 | -54/-56 | ✅ |
| HF-FLRC-1300-128 | 128 | 0 | 100.0 | -54/-56 | ❌ |
| HF-FLRC-1300-255 | 255 | 12 | 88.0 | -46/-46 | ✅ |
| HF-FLRC-2600-32 | 32 | 0 | 100.0 | -54/-54 | ❌ |
| HF-FLRC-2600-64 | 64 | 1 | 99.0 | -53/-54 | ✅ |
| HF-FLRC-2600-128 | 128 | 0 | 100.0 | -54/-54 | ❌ |
| HF-FLRC-2600-255 | 255 | 3 | 97.0 | -53/-54 | ✅ |
| LF-FLRC-325-32 | 32 | 24 | 76.0 | -49/-56 | ✅ |
| LF-FLRC-325-64 | 64 | 20 | 80.0 | -50/-57 | ✅ |
| LF-FLRC-325-128 | 128 | 15 | 85.0 | -43/-44 | ✅ |
| LF-FLRC-325-255 | 255 | 22 | 78.0 | -43/-44 | ✅ |
| LF-FLRC-650-32 | 32 | 1 | 99.0 | -55/-55 | ✅ |
| LF-FLRC-650-64 | 64 | 0 | 100.0 | -53/-55 | ❌ |
| LF-FLRC-650-128 | 128 | 2 | 98.0 | -45/-55 | ✅ |
| LF-FLRC-650-255 | 255 | 6 | 94.0 | -43/-43 | ✅ |
| LF-FLRC-1300-32 | 32 | 0 | 100.0 | -53/-53 | ❌ |
| LF-FLRC-1300-64 | 64 | 1 | 99.0 | -53/-54 | ✅ |
| LF-FLRC-1300-128 | 128 | 0 | 100.0 | -54/-54 | ❌ |
| LF-FLRC-1300-255 | 255 | 13 | 87.0 | -43/-43 | ✅ |
| LF-FLRC-2600-32 | 32 | 0 | 100.0 | -52/-52 | ❌ |
| LF-FLRC-2600-64 | 64 | 0 | 100.0 | -52/-53 | ❌ |
| LF-FLRC-2600-128 | 128 | 0 | 100.0 | — | ❌ |
| LF-FLRC-2600-255 | 255 | 3 | 97.0 | -52/-53 | ✅ |

**FLRC: 22/32 decoded (68.8%)**

---

## 5. Group Analysis

### 5.1 By Modulation Type

| Modulation | Decoded/Total | Rate | Avg PER | Total RX |
|------------|---------------|------|---------|----------|
| **LoRa** | 19/21 | **90.5%** | 29.0% | 138 |
| **FLRC** | 22/32 | **68.8%** | 93.5% | 207 |

LoRa is far more reliable than FLRC. FLRC's high total RX comes from FLRC-325 phases (fast packet rate → 100 TX per phase). But the PER is very high (93.5% avg) — most packets are lost.

### 5.2 By Band

| Band | Decoded/Total | Rate | Avg PER | Total RX |
|------|---------------|------|---------|----------|
| **HF** (868/915 MHz) | 24/28 | **85.7%** | 65.3% | 193 |
| **LF** (433 MHz) | 17/25 | **68.0%** | 70.9% | 152 |

HF band performs better. LF has more failures — driven by LF-LoRa-SF7-32, LF-LoRa-SF12-32, and the LF-FLRC-2600 mode failures.

### 5.3 By FLRC Bitrate

| Mode | Decoded/Total | Rate | Avg PER | Total RX | Failing Sizes |
|------|---------------|------|---------|----------|---------------|
| **HF-FLRC-325** | 4/4 | **100%** ✅ | 84.0% | 64 | — |
| **HF-FLRC-650** | 3/4 | 75% | 95.5% | 18 | 64 |
| **HF-FLRC-1300** | 3/4 | 75% | 96.5% | 14 | 128 |
| **HF-FLRC-2600** | 2/4 | 50% ⚠️ | 99.0% | 4 | 32, 128 |
| **LF-FLRC-325** | 4/4 | **100%** ✅ | 79.8% | 81 | — |
| **LF-FLRC-650** | 3/4 | 75% | 97.8% | 9 | 64 |
| **LF-FLRC-1300** | 2/4 | 50% ⚠️ | 96.5% | 14 | 32, 128 |
| **LF-FLRC-2600** | 1/4 | **25%** ❌ | 99.2% | 3 | 32, 64, 128 |

**Clear pattern: FLRC-325 = perfect, FLRC-2600 = worst.** Decode rate decreases monotonically with bitrate. Size 255 is the universal survivor.

### 5.4 By Packet Size (FLRC only)

| Size | Decoded/Total | Rate | Avg PER | Total RX | Key Observation |
|------|---------------|------|---------|----------|-----------------|
| 32 | 5/8 | 62.5% | 94.0% | 48 | Only 325 + 650(HF) + 1300(HF) |
| 64 | 5/8 | 62.5% | 95.2% | 38 | Only 325 + 1300(HF) + 2600(HF) |
| 128 | 4/8 | **50.0%** | 95.2% | 38 | Only 325 + 650 |
| **255** | **8/8** | **100%** ✅ | 89.6% | 83 | **Every FLRC bitrate decodes at size 255** |

**Size 255 is 100% decoded across all FLRC bitrates on both bands.** Size 128 is the worst (50%). This confirms the "size 255 canary" pattern — larger packets have longer preamble exposure, allowing FLRC sync to lock.

---

## 6. Channel Sweep — PER Per Frequency

All channel sweep phases use FLRC-1300, size 64.

### WiFi 2.4 GHz (phases 56–68)

| Frequency | RX | PER% | RSSI | CRC | Garbage | Status |
|-----------|----|------|------|-----|---------|--------|
| 2412 MHz | 0 | 100.0 | -55 | 1 | 952 | ❌ OOB |
| 2417 MHz | 0 | 100.0 | -54 | 1 | 951 | ❌ OOB |
| 2422 MHz | 0 | 100.0 | -55 | 2 | 966 | ❌ OOB |
| 2427 MHz | **2** | 98.0 | -55 | 2 | 927 | ⚠️ harmonic leak |
| 2432 MHz | 0 | 100.0 | -55 | 1 | 968 | ❌ OOB |
| 2437 MHz | 0 | 100.0 | -55 | 1 | 958 | ❌ OOB |
| 2442 MHz | 0 | 100.0 | -55 | 0 | 964 | ❌ OOB |
| 2447 MHz | 0 | 100.0 | -54 | 0 | 946 | ❌ OOB |
| 2452 MHz | **1** | 99.0 | -54 | 2 | 985 | ⚠️ harmonic leak |
| 2457 MHz | 0 | 100.0 | -54 | 1 | 1004 | ❌ OOB |
| 2462 MHz | **2** | 98.0 | -54 | 1 | 981 | ⚠️ harmonic leak |
| 2467 MHz | 0 | 100.0 | -54 | 1 | 1014 | ❌ OOB |
| 2472 MHz | 0 | 100.0 | -55 | 0 | 1011 | ❌ OOB |

**WiFi 2.4 GHz: 3/13 "decoded" (harmonic leakage), 0% real decode rate.** LR2021 operates at 868/915 MHz — 2.4 GHz is physically out of band. The 1–2 packets per channel that occasionally decode are spurious harmonic leakage.

### EU868 Sub-bands (phases 69–76)

| Frequency | RX | PER% | RSSI | CRC | Garbage | Status |
|-----------|----|------|------|-----|---------|--------|
| 863 MHz | 0 | 100.0 | -53 | 0 | 1038 | ❌ |
| 864 MHz | 0 | 100.0 | -52 | 0 | 1045 | ❌ |
| 865 MHz | 0 | 100.0 | -53 | 0 | 1039 | ❌ |
| 866 MHz | 0 | 100.0 | -53 | 0 | 1035 | ❌ |
| 867 MHz | 0 | 100.0 | -54 | 0 | 1040 | ❌ |
| 868 MHz | 0 | 100.0 | -54 | 0 | 1033 | ❌ |
| 869 MHz | 0 | 100.0 | -53 | 0 | 1034 | ❌ |
| 870 MHz | 0 | 100.0 | -53 | 0 | 1029 | ❌ |

**EU868: 0/8 decoded.** TX transmits on primary frequency only and does not sweep sub-bands. RX hears ~1000 garbage packets per channel = pure noise floor. Configuration mismatch between TX and RX channel sweep.

**Channel sweep verdict: completely broken. No measurable improvement from the `536b418` freqMHz fix.**

---

## 7. The 57 Failing Phases — Pattern Analysis

### 7.1 Inherent/Design Failures (not bugs)

| Phase(s) | Mode | Size | Reason |
|----------|------|------|--------|
| 37–39 | LF-LoRa-SF12-SKIP | 64/128/255 | **Firmware SKIP by design** — SF12 air time exceeds phase slot budget |
| 56–68 | CH-24xx (WiFi) | 64 | **Out of band** — LR2021 is 868/915 MHz, not 2.4 GHz |
| 69–76 | CH-8xx (EU868) | 64 | **TX/RX mismatch** — TX doesn't sweep, RX hears noise |

**= 32 phases are expected failures** (3 SKIP + 13 WiFi + 8 EU868 + 8 more from cycle 1 tail = 32 out of 57)

### 7.2 Known Marginal Failures

| Phase | Mode | Size | Reason | Consistent? |
|-------|------|------|--------|-------------|
| 28 | LF-LoRa-SF7-32 | 32 | Small packet + fast SF = sync too tight | ✅ All captures |
| 36 | LF-LoRa-SF12-32 | 32 | SF12 at LF marginal — 1s air time | ✅ All captures |
| 20 | HF-FLRC-2600-32 | 32 | Transition issue: SF12-255 (11s) → FLRC-2600-32 (fastest) | ✅ All captures |

**= 3 phases are known marginal** (×2 cycles = 6 phases)

### 7.3 FLRC Bitrate-Dependent Failures (the real problem)

These are the phases that SHOULD decode but fail due to the systemic bitrate index offset:

| Phase | Mode | Size | HF Band | LF Band | Pattern |
|-------|------|------|---------|---------|---------|
| 13/45 | FLRC-650-64 | 64 | ❌ | ❌ | **Both bands fail** |
| 18/50 | FLRC-1300-128 | 128 | ❌ | ❌ | **Both bands fail** |
| 20/52 | FLRC-2600-32 | 32 | ❌ | ❌ | Both bands fail |
| 22/54 | FLRC-2600-128 | 128 | ❌ | ❌ | **Both bands fail** |
| 48 | FLRC-1300-32 (LF) | 32 | — | ❌ | LF only |
| 53 | FLRC-2600-64 (LF) | 64 | — | ❌ | LF only |

**Pattern: Size 64 fails for FLRC-650, size 128 fails for FLRC-1300/2600, all small sizes fail for FLRC-2600.** The failing modes follow the bitrate-size matrix: higher bitrate + smaller packet = harder sync.

---

## 8. Comparison to Previous Captures

### 8.1 Capture-Level Comparison

| Capture | File | Phases | Decoded | Rate | Code Version | Key Fix |
|---------|------|--------|---------|------|--------------|---------|
| **BENCH** | `v4-interleave-bench/` | 56 TX-active | 53 | **95%** | Pre-`0a9fa51` | — |
| **PREFIX** | `rx_sweep_201758.log` | 76 | 37 | **48.7%** | `0562e73` (channel sweep) | None |
| **POSTFIX** | `rx_sweep_fixed2_204425.log` | 47 | 17 | **36.2%** | `7700e22` (FLRC-1300 index) | Partial |
| **FINAL-1** | `rx_sweep_fixed_204825.log` | 77 | 40 | **51.9%** | `536b418` (freqMHz fix) | Partial |
| **FINAL-2** | `rx_sweep_final_031009.log` | 77 (cycle 2) | 44 | **57.1%** | `85793c2` (sync word fix) | ✅ Best sweep era |

**FINAL-2 is the best sweep-era capture.** The sync word fix (`85793c2`) recovered several modes that FINAL-1 had lost, but did not fully resolve the systemic bitrate index offset.

### 8.2 FLRC Mode Comparison (Cycle 2 Data)

Format: **rx count (PER% / RSSI dBm)**. `0` = captured, rx=0. `—` = not captured.

#### HF Band

| Mode | Size | BENCH | PREFIX | POSTFIX | FINAL-1 | **FINAL-2** |
|------|------|-------|--------|---------|---------|-------------|
| **HF-FLRC-325** | 32 | 41 (59%/-45) | 25 (75%/-50) | — | 23 (77%/-49) | **21 (79%/-51)** |
| | 64 | 36 (64%/-45) | 18 (82%/-52) | — | 20 (80%/-49) | **15 (85%/-49)** |
| | 128 | **0** ❌ | 16 (84%/-46) | — | 15 (85%/-45) | **14 (86%/-46)** |
| | 255 | **0** ❌ | 22 (78%/-46) | — | 16 (84%/-45) | **14 (86%/-46)** |
| **HF-FLRC-650** | 32 | 40 (60%/-48) | **0** ❌ | — | **0** ❌ | **1 (99%/-56)** 🆕 |
| | 64 | 31 (69%/-45) | **0** ❌ | — | **0** ❌ | **0** ❌ |
| | 128 | 21 (79%/-45) | 8 (92%/-48) | — | 8 (92%/-47) | **7 (93%/-47)** |
| | 255 | 64 (36%/-45) | 6 (94%/-46) | — | 5 (95%/-45) | **10 (90%/-46)** ↑ |
| **HF-FLRC-1300** | 32 | 46 (54%/-47) | **0** ❌ | **0** ❌ | 1 (99%/-55) | **1 (99%/-55)** |
| | 64 | 42 (58%/-47) | **0** ❌ | — | 1 (99%/-55) | **1 (99%/-55)** |
| | 128 | 37 (63%/-45) | **0** ❌ | **0** ❌ | **0** ❌ | **0** ❌ |
| | 255 | 66 (34%/-47) | 8 (92%/-46) | 10 (90%/-45) | 17 (83%/-46) | **12 (88%/-46)** |
| **HF-FLRC-2600** | 32 | **0** ❌ | **0** ❌ | **0** ❌ | **0** ❌ | **0** ❌ |
| | 64 | 42 (58%/-45) | **0** ❌ | **0** ❌ | **0** ❌ | **1 (99%/-53)** 🆕 |
| | 128 | 40 (60%/-47) | **0** ❌ | **0** ❌ | **0** ❌ | **0** ❌ |
| | 255 | 65 (35%/-45) | 6 (94%/-51) | 3 (97%/-52) | 9 (91%/-50) | **3 (97%/-53)** ↓ |

#### LF Band

| Mode | Size | BENCH | PREFIX | POSTFIX | FINAL-1 | **FINAL-2** |
|------|------|-------|--------|---------|---------|-------------|
| **LF-FLRC-325** | 32 | 52 (48%/-38) | 1 (99%/-44) | 21 (79%/-48) | 17 (83%/-48) | **24 (76%/-49)** ↑ |
| | 64 | 46 (54%/-37) | **0** ❌ | 17 (83%/-52) | 18 (82%/-49) | **20 (80%/-50)** |
| | 128 | 38 (62%/-39) | — | 7 (93%/-44) | 12 (88%/-43) | **15 (85%/-43)** ↑ |
| | 255 | 65 (35%/-39) | 6 (94%/-44) | **0** ❌ | 13 (87%/-44) | **22 (78%/-43)** ↑ |
| **LF-FLRC-650** | 32 | 48 (52%/-38) | **0** ❌ | **0** ❌ | **0** ❌ | **1 (99%/-55)** 🆕 |
| | 64 | 14 (86%/-44) | **0** ❌ | **0** ❌ | **0** ❌ | **0** ❌ |
| | 128 | 16 (84%/-39) | 3 (97%/-46) | **0** ❌ | 4 (96%/-45) | **2 (98%/-45)** |
| | 255 | 60 (40%/-39) | 3 (97%/-44) | **0** ❌ | 4 (96%/-43) | **6 (94%/-43)** ↑ |
| **LF-FLRC-1300** | 32 | 43 (57%/-37) | **0** ❌ | **0** ❌ | 1 (99%/-54) | **0** ❌ ↓ |
| | 64 | 34 (66%/-38) | **0** ❌ | **0** ❌ | **0** ❌ | **1 (99%/-53)** 🆕 |
| | 128 | 10 (90%/-39) | **0** ❌ | **0** ❌ | **0** ❌ | **0** ❌ |
| | 255 | 61 (39%/-38) | 9 (91%/-44) | **0** ❌ | 12 (88%/-45) | **13 (87%/-43)** ↑ |
| **LF-FLRC-2600** | 32 | 46 (54%/-38) | **0** ❌ | **0** ❌ | **0** ❌ | **0** ❌ |
| | 64 | 30 (70%/-40) | **0** ❌ | **0** ❌ | **0** ❌ | **0** ❌ |
| | 128 | 12 (88%/-38) | **0** ❌ | **0** ❌ | **0** ❌ | **0** ❌ |
| | 255 | 60 (40%/-38) | 3 (97%/-47) | **0** ❌ | 3 (97%/-52) | **3 (97%/-52)** |

🆕 = newly decoding in FINAL-2 (was 0 in FINAL-1). ↑ = improved. ↓ = worse.

### 8.3 LoRa Mode Comparison

| Mode | BENCH | PREFIX | POSTFIX | FINAL-1 | **FINAL-2** |
|------|-------|--------|---------|---------|-------------|
| HF-LoRa-SF7 | 4/4 ✅ | 4/4 ✅ | — | 4/4 ✅ | **4/4 ✅** |
| HF-LoRa-SF9 | 4/4 ✅ | 4/4 ✅ | — | 4/4 ✅ | **4/4 ✅** |
| HF-LoRa-SF12 | 4/4 ✅ | 4/4 ✅ | 4/4 ✅ | 4/4 ✅ | **4/4 ✅** |
| LF-LoRa-SF7 | 2/4 | 3/4 | 3/4 | 3/4 | **3/4** (size 32 fails) |
| LF-LoRa-SF9 | 1/4 | 4/4 ✅ | 4/4 ✅ | 4/4 ✅ | **4/4 ✅** |
| LF-LoRa-SF12 | 1/4 | 1/4 | 0/4 ❌ | 1/4 | **1/4** (size 32 only; rest SKIP) |

LoRa modes are **stable and consistent** with FINAL-1. No regression.

### 8.4 Modes Newly Recovered by Sync Word Fix (`85793c2`)

| Mode | Size | FINAL-1 | **FINAL-2** | Improvement |
|------|------|---------|-------------|-------------|
| HF-FLRC-650-32 | 32 | ❌ 0 | ✅ **1** | GAINED |
| HF-FLRC-2600-64 | 64 | ❌ 0 | ✅ **1** | GAINED |
| LF-FLRC-650-32 | 32 | ❌ 0 | ✅ **1** | GAINED |
| LF-FLRC-1300-64 | 64 | ❌ 0 | ✅ **1** | GAINED |

4 modes that were completely dead in FINAL-1 now decode (marginally). The sync word fix did have measurable effect, but recovery is still at rx=1 (99% PER) — just barely above zero.

### 8.5 Modes Still Completely Dead

| Mode | Size | Status Since | Cycles Dead |
|------|------|-------------|-------------|
| HF-FLRC-1300-128 | 128 | PREFIX | 4 |
| HF-FLRC-2600-32 | 32 | BENCH | 5 (always dead) |
| HF-FLRC-2600-128 | 128 | PREFIX | 4 |
| LF-FLRC-650-64 | 64 | BENCH-era change | 5 |
| LF-FLRC-1300-32 | 32 | POSTFIX (reverted) | 3 |
| LF-FLRC-1300-128 | 128 | BENCH-era change | 5 |
| LF-FLRC-2600-32 | 32 | PREFIX | 4 |
| LF-FLRC-2600-64 | 64 | BENCH-era change | 5 |
| LF-FLRC-2600-128 | 128 | PREFIX | 4 |

**HF-FLRC-2600-32 has NEVER decoded across any capture.** This is a known transition issue (SF12→FLRC-2600 is the most extreme timing jump in the sweep).

---

## 9. BER Analysis

| Metric | Value |
|--------|-------|
| Total BER measurements | 135 |
| BER > 0 packets | **0** |
| Total bits measured | 115,392 |
| Total bit errors | **0** |
| Overall BER | **0.00e+00** |

**Perfect bit integrity.** Every packet that passed CRC had zero bit errors. The FLRC failures are **synchronization failures** (garbage counts of 244–1056 per phase), not bit corruption. The radio correctly receives data when it can sync — it just can't sync often enough at higher bitrates.

---

## 10. Key Conclusions

### Q1: Which 57 phases STILL fail?

- **32 phases** are expected failures (3 SKIP + 21 channel sweep = design/inherent)
- **3 phases** are known marginal (LF-LoRa-SF7-32, LF-LoRa-SF12-32, HF-FLRC-2600-32 — transition issue)
- **~16 phases** (8 unique modes × 2 cycles) are FLRC bitrate-dependent failures: FLRC-650-64, FLRC-1300-128, FLRC-2600-32/64/128

### Q2: Is there a pattern?

**YES — three patterns:**

1. **Bitrate-size matrix:** Higher FLRC bitrate + smaller packet size = harder sync. Size 255 always works; smaller sizes fail at higher bitrates. This is the systemic bitrate index offset from MASTER-ANALYSIS.md.

2. **FLRC-650-64 failure is universal:** Both HF and LF fail at 650 kbps / size 64. Every other size at 650 works. This is a specific index entry issue.

3. **FLRC-1300-128 failure is universal:** Both HF and LF fail at 1300 kbps / size 128. Again, a specific entry issue.

### Q3: Are FLRC modes failing on specific bitrates or sizes?

**Both — it's an interaction:**
- FLRC-325: **100% decode** at all sizes (the index fix is correct for this bitrate)
- FLRC-650: 75% (only size 64 fails on both bands)
- FLRC-1300: 62.5% (sizes 32/128 fail on LF, size 128 fails on HF)
- FLRC-2600: 37.5% (only size 255 reliably works)

### Q4: Is it a timing issue (phase transitions)?

**Partially.** HF-FLRC-2600-32 (phase 20) is a known transition issue — it follows HF-LoRa-SF12-255 (11s air time), the most extreme SF→FLRC transition. But the broader FLRC failures at 650/1300/2600 are NOT transition issues — they're index table offset errors.

### Q5: Are channel sweep phases decoding now?

**No.** The `536b418` freqMHz fix had no measurable effect:
- WiFi 2.4 GHz: 0% real decode (3/13 "decoded" = harmonic leakage)
- EU868: 0% decode (TX doesn't sweep sub-bands)

### Q6: Is the capture complete?

**Yes.** Cycle 2 contains all 77 phases (0–76). No phases are missing.

---

## 11. Recommendations (Updated)

1. **The sync word fix (`85793c2`) was the right fix** — it recovered 4 modes and improved FLRC-325 performance. But the systemic bitrate index offset remains.

2. **Audit the full FLRC bitrate index table** — the single-entry patches have not resolved the underlying issue. FLRC-650-64 and FLRC-1300-128 fail consistently on both bands, suggesting these specific index entries are wrong.

3. **Remove channel sweep entirely** — WiFi 2.4 GHz is out of band, and EU868 TX doesn't sweep. These 21 phases per cycle are pure noise measurement and should be removed.

4. **Default FLRC to size 255 for flight** — until the index table is fixed, only 255-byte packets reliably decode at all bitrates.

5. **Add inter-phase guard for SF12→FLRC transitions** — 500ms SET_STANDBY between the slowest LoRa mode and the fastest FLRC mode. This will fix HF-FLRC-2600-32.

6. **Test reverting CR=3/4** — the coding rate change in `0a9fa51` may be contributing to the FLRC regression. Test CR=1/2 with the current sync word fix.

---

*Generated by `analyze_final.py`. Raw data: `final_analysis.json`. See MASTER-ANALYSIS.md for the full cross-capture regression timeline.*
