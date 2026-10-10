# Balloon program — GAP TRACKING CHECKLIST (single actionable list)

**Status:** `docs/analysis/` findings document — it **tracks** work, it **orders nothing**.
**Date:** 2026-10-10
**Branch:** `docs/gap-tracking` (off `origin/main` @ `1cab792`).
**Author:** Hermes subagent (manager-delegated), read-only on every other ref.
**Reconciles:** `docs/analysis/PROGRAM-GAP-ANALYSIS.md` (round 1, 620 lines) and
`docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md` (round 2, open PR #36 — read with
`git fetch origin pull/36/head:pr36 && git show pr36:docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md`).

> **Honesty rule applied to every row.** Each row carries the **path of a file that was actually
> opened** for this checklist. Where a status could not be settled from a file, the status reads
> **UNCLEAR** with the path that was read and the path that would settle it. No price, part number
> or spec was invented.

---

## How to read the table

| Column | Meaning |
|---|---|
| **ID** | stable row id (prefix = area). Quote this id when closing a row. |
| **Area** | BS = base station · PRE = pre-stretch/pressure bench · MECH = mechanical/architecture · PCB = board/EDA · RF = link/band · LEGAL · SAFE = flight-safety · TOOL = bench tooling |
| **Blocking?** | **yes** = a flight / purchase / board-freeze is gated on it · **no** = it degrades evidence or adds risk but does not gate the next build step |
| **Owner** | **HUMAN/BENCH** = needs the operator's hands, bench or money · **AGENT** = can be done entirely in-repo (analysis, ADR, schematic, code, merge) · **AGENT→HUMAN** = the in-repo part is an agent's, the closing act is the operator's |
| **Status** | `OPEN` · `UNMERGED` (work exists on a branch, not on `main`) · `NOT DONE` · `TODO(unverified)` (a real gap counted as €0) · `FIXED-UNMERGED` · `UNCLEAR` |

**`main` truth for this document:** `origin/main` = `1cab79261ba1296d756a97935cb2789c749e308d`.
Anything marked `UNMERGED` is **not** in what an outsider cloning the repo sees.

---

## The checklist

