# Firmware Harmonization Gap Analysis

**Date:** 2026-08-20  
**Spec:** `docs/data-handover/FIRMWARE-HARMONIZATION-2026-08-19.md`  
**Repos checked:**  
- E80: `~/repos/balloon-e80bench/` (branch `feat/persist-tx-seq`)  
- C3: `~/repos/balloon-fresh/mesh-stack/flrc-bench-espidf/` (branch `feat/c3-harmonization`)  
- RP2040: `~/repos/balloon-fresh/firmware/rp2040/` (branch `feat/c3-harmonization`)  

---

## MUST-HAVE (M1–M7)

| Req | E80 | C3 | RP2040 | Status | Evidence |
|-----|-----|-----|--------|--------|----------|
| **M1** FW_HASH in boot banner | ✅ | ✅ | ✅ | **Done** | E80: `bench_banner.h:24` — `fw=FW_HASH=<sha7>`, injected via `CMakeLists.txt:77` / `Makefile:13`; C3: `range_test.cpp:607` — `FW_HASH=%s`, injected via `CMakeLists.txt:8-27`; RP2040: `multi_radio_sweep_gps_v4.cpp:64` prints `FW_GIT_HASH`, injected via `scripts/inject_build_id.py` / `tools/inject_git_version.py` |
| **M2** Capture tool firmware-hash gate | ✅ | ✅ | ✅ | **Done** | E80: `tools/pre_flight_check.sh:77` — `extract_fw_hash()`, checks TX/RX hash; C3: `monitor_range.py:82-113` — refuses capture if no valid `FW_HASH`; RP2040: same C3 tools at `~/repos/balloon-fresh/tools/firmware_hash_gate.py` (shared); also `rx_range_logger.py` and `capture_sweep.py` write `SESSION_START` headers |
| **M3** Per-packet output | ✅ | ✅ | ✅ | **Done** | E80: `bench.c:964-966` — emits PKT line per received packet; C3: `range_test.cpp:458,510` — emits PKT per packet; RP2040: `pkt_harmonized_rx.cpp:732-757` — `emitPktLine()` emits 23-field PKT per packet |
| **M4** 23-field common PKT format | ✅ | ✅ | ✅ | **Done** | E80: `bench_pkt.c:56-74` — 23-field `PKT,%lu,...` format with all fields; C3: `range_test.cpp:510` — `PKT,%s,%s,%u,...` 23-field format; RP2040: `pkt_harmonized_rx.cpp:733` — `PKT,%s,%s,%u,...` 23-field format. All emit: session_id, config_id, replicate, seq, ts_ms, rssi_dbm, snr_db, crc_ok, bit_err, bytes_bad, freq_hz, mod, sf, bw_khz, cr, power_dbm, pkt_size, gps_fix, gps_lat, gps_lon, gps_alt, gps_sats, gps_hdop |
| **M5** Config identifier in every data line | ✅ | ✅ | ✅ | **Done** | E80: `bench_pkt.c:59` — `config_id` in PKT line + radio params (freq_hz, mod, sf, bw_khz, cr, power_dbm, pkt_size); C3: `range_test.cpp:512` — `config_id` in PKT; RP2040: `pkt_harmonized_rx.cpp:735` — `config_id` in PKT. All three include full radio params in every PKT line |
| **M6** Non-resetting seq numbers | ✅ | ✅ | ✅ | **Done** | E80: `bench.c:71` — `static uint32_t tx_seq = 0`, increments at `bench.c:901`, `bench_get_tx_seq()` at `bench.c:1095`; test `test_bench_seq.c` verifies non-reset; C3: `range_test.cpp:110` — `uint32_t seqCounter = 0` persistent, never resets; test `test_seq_counter.c`; RP2040: `pkt_harmonized_rx.cpp:64` — `static uint32_t pktSeq = 0`, comment at line 8: "M6: Non-resetting uint32 seq counter" |
| **M7** CRC-failed packet logging | ✅ | ✅ | ✅ | **Done** | E80: `bench.c:970-990` — `RB_EVT_RX_CRC` case emits PKT with `crc_ok=0`, RSSI populated; C3: `range_test.cpp:443-459` — `C3-4/M7` comment, emits PKT with `crc_ok=0`; RP2040: `pkt_harmonized_rx.cpp:783-813,934-950` — `M7` comments, emits PKT with `crc_ok=0` and RSSI |

---

## NICE-TO-HAVE (N1–N5)

