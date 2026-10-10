# REPORT.md — half-duplex / bent-pipe answers

**Deliverable:** `docs/analysis/HALF-DUPLEX-AND-BENT-PIPE-ANSWERS.md` (analysis, not a decision).
**Branch:** `analysis/half-duplex-answers` (worktree `~/worktrees/bf-halftime`), off `origin/main`.
**Task:** answer the operator's four pointed system-design questions, grounded in the repo's own
committed files, each with a direct yes/no and a bottom line.

## The four answers

1. **Is a bent pipe simultaneous by definition, and can it be, given the radio is half-duplex?**
   The bent pipe *as this program defines it* **requires** simultaneity (`docs/adr/071-...md` INV-1),
   but that is an architecture property, not a radio property. One LR2021 is **half-duplex and can
   never be simultaneous** (`docs/coordination/CONSULTANT-PLAN-REVIEW-V2.md` CONCERN-4;
   `docs/coordination/ARCHITECTURE-FREERTOS-TASKS.md`; `docs/adr/034-...md` Context). True FDD
   therefore needs a **second radio chain** — which is exactly `docs/adr/034-...md` D1 (two chips).
   Extra chain cost in-repo: bare `LoRa2021` **1.2 g** mass item (`docs/analysis/two-variant-mass-budget.md`
   A4) / **+0.5 g per extra LR2021** (`docs/adr/014-...md`), **+3–25 mA day-only** (`docs/adr/014-...md`),
   **+4 GPIO** (`docs/adr/040-...md`, `docs/adr/108-...md`); a board-area figure is **not itemised**.
   TDD on one radio costs the simultaneity ADR-071 D2 rejects and drops packets during TX
   (CONCERN-4). At the committed **300 km** slant range, propagation is ~2 ms RTT (arithmetic from c);
   the floor is the schedule — the repo's TDMA transport records **RTT 2–6 s**
   (`docs/adr/106-...md`).

2. **Does "balloon ALWAYS transmits on 433 MHz and listens on 2.4 GHz" work?** **Yes as a
   band-direction assignment — it is literally `docs/adr/034-...md`** (TX 433 on the F33-2G4 2 W port,
   RX 2.4 on a bare `LoRa2021`), and it **requires two chips**. The high-rate leg correctly rides 433
   (**14.9 dB less path loss**: 134.7 vs 149.6 dB @300 km — `docs/adr/041-...md`,
   `docs/LINK-BUDGET-LICENCE-EXEMPT.md`); the 2.4 GHz return is the **binding** link and is closed on
   the ground. "ALWAYS" is not literal: licence-exempt design is a **~1.7 % duty cycle**
   (`docs/licence-exempt-design-point.md` §7); the **2 W F33 is over the ≤10 mW ERP** licence-exempt
   cap (§6).

3. **Circulator or band-split duplexer?** **Neither.** A circulator is the wrong device class
   (narrowband; a 2.4 GHz unit has no 433 MHz path) — `docs/adr/072-band-split-duplex-two-antennas-no-circulator.md`
   D1/D2; `docs/analysis/rf-shopping-list-and-duplex-architecture.md` §1. Duplex by **band separation**:
   two band antennas **≈68 dB** (recommended) or a band diplexer **≈60 dB** (one feedline only).
   The owned **TQP3M9037 (NF 0.4 dB, 0.7–6 GHz) does not cover 433** (`docs/analysis/433-lna-substitution-and-amateur-licence.md`);
   the cheap workable part is **Mini-Circuits ZX60-P103LN+ (NF 0.5 dB)**, and the recommended part is
   **SSB Electronic LNA ISM 433 (NF 0.7 dB)**. Coax ahead of the LNA degrades system NF ≈**1:1**
   (the repo measures the shack-end penalty at **1.2 dB @433 / 15 m**), so the LNA **must be masthead**
   (`docs/adr/079-...md` INV-1; `docs/analysis/ground-station/REPORT-design-rf-gaps-harmonics-diy.md` Part C).

4. **The 2 MHz FLRC / 1.74 MHz band conflict — can the balloon transmit its high-rate stream on 433?**
   **No.** The band **433.05–434.79 MHz is only 1.74 MHz wide**; on the amateur footing the max
   occupied bandwidth on 70 cm is **2 MHz** (AFuV Anlage 1, Lfd. Nr. 18 + Zusatzbestimmung 7,
   quoted in `docs/analysis/433-lna-substitution-and-amateur-licence.md` §2.1–2.2), and **FLRC-max is
   2.666 MHz**. The highest legal FLRC rate on 433 is **1300 kbps (1.333 MHz)**. Licence-exempt is
   worse: the continuous-duty window (45c, 434.04–434.79 MHz) caps bandwidth at **25 kHz**
   (`docs/analysis/free-balloon-mass-threshold-DE.md` §7.1). ADR-073's committed FLRC-max downlink
   (`docs/adr/073-...md` D1) is therefore in **unreconciled collision** with the bandwidth cap.

## Methods / provenance

- All figures are quoted from committed repo files; each claim in the deliverable carries its file
  path. No number is invented — the one computed value (300 km propagation, ~1 ms one-way) is stated
  as arithmetic from c, not as a repo measurement.
- Reproduce the regulatory/link figures from the cited Python models, e.g.
  `python3 docs/analysis/433_lna_licence_model.py` and
  `python3 docs/analysis/ground_station_flrc_max_model.py`.

## Status

Not merged. Ready for operator review. No hardware, BOM or schematic touched.
