# ADR-036 — Energy policy: burst-sized storage, daylight-only TX

- Status: **Proposed** — the *decision* this ADR records (the operator's energy policy)
  was given by the operator on 2026-10-07; the *text* has not been accepted by a human,
  so it does not say Accepted.
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: worker-balloon (Hermes agent), promoting the operator's 2026-10-07 energy-policy
  decision into a decision record.
- Related: ADR-006 (`docs/adr/006-supercapacitor-power.md`, the power architecture this
  ADR amends **in part**), ADR-035 (`docs/adr/035-tdm-radio-schedule.md`, whose D7
  energy-opportunistic TX hook this ADR promotes into policy), ADR-029
  (`docs/adr/029-dual-band-flight-board.md`, item O5 / the 5 V rail, still open),
  ADR-034 (`docs/adr/034-radio-band-split-433-tx-2g4-rx.md`, the band split whose TX
  burst this policy gates).
- Related artefacts in this repo: `docs/adr/006-supercapacitor-power.md`,
  `docs/adr/035-tdm-radio-schedule.md`, `docs/adr/029-dual-band-flight-board.md`,
  `docs/adr/034-radio-band-split-433-tx-2g4-rx.md`.

> Numbering note: next-free-number check performed on this branch (recorded at the
> bottom of this file). 036 was selected because 033 is claimed elsewhere in the tree
> (`docs/adr/033-giftwrap-single-construction-path.md` on an unmerged branch), 034 and
> 035 are taken on `adr/radioband-tdm`, and no `036-*` file exists on any branch
> inspected.

---

## Context

The operator's verbatim intent, 2026-10-07 (Felix / c08r4d0r):

> "yes I'm fine with no night Tx. Please lock this in as an ADR"

This was given in response to the framing: *storage sized to one burst instead of the
mission; the cost being no slow LoRa SF12 downlink and no night/shadow TX.*

ADR-006 records the power architecture as a **1.65 F @ 5.4 V** supercap bank (2x AVX SCC
3.3 F 2.7 V in series) fed by a 4-wings-x-3-cells, 6.0 V / 400 mA / 2.4 W peak solar
array, buffering the payload through a TPS7A02 3.3 V LDO. Its stated rationale is that
no battery works at -60 C. That record sized the bank implicitly toward **carrying the
payload through the mission**. This ADR records the operator's decision that the bank is
sized to **one transmission burst** instead, and that TX is **energy-gated and
daylight-only**.

### What this changes relative to ADR-006 (stated, not silent)

- **The storage is no longer mission-sized.** The 1.65 F bank's role changes from "carry
  the payload through darkness" to "hold the PA's peak during one TX burst". ADR-006's
  *solar architecture* — the 4 wings x 3 cells, 6.0 V, ~2.4 W peak array, the Schottky
  diode, and the TPS7A02 LDO — is **not** changed by this ADR and remains in force. A
  reader must not conclude the wings were removed.
- **TX becomes daylight-only.** The system does not transmit between dusk and dawn, and
  does not transmit in shadow or at low illumination.
- **Night deep sleep becomes mandatory.** If the payload does not transmit at night, it
  must also not burn the night's budget: the night is spent in deep sleep, or the
  (burst-sized) buffer cannot be relied on at all.

---

## Decision

**TX is energy-gated and daylight-only. There is no night downlink. Storage is sized to
one burst, not to the mission.**

Sub-parts, all of which the operator accepted together:

1. **No night TX.** The system does not transmit between dusk and dawn, and does not
   transmit in shadow or at low illumination.
2. **Storage sized to a burst, not to the mission.** The buffer exists to hold the PA's
   peak during one transmission, not to carry the payload through darkness. This amends
   ADR-006's 1.65 F bank (see relationship section).
3. **Cold start at dawn is accepted.** With a supercap the payload may deep-discharge to
   zero overnight and cold-boot when the array re-lights. This is only possible
   *because* the storage is a supercap: a Li-ion cell destroyed by deep discharge could
   not be treated this way. This reinforces ADR-006's supercap-over-battery rationale
   rather than contradicting it.
4. **Night sleep is mandatory.** If the payload does not transmit at night, it must also
   not burn the night's budget: the night must be spent in deep sleep, or the buffer
   cannot be relied on at all. Any night housekeeping load must be handled by deep sleep,
   not by carrying a bigger bank.

### The gate condition

TX may be keyed only when **stored energy >= the burst requirement** AND (for any slow
mode) **illumination is sufficient to recharge**. This is the "energy-opportunistic TX
hook" that ADR-035 D7 already records as a hook; this ADR turns it into the actual
policy.

### What is NOT changed

The **solar array itself** — ADR-006's 4 wings x 3 cells, 6 V, ~2.4 W peak — remains.
The array must still cover the **average** load and recharge the (now smaller) buffer.
State this explicitly so a reader does not conclude the wings were removed.

---

## Consequences (stated honestly, not hidden)

- **Telemetry gaps overnight and in shadow.** The ground segment must expect long
  periods with no downlink. There is no night downlink and no shadow downlink by
  decision, not by accident.
- **The flight recorder becomes the primary evidence source.** With no night downlink,
  the on-board log — the ESP32-S3's 8 MB PSRAM / flash logging rationale recorded in
  ADR-029 D1 item 3 — is what survives. Recovery must be planned accordingly.
- **A night gap in the LOG may be a bigger loss than the night gap in TX.** This is the
  real risk, and it is recorded as an **open item** (below), with the deciding quantity:
  the payload's deep-sleep current in µA. The arithmetic scale: at 1 mW of night
  housekeeping, 10 h = 36 J (a multi-farad bank — contradicting the mass goal); at
  100 µW, 10 h = 3.6 J (~0.3 F); at 10 µA-level sleep, the surviving-log question is
  decided by firmware, not by the capacitor. This ADR does **not** resolve it; it names
  the measurement that would (see open items).
- **GNSS cold start cost at dawn.** Losing power overnight loses almanac/time, so the
  first fix after sunrise is slower. This is an accepted cost, not a hidden one.

---

## Relationship to standing decisions

### Amended in part

- **ADR-006 `006-supercapacitor-power.md`: "Akzeptiert" (German) — the 1.65 F bank is
  amended in part.** The bank (2x AVX SCC 3.3 F 2.7 V series = 1.65 F @ 5.4 V) is now
  sized to a burst, not to the mission. ADR-006's solar architecture (4 wings x 3 cells,
  6.0 V / 400 mA / 2.4 W peak, Schottky diode, TPS7A02 LDO) stands unchanged. A
  one-line pointer is added to ADR-006; ADR-006 is **not** rewritten.

