# ADR-037 — v9 MCU = ESP32-S3; SKY66112 front-end module omitted from v9

- Status: **Proposed** — the two decisions this ADR records were made by the operator
  on 2026-10-07; the *text* has not been accepted by a human, so it does not say Accepted.
- Date: 2026-10-07
- Decision owner: Felix (operator)
- Author: worker-adr (Hermes agent), promoting the operator's 2026-10-07 decisions into a
  decision record with the link-budget evidence that turns "leave out the FEM if its not
  needed" into a number.
- Related: ADR-001 (ESP32-C3, scope split here), ADR-005 (SKY66112 FEM, superseded in part
  here), ADR-006 (supercap power, stale load list), ADR-026 (dual-MCU, unchanged),
  ADR-028/ADR-031 (bench variants), ADR-029 (v9 flight board, D1 confirmed here),
  ADR-034/ADR-035 (radio architecture, unaffected).

> Operator decision, 2026-10-07 (verbatim): *"lets go with the S3, lets leave out the
> FEM if its not needed."*

---

## Context

Two decisions, one record, plus the evidence that makes "if its not needed" a number
rather than an assertion.

**Decision 1 (MCU).** v9 already had its MCU fixed by ADR-029 D1 to
`ESP32-S3-WROOM-1U-N8R8`, and ADR-029's rejected-alternatives table explicitly states
that the ESP32-C3 "remains the *bench* MCU (ADR-028, ADR-001) and that is not changed
here" (line 154). The operator's "lets go with the S3" therefore **confirms** ADR-029 D1;
it does **not** overturn ADR-001, which selects the ESP32-C3 for a different board.

**Decision 2 (FEM).** ADR-005 selected the Skyworks SKY66112-11 FEM (PA + LNA + SPDT)
for a 2.4 GHz front end. That FEM was sized for the *bare* LR2021 module (whose own
2.4 GHz ceiling is +12 dBm and which has no internal LNA). v9 flies the
`LoRa2021F33-2G4` module instead (ADR-029 D2), which has a **built-in PA and 2.4 GHz LNA**
(ADR-029 line 182: "no external FEM (SKY66112 removed)"). The operator's "leave out the
FEM if its not needed" is therefore a documentation/architecture cleanup confirming what
the board already does — it is **not** a board change.

---

## Decision

### D1 — MCU: v9 is `ESP32-S3-WROOM-1U-N8R8` (confirming ADR-029 D1)

v9 uses the ESP32-S3-WROOM-1U `-N8R8` variant. This **confirms ADR-029 D1** and its
pin plan (§4, `docs/adr/108-f33-sx1280-pin-plan.md`). ADR-001 (ESP32-C3) is **scoped to
the bench board** and is **not superseded** — it never claimed to govern the v9 flight
board, and ADR-029's own rejected-alternatives table already records the C3 as the bench
MCU. A one-line scope pointer is added to ADR-001 (see below); its argument is not
rewritten.

The consequence is honest and stated, not implied: the S3 changes the module footprint
and the pin map versus the C3. The v8i/v8h board carries the **C3** footprint, so **v9 is
a new board, not a re-label** (ADR-029 §4 pin plan). Commit `4059860` already pinned the
F33 and SX1280 off the S3's PSRAM pins
(`docs/adr/108-f33-sx1280-pin-plan.md`); that work stands and is referenced, not redone.

### D2 — FEM: the SKY66112 front-end module is omitted from v9

The SKY66112-11 is **omitted from v9**. This is consistent with the board of record and
with ADR-029 D2 (which already removed it). The FEM remains the **bench** front end if the
bare-module bench board still wants it (ADR-005, ADR-028 bench variants); it is
**superseded in part for v9** by ADR-005's own logic once the F33 module is the flight
part.

### D3 — The evidence that the FEM is not needed (the number)

