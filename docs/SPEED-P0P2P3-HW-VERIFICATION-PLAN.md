# Hardware Verification Plan — SPEED-P0 / P2 / P3 (ESP32-C3 ↔ LR2021, 2.4 GHz FLRC)

**Status:** Operator-ready · **Platform:** 2× ESP32-C3 SuperMini + NiceRF LR2021 · **Track:** ESP32 speed (separate from the RP2040 track on `track/speed-testing`)
**Goal:** Verify the three untested raw-SPI TX firmware commits and measure the 838 kbps → 2.5 Mbps speed-record ladder.
**Master plan / root-cause analysis:** `~/comprehensive-plan-lr2021-speed-records.md`
**Firmware under test:** `mesh-stack/flrc-bench-espidf/main/bench_main.cpp`

---

## 0. Commits under test (read this first — command vocabulary differs per commit!)

All three commits branch from the same base (`36952f7`) and modify the **interactive** `bench_main.cpp`. **The raw-TX command is NOT the same on every branch** — get this wrong and the test produces nothing.

| Tag | Commit | Branch | What it adds | Raw-TX trigger command |
|-----|--------|--------|--------------|------------------------|
| **SPEED-P0** | `44ad093` | `fix/raw-tx-packet-params` | `rawSetFlrcPacketParams()` (SET_FLRC_PACKET_PARAMS `0x0249`) — fixes the **0/0 blocker** (radio got bytes but never learned payload length) | `RAWTX` (calls `runRawTx()`) |
| **SPEED-P2** | `67c0552` | `feat/radiolib-bypass-tx` | Zero-overhead raw-SPI bypass + `EspHalC3` `spi_device_polling_transmit`; `runRawTx()` rewritten | `RAWTX` (calls `runRawTx()`) |
| **SPEED-P3** | `45b57ab` | `feat/flrc-max-params` | `MODE_FLRC_MAX` + `runTxMax()` + `runSweep()`; `rawSetFlrcModParams()` (`0x0248`) — the **BR=650 fix** (sends CR explicitly) | `MODE FLRC_MAX` then `RUN` (calls `runTxMax()`); `SWEEP` for the matrix |
| **MERGE-FIX** | `dc9d2e2` | `feat/speed-merge-fix` | P3 **+** shaping correction `0x05` (BT=0.5, not the generic `0x02` enum) **+** removed redundant IRQ clear in hot loop | same as P3 |

> **RECOMMENDED PRIMARY TARGET = `dc9d2e2` (MERGE-FIX).** It is P3 with the two correctness fixes applied. Test P0/P2 individually for *isolation/debugging* (to attribute throughput to each change), then confirm the headline number on MERGE-FIX. Topology: `36952f7` → `{44ad093, 67c0552, 45b57ab(=6c18743)}`; `dc9d2e2` descends from P3.

**Command vocab cheat-sheet:**
- P0/P2: `MODE FLRC|LORA`, `FREQ/BR/CR/SIZE/COUNT/PWR/DELAY/PREAMBLE`, `ROLE TX|RX`, `RUN` (RadioLib), **`RAWTX`** (raw-SPI), `CONFIG`, `HELP`. *(no `MODE FLRC_MAX`, no `SWEEP`)*
- P3/merge-fix: adds **`MODE FLRC_MAX`**, **`SWEEP`**; `RUN` dispatches to `runTxMax()` when mode is `FLRC_MAX`, else `runTx()` (RadioLib).

**FLRC parameter codes (from `bench_main.cpp`):**
- Bitrate→nibble (`brToNibble`): `2600→0x00 2080→0x01 1300→0x02 1040→0x03 650→0x04 520→0x05 325→0x06 260→0x07`
- Coding rate: `1/2=0x00  3/4=0x01  1_0(uncoded)=0x02  2/3=0x03`
- Default `cfg` on P3/merge-fix is **FREQ=868 / BW=125** (LoRa-ish) — you MUST set `FREQ 2450` explicitly. P0/P2 default to 2450/2000. **Always set FREQ explicitly on every board.**

---

## 1. Pre-flight checklist (do all before touching a board)

### 1a. Hardware
- [ ] 2× ESP32-C3 SuperMini + NiceRF LR2021 modules wired per `docs/breadboard-wiring-guide.md` (SPI pins SCK6/MISO2/MOSI7/NSS10/BUSY4/RST3/DIO9-5).
- [ ] Both boards powered, antennas attached (or <1 m apart with intentional radiators — 2.4 GHz FLRC at +22 dBm is loud; keep ≥10 cm apart to avoid RX front-end overload).
- [ ] **Identify which physical board is TX vs RX** — label them now.