| ID | Area | What is missing | Why it matters | Blocking? | Owner | Source path (read for this row) | Current status |
|---|---|---|---|---|---|---|---|
| **BS-01** | BS | **The base-station board does not exist.** No schematic, netlist or gerber for the control/bias/telemetry board on any ref; the checklist is explicitly "a document, NOT a KiCad layout". | The gateway has zero fabricated hardware. Every ground-station claim (RX chain, AGC, TX LUT, PCBA plan) rests on a board nobody can order. | **yes** | AGENT→HUMAN | `docs/BASE-STATION-BOARD-CHECKLIST.md` (header + "MISSING" §); `docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md` §1 | OPEN — `PCBPROG-BASE-1` triage, `PCBPROG-BASE-2` todo (round 2 §1); no board on any ref |
| **BS-02** | BS | **2.4 GHz uplink PA/FEM — MISSING ENTIRELY.** No part selected, no topology, no price. | It is the **only RF block with no part at all**. Without it the uplink depends entirely on ground-side gain (see `uplink-budget-realistic-ground.md`). | **yes** | AGENT→HUMAN | `docs/BASE-STATION-BOARD-CHECKLIST.md` row 11 (line 42); ROUND2 §1, §5 | `TODO(unverified)` — "price/topology not decided" |
| **BS-03** | BS | **5 required BOM rows carry NO PRICE:** rows 7 (AD8318 log detector), 8 (ADC/MCU), **11 (the 2.4 GHz PA)**, 14 (bias tee + rails), 18 (masthead enclosure). | The budget is a **floor, not an estimate** — €274.58 excludes five required lines, each counted as €0. | **yes** | AGENT→HUMAN | `docs/BASE-STATION-BOARD-CHECKLIST.md` rows 7/8/11/14/18 (lines 38, 39, 42, 45, 49) + "Totals" § (lines 65–78) | `TODO(unverified)` — "not in the totals" |
| **BS-04** | BS | **No RF verification hardware.** The LiteVNA 62 is a *to-buy* row; the owned Red Pitaya is **IF-only** (DC–60 MHz) and the owned XR-613 is a resistive ~6 dB divider. | Passives, filter rejection and duplexer isolation at **both** bands are currently **unverified claims**. | **yes** | HUMAN/BENCH | `docs/BASE-STATION-BOARD-CHECKLIST.md` rows 13/15/16 (lines 44, 46, 47); ROUND2 §1 | TO-BUY €166.99 (deliberate — 38 % of the BOM) |
| **BS-05** | BS | **The 433 masthead LNA dispute resolved AGAINST the owned part** — the Qorvo TQP3M9037's vendor band is **0.7–6 GHz**, so it does not cover 433.92 MHz. | The whole 433 RX chain (the binding direction) was built around a part that does not cover the band. | **yes** | HUMAN/BENCH | `docs/analysis/433-lna-substitution-and-amateur-licence.md` §0.1 Q1, §1.1 (lines 52, 182–210) | RESOLVED in analysis; ADR-079 → **SUPERSEDED by ADR-085 (Proposed)** — not frozen |
| **BS-06** | BS | **The ground-station design is unmerged.** ~16 `design/*` branches, ~62 commits, 136 file-touches; **ADRs 071…084 exist only on branches**; `main` carries the flight-board ADR line only (to 065). | A branch is not a design of record. Every session re-derives; a board could be built from a branch nobody reviewed. | **yes** | AGENT | `docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md` §1, §7.1, §8 row 1; `docs/analysis/PROGRAM-GAP-ANALYSIS.md` §5 | OPEN (round 2 severity: **critical**) |
| **BS-07** | BS | **Tracker / positioner design unmerged** (ADRs 076/077/078 on `design/adr-set-groundstation` / `design/positioner-lowcost`). | Pointing, wind load and the masthead LNA's position all ride on it; ADR-078 D7 requires a measurement campaign **before** any dish/rotator purchase. | no | AGENT | `docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md` §6, §8 row 10 | UNMERGED |
| **PRE-01** | PRE | **The pre-pressurisation / pre-stretch board does not exist.** No schematic, footprint, layout or BOM on any ref — only a protocol, working breadboard firmware, and an analysis script. | No balloon flies without a passed leak test; the operator wants the cycle **automated** and the rig is a breadboard. | **yes** | AGENT→HUMAN | `docs/STATUS-balloon-pre-stretching.md`; `tools/balloon_pressure_test/` (`main/main.c`); ROUND2 §2 | PLANNED — NOT DESIGNED; `PCBPROG-PRE-1/2/3` todo; kanban `t_c561ea2d` **blocked** |
| **PRE-02** | PRE | **The `S_crack` coupon test has NOT been run.** ADR-063 D4 defines it: support a 78.55 × 38.90 × 0.21 mm cell end-only over a growing gap `S`, load to 1 g / 2 g, increase `S` to crack, record `S_crack`, repeat cold-soaked at ≈ −55 °C, require `pitch ≤ S_crack`. | **No `S_crack` value exists in the repo.** The wing rib pitch, the maximum overhang and the array-area ceiling are all unjustified until it is measured — and ADR-063 says plainly *"no number in D4 is frozen, and no pitch may be laid out from this record."* | **yes** | **HUMAN/BENCH** | `docs/adr/063-decouple-board-area-from-array-overhang.md` D4 (lines 169–195); ROUND2 §2 (`PCBPROG-0a`) | **NOT DONE** — `PCBPROG-0a` `scheduled`, HUMAN/BENCH (round 2 §2) |
| **PRE-03** | PRE | **BMP280-vs-MS5611 sensor-class mismatch.** The bench uses BMP280 (300–1100 mbar, ground only); the flight board carries MS5611 (10–1200 mbar). The bench cannot span the flight range, so its calibration does **not** transfer. | A leak test whose sensor class is not the flown sensor class is not a flight-readiness gate — it is a plausible-looking number. | **yes** | AGENT→HUMAN | ROUND2 §2; `docs/analysis/PROGRAM-GAP-ANALYSIS.md` §3a item 5; `docs/STATUS-balloon-pre-stretching.md` (BMP280 rig) | UNDECIDED (round 2 severity: medium) |
| **PRE-04** | PRE | **No over-pressure protection / safety interlock** — no relief valve, no firmware ceiling, no soft-start, no reverse-polarity protection. | Over-inflation is **the documented balloon-killer**: the protocol names it as the cause of the JR01–JR06 failures. A bench rig that can destroy an envelope is a *ground* reliability risk. | **yes** | AGENT→HUMAN | `docs/PRE-STRETCHING-PROTOCOL.md` line 129 (over-inflation past Ruthroff); ROUND2 §2, §7.5, §9.3 | ABSENT — nothing in any design |
| **MECH-01** | MECH | **Masthead-vs-shack board-split decision NOT made.** A masthead LNA, DSA, log detector, ADC/MCU and bias network all want to be at the masthead; the control PC wants to be indoors. | The current single-board framing does not express the split; it must be chosen **before the board is designed** (BS-01). Feedline loss degrades NF 1:1 (0.76 dB/10 m at 433), so the LNA must be at the antenna. | **yes** | AGENT | ROUND2 §6 (lines 201–216); `docs/BASE-STATION-BOARD-CHECKLIST.md` rows 3–8 | OPEN — **NEW** in round 2 |
| **PCB-01** | PCB | **Wing-board courtyard defect: 0 of 12 footprints carry a courtyard.** | Without courtyards, "0 overlap violations" is **not evidence** — clearance is unverifiable by construction. (Measured this session: wing `wing_board_v9.kicad_pcb` = **12 footprints / 0 with `CrtYd`**; hub `hub_board_v9.kicad_pcb` = **39 / 39**, the asymmetry is real.) | no | AGENT | `tracker/hardware/wing_board/wing_board_v9.kicad_pcb`; `tracker/hardware/hub_board_v9.kicad_pcb` (both measured); ROUND2 §7.7 | OPEN — measured; **NEW** in round 2 |
| **PCB-02** | PCB | **PCB 3D-render pipeline defect.** `KICAD9_3DMODEL_DIR` is unset and no 3D model library is installed, so `kicad-cli pcb render` draws **substrate + copper + silkscreen only** (no component bodies). `${KIPRJMOD}`-relative URIs in the schematic builder / sym-lib-tables; the self-contained-VRML fix lives **only on unmerged branches**. | Any "the parts look well placed" judgement from a render is really a judgement about copper and courtyards — the repo's own `AGENTS.md` says never trust a vision description of a render. | no | AGENT | `AGENTS.md` lines 136–137; `docs/analysis/PROGRAM-GAP-ANALYSIS.md` §3c item 2 (feat/3d-models-hub, feat/3d-models-wing, feat/board-view-renderer) | OPEN — fix **UNMERGED** |
| **RF-01** | RF | **Half-duplex-vs-bent-pipe scheduling decision NOT taken.** ADR-035 mandates **exactly one radio transmits at a time** (antenna-to-antenna isolation ~15–25 dB on a ~55×45 mm board), but a *bent pipe* is simultaneous by definition. The consultant round-1 half-claim: *"the flight schedule separates transmit and receive windows, contradicting the full-duplex requirement."* | If true, the timing plan cannot deliver the bent pipe as specified. It changes the relay from "simultaneous" to a TDM store-and-forward window schedule — which changes latency, throughput and the whole service model. | **yes** | AGENT→HUMAN | `docs/adr/035-tdm-radio-schedule.md`; ROUND2 §11.1 claim 1 | OPEN — **claim UNVERIFIED** (not accepted into round 2 §1–8; verify = read the flight-schedule doc + duplexer/band-plan together) |
| **RF-02** | RF | **The uplink link budget used LoRa sensitivity for an FLRC/high-rate mission.** `docs/2G4-LINK-BUDGET-ANALYSIS.md` budgets the 2.4 GHz link against **RX sensitivity −141.5 dBm (SF12/125 kHz)**, while the mission calls for a **2 MHz high-rate** mode whose sensitivity is ≈ **−99 dBm**. That is **~40 dB optimistic**. | Mixing a LoRa sensitivity with an FLRC plan makes an impossible link look comfortable — the most dangerous class of error. | **yes** | AGENT | `docs/2G4-LINK-BUDGET-ANALYSIS.md` lines 76, 89; ROUND2 §11.1 claim 2; **resolved by** `docs/analysis/uplink-budget-realistic-ground.md` (this PR) | ANALYSED — corrected figures now in `uplink-budget-realistic-ground.md`; the original doc is **stale, not yet corrected in place** |
| **RF-03** | RF | **2 MHz FLRC cannot fit the 1.74 MHz-wide 433 band.** The committed architecture (ADR-073) fixes the 433 downlink on **FLRC-max = 2.6 Mbps = 2.666 MHz DSB**, which is **1.53× the whole allocation**. | The band plan must be settled **before the duplexer/filter design is frozen** — otherwise the hardware is wrong at the fab stage and the money is spent. | **yes** | AGENT | `docs/adr/073-433-downlink-flrc-max-lora-rejected.md`; ROUND2 §3.1; **derived in** `docs/analysis/433-flrc-throughput-433mhz.md` (this PR) | OPEN (round 2 severity: **critical**) — **NEW** in round 2; settled numerically by this PR |
| **LEGAL-01** | LEGAL | **Airborne unlicensed operation and cross-border coordination remain open.** `UNVERIFIED`: whether generic ISM rules permit an airborne relay at all, and whether a German callsign covers a balloon transmitting over a foreign state. | A mass-market (licence-exempt) version is built on a premise nobody has verified against rule text; a cross-border flight transmits from foreign territory without that state's authorisation. | **yes** (for long-duration flights) | HUMAN/BENCH | `docs/REGULATORY-AMATEUR-LICENCE.md`; `docs/analysis/433-lna-substitution-and-amateur-licence.md` §2.3–2.4; ROUND2 §4, §7.10 | `TODO(unverified)` — route: written enquiry to BNetzA / § 16 Abs. 2 AFuV |
| **SAFE-01** | SAFE | **Descent, termination and recovery are not evidenced.** | A pico balloon that cannot be terminated is a liability; one that cannot be found is a lost payload. | **yes** | HUMAN/BENCH + AGENT | ROUND2 §7.11 | AUDIT NEEDED — "not evidenced in what I read" |
| **REL-01** | REL | **No link redundancy / second path.** One radio, one MCU, one battery — the operator's own *"sufficient redundancy"* rule is asserted as a principle but not implemented for the link. | For a relay whose whole purpose is availability, the absence of any fallback (low-rate beacon, second band path) is a structural gap. | no | AGENT | ROUND2 §7.9; `docs/adr/034-radio-band-split-433-tx-2g4-rx.md` (two chips, but one schedule) | OPEN — **NEW** in round 2 |
| **TOOL-01** | TOOL | **Leak-test sign error in the temperature compensation** — now fixed, **but the fix is UNMERGED.** | The old formula `(P_start − P_end − P_start·(T_end−T_start)/T_start)/h` **inverted the sign** and returned negative (physically impossible) rates: on synthetic data a genuine 1.5 mbar/h leak read **−1.329 mbar/h**, and a flight-ready 0.3 mbar/h balloon read **−2.570 mbar/h**. Because `verdict()` tests `rate < 0.5` first, a **warming balloon could be accepted as "Very good — flight ready" purely from a sign error.** | no | AGENT | `tools/balloon_pressure_test/plot_pressure.py` (line 76 on `main`); fix on branch `fix/leak-temp-comp-sign` @ `36993bf` | **FIXED-UNMERGED** — correct form `(P_start − P_end·T_start/T_end)/h`; `origin/main` @ `1cab792` **still carries the buggy formula** (verified this session) |

