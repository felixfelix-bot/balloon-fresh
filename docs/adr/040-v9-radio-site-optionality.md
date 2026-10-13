# ADR-040 — v9 dual radio-site optionality: one LP-or-HP variant site plus one LP-only site

- Status: **Proposed** — the *decision* this ADR records (the operator's optionality
  instruction) was given by the operator on 2026-10-07; the *text* has not been accepted
  by a human, so it does not say Accepted.
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: worker-balloon (Hermes agent), promoting the operator's instruction into a
  decision record and reconciling it against the existing v9 dual-LR design memo.
- Related: ADR-029 (`docs/adr/029-dual-band-flight-board.md`, the v9 board record),
  ADR-034 (`docs/adr/034-radio-band-split-433-tx-2g4-rx.md`, the band split),
  ADR-035 (`docs/adr/035-tdm-radio-schedule.md`, one-transmitter-at-a-time),
  ADR-036 (`docs/adr/036-energy-policy-burst-storage-daylight-only-tx.md`, night
  sleep-current budget), ADR-039 (licence-exempt 433.05–434.79 MHz design point —
  being written concurrently by another worker).
- Related artefacts in this repo:
  `docs/V9-DUAL-LR-DESIGN-MEMO.md` (branch `docs/v9-dual-lr`, tip `ad3b8ad`) —
  **this ADR is reconciled against it and does not silently contradict it**;
  `docs/f33-module/F33-LANDPATTERN-VERIFICATION.md` (branch `docs/f33-landpattern-verification`,
  tip `d983bab`);
  `docs/LR2021-LESSONS-2026-09.md` (branch `docs/lr2021-lessons`, tip `581b38b`);
  `docs/REGULATORY-AMATEUR-LICENCE.md` (branch `docs/regulatory-amateur`, tip `0f02f29d`);
  `docs/DUAL-VARIANT-DESIGN.md`, `docs/inventory.md`, `docs/power-budget.md`;
  `docs/V9-RADIO-SITE-MATRIX.md` (the per-config population/GPIO/rail/regulatory matrix,
  committed alongside this ADR).

> Numbering note: **040** was chosen. The next-free-number check run on this branch
> (recorded at the bottom of this file) finds **038 is the highest number committed to any
> inspected branch** (`adr/wifi-bt-disabled`), and **039 is being written concurrently by
> another worker** (the licence-exempt 433.05–434.79 MHz design point). No `040-*` file
> exists on any branch inspected, so 040 is free and is taken here.

---

## Context

The operator's verbatim intent, 2026-10-07 (Felix / c08r4d0r):

> "put solder pads on the back for another low power LR2021 so that we can choose between
> one low power LR2021 and a high power LR2021, or between two low power LR2021"

with the rationale:

> "we are anyway soldering the radios on manually ourselves, we might as well keep the
> optionality"

The interpretation recorded here (and reflected in the matrix): the v9 board carries **two
radio sites** on the back:

- **Site A — the "variant" site.** Accepts **either** the bare low-power `LoRa2021`
  (castellated, chip-only, ~160 mW) **or** the high-power `LoRa2021F33-2G4` (2 W PA + TCXO),
  **mutually exclusive, one at a time**.
- **Site B — the LP-only site.** Accepts only the bare low-power `LoRa2021`.

Both sites are **DNP by default**; the operator hand-solders whichever parts a given board
should carry. The two sites give four population configurations — `{LP}`, `{HP}`,
`{LP+LP}`, `{HP+LP}` — tabulated in `docs/V9-RADIO-SITE-MATRIX.md`.

---

## Decision

### D1 — Keep the pads: two sites, zero fab cost, mutual exclusivity is the point

The v9 board keeps **two** radio footprints on the back. This is the *optionality* decision;
it does **not** mandate a two-radio population, and it does **not** reopen the SX1280 or the
ADR-034 band split.