### 1b. Discover serial ports (DO NOT trust "ACM2/ACM3" — ports re-enumerate)
The task brief says `/dev/ttyACM2=TX, /dev/ttyACM3=RX`, but **those were a snapshot**. Right now only `/dev/ttyUSB0-2` exist (the ESP32-C3 bench boards are not connected). ESP32-C3 SuperMini uses **native USB CDC → `/dev/ttyACM*`** when plugged.

```bash
# Plug in BOTH C3 boards, then discover. C3 = native USB (ACM). RP2040 also = ACM.
for d in /dev/ttyACM* /dev/ttyUSB*; do
  [ -e "$d" ] || continue
  echo "=== $d ==="
  esptool.py --port "$d" chip_id 2>/dev/null | grep -i 'chip id\|Detecting' || echo "(not esptool: maybe RP2040/bridge)"
  udevadm info -q property "$d" 2>/dev/null | grep -E 'ID_SERIAL_SHORT|ID_MODEL' | head -2
done
```
- [ ] Confirmed TX board port = `______` (chip_id = `________`)
- [ ] Confirmed RX board port = `______` (chip_id = `________`)

> **Board-lock / coordination note:** `balloon-fresh/AGENTS.md` defines a hard device lock + flash-queue for the **3× ESP32-S3 TollGate boards** (`/dev/ttyACM0,1,3`). Those are a *different* hardware set from these C3+LR2021 boards, but ACM numbers can collide when many boards are plugged in. If you share this machine with the TollGate/balloon tracks, add a row to `~/repos/balloon-fresh/docs/coordination/FLASH-QUEUE.md` before flashing and re-discover ports after every replug.

### 1c. Build environment (ESP-IDF 5.4.1 — specific known-good invocation)
From prior sessions: the default `source export.sh` **fails** because system python3 is 3.11 but only the `idf5.4_py3.13_env` venv is complete. Use this **exact one-liner in a single terminal call** (do not split — IDF tool env vars do not persist across calls and cause a spurious `gdbinit.cmake:40` error):

```bash
export IDF_PYTHON_ENV_PATH=/home/c03rad0r/.espressif/python_env/idf5.4_py3.13_env \
  && source ~/esp/esp-idf/export.sh \
  && cd ~/repos/balloon-fresh/mesh-stack/flrc-bench-espidf
```
- [ ] `idf.py --version` prints 5.4.1 and `which idf.py` resolves.

### 1d. Build-mode trap (CRITICAL)
`sdkconfig.defaults` ships with **`CONFIG_BENCH_MODE_RAW_RX=y`**. With that set, the active `app_main` comes from `esp32_raw_rx.cpp` and the **interactive `bench_main.cpp` compiles to an empty translation unit** — you will get a serial prompt that does nothing. The Kconfig `choice` default is `BENCH_MODE_INTERACTIVE`, but `sdkconfig.defaults` overrides it.

**Fix:** before building, select Interactive mode.
- Menuconfig: `idf.py menuconfig` → `Benchmark mode` → **`Interactive (serial commands)`**. Save.
- Or hard-set in `sdkconfig`: ensure `CONFIG_BENCH_MODE_INTERACTIVE=y` and **all other `CONFIG_BENCH_MODE_*` are `is not set`** (especially `RAW_RX`, `RAW_TX`).
- [ ] Confirmed `CONFIG_BENCH_MODE_INTERACTIVE=y`, no other BENCH_MODE set.

---

## 2. Branch strategy & build/flash procedure

Checkout order (isolation → integration). The RX board firmware is **constant across all tests** (interactive RadioLib RX), so you only re-flash the **TX** board per commit. Build RX firmware once.

### 2a. Build & flash the RX board (ONCE — constant for all tests)
```bash
# (env from §1c already active, in flrc-bench-espidf)
git checkout master          # or any commit; RX path is RadioLib runRx() — stable
idf.py set-target esp32c3    # only first time
idf.py menuconfig            # §1d: Interactive mode
idf.py build
idf.py -p <RX_PORT> flash monitor   # use the RX port discovered in §1b
```
On the RX serial console, leave it at the prompt. You will configure it per-test (§3).