### Promoted from hook to policy

- **ADR-035 `035-tdm-radio-schedule.md`: "Proposed" — D7 energy-opportunistic TX.** This
  ADR promotes ADR-035's D7 "energy-opportunistic TX" hook from a recorded hook to the
  recorded policy. The TDM schedule itself is **not** restated here; it is the schedule
  this policy gates.

### Referenced, still open

- **ADR-029 item O5 (the 5 V rail) — still open.** The bank sits at 5.4 V, so a 5 V feed
  for the F33's 2 W output may be a tap *before* the 3.3 V LDO rather than a new boost
  converter. This is recorded as an **option to evaluate**, NOT a decision. The 5 V rail
  question (carried from ADR-029 O5 into ADR-034) remains open.

---

## Open items (kept open, not resolved here)

- **Burst energy vs modulation mode — NOT decided.** The modulation mode decides the
  storage size, and it is not yet measured. Both cases: a 100-byte FLRC burst at
  2.6 Mbps is ~0.31 ms at ~6 W DC ~ **2 mJ** (a ~1 mF cap, ~0.2 g); a LoRa SF12/BW125
  packet is ~0.65 s ~ **4 J** (a bank in the tenths-of-a-farad range). This requires a
  bench measurement.
- **FLRC availability on the sub-GHz port of the F33 — UNVERIFIED.** Must be checked
  before FLRC is used as a design commitment for the burst-energy assumption above.
- **Cold characterisation at -60 C — NOT done.** The chosen buffer must be characterised
  at -60 C (capacitance loss and ESR rise); a 25 C datasheet figure is not sufficient
  for a cold-soak mission.
- **Night sleep current — NOT measured.** The payload's deep-sleep current in µA is the
  deciding quantity for whether the night LOG survives. At 10 µA-level sleep the
  surviving-log question is decided by firmware, not by the capacitor. The measurement
  that would decide it is the payload's actual deep-sleep current.

---

## What would falsify this

- A bench measurement showing the F33's sub-GHz port cannot run FLRC at a rate that
  makes the burst energy small (2 mJ-class) would force the storage size back toward the
  tenths-of-a-farad LoRa case, reopening "burst-sized vs mission-sized" storage.
- A cold-soak measurement at -60 C showing capacitance loss / ESR rise so severe that a
  burst-sized cap cannot deliver one TX burst would reopen the buffer sizing.
- A night-sleep current measurement showing the payload cannot reach µA-level sleep
  (i.e. the night LOG cannot survive on firmware alone) would reopen the question of a
  night housekeeping budget.

---

## Next-free-number check (recorded)

Run on branch `adr/energy-policy` (base `697fb73`, tip of `adr/radioband-tdm`):

```
git ls-tree -r --name-only HEAD docs/adr            # in-tree: ... 031, 032, 034, 035; no 036
git log --all --oneline --name-only -- 'docs/adr/*' # all branches: 033-giftwrap... present; no 036/037/038
```

Known collisions checked: two files each claim 002, 017, 018, 019, 020, 025, 028, 029;
031, 032, 034, 035 are taken; 033 is used elsewhere (`033-giftwrap-single-construction-path.md`).
036 is free on every branch inspected; 037 and 038 are also free.