| Req | E80 | C3 | RP2040 | Status | Evidence |
|-----|-----|-----|--------|--------|----------|
| **N1** Per-packet SNR for LoRa | ✅ | ✅ | ✅ | **Done** | E80: `bench_pkt.c:32,64` — `snr_db = snr_qdb / 4` in PKT line; C3: `range_test.cpp:490-492` — `snr_db = radio->getSNR()` for LoRa mode; RP2040: `pkt_harmonized_rx.cpp:802,942,1047` — `snr_db = rfGetLoraSnr()` for LoRa, 0 for FLRC |
| **N2** Both RSSI fields (rssi_pkt + rssi_signal) | ⚠️ Partial | ❌ | ❌ | **Gap** | E80: `radio_bench.c:422-423,447` — reads `rssi_pkt_in_dbm` + `rssi_pkt_half_dbm_count` from `GetLoraPacketStatus()`, but only emits one `rssi_dbm` field in PKT line — `rssi_signal_pkt_in_dbm` available in struct (`lr20xx_radio_lora_types.h:308`) but not output; C3: only `getRSSI()` called, no `rssi_signal` field; RP2040: only single RSSI in PKT line. None emit both RSSI fields. |
| **N3** Gap/duty-cycle column | ❌ | ❌ | ❌ | **Gap** | E80: `gap_us` is a TX-side command parameter (`bench_cmd.h`, `e80_bench_ctl.py`) but not emitted in PKT or summary lines; C3: no `gap_us`/`duty` in output; RP2040: no `gap_us`/`duty` in output. No firmware emits a gap or duty-cycle column in per-packet or summary data. |
| **N4** Voltage/temperature | ❌ | ❌ | ❌ | **Gap** | E80: STM32 HAL ADC temp sensor defines exist (`stm32f1xx_ll_adc.h`) but no firmware code reads or emits VBAT/TEMP; C3: ESP32 `CONFIG_SOC_TEMP_SENSOR_SUPPORTED=y` in `sdkconfig` but no code reads/emits it; RP2040: no ADC/VBAT/TEMP code found. None emit voltage or temperature. |
| **N5** Attenuator column | ❌ | ❌ | ❌ | **Gap** | No `atten_db` or attenuator-related code found in any of the three firmware repos. Not implemented anywhere. |

---

## OPTIONAL (O1–O4)

| Req | E80 | C3 | RP2040 | Status | Evidence |
|-----|-----|-----|--------|--------|----------|
| **O1** Config table at session start | ⚠️ Partial | ⚠️ Partial | ❌ | **Partial** | E80: `bench.c:803-818` — `BENCH_CMD_CONFIG` sets config_id + replicate, emits `CONFIG_START` marker, but no full config table (freq, mod, sf, etc. as a table emission); C3: `range_test.cpp:557-568` — `CONFIG <id> <replicate>` sets config_id, emits `CONFIG_START` marker, no full config table; RP2040: no CONFIG table emission found. None emit a full configuration table at session start. |
| **O2** TX-side per-packet log | ❌ | ❌ | ❌ | **Gap** | E80: no `TX_PKT` emission found; C3: no `TX_PKT` emission found; RP2040: `TX_PKT_COUNT` is a loop constant in `flrc_timing_profiler.cpp` and `flrc_raw_tx.cpp` but not a per-packet TX log line. None emit a `TX_PKT` per-packet log on the TX side. |
| **O3** RSSI calibration table | ❌ | ❌ | ❌ | **Gap** | No `RSSI_CAL` or RSSI calibration table emission found in any of the three firmware repos. |
| **O4** CONFIG_START transition markers | ✅ | ✅ | ❌ | **Partial** | E80: `bench_pkt.c:85-91` — `bench_pkt_config_start()` formats `CONFIG_START,<config_id>,<replicate>,<ts_ms>`; `bench.c:811-818` emits it; test `test_bench_config_start.c`; C3: `range_test.cpp:566` — `printf("CONFIG_START,...")`; RP2040: no CONFIG_START marker found in `pkt_harmonized_rx.cpp` or other RP2040 sources. |

---

## Summary

| Category | Total | Done | Partial | Gap |
|----------|-------|------|---------|-----|
| **MUST-HAVE (M1–M7)** | 7 | 7 | 0 | 0 |
| **NICE-TO-HAVE (N1–N5)** | 5 | 1 | 1 | 3 |
| **OPTIONAL (O1–O4)** | 4 | 0 | 2 | 2 |
| **Total** | 16 | 8 | 3 | 5 |

### Phase 1 (MUST-HAVE): ✅ COMPLETE
All 7 MUST-HAVE items (M1–M7) are implemented across all three rigs (E80, C3, RP2040).

### Phase 2 (NICE-TO-HAVE): Partially done
- **N1** (per-packet SNR): ✅ Done on all rigs
- **N2** (both RSSI fields): ⚠️ E80 has access to both fields in the radio driver struct but only emits one; C3 and RP2040 don't access the second field at all
- **N3** (gap/duty-cycle): ❌ Not implemented on any rig
- **N4** (voltage/temperature): ❌ Not implemented on any rig (hardware support exists but unused)
- **N5** (attenuator column): ❌ Not implemented on any rig

### Phase 4 (OPTIONAL): Partially done
- **O1** (config table): ⚠️ E80 and C3 emit CONFIG_START markers with config_id but not a full config table; RP2040 has neither
- **O2** (TX-side per-packet log): ❌ Not implemented anywhere
- **O3** (RSSI calibration table): ❌ Not implemented anywhere
- **O4** (CONFIG_START markers): ✅ E80 and C3; ❌ RP2040 missing