### 2b. Build & flash the TX board per commit
```bash
# Checkout the commit under test:
git checkout 44ad093   # SPEED-P0   (branch fix/raw-tx-packet-params)
# git checkout 67c0552  # SPEED-P2   (branch feat/radiolib-bypass-tx)
# git checkout 45b57ab  # SPEED-P3   (branch feat/flrc-max-params)
# git checkout dc9d2e2  # MERGE-FIX  (branch feat/speed-merge-fix)  ← primary

idf.py build                                   # BENCH_MODE already set; sdkconfig caches it
idf.py -p <TX_PORT> flash monitor
```
> `git checkout <sha>` puts you in detached HEAD — that's fine for testing. Re-confirm `CONFIG_BENCH_MODE_INTERACTIVE=y` did not revert (a `set-target` or stale sdkconfig can reset it; re-check after each checkout if the build misbehaves).

---

## 3. Test matrix

**Method:** TX board = firmware-under-test; RX board = constant interactive RadioLib `runRx()` (`MODE FLRC`, `ROLE RX`). This isolates the TX-side variable. `runTxMax()` first calls `radio->beginFLRC()` (sets packet type, sync word, frequency, PA ramp) **then** overrides modulation params via raw SPI — so the RX's RadioLib framing stays compatible **as long as BR/CR/FREQ match on both boards**. The end-marker protocol (TX sends 8-byte `DEADBEEF`+sent-count; RX detects it and finalizes) means **the RX must be listening BEFORE you press RUN on TX.**

**Common RX setup (type into RX console before every TX run):**
```
MODE FLRC
FREQ 2450
BR 2600
CR 0x01
SIZE 255
COUNT 1000
ROLE RX
RUN
```
Wait for `RX: Waiting for packets...` then switch to the TX console.

### TEST 0 — Baseline regression anchor (run first, on every TX commit)
**Purpose:** prove the RadioLib path still works at 100/100 like the Phase-1 baseline (20.8 kbps, -105 dBm). If this fails, the hardware/wiring is bad — stop and fix before any raw-TX test.
- TX: `MODE FLRC; FREQ 2450; BR 2600; CR 0x01; SIZE 255; COUNT 1000; PWR 22; ROLE TX; RUN`
- RX: as above.
- **PASS:** RX `received,≥950` of 1000 (≥95%), `ber_pct,0.000000`, `avg_rssi` near baseline.
- Record the RadioLib `throughput_kbps` (expect ≈20) as the regression anchor.

### TEST 1 — SPEED-P0: does raw SPI TX produce packets at all? (the 0/0 blocker fix)
- TX commit: **`44ad093`**
- TX: `MODE FLRC; FREQ 2450; BR 2600; CR 0x01; SIZE 255; COUNT 100; ROLE TX; RAWTX`
- RX: `MODE FLRC; FREQ 2450; BR 2600; CR 0x01; SIZE 255; COUNT 100; ROLE RX; RUN`
- **PASS (binary gate):** RX `received,≥1`. Pre-fix this was **0/0**. Any packets = the `SET_FLRC_PACKET_PARAMS` fix works.
- Note RX delivery % — expect lower than RadioLib (P0 is the first raw attempt, not optimized).

### TEST 2 — SPEED-P2: zero-overhead bypass throughput
- TX commit: **`67c0552`**
- TX: `MODE FLRC; FREQ 2450; BR 2600; CR 0x01; SIZE 255; COUNT 1000; ROLE TX; RAWTX`
- RX: as common setup.
- **PASS:** RX `received,≥900` (≥90%), throughput **> 20.8 kbps baseline**. Capture TX `time_per_pkt` improvement vs P0.
- Compare RX-delivered throughput to TEST 1 — P2 should be measurably higher per-packet rate.

### TEST 3 — SPEED-P3 / MERGE-FIX: FLRC_MAX speed-record attempt (headline number)
- TX commit: **`45b57ab`** (P3) **and** **`dc9d2e2`** (merge-fix) — run both, compare.
- TX: `MODE FLRC_MAX; FREQ 2450; BR 2600; CR 0x02; SIZE 255; COUNT 1000; PWR 22; ROLE TX; RUN`
  - `CR 0x02` = uncoded (no FEC) — max air rate. *If uncoded gives 0% delivery at range, fall back to `CR 0x01` (3/4).*
- RX: `MODE FLRC; FREQ 2450; BR 2600; CR 0x02; SIZE 255; COUNT 1000; ROLE RX; RUN` (CR must match TX).
- Capture TX `=== TX_MAX RESULTS ===`: `throughput_kbps`, `time_per_pkt_us`, `sent`, `tx_errors`.
- Capture RX `=== RX RESULTS ===`: `received`, `per_pct`, `throughput_kbps`.
- **PASS tiers:**
  - Tier 1 (>10× RadioLib): TX throughput **> 200 kbps**
  - Tier 2: **> 500 kbps**
  - Tier 3: **> 1 Mbps**
  - Tier 4 (theoretical 97%): **≥ 2.5 Mbps** with RX `per_pct < 5%`
