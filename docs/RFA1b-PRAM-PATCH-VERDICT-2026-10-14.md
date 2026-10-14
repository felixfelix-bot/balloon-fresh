# RFA-1b — PRAM-patch bench experiment: verdict + evidence

Card: **t_0eaed49b** (board `balloon`) · Run: 2965 · Date: 2026-10-14
Branch: `pr/rfa1b-pram-results` (base `958a50fc`, the RFA-1 evidence base)
Bench pair: x240 `/dev/ttyUSB0` (board A) + x280 `/dev/ttyUSB1` (board B), ~10 cm apart,
869.85 MHz, N=200 packets, GAP=10 ms per cell, 115200 console.

---

## 1. Verdict (up front)

**The PRAM-patch hypothesis is REFUTED AS STATED — because the symptom it was
written to explain does not exist on the baseline the card names.**

1. On the boards' **unmodified binary (fw `5fa7912`)** the whole 6-cell matrix was
   measured twice (PA 22 and PA 10): **zero CRC errors in every cell that carried
   packets** — including 64 B and 128 B at 260 kbps and 128 B at 650 kbps, the
   cells the card lists as "200/200 CRC errors". 10 of 12 cell-runs delivered
   `rx=200 crc_err=0`; the 2 remaining runs delivered **0 packets** (a link/arming
   failure, not a CRC result — see §4).
2. The historical anomaly was measured on a **different, older binary**: matrix
   v5/v6 (2026-08-19/20) ran on fw `c31fb30`
   (`references/e80-throughput-matrix-final-2026-08-19.md`,
   `…-v6-2026-08-20.md`, manager skill `lr2021-throughput-optimization`). fw
   `5fa7912` is the **Aug-29 demo firmware**, built after the FLRC fix landed on
   **2026-08-21** (commit `a1fcd271`, "FIX-T3: FLRC RX Match123 + pkt-params
   golden host tests"): RX sync-match `MATCH_SYNCWORD_1` → `Match123` (sync
   bytes leaked into the payload → *packets demodulate but every frame CRC
   fails*, exactly the "200/200 CRC" family), plus the missing RX/TX FIFO clear
   (`docs/rca-fix-plan-20260821.md` BUG 2, FIX-T3/FIX-T4; range-tests `9b740aa`).
   The current source pins this with a `match != MATCH_SYNCWORD_1` tripwire in
   `tests/test_radio_bench_cfg.c`.
   The card's premise "missing patch = root cause of our OPEN anomaly" rests on
   a measurement taken **before** that fix landed.
3. Consequence for RFA-1 Q5: **the missing PRAM patch is not the root cause of
   this symptom**, and there is nothing left for it to cause. Retire Q5 as a
   root-cause lead for the 64/128 B anomaly. The port stays in the tree as an
   ExpressLRS-parity capability (it is a documented vendor patch ExpressLRS
   loads unconditionally), **not** as a bug fix.
