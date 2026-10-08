# REPORT — level-control cluster (`design/level-control-architecture`)

Date 2026-10-08. Base `github/main` @ `09e1b69`. Worktree `/home/c03rad0r/worktrees/bf-levelctrl`.

## Deliverables (two, one branch)

1. **Level-control design** — `docs/analysis/ground-station-level-control-design.md`
   + `docs/analysis/level_control_model.py` (reproduces every number)
   + `docs/analysis/render_level_control_figures.py` + `docs/analysis/assets/level-control/*`
   + **ADR-084** `docs/adr/084-ground-station-automatic-level-control.md`.
2. **Base-station board checklist** — `docs/BASE-STATION-BOARD-CHECKLIST.md`
   (OWNED / TO-BUY / TODO(unverified) / OPT statuses, subtotals, spec-dispute verify notes).

## Result head-line

- **Receive AGC chain fixed by Friis:** `antenna → 433 BPF → LNA (owned TQP3M9037) → VGA → receiver`.
  VGA-after-LNA adds **+0.04 dB** (ADL5240 VGA) to the system NF; VGA-first adds **+2.6 dB**. Real
  parts verified against live datasheets: **ADL5240 / ADL5243** (100 MHz–4 GHz, 31.5 dB DSA, 0.5 dB
  step) and **ADL5330** (10 MHz–3 GHz, **−35…+22 dB**). All cover 433 MHz **and** 2.45 GHz; all reach
  negative dB.
- **Digital AGC recommended over analog** (repeatability/loggability; MCU already present); analog is
  the fallback. Manual/commanded mode is the **baseline** (operator decision) — first flight needs no
  automation.
- **Transmit:** precomputed GNSS-range→attenuation **LUT** (PE43711-class DSA, 0–31.75 dB, 0.25 dB
  step). **Honest finding:** under the ISM ceiling the LUT sits near 0 dB for the whole flight (the
  LR2021 HF PA is only +12 dBm and an 11.1 dBi antenna already over-shoots the 14.26 dBm EIRP ceiling
  by 8.8 dB); it earns its keep at metres-range or with a PA on a higher footing.
- **Dynamic-range budget (the throughput argument):** 1→650 km = **56.26 dB** path swing (+15 dB fade).
  Fixed gain accepts **35 dB** (≈49% of the mission's dB span); +31.5 dB DSA → **66.5 dB (93 %)**;
  +57 dB VGA → **92 dB (100 %)**. The top FLRC rate has the worst sensitivity → first casualty of a
  mis-set level; level control is worth up to **4×** the bottom-rung rate at the far edge and the whole
  link during the overhead pass.
- **Failure modes:** the AGC is **433-RX-only** and **cannot** move the TX level or break the ADR-072
  band-split duplex. The availability risk (latching, hunting, blocker-driven desense) is mitigated by
  manual bypass, bounded gain + anti-windup, **433 band-limiting of the detector**, and an
  **autonomous** downlink-failure watchdog. "Band separation is not service independence" stated.

## Consultant (required) — engaged, twice

- Lane `scripts/fleet/visual_consult.py`. **Served model `gpt-6-astra`** (read back from the response).
- **Round 1** (`--timeout 540`): model's own line **`VERDICT: REFUTE`**; structured `verdict` field
  `UNPARSED` (CONFIRM/REFUTE is not the parser's vocabulary — parser declining, not the model
  disagreeing). Final line verbatim: *"VERDICT: REFUTE — The conditional Friis arithmetic is sound, but
  contradictory gain windows, unproven loop dynamics, insufficient TX control range and missing
  full-duplex self-interference analysis invalidate the plan's claimed coverage and safety."*
- **Round 2** (corrected figures, parser vocabulary): **`gpt-6-astra`**, parser verdict
  **`CHANGES_REQUESTED`**.
- **Acted on:** F1/F2 (figure gain windows; **a real 42-vs-35 dB plot bug**), F3 (31.5 vs 31.75 dB DSA
  = distinct parts), F4 (**fast attack / slow decay** + frame-latency budget), F5 (**433 BPF at the
  detector tap** — blocker-driven desense), F6 (extended failure table + autonomous recovery + TX→RX
  blocking row), F7 (dB-span wording), F8/F12 (full-system-NF caveat), F10 (**24.5 dB TX residual**
  explicit), F11 (separate RX/TX level elements), and a **label collision** the consultant caught on
  figure 1 (fixed). Full record: `docs/analysis/assets/level-control/consult-verdict.txt`.

## Git

- Branch `design/level-control-architecture`; commits pushed to **github first, then ngit separately**
  (no `--atomic`); **main never touched** (`09e1b69`).
- Final SHAs verified with `git ls-remote` on both remotes — local == github == ngit
  (see the final reply for the exact SHAs).

## Residual / open

- LR2021 max-input level (the top of the assumed 35 dB window) — `TODO(unverified)`.
- 433-specific FLRC sensitivity rows — `TODO(unverified)` (2.4 GHz proxy used).
- AGC detector/ADC/MCU part numbers & price — `TODO(unverified)` (checklist row 7–8).
- The **TQP3M9037 band edge** (0.1 MHz vs 0.7 GHz, ADR-079 D5) gates the whole 433 RX chain — bench
  sweep is the first action.
- Inherited, not re-opened: the 2.4 GHz uplink legal-ceiling defect (flat 20 dBm vs ~14.26 dBm PSD).