- If P3 shows high `tx_errors`/0 delivery but merge-fix works → the **shaping bug** (`0x02` vs `0x05`) was the cause; document it.

### TEST 4 — SPEED-P3: BR sweep + BR=650 fix validation
- TX commit: **`45b57ab`** or **`dc9d2e2`**
- TX: `COUNT 200; SWEEP` (runs 8 BR × 4 CR × 4 size = **128 combos**, prints CSV `br,cr,pkt_size,pkts_sent,throughput_kbps,time_per_pkt_us`, ends with `# SWEEP COMPLETE — 128 combos, raw SPI`).
- This is TX-only timing (no RX needed) — captures per-combo air-rate ceiling.
- **PASS:** every BR row reports `pkts_sent` ≈ 200 (no `tx_errors`), **especially the `650` row** (was 0 packets pre-fix). Validates `rawSetFlrcModParams` + `brToNibble`.
- Optional RX cross-check: pick the `650,0x01` row params, set TX+RX to `BR 650; CR 0x01`, confirm RX receives.

### TEST 5 (conditional) — Isolation / regression debug
Only if a prior test fails unexpectedly:
- Re-run the failing test's exact config on `master` interactive → confirms the RadioLib path works (rules out hardware).
- `git log --oneline 36952f7..<commit> -- mesh-stack/flrc-bench-espidf/main/bench_main.cpp` to list exactly what changed.
- Binary-search between P0→P2→P3 if throughput regresses.

---

## 4. Pass/fail summary

| Test | Commit | Primary criterion | Stretch |
|------|--------|-------------------|---------|
| 0 Baseline | any | RX ≥95% / 0% BER (≈20 kbps) | — |
| 1 P0 raw-TX works | `44ad093` | RX ≥1 packet (was 0/0) | ≥80% delivery |
| 2 P2 bypass | `67c0552` | RX ≥90%, throughput > 20.8 kbps | > 200 kbps |
| 3 P3/merge speed | `45b57ab`/`dc9d2e2` | TX > 200 kbps, RX per < 5% | ≥ 2.5 Mbps |
| 4 P3 sweep | `45b57ab`/`dc9d2e2` | all 8 BR rows sent>0 incl. 650 | clean 128-row CSV |

**Global stop conditions:** TEST 0 fails (hardware/wiring bad), or RX consistently `received,0` across P0+P2+P3 (points to FREQ/sync mismatch, not the TX fix — see §5).

---