The **variant site (Site A)** deliberately exploits the geometry the dual-LR memo already
measured: the bare-module pad field lies **inside** the F33 pad ring, so a single footprint
region can accept either part. The memo recorded this as "mutually exclusive, not two usable
modules" (shared pad numbers include VCC). That mutual exclusivity is **exactly** what a
LP-or-HP *variant* slot wants — the two parts are alternatives, not simultaneous radios.
The memo's objection was to nesting as a way to get **simultaneous** dual-band operation,
which the variant slot does **not** claim. This distinction is made explicit here so the two
documents are not read as contradictory:

> **Memo said:** nesting = "mutually exclusive footprint option, not two usable modules" —
> true, and correct as a rejection of *simultaneous* two-module operation.
> **This ADR says:** agreed — the variant slot *is* mutually exclusive on purpose. It buys
> *choose-one* optionality (LP *or* HP at Site A), never *two-radios-on-one-pad-ring*.

**Zero fab cost** is the load-bearing premise of keeping both pads: the operator already
hand-solders the radios, so a second (or superset) copper footprint adds no assembly-line
cost and no extra BOM line until a part is actually fitted.

### D2 — Default population: LOW-POWER at both sites

The default population for a flight board is the **bare low-power `LoRa2021`**, not the F33.
Rationale, in priority order:

1. **The two-LP configuration delivers the ADR-034 goal without PA-table work.** One LP on
   433 MHz TX (the ADR-034 TX direction) + one LP on 2.4 GHz RX (the ADR-034 RX direction)
   gives the simultaneous 433-TX / 2.4-GHz-RX split ADR-034 wanted, for the cheapest possible
   rail and firmware cost. A plain module needs **no PA table and no RF-switch table**
   (chip-only RF — `docs/LR2021-LESSONS-2026-09.md` §"PA table" and §"Implications"). The F33
   requires `setRfSwitchTable()` with a dense DIO array ordered from DIO5, a 2.4 GHz LNA enable
   on DIO5 (LOW costs 12 dB sensitivity) and a sub-GHz PA enable on DIO6 — all of which is
   **avoided** when the default part is plain.
2. **The HP leg is currently unsolderable.** The repo F33 land pattern fails 0 of 18 pads
   against the vendor pad file (`docs/f33-module/F33-LANDPATTERN-VERIFICATION.md` — see
   prerequisite P1). Until that footprint is fixed, no F33 can be assembled, so the HP leg
   cannot be the default.
3. **The HP leg is dead weight under the licence-exempt regime.** The operator chose the
   licence-exempt 433.05–434.79 MHz band at ≤ 10 mW ERP (ADR-039, being written by another
   worker). A 2 W PA is unusable there. The HP leg is only meaningful under the operator's
   German amateur licence or on the ground station — see D4.

### D3 — The HP leg stays as an *option*, not a default: licensed operation or ground station

The F33's value is its **0.5 ppm TCXO** (`docs/LR2021-LESSONS-2026-09.md`: plain modules have
no TCXO/NTC; temperature drift at −44…−60 °C is an **open risk** that drifts a narrow-BW
signal out of channel) and its 2 W PA. Both matter only where:

- **licensed operation** is legal (amateur licence, D4), or
- the board is a **ground station / permanent repeater**, where mass and the licence-exempt
  ERP ceiling are irrelevant and the TCXO buys frequency stability that the plain module's
  crystal cannot (the fkallay1 field-proven recipe — `docs/LR2021-LESSONS-2026-09.md`).

Recorded so the F33 is not silently dropped from the board's future: the variant site keeps
it available for both of those uses.

### D4 — Legal regime is per-configuration (tabulated in the matrix)

The 2 W F33 is **not** legal in the licence-exempt 433.05–434.79 MHz regime (≤ 10 mW ERP,
ADR-039). It **is** legal under the operator's German amateur licence on 70 cm — AFuV Anlage
1 entry 18 (430–440 MHz): 750 W PEP Class A / 75 W PEP Class E; with the attendant duties that
the amateur service is **secondary** (must not harm military/radar primaries), that a
**callsign is required**, and that AFuV §16(7)–(8) **prohibits encryption** of the telemetry
(`docs/REGULATORY-AMATEUR-LICENCE.md`). The full per-config legal table is in
`docs/V9-RADIO-SITE-MATRIX.md` §"Legal regime per config".