---

## Close-order (the blocking rows, in dependency order)

The intent of this list is to **unblock the next build step**, not to do everything. The blocking chain
as the evidence stands:

1. **RF-03** (band plan) and **BS-06** (consolidate the design) — settle these **first**; both are
   in-repo, zero-cost, and everything downstream assumes them. RF-03 is now numerically settled in
   `433-flrc-throughput-433mhz.md`; it still needs to be *written into the record* and the duplexer
   filter frozen against 1.333 MHz, not 2.666 MHz.
2. **TOOL-01** — merge `fix/leak-temp-comp-sign` (a correct leak test is a precondition for PRE-01/02).
3. **PRE-02** (`S_crack`, HUMAN/BENCH) and **MECH-01** (board split) — these gate the board designs
   (BS-01, PRE-01).
4. **BS-01 / PRE-01** board designs, then **BS-02 / BS-03** to close the BOM.
5. **LEGAL-01** and **RF-01** before any long-duration flight.

## What this list deliberately does NOT do

- It does **not** order anything, freeze a schematic, or set a price. Rows BS-02/BS-03/BS-04 keep
  their `TODO(unverified)` and vendor "from" prices exactly as the source documents carry them.
- It does **not** accept the round-2 consultant's three claims as findings. RF-01 and RF-02 are
  carried as **the agent's own verified reading of repo files** (RF-02: the LoRa number is in
  `docs/2G4-LINK-BUDGET-ANALYSIS.md` line 89; RF-01: the TDM conflict is in `docs/adr/035`); neither
  is quoted as consultant authority.

---

## Appendix — provenance

- `origin/main` = `1cab79261ba1296d756a97935cb2789c749e308d` (`git rev-parse origin/main`).
- PR #36 read without merging: `git fetch origin pull/36/head:pr36 && git show pr36:docs/analysis/PROGRAM-GAP-ANALYSIS-ROUND2.md`.
- Leak-test fix located: `git branch -a --contains 36993bf` → `fix/leak-temp-comp-sign`;
  `git merge-base --is-ancestor 36993bf origin/main` → **false** (not on main).
- Wing/hub courtyard counts: `grep -c '(footprint '` and a `CrtYd`-per-footprint parse of
  `tracker/hardware/wing_board/wing_board_v9.kicad_pcb` (12 / 0) and
  `tracker/hardware/hub_board_v9.kicad_pcb` (39 / 39).
- Every other row cites its source path inline.