## 5. Troubleshooting (most-likely first)

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `received,0` / `0/0` on raw-TX (all commits) | FREQ or sync-word mismatch TX↔RX | Both boards `FREQ 2450`; both `MODE FLRC`/`FLRC_MAX`; CR matches. RX uses RadioLib private sync — `runTxMax` calls `beginFLRC` first to inherit it, so don't skip init. |
| Interactive prompt does nothing | `CONFIG_BENCH_MODE_RAW_RX=y` still set → wrong app_main | menuconfig → Interactive (§1d); `rm sdkconfig` + rebuild if it won't clear |
| `received,0` but TX shows `sent,1000` / TX_DONE ok | Modulation mismatch (shaping/CR) | On P3 try merge-fix `dc9d2e2` (shaping `0x05`); match CR exactly; try `CR 0x01` instead of uncoded `0x02` |
| `BR 650` row = 0 sent | `brToNibble`/mod-params not applied | Only fixed on P3 (`0x0248`); on P0/P2 BR=650 is expected to fail — that's the bug P3 fixes |
| Serial port vanishes / `tcsetattr` errors when BR changes | USB CDC re-enumeration (BUG #3) | Keep port open across the sweep; add reset+re-detect between groups; `SWEEP` avoids the issue by not re-initing per combo |
| `TX_MAX timeout pkt N` repeatedly | `rawWaitTxDone` never sees TxDone bit | Check DIO9 wiring / BUSY pin; `rawEnableTxIrq` (`0x0115`) sets enable bits; verify LR2021 TxDone IRQ bit position |
| `gdbinit.cmake:40 TO_CMAKE_PATH` error | IDF env not active in this shell | Use the §1c one-liner in ONE call; don't split export + build |
| Port not found after replug | ACM numbers shifted | Re-run §1b discovery; match by `chip_id`, not by number |
| RX `out_of_order,>0` or SEQGAPS | RX blind window dropping packets | Expected at high rates; reduce COUNT or note in results — not a failure of the TX fix |

---

## 6. Data collection template

Fill one block per test run. CSV columns match the firmware's `printf`/`ESP_LOGI` output exactly.

### 6a. Per-run header
```
TEST:        [0|1|2|3|4|5]
TX_COMMIT:   [sha]   TX_BRANCH: [name]   TX_PORT: [port]   TX_CHIP: [id]
RX_COMMIT:   [master/sha]          RX_PORT: [port]   RX_CHIP: [id]
DATE:        YYYY-MM-DD   OPERATOR: [name]
FREQ_MHZ:    2450   BR: [2600]   CR: [0x02]   SIZE: [255]   COUNT: [1000]   PWR: [22]
NOTES:       [antenna/distance/anything odd]
```

### 6b. TX results (copy the `=== TX[_MAX] RESULTS ===` lines)
```
TX sent,            ____
TX tx_errors,       ____
TX elapsed_us,      ____      (TX_MAX)  /  elapsed_ms ____ (RadioLib)
TX throughput_kbps, ____
TX time_per_pkt,    ____ us   (TX_MAX)  /  ms ____ (RadioLib)
```

### 6c. RX results (copy the `=== RX RESULTS ===` lines)
```
RX received,            ____
RX crc_errors,          ____
RX lost,                ____
RX total_sent_by_tx,    ____
RX elapsed_ms,          ____
RX throughput_kbps,     ____
RX per_pct,             ____
RX ber_pct,             ____
RX avg_rssi,            ____
RX min_rssi / max_rssi, ____ / ____
RX payload_corrupt,     ____
RX bit_errors_total,    ____
RX out_of_order,        ____
SEQGAPS:                [paste]
```

### 6d. SWEEP (TEST 4) — save the full CSV
```
br,cr,pkt_size,pkts_sent,throughput_kbps,time_per_pkt_us
[128 rows]
# SWEEP COMPLETE — 128 combos, raw SPI
```
Save to `docs/results/speed-sweep-<commit>-<date>.csv`. Highlight the `650` rows.

### 6e. Roll-up table (one row per commit)
| Commit | TEST0 kbps | TEST1 recv/100 | TEST2 kbps | TEST3 TX kbps | TEST3 RX per% | TEST4 650 ok? | Verdict |
|--------|-----------|----------------|-----------|---------------|---------------|---------------|---------|
| `44ad093` P0 | | | — | — | — | n/a | |
| `67c0552` P2 | | | | | | n/a | |
| `45b57ab` P3 | | | | | | | |
| `dc9d2e2` FIX | | | | | | | **headline** |

---

## 7. Reporting back (when done)
1. Save filled templates + sweep CSV under `docs/results/`.
2. Recreate `docs/PHASE1-RESULTS.md` (referenced by the parent task but currently missing) with the roll-up table from §6e.
3. Update `~/comprehensive-plan-lr2021-speed-records.md` Step table with measured numbers.
4. Commit on a branch (e.g. `docs/speed-p0p2p3-results`) and post the headline throughput + per-commit verdict to the Kanban task thread.
5. **Cross-track note:** the proven RP2040 records (838 kbps RX / 1377 kbps TX) live on `track/speed-testing`; the ESP32 number from TEST 3 is the new ESP32-platform headline for comparison.

---

## Appendix A — Quick command card (print this)

```
RX (every test, type first, wait for "Waiting for packets"):
  MODE FLRC; FREQ 2450; BR 2600; CR <match>; SIZE 255; COUNT 1000; ROLE RX; RUN

TEST 0 baseline : TX  MODE FLRC; ...same params...; ROLE TX; RUN
TEST 1 P0 (44ad093): TX  ...; ROLE TX; RAWTX        (CR 0x01, COUNT 100)
TEST 2 P2 (67c0552): TX  ...; ROLE TX; RAWTX        (CR 0x01, COUNT 1000)
TEST 3 P3/merge : TX  MODE FLRC_MAX; FREQ 2450; BR 2600; CR 0x02; SIZE 255; COUNT 1000; ROLE TX; RUN
TEST 4 sweep   : TX  COUNT 200; SWEEP              (TX-only, no RX needed)

build/flash (TX per commit):
  export IDF_PYTHON_ENV_PATH=.../idf5.4_py3.13_env && source ~/esp/esp-idf/export.sh \
    && cd ~/repos/balloon-fresh/mesh-stack/flrc-bench-espidf
  git checkout <sha>; idf.py build; idf.py -p <TX_PORT> flash monitor
  (menuconfig → BENCH_MODE = Interactive, once)
```