---

## Prerequisites (recorded as NOT done, owned elsewhere)

- **P1 — the F33 land pattern is wrong and must be fixed before any `{HP}` or `{HP+LP}`
  population is assemblable.** `docs/f33-module/F33-LANDPATTERN-VERIFICATION.md` verdict:
  **FAIL — 0 of 18 pads coincide** with the vendor pad file; pad pitch is 2.0 mm in the repo
  footprint vs 3.9289 mm vendor, and the pattern is rotated 90°. **Another worker is fixing
  this now** (`fix/f33-landpattern-vendor`). This ADR records it as a **prerequisite**, not
  as done, and does not touch that branch.

## Open items (kept open, not resolved here)

- **O1 — the 5 V rail (carried from ADR-029 O5 into ADR-034).** The F33's 2 W / 33 dBm @433 is
  a 5 V figure; no 5 V rail exists on v9. Any `{HP}`/`{HP+LP}` population cannot reach its
  headline power until the rail is decided. Not resolved here.
- **O2 — plain-module temperature drift.** No TCXO/NTC on the bare part; −44…−60 °C drift out
  of channel at narrow BW is an open risk (`docs/LR2021-LESSONS-2026-09.md` §"Temperature
  drift"). The two-LP default therefore carries this risk in flight; the F33's TCXO is the
  escape hatch that the variant site preserves.
- **O3 — cross-border amateur operation.** Whether a German amateur licence covers an
  unmanned, automatically transmitting, airborne payload abroad is unsettled
  (`docs/REGULATORY-AMATEUR-LICENCE.md` §7, open item 1). Affects the `{HP}`/`{HP+LP}` legal
  case specifically.

---

## Constraints carried from the dual-LR memo (not re-derived, stated for traceability)

From `docs/V9-DUAL-LR-DESIGN-MEMO.md` §5 and §3, which this ADR **accepts** and re-uses:

- **Two F33 modules cannot fit** on the 55 × 45 mm v9 board: 39.6 × 21.6 mm each ≈ 79.2 mm of
  length before keep-outs, feeds and routing.
- **A genuinely independent second radio costs +4 GPIO** if it shares the existing SPI
  data/clock wires (CS + BUSY + RESET + IRQ/DIO), **or +7 GPIO** on a separate SPI master
  (adds SCK/MOSI/MISO).
- **The S3's two general SPI masters are already committed** — SPI2 to the F33 and SPI3 to the
  SX1280 — so the +7 independent-bus case is **not available** without a pin-reassignment
  decision; bus sharing (+4) is the only ready path.
- **The F33 rail delta** at its 5 V high-power point is up to **+0.8 A (868 TX) / +0.9 A
  (2.4 GHz TX)**. (Do **not** copy this figure to the *plain* modules — their rail delta is a
  separate, much smaller, repo-verified number; see the matrix.)
- **The nested bare-module pad field shares pad numbers including VCC** with the F33 ring, so
  the two cannot be powered independently when nested — this is *why* the variant site is
  choose-one, and is exactly the mutual-exclusivity this ADR wants.

## Next-free-number check (recorded)

Run on branch `adr/v9-radio-site-optionality` (base `2de3fa6` = `github/master`):

```bash
git ls-tree -r --name-only github/master docs/adr     # in-tree on trunk: ... up to 033
git for-each-ref --format='%(refname:short)' refs/remotes | grep -i adr
# highest ADR files found across all inspected branches:
#   036 energy-policy, 037 mcu-s3-no-fem, 038 wifi-bt-disabled  (no 039 anywhere)
```

038 is the highest committed number; 039 is reserved by a concurrently-written worker
(licence-exempt design point); **040 is free and taken here**.