The link-budget tool `tools/link_budget.py` was run for the v9 **2.4 GHz receive path**
(ground station transmits, the balloon's F33 module receives), at the established 300 km
slant range (`docs/link-budget.md`) and the ground-station EIRP already in
`docs/2G4-LINK-BUDGET-ANALYSIS.md` / the tool's `ground_station_2g4` scenario.

Observed tool output (`python3 tools/link_budget.py --freq 2400 --sf 12 --bw 125 --tx 27
--tx-ant 12 --rx-ant 10 --cable-loss 2 --dist 300 --payload 51`):

```
  EIRP:           37.0 dBm
  Distance:       300 km
  FSPL:           149.6 dB
  RX Power:       -102.6 dBm
```

The tool's own `LORA_SENSITIVITY` table reports SF12/BW125 = **-137.0 dBm**, giving a
+34.4 dB margin on its internal numbers. The *module's* documented 2.4 GHz sensitivity
(from ADR-029 D2, datasheet Rev 1.1) is **-136 dBm with the LNA in circuit** and
**-124 dBm with the LNA bypassed** (`DIO5` LOW costs 12 dB, ADR-029 lines 194/219). The
FEM's own LNA (ADR-005) is +14 dB gain / 1.8 dB noise figure.

| RX front end | Sensitivity (cited) | Margin vs -102.6 dBm |
|---|---|---|
| **With LNA in circuit** (F33 internal, `DIO5` HIGH) | -136 dBm (ADR-029) | **+33.4 dB** |
| **Without LNA** (bypass, `DIO5` LOW) | -124 dBm (ADR-029) | **+21.4 dB** |

**Verdict: adequate without the FEM.** Even with *no* LNA at all the v9 2.4 GHz receive
path closes the 300 km link with **+21.4 dB** of margin; with the F33's own internal LNA
in circuit it is **+33.4 dB**. The external SKY66112 LNA (a further +14 dB / 1.8 dB NF)
is therefore **not needed** — the module's built-in LNA already delivers -136 dBm, and
an external LNA in front of an already-low-NF front end cannot improve a system already
at its own floor. The operator's conditional ("if its not needed") resolves to **it is
not needed**, and this ADR records the margin as the justification rather than asserting
it.

> **Noise-figure honesty.** This ADR cites the module sensitivity (-136/-124 dBm, ADR-029)
> and the FEM LNA gain/NF (+14 dB / 1.8 dB, ADR-005) directly from those documents. It
> does **not** assert a numeric cascade noise figure for the F33's own front end — no NF
> number for the F33 receiver is stated in the committed docs, so none is invented here.
> The margin is computed from sensitivity, which is the documented, citable quantity.

---

## Consequences (stated honestly)

1. **The S3 changes footprint and pin map vs the C3.** The v8i/v8h board carries the C3
   footprint, so v9 is a new board, not a re-label (ADR-029 §4). The `-N8R8` part also
   consumes IO35/36/37 to octal PSRAM (ADR-029 D1.1).
2. **Commit `4059860` already pinned the F33 and SX1280 off the S3's PSRAM pins**
   (`docs/adr/108-f33-sx1280-pin-plan.md`). That work stands; it is referenced, not redone.
3. **ADR-006's load list is stale.** ADR-006 line 32 lists the SKY66112 in the power
   architecture chain (`ESP32-C3 + LR2021 + SKY66112 + BMP280`). With the FEM omitted from
   v9, that list contradicts this ADR. A pointer is added to ADR-006 below; a full re-draw
   of the power chain is left as a follow-up (see open items).
4. **Open item — do not decide here.** ADR-029 notes the S3's own Wi-Fi/BT is 2.4 GHz at
   +20 dBm on the same board, ~2 cm from the module. If that on-die radio is usable for
   config/telemetry, someone should ask whether a separate 2.4 GHz receiver is still
   necessary at all. Recorded, not decided.
5. **Open item — unchanged, not a new decision.** ADR-026 (dual-MCU: RP2040 + ESP32-C3)
   is not adopted for v9; choosing the single S3 leaves that unchanged. Recorded as
   "unchanged by this decision".
6. **Evidence correction (re-verified, not trusted).** The brief that seeded this ADR
   cited `tracker/hardware/output/v8i_krt_gnss.kicad_pcb` and
   `tracker/hardware/schematics/flight_board/v_c3_flight.kicad_sch`. Neither path exists
   in this tree. Re-verified directly:
   - The board of record (ADR-029) is `tracker/hardware/output/v8h_krt_u2_lora2021.kicad_pcb`;
     `grep -c SKY66112` on it returns **0**.
   - `tracker/hardware/schematics/v_c3_flight.kicad_sch` contains **2** occurrences of
     `SKY66112`, both as the value string `SKY66112 (opt)` — an *optional placeholder*, not
     a mandatory fitted part. This is consistent with ADR-029 D8 (the FEM is needed only
     for the bare-module fallback and is depopulated when the F33 flies).
   - SKY66112 still appears in **19** files under `docs/` (6 in `docs/adr/`), including
     `005`, `006`, `028`, `029`, `034`, `035`, `docs/link-budget.md`, `docs/power-budget.md`.

---

## Relationship to standing decisions

- **ADR-001 (ESP32-C3):** **scope split, not superseded.** ADR-001 selects the C3 for the
  bench board and is unchanged for that board; a one-line pointer now records that scope.
- **ADR-005 (SKY66112 FEM):** **superseded in part for v9.** The FEM stays as the bench
  front end; it is omitted from the v9 flight board. Pointer added.
- **ADR-006 (supercap power):** **stale load list.** Its power-architecture chain names the
  SKY66112; pointer added, full re-draw left as follow-up.
- **ADR-026 (dual-MCU):** **unchanged by this decision** (single S3, no RP2040).
- **ADR-028 / ADR-031 (bench variants / bring-up):** unaffected; the bench board (C3) and
  the staged-population plan stand.
- **ADR-029 (v9 flight board):** **D1 confirmed** (MCU = ESP32-S3-WROOM-1U-N8R8); the pin
  plan (commit `4059860`) stands.
- **ADR-034 / ADR-035 (433 TX / 2.4 GHz RX split, TDM schedule):** **unaffected.** This ADR
  does not alter the radio architecture or the schedule.

---

## Follow-up cleanup (do not rewrite the docs, list them)

The 19 `docs/` files that still mention SKY66112 (6 of them ADRs) should eventually be
reconciled against the FEM omission. Only the three ADR pointers above are made now; the
remaining files (`docs/link-budget.md`, `docs/power-budget.md`, and the rest) are a
follow-up documentation cleanup item, not part of this ADR.