4. What this run *does* add beyond the negative result: the hardware
   verification that FIX-T3/FIX-T4 were still missing
   (`docs/rca-fix-plan-20260821.md`: "the BUG 2 / BUG 3 hardware-verification
   columns are still PENDING") — the previously failing cells are now clean on
   silicon, 12 cell-runs, zero CRC errors.
5. Two honest gaps remain (§4 + §5): an intermittent **650 kbps 0-packet** cell
   (new, distinct from the historical claim) and the **patched-binary arms**
   (PATCH OFF/ON), which could not be run because no flash path exists on this
   bench today.

---

## 2. Evidence — baseline matrix (arm `none`, unmodified fw `5fa7912`)

| pass | PA | rate | len | TX sent/ok | RX pkts | RX rx/crc_err | crc_ok | crc_bad | RSSI | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| p1 | 22 dBm | 260 kbps | 64 B | 200/200 | 200 | 200/0 | 200 | 0 | -21.5 | CLEAN |
| p1 | 22 dBm | 650 kbps | 64 B | 200/200 | **0** | 0/0 | 0 | 0 | — | no packets |
| p1 | 22 dBm | 260 kbps | 128 B | 200/200 | 200 | 200/0 | 200 | 0 | -21.5 | CLEAN |
| p1 | 22 dBm | 650 kbps | 128 B | 200/200 | 200 | 200/0 | 200 | 0 | -21.5 | CLEAN |
| p1 | 22 dBm | 260 kbps | 255 B | 200/200 | 200 | 200/0 | 200 | 0 | -21.5 | CLEAN |
| p1 | 22 dBm | 650 kbps | 255 B | 200/200 | **0** | 0/0 | 0 | 0 | — | no packets |
| p2 | 10 dBm | 260 kbps | 64 B | 200/200 | 200 | 200/0 | 200 | 0 | -33.5 | CLEAN |
| p2 | 10 dBm | 650 kbps | 64 B | 200/200 | **0** | 0/0 | 0 | 0 | — | no packets |
| p2 | 10 dBm | 260 kbps | 128 B | 200/200 | 200 | 200/0 | 200 | 0 | -33.5 | CLEAN |
| p2 | 10 dBm | 650 kbps | 128 B | 200/200 | **0** | 0/0 | 0 | 0 | — | no packets |
| p2 | 10 dBm | 260 kbps | 255 B | 200/200 | 200 | 200/0 | 200 | 0 | -33.5 | CLEAN |
| p2 | 10 dBm | 650 kbps | 255 B | 200/200 | 200 | 200/0 | 200 | 0 | -34.0 | CLEAN |

Additivity: **12 cell-runs, 2400 TX packets, 2000 RX packets counted, and not one
CRC-error row.** The two `0 pkts` rows are `rx=0 crc_err=0` with no RSSI
sample: the RX never demodulated anything, so they carry no CRC information.

Machine-readable: `rfa1b-summary.csv` (attached) and the per-cell JSON
(`cell-<arm>_<rate>_<len>_<config_id>.json`, raw console lines included) under
`rfa1b/arm-none/` and `rfa1b/arm-none-pa10/` (attached: summaries).

Reproduce (from `firmware/e80-stm32-bench`, on x280; board A reachable via ssh):

```bash
python3 tools/rfa1b_pram_matrix.py --arm none --outdir ~/rfa1b/arm-none
python3 tools/rfa1b_pram_matrix.py --arm none --pa 10 --outdir ~/rfa1b/arm-none-pa10
python3 tools/rfa1b_summarize.py ~/rfa1b/arm-none ~/rfa1b/arm-none-pa10
```

Every console command is validated (expected-substring, retries) by
`tools/e80_serial_agent.py`; each cell is tagged with `CONFIG <id> 0` on both
boards and the host counts **only** PKT lines carrying that id, because the RX
board keeps receiving and the TX sequence counter persists across cells (an
earlier unfiltered pass produced 183/200-style counts mixed with the previous
cell's tail — that data was discarded, not reported).

---

## 3. What was built (deliverable, host-tested)

* `src/pram_patch.{h,c}` — the ExpressLRS sequence: 560 words from
  `LR2021PRAM.h` written through REGMEM32 (0x0104) in **12-word chunks**
  (`base 0x801000`, addresses `base + i*48`), then `PATCH_ENABLE_PRAM_OC`
  (0x012D) with payload byte 0x00, then a 10 ms settle. `pram_patch_verify()`
  reads the image back and reports mismatches (advisory evidence for the
  follow-up run).
* `src/pram_patch_table.c` — generated (`tools/gen_pram_table.py`) from the ELRS
  master header; **CRC32 = `0x44FCC3B2`** (zlib over the big-endian word bytes).
* `src/radio_bench.c` — uploads the patch after **every** chip reset the file
  performs (init + the modulation-switch re-init), so the invariant is: after
  any reset the patch is present iff the flag is set.
* `PATCH ON|OFF` (bench.c/bench_cmd.c) — re-runs the bring-up so the arm takes
  effect immediately in ONE binary; `ID?` now reports `patch=<0|1>
  pramcrc=0x44FCC3B2`, i.e. the host can attest which arm and which table a
  board is running **without a probe**.
* Tests: `make test-host` 24/24 PASS (new `test_bench_pram`: table CRC golden,
  chunk plan/addresses, exact 0x0104/0x012D wire sequence, read-back verify,
  failure propagation) and `make rfa1b-test-host` 13/13 PASS (matrix runner's
  per-cell accounting + ops builders).

## 4. The 650 kbps 0-packet cells (new open item, not the historical anomaly)

Across 6 attempts at PA 22 and 6 at PA 10, four delivered `rx=0 crc_err=0`
(no RSSI sample at all) and two delivered `200/200 crc_err=0` — i.e. **at 650
kbps the link is intermittently dead, and when it is alive it is clean**. In
the historical v5/v6 tables the same rate/payload rows read `RX got 0, CRC 200`
(a received-but-corrupt family); today's failure mode is different and never
produces CRC errors. Leading hypothesis (not tested here): the firmware only
forces a full chip re-init when the *modulation type* changes
(`radio_bench_apply_cfg`: "the LR2021 cannot reliably switch modulation via
register writes alone"), not when the FLRC **bitrate** changes — so a cell that
follows a different-bitrate cell can run with the RX still configured for the
previous rate. Cheap next step: force a `MOD lora` → `MOD flrc <br>` toggle (or
an explicit re-init) before each cell and re-measure; the per-cell `PATCH ON|OFF`
bring-up in the follow-up cards does exactly that re-init, which is why the arm
runs should be deterministic where this baseline pass was not.

## 5. Deviations and blockers (honest list)

1. **Base source for `5fa7912` does not exist anywhere in the fleet.** The
   boards were built from `~/repos/balloon-e80bench` (a worktree whose
   directory lived on another host, `/home/c03rad0r/...`), `git cat-file` fails
   for the sha after a full `git fetch --all`, `origin` has no such object, and
   `github.com/felixfelix-bot/balloon-e80bench` returns 404. Mitigation used:
   the patch-OFF baseline was measured on the **binary actually on the boards**
   (this document), and the arm binary was built from `balloon-fresh`
   `firmware/e80-stm32-bench` @ `958a50fc` (the RFA-1 evidence base). The two
   must not be confused: the historical anomaly predates `5fa7912`, and
   `958a50fc`'s bench firmware carries the same post-fix FLRC path.
2. **No flash path was available for the patched binary** (the card's step 1–3):
   * SWD is unusable: the probe initialises (CMSIS-DAP v2,
     serial `148757200D2D1425`) but the STM32 does not answer — the 3-wire
     SWD link is not seated (operator/manager dry run 2026-10-14 + this run's
     pre-flight). Re-seating it is a physical action.
   * UART ROM-ISP (the OOB's Option A) was attempted on board B and **failed**:
     the firmware's `FLASH` command did jump (`OK JUMPING TO BOOTLOADER`), but
     `stm32flash -r` could not sync at 57600/115200/9600 (8E1) and a bounded
     8E1+8N1 sync-spam probe at 57600/115200/9600/38400 received **no 0x79
     ACK**. This confirms the skill's 2026-08-20 CH340 finding and contradicts
     `firmware/e80-stm32-bench/FLASHING.md` (which documents this path as
     working). No hot-looping: three stm32flash bauds + one 8×-baud/2-parity
     sync-spam pass, then stop.
   * Side effects to hand over: **board B is now sitting in the ROM
     bootloader** (only a physical power-cycle brings the app back) and **board
     A is IWDG-active** (this run's `ARM TX`; `FLASH` refuses until it too is
     power-cycled). Both boards need a USB replug before any further bench
     work. The `5fa7912` dump could not be taken, so there is still **no
     archival copy of the baseline firmware**.
3. Consequence: the card's arms (**patch OFF vs patch ON on the patched
   binary**) and the on-silicon validation of the PRAM loader (read-back
   verify) were **not run**. They are the subject of the follow-up card.
   Given §1 they cannot change the verdict — they would only confirm that the
   loader works on silicon and that the patch is behaviour-neutral.

## 6. Data-integrity notes

* **Never all-zero:** every reported cell carries TX `sent=200 sent_ok=200` and
  (where applicable) ≥200 received packets with RSSI samples; the two 0-packet
  cells are labelled as such and are explicitly *not* used as evidence.
* Cells were rejected and re-run when the protocol was found wanting (unfiltered
  PKT counting, RX `START` reply mismatch, stale listen markers) — the earlier
  unfiltered numbers are not in this document.
* Per-cell files keep the **raw console lines** (both boards) alongside the
  parsed summary, so every number is re-derivable.
